"""Autograd/finite-difference sanity checks for the qualified value path."""

from __future__ import annotations

import math

from verification.autograd_scope import run_autograd_scope


def test_stage01b_short_rollout_exposes_upstream_backward_failure() -> None:
    rows = run_autograd_scope()
    assert {int(row["steps"]) for row in rows} == {3, 5, 8}
    assert {str(row["parameter"]) for row in rows} == {
        "physical_viscosity",
        "local_velocity_x_particle_0",
    }
    for row in rows:
        assert row["status"] == "FAIL"
        assert row["autograd_status"] == "FAIL"
        assert row["finite_difference_status"] == "PASS"
        assert math.isnan(float(row["gradient_norm"]))
        assert math.isfinite(float(row["finite_difference_gradient"]))
        assert abs(float(row["finite_difference_gradient"])) > 0.0
        assert math.isnan(float(row["relative_difference"]))
        assert row["exception_type"] == "TypeError"
        assert "NoneType" in str(row["exception_message"])
        assert "laplacian.py:1062" in str(row["exception_origin"])
