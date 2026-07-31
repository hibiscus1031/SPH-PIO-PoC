"""Native fixed-neighbor AD/FD qualification tests."""

from __future__ import annotations

import math

from structure_preserving.native_autograd_ops import (
    run_native_autograd_matrix,
)


def test_native_autograd_matrix_meets_preregistered_gate() -> None:
    rows = run_native_autograd_matrix()
    assert len(rows) == 20
    assert {int(row["steps"]) for row in rows} == {1, 3, 5, 8, 16}
    assert {str(row["parameter"]) for row in rows} == {
        "physical_viscosity",
        "initial_velocity_amplitude",
        "local_velocity_x_particle_0",
        "local_pressure_particle_0",
    }
    for row in rows:
        assert row["status"] == "PASS"
        assert row["finite"] is True
        assert row["nonzero"] is True
        assert math.isfinite(float(row["autograd_gradient"]))
        assert math.isfinite(float(row["finite_difference_gradient"]))
        assert float(row["gradient_norm"]) > 0.0
        if int(row["steps"]) in (1, 3, 5, 8):
            assert float(row["relative_difference"]) <= 0.01
        assert row["topology_differentiability_claimed"] is False
