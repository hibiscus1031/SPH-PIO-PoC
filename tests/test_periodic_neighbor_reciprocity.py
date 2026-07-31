"""Periodic minimum-image, reciprocity, uniqueness, and bounds checks."""

from __future__ import annotations

import pytest

from verification.operator_tools import (
    build_layout,
    evaluate_fluid_neighborhood,
    neighborhood_audit,
)


@pytest.mark.parametrize("resolution", [16, 24, 32])
@pytest.mark.parametrize("jitter_fraction", [0.0, 0.05, 0.10])
def test_periodic_neighbors_are_reciprocal_and_unique(
    resolution: int,
    jitter_fraction: float,
) -> None:
    context, _ = build_layout(resolution, jitter_fraction)
    audit = neighborhood_audit(
        context,
        evaluate_fluid_neighborhood(context),
    )

    assert audit["duplicate_edge_count"] == 0
    assert audit["nonreciprocal_nonself_edge_count"] == 0
    assert audit["out_of_bounds_edge_count"] == 0
    assert audit["missing_self_edge_count"] == 0
    assert audit["self_edge_count"] == resolution**2
    assert audit["omitted_strict_interior_edge_count"] == 0
    assert audit["unexpected_edge_count"] == 0
    assert audit["minimum_image_linf"] <= 2.0e-7
