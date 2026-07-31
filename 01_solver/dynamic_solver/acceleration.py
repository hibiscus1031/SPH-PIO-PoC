"""Structure-preserving force assembly for the Stage 01D dynamic solver."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from dynamic_solver.density import summation_density
from dynamic_solver.equation_of_state import isothermal_pressure
from dynamic_solver.state import DynamicSPHState
from structure_preserving.conservative_pressure import (
    conservative_pressure_forces,
    pressure_conservation_metrics,
)
from structure_preserving.conservative_viscosity import (
    conservative_viscosity_pair_forces,
    conservative_viscosity_forces,
    viscosity_conservation_metrics,
)
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    audit_periodic_neighborhood,
    build_periodic_neighborhood,
)


@dataclass(frozen=True)
class DynamicPhysicalParameters:
    """Fixed physical scalars shared by every force stage."""

    reference_density: float | torch.Tensor = 1.0
    sound_speed: float | torch.Tensor = 20.0
    physical_viscosity: float | torch.Tensor = 0.02


@dataclass(frozen=True)
class ForceEvaluation:
    """Complete value-path result at one position/velocity state."""

    neighborhood: PeriodicNeighborhood
    densities: torch.Tensor
    pressures: torch.Tensor
    pressure_force: torch.Tensor
    viscosity_force: torch.Tensor
    total_force: torch.Tensor
    acceleration: torch.Tensor


def _domain_tuple(value: torch.Tensor) -> tuple[float, float]:
    if value.shape != (2,):
        raise ValueError("periodic domain bound must have shape [2]")
    detached = value.detach()
    return (float(detached[0]), float(detached[1]))


def evaluate_internal_acceleration(
    state: DynamicSPHState,
    parameters: DynamicPhysicalParameters,
) -> ForceEvaluation:
    """Rebuild topology, density, EOS pressure, and internal acceleration.

    Each invocation is a complete force evaluation. The reciprocal graph is
    rebuilt from the current positions, density is evaluated solely by kernel
    summation, and the unclipped isothermal EOS is then applied. The pressure
    and viscosity forces are the frozen Stage 01C pair formulations.
    """

    neighborhood = build_periodic_neighborhood(
        state.positions,
        state.supports,
        domain_minimum=_domain_tuple(state.domain_min),
        domain_maximum=_domain_tuple(state.domain_max),
    )
    density = summation_density(
        neighborhood,
        mass=state.masses,
    )
    pressure = isothermal_pressure(
        density,
        reference_density=parameters.reference_density,
        sound_speed=parameters.sound_speed,
    )
    pressure_force = conservative_pressure_forces(
        neighborhood,
        mass=state.masses,
        density=density,
        pressure=pressure,
    )
    viscosity_force = conservative_viscosity_forces(
        neighborhood,
        mass=state.masses,
        density=density,
        velocity=state.velocities,
        physical_viscosity=parameters.physical_viscosity,
    )
    total_force = pressure_force + viscosity_force
    acceleration = total_force / state.masses[:, None]
    tensors = (
        density,
        pressure,
        pressure_force,
        viscosity_force,
        total_force,
        acceleration,
    )
    if not all(bool(torch.isfinite(value.detach()).all()) for value in tensors):
        raise FloatingPointError("nonfinite value in dynamic force evaluation")
    return ForceEvaluation(
        neighborhood=neighborhood,
        densities=density,
        pressures=pressure,
        pressure_force=pressure_force,
        viscosity_force=viscosity_force,
        total_force=total_force,
        acceleration=acceleration,
    )


def state_from_evaluation(
    state: DynamicSPHState,
    evaluation: ForceEvaluation,
) -> DynamicSPHState:
    """Synchronize the stored density and pressure with an evaluation."""

    return state.with_updates(
        densities=evaluation.densities,
        pressures=evaluation.pressures,
    )


def force_structure_audit(
    state: DynamicSPHState,
    evaluation: ForceEvaluation,
    parameters: DynamicPhysicalParameters,
) -> dict[str, float | int]:
    """Return independent topology, pressure, and viscosity evidence."""

    topology = audit_periodic_neighborhood(
        state.positions,
        evaluation.neighborhood,
    )
    pressure = pressure_conservation_metrics(
        evaluation.neighborhood,
        mass=state.masses,
        density=evaluation.densities,
        pressure=evaluation.pressures,
    )
    viscosity = viscosity_conservation_metrics(
        evaluation.neighborhood,
        mass=state.masses,
        density=evaluation.densities,
        velocity=state.velocities,
        physical_viscosity=parameters.physical_viscosity,
    )
    pressure_force_scale = float(pressure["force_scale"])
    _, _, viscosity_pair_force, _ = conservative_viscosity_pair_forces(
        evaluation.neighborhood,
        mass=state.masses,
        density=evaluation.densities,
        velocity=state.velocities,
        physical_viscosity=parameters.physical_viscosity,
    )
    viscosity_force_scale = float(
        2.0
        * torch.linalg.vector_norm(
            viscosity_pair_force,
            dim=-1,
        ).sum()
    )
    total_internal = torch.linalg.vector_norm(
        evaluation.total_force.sum(dim=0)
    )
    characteristic_scale = (
        pressure_force_scale
        + viscosity_force_scale
        + torch.finfo(state.positions.dtype).tiny
    )
    return {
        **{f"neighbor_{key}": value for key, value in topology.items()},
        "pressure_relative_pair_force_residual": pressure[
            "relative_pair_force_residual"
        ],
        "pressure_relative_total_internal_force": pressure[
            "relative_total_internal_force"
        ],
        "pressure_relative_pair_torque_linf": pressure[
            "relative_pair_torque_linf"
        ],
        "viscosity_relative_pair_force_residual": viscosity[
            "relative_pair_force_residual"
        ],
        "viscosity_relative_total_internal_force": viscosity[
            "relative_total_internal_force"
        ],
        "viscosity_relative_gamma_symmetry_residual": viscosity[
            "relative_gamma_symmetry_residual"
        ],
        "viscous_power": viscosity["accumulated_viscous_power"],
        "viscous_power_identity_difference": viscosity[
            "power_identity_absolute_difference"
        ],
        "characteristic_normalized_total_internal_force": float(
            total_internal / characteristic_scale
        ),
    }
