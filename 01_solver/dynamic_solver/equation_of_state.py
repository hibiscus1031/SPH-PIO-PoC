"""Fixed isothermal equation of state for Stage 01D."""

from __future__ import annotations

import torch

from dynamic_solver.state import DynamicSPHState


def _scalar_like(
    value: float | torch.Tensor,
    reference: torch.Tensor,
    *,
    name: str,
    positive: bool,
) -> torch.Tensor:
    if torch.is_tensor(value):
        if value.numel() != 1:
            raise ValueError(f"{name} must be scalar")
        result = value.reshape(()).to(
            dtype=reference.dtype,
            device=reference.device,
        )
    else:
        result = torch.as_tensor(
            value,
            dtype=reference.dtype,
            device=reference.device,
        )
    detached = result.detach()
    if not bool(torch.isfinite(detached)):
        raise ValueError(f"{name} must be finite")
    if positive and not bool(detached > 0.0):
        raise ValueError(f"{name} must be positive")
    return result


def isothermal_pressure(
    density: torch.Tensor,
    *,
    reference_density: float | torch.Tensor,
    sound_speed: float | torch.Tensor,
) -> torch.Tensor:
    r"""Evaluate the fixed, unclipped isothermal EOS.

    .. math::

       p_i = c_s^2(\rho_i-\rho_0).

    Negative pressures are retained. No background pressure, clipping, or
    artificial stabilizer is introduced.
    """

    if not torch.is_tensor(density) or density.ndim != 1:
        raise ValueError("density must have shape [particles]")
    if density.device.type != "cpu" or density.dtype != torch.float64:
        raise ValueError("density must use float64 on CPU")
    if not bool(torch.isfinite(density.detach()).all()):
        raise ValueError("density must be finite")
    if bool((density.detach() <= 0.0).any()):
        raise ValueError("density must be positive")
    rho0 = _scalar_like(
        reference_density,
        density,
        name="reference_density",
        positive=True,
    )
    c_s = _scalar_like(
        sound_speed,
        density,
        name="sound_speed",
        positive=True,
    )
    return c_s.square() * (density - rho0)


def recompute_pressure(
    state: DynamicSPHState,
    *,
    reference_density: float | torch.Tensor,
    sound_speed: float | torch.Tensor,
) -> DynamicSPHState:
    """Return ``state`` with pressure obtained directly from its density."""

    pressure = isothermal_pressure(
        state.densities,
        reference_density=reference_density,
        sound_speed=sound_speed,
    )
    return state.with_updates(pressures=pressure)
