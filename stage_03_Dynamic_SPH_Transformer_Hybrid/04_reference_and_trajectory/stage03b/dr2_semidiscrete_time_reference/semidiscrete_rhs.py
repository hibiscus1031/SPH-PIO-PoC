"""Frozen same-semidscrete WCSPH RHS and DOP853 driver for Stage 03B."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
import torch


HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]
CORE = HERE.parents[1] / "analytic_core"
for candidate in (str(ROOT / "01_solver"), str(CORE)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from dynamic_solver.equation_of_state import isothermal_pressure
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import build_periodic_neighborhood
from reference_core import evaluate_symbolic, load_config, physical_constants, wrap_positions


@dataclass
class RHSAccounting:
    graph_rebuild_count: int = 0
    source_evaluation_count: int = 0
    minimum_density_seen: float = math.inf
    maximum_density_seen: float = -math.inf


class SemidiscreteMMSRHS:
    """Independent-density semidiscrete RHS with a label-based exact MMS source."""

    def __init__(
        self,
        family: str,
        material_labels: np.ndarray,
        resolution: int,
    ) -> None:
        self.family = family
        self.material_labels = np.asarray(material_labels, dtype=np.float64)
        self.resolution = int(resolution)
        self.count = len(self.material_labels)
        length, rho0, cs, nu, lower, upper = physical_constants()
        self.length = length
        self.rho0 = rho0
        self.cs = cs
        self.nu = nu
        self.lower = lower
        self.upper = upper
        self.dx = length / self.resolution
        self.support = float(load_config()["execution"]["support_over_dx"]) * self.dx
        self.mass = np.full(self.count, rho0 * self.dx**2, dtype=np.float64)
        self.mass_t = torch.from_numpy(self.mass)
        self.accounting = RHSAccounting()

    def pack(self, positions: np.ndarray, velocity: np.ndarray, density: np.ndarray) -> np.ndarray:
        return np.concatenate((positions.ravel(), velocity.ravel(), density.ravel())).astype(np.float64)

    def unpack(self, state: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        count2 = 2 * self.count
        positions = state[:count2].reshape(self.count, 2)
        velocity = state[count2 : 2 * count2].reshape(self.count, 2)
        density = state[2 * count2 :]
        return positions, velocity, density

    def __call__(self, physical_time: float, state: np.ndarray) -> np.ndarray:
        positions, velocity, density = self.unpack(state)
        if not np.isfinite(state).all():
            raise FloatingPointError("nonfinite semidiscrete state")
        if np.min(density) <= 0.0:
            raise FloatingPointError("nonpositive density in semidiscrete RHS")
        self.accounting.minimum_density_seen = min(
            self.accounting.minimum_density_seen, float(np.min(density)),
        )
        self.accounting.maximum_density_seen = max(
            self.accounting.maximum_density_seen, float(np.max(density)),
        )
        wrapped = wrap_positions(positions)
        position_t = torch.from_numpy(np.ascontiguousarray(wrapped))
        velocity_t = torch.from_numpy(np.ascontiguousarray(velocity))
        density_t = torch.from_numpy(np.ascontiguousarray(density))
        graph = build_periodic_neighborhood(
            position_t,
            self.support,
            domain_minimum=(float(self.lower[0]), float(self.lower[1])),
            domain_maximum=(float(self.upper[0]), float(self.upper[1])),
        )
        self.accounting.graph_rebuild_count += 1
        pressure_t = isothermal_pressure(
            density_t,
            reference_density=self.rho0,
            sound_speed=self.cs,
        )
        pressure_force = conservative_pressure_forces(
            graph,
            mass=self.mass_t,
            density=density_t,
            pressure=pressure_t,
        )
        viscosity_force = conservative_viscosity_forces(
            graph,
            mass=self.mass_t,
            density=density_t,
            velocity=velocity_t,
            physical_viscosity=self.nu,
        )
        gradient = edge_kernel_gradients(graph)
        velocity_difference = velocity_t[graph.row] - velocity_t[graph.col]
        continuity_edge = self.mass_t[graph.col] * torch.einsum(
            "nd,nd->n", velocity_difference, gradient,
        )
        density_rate = scatter_sum(graph.row, continuity_edge, self.count)
        tau = physical_time * self.cs / self.length
        exact_source = evaluate_symbolic(
            self.family, self.material_labels, tau,
        )["source"]
        self.accounting.source_evaluation_count += 1
        acceleration = (
            (pressure_force + viscosity_force) / self.mass_t[:, None]
        ).detach().numpy() + exact_source
        return self.pack(velocity, acceleration, density_rate.detach().numpy())


def integrate_semidiscrete(
    family: str,
    material_labels: np.ndarray,
    resolution: int,
    physical_times: np.ndarray,
    *,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    cfg = load_config()["dr2"]
    length, _, cs, _, _, _ = physical_constants()
    exact0 = evaluate_symbolic(family, material_labels, 0.0)
    rhs = SemidiscreteMMSRHS(family, material_labels, resolution)
    initial = rhs.pack(exact0["position"], exact0["velocity"], exact0["density"])
    maximum_step = float(cfg["maximum_step_tau"]) * length / cs
    solution = solve_ivp(
        rhs,
        (float(physical_times[0]), float(physical_times[-1])),
        initial,
        method="DOP853",
        t_eval=np.asarray(physical_times, dtype=np.float64),
        rtol=float(rtol),
        atol=float(atol),
        max_step=maximum_step,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    frames = solution.y.T
    positions: list[np.ndarray] = []
    velocities: list[np.ndarray] = []
    densities: list[np.ndarray] = []
    pressures: list[np.ndarray] = []
    for frame in frames:
        position, velocity, density = rhs.unpack(frame)
        positions.append(position.copy())
        velocities.append(velocity.copy())
        densities.append(density.copy())
        pressures.append(rhs.cs**2 * (density - rhs.rho0))
    arrays = {
        "position_unwrapped": np.stack(positions),
        "position": wrap_positions(np.stack(positions)),
        "velocity": np.stack(velocities),
        "density": np.stack(densities),
        "pressure": np.stack(pressures),
    }
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise FloatingPointError("nonfinite DOP853 output")
    return {
        **arrays,
        "nfev": int(solution.nfev),
        "njev": int(solution.njev),
        "nlu": int(solution.nlu),
        "graph_rebuild_count": rhs.accounting.graph_rebuild_count,
        "source_evaluation_count": rhs.accounting.source_evaluation_count,
        "minimum_density_seen": rhs.accounting.minimum_density_seen,
        "maximum_density_seen": rhs.accounting.maximum_density_seen,
        "rtol": float(rtol),
        "atol": float(atol),
        "maximum_step": maximum_step,
        "integrator": "scipy.integrate.solve_ivp:DOP853",
        "source_identity": "exact_D-R1_material_label_source",
        "semidiscrete_identity": "frozen_continuity_pressure_viscosity_EOS_graph_rebuild",
    }
