"""Preregistered shell-safe support-ratio path diagnostics."""

from __future__ import annotations

import math


PATH = {16: (4.0 + math.sqrt(17.0)) / 2.0, 24: 4.5, 32: (5.0 + math.sqrt(26.0)) / 2.0, 48: 5.5, 64: (6.0 + math.sqrt(37.0)) / 2.0}


def shell_margin(support_ratio: float) -> dict[str, float]:
    shells = sorted({math.sqrt(i * i + j * j) for i in range(0, 16) for j in range(0, 16) if i or j})
    lower = max(value for value in shells if value < support_ratio)
    upper = min(value for value in shells if value > support_ratio)
    return {"nearest_lower_shell": lower, "nearest_upper_shell": upper, "minimum_cutoff_margin": min(support_ratio - lower, upper - support_ratio)}


def path_entry(resolution: int) -> dict[str, float]:
    ratio = PATH[resolution]
    dx = 2.0 / resolution
    return {"resolution": resolution, "dx": dx, "support_ratio": ratio, "support": ratio * dx, **shell_margin(ratio)}
