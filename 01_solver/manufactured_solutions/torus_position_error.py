"""Two-dimensional periodic minimum-image position errors."""

from __future__ import annotations

import torch


def minimum_image_displacement(
    numerical_positions: torch.Tensor,
    exact_positions: torch.Tensor,
    *,
    domain_length: float = 2.0,
) -> torch.Tensor:
    if numerical_positions.shape != exact_positions.shape:
        raise ValueError("position tensors must have identical shapes")
    delta = numerical_positions - exact_positions
    length = torch.as_tensor(domain_length, dtype=delta.dtype, device=delta.device)
    return torch.remainder(delta + 0.5 * length, length) - 0.5 * length


def position_error_norms(
    numerical_positions: torch.Tensor,
    exact_positions: torch.Tensor,
    *,
    domain_length: float = 2.0,
) -> dict[str, float]:
    distance = torch.linalg.vector_norm(
        minimum_image_displacement(
            numerical_positions, exact_positions, domain_length=domain_length
        ),
        dim=-1,
    )
    return {
        "L1": float(distance.mean()),
        "L2": float(torch.sqrt(torch.mean(distance.square()))),
        "Linf": float(distance.max()),
    }
