"""Atomic-step safety checks and named rejection evidence."""

from __future__ import annotations

import torch

from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph


class StepRejected(RuntimeError):
    pass


def validate_state(state: DynamicParticleState, *, name: str) -> None:
    for field in (state.x_unwrapped, state.x_wrapped, state.velocity, state.density, state.pressure):
        if not bool(torch.isfinite(field.detach()).all()):
            raise StepRejected(f"{name}:nonfinite_state")
    if not bool((state.density.detach() > 0.0).all()):
        raise StepRejected(f"{name}:nonpositive_density")


def validate_graph(graph: ReciprocalGraph, *, name: str) -> None:
    if graph.audit["nonreciprocal_nonself_edge_count"] or graph.audit["duplicate_edge_count"]:
        raise StepRejected(f"{name}:nonreciprocal_or_duplicate_graph")
    if not bool(torch.isfinite(graph.displacement.detach()).all()):
        raise StepRejected(f"{name}:nonfinite_graph")


def validate_force(force: torch.Tensor, *, name: str) -> None:
    if not bool(torch.isfinite(force.detach()).all()):
        raise StepRejected(f"{name}:nonfinite_force")


def validate_hidden(hidden: torch.Tensor, *, name: str) -> None:
    if not bool(torch.isfinite(hidden.detach()).all()):
        raise StepRejected(f"{name}:nonfinite_hidden")

