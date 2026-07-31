"""Stage 01D fixed isothermal equation-of-state tests."""

from __future__ import annotations

import pytest
import torch

from dynamic_solver.equation_of_state import isothermal_pressure


def test_isothermal_eos_is_exact_unclipped_and_differentiable() -> None:
    density = torch.tensor(
        [0.95, 1.0, 1.05],
        dtype=torch.float64,
        requires_grad=True,
    )
    pressure = isothermal_pressure(
        density,
        reference_density=1.0,
        sound_speed=20.0,
    )
    torch.testing.assert_close(
        pressure,
        torch.tensor([-20.0, 0.0, 20.0], dtype=torch.float64),
        rtol=0.0,
        atol=2.0e-14,
    )
    assert pressure[0] < 0.0
    pressure.sum().backward()
    torch.testing.assert_close(
        density.grad,
        torch.full_like(density, 400.0),
        rtol=0.0,
        atol=0.0,
    )


def test_isothermal_eos_rejects_nonpositive_sound_speed_and_float32() -> None:
    density = torch.ones(3, dtype=torch.float64)
    with pytest.raises(ValueError, match="sound_speed must be positive"):
        isothermal_pressure(
            density,
            reference_density=1.0,
            sound_speed=0.0,
        )
    with pytest.raises(ValueError, match="float64 on CPU"):
        isothermal_pressure(
            density.float(),
            reference_density=1.0,
            sound_speed=20.0,
        )
