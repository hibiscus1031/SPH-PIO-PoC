"""Native-PyTorch fixed-neighbor value-path qualification."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import torch

from structure_preserving.conservative_pressure import (
    conservative_pressure_forces,
)
from structure_preserving.conservative_viscosity import (
    conservative_viscosity_forces,
)
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    build_periodic_neighborhood,
    periodic_cartesian_layout,
)


@dataclass(frozen=True)
class NativeAutogradProblem:
    positions: torch.Tensor
    neighborhood: PeriodicNeighborhood
    mass: torch.Tensor
    density: torch.Tensor
    base_pressure: torch.Tensor
    base_velocity_shape: torch.Tensor
    time_step: float


def build_native_autograd_problem() -> NativeAutogradProblem:
    """Build the exact supplemental preregistration state."""

    positions, dx, _ = periodic_cartesian_layout(
        16,
        jitter_fraction=0.05,
        seed=20261001,
        dtype=torch.float64,
    )
    neighborhood = build_periodic_neighborhood(positions, 4.0 * dx)
    x = positions[:, 0]
    y = positions[:, 1]
    density = 1.0 + 0.05 * torch.sin(2.0 * torch.pi * x)
    pressure = (
        0.05 * torch.sin(2.0 * torch.pi * x)
        - 0.03 * torch.cos(2.0 * torch.pi * y)
    )
    velocity = torch.stack(
        (
            torch.sin(2.0 * torch.pi * x),
            torch.cos(2.0 * torch.pi * y),
        ),
        dim=-1,
    )
    mass = torch.full(
        (positions.shape[0],),
        dx**2,
        dtype=positions.dtype,
    )
    return NativeAutogradProblem(
        positions=positions,
        neighborhood=neighborhood,
        mass=mass,
        density=density,
        base_pressure=pressure,
        base_velocity_shape=velocity,
        time_step=1.0e-4,
    )


def conservative_acceleration(
    problem: NativeAutogradProblem,
    *,
    velocity: torch.Tensor,
    pressure: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
) -> torch.Tensor:
    pressure_force = conservative_pressure_forces(
        problem.neighborhood,
        mass=problem.mass,
        density=problem.density,
        pressure=pressure,
    )
    viscous_force = conservative_viscosity_forces(
        problem.neighborhood,
        mass=problem.mass,
        density=problem.density,
        velocity=velocity,
        physical_viscosity=physical_viscosity,
    )
    return (pressure_force + viscous_force) / problem.mass[:, None]


def rollout_fixed_neighborhood(
    problem: NativeAutogradProblem,
    *,
    initial_velocity: torch.Tensor,
    pressure: torch.Tensor,
    physical_viscosity: float | torch.Tensor,
    steps: int,
) -> torch.Tensor:
    """Advance only continuous values; topology and geometry stay frozen."""

    if steps <= 0:
        raise ValueError("steps must be positive")
    velocity = initial_velocity
    for _ in range(steps):
        acceleration = conservative_acceleration(
            problem,
            velocity=velocity,
            pressure=pressure,
            physical_viscosity=physical_viscosity,
        )
        velocity = velocity + problem.time_step * acceleration
    return velocity


def _parameterized_loss(
    problem: NativeAutogradProblem,
    parameter_name: str,
    parameter: float | torch.Tensor,
    steps: int,
) -> torch.Tensor:
    reference = problem.base_velocity_shape
    value = (
        parameter.to(dtype=reference.dtype, device=reference.device)
        if torch.is_tensor(parameter)
        else torch.as_tensor(
            parameter,
            dtype=reference.dtype,
            device=reference.device,
        )
    )
    viscosity: float | torch.Tensor = 0.02
    amplitude: float | torch.Tensor = 1.0
    local_velocity: float | torch.Tensor = 0.0
    local_pressure: float | torch.Tensor = 0.0
    if parameter_name == "physical_viscosity":
        viscosity = value
    elif parameter_name == "initial_velocity_amplitude":
        amplitude = value
    elif parameter_name == "local_velocity_x_particle_0":
        local_velocity = value
    elif parameter_name == "local_pressure_particle_0":
        local_pressure = value
    else:
        raise ValueError(f"unknown parameter: {parameter_name}")

    velocity_mask = torch.zeros_like(reference)
    velocity_mask[0, 0] = 1.0
    pressure_mask = torch.zeros_like(problem.base_pressure)
    pressure_mask[0] = 1.0
    initial_velocity = amplitude * reference + local_velocity * velocity_mask
    pressure = problem.base_pressure + local_pressure * pressure_mask
    final_velocity = rollout_fixed_neighborhood(
        problem,
        initial_velocity=initial_velocity,
        pressure=pressure,
        physical_viscosity=viscosity,
        steps=steps,
    )
    return torch.mean(final_velocity.square())


def native_autograd_case(
    problem: NativeAutogradProblem,
    *,
    parameter_name: str,
    parameter_value: float,
    finite_difference_step: float,
    steps: int,
) -> dict[str, float | int | str | bool]:
    parameter = torch.tensor(
        parameter_value,
        dtype=torch.float64,
        requires_grad=True,
    )
    loss = _parameterized_loss(
        problem,
        parameter_name,
        parameter,
        steps,
    )
    gradient = torch.autograd.grad(loss, parameter)[0]
    plus = _parameterized_loss(
        problem,
        parameter_name,
        parameter_value + finite_difference_step,
        steps,
    )
    minus = _parameterized_loss(
        problem,
        parameter_name,
        parameter_value - finite_difference_step,
        steps,
    )
    finite_difference = (plus - minus) / (2.0 * finite_difference_step)
    denominator = torch.maximum(
        torch.maximum(gradient.abs(), finite_difference.abs()),
        torch.tensor(1.0e-12, dtype=torch.float64),
    )
    relative_difference = (gradient - finite_difference).abs() / denominator
    finite = bool(
        torch.isfinite(loss)
        & torch.isfinite(gradient)
        & torch.isfinite(finite_difference)
        & torch.isfinite(relative_difference)
    )
    nonzero = bool(gradient.abs() > torch.finfo(torch.float64).eps)
    threshold_applies = steps in (1, 3, 5, 8)
    passed = finite and nonzero and (
        (not threshold_applies) or bool(relative_difference <= 0.01)
    )
    return {
        "parameter": parameter_name,
        "steps": steps,
        "parameter_value": parameter_value,
        "finite_difference_step": finite_difference_step,
        "loss": float(loss.detach()),
        "autograd_gradient": float(gradient.detach()),
        "gradient_norm": float(gradient.detach().abs()),
        "finite_difference_gradient": float(finite_difference.detach()),
        "relative_difference": float(relative_difference.detach()),
        "finite": finite,
        "nonzero": nonzero,
        "AD_FD_threshold_applies": threshold_applies,
        "status": "PASS" if passed else "FAIL",
        "gradient_scope": "fixed_neighbor_indices_and_geometry_value_path",
        "topology_differentiability_claimed": False,
    }


def run_native_autograd_matrix() -> list[dict[str, float | int | str | bool]]:
    problem = build_native_autograd_problem()
    cases: tuple[tuple[str, float, float], ...] = (
        ("physical_viscosity", 0.02, 1.0e-6),
        ("initial_velocity_amplitude", 1.0, 1.0e-6),
        ("local_velocity_x_particle_0", 0.0, 1.0e-6),
        ("local_pressure_particle_0", 0.0, 1.0e-6),
    )
    rows = []
    for parameter_name, value, epsilon in cases:
        for steps in (1, 3, 5, 8, 16):
            rows.append(
                native_autograd_case(
                    problem,
                    parameter_name=parameter_name,
                    parameter_value=value,
                    finite_difference_step=epsilon,
                    steps=steps,
                )
            )
    return rows


def maximum_relative_difference(
    rows: list[dict[str, float | int | str | bool]],
    *,
    predicate: Callable[[dict[str, float | int | str | bool]], bool],
) -> float:
    selected = [
        float(row["relative_difference"])
        for row in rows
        if predicate(row)
    ]
    if not selected or not all(math.isfinite(value) for value in selected):
        raise ValueError("relative-difference selection is empty or nonfinite")
    return max(selected)
