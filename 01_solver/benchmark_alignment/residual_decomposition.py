"""Closed Stage 01E decomposition of the frozen WCSPH acceleration."""

from __future__ import annotations

import math
from typing import Any

import torch

from benchmark_alignment.analytic_pressure import analytic_pressure_operator_acceleration
from benchmark_alignment.incompressible_tgv_exact import material_acceleration, pressure_acceleration, viscous_acceleration
from dynamic_solver.acceleration import DynamicPhysicalParameters, ForceEvaluation, evaluate_internal_acceleration
from dynamic_solver.state import DynamicSPHState
from dynamic_solver.taylor_green import initialize_taylor_green_state


def vector_norms(value: torch.Tensor, scale: torch.Tensor | None = None) -> dict[str, float]:
    point = torch.linalg.vector_norm(value, dim=-1) if value.ndim == 2 else value.abs()
    l1 = point.mean(); l2 = torch.sqrt(torch.mean(point.square())); linf = point.max()
    if scale is None:
        denominator = torch.tensor(1.0, dtype=value.dtype)
    else:
        scale_point = torch.linalg.vector_norm(scale, dim=-1) if scale.ndim == 2 else scale.abs()
        denominator = torch.sqrt(torch.mean(scale_point.square())).clamp_min(torch.finfo(value.dtype).eps)
    return {"L1": float(l1), "L2": float(l2), "Linf": float(linf), "relative_L2": float(l2/denominator)}


def decompose_state(state: DynamicSPHState, evaluation: ForceEvaluation, *, reference_density: float = 1.0, velocity_amplitude: float = 1.0, viscosity: float = 0.02) -> dict[str, Any]:
    exact_pressure, pressure_exact_input = analytic_pressure_operator_acceleration(evaluation.neighborhood, positions=state.positions, mass=state.masses, density=evaluation.densities, time=float(state.time), reference_density=reference_density, velocity_amplitude=velocity_amplitude, viscosity=viscosity)
    pressure_eos = evaluation.pressure_force / state.masses[:, None]
    viscous_discrete = evaluation.viscosity_force / state.masses[:, None]
    pressure_exact = pressure_acceleration(state.positions, float(state.time), reference_density=reference_density, velocity_amplitude=velocity_amplitude, viscosity=viscosity)
    viscous_exact = viscous_acceleration(state.positions, float(state.time), velocity_amplitude=velocity_amplitude, viscosity=viscosity)
    material_exact = material_acceleration(state.positions, float(state.time), reference_density=reference_density, velocity_amplitude=velocity_amplitude, viscosity=viscosity)
    residuals = {
        "density": evaluation.densities-reference_density,
        "pressure_operator": pressure_exact_input-pressure_exact,
        "EOS_initialization": pressure_eos-pressure_exact_input,
        "viscosity": viscous_discrete-viscous_exact,
        "total": pressure_eos+viscous_discrete-material_exact,
    }
    closure = residuals["total"]-residuals["pressure_operator"]-residuals["EOS_initialization"]-residuals["viscosity"]
    scales = {"density": torch.full_like(evaluation.densities, reference_density), "pressure_operator": pressure_exact, "EOS_initialization": pressure_exact, "viscosity": viscous_exact, "total": material_exact}
    result: dict[str, Any] = {}
    for name, value in residuals.items():
        result.update({f"R_{name}_{key}": metric for key, metric in vector_norms(value, scales[name]).items()})
    result.update({f"closure_{key}": metric for key, metric in vector_norms(closure, material_exact).items()})
    nonself = evaluation.neighborhood.nonself
    counts = torch.bincount(evaluation.neighborhood.row[nonself], minlength=state.particle_count).to(torch.float64)
    result.update({
        "density_rms": float(torch.sqrt(torch.mean((evaluation.densities-reference_density).square()))),
        "EOS_pressure_rms": float(torch.sqrt(torch.mean(evaluation.pressures.square()))),
        "analytic_pressure_rms": float(torch.sqrt(torch.mean(exact_pressure.square()))),
        "mean_edge_count": float(evaluation.neighborhood.row.numel()),
        "mean_neighbor_count": float(counts.mean()),
        "minimum_separation": float(evaluation.neighborhood.distance[nonself].min()),
    })
    return result


def compute_initial_case(*, resolution: int, support_ratio: float, jitter_fraction: float, seed: int, reference_density: float = 1.0, sound_speed: float = 20.0, velocity_amplitude: float = 1.0, viscosity: float = 0.02) -> dict[str, Any]:
    with torch.no_grad():
        state = initialize_taylor_green_state(resolution, support_ratio=support_ratio, reference_density=reference_density, velocity_amplitude=velocity_amplitude, physical_viscosity=viscosity, sound_speed=sound_speed, jitter_fraction=jitter_fraction, seed=seed)
        evaluation = evaluate_internal_acceleration(state, DynamicPhysicalParameters(reference_density=reference_density, sound_speed=sound_speed, physical_viscosity=viscosity))
        row = decompose_state(state, evaluation, reference_density=reference_density, velocity_amplitude=velocity_amplitude, viscosity=viscosity)
    dx = 2.0/resolution
    row.update(resolution=resolution, particle_count=resolution**2, dx=dx, H=support_ratio*dx, support_ratio=support_ratio, dx_over_H=1.0/support_ratio, jitter_fraction=jitter_fraction, seed=seed)
    return row
