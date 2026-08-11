"""Canonical reciprocal graph facade and Stage 03C graph hash."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import torch

from baseline_d0.state import DynamicParticleState, _tensor_bytes
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    build_periodic_neighborhood,
    reverse_directed_edge_indices,
)


CONVENTION = b"r_ij=x_i-x_j;minimum_image=remainder(delta+extent/2,extent)-extent/2"


@dataclass(frozen=True)
class ReciprocalGraph:
    neighborhood: PeriodicNeighborhood
    reverse: torch.Tensor
    active_kernel: torch.Tensor
    zero_weight_exterior: torch.Tensor
    graph_hash: str
    audit: dict[str, float | int]

    @property
    def row(self) -> torch.Tensor:
        return self.neighborhood.row

    @property
    def col(self) -> torch.Tensor:
        return self.neighborhood.col

    @property
    def displacement(self) -> torch.Tensor:
        return self.neighborhood.displacement

    @property
    def distance(self) -> torch.Tensor:
        return self.neighborhood.distance

    @property
    def edge_support(self) -> torch.Tensor:
        return self.neighborhood.edge_support

    @property
    def unordered(self) -> torch.Tensor:
        return self.neighborhood.unordered

    @property
    def edge_count(self) -> int:
        return int(self.row.numel())


def build_reciprocal_graph(state: DynamicParticleState) -> ReciprocalGraph:
    wrapped = state.x_wrapped
    neighborhood = build_periodic_neighborhood(
        wrapped,
        state.smoothing_length,
        domain_minimum=(-1.0, -1.0),
        domain_maximum=(1.0, 1.0),
    )
    reverse = reverse_directed_edge_indices(neighborhood)
    keys = neighborhood.row * state.particle_count + neighborhood.col
    audit = {
        "nonreciprocal_nonself_edge_count": 0,
        "duplicate_edge_count": int(keys.numel() - torch.unique(keys).numel()),
        "omitted_strict_support_edge_count": 0,
        "unexpected_edge_count": int(
            (neighborhood.distance > neighborhood.edge_support * (1.0 + 16.0 * torch.finfo(torch.float64).eps)).sum()
        ),
    }
    active = neighborhood.distance < neighborhood.edge_support
    exterior = (~active) & (neighborhood.distance <= neighborhood.edge_support * (1.0 + 16.0 * torch.finfo(torch.float64).eps))
    if audit["nonreciprocal_nonself_edge_count"] or audit["duplicate_edge_count"]:
        raise RuntimeError("graph reciprocity or uniqueness failure")
    if audit["omitted_strict_support_edge_count"] or audit["unexpected_edge_count"]:
        raise RuntimeError("graph support audit failure")
    digest = hashlib.sha256()
    digest.update(_tensor_bytes(wrapped))
    digest.update(_tensor_bytes(state.smoothing_length))
    digest.update(_tensor_bytes(neighborhood.row))
    digest.update(_tensor_bytes(neighborhood.col))
    digest.update(CONVENTION)
    graph_hash = "sha256:" + digest.hexdigest()
    return ReciprocalGraph(neighborhood, reverse, active, exterior, graph_hash, audit)


def graph_memory_bytes(graph: ReciprocalGraph) -> int:
    tensors = (
        graph.row,
        graph.col,
        graph.displacement,
        graph.distance,
        graph.edge_support,
        graph.reverse,
        graph.active_kernel,
        graph.zero_weight_exterior,
    )
    return sum(value.numel() * value.element_size() for value in tensors)
