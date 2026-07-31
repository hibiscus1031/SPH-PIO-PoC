"""Independent order verification for the native explicit-midpoint method."""

from __future__ import annotations

import math

import pytest
import torch

from dynamic_solver.integrator import integrate_fixed_steps


TIME_STEPS = (0.1, 0.05, 0.025, 0.0125)
FINAL_TIME = 1.0


def _steps_for(dt: float) -> int:
    steps = int(round(FINAL_TIME / dt))
    assert math.isclose(steps * dt, FINAL_TIME, rel_tol=0.0, abs_tol=1.0e-14)
    return steps


def _observed_orders(errors: list[float]) -> list[float]:
    assert all(error > 0.0 and math.isfinite(error) for error in errors)
    return [
        math.log(coarse / fine, 2.0)
        for coarse, fine in zip(errors, errors[1:])
    ]


def _assert_second_order(errors: list[float]) -> None:
    assert all(
        fine < coarse
        for coarse, fine in zip(errors, errors[1:])
    )
    orders = _observed_orders(errors)
    assert all(1.8 < order < 2.2 for order in orders)
    assert 1.9 < sum(orders[-2:]) / 2.0 < 2.1


def scalar_decay_rhs(
    time: torch.Tensor,
    state: torch.Tensor,
    decay_rate: float,
) -> torch.Tensor:
    del time
    return -decay_rate * state


def coupled_damped_oscillator_rhs(
    time: torch.Tensor,
    state: torch.Tensor,
) -> torch.Tensor:
    del time
    y0, y1 = state.unbind()
    return torch.stack(
        (
            y1,
            -2.0 * y0 - 0.4 * y1,
        )
    )


def coupled_damped_oscillator_exact(
    time: float,
    *,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    """Exact solution for y0'=y1, y1'=-2*y0-0.4*y1, y(0)=[1,0]."""

    damped_frequency = 1.4
    angle = damped_frequency * time
    envelope = math.exp(-0.2 * time)
    return torch.tensor(
        [
            envelope
            * (
                math.cos(angle)
                + (1.0 / 7.0) * math.sin(angle)
            ),
            -(10.0 / 7.0) * envelope * math.sin(angle),
        ],
        dtype=dtype,
        device=device,
    )


def test_scalar_decay_observes_second_order_from_actual_errors() -> None:
    decay_rate = 1.3
    initial = torch.tensor(1.0, dtype=torch.float64)
    exact = math.exp(-decay_rate * FINAL_TIME)
    errors: list[float] = []
    for dt in TIME_STEPS:
        numerical = integrate_fixed_steps(
            scalar_decay_rhs,
            initial,
            dt=dt,
            steps=_steps_for(dt),
            args=(decay_rate,),
        )
        errors.append(abs(float(numerical) - exact))

    _assert_second_order(errors)
    assert _observed_orders(errors)[-1] == pytest.approx(
        2.0,
        abs=0.08,
    )


def test_coupled_system_observes_second_order_from_actual_errors() -> None:
    initial = torch.tensor([1.0, 0.0], dtype=torch.float64)
    exact = coupled_damped_oscillator_exact(
        FINAL_TIME,
        dtype=initial.dtype,
        device=initial.device,
    )
    errors: list[float] = []
    for dt in TIME_STEPS:
        numerical = integrate_fixed_steps(
            coupled_damped_oscillator_rhs,
            initial,
            dt=dt,
            steps=_steps_for(dt),
        )
        errors.append(float(torch.linalg.vector_norm(numerical - exact)))

    _assert_second_order(errors)
    assert _observed_orders(errors)[-1] == pytest.approx(
        2.0,
        abs=0.08,
    )
