"""Deterministic periodic neighborhoods with explicit structural audits."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable

import torch


@dataclass(frozen=True)
class PeriodicNeighborhood:
    """A deduplicated directed periodic neighbor graph."""

    row: torch.Tensor
    col: torch.Tensor
    displacement: torch.Tensor
    distance: torch.Tensor
    edge_support: torch.Tensor
    particle_support: torch.Tensor
    domain_min: torch.Tensor
    domain_max: torch.Tensor
    particle_count: int

    @property
    def nonself(self) -> torch.Tensor:
        return self.row != self.col

    @property
    def unordered(self) -> torch.Tensor:
        return self.row < self.col


def tensor_sha256(value: torch.Tensor) -> str:
    """Return a reproducible hash of tensor values and dtype."""

    array = value.detach().contiguous().cpu().numpy()
    payload = str(value.dtype).encode("ascii") + b"\0" + array.tobytes()
    return hashlib.sha256(payload).hexdigest()


def minimum_image(
    displacement: torch.Tensor,
    extent: torch.Tensor,
) -> torch.Tensor:
    """Apply the minimum-image convention in every periodic dimension."""

    return torch.remainder(displacement + 0.5 * extent, extent) - 0.5 * extent


def wrap_periodic(
    positions: torch.Tensor,
    domain_min: torch.Tensor,
    domain_max: torch.Tensor,
) -> torch.Tensor:
    extent = domain_max - domain_min
    return torch.remainder(positions - domain_min, extent) + domain_min


def periodic_cartesian_layout(
    resolution: int,
    *,
    jitter_fraction: float,
    seed: int,
    dtype: torch.dtype = torch.float64,
    domain_minimum: tuple[float, float] = (-1.0, -1.0),
    domain_maximum: tuple[float, float] = (1.0, 1.0),
) -> tuple[torch.Tensor, float, str]:
    """Create the preregistered Cartesian or uniformly jittered layout."""

    if resolution <= 0:
        raise ValueError("resolution must be positive")
    if jitter_fraction not in (0.0, 0.05, 0.10):
        raise ValueError("jitter_fraction must be 0, 0.05, or 0.10")
    domain_min = torch.tensor(domain_minimum, dtype=dtype)
    domain_max = torch.tensor(domain_maximum, dtype=dtype)
    extent = domain_max - domain_min
    if not bool(torch.allclose(extent, extent[0].expand_as(extent))):
        raise ValueError("Stage 01C layouts require a square domain")
    dx = float(extent[0]) / resolution
    axis = (
        torch.arange(resolution, dtype=dtype) + 0.5
    ) * dx + domain_min[0]
    grid_x, grid_y = torch.meshgrid(axis, axis, indexing="ij")
    positions = torch.stack((grid_x.reshape(-1), grid_y.reshape(-1)), dim=-1)
    if jitter_fraction:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(int(seed))
        jitter = (
            2.0
            * torch.rand(
                positions.shape,
                dtype=dtype,
                generator=generator,
            )
            - 1.0
        )
        positions = positions + jitter_fraction * dx * jitter
        positions = wrap_periodic(positions, domain_min, domain_max)
    return positions, dx, tensor_sha256(positions)


def deduplicate_directed_edges(
    row: torch.Tensor,
    col: torch.Tensor,
    particle_count: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return lexicographically sorted unique directed edges."""

    if row.shape != col.shape:
        raise ValueError("row and col must have the same shape")
    if row.ndim != 1:
        raise ValueError("row and col must be one-dimensional")
    row64 = row.to(torch.int64)
    col64 = col.to(torch.int64)
    if row64.numel() == 0:
        return row64, col64
    if bool(
        ((row64 < 0) | (row64 >= particle_count)).any()
        or ((col64 < 0) | (col64 >= particle_count)).any()
    ):
        raise ValueError("edge indices are out of bounds")
    keys = torch.unique(row64 * particle_count + col64, sorted=True)
    return keys // particle_count, keys % particle_count


def reverse_directed_edge_indices(
    neighborhood: PeriodicNeighborhood,
) -> torch.Tensor:
    """Locate each directed edge's independently stored reverse edge."""

    keys = (
        neighborhood.row * neighborhood.particle_count
        + neighborhood.col
    )
    reverse_keys = (
        neighborhood.col * neighborhood.particle_count
        + neighborhood.row
    )
    reverse = torch.searchsorted(keys, reverse_keys)
    if reverse.numel() == 0:
        return reverse
    bounded = reverse.clamp_max(keys.numel() - 1)
    valid = (reverse < keys.numel()) & (keys[bounded] == reverse_keys)
    if not bool(valid.all()):
        raise RuntimeError("periodic neighborhood is not reciprocal")
    return reverse


