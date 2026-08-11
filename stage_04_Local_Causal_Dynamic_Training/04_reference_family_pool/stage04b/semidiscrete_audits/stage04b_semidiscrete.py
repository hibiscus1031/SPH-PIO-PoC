"""Frozen same-semidscrete WCSPH/DOP853 audit for Stage 04B."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
import torch


HERE = Path(__file__).resolve()
STAGE04B = HERE.parents[1]
ROOT = HERE.parents[4]
CORE = STAGE04B / "formula_templates"
for candidate in (CORE, ROOT / "01_solver"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from dynamic_solver.equation_of_state import isothermal_pressure
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import build_periodic_neighborhood
from stage04b_reference_core import (
    CS, L, NU, RHO0, SUPPORT_OVER_DX, array_sha256, evaluate_symbolic,
    exact_frames, graph_for_positions, minimum_image, output_times,
    regular_material_layout, wrap_positions,
)


@dataclass
class Accounting:
    graph_rebuild_count: int = 0
    source_evaluation_count: int = 0
    minimum_density_seen: float = math.inf
    maximum_density_seen: float = -math.inf


class Stage04BSemidiscreteRHS:
    def __init__(self, family_id: str, material_labels: np.ndarray, resolution: int) -> None:
        self.family_id = family_id
        self.variant = "VARIANT_MAIN"
        self.material_labels = np.asarray(material_labels, dtype=np.float64)
        self.resolution = int(resolution)
        self.count = len(self.material_labels)
        self.dx = L / self.resolution
        self.support = SUPPORT_OVER_DX * self.dx
        self.mass = np.full(self.count, RHO0 * self.dx**2, dtype=np.float64)
        self.mass_t = torch.from_numpy(self.mass)
        self.accounting = Accounting()
        self.sequence_digest = hashlib.sha256()

    def pack(self, position: np.ndarray, velocity: np.ndarray, density: np.ndarray) -> np.ndarray:
        return np.concatenate((position.ravel(), velocity.ravel(), density.ravel())).astype(np.float64)

    def unpack(self, state: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        count2 = 2 * self.count
        return state[:count2].reshape(self.count, 2), state[count2:2 * count2].reshape(self.count, 2), state[2 * count2:]

    def __call__(self, physical_time: float, state: np.ndarray) -> np.ndarray:
        position, velocity, density = self.unpack(state)
        if not np.isfinite(state).all() or np.min(density) <= 0.0:
            raise FloatingPointError("nonfinite or nonpositive semidiscrete state")
        self.accounting.minimum_density_seen = min(self.accounting.minimum_density_seen, float(np.min(density)))
        self.accounting.maximum_density_seen = max(self.accounting.maximum_density_seen, float(np.max(density)))
        wrapped = wrap_positions(position)
        position_t = torch.from_numpy(np.ascontiguousarray(wrapped))
        velocity_t = torch.from_numpy(np.ascontiguousarray(velocity))
        density_t = torch.from_numpy(np.ascontiguousarray(density))
        graph = build_periodic_neighborhood(position_t, self.support, domain_minimum=(-1.0, -1.0), domain_maximum=(1.0, 1.0))
        self.accounting.graph_rebuild_count += 1
        directed = np.stack((graph.row.detach().numpy(), graph.col.detach().numpy()), axis=1).astype(np.int32, copy=False)
        self.sequence_digest.update(directed.tobytes())
        pressure_t = isothermal_pressure(density_t, reference_density=RHO0, sound_speed=CS)
        pressure_force = conservative_pressure_forces(graph, mass=self.mass_t, density=density_t, pressure=pressure_t)
        viscosity_force = conservative_viscosity_forces(graph, mass=self.mass_t, density=density_t, velocity=velocity_t, physical_viscosity=NU)
        gradient = edge_kernel_gradients(graph)
        velocity_difference = velocity_t[graph.row] - velocity_t[graph.col]
        continuity_edge = self.mass_t[graph.col] * torch.einsum("nd,nd->n", velocity_difference, gradient)
        density_rate = scatter_sum(graph.row, continuity_edge, self.count)
        tau = physical_time * CS / L
        exact_source = evaluate_symbolic(self.family_id, self.variant, self.material_labels, tau)["source"]
        self.accounting.source_evaluation_count += 1
        acceleration = ((pressure_force + viscosity_force) / self.mass_t[:, None]).detach().numpy() + exact_source
        return self.pack(velocity, acceleration, density_rate.detach().numpy())


def integrate_semidiscrete(family_id: str, resolution: int, *, rtol: float, atol: float) -> dict[str, Any]:
    labels, _dx = regular_material_layout(resolution)
    _frame_n, tau, physical_time = output_times()
    exact0 = evaluate_symbolic(family_id, "VARIANT_MAIN", labels, tau[0])
    rhs = Stage04BSemidiscreteRHS(family_id, labels, resolution)
    initial = rhs.pack(exact0["position"], exact0["velocity"], exact0["density"])
    solution = solve_ivp(
        rhs, (float(physical_time[0]), float(physical_time[-1])), initial,
        method="DOP853", t_eval=physical_time, rtol=float(rtol), atol=float(atol),
        max_step=(1.0 / 256.0) * L / CS,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    positions: list[np.ndarray] = []
    velocities: list[np.ndarray] = []
    densities: list[np.ndarray] = []
    pressures: list[np.ndarray] = []
    for frame in solution.y.T:
        position, velocity, density = rhs.unpack(frame)
        positions.append(position.copy()); velocities.append(velocity.copy()); densities.append(density.copy())
        pressures.append(CS**2 * (density - RHO0))
    arrays = {
        "position_unwrapped": np.stack(positions),
        "position": wrap_positions(np.stack(positions)),
        "velocity": np.stack(velocities),
        "density": np.stack(densities),
        "pressure": np.stack(pressures),
    }
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise FloatingPointError("nonfinite DOP853 output")
    output_graph_hashes = [graph_for_positions(frame, SUPPORT_OVER_DX * L / resolution)["graph_sha256"] for frame in arrays["position"]]
    return {
        **arrays,
        "nfev": int(solution.nfev), "njev": int(solution.njev), "nlu": int(solution.nlu),
        "graph_rebuild_count": rhs.accounting.graph_rebuild_count,
        "source_evaluation_count": rhs.accounting.source_evaluation_count,
        "minimum_density_seen": rhs.accounting.minimum_density_seen,
        "maximum_density_seen": rhs.accounting.maximum_density_seen,
        "rhs_graph_sequence_sha256": "sha256:" + rhs.sequence_digest.hexdigest(),
        "output_graph_hashes": output_graph_hashes,
        "rtol": float(rtol), "atol": float(atol),
        "integrator": "scipy.integrate.solve_ivp:DOP853",
        "semidiscrete_identity": "frozen_continuity_pressure_viscosity_EOS_graph_rebuild_exact_label_time_source",
    }


def _normalized(error: np.ndarray, scale: float) -> tuple[float, float]:
    values = np.asarray(error, dtype=np.float64) / scale
    return float(np.sqrt(np.mean(values**2))), float(np.max(np.abs(values)))


def audit_case(family_id: str, resolution: int) -> tuple[dict[str, Any], dict[str, Any]]:
    exact = exact_frames(family_id, "VARIANT_MAIN", resolution)
    primary = integrate_semidiscrete(family_id, resolution, rtol=1e-11, atol=1e-13)
    sensitivity = integrate_semidiscrete(family_id, resolution, rtol=1e-12, atol=1e-14)
    repeat = integrate_semidiscrete(family_id, resolution, rtol=1e-11, atol=1e-13)
    scales = {"position": L, "velocity": CS, "density": RHO0, "pressure": RHO0 * CS**2}
    field_metrics: dict[str, Any] = {}
    exact_diagnostic: dict[str, Any] = {}
    for key, scale in scales.items():
        delta = minimum_image(primary[key] - sensitivity[key]) if key == "position" else primary[key] - sensitivity[key]
        dl2, dlinf = _normalized(delta, scale)
        exact_delta = minimum_image(primary[key] - exact[key]) if key == "position" else primary[key] - exact[key]
        el2, elinf = _normalized(exact_delta, scale)
        field_metrics[key] = {"normalized_L2": dl2, "normalized_Linf": dlinf}
        exact_diagnostic[key] = {"normalized_L2": el2, "normalized_Linf": elinf, "role": "semidiscrete_spatial_model_form_diagnostic_only"}
    repeat_equal = all(np.array_equal(primary[key], repeat[key]) for key in scales)
    graph_repeat = primary["rhs_graph_sequence_sha256"] == repeat["rhs_graph_sequence_sha256"]
    output_graph_deterministic = primary["output_graph_hashes"] == sensitivity["output_graph_hashes"] == repeat["output_graph_hashes"]
    max_l2 = max(item["normalized_L2"] for item in field_metrics.values())
    max_linf = max(item["normalized_Linf"] for item in field_metrics.values())
    gates = {
        "primary_sensitivity_L2": max_l2 <= 1e-9,
        "primary_sensitivity_Linf": max_linf <= 1e-8,
        "primary_repeat_deterministic": repeat_equal and graph_repeat,
        "graph_event_sequence_deterministic": output_graph_deterministic,
        "finite": all(np.isfinite(value).all() for run in (primary, sensitivity, repeat) for key, value in run.items() if isinstance(value, np.ndarray)),
    }
    metrics = {
        "family_id": family_id, "variant": "VARIANT_MAIN", "resolution": resolution,
        "field_primary_sensitivity": field_metrics,
        "maximum_normalized_L2": max_l2, "maximum_normalized_Linf": max_linf,
        "primary_repeat_bitwise": repeat_equal,
        "rhs_graph_sequence_repeat": graph_repeat,
        "output_graph_event_sequence_deterministic": output_graph_deterministic,
        "primary_nfev": primary["nfev"], "sensitivity_nfev": sensitivity["nfev"], "repeat_nfev": repeat["nfev"],
        "graph_rebuild_count": primary["graph_rebuild_count"] + sensitivity["graph_rebuild_count"] + repeat["graph_rebuild_count"],
        "semidiscrete_versus_exact": exact_diagnostic,
        "time_reference_role": "same_semidiscrete_time_reference_audit",
        "training_target": False, "spatial_truth": False,
        "gates": gates, "verdict": "PASS" if all(gates.values()) else "FAIL",
    }
    private = {
        "primary_array_sha256": array_sha256(*[primary[key] for key in scales]),
        "sensitivity_array_sha256": array_sha256(*[sensitivity[key] for key in scales]),
        "repeat_array_sha256": array_sha256(*[repeat[key] for key in scales]),
        "primary_rhs_graph_sequence_sha256": primary["rhs_graph_sequence_sha256"],
        "sensitivity_rhs_graph_sequence_sha256": sensitivity["rhs_graph_sequence_sha256"],
        "repeat_rhs_graph_sequence_sha256": repeat["rhs_graph_sequence_sha256"],
    }
    return metrics, private
