"""External-source evaluation and audit records, separate from pair forces."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from dynamic_solver.density import summation_density
from dynamic_solver.equation_of_state import isothermal_pressure
from dynamic_solver.state import DynamicSPHState
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS
from manufactured_solutions.particle_initialization import regular_initialization
from structure_preserving.neighborhood import build_periodic_neighborhood


@dataclass(frozen=True)
class SourceCallRecord:
    stage: str
    physical_time: float
    position_object_identity: int
    source_l1: float
    source_l2: float
    source_linf: float
    mass_weighted_external_force: tuple[float, float]


@dataclass(frozen=True)
class SourcedAcceleration:
    internal_acceleration: torch.Tensor
    external_acceleration: torch.Tensor
    total_acceleration: torch.Tensor
    record: SourceCallRecord


def initialize_mms_state(
    solution_id: str,
    resolution: int,
    *,
    support_ratio: float,
    parameters: MMSParameters = PARAMETERS,
) -> DynamicSPHState:
    """Initialize fixed masses analytically and numerical density by SPH sum."""

    initialized = regular_initialization(solution_id, resolution, parameters)
    positions = initialized.positions
    dx = (parameters.domain_maximum - parameters.domain_minimum) / resolution
    supports = torch.full((positions.shape[0],), support_ratio * dx, dtype=torch.float64)
    domain_min = torch.full((2,), parameters.domain_minimum, dtype=torch.float64)
    domain_max = torch.full((2,), parameters.domain_maximum, dtype=torch.float64)
    neighborhood = build_periodic_neighborhood(
        positions,
        supports,
        domain_minimum=(parameters.domain_minimum, parameters.domain_minimum),
        domain_maximum=(parameters.domain_maximum, parameters.domain_maximum),
    )
    numerical_density = summation_density(neighborhood, mass=initialized.mass)
    numerical_pressure = isothermal_pressure(
        numerical_density,
        reference_density=parameters.rho0,
        sound_speed=parameters.sound_speed,
    )
    velocity = solution_module(solution_id).velocity(positions, 0.0, parameters)
    return DynamicSPHState(
        positions=positions, velocities=velocity, masses=initialized.mass,
        densities=numerical_density, pressures=numerical_pressure, supports=supports,
        domain_min=domain_min, domain_max=domain_max, time=0.0,
    )


def evaluate_sourced_acceleration(
    *,
    solution_id: str,
    stage: str,
    numerical_positions: torch.Tensor,
    physical_stage_time: float,
    masses: torch.Tensor,
    internal_acceleration: torch.Tensor,
    parameters: MMSParameters = PARAMETERS,
) -> SourcedAcceleration:
    if stage not in ("start", "midpoint"):
        raise ValueError("source stage must be start or midpoint")
    external = evaluate_mms_source(
        solution_id, numerical_positions, physical_stage_time, parameters
    )
    total = internal_acceleration + external
    magnitudes = torch.linalg.vector_norm(external, dim=-1)
    weighted = torch.sum(masses[:, None] * external, dim=0)
    record = SourceCallRecord(
        stage=stage,
        physical_time=float(physical_stage_time),
        position_object_identity=id(numerical_positions),
        source_l1=float(magnitudes.mean().detach()),
        source_l2=float(torch.sqrt(torch.mean(magnitudes.square())).detach()),
        source_linf=float(magnitudes.max().detach()),
        mass_weighted_external_force=(float(weighted[0].detach()), float(weighted[1].detach())),
    )
    return SourcedAcceleration(
        internal_acceleration=internal_acceleration,
        external_acceleration=external,
        total_acceleration=total,
        record=record,
    )
