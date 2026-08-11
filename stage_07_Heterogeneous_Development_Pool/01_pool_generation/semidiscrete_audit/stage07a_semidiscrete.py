"""Frozen same-semidiscrete WCSPH/DOP853 audit for Stage07A."""

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


HERE = Path(__file__).resolve(); POOL = HERE.parents[1]; ROOT = HERE.parents[3]
for candidate in (POOL / "lineage_generator", ROOT / "01_solver"):
    if str(candidate) not in sys.path: sys.path.insert(0, str(candidate))

from dynamic_solver.equation_of_state import isothermal_pressure
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import build_periodic_neighborhood
from stage07a_reference_core import (CS, L, NU, RHO0, SUPPORT_OVER_DX, array_sha, evaluate_symbolic,
                                     exact_frames, graph_for_positions, minimum_image, output_times,
                                     regular_material_layout, wrap_positions)


@dataclass
class Accounting:
    graph_rebuild_count: int = 0
    source_evaluation_count: int = 0
    minimum_density_seen: float = math.inf
    maximum_density_seen: float = -math.inf


class Stage07ASemidiscreteRHS:
    def __init__(self, lineage_id: str, labels: np.ndarray, resolution: int) -> None:
        self.lineage_id = lineage_id; self.variant = "MAIN"; self.labels = np.asarray(labels, dtype=np.float64)
        self.resolution = int(resolution); self.count = len(labels); self.dx = L / resolution
        self.support = SUPPORT_OVER_DX * self.dx
        self.mass = np.full(self.count, RHO0 * self.dx**2, dtype=np.float64); self.mass_t = torch.from_numpy(self.mass)
        self.accounting = Accounting(); self.sequence = hashlib.sha256()

    def pack(self, position: np.ndarray, velocity: np.ndarray, density: np.ndarray) -> np.ndarray:
        return np.concatenate((position.ravel(), velocity.ravel(), density.ravel())).astype(np.float64)

    def unpack(self, state: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        count2 = 2 * self.count
        return state[:count2].reshape(self.count, 2), state[count2:2*count2].reshape(self.count, 2), state[2*count2:]

    def __call__(self, physical_time: float, state: np.ndarray) -> np.ndarray:
        position, velocity, density = self.unpack(state)
        if not np.isfinite(state).all() or np.min(density) <= 0.0: raise FloatingPointError("invalid semidiscrete state")
        self.accounting.minimum_density_seen = min(self.accounting.minimum_density_seen, float(np.min(density)))
        self.accounting.maximum_density_seen = max(self.accounting.maximum_density_seen, float(np.max(density)))
        position_t = torch.from_numpy(np.ascontiguousarray(wrap_positions(position)))
        velocity_t = torch.from_numpy(np.ascontiguousarray(velocity)); density_t = torch.from_numpy(np.ascontiguousarray(density))
        graph = build_periodic_neighborhood(position_t, self.support, domain_minimum=(-1.0, -1.0), domain_maximum=(1.0, 1.0))
        self.accounting.graph_rebuild_count += 1
        directed = np.stack((graph.row.detach().numpy(), graph.col.detach().numpy()), axis=1).astype(np.int32, copy=False)
        self.sequence.update(directed.tobytes())
        pressure = isothermal_pressure(density_t, reference_density=RHO0, sound_speed=CS)
        pf = conservative_pressure_forces(graph, mass=self.mass_t, density=density_t, pressure=pressure)
        vf = conservative_viscosity_forces(graph, mass=self.mass_t, density=density_t, velocity=velocity_t, physical_viscosity=NU)
        gradient = edge_kernel_gradients(graph); dv = velocity_t[graph.row] - velocity_t[graph.col]
        density_rate = scatter_sum(graph.row, self.mass_t[graph.col] * torch.einsum("nd,nd->n", dv, gradient), self.count)
        tau = physical_time * CS / L
        source = evaluate_symbolic(self.lineage_id, self.variant, self.labels, tau)["source"]
        self.accounting.source_evaluation_count += 1
        acceleration = ((pf + vf) / self.mass_t[:, None]).detach().numpy() + source
        return self.pack(velocity, acceleration, density_rate.detach().numpy())


def integrate(lineage_id: str, resolution: int, rtol: float, atol: float) -> dict[str, Any]:
    labels, _ = regular_material_layout(resolution); _n, tau, physical = output_times()
    exact0 = evaluate_symbolic(lineage_id, "MAIN", labels, tau[0]); rhs = Stage07ASemidiscreteRHS(lineage_id, labels, resolution)
    initial = rhs.pack(exact0["position"], exact0["velocity"], exact0["density"])
    solution = solve_ivp(rhs, (float(physical[0]), float(physical[-1])), initial, method="DOP853", t_eval=physical,
                         rtol=float(rtol), atol=float(atol), max_step=(1.0/256.0)*L/CS)
    if not solution.success: raise RuntimeError(solution.message)
    positions = []; velocities = []; densities = []
    for frame in solution.y.T:
        p, v, rho = rhs.unpack(frame); positions.append(p.copy()); velocities.append(v.copy()); densities.append(rho.copy())
    density = np.stack(densities)
    arrays = {"position": wrap_positions(np.stack(positions)), "velocity": np.stack(velocities),
              "density": density, "pressure": CS**2 * (density - RHO0)}
    graph_hashes = [graph_for_positions(frame, SUPPORT_OVER_DX * L / resolution)["graph_sha256"] for frame in arrays["position"]]
    return {**arrays, "nfev": int(solution.nfev), "graph_rebuild_count": rhs.accounting.graph_rebuild_count,
            "rhs_graph_sequence_sha256": "sha256:" + rhs.sequence.hexdigest(), "output_graph_hashes": graph_hashes}


def normalized(error: np.ndarray, scale: float) -> tuple[float, float]:
    values = np.asarray(error) / scale
    return float(np.sqrt(np.mean(values**2))), float(np.max(np.abs(values)))


def audit_case(lineage_id: str, resolution: int) -> tuple[dict[str, Any], dict[str, Any]]:
    exact = exact_frames(lineage_id, "MAIN", resolution)
    primary = integrate(lineage_id, resolution, 1e-11, 1e-13)
    sensitivity = integrate(lineage_id, resolution, 1e-12, 1e-14)
    repeat = integrate(lineage_id, resolution, 1e-11, 1e-13)
    scales = {"position": L, "velocity": CS, "density": RHO0, "pressure": RHO0 * CS**2}
    field = {}; exact_diagnostic = {}
    for key, scale in scales.items():
        delta = minimum_image(primary[key] - sensitivity[key]) if key == "position" else primary[key] - sensitivity[key]
        l2, linf = normalized(delta, scale); field[key] = {"normalized_L2": l2, "normalized_Linf": linf}
        edelta = minimum_image(primary[key] - exact[key]) if key == "position" else primary[key] - exact[key]
        el2, elinf = normalized(edelta, scale)
        exact_diagnostic[key] = {"normalized_L2": el2, "normalized_Linf": elinf,
                                 "role": "semidiscrete_spatial_model_form_diagnostic_only"}
    repeat_equal = all(np.array_equal(primary[key], repeat[key]) for key in scales)
    rhs_sequence_equal = primary["rhs_graph_sequence_sha256"] == repeat["rhs_graph_sequence_sha256"]
    output_graph_equal = primary["output_graph_hashes"] == sensitivity["output_graph_hashes"] == repeat["output_graph_hashes"]
    max_l2 = max(row["normalized_L2"] for row in field.values()); max_linf = max(row["normalized_Linf"] for row in field.values())
    gates = {"normalized_L2": max_l2 <= 1e-9, "normalized_Linf": max_linf <= 1e-8,
             "primary_repeat_deterministic": repeat_equal and rhs_sequence_equal,
             "graph_sequence_deterministic": output_graph_equal,
             "finite": all(np.isfinite(value).all() for run in (primary, sensitivity, repeat) for value in run.values() if isinstance(value, np.ndarray))}
    metrics = {"lineage_id": lineage_id, "variant": "MAIN", "resolution": resolution,
               "field_primary_sensitivity": field, "maximum_normalized_L2": max_l2, "maximum_normalized_Linf": max_linf,
               "primary_repeat_bitwise": repeat_equal, "rhs_graph_sequence_repeat": rhs_sequence_equal,
               "output_graph_event_sequence_deterministic": output_graph_equal,
               "primary_nfev": primary["nfev"], "sensitivity_nfev": sensitivity["nfev"], "repeat_nfev": repeat["nfev"],
               "graph_rebuild_count": primary["graph_rebuild_count"] + sensitivity["graph_rebuild_count"] + repeat["graph_rebuild_count"],
               "semidiscrete_versus_exact": exact_diagnostic, "gates": gates,
               "verdict": "PASS" if all(gates.values()) else "FAIL"}
    private = {"primary_array_sha256": array_sha(*[primary[key] for key in scales]),
               "sensitivity_array_sha256": array_sha(*[sensitivity[key] for key in scales]),
               "repeat_array_sha256": array_sha(*[repeat[key] for key in scales]),
               "primary_rhs_graph_sequence_sha256": primary["rhs_graph_sequence_sha256"],
               "sensitivity_rhs_graph_sequence_sha256": sensitivity["rhs_graph_sequence_sha256"],
               "repeat_rhs_graph_sequence_sha256": repeat["rhs_graph_sequence_sha256"]}
    return metrics, private
