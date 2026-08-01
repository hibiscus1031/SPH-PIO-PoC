"""Independent dense periodic all-pairs WCSPH value path for N16 audits."""

from __future__ import annotations

from dataclasses import dataclass
import math
import torch

from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS
from structure_preserving.conservative_pressure import pressure_pair_force
from structure_preserving.conservative_viscosity import viscosity_gamma, viscosity_pair_force
from structure_preserving.kernels import wendland_c4_shape, wendland_c4_shape_derivative


@dataclass(frozen=True)
class DenseEvaluation:
    density: torch.Tensor
    pressure: torch.Tensor
    pressure_acceleration: torch.Tensor
    viscosity_acceleration: torch.Tensor
    source_acceleration: torch.Tensor
    total_acceleration: torch.Tensor
    displacement: torch.Tensor
    distance: torch.Tensor
    support: torch.Tensor
    included: torch.Tensor


def dense_pair_acceleration_contributions(
    evaluation: DenseEvaluation,
    i: int,
    j: int,
    masses: torch.Tensor,
    velocities: torch.Tensor,
    physical_viscosity: float = 0.02,
) -> dict[str, torch.Tensor]:
    """Return force-on-i accelerations for one unordered dense pair."""

    index_i = torch.tensor([i], dtype=torch.int64)
    index_j = torch.tensor([j], dtype=torch.int64)
    if not bool(evaluation.included[i, j]):
        zero = torch.zeros(2, dtype=masses.dtype)
        return {"pressure": zero, "viscosity": zero, "total": zero}
    pressure = pressure_pair_force(
        masses[index_i], masses[index_j], evaluation.density[index_i],
        evaluation.density[index_j], evaluation.pressure[index_i],
        evaluation.pressure[index_j],
        _gradient_from_evaluation(evaluation, i, j).reshape(1, 2),
    )[0] / masses[i]
    displacement = evaluation.displacement[i, j]
    gradient = _gradient_from_evaluation(evaluation, i, j)
    radial = torch.sum(displacement * gradient).reshape(1)
    gamma = viscosity_gamma(
        evaluation.density[index_i], evaluation.density[index_j],
        physical_viscosity, radial, evaluation.distance[i, j].reshape(1),
        evaluation.support[i, j].reshape(1),
    )
    viscosity = viscosity_pair_force(
        masses[index_i], masses[index_j], velocities[index_i],
        velocities[index_j], gamma,
    )[0] / masses[i]
    return {"pressure": pressure, "viscosity": viscosity, "total": pressure + viscosity}


def _gradient_from_evaluation(evaluation: DenseEvaluation, i: int, j: int) -> torch.Tensor:
    q = evaluation.distance[i, j] / evaluation.support[i, j]
    if not bool(evaluation.included[i, j]):
        return torch.zeros(2, dtype=evaluation.distance.dtype)
    radial = (
        9.0 / math.pi * wendland_c4_shape_derivative(q)
        / evaluation.support[i, j].pow(3)
    )
    if not bool(evaluation.distance[i, j] > 0.0):
        return torch.zeros(2, dtype=evaluation.distance.dtype)
    return radial * evaluation.displacement[i, j] / evaluation.distance[i, j]


def minimum_image_matrix(positions: torch.Tensor, domain_length: float = 2.0) -> torch.Tensor:
    raw = positions[:, None, :] - positions[None, :, :]
    canonical = torch.remainder(raw + 0.5 * domain_length, domain_length) - 0.5 * domain_length
    count = positions.shape[0]
    upper = torch.triu(
        torch.ones((count, count), dtype=torch.bool, device=positions.device),
        diagonal=1,
    )
    displacement = torch.where(
        upper[..., None], canonical, -canonical.transpose(0, 1)
    )
    diagonal = torch.arange(count, device=positions.device)
    displacement[diagonal, diagonal] = 0.0
    return displacement


