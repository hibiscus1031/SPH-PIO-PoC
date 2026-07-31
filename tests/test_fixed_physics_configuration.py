r"""Qualification tests for explicit fixed-\(\nu\), fixed-\(c_s\) configuration."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import torch
import yaml

from verification.fixed_physics_tgv import (
    FixedPhysicsTGVConfig,
    build_fixed_physics_context,
)
from viscosity_audit.physical_nu_adapter import (
    VELOCITY_SCHEME_NAME,
    physical_nu_laplacian,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fluid_neighborhood(context):
    from diffSPH.neighborhood import SupportScheme, evaluateNeighborhood

    state = context.system.systemState
    _, neighbors = evaluateNeighborhood(
        state,
        context.config["domain"],
        context.config["kernel"],
        verletScale=context.config["neighborhood"]["verletScale"],
        mode=SupportScheme.SuperSymmetric,
        priorNeighborhood=None,
        computeHessian=context.config["neighborhood"]["computeHessian"],
        computeDkDh=context.config["neighborhood"]["computeDkDh"],
        only_j=context.config["neighborhood"]["only_j"],
    )
    return neighbors.get("fluid")


def test_preregistered_physics_is_self_consistent() -> None:
    spec = FixedPhysicsTGVConfig(
        resolution=32,
        total_time=0.001,
        total_steps=1,
    )
    assert spec.reynolds_number == pytest.approx(100.0)
    assert spec.nominal_mach == pytest.approx(0.1)
    assert spec.physical_viscosity == pytest.approx(
        spec.velocity_amplitude
        * spec.domain_length
        / spec.target_reynolds
    )

    with pytest.raises(ValueError, match="imply Re"):
        FixedPhysicsTGVConfig(
            resolution=16,
            physical_viscosity=0.01,
            total_time=0.001,
            total_steps=1,
        )
    with pytest.raises(ValueError, match="nominal Mach"):
        FixedPhysicsTGVConfig(
            resolution=16,
            sound_speed=5.0,
            total_time=0.001,
            total_steps=1,
        )


def test_machine_readable_preregistration_is_frozen_and_not_executed() -> None:
    path = (
        PROJECT_ROOT
        / "06_experiments"
        / "stage_01b_fixed_physics_tgv"
        / "configs"
        / "preregistered_fixed_physics.yml"
    )
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    physics = record["physics"]
    discretization = record["discretization"]

    assert record["configuration_status"] == "PREREGISTERED_NOT_EXECUTED"
    assert record["execution_gate"] == {
        "v1_status": "V1_FAIL",
        "v2_authorized": False,
        "reason": (
            "Required disorder and conservation/operator checks did not "
            "qualify."
        ),
    }
    assert physics["kinematic_viscosity"] == pytest.approx(0.02)
    assert physics["target_reynolds_number"] == pytest.approx(100.0)
    assert physics["sound_speed"] == pytest.approx(10.0)
    assert discretization["particle_resolutions"] == [16, 24, 32]
    assert discretization["proposed_time_steps"] == [
        pytest.approx(1.0e-3),
        pytest.approx(5.0e-4),
        pytest.approx(2.5e-4),
    ]
    assert discretization["verlet_scale"] == pytest.approx(1.0)


@pytest.mark.parametrize("resolution", [16, 24, 32])
def test_fixed_sound_speed_viscosity_and_cfl_propagate(
    resolution: int,
) -> None:
    spec = FixedPhysicsTGVConfig(
        resolution=resolution,
        total_time=0.001,
        total_steps=1,
    )
    context = build_fixed_physics_context(spec)
    state = context.system.systemState

    assert context.config["fluid"]["c_s"] == pytest.approx(10.0)
    torch.testing.assert_close(
        state.soundspeeds,
        torch.full_like(state.soundspeeds, 10.0),
    )
    assert context.config["diffusion"]["nu"] == pytest.approx(0.02)
    assert (
        context.config["diffusion"]["velocityScheme"]
        == VELOCITY_SCHEME_NAME
    )
    assert context.timestep_limits["support"] == pytest.approx(
        8.0 / resolution
    )
    assert spec.target_dt <= context.timestep_limits["permitted_initial_dt"]


def test_private_scheme_binding_does_not_patch_upstream_global() -> None:
    spec = FixedPhysicsTGVConfig(
        resolution=16,
        total_time=0.001,
        total_steps=1,
    )
    context = build_fixed_physics_context(spec)
    import diffSPH.schemes.deltaSPH as upstream

    official_binding = upstream.deltaPlusSPHScheme.__globals__[
        "computeViscosity_deltaSPH_inviscid"
    ]
    private_binding = context.simulator.__globals__[
        "computeViscosity_deltaSPH_inviscid"
    ]
    assert private_binding is physical_nu_laplacian
    assert official_binding is not physical_nu_laplacian
    assert (
        context.simulator._stage01b_upstream_code_identity
        is upstream.deltaPlusSPHScheme.__code__
    )


def test_physical_nu_operator_zero_and_linear_scaling() -> None:
    spec = FixedPhysicsTGVConfig(
        resolution=16,
        total_time=0.001,
        total_steps=1,
    )
    context = build_fixed_physics_context(spec)
    neighborhood = _fluid_neighborhood(context)

    outputs = {}
    for nu in (0.0, 0.02, 0.04):
        config = copy.deepcopy(context.config)
        config["diffusion"]["nu"] = nu
        outputs[nu] = physical_nu_laplacian(
            context.system.systemState,
            context.config["kernel"],
            neighborhood,
            config=config,
        )

    assert torch.count_nonzero(outputs[0.0]) == 0
    torch.testing.assert_close(
        outputs[0.04],
        2.0 * outputs[0.02],
        rtol=2.0e-6,
        atol=2.0e-6,
    )
    assert bool(torch.linalg.vector_norm(outputs[0.02]) > 0)


def test_physical_nu_reaches_full_scheme_update_linearly() -> None:
    spec = FixedPhysicsTGVConfig(
        resolution=16,
        total_time=0.001,
        total_steps=1,
    )
    context = build_fixed_physics_context(spec)

    updates = {}
    for nu in (0.0, 0.02, 0.04):
        config = copy.deepcopy(context.config)
        config["diffusion"]["nu"] = nu
        update, _, _ = context.simulator(
            context.system,
            context.dt,
            config,
            verbose=False,
        )
        updates[nu] = update.velocities.detach()

    increment_002 = updates[0.02] - updates[0.0]
    increment_004 = updates[0.04] - updates[0.0]
    assert bool(torch.linalg.vector_norm(increment_002) > 0)
    torch.testing.assert_close(
        increment_004,
        2.0 * increment_002,
        rtol=5.0e-5,
        atol=2.0e-5,
    )


def test_official_timestep_reads_explicit_physical_nu() -> None:
    from diffSPH.modules.timestep import computeTimestepWCSPH

    spec = FixedPhysicsTGVConfig(
        resolution=32,
        total_time=0.001,
        total_steps=1,
    )
    context = build_fixed_physics_context(spec)
    config = copy.deepcopy(context.config)
    config["timestep"].update(
        {"active": True, "maxDt": 1.0, "minDt": 1.0e-8}
    )
    config["diffusion"]["nu"] = 2.0
    observed = computeTimestepWCSPH(
        context.dt,
        context.system.systemState,
        None,
        config,
    )
    expected_viscous = (
        0.125
        * context.smoothing_length**2
        / 2.0
        / context.timestep_limits["kernel_scale"]
    )
    assert float(observed) == pytest.approx(expected_viscous, rel=2.0e-6)
