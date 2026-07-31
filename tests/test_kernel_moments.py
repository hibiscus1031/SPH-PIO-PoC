"""Quantitative zeroth- and first-kernel-moment checks."""

from __future__ import annotations

import pytest
import torch

from verification.operator_tools import (
    build_layout,
    error_norms,
    evaluate_fluid_neighborhood,
    kernel_moments,
)


@pytest.mark.parametrize("resolution", [16, 24, 32])
@pytest.mark.parametrize("jitter_fraction", [0.0, 0.05, 0.10])
def test_kernel_moments_are_finite_and_quantified(
    resolution: int,
    jitter_fraction: float,
) -> None:
    context, state_hash = build_layout(resolution, jitter_fraction)
    neighborhood = evaluate_fluid_neighborhood(context)
    moments = kernel_moments(context, neighborhood)
    s0_error = error_norms(moments["s0"], torch.ones_like(moments["s0"]))
    s1_l2 = torch.sqrt(torch.mean(moments["s1"].square()))
    s1_linf = moments["s1"].abs().max()

    assert len(state_hash) == 64
    assert all(torch.isfinite(value).all() for value in moments.values())
    assert s0_error["l2"] < 3.0e-2
    assert float(s1_l2) < 3.0e-3
    assert float(s1_linf) < 8.0e-3


@pytest.mark.parametrize("jitter_fraction", [0.0, 0.05, 0.10])
def test_layout_hash_is_reproducible(jitter_fraction: float) -> None:
    _, first = build_layout(16, jitter_fraction)
    _, second = build_layout(16, jitter_fraction)
    assert first == second
