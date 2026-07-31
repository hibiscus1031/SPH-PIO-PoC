"""Pressure/viscosity internal-force and pair-antisymmetry audits."""

from __future__ import annotations

import math

from manufactured_fields.periodic import vector_field
from verification.operator_tools import (
    build_layout,
    evaluate_fluid_neighborhood,
    pressure_conservation_audit,
    viscous_conservation_audit,
)


def test_physical_viscosity_is_pairwise_antisymmetric_at_uniform_density() -> None:
    context, _ = build_layout(24, 0.05)
    neighborhood = evaluate_fluid_neighborhood(context)
    audit = viscous_conservation_audit(
        context,
        neighborhood,
        vector_field(context.system.systemState.positions),
        density_perturbation=0.0,
    )

    assert audit["pair_force_residual_linf"] <= 2.0e-8
    assert audit["characteristic_normalized_internal_force"] <= 2.0e-6
    assert audit["viscous_power"] < 0.0
    assert math.isfinite(audit["total_internal_torque"])


def test_variable_density_nonconservation_is_detected_not_hidden() -> None:
    context, _ = build_layout(24, 0.05)
    neighborhood = evaluate_fluid_neighborhood(context)
    audit = viscous_conservation_audit(
        context,
        neighborhood,
        vector_field(context.system.systemState.positions),
        density_perturbation=0.05,
    )

    assert audit["pair_force_residual_linf"] > 0.0
    assert audit["characteristic_normalized_internal_force"] > 1.0e-4
    assert audit["viscous_power"] < 0.0


def test_all_positive_pressure_branch_is_pairwise_antisymmetric() -> None:
    context, _ = build_layout(24, 0.05)
    neighborhood = evaluate_fluid_neighborhood(context)
    audit = pressure_conservation_audit(
        context,
        neighborhood,
        density_offset=1.01,
        density_amplitude=0.005,
    )
    assert audit["minimum_pressure"] > 0.0
    assert audit["pair_force_residual_linf"] < 5.0e-8
    assert audit["characteristic_normalized_internal_force"] < 2.0e-6


def test_antuono_mixed_pressure_nonconservation_is_detected() -> None:
    context, _ = build_layout(24, 0.05)
    neighborhood = evaluate_fluid_neighborhood(context)
    audit = pressure_conservation_audit(
        context,
        neighborhood,
        density_offset=1.0,
        density_amplitude=0.005,
    )
    assert audit["minimum_pressure"] < 0.0 < audit["maximum_pressure"]
    assert audit["pair_force_residual_linf"] > 0.0
    assert audit["characteristic_normalized_internal_force"] > 1.0e-4
