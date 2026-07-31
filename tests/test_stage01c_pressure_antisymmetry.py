"""Conservative pressure pair-force tests."""

from __future__ import annotations

import pytest
import torch

from structure_preserving.conservative_pressure import (
    pressure_conservation_metrics,
)
from structure_preserving.neighborhood import (
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


@pytest.mark.parametrize(
    ("dtype", "tolerance"),
    [(torch.float64, 1.0e-12), (torch.float32, 5.0e-6)],
)
def test_pressure_is_conservative_for_all_pressure_signs(
    dtype: torch.dtype,
    tolerance: float,
) -> None:
    positions, dx, _ = periodic_cartesian_layout(
        24,
        jitter_fraction=0.10,
        seed=20261019,
        dtype=dtype,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.5 * dx)
    x, y = positions[:, 0], positions[:, 1]
    density_cases = (
        torch.ones_like(x),
        1.0 + 0.05 * torch.sin(2.0 * torch.pi * x),
    )
    pressure_cases = (
        0.10 + 0.02 * torch.sin(2.0 * torch.pi * x),
        -0.10 + 0.02 * torch.sin(2.0 * torch.pi * x),
        0.05 * torch.sin(2.0 * torch.pi * x)
        - 0.03 * torch.cos(2.0 * torch.pi * y),
    )
    for density in density_cases:
        for pressure in pressure_cases:
            metrics = pressure_conservation_metrics(
                neighborhood,
                mass=dx**2,
                density=density,
                pressure=pressure,
            )
            assert metrics["relative_pair_force_residual"] <= tolerance
            assert metrics["relative_total_internal_force"] <= tolerance
            assert metrics["relative_pair_torque_linf"] <= tolerance
            assert metrics["relative_total_pair_torque"] <= tolerance