def dense_kernel_geometry(positions: torch.Tensor, supports: torch.Tensor) -> dict[str, torch.Tensor]:
    displacement = minimum_image_matrix(positions)
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    support = 0.5 * (supports[:, None] + supports[None, :])
    q = distance / support
    included = distance < support
    shape = torch.where(included, wendland_c4_shape(q), torch.zeros_like(q))
    derivative = torch.where(included, wendland_c4_shape_derivative(q), torch.zeros_like(q))
    kernel = 9.0 / (math.pi * support.square()) * shape
    radial = 9.0 / math.pi * derivative / support.pow(3)
    inverse = torch.where(distance > 0.0, distance.reciprocal(), torch.zeros_like(distance))
    gradient = radial[..., None] * displacement * inverse[..., None]
    return {"displacement": displacement, "distance": distance, "support": support, "included": included, "kernel": kernel, "gradient": gradient}


def _accumulate_pairs(count: int, i: torch.Tensor, j: torch.Tensor, force: torch.Tensor, order: torch.Tensor | None) -> torch.Tensor:
    if order is not None:
        i, j, force = i[order], j[order], force[order]
    result = torch.zeros((count, 2), dtype=force.dtype, device=force.device)
    result.index_add_(0, i, force)
    result.index_add_(0, j, -force)
    return result


def evaluate_dense_all_pairs(
    solution_id: str,
    positions: torch.Tensor,
    velocities: torch.Tensor,
    masses: torch.Tensor,
    supports: torch.Tensor,
    physical_time: float | torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
    *,
    pair_order: torch.Tensor | None = None,
) -> DenseEvaluation:
    count = positions.shape[0]
    if positions.shape != (count, 2) or velocities.shape != (count, 2) or masses.shape != (count,) or supports.shape != (count,):
        raise ValueError("invalid dense all-pairs state shape")
    geometry = dense_kernel_geometry(positions, supports)
    density_mask = geometry["included"] | torch.eye(count, dtype=torch.bool)
    density_i, density_j = torch.nonzero(density_mask, as_tuple=True)
    density = torch.zeros(count, dtype=positions.dtype)
    density.index_add_(
        0, density_i, masses[density_j] * geometry["kernel"][density_i, density_j]
    )
    pressure = parameters.sound_speed**2 * (density - parameters.rho0)
    upper = torch.triu(torch.ones((count, count), dtype=torch.bool), diagonal=1)
    selected = upper & geometry["included"]
    i, j = torch.nonzero(selected, as_tuple=True)
    pressure_pair = pressure_pair_force(
        masses[i], masses[j], density[i], density[j], pressure[i], pressure[j],
        geometry["gradient"][i, j],
    )
    radial = torch.sum(geometry["displacement"][i, j] * geometry["gradient"][i, j], dim=-1)
    gamma = viscosity_gamma(
        density[i], density[j], parameters.viscosity, radial,
        geometry["distance"][i, j], geometry["support"][i, j],
    )
    viscosity_pair = viscosity_pair_force(masses[i], masses[j], velocities[i], velocities[j], gamma)
    pressure_force = _accumulate_pairs(count, i, j, pressure_pair, pair_order)
    viscosity_force = _accumulate_pairs(count, i, j, viscosity_pair, pair_order)
    pressure_acceleration = pressure_force / masses[:, None]
    viscosity_acceleration = viscosity_force / masses[:, None]
    source = evaluate_mms_source(solution_id, positions, physical_time, parameters)
    total = pressure_acceleration + viscosity_acceleration + source
    values = (density, pressure, pressure_acceleration, viscosity_acceleration, source, total)
    if not all(bool(torch.isfinite(value.detach()).all()) for value in values):
        raise FloatingPointError("dense all-pairs evaluation is nonfinite")
    return DenseEvaluation(
        density=density, pressure=pressure,
        pressure_acceleration=pressure_acceleration,
        viscosity_acceleration=viscosity_acceleration,
        source_acceleration=source, total_acceleration=total,
        displacement=geometry["displacement"], distance=geometry["distance"],
        support=geometry["support"], included=geometry["included"],
    )


def dense_rhs(
    solution_id: str, unwrapped_positions: torch.Tensor, velocities: torch.Tensor,
    masses: torch.Tensor, supports: torch.Tensor, physical_time: float | torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
) -> tuple[torch.Tensor, torch.Tensor, DenseEvaluation]:
    wrapped = torch.remainder(unwrapped_positions + 1.0, 2.0) - 1.0
    evaluation = evaluate_dense_all_pairs(
        solution_id, wrapped, velocities, masses, supports, physical_time, parameters
    )
    return velocities, evaluation.total_acceleration, evaluation
