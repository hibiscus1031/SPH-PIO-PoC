"""Native-PyTorch explicit midpoint (second-order Runge--Kutta) integrator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import torch


TensorRHS = Callable[..., torch.Tensor]


def _scalar_like(
    value: float | torch.Tensor,
    reference: torch.Tensor,
    *,
    name: str,
    positive: bool,
) -> torch.Tensor:
    scalar = torch.as_tensor(
        value,
        dtype=reference.dtype,
        device=reference.device,
    )
    if scalar.numel() != 1:
        raise ValueError(f"{name} must be scalar")
    detached = scalar.detach()
    if not bool(torch.isfinite(detached)):
        raise ValueError(f"{name} must be finite")
    if positive and not bool(detached > 0):
        raise ValueError(f"{name} must be positive")
    return scalar.reshape(())


def _evaluate_rhs(
    rhs: TensorRHS,
    time: torch.Tensor,
    state: torch.Tensor,
    *args: Any,
    **kwargs: Any,
) -> torch.Tensor:
    derivative = rhs(time, state, *args, **kwargs)
    if not torch.is_tensor(derivative):
        raise TypeError("rhs must return a torch.Tensor")
    if derivative.shape != state.shape:
        raise ValueError(
            "rhs output shape must match state shape: "
            f"{derivative.shape} != {state.shape}"
        )
    if derivative.device != state.device or derivative.dtype != state.dtype:
        raise ValueError("rhs output must preserve the state dtype and device")
    return derivative


def explicit_midpoint_step(
    rhs: TensorRHS,
    time: float | torch.Tensor,
    state: torch.Tensor,
    dt: float | torch.Tensor,
    *args: Any,
    **kwargs: Any,
) -> torch.Tensor:
    r"""Advance one step with the explicit midpoint RK2 formula.

    The method evaluates

    \[
    k_1=f(t_n,y_n),\qquad
    k_2=f(t_n+\tfrac12\Delta t,y_n+\tfrac12\Delta t\,k_1),
    \]

    and returns \(y_{n+1}=y_n+\Delta t\,k_2\). Only native PyTorch
    operations are used, so gradients through continuous tensor values remain
    available.
    """

    if not torch.is_tensor(state):
        raise TypeError("state must be a torch.Tensor")
    if not state.is_floating_point():
        raise TypeError("state must have a floating-point dtype")
    step = _scalar_like(dt, state, name="dt", positive=True)
    current_time = _scalar_like(time, state, name="time", positive=False)

    k1 = _evaluate_rhs(rhs, current_time, state, *args, **kwargs)
    midpoint_time = current_time + 0.5 * step
    midpoint_state = state + 0.5 * step * k1
    k2 = _evaluate_rhs(
        rhs,
        midpoint_time,
        midpoint_state,
        *args,
        **kwargs,
    )
    return state + step * k2


def integrate_fixed_steps(
    rhs: TensorRHS,
    initial_state: torch.Tensor,
    *,
    dt: float | torch.Tensor,
    steps: int,
    initial_time: float | torch.Tensor = 0.0,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> torch.Tensor:
    """Apply :func:`explicit_midpoint_step` for a fixed number of steps."""

    if not isinstance(steps, int):
        raise TypeError("steps must be an integer")
    if steps < 0:
        raise ValueError("steps must be nonnegative")
    if not torch.is_tensor(initial_state):
        raise TypeError("initial_state must be a torch.Tensor")
    if not initial_state.is_floating_point():
        raise TypeError("initial_state must have a floating-point dtype")

    step = _scalar_like(dt, initial_state, name="dt", positive=True)
    time = _scalar_like(
        initial_time,
        initial_state,
        name="initial_time",
        positive=False,
    )
    state = initial_state
    call_kwargs = {} if kwargs is None else kwargs
    for _ in range(steps):
        state = explicit_midpoint_step(
            rhs,
            time,
            state,
            step,
            *args,
            **call_kwargs,
        )
        time = time + step
    return state
