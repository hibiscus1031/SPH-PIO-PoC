"""Native-PyTorch AD/FD regression for the full Stage 01D rollout.

The neighbor graph is rebuilt at every force evaluation.  Autograd follows
the continuous tensor-value path selected by those rebuilt integer indices;
this module deliberately makes no claim that changes in neighbor topology
are differentiable.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.periodic_rollout import rollout_periodic
from dynamic_solver.state import DynamicSPHState
from dynamic_solver.taylor_green import initialize_taylor_green_state


@dataclass(frozen=True)
class DynamicAutogradConfiguration:
    """Pre-registered configuration for the full dynamic regression."""

    resolution: int = 16
    support_ratio: float = 4.0
    time_step: float = 1.0e-4
    sound_speed: float = 20.0
    base_reference_density: float = 1.0
    base_physical_viscosity: float = 0.02
    base_velocity_amplitude: float = 1.0
    finite_difference_step: float = 1.0e-6
    steps: tuple[int, ...] = (1, 3, 5, 8, 16)
    short_steps: tuple[int, ...] = (1, 3, 5, 8)
    short_step_relative_tolerance: float = 0.01


CONFIGURATION = DynamicAutogradConfiguration()
PARAMETER_CASES: tuple[tuple[str, float], ...] = (
    ("physical_viscosity", 0.02),
    ("initial_velocity_amplitude", 1.0),
    ("local_velocity_x_particle_0", 0.0),
    ("reference_density_scalar", 1.0),
)


@dataclass(frozen=True)
class ParameterizedDynamicProblem:
    """Initial state and physical parameters for one scalar perturbation."""

    initial_state: DynamicSPHState
    parameters: DynamicPhysicalParameters


def _scalar_parameter(
    parameter: float | torch.Tensor,
) -> torch.Tensor:
    if torch.is_tensor(parameter):
        if parameter.numel() != 1:
            raise ValueError("regression parameter must be scalar")
        value = parameter.reshape(()).to(dtype=torch.float64, device="cpu")
    else:
        value = torch.as_tensor(parameter, dtype=torch.float64, device="cpu")
    if not bool(torch.isfinite(value.detach())):
        raise ValueError("regression parameter must be finite")
    return value


def build_parameterized_dynamic_problem(
    parameter_name: str,
    parameter: float | torch.Tensor,
    *,
    configuration: DynamicAutogradConfiguration = CONFIGURATION,
) -> ParameterizedDynamicProblem:
    """Build the pre-registered state without detaching ``parameter``.

    ``reference_density_scalar`` is intentionally an EOS-only diagnostic.
    Particle masses stay fixed at the baseline reference density times the
    cell area.  This scope was pre-registered before the dynamic AD run and
    avoids the exact uniform-density scale cancellation that would result if
    both mass and EOS reference density were scaled together.
    """

    value = _scalar_parameter(parameter)
    viscosity: float | torch.Tensor = configuration.base_physical_viscosity
    amplitude: float | torch.Tensor = configuration.base_velocity_amplitude
    eos_reference_density: float | torch.Tensor = (
        configuration.base_reference_density
    )
    local_velocity: float | torch.Tensor = 0.0

    if parameter_name == "physical_viscosity":
        viscosity = value
    elif parameter_name == "initial_velocity_amplitude":
        amplitude = value
    elif parameter_name == "local_velocity_x_particle_0":
        local_velocity = value
    elif parameter_name == "reference_density_scalar":
        if not bool(value.detach() > 0.0):
            raise ValueError("reference_density_scalar must be positive")
        eos_reference_density = value
    else:
        raise ValueError(f"unknown parameter: {parameter_name}")

    state = initialize_taylor_green_state(
        configuration.resolution,
        support_ratio=configuration.support_ratio,
        reference_density=configuration.base_reference_density,
        velocity_amplitude=amplitude,
        physical_viscosity=viscosity,
        sound_speed=configuration.sound_speed,
    )
    if parameter_name == "local_velocity_x_particle_0":
        velocity_mask = torch.zeros_like(state.velocities)
        velocity_mask[0, 0] = 1.0
        state = state.with_updates(
            velocities=state.velocities + local_velocity * velocity_mask,
        )
    parameters = DynamicPhysicalParameters(
        reference_density=eos_reference_density,
        sound_speed=configuration.sound_speed,
        physical_viscosity=viscosity,
    )
    return ParameterizedDynamicProblem(
        initial_state=state,
        parameters=parameters,
    )


def dynamic_rollout_loss(
    parameter_name: str,
    parameter: float | torch.Tensor,
    steps: int,
    *,
    configuration: DynamicAutogradConfiguration = CONFIGURATION,
) -> torch.Tensor:
    """Return ``mean(final_velocity**2)`` after a rebuilt-topology rollout."""

    if not isinstance(steps, int):
        raise TypeError("steps must be an integer")
    if steps <= 0:
        raise ValueError("steps must be positive")
    problem = build_parameterized_dynamic_problem(
        parameter_name,
        parameter,
        configuration=configuration,
    )
    result = rollout_periodic(
        problem.initial_state,
        dt=configuration.time_step,
        steps=steps,
        parameters=problem.parameters,
    )
    return torch.mean(result.final_state.velocities.square())


def dynamic_autograd_case(
    *,
    parameter_name: str,
    parameter_value: float,
    finite_difference_step: float,
    steps: int,
    configuration: DynamicAutogradConfiguration = CONFIGURATION,
) -> dict[str, float | int | str | bool]:
    """Compare native autograd with a centered finite difference."""

    if (
        not math.isfinite(finite_difference_step)
        or finite_difference_step <= 0.0
    ):
        raise ValueError("finite_difference_step must be finite and positive")
    parameter = torch.tensor(
        parameter_value,
        dtype=torch.float64,
        device="cpu",
        requires_grad=True,
    )
    loss = dynamic_rollout_loss(
        parameter_name,
        parameter,
        steps,
        configuration=configuration,
    )
    gradient = torch.autograd.grad(loss, parameter)[0]
    plus = dynamic_rollout_loss(
        parameter_name,
        parameter_value + finite_difference_step,
        steps,
        configuration=configuration,
    )
    minus = dynamic_rollout_loss(
        parameter_name,
        parameter_value - finite_difference_step,
        steps,
        configuration=configuration,
    )
    finite_difference = (plus - minus) / (2.0 * finite_difference_step)
    denominator = torch.maximum(
        torch.maximum(gradient.abs(), finite_difference.abs()),
        torch.tensor(1.0e-12, dtype=torch.float64),
    )
    relative_difference = (
        (gradient - finite_difference).abs() / denominator
    )
    finite = bool(
        torch.isfinite(loss)
        & torch.isfinite(gradient)
        & torch.isfinite(finite_difference)
        & torch.isfinite(relative_difference)
    )
    nonzero = bool(gradient.abs() > torch.finfo(torch.float64).eps)
    threshold_applies = steps in configuration.short_steps
    passed = finite and nonzero and (
        (not threshold_applies)
        or bool(
            relative_difference
            <= configuration.short_step_relative_tolerance
        )
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
        "resolution": configuration.resolution,
        "support_ratio": configuration.support_ratio,
        "time_step": configuration.time_step,
        "gradient_scope": (
            "rebuilt_neighbor_indices_continuous_tensor_value_path"
        ),
        "density_scalar_scope": (
            "EOS_reference_density_only_with_fixed_baseline_masses"
        ),
        "topology_differentiability_claimed": False,
    }


def run_dynamic_autograd_matrix(
    *,
    configuration: DynamicAutogradConfiguration = CONFIGURATION,
) -> list[dict[str, float | int | str | bool]]:
    """Run all four parameters at all five pre-registered step counts."""

    rows: list[dict[str, float | int | str | bool]] = []
    for parameter_name, value in PARAMETER_CASES:
        for steps in configuration.steps:
            rows.append(
                dynamic_autograd_case(
                    parameter_name=parameter_name,
                    parameter_value=value,
                    finite_difference_step=(
                        configuration.finite_difference_step
                    ),
                    steps=steps,
                    configuration=configuration,
                )
            )
    return rows


def maximum_relative_difference(
    rows: list[dict[str, float | int | str | bool]],
    *,
    predicate: Callable[[dict[str, float | int | str | bool]], bool],
) -> float:
    """Return a checked maximum over a selected group of result rows."""

    selected = [
        float(row["relative_difference"])
        for row in rows
        if predicate(row)
    ]
    if not selected or not all(math.isfinite(value) for value in selected):
        raise ValueError("relative-difference selection is empty or nonfinite")
    return max(selected)
