"""Differentiable density statistics for weakly compressible SPH."""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import Tensor


def _validate_density(density: Tensor) -> None:
    if not isinstance(density, Tensor):
        raise TypeError("density must be a torch.Tensor")
    if not density.is_floating_point():
        raise TypeError("density must be floating point")
    if density.numel() == 0:
        raise ValueError("density statistics are undefined for an empty tensor")


def _positive_epsilon(tensor: Tensor, eps: float | None) -> Tensor:
    value = torch.finfo(tensor.dtype).eps if eps is None else eps
    if value <= 0:
        raise ValueError(f"eps must be positive, got {value!r}")
    return tensor.new_tensor(value)


def relative_density_fluctuation(
    density: Tensor,
    reference_density: Tensor | float | None = None,
    *,
    reduction: str = "max",
    eps: float | None = None,
) -> Tensor:
    """Return relative density deviation from a reference.

    If ``reference_density`` is omitted, the current mean density is used.
    A scalar or tensor broadcastable to ``density`` may be supplied.  The
    pointwise deviation is ``abs(rho-rho_ref)/max(abs(rho_ref), eps)`` and is
    reduced by either ``"max"`` (the Stage 01 default) or ``"rms"``.
    """

    _validate_density(density)
    if reference_density is None:
        reference = density.mean()
    elif isinstance(reference_density, Tensor):
        if reference_density.device != density.device:
            raise ValueError(
                "density and reference_density must be on the same device"
            )
        if not reference_density.is_floating_point():
            raise TypeError("reference_density must be floating point")
        reference = reference_density.to(dtype=density.dtype)
    else:
        reference = density.new_tensor(reference_density)

    try:
        relative_deviation = (density - reference).abs() / reference.abs().clamp_min(
            _positive_epsilon(density, eps)
        )
    except RuntimeError as exc:
        raise ValueError(
            "reference_density must be scalar or broadcastable to density shape "
            f"{tuple(density.shape)}"
        ) from exc

    if reduction == "max":
        return relative_deviation.amax()
    if reduction == "rms":
        return torch.sqrt(relative_deviation.square().mean())
    raise ValueError(f"reduction must be 'max' or 'rms', got {reduction!r}")


def density_statistics(
    density: Tensor,
    reference_density: Tensor | float | None = None,
    *,
    eps: float | None = None,
) -> Mapping[str, Tensor]:
    """Return mean, extrema, and maximum relative density fluctuation."""

    _validate_density(density)
    return {
        "mean_density": density.mean(),
        "min_density": density.amin(),
        "max_density": density.amax(),
        "relative_density_fluctuation": relative_density_fluctuation(
            density, reference_density, reduction="max", eps=eps
        ),
    }


# Report-friendly alias.
density_relative_fluctuation = relative_density_fluctuation


__all__ = [
    "density_relative_fluctuation",
    "density_statistics",
    "relative_density_fluctuation",
]
