"""Periodic explicit-midpoint rollout for the Stage 01D SPH state."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import torch

from dynamic_solver.acceleration import (
    DynamicPhysicalParameters,
    ForceEvaluation,
    evaluate_internal_acceleration,
    state_from_evaluation,
)
from dynamic_solver.state import DynamicSPHState
from structure_preserving.neighborhood import wrap_periodic


SampleObserver = Callable[
    [int, DynamicSPHState, ForceEvaluation],
    dict[str, Any] | None,
]


@dataclass(frozen=True)
class DynamicStepResult:
    state: DynamicSPHState
    start_evaluation: ForceEvaluation
    midpoint_evaluation: ForceEvaluation
    end_evaluation: ForceEvaluation


@dataclass(frozen=True)
class DynamicRolloutResult:
    final_state: DynamicSPHState
    final_evaluation: ForceEvaluation
    sampled_records: tuple[dict[str, Any], ...]


def _positive_time_step(
    dt: float | torch.Tensor,
    reference: torch.Tensor,
) -> torch.Tensor:
    step = torch.as_tensor(
        dt,
        dtype=reference.dtype,
        device=reference.device,
    )
    if step.numel() != 1:
        raise ValueError("dt must be scalar")
    if not bool(torch.isfinite(step.detach())) or not bool(step.detach() > 0):
        raise ValueError("dt must be finite and positive")
    return step.reshape(())


def prepare_dynamic_state(
    state: DynamicSPHState,
    parameters: DynamicPhysicalParameters,
) -> tuple[DynamicSPHState, ForceEvaluation]:
    """Synchronize density/pressure and provide the reusable first stage."""

    evaluation = evaluate_internal_acceleration(state, parameters)
    return state_from_evaluation(state, evaluation), evaluation


def explicit_midpoint_dynamic_step(
    state: DynamicSPHState,
    *,
    dt: float | torch.Tensor,
    parameters: DynamicPhysicalParameters,
    start_evaluation: ForceEvaluation | None = None,
) -> DynamicStepResult:
    """Advance the coupled position/velocity system by one RK2 step."""

    step = _positive_time_step(dt, state.positions)
    current_evaluation = (
        evaluate_internal_acceleration(state, parameters)
        if start_evaluation is None
        else start_evaluation
    )
    synchronized = state_from_evaluation(state, current_evaluation)
    midpoint_positions = wrap_periodic(
        synchronized.positions
        + 0.5 * step * synchronized.velocities,
        synchronized.domain_min,
        synchronized.domain_max,
    )
    midpoint_velocities = (
        synchronized.velocities
        + 0.5 * step * current_evaluation.acceleration
    )
    midpoint_state = synchronized.with_updates(
        positions=midpoint_positions,
        velocities=midpoint_velocities,
        time=synchronized.time + 0.5 * float(step.detach()),
    )
    midpoint_evaluation = evaluate_internal_acceleration(
        midpoint_state,
        parameters,
    )

    final_positions = wrap_periodic(
        synchronized.positions + step * midpoint_velocities,
        synchronized.domain_min,
        synchronized.domain_max,
    )
    final_velocities = (
        synchronized.velocities
        + step * midpoint_evaluation.acceleration
    )
    provisional_final = synchronized.with_updates(
        positions=final_positions,
        velocities=final_velocities,
        time=synchronized.time + float(step.detach()),
    )
    end_evaluation = evaluate_internal_acceleration(
        provisional_final,
        parameters,
    )
    final_state = state_from_evaluation(
        provisional_final,
        end_evaluation,
    )
    return DynamicStepResult(
        state=final_state,
        start_evaluation=current_evaluation,
        midpoint_evaluation=midpoint_evaluation,
        end_evaluation=end_evaluation,
    )


def rollout_periodic(
    initial_state: DynamicSPHState,
    *,
    dt: float | torch.Tensor,
    steps: int,
    parameters: DynamicPhysicalParameters,
    sample_steps: Iterable[int] = (),
    observer: SampleObserver | None = None,
) -> DynamicRolloutResult:
    """Run fixed steps while retaining only caller-requested sample records."""

    if not isinstance(steps, int):
        raise TypeError("steps must be an integer")
    if steps < 0:
        raise ValueError("steps must be nonnegative")
    selected = set(int(value) for value in sample_steps)
    if any(value < 0 or value > steps for value in selected):
        raise ValueError("sample steps must lie in [0, steps]")
    state, evaluation = prepare_dynamic_state(initial_state, parameters)
    records: list[dict[str, Any]] = []
    if observer is not None and 0 in selected:
        record = observer(0, state, evaluation)
        if record is not None:
            records.append(record)
    for step_index in range(1, steps + 1):
        result = explicit_midpoint_dynamic_step(
            state,
            dt=dt,
            parameters=parameters,
            start_evaluation=evaluation,
        )
        state = result.state
        evaluation = result.end_evaluation
        if observer is not None and step_index in selected:
            record = observer(step_index, state, evaluation)
            if record is not None:
                records.append(record)
    return DynamicRolloutResult(
        final_state=state,
        final_evaluation=evaluation,
        sampled_records=tuple(records),
    )
