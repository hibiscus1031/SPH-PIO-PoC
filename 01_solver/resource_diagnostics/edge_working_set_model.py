"""Robust edge/step attribution models with deterministic bootstrap CIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class RobustFit:
    intercept: float
    edge_coefficient: float
    step_coefficient: float
    step_ci95_lower: float
    step_ci95_upper: float
    edge_ci95_lower: float
    edge_ci95_upper: float
    robust_scale: float
    observations: int
    bootstrap_samples: int

    def as_dict(self, *, prefix: str = "") -> dict[str, float | int]:
        return {
            f"{prefix}intercept": self.intercept,
            f"{prefix}edge_coefficient": self.edge_coefficient,
            f"{prefix}step_coefficient": self.step_coefficient,
            f"{prefix}step_ci95_lower": self.step_ci95_lower,
            f"{prefix}step_ci95_upper": self.step_ci95_upper,
            f"{prefix}edge_ci95_lower": self.edge_ci95_lower,
            f"{prefix}edge_ci95_upper": self.edge_ci95_upper,
            f"{prefix}robust_scale": self.robust_scale,
            f"{prefix}observations": self.observations,
            f"{prefix}bootstrap_samples": self.bootstrap_samples,
        }


def _huber_fit(design: np.ndarray, response: np.ndarray) -> tuple[np.ndarray, float]:
    coefficients, *_ = np.linalg.lstsq(design, response, rcond=None)
    scale = 0.0
    for _ in range(50):
        residual = response - design @ coefficients
        median = float(np.median(residual))
        mad = float(np.median(np.abs(residual - median)))
        scale = max(1.4826 * mad, np.finfo(float).eps)
        normalized = np.abs(residual) / (1.345 * scale)
        weights = np.ones_like(normalized)
        mask = normalized > 1.0
        weights[mask] = 1.0 / normalized[mask]
        root = np.sqrt(weights)
        updated, *_ = np.linalg.lstsq(
            design * root[:, None], response * root, rcond=None
        )
        if np.allclose(updated, coefficients, rtol=1.0e-10, atol=1.0e-8):
            coefficients = updated
            break
        coefficients = updated
    return coefficients, scale


def robust_edge_step_fit(
    *,
    steps: Iterable[float],
    edge_counts: Iterable[float],
    values: Iterable[float],
    bootstrap_samples: int,
    seed: int,
) -> RobustFit:
    step = np.asarray(tuple(steps), dtype=float)
    edge = np.asarray(tuple(edge_counts), dtype=float)
    response = np.asarray(tuple(values), dtype=float)
    if not (step.shape == edge.shape == response.shape) or step.ndim != 1:
        raise ValueError("steps, edge_counts, and values must be equal 1-D arrays")
    if step.size < 8:
        raise ValueError("at least eight observations are required")
    if not np.isfinite(step).all() or not np.isfinite(edge).all() or not np.isfinite(response).all():
        raise ValueError("regression inputs must be finite")
    if bootstrap_samples < 100:
        raise ValueError("at least 100 bootstrap samples are required")
    step_center = float(np.mean(step))
    edge_center = float(np.mean(edge))
    step_scale = max(float(np.std(step)), 1.0)
    edge_scale = max(float(np.std(edge)), 1.0)
    design = np.column_stack(
        (
            np.ones(step.size),
            (edge - edge_center) / edge_scale,
            (step - step_center) / step_scale,
        )
    )
    coefficient, robust_scale = _huber_fit(design, response)
    converted_edge = float(coefficient[1] / edge_scale)
    converted_step = float(coefficient[2] / step_scale)
    intercept = float(
        coefficient[0]
        - converted_edge * edge_center
        - converted_step * step_center
    )
    rng = np.random.default_rng(int(seed))
    bootstrap: list[tuple[float, float]] = []
    attempts = 0
    while len(bootstrap) < bootstrap_samples and attempts < bootstrap_samples * 4:
        attempts += 1
        indices = rng.integers(0, step.size, size=step.size)
        sampled_design = design[indices]
        if np.linalg.matrix_rank(sampled_design) < 3:
            continue
        sampled_coefficient, _ = _huber_fit(sampled_design, response[indices])
        bootstrap.append(
            (
                float(sampled_coefficient[1] / edge_scale),
                float(sampled_coefficient[2] / step_scale),
            )
        )
    if len(bootstrap) < bootstrap_samples:
        raise RuntimeError("insufficient full-rank bootstrap samples")
    array = np.asarray(bootstrap)
    edge_lower, edge_upper = np.quantile(array[:, 0], (0.025, 0.975))
    step_lower, step_upper = np.quantile(array[:, 1], (0.025, 0.975))
    return RobustFit(
        intercept=intercept,
        edge_coefficient=converted_edge,
        step_coefficient=converted_step,
        step_ci95_lower=float(step_lower),
        step_ci95_upper=float(step_upper),
        edge_ci95_lower=float(edge_lower),
        edge_ci95_upper=float(edge_upper),
        robust_scale=float(robust_scale),
        observations=int(step.size),
        bootstrap_samples=int(bootstrap_samples),
    )
