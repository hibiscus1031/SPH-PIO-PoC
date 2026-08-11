"""Frozen graph-balanced loss and static metric definitions."""

from __future__ import annotations

import torch
from torch import Tensor

A0 = 400.0
EPSILON_METRIC = 4.0e-10


def graph_node_mse(prediction: Tensor, target: Tensor) -> Tensor:
    return torch.mean(torch.sum(((prediction - target) / A0) ** 2, dim=-1))


def graph_balanced_node_mse(predictions: list[Tensor], targets: list[Tensor]) -> Tensor:
    if len(predictions) != len(targets) or not predictions:
        raise ValueError("nonempty one-to-one complete graph lists required")
    return torch.stack([graph_node_mse(p, t) for p, t in zip(predictions, targets)]).mean()


def static_metrics(prediction: Tensor, target: Tensor) -> dict[str, Tensor]:
    error = prediction - target
    rms_error = torch.sqrt(torch.mean(torch.sum(error * error, dim=-1)))
    rms_target = torch.sqrt(torch.mean(torch.sum(target * target, dim=-1)))
    linf_error = torch.max(torch.linalg.vector_norm(error, dim=-1))
    linf_target = torch.max(torch.linalg.vector_norm(target, dim=-1))
    flat_prediction, flat_target = prediction.reshape(-1), target.reshape(-1)
    cosine = torch.sum(flat_prediction * flat_target) / torch.clamp(torch.linalg.vector_norm(flat_prediction) * torch.linalg.vector_norm(flat_target), min=EPSILON_METRIC**2)
    return {"Q_L2": rms_error / (rms_target + EPSILON_METRIC), "Q_Linf": linf_error / (linf_target + EPSILON_METRIC), "cosine": cosine}
