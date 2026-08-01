"""Pure convergence metrics and guarded extrapolation qualification."""

from __future__ import annotations

import math
from collections.abc import Sequence
import numpy as np


def fitted_order(scales: Sequence[float], errors: Sequence[float]) -> float:
    x = np.asarray(scales, dtype=np.float64)
    e = np.asarray(errors, dtype=np.float64)
    if len(x) < 2 or x.shape != e.shape or np.any(x <= 0) or np.any(e <= 0) or not np.isfinite(x).all() or not np.isfinite(e).all():
        raise ValueError("positive finite scale/error vectors of equal length required")
    return float(np.polyfit(np.log(x), np.log(e), 1)[0])


def successive_orders(errors: Sequence[float], refinement_ratios: Sequence[float] | None = None) -> list[float]:
    e = np.asarray(errors, dtype=np.float64)
    if np.any(e <= 0) or not np.isfinite(e).all():
        raise ValueError("errors must be positive and finite")
    ratios = np.full(len(e) - 1, 2.0) if refinement_ratios is None else np.asarray(refinement_ratios, dtype=np.float64)
    if ratios.shape != (len(e) - 1,) or np.any(ratios <= 1.0):
        raise ValueError("one refinement ratio greater than one per error pair required")
    return [float(math.log(e[i] / e[i + 1]) / math.log(ratios[i])) for i in range(len(e) - 1)]


def strictly_decreasing(values: Sequence[float]) -> bool:
    return all(float(a) > float(b) for a, b in zip(values, values[1:]))


def gci_qualification(errors: Sequence[float], refinement_ratios: Sequence[float]) -> dict[str, object]:
    e = np.asarray(errors, dtype=np.float64)
    ratios = np.asarray(refinement_ratios, dtype=np.float64)
    orders = successive_orders(e, ratios)
    same_sign = all(value > 0 for value in orders) or all(value < 0 for value in orders)
    stable = all(abs(a - b) / max(abs(a), abs(b), 1e-15) <= 0.25 for a, b in zip(orders, orders[1:]))
    near_asymptotic = float(e[-1] / e[0]) <= 0.5
    qualified = len(e) >= 3 and strictly_decreasing(e) and same_sign and stable and near_asymptotic and bool(np.all(ratios > 1))
    return {"qualified": qualified, "local_orders": orders, "monotone": strictly_decreasing(e), "same_sign": same_sign, "stable_orders": stable, "near_asymptotic": near_asymptotic}