def _cell_members(
    positions: torch.Tensor,
    domain_min: torch.Tensor,
    cell_size: torch.Tensor,
    cells_per_axis: int,
) -> dict[int, torch.Tensor]:
    coordinates = torch.floor(
        (positions - domain_min) / cell_size
    ).to(torch.int64)
    coordinates = torch.remainder(coordinates, cells_per_axis)
    linear = coordinates[:, 0] * cells_per_axis + coordinates[:, 1]
    members: dict[int, torch.Tensor] = {}
    for cell in torch.unique(linear, sorted=True).tolist():
        members[int(cell)] = torch.nonzero(
            linear == int(cell),
            as_tuple=False,
        ).reshape(-1)
    return members


def _neighbor_cell_ids(
    cell: int,
    cells_per_axis: int,
) -> Iterable[int]:
    x = cell // cells_per_axis
    y = cell % cells_per_axis
    for offset_x in (-1, 0, 1):
        for offset_y in (-1, 0, 1):
            nx = (x + offset_x) % cells_per_axis
            ny = (y + offset_y) % cells_per_axis
            yield nx * cells_per_axis + ny


def build_periodic_neighborhood(
    positions: torch.Tensor,
    support: float | torch.Tensor,
    *,
    domain_minimum: tuple[float, float] = (-1.0, -1.0),
    domain_maximum: tuple[float, float] = (1.0, 1.0),
) -> PeriodicNeighborhood:
    """Build an exact compact-support graph using a periodic cell list."""

    if positions.ndim != 2 or positions.shape[1] != 2:
        raise ValueError("positions must have shape [particles, 2]")
    if positions.device.type != "cpu":
        raise ValueError("Stage 01C neighborhood construction is CPU-only")
    count = int(positions.shape[0])
    domain_min = torch.tensor(
        domain_minimum,
        dtype=positions.dtype,
        device=positions.device,
    )
    domain_max = torch.tensor(
        domain_maximum,
        dtype=positions.dtype,
        device=positions.device,
    )
    extent = domain_max - domain_min
    if torch.is_tensor(support):
        particle_support = support.to(
            dtype=positions.dtype,
            device=positions.device,
        ).reshape(-1)
        if particle_support.numel() == 1:
            particle_support = particle_support.expand(count).clone()
        elif particle_support.numel() != count:
            raise ValueError("support must be scalar or one value per particle")
    else:
        particle_support = torch.full(
            (count,),
            float(support),
            dtype=positions.dtype,
            device=positions.device,
        )
    if bool(
        (~torch.isfinite(particle_support)).any()
        or (particle_support <= 0).any()
    ):
        raise ValueError("support values must be finite and positive")
    maximum_support = float(particle_support.max())
    if maximum_support >= 0.5 * float(extent.min()):
        raise ValueError(
            "compact support must be smaller than half the periodic extent"
        )
    cells_per_axis = max(1, int(math.floor(float(extent.min()) / maximum_support)))
    cell_size = extent / cells_per_axis
    members = _cell_members(
        positions,
        domain_min,
        cell_size,
        cells_per_axis,
    )

    row_blocks: list[torch.Tensor] = []
    col_blocks: list[torch.Tensor] = []
    eps = torch.finfo(positions.dtype).eps
    for cell, indices_i in members.items():
        for neighbor_cell in _neighbor_cell_ids(cell, cells_per_axis):
            indices_j = members.get(neighbor_cell)
            if indices_j is None:
                continue
            row = indices_i.repeat_interleave(indices_j.numel())
            col = indices_j.repeat(indices_i.numel())
            delta = minimum_image(positions[row] - positions[col], extent)
            distance = torch.linalg.vector_norm(delta, dim=-1)
            edge_support = 0.5 * (
                particle_support[row] + particle_support[col]
            )
            retained = distance <= edge_support * (1.0 + 16.0 * eps)
            if bool(retained.any()):
                row_blocks.append(row[retained])
                col_blocks.append(col[retained])
    if not row_blocks:
        raise RuntimeError("periodic neighborhood construction returned no edges")
    row, col = deduplicate_directed_edges(
        torch.cat(row_blocks),
        torch.cat(col_blocks),
        count,
    )
    keys = row * count + col
    reverse_keys = col * count + row
    reverse = torch.searchsorted(keys, reverse_keys)
    bounded = reverse.clamp_max(keys.numel() - 1)
    if not bool(
        ((reverse < keys.numel()) & (keys[bounded] == reverse_keys)).all()
    ):
        raise RuntimeError("constructed periodic neighborhood is not reciprocal")
    displacement = torch.zeros(
        (row.numel(), positions.shape[1]),
        dtype=positions.dtype,
        device=positions.device,
    )
    unordered = row < col
    canonical = minimum_image(
        positions[row[unordered]] - positions[col[unordered]],
        extent,
    )
    displacement[unordered] = canonical
    displacement[reverse[unordered]] = -canonical
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    edge_support = 0.5 * (
        particle_support[row] + particle_support[col]
    )
    return PeriodicNeighborhood(
        row=row,
        col=col,
        displacement=displacement,
        distance=distance,
        edge_support=edge_support,
        particle_support=particle_support,
        domain_min=domain_min,
        domain_max=domain_max,
        particle_count=count,
    )


