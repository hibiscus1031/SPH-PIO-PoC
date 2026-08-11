"""The exact frozen ten-channel invariant node token."""

from __future__ import annotations

import torch

from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph
from structure_preserving.kernels import edge_kernel_values, scatter_sum


TOKEN_FIELDS = (
    "constant",
    "density_deviation",
    "normalized_pressure",
    "normalized_mass",
    "normalized_smoothing_length",
    "normalized_active_neighbor_count",
    "kernel_zeroth_moment",
    "kernel_radial_relative_velocity_mean",
    "kernel_relative_speed_second_moment",
    "kernel_isotropic_second_position_moment",
)


def build_node_token(state: DynamicParticleState, graph: ReciprocalGraph) -> torch.Tensor:
    row, col = graph.row, graph.col
    count = state.particle_count
    nonself_active = graph.active_kernel & (row != col)
    active_count = scatter_sum(row, nonself_active.to(torch.float64), count)
    kernel = edge_kernel_values(graph.neighborhood)
    omega = state.mass[col] / state.density[col] * kernel
    rhat = graph.displacement / (graph.distance[:, None] + 2.0e-12)
    relative_velocity = (state.velocity[col] - state.velocity[row]) / 20.0
    radial = torch.einsum("nd,nd->n", relative_velocity, rhat)
    relative_speed2 = relative_velocity.square().sum(dim=-1)
    position2 = (graph.displacement / 2.0).square().sum(dim=-1)
    values = (
        torch.ones_like(state.density),
        state.density - 1.0,
        state.pressure / 400.0,
        state.mass / 4.0,
        state.smoothing_length / 2.0,
        active_count / 64.0,
        scatter_sum(row, omega, count),
        scatter_sum(row, omega * radial, count),
        scatter_sum(row, omega * relative_speed2, count),
        scatter_sum(row, omega * position2, count),
    )
    token = torch.stack(values, dim=-1)
    if token.shape != (count, 10) or not bool(torch.isfinite(token.detach()).all()):
        raise FloatingPointError("invalid node token")
    return token

