"""Full-dynamic native-PyTorch AD/FD regression tests for Stage 01D."""

from __future__ import annotations

import math

import pytest
import torch

from dynamic_solver.acceleration import evaluate_internal_acceleration
from dynamic_solver.native_autograd import (
    CONFIGURATION,
    PARAMETER_CASES,
    build_parameterized_dynamic_problem,
    dynamic_autograd_case,
    dynamic_rollout_loss,
    run_dynamic_autograd_matrix,
)


@pytest.fixture(scope="module")
def regression_rows() -> list[dict[str, float | int | str | bool]]:
    return run_dynamic_autograd_matrix()


def test_configuration_matches_revised_preregistration() -> None:
    assert CONFIGURATION.resolution == 16
    assert CONFIGURATION.support_ratio == 4.0
    assert CONFIGURATION.time_step == 1.0e-4
    assert CONFIGURATION.steps == (1, 3, 5, 8, 16)
    assert CONFIGURATION.finite_difference_step == 1.0e-6


def test_parameter_names_and_base_values_are_frozen() -> None:
    assert PARAMETER_CASES == (
        ("physical_viscosity", 0.02),
        ("initial_velocity_amplitude", 1.0),
        ("local_velocity_x_particle_0", 0.0),
        ("reference_density_scalar", 1.0),
    )


def test_parameterized_problem_is_float64_cpu_with_expected_size() -> None:
    problem = build_parameterized_dynamic_problem(
        "initial_velocity_amplitude",
        torch.tensor(1.0, dtype=torch.float64, requires_grad=True),
    )
    state = problem.initial_state
    assert state.particle_count == 16**2
    for value in (
        state.positions,
        state.velocities,
        state.masses,
        state.densities,
        state.pressures,
        state.supports,
    ):
        assert value.dtype == torch.float64
        assert value.device.type == "cpu"


def test_reference_density_is_eos_only_and_retains_its_graph() -> None:
    reference_density = torch.tensor(
        1.0,
        dtype=torch.float64,
        requires_grad=True,
    )
    problem = build_parameterized_dynamic_problem(
        "reference_density_scalar",
        reference_density,
    )
    state = problem.initial_state
    expected_mass = (2.0 / CONFIGURATION.resolution) ** 2
    torch.testing.assert_close(
        state.masses,
        torch.full_like(state.masses, expected_mass),
        rtol=0.0,
        atol=0.0,
    )
    assert state.masses.requires_grad is False
    assert torch.is_tensor(problem.parameters.reference_density)
    assert problem.parameters.reference_density.requires_grad
    assert problem.parameters.reference_density.dtype == torch.float64
    assert problem.parameters.reference_density.device.type == "cpu"
    assert float(problem.parameters.reference_density.detach()) == 1.0

    evaluation = evaluate_internal_acceleration(
        state,
        problem.parameters,
    )
    assert evaluation.pressures.requires_grad
    pressure_gradient = torch.autograd.grad(
        evaluation.pressures.sum(),
        reference_density,
    )[0]
    assert bool(torch.isfinite(pressure_gradient))
    expected_gradient = -(
        state.particle_count * CONFIGURATION.sound_speed**2
    )
    torch.testing.assert_close(
        pressure_gradient,
        torch.tensor(expected_gradient, dtype=torch.float64),
        rtol=1.0e-14,
        atol=0.0,
    )


def test_local_velocity_parameter_changes_only_requested_component() -> None:
    baseline = build_parameterized_dynamic_problem(
        "local_velocity_x_particle_0",
        0.0,
    ).initial_state
    perturbed = build_parameterized_dynamic_problem(
        "local_velocity_x_particle_0",
        0.125,
    ).initial_state
    difference = perturbed.velocities - baseline.velocities
    expected = torch.zeros_like(difference)
    expected[0, 0] = 0.125
    torch.testing.assert_close(difference, expected, rtol=0.0, atol=0.0)


@pytest.mark.parametrize("parameter_name,base_value", PARAMETER_CASES)
def test_rollout_loss_is_scalar_finite_and_connected(
    parameter_name: str,
    base_value: float,
) -> None:
    parameter = torch.tensor(
        base_value,
        dtype=torch.float64,
        requires_grad=True,
    )
    loss = dynamic_rollout_loss(parameter_name, parameter, 1)
    gradient = torch.autograd.grad(loss, parameter)[0]
    assert loss.shape == ()
    assert loss.dtype == torch.float64
    assert bool(torch.isfinite(loss))
    assert bool(torch.isfinite(gradient))
    assert abs(float(gradient)) > torch.finfo(torch.float64).eps


def test_invalid_parameter_and_step_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown parameter"):
        dynamic_rollout_loss("not_a_parameter", 1.0, 1)
    with pytest.raises(ValueError, match="steps must be positive"):
        dynamic_rollout_loss("physical_viscosity", 0.02, 0)
    with pytest.raises(TypeError, match="steps must be an integer"):
        dynamic_rollout_loss("physical_viscosity", 0.02, 1.0)  # type: ignore[arg-type]


def test_centered_finite_difference_case_passes() -> None:
    row = dynamic_autograd_case(
        parameter_name="physical_viscosity",
        parameter_value=0.02,
        finite_difference_step=1.0e-6,
        steps=3,
    )
    assert row["status"] == "PASS"
    assert row["finite"] is True
    assert row["nonzero"] is True
    assert float(row["relative_difference"]) <= 0.01


def test_regression_matrix_has_all_twenty_rows(
    regression_rows: list[dict[str, float | int | str | bool]],
) -> None:
    assert len(regression_rows) == 20
    assert {int(row["steps"]) for row in regression_rows} == {
        1,
        3,
        5,
        8,
        16,
    }
    assert {str(row["parameter"]) for row in regression_rows} == {
        name for name, _ in PARAMETER_CASES
    }


def test_short_step_ad_fd_gate_passes(
    regression_rows: list[dict[str, float | int | str | bool]],
) -> None:
    short_rows = [
        row
        for row in regression_rows
        if int(row["steps"]) in CONFIGURATION.short_steps
    ]
    assert len(short_rows) == 16
    for row in short_rows:
        assert row["AD_FD_threshold_applies"] is True
        assert row["status"] == "PASS"
        assert float(row["relative_difference"]) <= 0.01


def test_step_16_is_finite_nonzero_diagnostic(
    regression_rows: list[dict[str, float | int | str | bool]],
) -> None:
    diagnostic_rows = [
        row for row in regression_rows if int(row["steps"]) == 16
    ]
    assert len(diagnostic_rows) == 4
    for row in diagnostic_rows:
        assert row["AD_FD_threshold_applies"] is False
        assert row["status"] == "PASS"
        assert row["finite"] is True
        assert row["nonzero"] is True
        assert math.isfinite(float(row["autograd_gradient"]))
        assert math.isfinite(float(row["finite_difference_gradient"]))
        assert float(row["gradient_norm"]) > 0.0


def test_every_row_disclaims_topology_differentiability(
    regression_rows: list[dict[str, float | int | str | bool]],
) -> None:
    for row in regression_rows:
        assert (
            row["gradient_scope"]
            == "rebuilt_neighbor_indices_continuous_tensor_value_path"
        )
        assert row["topology_differentiability_claimed"] is False
        assert (
            row["density_scalar_scope"]
            == "EOS_reference_density_only_with_fixed_baseline_masses"
        )
