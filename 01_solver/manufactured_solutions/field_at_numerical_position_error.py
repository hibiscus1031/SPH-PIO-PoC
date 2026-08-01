"""Field reconstruction errors evaluated at numerical particle positions."""

from __future__ import annotations

import torch
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS


def _norms(error: torch.Tensor) -> dict[str, float]:
    magnitude = torch.linalg.vector_norm(error, dim=-1) if error.ndim == 2 else error.abs()
    return {"L1": float(magnitude.mean()), "L2": float(torch.sqrt(torch.mean(magnitude.square()))), "Linf": float(magnitude.max())}


def field_at_numerical_position_error(
    solution_id: str, numerical_positions: torch.Tensor, physical_time: float,
    numerical_velocity: torch.Tensor, numerical_density: torch.Tensor,
    numerical_pressure: torch.Tensor, parameters: MMSParameters = PARAMETERS,
) -> dict[str, dict[str, float]]:
    module = solution_module(solution_id)
    return {
        "velocity": _norms(numerical_velocity - module.velocity(numerical_positions, physical_time, parameters)),
        "density": _norms(numerical_density - module.density(numerical_positions, physical_time, parameters)),
        "pressure": _norms(numerical_pressure - module.pressure(numerical_positions, physical_time, parameters)),
    }
