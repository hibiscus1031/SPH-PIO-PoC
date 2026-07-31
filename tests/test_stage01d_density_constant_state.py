"""Stage 01D kernel-summation density tests."""

from __future__ import annotations

import torch

from dynamic_solver.density import recompute_density, summation_density
from dynamic_solver.state import DynamicSPHState
from structure_preserving.kernels import edge_kernel_values, scatter_sum
from structure_preserving.neighborhood import (
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


def _constant_state() -> tuple[DynamicSPHState, object, float]:
    positions, dx, _ = periodic_cartesian_layout(
        16,
        jitter_fraction=0.0,
        seed=20260731,
        dtype=torch.float64,
    )
    count = positions.shape[0]
    supports = torch.full((count,), 4.0 * dx, dtype=torch.float64)
    neighborhood = build_periodic_neighborhood(positions, supports)
    state = DynamicSPHState(
        positions=positions,
        velocities=torch.zeros_like(positions),
        masses=torch.full((count,), dx**2, dtype=torch.float64),
        densities=torch.ones(count, dtype=torch.float64),
        pressures=torch.zeros(count, dtype=torch.float64),
        supports=supports,
        domain_min=torch.tensor([-1.0, -1.0], dtype=torch.float64),
        domain_max=torch.tensor([1.0, 1.0], dtype=torch.float64),
        time=0.0,
    )
    return state, neighborhood, dx


def test_constant_periodic_state_uses_exact_mass_weighted_kernel_sum() -> None:
    state, neighborhood, _ = _constant_state()
    density = summation_density(neighborhood, mass=state.masses)
    direct = scatter_sum(
        neighborhood.row,
        state.masses[neighborhood.col]
        * edge_kernel_values(neighborhood),
        state.particle_count,
    )
    torch.testing.assert_close(density, direct, rtol=0.0, atol=0.0)
    assert density.dtype == torch.float64
    assert density.device.type == "cpu"
    assert torch.isfinite(density).all()
    assert bool((density > 0.0).all())
    torch.testing.assert_close(
        density,
        density[0].expand_as(density),
        rtol=0.0,
        atol=2.0e-15,
    )


def test_density_update_is_functional_and_preserves_autograd() -> None:
    state, neighborhood, _ = _constant_state()
    differentiable_mass = state.masses.clone().requires_grad_(True)
    graph_state = state.with_updates(masses=differentiable_mass)
    updated = recompute_density(graph_state, neighborhood)
    assert updated is not graph_state
    assert updated.positions is graph_state.positions
    assert updated.velocities is graph_state.velocities
    assert updated.masses is differentiable_mass
    updated.densities.sum().backward()
    assert differentiable_mass.grad is not None
    assert torch.isfinite(differentiable_mass.grad).all()
    assert bool((differentiable_mass.grad > 0.0).all())
