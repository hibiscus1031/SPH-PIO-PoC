"""Stage 01C periodic-neighborhood structural qualification."""

from __future__ import annotations

import torch

from structure_preserving.neighborhood import (
    audit_periodic_neighborhood,
    build_periodic_neighborhood,
    deduplicate_directed_edges,
    periodic_cartesian_layout,
    reverse_directed_edge_indices,
)
from structure_preserving.run_static_requalification import compute_static_case
from structure_preserving.support_scaling import load_preregistered_design


def test_duplicate_directed_edges_are_removed_by_construction() -> None:
    row = torch.tensor([0, 0, 0, 1, 1, 1, 1])
    col = torch.tensor([0, 1, 1, 0, 0, 1, 1])
    unique_row, unique_col = deduplicate_directed_edges(row, col, 2)
    assert list(zip(unique_row.tolist(), unique_col.tolist())) == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ]


def test_periodic_neighbor_graph_passes_full_structural_audit() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        32,
        jitter_fraction=0.10,
        seed=20261001,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 5.0 * dx)
    audit = audit_periodic_neighborhood(positions, neighborhood)
    assert audit["duplicate_edge_count"] == 0
    assert audit["missing_self_edge_count"] == 0
    assert audit["nonreciprocal_nonself_edge_count"] == 0
    assert audit["out_of_bounds_edge_count"] == 0
    assert audit["omitted_strict_support_edge_count"] == 0
    assert audit["unexpected_edge_count"] == 0
    assert (
        audit["minimum_image_linf"]
        <= 64.0 * torch.finfo(positions.dtype).eps * 2.0
    )


def test_reverse_edges_share_exact_pair_defined_geometry() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        32,
        jitter_fraction=0.10,
        seed=20261019,
        dtype=torch.float32,
    )
    neighborhood = build_periodic_neighborhood(positions, 5.0 * dx)
    reverse = reverse_directed_edge_indices(neighborhood)
    torch.testing.assert_close(
        neighborhood.displacement[reverse],
        -neighborhood.displacement,
        rtol=0.0,
        atol=0.0,
    )
    torch.testing.assert_close(
        neighborhood.distance[reverse],
        neighborhood.distance,
        rtol=0.0,
        atol=0.0,
    )
    torch.testing.assert_close(
        neighborhood.edge_support[reverse],
        neighborhood.edge_support,
        rtol=0.0,
        atol=0.0,
    )


def test_preregistered_increasing_support_still_decreases() -> None:
    design, _ = load_preregistered_design()
    supports = [
        design.support("increasing_neighbor", resolution)
        for resolution in design.resolutions
    ]
    assert all(
        left > right
        for left, right in zip(supports, supports[1:])
    )


def test_precision_cases_share_one_canonical_reference_layout() -> None:
    reference, _, reference_hash = periodic_cartesian_layout(
        16,
        jitter_fraction=0.10,
        seed=20261001,
        dtype=torch.float64,
    )
    common = {
        "family": "constant_neighbor",
        "resolution": 16,
        "jitter": 0.10,
        "seed": 20261001,
        "support_ratio": 4.0,
        "include_conservation": False,
        "experiment_scope": "precision_isolation_test",
        "reference_positions": reference,
        "reference_position_hash": reference_hash,
    }
    float32, _, _ = compute_static_case(dtype=torch.float32, **common)
    float64, _, _ = compute_static_case(dtype=torch.float64, **common)
    assert float32["position_reference_sha256"] == reference_hash
    assert float64["position_reference_sha256"] == reference_hash
    assert float64["position_state_sha256"] == reference_hash
    assert float32["position_state_sha256"] != reference_hash
