"""One-hundred-step regular periodic zero-flow equilibrium test."""

from __future__ import annotations

import torch

from dynamic_solver.acceleration import (
    DynamicPhysicalParameters,
    force_structure_audit,
)
from dynamic_solver.periodic_rollout import rollout_periodic
from dynamic_solver.taylor_green import initialize_taylor_green_state


def test_regular_zero_flow_remains_at_roundoff_for_one_hundred_steps() -> None:
    initial = initialize_taylor_green_state(8, support_ratio=3.0)
    initial = initial.with_updates(
        velocities=torch.zeros_like(initial.velocities),
    )
    # The regular kernel sum is spatially uniform but is not forced to one by
    # retuning particle masses. Its mean defines this dedicated zero-pressure
    # equilibrium EOS reference without changing the state or masses.
    equilibrium_density = float(initial.densities.mean())
    parameters = DynamicPhysicalParameters(
        reference_density=equilibrium_density,
        sound_speed=20.0,
        physical_viscosity=0.02,
    )

    def observe(step, state, evaluation):
        audit = force_structure_audit(state, evaluation, parameters)
        assert torch.isfinite(state.positions).all()
        assert torch.isfinite(state.velocities).all()
        assert torch.isfinite(evaluation.densities).all()
        assert torch.isfinite(evaluation.pressures).all()
        return {
            "step": step,
            "position_drift": float(
                (state.positions - initial.positions).abs().max()
            ),
            "velocity_linf": float(state.velocities.abs().max()),
            "density_drift": float(
                (evaluation.densities - initial.densities).abs().max()
            ),
            "pressure_linf": float(evaluation.pressures.abs().max()),
            **audit,
        }

    result = rollout_periodic(
        initial,
        dt=1.0e-4,
        steps=100,
        parameters=parameters,
        sample_steps=range(101),
        observer=observe,
    )
    records = result.sampled_records
    assert len(records) == 101

    epsilon = torch.finfo(torch.float64).eps
    assert max(record["position_drift"] for record in records) <= 256 * epsilon
    assert max(record["velocity_linf"] for record in records) <= 1.0e-12
    assert max(record["density_drift"] for record in records) <= 1.0e-13
    assert max(record["pressure_linf"] for record in records) <= 1.0e-12
    assert max(
        record["characteristic_normalized_total_internal_force"]
        for record in records
    ) <= 1.0e-10
    assert max(
        record["pressure_relative_pair_force_residual"]
        for record in records
    ) <= 1.0e-12
    assert max(
        record["viscosity_relative_pair_force_residual"]
        for record in records
    ) <= 1.0e-12
    assert max(record["viscous_power"] for record in records) <= 1.0e-14

    zero_topology_keys = (
        "neighbor_duplicate_edge_count",
        "neighbor_missing_self_edge_count",
        "neighbor_nonreciprocal_nonself_edge_count",
        "neighbor_out_of_bounds_edge_count",
        "neighbor_omitted_strict_support_edge_count",
        "neighbor_unexpected_edge_count",
    )
    for record in records:
        assert all(record[key] == 0 for key in zero_topology_keys)

    torch.testing.assert_close(
        result.final_state.positions,
        initial.positions,
        rtol=0.0,
        atol=256 * epsilon,
    )
    torch.testing.assert_close(
        result.final_state.densities,
        initial.densities,
        rtol=0.0,
        atol=1.0e-13,
    )
