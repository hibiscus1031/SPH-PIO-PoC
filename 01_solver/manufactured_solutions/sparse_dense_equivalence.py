"""Aggregation-based sparse/dense comparison metrics."""

from __future__ import annotations
import torch


def difference_metrics(sparse: torch.Tensor, dense: torch.Tensor) -> dict[str, float]:
    if sparse.shape != dense.shape:
        raise ValueError("sparse and dense values must share shape")
    delta = sparse - dense
    absolute = float(delta.abs().max())
    scale = float(torch.maximum(sparse.abs(), dense.abs()).max())
    return {"absolute_linf": absolute, "relative_linf": absolute / max(scale, torch.finfo(delta.dtype).tiny)}


def equivalence_gate(comparisons: dict[str, dict[str, float]]) -> dict[str, bool]:
    return {
        "density": comparisons["density"]["relative_linf"] <= 1e-13,
        "pressure": comparisons["pressure"]["relative_linf"] <= 1e-13,
        "acceleration_relative": comparisons["total_acceleration"]["relative_linf"] <= 1e-11,
        "acceleration_absolute": comparisons["total_acceleration"]["absolute_linf"] <= 1e-12,
    }
