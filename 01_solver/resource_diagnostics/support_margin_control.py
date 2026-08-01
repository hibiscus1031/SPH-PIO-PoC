"""Support-margin geometry and topology identity checks for Control M."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import torch

from dynamic_solver.state import DynamicSPHState
from resource_diagnostics.cutoff_shell_audit import offsets_on_shell
from structure_preserving.neighborhood import PeriodicNeighborhood, minimum_image


@dataclass(frozen=True)
class MarginPairSet:
    row: torch.Tensor
    col: torch.Tensor
    expected_shells: torch.Tensor
    dx: float


def make_margin_pair_set(
    *,
    resolution: int,
    dx: float,
    lower_shell: float,
    upper_shell: float,
) -> MarginPairSet:
    rows: list[int] = []
    cols: list[int] = []
    shells: list[float] = []
    for shell in (lower_shell, upper_shell):
        for offset_x, offset_y in offsets_on_shell(resolution, shell):
            for x in range(resolution):
                for y in range(resolution):
                    rows.append(x * resolution + y)
                    cols.append(
                        ((x - offset_x) % resolution) * resolution
                        + ((y - offset_y) % resolution)
                    )
                    shells.append(float(shell))
    return MarginPairSet(
        row=torch.tensor(rows, dtype=torch.int64),
        col=torch.tensor(cols, dtype=torch.int64),
        expected_shells=torch.tensor(shells, dtype=torch.float64),
        dx=float(dx),
    )


def minimum_cutoff_margin_ratio(
    state: DynamicSPHState,
    pairs: MarginPairSet,
    support_ratio: float,
) -> float:
    extent = state.domain_max - state.domain_min
    displacement = minimum_image(
        state.positions[pairs.row] - state.positions[pairs.col],
        extent,
    )
    shell_distance = torch.linalg.vector_norm(displacement, dim=-1) / pairs.dx
    return float(torch.min(torch.abs(shell_distance - float(support_ratio))))


def edge_identity_sha256(neighborhood: PeriodicNeighborhood) -> str:
    keys = (
        neighborhood.row.to(torch.int64) * neighborhood.particle_count
        + neighborhood.col.to(torch.int64)
    ).contiguous()
    return hashlib.sha256(keys.numpy().tobytes()).hexdigest()


def lightweight_topology_invariants(
    neighborhood: PeriodicNeighborhood,
) -> dict[str, int | str]:
    row = neighborhood.row
    col = neighborhood.col
    keys = row * neighborhood.particle_count + col
    unique = torch.unique(keys, sorted=True)
    reverse = col * neighborhood.particle_count + row
    locations = torch.searchsorted(unique, reverse)
    found = (
        (locations < unique.numel())
        & (unique[locations.clamp_max(unique.numel() - 1)] == reverse)
    )
    return {
        "edge_count": int(keys.numel()),
        "duplicate_edge_count": int(keys.numel() - unique.numel()),
        "nonreciprocal_edge_count": int((~found).sum()),
        "edge_identity_sha256": edge_identity_sha256(neighborhood),
    }
