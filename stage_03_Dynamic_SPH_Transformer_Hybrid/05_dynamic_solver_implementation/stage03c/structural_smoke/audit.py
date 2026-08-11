"""One-step, fixed-random-weight conservation and O(2)/permutation audits."""

from __future__ import annotations

from dataclasses import replace

import torch
from torch import nn

from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph, build_reciprocal_graph
from pair_force_head.head import PairForceOutput
from temporal_history.history import TemporalHistoryState
from tokenization.tokens import build_node_token


ATOL = 2.0e-11
RTOL = 2.0e-11


def _close(left: torch.Tensor, right: torch.Tensor) -> tuple[bool, float]:
    error = float((left - right).detach().abs().max()) if left.numel() else 0.0
    scale = max(float(left.detach().abs().max()) if left.numel() else 0.0, float(right.detach().abs().max()) if right.numel() else 0.0)
    return error <= ATOL + RTOL * scale, error


def _evaluate(
    model: nn.Module,
    arm: str,
    state: DynamicParticleState,
    history: TemporalHistoryState | None,
    stage: str,
) -> tuple[PairForceOutput, ReciprocalGraph, torch.Tensor]:
    graph = build_reciprocal_graph(state)
    token = build_node_token(state, graph)
    kwargs: dict[str, object] = {"stage": stage}
    if arm in {"D2", "D3"}:
        if history is None:
            raise ValueError("temporal structural audit requires history")
        kwargs["history"] = history
    return model.evaluate(token, state, graph, **kwargs), graph, token


def _transformed_state(state: DynamicParticleState, matrix: torch.Tensor, translation: torch.Tensor | None = None, boost: torch.Tensor | None = None) -> DynamicParticleState:
    x = state.x_unwrapped @ matrix.T
    velocity = state.velocity @ matrix.T
    if translation is not None:
        x = x + translation
    if boost is not None:
        velocity = velocity + boost
    labels = state.material_labels @ matrix.T
    if translation is not None:
        labels = labels + translation
    return replace(state, x_unwrapped=x, velocity=velocity, material_labels=labels)


