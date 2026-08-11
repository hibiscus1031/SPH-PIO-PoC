"""Class-based explicit midpoint solver with transactional causal history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
from torch import nn

from baseline_d0.rhs import StateDerivative, evaluate_baseline_rhs
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import ReciprocalGraph, build_reciprocal_graph
from pair_force_head.head import PairForceOutput
from safety.checks import StepRejected, validate_force, validate_graph, validate_hidden, validate_state
from temporal_history.history import TemporalHistoryState, repeat_initial_history
from tokenization.tokens import build_node_token


@dataclass
class SolverAccounting:
    graph_rebuild_count: int = 0
    accepted_graph_materialization_count: int = 0
    source_evaluation_count: int = 0
    graph_hash_sequence: list[str] = field(default_factory=list)
    edge_count_sequence: list[int] = field(default_factory=list)
    accepted_graph_hash_sequence: list[str] = field(default_factory=list)
    accepted_edge_count_sequence: list[int] = field(default_factory=list)
    neural_forward_count: int = 0
    history_commit_count: int = 0
    midpoint_commit_count: int = 0
    rejected_commit_count: int = 0
    rejection_evidence: list[str] = field(default_factory=list)

    def snapshot(self) -> tuple[Any, ...]:
        return (
            self.graph_rebuild_count,
            self.accepted_graph_materialization_count,
            self.source_evaluation_count,
            len(self.graph_hash_sequence),
            len(self.edge_count_sequence),
            len(self.accepted_graph_hash_sequence),
            len(self.accepted_edge_count_sequence),
            self.neural_forward_count,
            self.history_commit_count,
            self.midpoint_commit_count,
            self.rejected_commit_count,
        )

    def rollback(self, snapshot: tuple[Any, ...]) -> None:
        (
            self.graph_rebuild_count,
            self.accepted_graph_materialization_count,
            self.source_evaluation_count,
            graph_len,
            edge_len,
            accepted_graph_len,
            accepted_edge_len,
            self.neural_forward_count,
            self.history_commit_count,
            self.midpoint_commit_count,
            self.rejected_commit_count,
        ) = snapshot
        del self.graph_hash_sequence[graph_len:]
        del self.edge_count_sequence[edge_len:]
        del self.accepted_graph_hash_sequence[accepted_graph_len:]
        del self.accepted_edge_count_sequence[accepted_edge_len:]


@dataclass(frozen=True)
class RK2StepRecord:
    start_state: DynamicParticleState
    midpoint_state: DynamicParticleState
    start_graph: ReciprocalGraph
    midpoint_graph: ReciprocalGraph
    accepted_graph: ReciprocalGraph
    start_token: torch.Tensor | None
    midpoint_token: torch.Tensor | None
    accepted_token: torch.Tensor | None
    start_pair_output: PairForceOutput | None
    midpoint_pair_output: PairForceOutput | None
    commit_count_delta: int


@dataclass(frozen=True)
class StepAttempt:
    accepted: bool
    state: DynamicParticleState
    history: TemporalHistoryState | None
    record: RK2StepRecord | None
    rejection_reason: str | None


class DynamicHybridRK2Solver:
    def __init__(
        self,
        *,
        arm: str,
        family_id: str,
        dt: float,
        model: nn.Module | None = None,
        correction_enabled: bool = True,
        zero_head: bool = False,
    ) -> None:
        self.arm = arm
        self.family_id = family_id
        self.dt = float(dt)
        self.model = model
        self.correction_enabled = bool(correction_enabled and arm != "D0")
        self.zero_head = bool(zero_head)
        self.accounting = SolverAccounting()
        if arm == "D0" and model is not None:
            raise ValueError("D0 cannot own neural parameters")
        if arm != "D0" and model is None:
            raise ValueError(f"{arm} requires its frozen model")

    @property
    def temporal(self) -> bool:
        return self.arm in {"D2", "D3"}

    def initialize_history(self, state: DynamicParticleState) -> TemporalHistoryState | None:
        if not self.temporal or not self.correction_enabled:
            return None
        accepted = state.with_eos()
        graph = build_reciprocal_graph(accepted)
        token = build_node_token(accepted, graph)
        hidden = self.model.initialize_hidden(token)  # type: ignore[union-attr]
        validate_hidden(hidden, name="initial")
        return repeat_initial_history(token, hidden, accepted.material_labels, accepted.physical_time)

    def _record_rhs_graph(self, graph: ReciprocalGraph) -> None:
        self.accounting.graph_rebuild_count += 1
        self.accounting.graph_hash_sequence.append(graph.graph_hash)
        self.accounting.edge_count_sequence.append(graph.edge_count)

    def _correction(
        self,
        state: DynamicParticleState,
        graph: ReciprocalGraph,
        history: TemporalHistoryState | None,
        stage: str,
    ) -> tuple[torch.Tensor, torch.Tensor | None, PairForceOutput | None]:
        if not self.correction_enabled:
            return torch.zeros_like(state.velocity), None, None
        token = build_node_token(state, graph)
        kwargs: dict[str, object] = {"stage": stage}
        if self.temporal:
            if history is None:
                raise ValueError("temporal arm requires history")
            kwargs["history"] = history
        output = self.model.evaluate(token, state, graph, **kwargs)  # type: ignore[union-attr]
        self.accounting.neural_forward_count += 1
        validate_force(output.acceleration, name=stage)
        validate_hidden(output.particle_hidden, name=stage)
        if self.zero_head:
            if not bool((output.acceleration == 0.0).all() and (output.pair_force_on_i == 0.0).all()):
                raise StepRejected(f"{stage}:zero_head_nonzero_correction")
            # Preserve the baseline arithmetic path exactly after executing the network.
            return torch.zeros_like(state.velocity), token, output
        return output.acceleration, token, output

    def _rhs(
        self,
        state: DynamicParticleState,
        graph: ReciprocalGraph,
        correction: torch.Tensor,
    ) -> StateDerivative:
        baseline = evaluate_baseline_rhs(state, graph, self.family_id)
        self.accounting.source_evaluation_count += 1
        if not self.correction_enabled or self.zero_head:
            return baseline
        velocity_rate = baseline.velocity_rate + correction
        validate_force(velocity_rate, name="combined_rhs")
        return StateDerivative(
            baseline.x_rate,
            velocity_rate,
            baseline.density_rate,
            baseline.baseline_acceleration,
            baseline.external_source,
        )

    def attempt_step(
        self,
        state: DynamicParticleState,
        history: TemporalHistoryState | None,
    ) -> StepAttempt:
        accounting_snapshot = self.accounting.snapshot()
        history_hash_before = None if history is None else history.history_hash
        try:
            start = state.with_eos()
            validate_state(start, name="start")
            graph_start = build_reciprocal_graph(start)
            validate_graph(graph_start, name="start")
            self._record_rhs_graph(graph_start)
            correction_start, token_start, pair_start = self._correction(start, graph_start, history, "start")
            k1 = self._rhs(start, graph_start, correction_start)

            half = 0.5 * self.dt
            midpoint = DynamicParticleState(
                x_unwrapped=start.x_unwrapped + half * k1.x_rate,
                velocity=start.velocity + half * k1.velocity_rate,
                density=start.density + half * k1.density_rate,
                pressure=torch.empty_like(start.pressure),
                mass=start.mass,
                smoothing_length=start.smoothing_length,
                material_labels=start.material_labels,
                physical_time=start.physical_time + half,
                accepted_step_index=start.accepted_step_index,
            ).with_eos()
            validate_state(midpoint, name="midpoint")
            graph_midpoint = build_reciprocal_graph(midpoint)
            validate_graph(graph_midpoint, name="midpoint")
            self._record_rhs_graph(graph_midpoint)
            correction_midpoint, token_midpoint, pair_midpoint = self._correction(midpoint, graph_midpoint, history, "midpoint")
            k2 = self._rhs(midpoint, graph_midpoint, correction_midpoint)

            accepted = DynamicParticleState(
                x_unwrapped=start.x_unwrapped + self.dt * k2.x_rate,
                velocity=start.velocity + self.dt * k2.velocity_rate,
                density=start.density + self.dt * k2.density_rate,
                pressure=torch.empty_like(start.pressure),
                mass=start.mass,
                smoothing_length=start.smoothing_length,
                material_labels=start.material_labels,
                physical_time=start.physical_time + self.dt,
                accepted_step_index=start.accepted_step_index + 1,
            ).with_eos()
            validate_state(accepted, name="accepted")
            accepted_graph = build_reciprocal_graph(accepted)
            validate_graph(accepted_graph, name="accepted")
            self.accounting.accepted_graph_materialization_count += 1
            self.accounting.accepted_graph_hash_sequence.append(accepted_graph.graph_hash)
            self.accounting.accepted_edge_count_sequence.append(accepted_graph.edge_count)

            accepted_token: torch.Tensor | None = None
            new_history = history
            if self.temporal and self.correction_enabled:
                if history is None:
                    raise StepRejected("accepted:missing_history")
                accepted_token = build_node_token(accepted, accepted_graph)
                accepted_hidden = self.model.accepted_hidden(accepted_token, history=history)  # type: ignore[union-attr]
                validate_hidden(accepted_hidden, name="accepted")
                new_history = history.commit(accepted_token, accepted_hidden, accepted.physical_time)
                self.accounting.history_commit_count += 1
            record = RK2StepRecord(
                start,
                midpoint,
                graph_start,
                graph_midpoint,
                accepted_graph,
                token_start,
                token_midpoint,
                accepted_token,
                pair_start,
                pair_midpoint,
                1 if new_history is not history else 0,
            )
            return StepAttempt(True, accepted, new_history, record, None)
        except (StepRejected, FloatingPointError, RuntimeError, ValueError) as error:
            self.accounting.rollback(accounting_snapshot)
            self.accounting.rejected_commit_count += 0
            reason = str(error)
            self.accounting.rejection_evidence.append(reason)
            if history is not None and history.history_hash != history_hash_before:
                raise RuntimeError("history mutated during rejected step") from error
            return StepAttempt(False, state, history, None, reason)

    def step(
        self,
        state: DynamicParticleState,
        history: TemporalHistoryState | None,
    ) -> tuple[DynamicParticleState, TemporalHistoryState | None, RK2StepRecord]:
        attempt = self.attempt_step(state, history)
        if not attempt.accepted or attempt.record is None:
            raise StepRejected(attempt.rejection_reason or "unnamed rejection")
        return attempt.state, attempt.history, attempt.record

    def rollout(
        self,
        state: DynamicParticleState,
        history: TemporalHistoryState | None,
        steps: int,
    ) -> tuple[DynamicParticleState, TemporalHistoryState | None, list[RK2StepRecord]]:
        records: list[RK2StepRecord] = []
        for _ in range(int(steps)):
            state, history, record = self.step(state, history)
            records.append(record)
        return state, history, records
