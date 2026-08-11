"""Physical state with separate wrapped and unwrapped position semantics."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import struct

import torch


DOMAIN_MINIMUM = (-1.0, -1.0)
DOMAIN_MAXIMUM = (1.0, 1.0)
RHO0 = 1.0
SOUND_SPEED = 20.0


def _tensor_bytes(value: torch.Tensor) -> bytes:
    array = value.detach().contiguous().cpu().numpy()
    return (
        str(value.dtype).encode("ascii")
        + b"\0"
        + str(tuple(value.shape)).encode("ascii")
        + b"\0"
        + array.tobytes()
    )


def wrap_to_periodic_domain(x_unwrapped: torch.Tensor) -> torch.Tensor:
    lower = torch.tensor(DOMAIN_MINIMUM, dtype=x_unwrapped.dtype, device=x_unwrapped.device)
    upper = torch.tensor(DOMAIN_MAXIMUM, dtype=x_unwrapped.dtype, device=x_unwrapped.device)
    return torch.remainder(x_unwrapped - lower, upper - lower) + lower


def eos_pressure(density: torch.Tensor) -> torch.Tensor:
    return SOUND_SPEED**2 * (density - RHO0)


@dataclass(frozen=True)
class DynamicParticleState:
    x_unwrapped: torch.Tensor
    velocity: torch.Tensor
    density: torch.Tensor
    pressure: torch.Tensor
    mass: torch.Tensor
    smoothing_length: torch.Tensor
    material_labels: torch.Tensor
    physical_time: float
    accepted_step_index: int

    def __post_init__(self) -> None:
        count = int(self.density.numel())
        required = {
            "x_unwrapped": (self.x_unwrapped, (count, 2)),
            "velocity": (self.velocity, (count, 2)),
            "density": (self.density, (count,)),
            "pressure": (self.pressure, (count,)),
            "mass": (self.mass, (count,)),
            "smoothing_length": (self.smoothing_length, (count,)),
            "material_labels": (self.material_labels, (count, 2)),
        }
        for name, (value, shape) in required.items():
            if value.shape != shape:
                raise ValueError(f"{name} must have shape {shape}")
            if value.device.type != "cpu" or value.dtype != torch.float64:
                raise ValueError(f"{name} must be CPU float64")
        if not bool(torch.isfinite(self.density.detach()).all()):
            raise ValueError("density must be finite")

    @property
    def particle_count(self) -> int:
        return int(self.density.numel())

    @property
    def x_wrapped(self) -> torch.Tensor:
        return wrap_to_periodic_domain(self.x_unwrapped)

    @property
    def state_hash(self) -> str:
        digest = hashlib.sha256()
        for tensor in (
            self.x_unwrapped,
            self.x_wrapped,
            self.velocity,
            self.density,
            self.pressure,
            self.mass,
            self.smoothing_length,
            self.material_labels,
        ):
            digest.update(_tensor_bytes(tensor))
        digest.update(struct.pack("<d", float(self.physical_time)))
        digest.update(struct.pack("<q", int(self.accepted_step_index)))
        return "sha256:" + digest.hexdigest()

    def with_eos(self) -> "DynamicParticleState":
        return replace(self, pressure=eos_pressure(self.density))

    def updated(self, **kwargs: object) -> "DynamicParticleState":
        return replace(self, **kwargs)

    def detached_clone(self) -> "DynamicParticleState":
        return replace(
            self,
            x_unwrapped=self.x_unwrapped.detach().clone(),
            velocity=self.velocity.detach().clone(),
            density=self.density.detach().clone(),
            pressure=self.pressure.detach().clone(),
            mass=self.mass.detach().clone(),
            smoothing_length=self.smoothing_length.detach().clone(),
            material_labels=self.material_labels.detach().clone(),
        )


def bitwise_state_equal(left: DynamicParticleState, right: DynamicParticleState) -> bool:
    tensors = (
        "x_unwrapped",
        "x_wrapped",
        "velocity",
        "density",
        "pressure",
        "mass",
        "smoothing_length",
        "material_labels",
    )
    return (
        all(torch.equal(getattr(left, name), getattr(right, name)) for name in tensors)
        and left.physical_time == right.physical_time
        and left.accepted_step_index == right.accepted_step_index
    )

