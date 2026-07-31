"""Empirical order check through the current diffSPH integrator interface."""

from __future__ import annotations

import math

from verification.integrator_ode import integrator_order_study


def test_current_symplectic_euler_interface_is_second_order_for_decay_ode() -> None:
    rows = integrator_order_study(
        base_dt=0.1,
        final_time=1.0,
        lam=1.3,
        integration_scheme="symplecticEuler",
    )
    errors = [float(row["absolute_error"]) for row in rows]
    orders = [float(row["observed_order"]) for row in rows[1:]]

    assert all(later < earlier for earlier, later in zip(errors, errors[1:]))
    assert all(math.isfinite(order) for order in orders)
    assert all(1.8 < order < 2.2 for order in orders)
