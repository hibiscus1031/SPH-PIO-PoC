"""Labeled-particle exact trajectory and state error metrics."""

from __future__ import annotations

import torch
from manufactured_solutions.torus_position_error import position_error_norms


def _norms(numerical: torch.Tensor, exact: torch.Tensor) -> dict[str, float]:
    error = numerical - exact
    magnitude = torch.linalg.vector_norm(error, dim=-1) if error.ndim == 2 else error.abs()
    return {"L1": float(magnitude.mean()), "L2": float(torch.sqrt(torch.mean(magnitude.square()))), "Linf": float(magnitude.max())}


def labeled_state_error(
    *, numerical_positions: torch.Tensor, exact_positions: torch.Tensor,
    numerical_velocity: torch.Tensor, exact_velocity: torch.Tensor,
    numerical_density: torch.Tensor, exact_density: torch.Tensor,
    numerical_pressure: torch.Tensor, exact_pressure: torch.Tensor,
) -> dict[str, dict[str, float]]:
    return {
        "position": position_error_norms(numerical_positions, exact_positions),
        "velocity": _norms(numerical_velocity, exact_velocity),
        "density": _norms(numerical_density, exact_density),
        "pressure": _norms(numerical_pressure, exact_pressure),
    }
