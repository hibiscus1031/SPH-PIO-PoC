"""Conservative physical-viscosity pair-force tests."""

from __future__ import annotations

import pytest
import torch

from manufactured_fields.periodic import vector_field
from structure_preserving.conservative_viscosity import (
    conservative_viscosity_forces,
    stage01b_style_generic_acceleration,
    viscosity_conservation_metrics,
    viscosity_gamma,
)
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import (
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


@pytest.mark.parametrize(
    ("dtype", "tolerance"),
    [(torch.float64, 1.0e-12), (torch.float32, 5.0e-6)],
)
def test_variable_density_viscosity_remains_pair_conservative(
    dtype: torch.dtype,
    tolerance: float,
) -> None:
    positions, dx, _ = periodic_cartesian_layout(
        24,
        jitter_fraction=0.10,
        seed=20261037,
        dtype=dtype,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.5 * dx)
    density = 1.0 + 0.05 * torch.sin(2.0 * torch.pi * positions[:, 0])
    metrics = viscosity_conservation_metrics(
        neighborhood,
        mass=dx**2,
        density=density,
        velocity=vector_field(positions),
        physical_viscosity=0.02,
    )
    assert metrics["gamma_minimum"] >= 0.0
    assert metrics["relative_gamma_symmetry_residual"] <= tolerance
    assert metrics["relative_pair_force_residual"] <= tolerance
    assert metrics["relative_total_internal_force"] <= tolerance


def test_viscosity_is_exactly_zero_and_linear_in_physical_nu() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        16,
        jitter_fraction=0.05,
        seed=20261061,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.0 * dx)
    density = 1.0 + 0.05 * torch.sin(2.0 * torch.pi * positions[:, 0])
    velocity = vector_field(positions)
    force_0 = conservative_viscosity_forces(
        neighborhood,
        mass=dx**2,
        density=density,
        velocity=velocity,
        physical_viscosity=0.0,
    )
    force_1 = conservative_viscosity_forces(
        neighborhood,
        mass=dx**2,
        density=density,
        velocity=velocity,
        physical_viscosity=0.02,
    )
    force_2 = conservative_viscosity_forces(
        neighborhood,
        mass=dx**2,
        density=density,
        velocity=velocity,
        physical_viscosity=0.04,
    )
    assert torch.count_nonzero(force_0) == 0
    torch.testing.assert_close(force_2, 2.0 * force_1, rtol=0.0, atol=0.0)


def test_stage01b_comparator_uses_frozen_upstream_regularization() -> None:
    positions, dx, _ = periodic_cartesian_layout(
        24,
        jitter_fraction=0.10,
        seed=20261079,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.5 * dx)
    density = torch.ones(positions.shape[0], dtype=positions.dtype)
    velocity = vector_field(positions)
    stage01b_style = stage01b_style_generic_acceleration(
        neighborhood,
        mass=dx**2,
        density=density,
        velocity=velocity,
        physical_viscosity=0.02,
    )
    gradient = edge_kernel_gradients(neighborhood)
    radial = torch.einsum(
        "nd,nd->n",
        neighborhood.displacement,
        gradient,
    )
    regularized_distance = (
        neighborhood.distance
        + 1.0e-8 * neighborhood.particle_support[neighborhood.row]
    )
    coefficient = (
        -2.0
        * 0.02
        * dx**2
        / density[neighborhood.col]
        * radial
        / regularized_distance.square()
    )
    coefficient = torch.where(
        neighborhood.row != neighborhood.col,
        coefficient,
        torch.zeros_like(coefficient),
    )
    expected = scatter_sum(
        neighborhood.row,
        coefficient[:, None]
        * (
            velocity[neighborhood.col]
            - velocity[neighborhood.row]
        ),
        positions.shape[0],
    )
    torch.testing.assert_close(
        stage01b_style,
        expected,
        rtol=0.0,
        atol=0.0,
    )


def test_viscosity_gamma_rejects_nonfinite_or_wrong_sign_inputs() -> None:
    value = torch.ones(1, dtype=torch.float64)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        viscosity_gamma(value, value, float("nan"), -value, value, value)
    with pytest.raises(ValueError, match=r"r dot grad\(W\) <= 0"):
        viscosity_gamma(value, value, 0.02, value, value, value)
