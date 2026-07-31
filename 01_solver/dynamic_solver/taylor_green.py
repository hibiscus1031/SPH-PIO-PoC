"""Fixed-physics Taylor--Green reference and initial state."""

from __future__ import annotations

import math

import torch

from dynamic_solver.density import summation_density
from dynamic_solver.equation_of_state import isothermal_pressure
from dynamic_solver.state import DynamicSPHState
from structure_preserving.neighborhood import (
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


def _validate_positions(positions: torch.Tensor) -> None:
    if not torch.is_tensor(positions) or positions.ndim != 2:
        raise ValueError("positions must have shape [particles, 2]")
    if positions.shape[1] != 2:
        raise ValueError("positions must have shape [particles, 2]")
    if positions.device.type != "cpu" or positions.dtype != torch.float64:
        raise ValueError("positions must use float64 on CPU")
    if not bool(torch.isfinite(positions.detach()).all()):
        raise ValueError("positions must be finite")


def _scalar_like(
    value: float | torch.Tensor,
    reference: torch.Tensor,
    *,
    name: str,
    nonnegative: bool,
) -> torch.Tensor:
    if torch.is_tensor(value):
        if value.numel() != 1:
            raise ValueError(f"{name} must be scalar")
        result = value.reshape(()).to(
            dtype=reference.dtype,
            device=reference.device,
        )
    else:
        result = torch.as_tensor(
            value,
            dtype=reference.dtype,
            device=reference.device,
        )
    detached = result.detach()
    if not bool(torch.isfinite(detached)):
        raise ValueError(f"{name} must be finite")
    if nonnegative and not bool(detached >= 0.0):
        raise ValueError(f"{name} must be nonnegative")
    return result


def taylor_green_velocity(
    positions: torch.Tensor,
    time: float | torch.Tensor = 0.0,
    *,
    velocity_amplitude: float | torch.Tensor = 1.0,
    physical_viscosity: float | torch.Tensor = 0.02,
) -> torch.Tensor:
    r"""Return the preregistered two-dimensional Taylor--Green velocity.

    .. math::

       u_x &= -U_0\sin(\pi x)\cos(\pi y)
              \exp(-2\nu\pi^2t),\\
       u_y &=  U_0\cos(\pi x)\sin(\pi y)
              \exp(-2\nu\pi^2t).
    """

    _validate_positions(positions)
    amplitude = _scalar_like(
        velocity_amplitude,
        positions,
        name="velocity_amplitude",
        nonnegative=False,
    )
    viscosity = _scalar_like(
        physical_viscosity,
        positions,
        name="physical_viscosity",
        nonnegative=True,
    )
    current_time = _scalar_like(
        time,
        positions,
        name="time",
        nonnegative=True,
    )
    x = positions[:, 0]
    y = positions[:, 1]
    decay = torch.exp(-2.0 * viscosity * math.pi**2 * current_time)
    velocity = torch.stack(
        (
            -torch.sin(math.pi * x) * torch.cos(math.pi * y),
            torch.cos(math.pi * x) * torch.sin(math.pi * y),
        ),
        dim=-1,
    )
    return amplitude * decay * velocity


def taylor_green_kinetic_energy(
    time: float | torch.Tensor = 0.0,
    *,
    velocity_amplitude: float | torch.Tensor = 1.0,
    physical_viscosity: float | torch.Tensor = 0.02,
    reference: torch.Tensor | None = None,
) -> torch.Tensor:
    r"""Return the exact domain-mean specific kinetic energy.

    For the preregistered periodic mode,

    .. math::

       E(t)=\frac{U_0^2}{4}\exp(-4\nu\pi^2t).
    """

    if reference is None:
        reference = torch.empty((), dtype=torch.float64, device="cpu")
    if reference.device.type != "cpu" or reference.dtype != torch.float64:
        raise ValueError("reference must use float64 on CPU")
    amplitude = _scalar_like(
        velocity_amplitude,
        reference,
        name="velocity_amplitude",
        nonnegative=False,
    )
    viscosity = _scalar_like(
        physical_viscosity,
        reference,
        name="physical_viscosity",
        nonnegative=True,
    )
    current_time = _scalar_like(
        time,
        reference,
        name="time",
        nonnegative=True,
    )
    return (
        0.25
        * amplitude.square()
        * torch.exp(-4.0 * viscosity * math.pi**2 * current_time)
    )


def initialize_taylor_green_state(
    resolution: int,
    *,
    support_ratio: float = 4.0,
    reference_density: float | torch.Tensor = 1.0,
    velocity_amplitude: float | torch.Tensor = 1.0,
    physical_viscosity: float | torch.Tensor = 0.02,
    sound_speed: float | torch.Tensor = 20.0,
    time: float = 0.0,
    jitter_fraction: float = 0.0,
    seed: int = 20260731,
    domain_minimum: tuple[float, float] = (-1.0, -1.0),
    domain_maximum: tuple[float, float] = (1.0, 1.0),
) -> DynamicSPHState:
    """Build a float64 CPU state without mass or pressure adjustments."""

    if resolution <= 0:
        raise ValueError("resolution must be positive")
    if not math.isfinite(support_ratio) or support_ratio <= 0.0:
        raise ValueError("support_ratio must be finite and positive")
    if not math.isfinite(float(time)) or float(time) < 0.0:
        raise ValueError("time must be finite and nonnegative")
    positions, dx, _ = periodic_cartesian_layout(
        resolution,
        jitter_fraction=jitter_fraction,
        seed=seed,
        dtype=torch.float64,
        domain_minimum=domain_minimum,
        domain_maximum=domain_maximum,
    )
    particle_count = int(positions.shape[0])
    support = support_ratio * dx
    supports = torch.full(
        (particle_count,),
        support,
        dtype=torch.float64,
        device="cpu",
    )
    rho0 = _scalar_like(
        reference_density,
        positions,
        name="reference_density",
        nonnegative=True,
    )
    if not bool(rho0.detach() > 0.0):
        raise ValueError("reference_density must be positive")
    cell_area = torch.full(
        (particle_count,),
        dx**2,
        dtype=torch.float64,
        device="cpu",
    )
    masses = rho0 * cell_area
    neighborhood = build_periodic_neighborhood(
        positions,
        supports,
        domain_minimum=domain_minimum,
        domain_maximum=domain_maximum,
    )
    densities = summation_density(neighborhood, mass=masses)
    pressures = isothermal_pressure(
        densities,
        reference_density=rho0,
        sound_speed=sound_speed,
    )
    velocities = taylor_green_velocity(
        positions,
        time,
        velocity_amplitude=velocity_amplitude,
        physical_viscosity=physical_viscosity,
    )
    domain_min = torch.tensor(domain_minimum, dtype=torch.float64)
    domain_max = torch.tensor(domain_maximum, dtype=torch.float64)
    return DynamicSPHState(
        positions=positions,
        velocities=velocities,
        masses=masses,
        densities=densities,
        pressures=pressures,
        supports=supports,
        domain_min=domain_min,
        domain_max=domain_max,
        time=float(time),
    )
