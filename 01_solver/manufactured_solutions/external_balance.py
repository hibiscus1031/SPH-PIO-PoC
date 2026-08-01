"""Mass-weighted separation of internal and MMS external accelerations."""

from __future__ import annotations

import torch


def force_balance(
    masses: torch.Tensor,
    internal_acceleration: torch.Tensor,
    external_acceleration: torch.Tensor,
) -> dict[str, torch.Tensor]:
    internal = torch.sum(masses[:, None] * internal_acceleration, dim=0)
    external = torch.sum(masses[:, None] * external_acceleration, dim=0)
    total = torch.sum(
        masses[:, None] * (internal_acceleration + external_acceleration), dim=0
    )
    return {
        "internal_force": internal,
        "external_force": external,
        "total_force": total,
        "assembly_defect": total - (internal + external),
    }


def midpoint_momentum_defect(
    masses: torch.Tensor,
    velocity_start: torch.Tensor,
    velocity_end: torch.Tensor,
    midpoint_internal_acceleration: torch.Tensor,
    midpoint_external_acceleration: torch.Tensor,
    dt: float | torch.Tensor,
) -> dict[str, torch.Tensor]:
    momentum_change = torch.sum(masses[:, None] * (velocity_end - velocity_start), dim=0)
    step = torch.as_tensor(dt, dtype=masses.dtype, device=masses.device)
    internal_impulse = step * torch.sum(
        masses[:, None] * midpoint_internal_acceleration, dim=0
    )
    external_impulse = step * torch.sum(
        masses[:, None] * midpoint_external_acceleration, dim=0
    )
    return {
        "momentum_change": momentum_change,
        "internal_impulse": internal_impulse,
        "external_impulse": external_impulse,
        "defect": momentum_change - internal_impulse - external_impulse,
    }
