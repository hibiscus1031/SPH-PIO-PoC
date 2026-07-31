"""Discrete viscous-power identity tests."""

from __future__ import annotations

import math

import torch

from manufactured_fields.periodic import vector_field
from structure_preserving.conservative_viscosity import (
    viscosity_conservation_metrics,
)
from structure_preserving.neighborhood import (
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


def test_viscous_power_is_nonpositive_and_matches_pair_identity() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        32,
        jitter_fraction=0.10,
        seed=20261103,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 5.0 * dx)
    density = 1.0 + 0.05 * torch.sin(2.0 * torch.pi * positions[:, 0])
    metrics = viscosity_conservation_metrics(
        neighborhood,
        mass=dx**2,
        density=density,
        velocity=vector_field(positions),
        physical_viscosity=0.02,
    )
    assert metrics["accumulated_viscous_power"] <= 0.0
    assert metrics["pair_direct_viscous_power"] <= 0.0
    assert metrics["power_identity_absolute_difference"] <= 1.0e-12
    assert math.isfinite(metrics["minimum_image_pair_torque_linf"])


def test_noncentral_viscous_force_does_not_claim_angular_conservation() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        24,
        jitter_fraction=0.10,
        seed=20261121,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.5 * dx)
    metrics = viscosity_conservation_metrics(
        neighborhood,
        mass=dx**2,
        density=1.0,
        velocity=vector_field(positions),
        physical_viscosity=0.02,
    )
    assert metrics["minimum_image_pair_torque_linf"] > 0.0
