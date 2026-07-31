"""Smooth periodic manufactured fields and their exact derivatives."""

from __future__ import annotations

import math

import torch


TWO_PI = 2.0 * math.pi


def scalar_field(positions: torch.Tensor) -> torch.Tensor:
    r"""Return \(f=\sin(2\pi x)+\frac12\cos(2\pi y)\)."""

    x, y = positions[:, 0], positions[:, 1]
    return torch.sin(TWO_PI * x) + 0.5 * torch.cos(TWO_PI * y)


def scalar_gradient(positions: torch.Tensor) -> torch.Tensor:
    r"""Return the exact gradient of :func:`scalar_field`."""

    x, y = positions[:, 0], positions[:, 1]
    return torch.stack(
        (
            TWO_PI * torch.cos(TWO_PI * x),
            -math.pi * torch.sin(TWO_PI * y),
        ),
        dim=-1,
    )


def scalar_laplacian(positions: torch.Tensor) -> torch.Tensor:
    r"""Return the exact Laplacian of :func:`scalar_field`."""

    x, y = positions[:, 0], positions[:, 1]
    return -(TWO_PI**2) * (
        torch.sin(TWO_PI * x) + 0.5 * torch.cos(TWO_PI * y)
    )


def vector_field(positions: torch.Tensor) -> torch.Tensor:
    r"""Return \(v_x=\sin(2\pi x), v_y=\cos(2\pi y)\)."""

    x, y = positions[:, 0], positions[:, 1]
    return torch.stack(
        (torch.sin(TWO_PI * x), torch.cos(TWO_PI * y)),
        dim=-1,
    )


def vector_divergence(positions: torch.Tensor) -> torch.Tensor:
    r"""Return the exact divergence of :func:`vector_field`."""

    x, y = positions[:, 0], positions[:, 1]
    return TWO_PI * (
        torch.cos(TWO_PI * x) - torch.sin(TWO_PI * y)
    )


def vector_laplacian(positions: torch.Tensor) -> torch.Tensor:
    r"""Return the componentwise exact Laplacian of the vector field."""

    return -(TWO_PI**2) * vector_field(positions)
