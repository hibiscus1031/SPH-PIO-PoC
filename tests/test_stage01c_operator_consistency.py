"""Consistency-correction and manufactured-operator checks."""

from __future__ import annotations

import torch

from manufactured_fields.periodic import scalar_field
from structure_preserving.kernels import (
    first_order_corrected_gradient,
    linear_reproducing_edge_weights,
    moment_corrected_laplacian,
    quadratic_weighted_least_squares,
    raw_gradient,
    raw_kernel_moments,
    raw_laplacian,
    shepard_edge_weights,
    moments_from_edge_weights,
)
from structure_preserving.neighborhood import (
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


def test_normalizations_reproduce_required_kernel_moments() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        24,
        jitter_fraction=0.10,
        seed=20261147,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.5 * dx)
    raw = raw_kernel_moments(neighborhood, dx**2)
    shepard = moments_from_edge_weights(
        neighborhood,
        shepard_edge_weights(neighborhood, dx**2),
    )
    reproducing_weights, _ = linear_reproducing_edge_weights(
        neighborhood,
        dx**2,
    )
    reproducing = moments_from_edge_weights(
        neighborhood,
        reproducing_weights,
    )
    assert torch.isfinite(raw["s0"]).all()
    torch.testing.assert_close(
        shepard["s0"],
        torch.ones_like(shepard["s0"]),
        rtol=0.0,
        atol=2.0e-15,
    )
    torch.testing.assert_close(
        reproducing["s0"],
        torch.ones_like(reproducing["s0"]),
        rtol=0.0,
        atol=2.0e-15,
    )
    torch.testing.assert_close(
        reproducing["s1"],
        torch.zeros_like(reproducing["s1"]),
        rtol=0.0,
        atol=2.0e-15,
    )


def test_constant_field_native_differential_operators_are_zero() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        24,
        jitter_fraction=0.10,
        seed=20261171,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.5 * dx)
    constant = torch.ones(positions.shape[0], dtype=positions.dtype)
    raw_g = raw_gradient(neighborhood, constant, dx**2)
    corrected_g, _ = first_order_corrected_gradient(
        neighborhood,
        constant,
        dx**2,
    )
    raw_l = raw_laplacian(neighborhood, constant, dx**2)
    corrected_l, _ = moment_corrected_laplacian(
        neighborhood,
        constant,
        dx**2,
    )
    wls_g, wls_l, _ = quadratic_weighted_least_squares(
        neighborhood,
        constant,
        dx**2,
    )
    for value in (raw_g, corrected_g, raw_l, corrected_l, wls_g, wls_l):
        assert torch.count_nonzero(value) == 0


def test_manufactured_candidate_outputs_are_finite() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        32,
        jitter_fraction=0.10,
        seed=20261189,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 5.0 * dx)
    scalar = scalar_field(positions)
    outputs = [
        raw_gradient(neighborhood, scalar, dx**2),
        raw_laplacian(neighborhood, scalar, dx**2),
        *quadratic_weighted_least_squares(
            neighborhood,
            scalar,
            dx**2,
        )[:2],
    ]
    assert all(torch.isfinite(value).all() for value in outputs)
