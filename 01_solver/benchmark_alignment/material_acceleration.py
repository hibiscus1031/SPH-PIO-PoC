"""Independent bookkeeping for the exact TGV material-momentum identity."""

from __future__ import annotations

import torch

from benchmark_alignment.incompressible_tgv_exact import (
    convective_acceleration,
    material_acceleration,
    partial_time_velocity,
    pressure_acceleration,
    viscous_acceleration,
)


def exact_balance(positions: torch.Tensor, time: float = 0.0, **parameters: float) -> dict[str, torch.Tensor]:
    kinematic = {key: value for key, value in parameters.items() if key != "reference_density"}
    partial = partial_time_velocity(positions, time, **kinematic)
    convective = convective_acceleration(positions, time, **kinematic)
    pressure = pressure_acceleration(positions, time, **parameters)
    viscous = viscous_acceleration(positions, time, **kinematic)
    material = material_acceleration(positions, time, **parameters)
    return {"partial_time": partial, "convective": convective, "pressure": pressure, "viscous": viscous, "material": material, "kinematic_residual": material-partial-convective, "momentum_residual": material-pressure-viscous}
