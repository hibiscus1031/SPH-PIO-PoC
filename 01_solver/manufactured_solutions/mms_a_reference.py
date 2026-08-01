"""Closed, non-integrated particle trajectory reference for MMS-A."""

from __future__ import annotations

import torch

from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS, validate_points
from manufactured_solutions.mms_a_translating_density_wave import wrap_position


def unwrapped_trajectory(
    initial_positions: torch.Tensor,
    physical_time: float | torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
) -> torch.Tensor:
    positions, times = validate_points(initial_positions, physical_time)
    displacement = torch.stack(
        (parameters.translation_speed * times, torch.zeros_like(times)), dim=-1
    )
    return positions + displacement


def wrapped_trajectory(
    initial_positions: torch.Tensor,
    physical_time: float | torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
) -> torch.Tensor:
    return wrap_position(unwrapped_trajectory(initial_positions, physical_time, parameters), parameters)
