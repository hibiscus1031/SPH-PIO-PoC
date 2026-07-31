"""Checks for the official diffSPH Taylor–Green initialization adapter."""

import torch
import pytest

from diffsph_adapter import TGVConfig, build_context, taylor_green_velocity


def test_tgv_initial_condition_has_expected_particles_and_velocity() -> None:
    spec = TGVConfig(
        resolution=16,
        backend="cpu",
        total_time=0.001,
        total_steps=2,
        shuffle_iterations=0,
        warmup_steps=0,
    )
    context = build_context(spec)
    state = context.system.systemState

    assert state.positions.shape == (256, 2)
    assert state.velocities.shape == (256, 2)
    assert state.positions.device.type == "cpu"
    expected = taylor_green_velocity(
        state.positions,
        0.0,
        amplitude=1.0,
        viscosity=context.reference_kinematic_viscosity,
        wave_number=spec.wave_number,
    )
    torch.testing.assert_close(state.velocities, expected)
    torch.testing.assert_close(
        state.densities,
        torch.ones_like(state.densities),
        rtol=2.0e-4,
        atol=2.0e-4,
    )
    assert context.config["kernel"].name == "Wendland4"
    assert context.config["diffusion"]["alpha"] > 0


@pytest.mark.skipif(
    not torch.backends.mps.is_available(),
    reason="MPS is not available",
)
def test_cpu_and_mps_receive_identical_initial_particle_state() -> None:
    common = dict(
        resolution=16,
        total_time=0.0005,
        total_steps=1,
        shuffle_iterations=4,
        warmup_steps=0,
    )
    cpu = build_context(TGVConfig(backend="cpu", **common))
    mps = build_context(TGVConfig(backend="mps", **common))
    for name in (
        "positions",
        "velocities",
        "densities",
        "masses",
        "supports",
        "UIDs",
    ):
        cpu_tensor = getattr(cpu.system.systemState, name)
        mps_tensor = getattr(mps.system.systemState, name).cpu()
        assert torch.equal(cpu_tensor, mps_tensor), name
