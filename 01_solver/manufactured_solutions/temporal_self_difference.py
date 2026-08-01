"""Common-time-grid trajectory differences between successive time steps."""

from __future__ import annotations

import numpy as np


def common_time_grid_identity(first: np.ndarray, second: np.ndarray, *, atol: float = 1e-14) -> bool:
    return first.shape == second.shape and bool(np.allclose(first, second, rtol=0.0, atol=atol))


def periodic_trajectory_rms(first: np.ndarray, second: np.ndarray, *, domain_length: float = 2.0) -> float:
    if first.shape != second.shape or first.ndim != 3 or first.shape[-1] != 2:
        raise ValueError("trajectory arrays must share shape [time,particle,2]")
    delta = np.remainder(first - second + 0.5 * domain_length, domain_length) - 0.5 * domain_length
    return float(np.sqrt(np.mean(np.sum(delta * delta, axis=-1))))


def trajectory_rms(first: np.ndarray, second: np.ndarray) -> float:
    if first.shape != second.shape:
        raise ValueError("trajectory arrays must share shape")
    return float(np.sqrt(np.mean((first - second) ** 2)))
