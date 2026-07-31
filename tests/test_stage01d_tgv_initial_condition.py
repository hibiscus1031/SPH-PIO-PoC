"""Stage 01D fixed-physics Taylor--Green initial-condition tests."""

from __future__ import annotations

import math

import torch

from dynamic_solver.density import summation_density
from dynamic_solver.equation_of_state import isothermal_pressure
from dynamic_solver.taylor_green import (
    initialize_taylor_green_state,
    taylor_green_kinetic_energy,
    taylor_green_velocity,
)
from structure_preserving.neighborhood import build_periodic_neighborhood


def test_tgv_state_matches_preregistered_fields_without_mass_retuning() -> None:
    resolution = 16
    state = initialize_taylor_green_state(
        resolution,
        support_ratio=4.0,
        reference_density=1.0,
        velocity_amplitude=1.0,
        physical_viscosity=0.02,
        sound_speed=20.0,
    )
    dx = 2.0 / resolution
    assert state.particle_count == resolution**2
    assert state.time == 0.0
    for tensor in (
        state.positions,
        state.velocities,
        state.masses,
        state.densities,
        state.pressures,
        state.supports,
        state.domain_min,
        state.domain_max,
    ):
        assert tensor.dtype == torch.float64
        assert tensor.device.type == "cpu"
    torch.testing.assert_close(
        state.masses,
        torch.full_like(state.masses, dx**2),
        rtol=0.0,
        atol=0.0,
    )
    torch.testing.assert_close(
        state.supports,
        torch.full_like(state.supports, 4.0 * dx),
        rtol=0.0,
        atol=0.0,
    )
    expected_velocity = torch.stack(
        (
            -torch.sin(math.pi * state.positions[:, 0])
            * torch.cos(math.pi * state.positions[:, 1]),
            torch.cos(math.pi * state.positions[:, 0])
            * torch.sin(math.pi * state.positions[:, 1]),
        ),
        dim=-1,
    )
    torch.testing.assert_close(
        state.velocities,
        expected_velocity,
        rtol=0.0,
        atol=0.0,
    )

    neighborhood = build_periodic_neighborhood(
        state.positions,
        state.supports,
    )
    expected_density = summation_density(
        neighborhood,
        mass=state.masses,
    )
    torch.testing.assert_close(
        state.densities,
        expected_density,
        rtol=0.0,
        atol=0.0,
    )
    expected_pressure = isothermal_pressure(
        expected_density,
        reference_density=1.0,
        sound_speed=20.0,
    )
    torch.testing.assert_close(
        state.pressures,
        expected_pressure,
        rtol=0.0,
        atol=0.0,
    )


def test_tgv_reference_is_periodic_and_has_exact_decay() -> None:
    positions = torch.tensor(
        [
            [-0.75, -0.25],
            [-0.25, 0.25],
            [0.25, 0.75],
        ],
        dtype=torch.float64,
    )
    translated = positions + torch.tensor([2.0, -2.0], dtype=torch.float64)
    initial = taylor_green_velocity(
        positions,
        0.0,
        velocity_amplitude=1.0,
        physical_viscosity=0.02,
    )
    periodic = taylor_green_velocity(
        translated,
        0.0,
        velocity_amplitude=1.0,
        physical_viscosity=0.02,
    )
    torch.testing.assert_close(periodic, initial, rtol=0.0, atol=4.0e-16)

    time = 0.2
    decayed = taylor_green_velocity(
        positions,
        time,
        velocity_amplitude=1.0,
        physical_viscosity=0.02,
    )
    velocity_factor = math.exp(-2.0 * 0.02 * math.pi**2 * time)
    torch.testing.assert_close(
        decayed,
        velocity_factor * initial,
        rtol=2.0e-16,
        atol=2.0e-16,
    )
    energy = taylor_green_kinetic_energy(
        time,
        velocity_amplitude=1.0,
        physical_viscosity=0.02,
    )
    expected_energy = 0.25 * math.exp(-4.0 * 0.02 * math.pi**2 * time)
    torch.testing.assert_close(
        energy,
        torch.tensor(expected_energy, dtype=torch.float64),
        rtol=2.0e-16,
        atol=0.0,
    )


def test_tgv_velocity_amplitude_retains_autograd_graph() -> None:
    amplitude = torch.tensor(1.0, dtype=torch.float64, requires_grad=True)
    state = initialize_taylor_green_state(
        16,
        velocity_amplitude=amplitude,
    )
    assert state.velocities.grad_fn is not None
    state.velocities.square().mean().backward()
    assert amplitude.grad is not None
    assert torch.isfinite(amplitude.grad)
    assert amplitude.grad > 0.0
