"""Closed-form two-dimensional incompressible Taylor--Green vortex fields."""

from __future__ import annotations

import math
import torch


def _positions(value: torch.Tensor) -> torch.Tensor:
    if not torch.is_tensor(value) or value.ndim != 2 or value.shape[1] != 2:
        raise ValueError("positions must have shape [particles, 2]")
    if value.dtype != torch.float64 or value.device.type != "cpu":
        raise ValueError("positions must be float64 on CPU")
    if not bool(torch.isfinite(value).all()):
        raise ValueError("positions must be finite")
    return value


def amplitude(time: float | torch.Tensor, *, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    t = torch.as_tensor(time, dtype=torch.float64, device="cpu")
    return torch.exp(-2.0 * viscosity * wave_number**2 * t)


def velocity(positions: torch.Tensor, time: float = 0.0, *, velocity_amplitude: float = 1.0, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    p = _positions(positions); x, y = p[:, 0], p[:, 1]; a = amplitude(time, viscosity=viscosity, wave_number=wave_number)
    return velocity_amplitude * a * torch.stack((-torch.sin(wave_number*x)*torch.cos(wave_number*y), torch.cos(wave_number*x)*torch.sin(wave_number*y)), dim=-1)


def pressure(positions: torch.Tensor, time: float = 0.0, *, reference_density: float = 1.0, velocity_amplitude: float = 1.0, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    p = _positions(positions); x, y = p[:, 0], p[:, 1]; a = amplitude(time, viscosity=viscosity, wave_number=wave_number)
    return reference_density * velocity_amplitude**2 * a.square() * (torch.cos(2*wave_number*x) + torch.cos(2*wave_number*y)) / 4.0


def partial_time_velocity(positions: torch.Tensor, time: float = 0.0, **kwargs: float) -> torch.Tensor:
    viscosity = float(kwargs.get("viscosity", 0.02)); wave_number = float(kwargs.get("wave_number", math.pi))
    return -2.0 * viscosity * wave_number**2 * velocity(positions, time, **kwargs)


def convective_acceleration(positions: torch.Tensor, time: float = 0.0, *, velocity_amplitude: float = 1.0, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    p = _positions(positions); x, y = p[:, 0], p[:, 1]; a = amplitude(time, viscosity=viscosity, wave_number=wave_number)
    coefficient = 0.5 * velocity_amplitude**2 * a.square() * wave_number
    return coefficient * torch.stack((torch.sin(2*wave_number*x), torch.sin(2*wave_number*y)), dim=-1)


def pressure_acceleration(positions: torch.Tensor, time: float = 0.0, *, reference_density: float = 1.0, velocity_amplitude: float = 1.0, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    del reference_density
    return convective_acceleration(positions, time, velocity_amplitude=velocity_amplitude, viscosity=viscosity, wave_number=wave_number)


def viscous_acceleration(positions: torch.Tensor, time: float = 0.0, *, velocity_amplitude: float = 1.0, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    return -2.0 * viscosity * wave_number**2 * velocity(positions, time, velocity_amplitude=velocity_amplitude, viscosity=viscosity, wave_number=wave_number)


def material_acceleration(positions: torch.Tensor, time: float = 0.0, *, reference_density: float = 1.0, velocity_amplitude: float = 1.0, viscosity: float = 0.02, wave_number: float = math.pi) -> torch.Tensor:
    return partial_time_velocity(positions, time, velocity_amplitude=velocity_amplitude, viscosity=viscosity, wave_number=wave_number) + convective_acceleration(positions, time, velocity_amplitude=velocity_amplitude, viscosity=viscosity, wave_number=wave_number)

