"""Discrete lattice-shell diagnostics for Stage 01D-R3."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import torch


@dataclass(frozen=True)
class SupportMarginSelection:
    target_shell: float
    next_shell: float
    support_ratio: float
    dimensionless_margin: float


def minimal_periodic_offsets(resolution: int) -> tuple[tuple[int, int], ...]:
    """Return one signed representative for every N×N periodic offset."""

    if resolution <= 0 or resolution % 2:
        raise ValueError("resolution must be a positive even integer")
    half = resolution // 2
    values = range(-half + 1, half + 1)
    return tuple((a, b) for a in values for b in values)


def unique_lattice_shells(resolution: int) -> tuple[float, ...]:
    squared = sorted({a * a + b * b for a, b in minimal_periodic_offsets(resolution)})
    return tuple(math.sqrt(value) for value in squared)


def offsets_on_shell(
    resolution: int,
    shell: float,
    *,
    absolute_tolerance: float = 0.0,
) -> tuple[tuple[int, int], ...]:
    if absolute_tolerance < 0.0:
        raise ValueError("absolute_tolerance must be nonnegative")
    return tuple(
        (a, b)
        for a, b in minimal_periodic_offsets(resolution)
        if math.isclose(
            math.hypot(a, b),
            float(shell),
            rel_tol=0.0,
            abs_tol=float(absolute_tolerance),
        )
    )


def select_mid_shell_support(
    resolution: int,
    *,
    target_shell: float = 5.0,
) -> SupportMarginSelection:
    """Select the midpoint between target and the next lattice shell."""

    shells = unique_lattice_shells(resolution)
    matching = [value for value in shells if value == float(target_shell)]
    if len(matching) != 1:
        raise ValueError("target shell is absent or ambiguous")
    next_shell = min(value for value in shells if value > float(target_shell))
    support = 0.5 * (float(target_shell) + next_shell)
    margin = min(support - float(target_shell), next_shell - support)
    return SupportMarginSelection(
        target_shell=float(target_shell),
        next_shell=float(next_shell),
        support_ratio=support,
        dimensionless_margin=margin,
    )


def directed_shell_edge_count(resolution: int, shell: float) -> int:
    return int(resolution * resolution * len(offsets_on_shell(resolution, shell)))


def particle_offset(row: int, col: int, resolution: int) -> tuple[int, int]:
    """Return the signed minimal lattice offset from col to row."""

    if not 0 <= row < resolution**2 or not 0 <= col < resolution**2:
        raise ValueError("particle index is out of range")
    row_x, row_y = divmod(int(row), resolution)
    col_x, col_y = divmod(int(col), resolution)

    def minimum(value: int) -> int:
        half = resolution // 2
        return int((value + half) % resolution - half)

    return minimum(row_x - col_x), minimum(row_y - col_y)


def edge_keys(row: torch.Tensor, col: torch.Tensor, particle_count: int) -> torch.Tensor:
    """Return sorted directed integer keys for exact topology comparison."""

    if row.shape != col.shape or row.ndim != 1:
        raise ValueError("row and col must be equal one-dimensional tensors")
    return torch.sort(row.to(torch.int64) * int(particle_count) + col.to(torch.int64)).values


def switched_edge_keys(
    reference_keys: torch.Tensor,
    current_keys: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return ``(removed, added)`` keys without materializing pair tensors."""

    reference = set(int(value) for value in reference_keys.tolist())
    current = set(int(value) for value in current_keys.tolist())
    removed = torch.tensor(sorted(reference - current), dtype=torch.int64)
    added = torch.tensor(sorted(current - reference), dtype=torch.int64)
    return removed, added


def all_offsets_belong_to_shell(
    pairs: Iterable[tuple[int, int]],
    *,
    resolution: int,
    shell: float,
) -> bool:
    return all(math.hypot(*particle_offset(row, col, resolution)) == shell for row, col in pairs)
