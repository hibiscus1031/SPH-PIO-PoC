from __future__ import annotations

import gc
import weakref

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.periodic_rollout import (
    explicit_midpoint_dynamic_step,
    prepare_dynamic_state,
)
from dynamic_solver.taylor_green import initialize_taylor_green_state


def test_midpoint_neighbor_and_force_tensors_release_after_result_deletion() -> None:
    with torch.no_grad():
        state = initialize_taylor_green_state(6, support_ratio=2.0)
        parameters = DynamicPhysicalParameters()
        state, evaluation = prepare_dynamic_state(state, parameters)
        result = explicit_midpoint_dynamic_step(
            state,
            dt=1.0e-4,
            parameters=parameters,
            start_evaluation=evaluation,
        )
        midpoint = result.midpoint_evaluation
        midpoint_references = [
            weakref.ref(midpoint),
            weakref.ref(midpoint.neighborhood),
            weakref.ref(midpoint.neighborhood.row),
            weakref.ref(midpoint.neighborhood.col),
            weakref.ref(midpoint.neighborhood.displacement),
            weakref.ref(midpoint.pressure_force),
            weakref.ref(midpoint.viscosity_force),
        ]
        current_neighborhood_reference = weakref.ref(
            result.end_evaluation.neighborhood
        )
        state = result.state
        evaluation = result.end_evaluation
        del result, midpoint
        gc.collect()
        assert all(reference() is None for reference in midpoint_references)
        assert current_neighborhood_reference() is not None
        del state, evaluation
        gc.collect()
        assert current_neighborhood_reference() is None
