"""Periodic wrapping through the dynamic explicit-midpoint rollout."""

from __future__ import annotations

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.periodic_rollout import rollout_periodic
from dynamic_solver.taylor_green import initialize_taylor_green_state
from structure_preserving.neighborhood import (
    audit_periodic_neighborhood,
    wrap_periodic,
)


def test_dynamic_rollout_wraps_crossing_particles_into_half_open_domain() -> None:
    state = initialize_taylor_green_state(6, support_ratio=2.0)
    uniform_velocity = torch.tensor(
        [3.0, -4.0],
        dtype=torch.float64,
    ).expand_as(state.velocities).clone()
    state = state.with_updates(velocities=uniform_velocity)
    dt = 0.2
    unwrapped = state.positions + dt * uniform_velocity
    assert bool(
        (
            (unwrapped < state.domain_min)
            | (unwrapped >= state.domain_max)
        ).any()
    )
    expected = wrap_periodic(
        unwrapped,
        state.domain_min,
        state.domain_max,
    )

    result = rollout_periodic(
        state,
        dt=dt,
        steps=1,
        parameters=DynamicPhysicalParameters(),
    )
    final = result.final_state
    assert final.time == dt
    assert bool((final.positions >= final.domain_min).all())
    assert bool((final.positions < final.domain_max).all())
    torch.testing.assert_close(
        final.positions,
        expected,
        rtol=0.0,
        atol=2.0e-14,
    )
    torch.testing.assert_close(
        final.velocities,
        uniform_velocity,
        rtol=0.0,
        atol=2.0e-13,
    )

    topology = audit_periodic_neighborhood(
        final.positions,
        result.final_evaluation.neighborhood,
    )
    assert topology["duplicate_edge_count"] == 0
    assert topology["nonreciprocal_nonself_edge_count"] == 0
    assert topology["omitted_strict_support_edge_count"] == 0
    assert topology["unexpected_edge_count"] == 0
