"""Differentiable linear-momentum and finite-state diagnostics.

The numerical reductions in this module remain on the input device and retain
autograd history.  Boolean finite-state checks are diagnostics and naturally
do not carry gradients.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import torch
from torch import Tensor


def _validate_velocity(velocity: Tensor) -> None:
    if not isinstance(velocity, Tensor):
        raise TypeError("velocity must be a torch.Tensor")
    if not velocity.is_floating_point():
        raise TypeError("velocity must be floating point")
    if velocity.ndim != 2:
        raise ValueError(
            "velocity must have shape (particles, dimensions); "
            f"got {tuple(velocity.shape)}"
        )
    if velocity.shape[0] == 0 or velocity.shape[1] == 0:
        raise ValueError("velocity must contain particles and vector components")


def _particle_mass(mass: Tensor | float | None, velocity: Tensor) -> Tensor:
    """Normalize scalar or per-particle mass to a broadcastable tensor."""

    particle_count = velocity.shape[0]
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
    if normalized.shape == (particle_count,):
        return normalized[:, None]
    if normalized.shape == (particle_count, 1):
        return normalized
    raise ValueError(
        "mass must be scalar or have shape (particles,) or (particles, 1); "
        f"got {tuple(normalized.shape)} for {particle_count} particles"
    )


def _positive_epsilon(tensor: Tensor, eps: float | None) -> Tensor:
    value = torch.finfo(tensor.dtype).eps if eps is None else eps
    if value <= 0:
        raise ValueError(f"eps must be positive, got {value!r}")
    return tensor.new_tensor(value)


def total_momentum(
    velocity: Tensor,
    mass: Tensor | float | None = None,
) -> Tensor:
    """Return total linear momentum ``sum_i mass_i * velocity_i``.

    Args:
        velocity: Floating tensor with shape ``(particles, dimensions)``.
        mass: A scalar mass, ``(particles,)`` masses, ``(particles, 1)``
            masses, or ``None`` for unit mass.

    Returns:
        A tensor of shape ``(dimensions,)`` on the velocity device.
    """

    _validate_velocity(velocity)
    normalized_mass = _particle_mass(mass, velocity)
    return (velocity * normalized_mass).sum(dim=0)


def relative_momentum_drift(
    momentum: Tensor,
    reference_momentum: Tensor,
    *,
    scale: Tensor | float | None = None,
    eps: float | None = None,
) -> Tensor:
    """Return relative L2 drift from a reference total momentum.

    By default the denominator is ``||reference_momentum||_2``.  For
    zero-net-momentum flows such as Taylor--Green vortex, callers may supply a
    physically meaningful positive ``scale`` (for example initial total
    absolute particle momentum).  In all cases the denominator is clamped by
    ``eps`` so that exact zero drift remains zero and no NaN/Inf is introduced.
    """

    if not isinstance(momentum, Tensor) or not isinstance(reference_momentum, Tensor):
        raise TypeError("momentum and reference_momentum must be torch.Tensor objects")
    if momentum.shape != reference_momentum.shape or momentum.numel() == 0:
        raise ValueError(
            "momentum and reference_momentum must be non-empty and have the "
            f"same shape; got {tuple(momentum.shape)} and "
            f"{tuple(reference_momentum.shape)}"
        )
    if not momentum.is_floating_point() or not reference_momentum.is_floating_point():
        raise TypeError("momentum tensors must be floating point")
    if momentum.device != reference_momentum.device:
        raise ValueError("momentum tensors must be on the same device")
    if momentum.dtype != reference_momentum.dtype:
        raise ValueError("momentum tensors must have the same dtype")

    numerator = torch.linalg.vector_norm((momentum - reference_momentum).reshape(-1))
    if scale is None:
        denominator = torch.linalg.vector_norm(reference_momentum.reshape(-1))
    elif isinstance(scale, Tensor):
        if scale.device != momentum.device:
            raise ValueError("scale and momentum must be on the same device")
        if scale.numel() != 1:
            raise ValueError("scale must be scalar")
        denominator = scale.to(dtype=momentum.dtype).reshape(()).abs()
    else:
        denominator = momentum.new_tensor(scale).abs()

    denominator = denominator.clamp_min(_positive_epsilon(momentum, eps))
    return numerator / denominator


def total_absolute_momentum_scale(
    velocity: Tensor,
    mass: Tensor | float | None = None,
) -> Tensor:
    """Return ``sum_i |mass_i| * ||velocity_i||_2`` as a drift scale."""

    _validate_velocity(velocity)
    normalized_mass = _particle_mass(mass, velocity)
    particle_speed = torch.linalg.vector_norm(velocity, dim=-1)
    if normalized_mass.ndim == 0:
        particle_mass = normalized_mass.abs()
    else:
        particle_mass = normalized_mass[:, 0].abs()
    return (particle_speed * particle_mass).sum()


def momentum_metrics(
    velocity: Tensor,
    reference_velocity: Tensor,
    *,
    mass: Tensor | float | None = None,
    reference_mass: Tensor | float | None = None,
    drift_scale: Tensor | float | None = None,
    eps: float | None = None,
) -> Mapping[str, Tensor]:
    """Return total momentum and relative drift for two particle states."""

    reference_mass = mass if reference_mass is None else reference_mass
    momentum = total_momentum(velocity, mass)
    reference = total_momentum(reference_velocity, reference_mass)
    if drift_scale is None:
        drift_scale = total_absolute_momentum_scale(reference_velocity, reference_mass)
    return {
        "total_momentum": momentum,
        "relative_momentum_drift": relative_momentum_drift(
            momentum, reference, scale=drift_scale, eps=eps
        ),
    }


def state_is_finite(*tensors: Tensor) -> Tensor:
    """Return a scalar bool tensor indicating whether all states are finite.

    All tensors must be on the same device.  The function intentionally
    returns a tensor rather than a Python bool to avoid an implicit device
    synchronization in the simulation loop.
    """

    if not tensors:
        raise ValueError("at least one tensor is required")
    if any(not isinstance(tensor, Tensor) for tensor in tensors):
        raise TypeError("all states must be torch.Tensor objects")
    device = tensors[0].device
    if any(tensor.device != device for tensor in tensors):
        raise ValueError("all states must be on the same device")
    result = torch.ones((), dtype=torch.bool, device=device)
    for tensor in tensors:
        result = result & torch.isfinite(tensor).all()
    return result


def has_nonfinite(*tensors: Tensor) -> Tensor:
    """Return a scalar bool tensor that is true if any state has NaN or Inf."""

    return torch.logical_not(state_is_finite(*tensors))


# Common terminology aliases.
linear_momentum = total_momentum
relative_linear_momentum_drift = relative_momentum_drift


__all__ = [
    "has_nonfinite",
    "linear_momentum",
    "momentum_metrics",
    "relative_linear_momentum_drift",
    "relative_momentum_drift",
    "state_is_finite",
    "total_absolute_momentum_scale",
    "total_momentum",
]
