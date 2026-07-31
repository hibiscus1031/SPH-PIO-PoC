"""Kernel-summation density for the Stage 01D dynamic solver."""

from __future__ import annotations

import torch

from dynamic_solver.state import DynamicSPHState
from structure_preserving.kernels import edge_kernel_values, scatter_sum
from structure_preserving.neighborhood import PeriodicNeighborhood


def _validate_mass(
    neighborhood: PeriodicNeighborhood,
    mass: torch.Tensor,
) -> None:
    if not torch.is_tensor(mass):
        raise TypeError("mass must be a torch.Tensor")
    if mass.shape != (neighborhood.particle_count,):
        raise ValueError("mass must have shape [particles]")
    if mass.device.type != "cpu" or mass.dtype != torch.float64:
        raise ValueError("mass must use float64 on CPU")
    if not bool(torch.isfinite(mass.detach()).all()):
        raise ValueError("mass must be finite")
    if bool((mass.detach() <= 0.0).any()):
        raise ValueError("mass must be positive")
    if (
        neighborhood.distance.device.type != "cpu"
        or neighborhood.distance.dtype != torch.float64
    ):
        raise ValueError("neighborhood geometry must use float64 on CPU")


def summation_density(
    neighborhood: PeriodicNeighborhood,
    *,
    mass: torch.Tensor,
) -> torch.Tensor:
    r"""Evaluate the unique Stage 01D density definition.

    .. math::

       \rho_i = \sum_j m_j W_{ij}.

    Self edges are retained, as required by the compact-kernel summation.
    No Shepard normalization, mass retuning, clipping, or density diffusion
    is applied.
    """

    _validate_mass(neighborhood, mass)
    edge_density = (
        mass[neighborhood.col] * edge_kernel_values(neighborhood)
    )
    density = scatter_sum(
        neighborhood.row,
        edge_density,
        neighborhood.particle_count,
    )
    if not bool(torch.isfinite(density.detach()).all()):
        raise FloatingPointError("summation density is nonfinite")
    if bool((density.detach() <= 0.0).any()):
        raise FloatingPointError("summation density must remain positive")
    return density


def recompute_density(
    state: DynamicSPHState,
    neighborhood: PeriodicNeighborhood,
) -> DynamicSPHState:
    """Return ``state`` with density recomputed from the current graph.

    Pressure is intentionally left unchanged. A complete force evaluation
    must call :func:`dynamic_solver.equation_of_state.recompute_pressure`
    immediately after this operation.
    """

    if neighborhood.particle_count != state.particle_count:
        raise ValueError("neighborhood and state particle counts differ")
    density = summation_density(neighborhood, mass=state.masses)
    return state.with_updates(densities=density)
