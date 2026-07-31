"""Manufactured periodic vector-divergence verification."""

from __future__ import annotations

import pytest

from manufactured_fields.periodic import vector_divergence, vector_field
from verification.operator_tools import (
    apply_divergence,
    build_layout,
    error_norms,
    evaluate_fluid_neighborhood,
)


@pytest.mark.parametrize("jitter_fraction", [0.0, 0.05, 0.10])
def test_manufactured_divergence_has_overall_refinement_trend(
    jitter_fraction: float,
) -> None:
    errors = []
    for resolution in (16, 24, 32):
        context, _ = build_layout(resolution, jitter_fraction)
        neighborhood = evaluate_fluid_neighborhood(context)
        positions = context.system.systemState.positions
        numerical = apply_divergence(
            context,
            neighborhood,
            vector_field(positions),
        )
        errors.append(error_norms(numerical, vector_divergence(positions)))

    for norm in ("l1", "l2", "linf"):
        assert errors[-1][norm] < errors[0][norm]
