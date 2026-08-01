"""Pure Stage 01F2 adapter for frozen Stage 01F manufactured sources."""

from __future__ import annotations

from dataclasses import replace
import torch

from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS
from manufactured_solutions.source_terms import manufactured_acceleration


def evaluate_mms_source(
    solution_id: str,
    numerical_positions: torch.Tensor,
    physical_stage_time: float | torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
) -> torch.Tensor:
    """Return external acceleration from current numerical positions.

    This deliberately thin adapter calls the frozen Stage 01F analytic source
    implementation.  It has no state, cache, residual inputs, or side effects.
    """

    if not torch.is_tensor(numerical_positions):
        raise TypeError("numerical_positions must be a torch.Tensor")
    if numerical_positions.device.type != "cpu" or numerical_positions.dtype != torch.float64:
        raise ValueError("numerical_positions must use float64 on CPU")
    source_positions = numerical_positions
    source_parameters = parameters
    # The frozen MMS-A velocity helper uses ``torch.full_like`` and therefore
    # accepts a numeric translation speed only.  Preserve parameter autograd
    # without changing that frozen module by applying the exact translating
    # coordinate map before calling it with the frozen numeric speed.
    if solution_id.upper().replace("-", "_") in ("A", "MMS_A") and torch.is_tensor(
        parameters.translation_speed
    ):
        speed = parameters.translation_speed
        time = torch.as_tensor(
            physical_stage_time,
            dtype=numerical_positions.dtype,
            device=numerical_positions.device,
        )
        if time.numel() == 1:
            time = time.reshape(1).expand(numerical_positions.shape[0])
        frozen_speed = PARAMETERS.translation_speed
        shift = torch.stack(
            (-(speed - frozen_speed) * time, torch.zeros_like(time)), dim=-1
        )
        source_positions = numerical_positions + shift
        source_parameters = replace(parameters, translation_speed=frozen_speed)
    source = manufactured_acceleration(
        solution_id,
        source_positions,
        physical_stage_time,
        source_parameters,
    )
    if source.shape != numerical_positions.shape:
        raise ValueError("manufactured source must match numerical_positions shape")
    if not bool(torch.isfinite(source.detach()).all()):
        raise FloatingPointError("manufactured source contains nonfinite values")
    return source