def audit_periodic_neighborhood(
    positions: torch.Tensor,
    neighborhood: PeriodicNeighborhood,
    *,
    reference_chunk_size: int = 256,
) -> dict[str, float | int]:
    """Audit topology against a chunked all-pairs compact-support reference."""

    row = neighborhood.row
    col = neighborhood.col
    count = neighborhood.particle_count
    extent = neighborhood.domain_max - neighborhood.domain_min
    keys = row * count + col
    unique_keys, key_counts = torch.unique(
        keys,
        sorted=True,
        return_counts=True,
    )
    reverse_keys = col * count + row
    reverse_location = torch.searchsorted(unique_keys, reverse_keys)
    reverse_found = (
        (reverse_location < unique_keys.numel())
        & (
            unique_keys[
                reverse_location.clamp_max(unique_keys.numel() - 1)
            ]
            == reverse_keys
        )
    )
    self_edges = row == col
    out_of_bounds = (
        (row < 0) | (row >= count) | (col < 0) | (col >= count)
    )
    recomputed = minimum_image(positions[row] - positions[col], extent)
    minimum_image_linf = float(
        (recomputed - neighborhood.displacement).abs().max()
    )
    eps = torch.finfo(positions.dtype).eps
    strict_factor = 1.0 - 64.0 * eps
    missing_strict = 0
    expected_strict_count = 0
    supports = neighborhood.particle_support
    for start in range(0, count, reference_chunk_size):
        stop = min(start + reference_chunk_size, count)
        delta = minimum_image(
            positions[start:stop, None, :] - positions[None, :, :],
            extent,
        )
        distance = torch.linalg.vector_norm(delta, dim=-1)
        pair_support = 0.5 * (
            supports[start:stop, None] + supports[None, :]
        )
        expected = torch.nonzero(
            distance < pair_support * strict_factor,
            as_tuple=False,
        )
        expected_keys = (
            (expected[:, 0] + start) * count + expected[:, 1]
        )
        locations = torch.searchsorted(unique_keys, expected_keys)
        found = (
            (locations < unique_keys.numel())
            & (
                unique_keys[
                    locations.clamp_max(unique_keys.numel() - 1)
                ]
                == expected_keys
            )
        )
        missing_strict += int((~found).sum())
        expected_strict_count += int(expected_keys.numel())

    unexpected = neighborhood.distance > (
        neighborhood.edge_support * (1.0 + 64.0 * eps)
    )
    counts = torch.bincount(row, minlength=count).to(positions.dtype)
    nonself_counts = torch.bincount(
        row[row != col],
        minlength=count,
    ).to(positions.dtype)
    return {
        "edge_count": int(keys.numel()),
        "unique_edge_count": int(unique_keys.numel()),
        "duplicate_edge_count": int((key_counts - 1).clamp_min(0).sum()),
        "self_edge_count": int(self_edges.sum()),
        "missing_self_edge_count": int(
            count - torch.unique(row[self_edges]).numel()
        ),
        "nonreciprocal_nonself_edge_count": int(
            (~reverse_found[row != col]).sum()
        ),
        "out_of_bounds_edge_count": int(out_of_bounds.sum()),
        "omitted_strict_support_edge_count": int(missing_strict),
        "unexpected_edge_count": int(unexpected.sum()),
        "minimum_image_linf": minimum_image_linf,
        "expected_strict_edge_count": expected_strict_count,
        "neighbor_count_mean": float(counts.mean()),
        "neighbor_count_std": float(counts.std(unbiased=True)),
        "neighbor_count_median": float(counts.median()),
        "neighbor_count_min": int(counts.min()),
        "neighbor_count_max": int(counts.max()),
        "nonself_neighbor_count_mean": float(nonself_counts.mean()),
    }
