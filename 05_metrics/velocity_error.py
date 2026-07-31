"""Differentiable velocity-error metrics for Stage 01.

All reductions stay in PyTorch so that callers may include the returned
scalars in an autograd graph.  Detaching values for CSV or log output is the
caller's responsibility.
"""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import Tensor


def _validate_velocity_pair(velocity: Tensor, reference: Tensor) -> None:
    """Validate a pair of velocity tensors without moving either tensor."""

    if not isinstance(velocity, Tensor) or not isinstance(reference, Tensor):
        raise TypeError("velocity and reference must both be torch.Tensor objects")
    if velocity.shape != reference.shape:
        raise ValueError(
            "velocity and reference must have the same shape; "
            f"got {tuple(velocity.shape)} and {tuple(reference.shape)}"
        )
    if velocity.numel() == 0:
        raise ValueError("velocity metrics are undefined for empty tensors")
    if not velocity.is_floating_point() or not reference.is_floating_point():
        raise TypeError("velocity metrics require floating-point tensors")
    if velocity.device != reference.device:
        raise ValueError(
            "velocity and reference must be on the same device; "
            f"got {velocity.device} and {reference.device}"
        )
    if velocity.dtype != reference.dtype:
        raise ValueError(
            "velocity and reference must have the same dtype; "
            f"got {velocity.dtype} and {reference.dtype}"
        )


def _positive_epsilon(tensor: Tensor, eps: float | None) -> Tensor:
    """Return a positive scalar epsilon on ``tensor``'s device and dtype."""

    value = torch.finfo(tensor.dtype).eps if eps is None else eps
    if value <= 0:
        raise ValueError(f"eps must be positive, got {value!r}")
    return tensor.new_tensor(value)


def velocity_relative_l2(
    velocity: Tensor,
    reference: Tensor,
    *,
    eps: float | None = None,
) -> Tensor:
    """Return the global relative L2 velocity error.

    The metric is

    ``||velocity - reference||_2 / max(||reference||_2, eps)``.

    ``eps`` defaults to the machine epsilon of the input dtype.  Therefore a
    zero reference field produces a finite result: zero for an identical
    field and an epsilon-normalized absolute error otherwise.
    """

    _validate_velocity_pair(velocity, reference)
    numerator = torch.linalg.vector_norm((velocity - reference).reshape(-1))
    denominator = torch.linalg.vector_norm(reference.reshape(-1))
    denominator = denominator.clamp_min(_positive_epsilon(reference, eps))
    return numerator / denominator


def velocity_rmse(velocity: Tensor, reference: Tensor) -> Tensor:
    """Return the absolute root-mean-square velocity-component error."""

    _validate_velocity_pair(velocity, reference)
    difference = velocity - reference
    return torch.sqrt(torch.mean(difference.square()))


def max_particle_speed(velocity: Tensor) -> Tensor:
    """Return the maximum Euclidean particle speed.

    ``velocity`` must use its last axis for spatial components.  Any leading
    axes are treated as particle or batch axes and reduced globally.
    """

    if not isinstance(velocity, Tensor):
        raise TypeError("velocity must be a torch.Tensor")
    if not velocity.is_floating_point():
        raise TypeError("velocity must be floating point")
    if velocity.numel() == 0 or velocity.ndim < 1 or velocity.shape[-1] == 0:
        raise ValueError("velocity must contain at least one vector component")
    return torch.linalg.vector_norm(velocity, dim=-1).amax()


def velocity_metrics(
    velocity: Tensor,
    reference: Tensor,
    *,
    eps: float | None = None,
) -> Mapping[str, Tensor]:
    """Return the Stage 01 velocity metrics as differentiable scalars."""

    return {
        "velocity_relative_l2": velocity_relative_l2(
            velocity, reference, eps=eps
        ),
        "velocity_rmse": velocity_rmse(velocity, reference),
        "max_particle_speed": max_particle_speed(velocity),
    }


# Descriptive aliases used by experiment/report code.
relative_l2_velocity_error = velocity_relative_l2
absolute_velocity_rmse = velocity_rmse


__all__ = [
    "absolute_velocity_rmse",
    "max_particle_speed",
    "relative_l2_velocity_error",
    "velocity_metrics",
    "velocity_relative_l2",
    "velocity_rmse",
]
