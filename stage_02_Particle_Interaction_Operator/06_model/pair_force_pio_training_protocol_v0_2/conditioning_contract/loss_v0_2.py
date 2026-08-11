"""Frozen prospective Stage 02M-P scaled graph-balanced loss; no training code."""

from __future__ import annotations

import torch
from torch import Tensor

A_SUP = 0.392220124168075
SUPERVISION_SCALE_HASH = "sha256:85d5339dde02c29dba5bfa753096ab25598bd29a5df576def7691dcdbfef838e"


def graph_scaled_node_mse(prediction: Tensor, target: Tensor) -> Tensor:
    return torch.mean(torch.sum(((prediction - target) / A_SUP) ** 2, dim=-1))


def complete_graph_balanced_loss(predictions: list[Tensor], targets: list[Tensor]) -> Tensor:
    if len(predictions) != 10 or len(targets) != 10:
        raise ValueError("exactly ten one-to-one complete train graphs required")
    return torch.stack([graph_scaled_node_mse(prediction, target) for prediction, target in zip(predictions, targets)]).mean()
