"""Frozen WCSPH continuity/pressure/viscosity/source right-hand side."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph
from source_interface.source import evaluate_external_momentum_source
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum


@dataclass(frozen=True)
class StateDerivative:
    x_rate: torch.Tensor
    velocity_rate: torch.Tensor
    density_rate: torch.Tensor
    baseline_acceleration: torch.Tensor
    external_source: torch.Tensor


def evaluate_baseline_rhs(
    state: DynamicParticleState,
    graph: ReciprocalGraph,
    family_id: str,
) -> StateDerivative:
    if bool((state.density.detach() <= 0.0).any()):
        raise FloatingPointError("nonpositive density")
    pressure_force = conservative_pressure_forces(
        graph.neighborhood,
        mass=state.mass,
        density=state.density,
        pressure=state.pressure,
    )
    viscosity_force = conservative_viscosity_forces(
        graph.neighborhood,
        mass=state.mass,
        density=state.density,
        velocity=state.velocity,
        physical_viscosity=0.02,
    )
    gradient = edge_kernel_gradients(graph.neighborhood)
    velocity_difference = state.velocity[graph.row] - state.velocity[graph.col]
    continuity_edge = state.mass[graph.col] * torch.einsum("nd,nd->n", velocity_difference, gradient)
    density_rate = scatter_sum(graph.row, continuity_edge, state.particle_count)
    source = evaluate_external_momentum_source(
        family_id,
        state.material_labels,
        state.physical_time,
        state,
    )
    baseline_acceleration = (pressure_force + viscosity_force) / state.mass[:, None] + source
    return StateDerivative(state.velocity, baseline_acceleration, density_rate, baseline_acceleration, source)

