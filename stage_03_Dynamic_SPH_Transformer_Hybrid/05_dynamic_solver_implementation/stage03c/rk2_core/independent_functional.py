"""Independent functional D0 RK2 route without solver/history orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

import torch

from baseline_d0.rhs import evaluate_baseline_rhs
from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import build_reciprocal_graph


@dataclass
class FunctionalAccounting:
    graph_rebuild_count: int = 0
    accepted_graph_materialization_count: int = 0
    source_evaluation_count: int = 0
    graph_hash_sequence: list[str] = field(default_factory=list)
    edge_count_sequence: list[int] = field(default_factory=list)
    accepted_graph_hash_sequence: list[str] = field(default_factory=list)


def functional_rk2_rollout(
    initial: DynamicParticleState,
    *,
    family_id: str,
    dt: float,
    steps: int,
) -> tuple[DynamicParticleState, FunctionalAccounting]:
    state = initial
    accounting = FunctionalAccounting()
    for _ in range(int(steps)):
        start = state.with_eos()
        graph_start = build_reciprocal_graph(start)
        accounting.graph_rebuild_count += 1
        accounting.graph_hash_sequence.append(graph_start.graph_hash)
        accounting.edge_count_sequence.append(graph_start.edge_count)
        k1 = evaluate_baseline_rhs(start, graph_start, family_id)
        accounting.source_evaluation_count += 1
        midpoint = DynamicParticleState(
            start.x_unwrapped + 0.5 * dt * k1.x_rate,
            start.velocity + 0.5 * dt * k1.velocity_rate,
            start.density + 0.5 * dt * k1.density_rate,
            torch.empty_like(start.pressure),
            start.mass,
            start.smoothing_length,
            start.material_labels,
            start.physical_time + 0.5 * dt,
            start.accepted_step_index,
        ).with_eos()
        graph_midpoint = build_reciprocal_graph(midpoint)
        accounting.graph_rebuild_count += 1
        accounting.graph_hash_sequence.append(graph_midpoint.graph_hash)
        accounting.edge_count_sequence.append(graph_midpoint.edge_count)
        k2 = evaluate_baseline_rhs(midpoint, graph_midpoint, family_id)
        accounting.source_evaluation_count += 1
        state = DynamicParticleState(
            start.x_unwrapped + dt * k2.x_rate,
            start.velocity + dt * k2.velocity_rate,
            start.density + dt * k2.density_rate,
            torch.empty_like(start.pressure),
            start.mass,
            start.smoothing_length,
            start.material_labels,
            start.physical_time + dt,
            start.accepted_step_index + 1,
        ).with_eos()
        accepted_graph = build_reciprocal_graph(state)
        accounting.accepted_graph_materialization_count += 1
        accounting.accepted_graph_hash_sequence.append(accepted_graph.graph_hash)
    return state, accounting

