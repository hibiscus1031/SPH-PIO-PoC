"""Differentiable kinetic-energy metrics for SPH particle states."""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import Tensor


def _validate_velocity(velocity: Tensor) -> None:
    if not isinstance(velocity, Tensor):
        raise TypeError("velocity must be a torch.Tensor")
    if not velocity.is_floating_point():
        raise TypeError("velocity must be floating point")
    if velocity.ndim != 2 or velocity.shape[0] == 0 or velocity.shape[1] == 0:
        raise ValueError(
            "velocity must have non-empty shape (particles, dimensions); "
            f"got {tuple(velocity.shape)}"
        )


def _particle_mass(mass: Tensor | float | None, velocity: Tensor) -> Tensor:
    count = velocity.shape[0]
    if mass is None:
        return velocity.new_ones(())
    if isinstance(mass, Tensor):
        if mass.device != velocity.device:
            raise ValueError(
                f"mass is on {mass.device}, but velocity is on {velocity.device}"
            )
        if not mass.is_floating_point():
            raise TypeError("mass must be floating point")
        normalized = mass.to(dtype=velocity.dtype)
    else:
        normalized = velocity.new_tensor(mass)

    if normalized.ndim == 0:
        return normalized
    if normalized.shape == (count,):
        return normalized
    if normalized.shape == (count, 1):
        return normalized[:, 0]
    raise ValueError(
        "mass must be scalar or have shape (particles,) or (particles, 1); "
        f"got {tuple(normalized.shape)} for {count} particles"
    )


def _positive_epsilon(tensor: Tensor, eps: float | None) -> Tensor:
    value = torch.finfo(tensor.dtype).eps if eps is None else eps
    if value <= 0:
        raise ValueError(f"eps must be positive, got {value!r}")
    return tensor.new_tensor(value)


def total_kinetic_energy(
    velocity: Tensor,
    mass: Tensor | float | None = None,
) -> Tensor:
    """Return ``0.5 * sum_i mass_i * ||velocity_i||^2``.

    ``mass`` may be scalar, ``(particles,)``, or ``(particles, 1)``.  The
    returned scalar remains connected to both velocity and tensor-valued mass.
    """

    _validate_velocity(velocity)
    normalized_mass = _particle_mass(mass, velocity)
    speed_squared = velocity.square().sum(dim=-1)
    return 0.5 * (speed_squared * normalized_mass).sum()


def relative_energy_error(
    energy: Tensor,
    reference_energy: Tensor | float,
    *,
    eps: float | None = None,
) -> Tensor:
    """Return ``abs(energy-reference) / max(abs(reference), eps)``.

    Both values must be scalar.  The epsilon guard makes zero-energy reference
    cases finite without detaching the numerator from autograd.
    """

    if not isinstance(energy, Tensor):
        raise TypeError("energy must be a torch.Tensor")
    if energy.numel() != 1 or not energy.is_floating_point():
        raise ValueError("energy must be a scalar floating-point tensor")
    energy = energy.reshape(())
    if isinstance(reference_energy, Tensor):
        if reference_energy.device != energy.device:
            raise ValueError("energy and reference_energy must be on the same device")
        if reference_energy.numel() != 1 or not reference_energy.is_floating_point():
            raise ValueError(
                "reference_energy must be a scalar floating-point tensor"
            )
        reference = reference_energy.to(dtype=energy.dtype).reshape(())
    else:
        reference = energy.new_tensor(reference_energy)

    denominator = reference.abs().clamp_min(_positive_epsilon(energy, eps))
    return (energy - reference).abs() / denominator


def kinetic_energy_metrics(
    velocity: Tensor,
    reference_velocity: Tensor,
    *,
    mass: Tensor | float | None = None,
    reference_mass: Tensor | float | None = None,
    eps: float | None = None,
) -> Mapping[str, Tensor]:
    """Return total kinetic energy and error relative to a reference state."""

    reference_mass = mass if reference_mass is None else reference_mass
    energy = total_kinetic_energy(velocity, mass)
    reference = total_kinetic_energy(reference_velocity, reference_mass)
    return {
        "total_kinetic_energy": energy,
        "kinetic_energy_relative_error": relative_energy_error(
            energy, reference, eps=eps
        ),
    }


# Concise aliases for callers that already establish kinetic context.
kinetic_energy = total_kinetic_energy
relative_kinetic_energy_error = relative_energy_error


__all__ = [
    "kinetic_energy",
    "kinetic_energy_metrics",
    "relative_energy_error",
    "relative_kinetic_energy_error",
    "total_kinetic_energy",
]