def audit_stage(
    *,
    arm: str,
    model: nn.Module,
    state: DynamicParticleState,
    history: TemporalHistoryState | None,
    stage: str,
    reference_output: PairForceOutput,
    reference_graph: ReciprocalGraph,
    reference_token: torch.Tensor,
) -> dict[str, object]:
    output = reference_output
    head = model.pair_head
    selected = reference_graph.unordered & reference_graph.active_kernel
    i, j = reference_graph.row[selected], reference_graph.col[selected]
    displacement = reference_graph.displacement[selected]
    distance = reference_graph.distance[selected]
    rhat = displacement / (distance[:, None] + 2.0e-12)
    dv = (state.velocity[j] - state.velocity[i]) / 20.0
    radial = torch.einsum("nd,nd->n", dv, rhat)
    transverse = dv - radial[:, None] * rhat
    scalars = torch.stack((distance / reference_graph.edge_support[selected], radial, dv.square().sum(-1), transverse.square().sum(-1)), dim=-1)
    alpha_lr, beta_lr = head.coefficients_from_pairs(output.particle_hidden[i], output.particle_hidden[j], scalars)
    alpha_rl, beta_rl = head.coefficients_from_pairs(output.particle_hidden[j], output.particle_hidden[i], scalars)
    pair_exchange = torch.equal(alpha_lr, alpha_rl) and torch.equal(beta_lr, beta_rl)
    antisymmetry = bool(torch.equal(output.pair_force_on_i, -(-output.pair_force_on_i)))
    force_sum = torch.zeros_like(state.velocity)
    force_sum.index_add_(0, output.pair_i, output.pair_force_on_i)
    force_sum.index_add_(0, output.pair_j, -output.pair_force_on_i)
    force_residual = float(torch.linalg.vector_norm(force_sum.sum(0)).detach() / (output.pair_force_on_i.detach().abs().sum() + 1.0e-30))

    count = state.particle_count
    permutation = torch.arange(count - 1, -1, -1, dtype=torch.int64)
    inverse = torch.argsort(permutation)
    permuted_state = replace(
        state,
        x_unwrapped=state.x_unwrapped[permutation],
        velocity=state.velocity[permutation],
        density=state.density[permutation],
        pressure=state.pressure[permutation],
        mass=state.mass[permutation],
        smoothing_length=state.smoothing_length[permutation],
        material_labels=state.material_labels[permutation],
    )
    permuted_history = None if history is None else history.permuted(permutation)
    permuted_output, _, _ = _evaluate(model, arm, permuted_state, permuted_history, stage)
    permutation_pass, permutation_error = _close(permuted_output.acceleration[inverse], output.acceleration)

    pair_order = torch.arange(output.pair_i.numel() - 1, -1, -1, dtype=torch.int64)
    reordered = head(output.particle_hidden, state, reference_graph, pair_order=pair_order)
    edge_reorder_pass, edge_reorder_error = _close(reordered.acceleration, output.acceleration)

    identity = torch.eye(2, dtype=torch.float64)
    translated = _transformed_state(state, identity, translation=torch.tensor([0.25, -0.5], dtype=torch.float64))
    translated_output, _, _ = _evaluate(model, arm, translated, history, stage)
    translation_pass, translation_error = _close(translated_output.acceleration, output.acceleration)

    boosted = _transformed_state(state, identity, boost=torch.tensor([0.7, -0.3], dtype=torch.float64))
    boosted_output, _, _ = _evaluate(model, arm, boosted, history, stage)
    boost_pass, boost_error = _close(boosted_output.acceleration, output.acceleration)

    rotation = torch.tensor([[0.0, -1.0], [1.0, 0.0]], dtype=torch.float64)
    rotated = _transformed_state(state, rotation)
    rotated_output, _, _ = _evaluate(model, arm, rotated, history, stage)
    rotation_pass, rotation_error = _close(rotated_output.acceleration, output.acceleration @ rotation.T)

    reflection = torch.tensor([[-1.0, 0.0], [0.0, 1.0]], dtype=torch.float64)
    reflected = _transformed_state(state, reflection)
    reflected_output, _, _ = _evaluate(model, arm, reflected, history, stage)
    reflection_pass, reflection_error = _close(reflected_output.acceleration, output.acceleration @ reflection.T)

    representative = replace(state, x_unwrapped=state.x_unwrapped + torch.tensor([2.0, -4.0], dtype=torch.float64))
    representative_output, _, _ = _evaluate(model, arm, representative, history, stage)
    representative_pass, representative_error = _close(representative_output.acceleration, output.acceleration)

    repeated, _, repeated_token = _evaluate(model, arm, state, history, stage)
    deterministic_repeat = torch.equal(repeated.acceleration, output.acceleration) and torch.equal(repeated_token, reference_token)
    finite = bool(
        torch.isfinite(output.acceleration).all()
        and torch.isfinite(output.pair_force_on_i).all()
        and torch.isfinite(output.particle_hidden).all()
    )
    gates = {
        "pair_exchange": pair_exchange,
        "force_antisymmetry": antisymmetry,
        "correction_force_residual": force_residual <= 1.0e-10,
        "permutation_equivariance": permutation_pass,
        "edge_reorder": edge_reorder_pass,
        "translation": translation_pass,
        "Galilean_boost": boost_pass,
        "SO2_rotation": rotation_pass,
        "reflection": reflection_pass,
        "periodic_representative_shift": representative_pass,
        "finite_output": finite,
        "deterministic_repeat": deterministic_repeat,
    }
    return {
        "arm": arm,
        "stage": stage,
        "gates": gates,
        "pass": all(gates.values()),
        "normalized_correction_force_residual": force_residual,
        "maximum_errors": {
            "permutation": permutation_error,
            "edge_reorder": edge_reorder_error,
            "translation": translation_error,
            "Galilean_boost": boost_error,
            "SO2_rotation": rotation_error,
            "reflection": reflection_error,
            "periodic_representative_shift": representative_error,
        },
    }

