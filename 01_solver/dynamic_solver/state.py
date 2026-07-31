"""Immutable dynamic SPH state with explicit Stage 01D invariants."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from numbers import Real
from typing import Any

import torch


def _require_float64_cpu(
    name: str,
    value: torch.Tensor,
    shape: tuple[int, ...],
) -> None:
    if not torch.is_tensor(value):
        raise TypeError(f"{name} must be a torch.Tensor")
    if value.device.type != "cpu":
        raise ValueError(f"{name} must be on CPU")
    if value.dtype != torch.float64:
        raise ValueError(f"{name} must use torch.float64")
    if value.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {value.shape}")
    if not bool(torch.isfinite(value.detach()).all()):
        raise ValueError(f"{name} must contain only finite values")


@dataclass(frozen=True)
class DynamicSPHState:
    """Complete two-dimensional periodic SPH state.

    The class validates but never detaches, clones, or casts state tensors.
    Consequently, tensors supplied for positions and velocities retain their
    original autograd graphs. Updates are functional through
    :meth:`with_updates`.
    """

    positions: torch.Tensor
    velocities: torch.Tensor
    masses: torch.Tensor
    densities: torch.Tensor
    pressures: torch.Tensor
    supports: torch.Tensor
    domain_min: torch.Tensor
    domain_max: torch.Tensor
    time: float

    def __post_init__(self) -> None:
        if not torch.is_tensor(self.positions) or self.positions.ndim != 2:
            raise ValueError("positions must have shape [particles, 2]")
        if self.positions.shape[1] != 2:
            raise ValueError("positions must have shape [particles, 2]")
        count = int(self.positions.shape[0])
        _require_float64_cpu("positions", self.positions, (count, 2))
        _require_float64_cpu("velocities", self.velocities, (count, 2))
        _require_float64_cpu("masses", self.masses, (count,))
        _require_float64_cpu("densities", self.densities, (count,))
        _require_float64_cpu("pressures", self.pressures, (count,))
        _require_float64_cpu("supports", self.supports, (count,))
        _require_float64_cpu("domain_min", self.domain_min, (2,))
        _require_float64_cpu("domain_max", self.domain_max, (2,))

        if count == 0:
            raise ValueError("state must contain at least one particle")
        if bool((self.masses.detach() <= 0.0).any()):
            raise ValueError("masses must be positive")
        if bool((self.densities.detach() <= 0.0).any()):
            raise ValueError("densities must be positive")
        if bool((self.supports.detach() <= 0.0).any()):
            raise ValueError("supports must be positive")
        if bool((self.domain_max.detach() <= self.domain_min.detach()).any()):
            raise ValueError("domain_max must exceed domain_min")
        outside = (
            (self.positions.detach() < self.domain_min.detach())
            | (self.positions.detach() >= self.domain_max.detach())
        )
        if bool(outside.any()):
            raise ValueError(
                "positions must lie in the half-open periodic domain"
            )
        if isinstance(self.time, bool) or not isinstance(self.time, Real):
            raise TypeError("time must be a real scalar")
        if not math.isfinite(float(self.time)) or float(self.time) < 0.0:
            raise ValueError("time must be finite and nonnegative")

    @property
    def particle_count(self) -> int:
        return int(self.positions.shape[0])

    @property
    def domain_extent(self) -> torch.Tensor:
        return self.domain_max - self.domain_min

    def with_updates(self, **changes: Any) -> "DynamicSPHState":
        """Return a validated replacement without breaking tensor graphs."""

        return replace(self, **changes)
