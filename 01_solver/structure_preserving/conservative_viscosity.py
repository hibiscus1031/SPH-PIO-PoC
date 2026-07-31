"""Pair-defined conservative and dissipative physical-viscosity force."""

from __future__ import annotations

import torch

from structure_preserving.conservative_pressure import (
    _particle_scalar,
    accumulate_pair_forces,
)
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    reverse_directed_edge_indices,
)


def viscosity_gamma(
    density_i: torch.Tensor,
    density_j: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
    radial_kernel_product: torch.Tensor,
    distance: torch.Tensor,
    support: torch.Tensor,
    *,
    regularization: float = 0.01,
) -> torch.Tensor:
    r"""Return symmetric nonnegative \(\Gamma_{ij}\)."""

    nu = torch.as_tensor(
        physical_viscosity,
        dtype=distance.dtype,
        device=distance.device,
    )
    if nu.numel() != 1:
        raise ValueError("physical viscosity must be scalar")
    if bool((~torch.isfinite(nu.detach())).any() or (nu.detach() < 0).any()):
        raise ValueError("physical viscosity must be finite and nonnegative")
    if bool(
        (~torch.isfinite(density_i.detach())).any()
        or (~torch.isfinite(density_j.detach())).any()
        or (density_i.detach() <= 0).any()
        or (density_j.detach() <= 0).any()
    ):
        raise ValueError("densities must be finite and positive")
    if bool(
        (~torch.isfinite(distance.detach())).any()
        or (distance.detach() < 0).any()
        or (~torch.isfinite(support.detach())).any()
        or (support.detach() <= 0).any()
        or (~torch.isfinite(radial_kernel_product.detach())).any()
        or (radial_kernel_product.detach() > 0).any()
    ):
        raise ValueError(
            "kernel geometry must be finite with r dot grad(W) <= 0"
        )
    denominator = distance.square() + (regularization * support).square()
    gamma = (
        -4.0
        * nu.reshape(())
        / (density_i + density_j)
        * radial_kernel_product
        / denominator
    )
    if bool((~torch.isfinite(gamma.detach())).any() or (gamma.detach() < 0).any()):
        raise ValueError("viscosity Gamma must be finite and nonnegative")
    return gamma


def viscosity_pair_force(
    mass_i: torch.Tensor,
    mass_j: torch.Tensor,
    velocity_i: torch.Tensor,
    velocity_j: torch.Tensor,
    gamma: torch.Tensor,
) -> torch.Tensor:
    return (
        mass_i * mass_j * gamma
    )[:, None] * (velocity_j - velocity_i)


