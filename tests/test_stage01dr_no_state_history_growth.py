from __future__ import annotations

import gc

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.periodic_rollout import (
    explicit_midpoint_dynamic_step,
    prepare_dynamic_state,
)
from dynamic_solver.taylor_green import initialize_taylor_green_state
from resource_diagnostics.object_retention import RetentionTracker


def test_old_state_and_step_result_do_not_form_a_step_history() -> None:
    tracker = RetentionTracker()
    with torch.no_grad():
        state = initialize_taylor_green_state(6, support_ratio=2.0)
        parameters = DynamicPhysicalParameters()
        state, evaluation = prepare_dynamic_state(state, parameters)
        for step in range(1, 26):
            old_state = state
            old_evaluation = evaluation
            result = explicit_midpoint_dynamic_step(
                state,
                dt=1.0e-4,
                parameters=parameters,
                start_evaluation=evaluation,
            )
            tracker.watch("old_state", old_state)
            tracker.watch("old_evaluation", old_evaluation)
            tracker.watch("step_result", result)
            tracker.watch("midpoint_evaluation", result.midpoint_evaluation)
            state = result.state.with_updates(time=step * 1.0e-4)
            evaluation = result.end_evaluation
            del result, old_state, old_evaluation
            gc.collect()
            snapshot = tracker.snapshot(collect=False)
            assert snapshot["old_state_alive"] == 0
            assert snapshot["old_evaluation_alive"] == 0
            assert snapshot["step_result_alive"] == 0
            assert snapshot["midpoint_evaluation_alive"] == 0
