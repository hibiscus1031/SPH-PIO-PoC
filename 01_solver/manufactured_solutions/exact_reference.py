"""Shared exact-field and fixed-mass initialization helpers for Stage 01F2."""

from __future__ import annotations

import torch

from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS


def exact_fields(
    solution_id: str,
    positions: torch.Tensor,
    physical_time: float | torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
) -> dict[str, torch.Tensor]:
    module = solution_module(solution_id)
    return {
        "velocity": module.velocity(positions, physical_time, parameters),
        "density": module.density(positions, physical_time, parameters),
        "pressure": module.pressure(positions, physical_time, parameters),
    }
