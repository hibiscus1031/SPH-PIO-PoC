"""Diagnostic force evaluation with a frozen reciprocal edge index."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters, ForceEvaluation
from dynamic_solver.density import summation_density
from dynamic_solver.equation_of_state import isothermal_pressure
from dynamic_solver.state import DynamicSPHState
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    build_periodic_neighborhood,
    minimum_image,
)


@dataclass(frozen=True)
class FrozenReciprocalTopology:
    row: torch.Tensor
    col: torch.Tensor
    particle_count: int
    edge_key_sha256: str


def _edge_hash(row: torch.Tensor, col: torch.Tensor, particle_count: int) -> str:
    keys = (row.to(torch.int64) * int(particle_count) + col.to(torch.int64)).contiguous()
    return hashlib.sha256(keys.numpy().tobytes()).hexdigest()


def freeze_initial_topology(state: DynamicSPHState) -> FrozenReciprocalTopology:
    neighborhood = build_periodic_neighborhood(
        state.positions,
        state.supports,
        domain_minimum=tuple(float(value) for value in state.domain_min),
        domain_maximum=tuple(float(value) for value in state.domain_max),
    )
    row = neighborhood.row.detach().clone()
    col = neighborhood.col.detach().clone()
    return FrozenReciprocalTopology(
        row=row,
        col=col,
        particle_count=state.particle_count,
        edge_key_sha256=_edge_hash(row, col, state.particle_count),
    )


def frozen_periodic_neighborhood(
    state: DynamicSPHState,
    topology: FrozenReciprocalTopology,
) -> PeriodicNeighborhood:
    if state.particle_count != topology.particle_count:
        raise ValueError("state and frozen topology particle counts differ")
    row = topology.row
    col = topology.col
    extent = state.domain_max - state.domain_min
    keys = row * topology.particle_count + col
    reverse_keys = col * topology.particle_count + row
    reverse = torch.searchsorted(keys, reverse_keys)
    bounded = reverse.clamp_max(keys.numel() - 1)
    if not bool(((reverse < keys.numel()) & (keys[bounded] == reverse_keys)).all()):
        raise RuntimeError("frozen topology is not reciprocal")
    displacement = torch.zeros(
        (row.numel(), state.positions.shape[1]),
        dtype=state.positions.dtype,
        device=state.positions.device,
    )
    unordered = row < col
    canonical = minimum_image(
        state.positions[row[unordered]] - state.positions[col[unordered]],
        extent,
    )
    displacement[unordered] = canonical
    displacement[reverse[unordered]] = -canonical
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    edge_support = 0.5 * (state.supports[row] + state.supports[col])
    return PeriodicNeighborhood(
        row=row,
        col=col,
        displacement=displacement,
        distance=distance,
        edge_support=edge_support,
        particle_support=state.supports,
        domain_min=state.domain_min,
        domain_max=state.domain_max,
        particle_count=state.particle_count,
    )


def evaluate_frozen_topology_acceleration(
    state: DynamicSPHState,
    parameters: DynamicPhysicalParameters,
    topology: FrozenReciprocalTopology,
) -> ForceEvaluation:
    """Evaluate unchanged SPH operators on the frozen diagnostic edge index."""

    neighborhood = frozen_periodic_neighborhood(state, topology)
    density = summation_density(neighborhood, mass=state.masses)
    pressure = isothermal_pressure(
        density,
        reference_density=parameters.reference_density,
        sound_speed=parameters.sound_speed,
    )
    pressure_force = conservative_pressure_forces(
        neighborhood,
        mass=state.masses,
        density=density,
        pressure=pressure,
    )
    viscosity_force = conservative_viscosity_forces(
        neighborhood,
        mass=state.masses,
        density=density,
        velocity=state.velocities,
        physical_viscosity=parameters.physical_viscosity,
    )
    total_force = pressure_force + viscosity_force
    acceleration = total_force / state.masses[:, None]
    if not all(
        bool(torch.isfinite(value).all())
        for value in (
            density,
            pressure,
            pressure_force,
            viscosity_force,
            total_force,
            acceleration,
        )
    ):
        raise FloatingPointError("nonfinite frozen-topology force evaluation")
    return ForceEvaluation(
        neighborhood=neighborhood,
        densities=density,
        pressures=pressure,
        pressure_force=pressure_force,
        viscosity_force=viscosity_force,
        total_force=total_force,
        acceleration=acceleration,
    )
