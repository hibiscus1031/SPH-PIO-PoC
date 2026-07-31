"""Native Wendland kernel and consistency-correction candidates."""

from __future__ import annotations

import math

import torch

from structure_preserving.neighborhood import PeriodicNeighborhood


def _particle_values(
    value: float | torch.Tensor,
    count: int,
    reference: torch.Tensor,
) -> torch.Tensor:
    if torch.is_tensor(value):
        result = value.to(dtype=reference.dtype, device=reference.device)
        if result.numel() == 1:
            return result.reshape(1).expand(count)
        if result.shape != (count,):
            raise ValueError("particle scalar must have shape [particles]")
        return result
    return torch.full(
        (count,),
        float(value),
        dtype=reference.dtype,
        device=reference.device,
    )


def scatter_sum(
    row: torch.Tensor,
    values: torch.Tensor,
    particle_count: int,
) -> torch.Tensor:
    output = torch.zeros(
        (particle_count, *values.shape[1:]),
        dtype=values.dtype,
        device=values.device,
    )
    output.index_add_(0, row, values)
    return output


def wendland_c4_shape(q: torch.Tensor) -> torch.Tensor:
    retained = torch.clamp(1.0 - q, min=0.0)
    return retained.pow(6) * (1.0 + 6.0 * q + (35.0 / 3.0) * q.square())


def wendland_c4_shape_derivative(q: torch.Tensor) -> torch.Tensor:
    retained = torch.clamp(1.0 - q, min=0.0)
    return -(56.0 / 3.0) * q * (5.0 * q + 1.0) * retained.pow(5)


def edge_kernel_values(
    neighborhood: PeriodicNeighborhood,
) -> torch.Tensor:
    q = neighborhood.distance / neighborhood.edge_support
    normalization = 9.0 / (
        math.pi * neighborhood.edge_support.square()
    )
    return normalization * wendland_c4_shape(q)


def edge_kernel_gradients(
    neighborhood: PeriodicNeighborhood,
) -> torch.Tensor:
    """Return the radial gradient with respect to particle ``i``."""

    q = neighborhood.distance / neighborhood.edge_support
    radial_derivative = (
        9.0
        / math.pi
        * wendland_c4_shape_derivative(q)
        / neighborhood.edge_support.pow(3)
    )
    inverse_distance = torch.where(
        neighborhood.distance > 0,
        neighborhood.distance.reciprocal(),
        torch.zeros_like(neighborhood.distance),
    )
    direction = neighborhood.displacement * inverse_distance[:, None]
    return radial_derivative[:, None] * direction


def raw_edge_weights(
    neighborhood: PeriodicNeighborhood,
    particle_volume: float | torch.Tensor,
) -> torch.Tensor:
    volumes = _particle_values(
        particle_volume,
        neighborhood.particle_count,
        neighborhood.distance,
    )
    return volumes[neighborhood.col] * edge_kernel_values(neighborhood)


def raw_kernel_moments(
    neighborhood: PeriodicNeighborhood,
    particle_volume: float | torch.Tensor,
) -> dict[str, torch.Tensor]:
    weights = raw_edge_weights(neighborhood, particle_volume)
    displacement_j_minus_i = -neighborhood.displacement
    return {
        "s0": scatter_sum(
            neighborhood.row,
            weights,
            neighborhood.particle_count,
        ),
        "s1": scatter_sum(
            neighborhood.row,
            weights[:, None] * displacement_j_minus_i,
            neighborhood.particle_count,
        ),
    }


def shepard_edge_weights(
    neighborhood: PeriodicNeighborhood,
    particle_volume: float | torch.Tensor,
) -> torch.Tensor:
    raw = raw_edge_weights(neighborhood, particle_volume)
    denominator = scatter_sum(
        neighborhood.row,
        raw,
        neighborhood.particle_count,
    )
    return raw / denominator[neighborhood.row]


