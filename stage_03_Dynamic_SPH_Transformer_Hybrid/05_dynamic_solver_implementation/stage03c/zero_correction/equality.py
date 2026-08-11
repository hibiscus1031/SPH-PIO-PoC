"""Strict bitwise physical-state comparison used by both zero modes."""

from __future__ import annotations

import torch

from baseline_d0.state import DynamicParticleState


def physical_bitwise_gates(reference: DynamicParticleState, candidate: DynamicParticleState) -> dict[str, bool]:
    return {
        "x_unwrapped_bitwise": torch.equal(reference.x_unwrapped, candidate.x_unwrapped),
        "x_wrapped_bitwise": torch.equal(reference.x_wrapped, candidate.x_wrapped),
        "velocity_bitwise": torch.equal(reference.velocity, candidate.velocity),
        "density_bitwise": torch.equal(reference.density, candidate.density),
        "pressure_bitwise": torch.equal(reference.pressure, candidate.pressure),
        "accepted_time_bitwise": reference.physical_time == candidate.physical_time,
        "accepted_step_bitwise": reference.accepted_step_index == candidate.accepted_step_index,
    }

