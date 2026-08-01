"""Independent DOP853 integration of a caller-supplied semidiscrete RHS."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import numpy as np
from scipy.integrate import solve_ivp


ArrayRHS = Callable[[float, np.ndarray], np.ndarray]


@dataclass(frozen=True)
class SemidiscreteReference:
    times: np.ndarray
    states: np.ndarray
    nfev: int
    njev: int
    nlu: int
    rtol: float
    atol: float
    max_step: float


def integrate_semidiscrete_dop853(
    rhs: ArrayRHS,
    initial_state: np.ndarray,
    sample_times: Sequence[float],
    *,
    rtol: float,
    atol: float,
    max_step: float,
) -> SemidiscreteReference:
    times = np.asarray(sample_times, dtype=np.float64)
    initial = np.asarray(initial_state, dtype=np.float64)
    if times.ndim != 1 or len(times) < 2 or times[0] != 0.0 or np.any(np.diff(times) <= 0):
        raise ValueError("sample_times must start at zero and increase strictly")
    solution = solve_ivp(
        rhs, (0.0, float(times[-1])), initial, method="DOP853", t_eval=times,
        rtol=rtol, atol=atol, max_step=max_step,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    states = solution.y.T
    if not np.isfinite(states).all():
        raise FloatingPointError("semidiscrete reference is nonfinite")
    states[0] = initial
    return SemidiscreteReference(
        times=times, states=states, nfev=solution.nfev, njev=solution.njev,
        nlu=solution.nlu, rtol=rtol, atol=atol, max_step=max_step,
    )