def linear_reproducing_edge_weights(
    neighborhood: PeriodicNeighborhood,
    particle_volume: float | torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return RKPM-style weights reproducing constants and linear fields."""

    base = raw_edge_weights(neighborhood, particle_volume)
    displacement = -neighborhood.displacement
    basis = torch.cat(
        (
            torch.ones_like(base)[:, None],
            displacement,
        ),
        dim=1,
    )
    moment = scatter_sum(
        neighborhood.row,
        base[:, None, None] * basis[:, :, None] * basis[:, None, :],
        neighborhood.particle_count,
    )
    target = torch.zeros(
        (neighborhood.particle_count, 3),
        dtype=base.dtype,
        device=base.device,
    )
    target[:, 0] = 1.0
    coefficients = torch.linalg.solve(moment, target)
    correction = torch.einsum(
        "ni,ni->n",
        basis,
        coefficients[neighborhood.row],
    )
    return base * correction, moment


def moments_from_edge_weights(
    neighborhood: PeriodicNeighborhood,
    edge_weights: torch.Tensor,
) -> dict[str, torch.Tensor]:
    displacement = -neighborhood.displacement
    return {
        "s0": scatter_sum(
            neighborhood.row,
            edge_weights,
            neighborhood.particle_count,
        ),
        "s1": scatter_sum(
            neighborhood.row,
            edge_weights[:, None] * displacement,
            neighborhood.particle_count,
        ),
    }


def interpolate_from_edge_weights(
    neighborhood: PeriodicNeighborhood,
    edge_weights: torch.Tensor,
    quantity: torch.Tensor,
) -> torch.Tensor:
    factor = edge_weights
    while factor.ndim < quantity[neighborhood.col].ndim:
        factor = factor.unsqueeze(-1)
    return scatter_sum(
        neighborhood.row,
        factor * quantity[neighborhood.col],
        neighborhood.particle_count,
    )


def raw_gradient(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> torch.Tensor:
    volumes = _particle_values(
        particle_volume,
        neighborhood.particle_count,
        neighborhood.distance,
    )
    difference = (
        quantity[neighborhood.col] - quantity[neighborhood.row]
    )
    gradient = edge_kernel_gradients(neighborhood)
    factor = volumes[neighborhood.col]
    if quantity.ndim == 1:
        contribution = factor[:, None] * difference[:, None] * gradient
    elif quantity.ndim == 2:
        contribution = (
            factor[:, None, None]
            * difference[:, :, None]
            * gradient[:, None, :]
        )
    else:
        raise ValueError("quantity must be scalar or vector per particle")
    return scatter_sum(
        neighborhood.row,
        contribution,
        neighborhood.particle_count,
    )


def shepard_gradient(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> torch.Tensor:
    moments = raw_kernel_moments(neighborhood, particle_volume)
    raw = raw_gradient(neighborhood, quantity, particle_volume)
    denominator = moments["s0"]
    while denominator.ndim < raw.ndim:
        denominator = denominator.unsqueeze(-1)
    return raw / denominator


def first_order_corrected_gradient(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply a local first-order correction matrix to the raw gradient."""

    volumes = _particle_values(
        particle_volume,
        neighborhood.particle_count,
        neighborhood.distance,
    )
    gradient = edge_kernel_gradients(neighborhood)
    displacement = -neighborhood.displacement
    matrix = scatter_sum(
        neighborhood.row,
        (
            volumes[neighborhood.col, None, None]
            * gradient[:, :, None]
            * displacement[:, None, :]
        ),
        neighborhood.particle_count,
    )
    raw = raw_gradient(neighborhood, quantity, particle_volume)
    if raw.ndim == 2:
        corrected = torch.linalg.solve(matrix, raw)
    else:
        corrected = torch.linalg.solve(
            matrix,
            raw.transpose(1, 2),
        ).transpose(1, 2)
    return corrected, matrix


def _brookshaw_edge_coefficient(
    neighborhood: PeriodicNeighborhood,
    particle_volume: float | torch.Tensor,
    *,
    regularization: float = 0.01,
) -> torch.Tensor:
    volumes = _particle_values(
        particle_volume,
        neighborhood.particle_count,
        neighborhood.distance,
    )
    gradient = edge_kernel_gradients(neighborhood)
    radial = torch.einsum(
        "nd,nd->n",
        neighborhood.displacement,
        gradient,
    )
    denominator = neighborhood.distance.square() + (
        regularization * neighborhood.edge_support
    ).square()
    coefficient = (
        -2.0
        * volumes[neighborhood.col]
        * radial
        / denominator
    )
    return torch.where(
        neighborhood.row != neighborhood.col,
        coefficient,
        torch.zeros_like(coefficient),
    )


def raw_laplacian(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> torch.Tensor:
    coefficient = _brookshaw_edge_coefficient(
        neighborhood,
        particle_volume,
    )
    difference = (
        quantity[neighborhood.col] - quantity[neighborhood.row]
    )
    factor = coefficient
    while factor.ndim < difference.ndim:
        factor = factor.unsqueeze(-1)
    return scatter_sum(
        neighborhood.row,
        factor * difference,
        neighborhood.particle_count,
    )


def shepard_laplacian(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> torch.Tensor:
    raw = raw_laplacian(neighborhood, quantity, particle_volume)
    denominator = raw_kernel_moments(
        neighborhood,
        particle_volume,
    )["s0"]
    while denominator.ndim < raw.ndim:
        denominator = denominator.unsqueeze(-1)
    return raw / denominator


def moment_corrected_laplacian(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Calibrate Brookshaw's operator on ``0.5*|x_j-x_i|^2``."""

    coefficient = _brookshaw_edge_coefficient(
        neighborhood,
        particle_volume,
    )
    quadratic = 0.5 * neighborhood.distance.square()
    response = scatter_sum(
        neighborhood.row,
        coefficient * quadratic,
        neighborhood.particle_count,
    )
    correction = 2.0 / response
    raw = raw_laplacian(neighborhood, quantity, particle_volume)
    factor = correction
    while factor.ndim < raw.ndim:
        factor = factor.unsqueeze(-1)
    return factor * raw, response


def quadratic_weighted_least_squares(
    neighborhood: PeriodicNeighborhood,
    quantity: torch.Tensor,
    particle_volume: float | torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Fit a local quadratic polynomial and return gradient and Laplacian."""

    base_weight = raw_edge_weights(neighborhood, particle_volume)
    scaled = -neighborhood.displacement / neighborhood.edge_support[:, None]
    basis = torch.stack(
        (
            scaled[:, 0],
            scaled[:, 1],
            0.5 * scaled[:, 0].square(),
            scaled[:, 0] * scaled[:, 1],
            0.5 * scaled[:, 1].square(),
        ),
        dim=1,
    )
    normal = scatter_sum(
        neighborhood.row,
        (
            base_weight[:, None, None]
            * basis[:, :, None]
            * basis[:, None, :]
        ),
        neighborhood.particle_count,
    )
    difference = (
        quantity[neighborhood.col] - quantity[neighborhood.row]
    )
    if quantity.ndim == 1:
        right_hand_side = scatter_sum(
            neighborhood.row,
            base_weight[:, None] * basis * difference[:, None],
            neighborhood.particle_count,
        )
        coefficients = torch.linalg.solve(normal, right_hand_side)
        support = neighborhood.particle_support
        gradient = coefficients[:, :2] / support[:, None]
        laplacian = (
            coefficients[:, 2] + coefficients[:, 4]
        ) / support.square()
    elif quantity.ndim == 2:
        right_hand_side = scatter_sum(
            neighborhood.row,
            (
                base_weight[:, None, None]
                * basis[:, :, None]
                * difference[:, None, :]
            ),
            neighborhood.particle_count,
        )
        coefficients = torch.linalg.solve(normal, right_hand_side)
        support = neighborhood.particle_support
        gradient = (
            coefficients[:, :2, :].transpose(1, 2)
            / support[:, None, None]
        )
        laplacian = (
            coefficients[:, 2, :] + coefficients[:, 4, :]
        ) / support[:, None].square()
    else:
        raise ValueError("quantity must be scalar or vector per particle")
    return gradient, laplacian, normal


def divergence_from_vector_gradient(gradient: torch.Tensor) -> torch.Tensor:
    if gradient.ndim != 3 or gradient.shape[1:] != (2, 2):
        raise ValueError("vector gradient must have shape [particles, 2, 2]")
    return gradient[:, 0, 0] + gradient[:, 1, 1]
