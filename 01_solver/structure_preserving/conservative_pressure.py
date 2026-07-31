"""Pair-defined conservative pressure force for fixed periodic neighborhoods."""

from __future__ import annotations

import torch

from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    reverse_directed_edge_indices,
)


def _particle_scalar(
    value: float | torch.Tensor,
    count: int,
    reference: torch.Tensor,
    *,
    name: str,
) -> torch.Tensor:
    if torch.is_tensor(value):
        result = value.to(dtype=reference.dtype, device=reference.device)
        if result.numel() == 1:
            return result.reshape(1).expand(count)
        if result.shape != (count,):
            raise ValueError(f"{name} must be scalar or [particles]")
        return result
    return torch.full(
        (count,),
        float(value),
        dtype=reference.dtype,
        device=reference.device,
    )


def pressure_pair_force(
    mass_i: torch.Tensor,
    mass_j: torch.Tensor,
    density_i: torch.Tensor,
    density_j: torch.Tensor,
    pressure_i: torch.Tensor,
    pressure_j: torch.Tensor,
    gradient_i: torch.Tensor,
) -> torch.Tensor:
    """Evaluate the preregistered symmetric pressure pair formula."""

    coefficient = (
        pressure_i / density_i.square()
        + pressure_j / density_j.square()
    )
    return -(mass_i * mass_j * coefficient)[:, None] * gradient_i


def conservative_pressure_pair_forces(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    pressure: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return unique pair indices and force on ``i`` from ``j``."""

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
    pressures = _particle_scalar(
        pressure,
        count,
        neighborhood.distance,
        name="pressure",
    )
    if bool((densities.detach() <= 0).any()):
        raise ValueError("density must be positive")
    selected = neighborhood.unordered
    i = neighborhood.row[selected]
    j = neighborhood.col[selected]
    gradient_i = edge_kernel_gradients(neighborhood)[selected]
    pair_force = pressure_pair_force(
        masses[i],
        masses[j],
        densities[i],
        densities[j],
        pressures[i],
        pressures[j],
        gradient_i,
    )
    return i, j, pair_force


def accumulate_pair_forces(
    particle_count: int,
    i: torch.Tensor,
    j: torch.Tensor,
    pair_force_on_i: torch.Tensor,
) -> torch.Tensor:
    """Accumulate the same pair force with opposite signs."""

    force = scatter_sum(i, pair_force_on_i, particle_count)
    force = force + scatter_sum(j, -pair_force_on_i, particle_count)
    return force


def conservative_pressure_forces(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    pressure: torch.Tensor,
) -> torch.Tensor:
    i, j, pair_force = conservative_pressure_pair_forces(
        neighborhood,
        mass=mass,
        density=density,
        pressure=pressure,
    )
    return accumulate_pair_forces(
        neighborhood.particle_count,
        i,
        j,
        pair_force,
    )


def pressure_conservation_metrics(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    pressure: torch.Tensor,
) -> dict[str, float]:
    """Return pair, global-force, and minimum-image torque residuals."""

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
    pressures = _particle_scalar(
        pressure,
        count,
        neighborhood.distance,
        name="pressure",
    )
    selected = neighborhood.unordered
    i = neighborhood.row[selected]
    j = neighborhood.col[selected]
    directed_gradients = edge_kernel_gradients(neighborhood)
    gradient_i = directed_gradients[selected]
    reverse = reverse_directed_edge_indices(neighborhood)[selected]
    gradient_j = directed_gradients[reverse]
    force_ij = pressure_pair_force(
        masses[i],
        masses[j],
        densities[i],
        densities[j],
        pressures[i],
        pressures[j],
        gradient_i,
    )
    force_ji = pressure_pair_force(
        masses[j],
        masses[i],
        densities[j],
        densities[i],
        pressures[j],
        pressures[i],
        gradient_j,
    )
    pair_residual = force_ij + force_ji
    total_force_per_particle = accumulate_pair_forces(
        count,
        i,
        j,
        force_ij,
    )
    total_force = total_force_per_particle.sum(dim=0)
    force_scale = 2.0 * torch.linalg.vector_norm(
        force_ij,
        dim=-1,
    ).sum()
    tiny = torch.finfo(force_ij.dtype).tiny
    pair_scale = torch.linalg.vector_norm(
        force_ij,
        dim=-1,
    ).max()
    pair_residual_norm = torch.linalg.vector_norm(
        pair_residual,
        dim=-1,
    )
    displacement = neighborhood.displacement[selected]
    pair_torque = (
        displacement[:, 0] * force_ij[:, 1]
        - displacement[:, 1] * force_ij[:, 0]
    )
    torque_scale = (
        torch.linalg.vector_norm(displacement, dim=-1)
        * torch.linalg.vector_norm(force_ij, dim=-1)
    )
    relative_pair_torque = torch.where(
        torque_scale > 0.0,
        pair_torque.abs() / torque_scale,
        torch.zeros_like(pair_torque),
    )
    return {
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
        "minimum_image_pair_torque_linf": float(pair_torque.abs().max()),
        "relative_pair_torque_linf": float(relative_pair_torque.max()),
        "relative_total_pair_torque": float(
            pair_torque.sum().abs() / (torque_scale.sum() + tiny)
        ),
        "force_scale": float(force_scale),
    }
