"""Dynamic mixed-sign EOS pressure and viscosity balance checks."""

from __future__ import annotations

import torch

from dynamic_solver.acceleration import (
    DynamicPhysicalParameters,
    evaluate_internal_acceleration,
    force_structure_audit,
)
from dynamic_solver.taylor_green import initialize_taylor_green_state


def test_dynamic_mixed_pressure_and_variable_density_are_pair_balanced() -> None:
    state = initialize_taylor_green_state(
        8,
        support_ratio=3.0,
        jitter_fraction=0.10,
        seed=20261001,
    )
    parameters = DynamicPhysicalParameters(
        reference_density=1.0,
        sound_speed=20.0,
        physical_viscosity=0.02,
    )
    evaluation = evaluate_internal_acceleration(state, parameters)
    audit = force_structure_audit(state, evaluation, parameters)

    assert float(evaluation.densities.max() - evaluation.densities.min()) > 0.05
    assert float(evaluation.pressures.min()) < 0.0
    assert float(evaluation.pressures.max()) > 0.0
    assert torch.isfinite(evaluation.pressure_force).all()
    assert torch.isfinite(evaluation.viscosity_force).all()

    assert audit["pressure_relative_pair_force_residual"] <= 1.0e-12
    assert audit["pressure_relative_total_internal_force"] <= 1.0e-10
    assert audit["viscosity_relative_pair_force_residual"] <= 1.0e-12
    assert audit["viscosity_relative_total_internal_force"] <= 1.0e-10
    assert audit["viscosity_relative_gamma_symmetry_residual"] <= 1.0e-12
    assert audit["characteristic_normalized_total_internal_force"] <= 1.0e-10

    # The nonuniform TGV velocity makes the dissipative check nontrivial.
    assert audit["viscous_power"] < 0.0
    assert audit["viscous_power_identity_difference"] <= (
        1.0e-12 * max(1.0, abs(float(audit["viscous_power"])))
    )
