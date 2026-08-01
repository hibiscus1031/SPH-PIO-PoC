"""Stage 01F2 external-source adapter around the frozen midpoint RK2 path."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from dynamic_solver.acceleration import (
    DynamicPhysicalParameters,
    ForceEvaluation,
    evaluate_internal_acceleration,
    state_from_evaluation,
)
from dynamic_solver.periodic_rollout import (
    DynamicStepResult,
    _positive_time_step,
    explicit_midpoint_dynamic_step,
)
from dynamic_solver.sourced_acceleration import SourceCallRecord, evaluate_sourced_acceleration
from dynamic_solver.state import DynamicSPHState
from manufactured_solutions.external_balance import midpoint_momentum_defect
from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS
from structure_preserving.neighborhood import wrap_periodic


@dataclass(frozen=True)
class SourcedDynamicStepResult:
    state: DynamicSPHState
    midpoint_state: DynamicSPHState
    start_evaluation: ForceEvaluation
    midpoint_evaluation: ForceEvaluation
    end_evaluation: ForceEvaluation
    source_calls: tuple[SourceCallRecord, SourceCallRecord]
    midpoint_numerical_positions: torch.Tensor
    start_external_acceleration: torch.Tensor
    midpoint_external_acceleration: torch.Tensor
    momentum_defect: torch.Tensor
    internal_impulse: torch.Tensor
    external_impulse: torch.Tensor


def explicit_midpoint_sourced_step(
    state: DynamicSPHState,
    *,
    dt: float | torch.Tensor,
    parameters: DynamicPhysicalParameters,
    solution_id: str | None,
    mms_parameters: MMSParameters = PARAMETERS,
    start_evaluation: ForceEvaluation | None = None,
) -> DynamicStepResult | SourcedDynamicStepResult:
    """Advance one step, delegating exactly to Stage 01D when source is off."""

    if solution_id is None:
        return explicit_midpoint_dynamic_step(
            state, dt=dt, parameters=parameters, start_evaluation=start_evaluation
        )

    step = _positive_time_step(dt, state.positions)
    current = (
        evaluate_internal_acceleration(state, parameters)
        if start_evaluation is None
        else start_evaluation
    )
    synchronized = state_from_evaluation(state, current)
    start = evaluate_sourced_acceleration(
        solution_id=solution_id,
        stage="start",
        numerical_positions=synchronized.positions,
        physical_stage_time=synchronized.time,
        masses=synchronized.masses,
        internal_acceleration=current.acceleration,
        parameters=mms_parameters,
    )
    midpoint_positions = wrap_periodic(
        synchronized.positions + 0.5 * step * synchronized.velocities,
        synchronized.domain_min,
        synchronized.domain_max,
    )
    midpoint_velocities = synchronized.velocities + 0.5 * step * start.total_acceleration
    midpoint_state = synchronized.with_updates(
        positions=midpoint_positions,
        velocities=midpoint_velocities,
        time=synchronized.time + 0.5 * float(step.detach()),
    )
    midpoint_evaluation = evaluate_internal_acceleration(midpoint_state, parameters)
    midpoint = evaluate_sourced_acceleration(
        solution_id=solution_id,
        stage="midpoint",
        numerical_positions=midpoint_state.positions,
        physical_stage_time=midpoint_state.time,
        masses=midpoint_state.masses,
        internal_acceleration=midpoint_evaluation.acceleration,
        parameters=mms_parameters,
    )
    final_positions = wrap_periodic(
        synchronized.positions + step * midpoint_velocities,
        synchronized.domain_min,
        synchronized.domain_max,
    )
    final_velocities = synchronized.velocities + step * midpoint.total_acceleration
    provisional_final = synchronized.with_updates(
        positions=final_positions,
        velocities=final_velocities,
        time=synchronized.time + float(step.detach()),
    )
    end_evaluation = evaluate_internal_acceleration(provisional_final, parameters)
    final_state = state_from_evaluation(provisional_final, end_evaluation)
    balance = midpoint_momentum_defect(
        synchronized.masses,
        synchronized.velocities,
        final_state.velocities,
        midpoint_evaluation.acceleration,
        midpoint.external_acceleration,
        step,
    )
    return SourcedDynamicStepResult(
        state=final_state,
        midpoint_state=midpoint_state,
        start_evaluation=current,
        midpoint_evaluation=midpoint_evaluation,
        end_evaluation=end_evaluation,
        source_calls=(start.record, midpoint.record),
        midpoint_numerical_positions=midpoint_state.positions,
        start_external_acceleration=start.external_acceleration,
        midpoint_external_acceleration=midpoint.external_acceleration,
        momentum_defect=balance["defect"],
        internal_impulse=balance["internal_impulse"],
        external_impulse=balance["external_impulse"],
    )
