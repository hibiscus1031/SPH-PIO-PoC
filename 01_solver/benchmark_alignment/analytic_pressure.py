"""Insert the exact incompressible TGV pressure into the frozen pair operator."""

from __future__ import annotations

import torch

from benchmark_alignment.incompressible_tgv_exact import pressure, pressure_acceleration
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.neighborhood import PeriodicNeighborhood


def analytic_pressure_operator_acceleration(neighborhood: PeriodicNeighborhood, *, positions: torch.Tensor, mass: torch.Tensor, density: torch.Tensor, time: float = 0.0, reference_density: float = 1.0, velocity_amplitude: float = 1.0, viscosity: float = 0.02) -> tuple[torch.Tensor, torch.Tensor]:
    exact_pressure = pressure(positions, time, reference_density=reference_density, velocity_amplitude=velocity_amplitude, viscosity=viscosity)
    force = conservative_pressure_forces(neighborhood, mass=mass, density=density, pressure=exact_pressure)
    return exact_pressure, force / mass[:, None]


__all__ = ["analytic_pressure_operator_acceleration", "pressure", "pressure_acceleration"]
