"""Periodic-domain checks for Taylor–Green initialization and references."""

import torch

from diffsph_adapter import (
    TGVConfig,
    build_context,
    taylor_green_velocity,
    wrap_periodic_positions,
)


def test_periodic_wrapping_and_velocity_are_translation_invariant() -> None:
    domain_min = torch.tensor([-1.0, -1.0])
    domain_max = torch.tensor([1.0, 1.0])
    points = torch.tensor(
        [[-1.25, 1.25], [1.0, -1.0], [3.1, -4.2]],
        dtype=torch.float32,
    )
    wrapped = wrap_periodic_positions(points, domain_min, domain_max)
    assert bool((wrapped >= domain_min).all())
    assert bool((wrapped < domain_max).all())

    base_velocity = taylor_green_velocity(
        wrapped,
        0.1,
        amplitude=1.0,
        viscosity=0.01,
        wave_number=2,
    )
    translated_velocity = taylor_green_velocity(
        wrapped + torch.tensor([2.0, -4.0]),
        0.1,
        amplitude=1.0,
        viscosity=0.01,
        wave_number=2,
    )
    torch.testing.assert_close(base_velocity, translated_velocity, atol=2.0e-6, rtol=1.0e-6)


def test_official_domain_marks_both_axes_periodic() -> None:
    context = build_context(
        TGVConfig(
            resolution=16,
            backend="cpu",
            total_time=0.001,
            total_steps=2,
            shuffle_iterations=0,
            warmup_steps=0,
        )
    )
    domain = context.config["domain"]
    assert domain.periodic.tolist() == [True, True]
    assert bool((context.system.systemState.positions >= domain.min).all())
    assert bool((context.system.systemState.positions < domain.max).all())