def conservative_viscosity_pair_forces(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    velocity: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    count = neighborhood.particle_count
    masses = _particle_scalar(
        mass,
        count,
        neighborhood.distance,
        name="mass",
    )
    densities = _particle_scalar(
        density,
        count,
        neighborhood.distance,
        name="density",
    )
    if velocity.shape != (count, 2):
        raise ValueError("velocity must have shape [particles, 2]")
    if bool((densities.detach() <= 0).any()):
        raise ValueError("density must be positive")
    selected = neighborhood.unordered
    i = neighborhood.row[selected]
    j = neighborhood.col[selected]
    gradient = edge_kernel_gradients(neighborhood)[selected]
    displacement = neighborhood.displacement[selected]
    radial = torch.einsum("nd,nd->n", displacement, gradient)
    gamma = viscosity_gamma(
        densities[i],
        densities[j],
        physical_viscosity,
        radial,
        neighborhood.distance[selected],
        neighborhood.edge_support[selected],
    )
    pair_force = viscosity_pair_force(
        masses[i],
        masses[j],
        velocity[i],
        velocity[j],
        gamma,
    )
    return i, j, pair_force, gamma


def conservative_viscosity_forces(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    velocity: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
) -> torch.Tensor:
    i, j, pair_force, _ = conservative_viscosity_pair_forces(
        neighborhood,
        mass=mass,
        density=density,
        velocity=velocity,
        physical_viscosity=physical_viscosity,
    )
    return accumulate_pair_forces(
        neighborhood.particle_count,
        i,
        j,
        pair_force,
    )


def conservative_viscosity_acceleration(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    velocity: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
) -> torch.Tensor:
    masses = _particle_scalar(
        mass,
        neighborhood.particle_count,
        neighborhood.distance,
        name="mass",
    )
    force = conservative_viscosity_forces(
        neighborhood,
        mass=masses,
        density=density,
        velocity=velocity,
        physical_viscosity=physical_viscosity,
    )
    return force / masses[:, None]


def stage01b_style_generic_acceleration(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    velocity: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
    regularization: float = 1.0e-8,
) -> torch.Tensor:
    """Reproduce the frozen Stage 01B one-sided generic-Laplacian formula."""

    count = neighborhood.particle_count
    masses = _particle_scalar(
        mass,
        count,
        neighborhood.distance,
        name="mass",
    )
    densities = _particle_scalar(
        density,
        count,
        neighborhood.distance,
        name="density",
    )
    nu = torch.as_tensor(
        physical_viscosity,
        dtype=velocity.dtype,
        device=velocity.device,
    ).reshape(())
    gradient = edge_kernel_gradients(neighborhood)
    radial = torch.einsum(
        "nd,nd->n",
        neighborhood.displacement,
        gradient,
    )
    regularized_distance = (
        neighborhood.distance
        + regularization
        * neighborhood.particle_support[neighborhood.row]
    )
    coefficient = (
        -2.0
        * nu
        * masses[neighborhood.col]
        / densities[neighborhood.col]
        * radial
        / regularized_distance.square()
    )
    coefficient = torch.where(
        neighborhood.row != neighborhood.col,
        coefficient,
        torch.zeros_like(coefficient),
    )
    contribution = coefficient[:, None] * (
        velocity[neighborhood.col] - velocity[neighborhood.row]
    )
    return scatter_sum(
        neighborhood.row,
        contribution,
        count,
    )


def viscosity_conservation_metrics(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    velocity: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
) -> dict[str, float]:
    count = neighborhood.particle_count
    masses = _particle_scalar(
        mass,
        count,
        neighborhood.distance,
        name="mass",
    )
    densities = _particle_scalar(
        density,
        count,
        neighborhood.distance,
        name="density",
    )
    i, j, force_ij, gamma_ij = conservative_viscosity_pair_forces(
        neighborhood,
        mass=masses,
        density=density,
        velocity=velocity,
        physical_viscosity=physical_viscosity,
    )
    reverse = reverse_directed_edge_indices(
        neighborhood
    )[neighborhood.unordered]
    reverse_gradient = edge_kernel_gradients(neighborhood)[reverse]
    reverse_displacement = neighborhood.displacement[reverse]
    reverse_radial = torch.einsum(
        "nd,nd->n",
        reverse_displacement,
        reverse_gradient,
    )
    gamma_ji = viscosity_gamma(
        densities[j],
        densities[i],
        physical_viscosity,
        reverse_radial,
        neighborhood.distance[reverse],
        neighborhood.edge_support[reverse],
    )
    force_ji = viscosity_pair_force(
        masses[j],
        masses[i],
        velocity[j],
        velocity[i],
        gamma_ji,
    )
    pair_residual = force_ij + force_ji
    particle_force = accumulate_pair_forces(count, i, j, force_ij)
    total_force = particle_force.sum(dim=0)
    force_scale = 2.0 * torch.linalg.vector_norm(
        force_ij,
        dim=-1,
    ).sum()
    tiny = torch.finfo(force_ij.dtype).tiny
    pair_scale = torch.linalg.vector_norm(force_ij, dim=-1).max()
    pair_residual_norm = torch.linalg.vector_norm(
        pair_residual,
        dim=-1,
    )
    accumulated_power = torch.sum(velocity * particle_force)
    direct_power = -torch.sum(
        masses[i]
        * masses[j]
        * gamma_ij
        * torch.sum((velocity[j] - velocity[i]).square(), dim=-1)
    )
    displacement = neighborhood.displacement[neighborhood.unordered]
    pair_torque = (
        displacement[:, 0] * force_ij[:, 1]
        - displacement[:, 1] * force_ij[:, 0]
    )
    return {
        "gamma_minimum": float(torch.minimum(gamma_ij, gamma_ji).min()),
        "gamma_maximum": float(torch.maximum(gamma_ij, gamma_ji).max()),
        "relative_gamma_symmetry_residual": float(
            (gamma_ij - gamma_ji).abs().max()
            / (
                torch.maximum(gamma_ij.abs(), gamma_ji.abs()).max()
                + tiny
            )
        ),
        "pair_force_residual_linf": float(pair_residual_norm.max()),
        "relative_pair_force_residual": float(
            pair_residual_norm.max() / (pair_scale + tiny)
        ),
        "total_internal_force": float(
            torch.linalg.vector_norm(total_force)
        ),
        "relative_total_internal_force": float(
            torch.linalg.vector_norm(total_force) / (force_scale + tiny)
        ),
        "accumulated_viscous_power": float(accumulated_power),
        "pair_direct_viscous_power": float(direct_power),
        "power_identity_absolute_difference": float(
            (accumulated_power - direct_power).abs()
        ),
        "minimum_image_pair_torque_linf": float(pair_torque.abs().max()),
    }
