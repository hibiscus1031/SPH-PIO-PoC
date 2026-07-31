"""Bitwise repeatability of the CPU/float64 dynamic rollout."""

from __future__ import annotations

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.periodic_rollout import rollout_periodic
from dynamic_solver.taylor_green import initialize_taylor_green_state


def test_repeated_rollout_from_identical_initial_state_is_bitwise_equal() -> None:
    common = {
        "resolution": 8,
        "support_ratio": 3.0,
        "jitter_fraction": 0.05,
        "seed": 20261001,
    }
    first_initial = initialize_taylor_green_state(**common)
    second_initial = initialize_taylor_green_state(**common)
    state_fields = (
        "positions",
        "velocities",
        "masses",
        "densities",
        "pressures",
        "supports",
        "domain_min",
        "domain_max",
    )
    assert all(
        torch.equal(
            getattr(first_initial, name),
            getattr(second_initial, name),
        )
        for name in state_fields
    )

    parameters = DynamicPhysicalParameters()
    first = rollout_periodic(
        first_initial,
        dt=1.0e-4,
        steps=8,
        parameters=parameters,
    )
    second = rollout_periodic(
        second_initial,
        dt=1.0e-4,
        steps=8,
        parameters=parameters,
    )

    assert first.final_state.time == second.final_state.time
    for name in state_fields:
        assert torch.equal(
            getattr(first.final_state, name),
            getattr(second.final_state, name),
        ), name

    evaluation_fields = (
        "densities",
        "pressures",
        "pressure_force",
        "viscosity_force",
        "total_force",
        "acceleration",
    )
    for name in evaluation_fields:
        assert torch.equal(
            getattr(first.final_evaluation, name),
            getattr(second.final_evaluation, name),
        ), name

    neighborhood_fields = (
        "row",
        "col",
        "displacement",
        "distance",
        "edge_support",
        "particle_support",
        "domain_min",
        "domain_max",
    )
    for name in neighborhood_fields:
        assert torch.equal(
            getattr(first.final_evaluation.neighborhood, name),
            getattr(second.final_evaluation.neighborhood, name),
        ), name
