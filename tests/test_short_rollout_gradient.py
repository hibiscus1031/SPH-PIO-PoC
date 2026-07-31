"""Two-step full-diffSPH graph-retention smoke tests."""

import pytest
import torch

from diffsph_adapter import (
    TGVConfig,
    advance_one_step,
    build_context,
    taylor_green_velocity,
)


def _backends() -> list[str]:
    result = ["cpu"]
    if torch.backends.mps.is_available():
        result.append("mps")
    return result


@pytest.mark.parametrize("backend", _backends())
def test_two_step_rollout_retains_nonzero_finite_alpha_gradient(backend: str) -> None:
    alpha = torch.tensor(
        0.9,
        dtype=torch.float32,
        device=backend,
        requires_grad=True,
    )
    spec = TGVConfig(
        resolution=16,
        backend=backend,
        total_time=0.001,
        total_steps=2,
        shuffle_iterations=0,
        warmup_steps=0,
    )
    context = build_context(spec, amplitude=alpha)
    for _ in range(2):
        advance_one_step(context)
        assert context.system.systemState.velocities.requires_grad

    state = context.system.systemState
    target = taylor_green_velocity(
        state.positions,
        context.system.t,
        amplitude=1.0,
        viscosity=context.reference_kinematic_viscosity,
        wave_number=spec.wave_number,
    )
    loss = (state.velocities - target).square().mean()
    loss.backward()
    if backend == "mps":
        torch.mps.synchronize()

    assert alpha.grad is not None
    assert bool(torch.isfinite(alpha.grad))
    assert bool(alpha.grad != 0)
