"""Verify the current diffSPH integrator interface on an analytical ODE."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import math
from typing import Any

import torch


@dataclass
class ScalarDecayUpdate:
    """Minimal update object representing a derivative of the velocity slot."""

    velocities: torch.Tensor
    positions: torch.Tensor


@dataclass
class ScalarDecaySystem:
    r"""Minimal diffSPH-compatible state adapter for \(y'=-\lambda y\)."""

    y: torch.Tensor
    t: float = 0.0

    def initializeNewState(self, *args: Any, **kwargs: Any):
        del args, kwargs
        return copy.deepcopy(self)

    def initialize(self, dt: float, *args: Any, **kwargs: Any):
        del dt, args, kwargs
        return self

    def preprocess(
        self,
        initial_state: Any,
        dt: float,
        *args: Any,
        **kwargs: Any,
    ):
        del initial_state, dt, args, kwargs
        return self

    def postprocess(
        self,
        current_state: Any,
        dt: float,
        result: Any,
        *args: Any,
        **kwargs: Any,
    ):
        del current_state, dt, result, args, kwargs
        return self

    def finalize(
        self,
        initial_state: Any,
        dt: float,
        *args: Any,
        **kwargs: Any,
    ):
        del initial_state, dt, args, kwargs
        return self

    def integrate(self, update: ScalarDecayUpdate, dt: float, **kwargs: Any):
        del kwargs
        self.y = self.y + dt * update.velocities
        self.t += float(dt)
        return self

    def integrateVelocity(
        self,
        update: ScalarDecayUpdate,
        dt: float,
        **kwargs: Any,
    ):
        del kwargs
        self.y = self.y + dt * update.velocities
        return self

    def integratePosition(
        self,
        update: ScalarDecayUpdate,
        dt: float,
        **kwargs: Any,
    ):
        del update, dt, kwargs
        return self

    def integrateQuantities(
        self,
        update: ScalarDecayUpdate,
        dt: float,
        **kwargs: Any,
    ):
        del update, dt, kwargs
        return self


def scalar_decay_rhs(
    state: ScalarDecaySystem,
    dt: float,
    lam: float,
    **kwargs: Any,
) -> ScalarDecayUpdate:
    del dt, kwargs
    return ScalarDecayUpdate(
        velocities=-lam * state.y,
        positions=torch.zeros_like(state.y),
    )


def integrate_scalar_decay(
    *,
    dt: float,
    final_time: float,
    lam: float = 1.3,
    y0: float = 1.0,
    integration_scheme: str = "symplecticEuler",
) -> float:
    from diffSPH.integration import getIntegrationEnum, getIntegrator

    integrator = getIntegrator(getIntegrationEnum(integration_scheme))
    steps = int(round(final_time / dt))
    if not math.isclose(steps * dt, final_time, abs_tol=1.0e-14):
        raise ValueError("final_time must be an integer multiple of dt")
    state = ScalarDecaySystem(torch.tensor(y0, dtype=torch.float64))
    for _ in range(steps):
        result = integrator.function(
            state,
            dt,
            scalar_decay_rhs,
            lam,
            priorStep=None,
        )
        state = result[0]
    return float(state.y)


def integrator_order_study(
    *,
    base_dt: float = 0.1,
    final_time: float = 1.0,
    lam: float = 1.3,
    integration_scheme: str = "symplecticEuler",
) -> list[dict[str, float | str]]:
    exact = math.exp(-lam * final_time)
    rows: list[dict[str, float | str]] = []
    previous_error: float | None = None
    for level in range(4):
        dt = base_dt / (2**level)
        numerical = integrate_scalar_decay(
            dt=dt,
            final_time=final_time,
            lam=lam,
            integration_scheme=integration_scheme,
        )
        error = abs(numerical - exact)
        order = (
            math.log(previous_error / error, 2.0)
            if previous_error is not None
            else math.nan
        )
        rows.append(
            {
                "integration_scheme": integration_scheme,
                "dt": dt,
                "numerical": numerical,
                "exact": exact,
                "absolute_error": error,
                "observed_order": order,
            }
        )
        previous_error = error
    return rows
