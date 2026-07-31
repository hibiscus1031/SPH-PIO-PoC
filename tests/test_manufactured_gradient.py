"""Manufactured periodic scalar-gradient verification."""

from __future__ import annotations

import pytest
import torch

from manufactured_fields.periodic import scalar_field, scalar_gradient
from verification.operator_tools import (
    apply_gradient,
    build_layout,
    error_norms,
    evaluate_fluid_neighborhood,
)


@pytest.mark.parametrize("jitter_fraction", [0.0, 0.05, 0.10])
def test_manufactured_gradient_has_overall_refinement_trend(
    jitter_fraction: float,
) -> None:
    errors = []
    for resolution in (16, 24, 32):
        context, _ = build_layout(resolution, jitter_fraction)
        neighborhood = evaluate_fluid_neighborhood(context)
        positions = context.system.systemState.positions
        numerical = apply_gradient(
            context,
            neighborhood,
            scalar_field(positions),
        )
        errors.append(error_norms(numerical, scalar_gradient(positions)))

    for norm in ("l1", "l2", "linf"):
        assert errors[-1][norm] < errors[0][norm]


def test_constant_scalar_gradient_is_zero() -> None:
    context, _ = build_layout(24, 0.10)
    neighborhood = evaluate_fluid_neighborhood(context)
    constant = torch.ones(
        context.system.systemState.positions.shape[0],
        dtype=context.system.systemState.positions.dtype,
    )
    numerical = apply_gradient(context, neighborhood, constant)
    assert torch.count_nonzero(numerical) == 0
