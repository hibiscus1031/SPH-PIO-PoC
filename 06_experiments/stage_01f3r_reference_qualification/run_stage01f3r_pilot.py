"""Single preregistered MMS-B RK2 pilot against the qualified dense reference."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

import numpy as np
import torch
import yaml


ROOT = Path(__file__).resolve().parents[2]
SOLVER = ROOT / "01_solver"
sys.path.insert(0, str(SOLVER))
STAGE = ROOT / "06_experiments" / "stage_01f3r_reference_qualification"
CONFIG = STAGE / "configs" / "preregistered_stage01f3r.yml"

from dynamic_solver.acceleration import DynamicPhysicalParameters, force_structure_audit
from dynamic_solver.diagnostics import process_peak_rss_bytes
from dynamic_solver.periodic_rollout import prepare_dynamic_state
from dynamic_solver.sourced_acceleration import initialize_mms_state
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step
from manufactured_solutions.exact_reference import exact_fields
from manufactured_solutions.external_balance import force_balance
from manufactured_solutions.mms_b_dop853_reference import integrate_reference
from manufactured_solutions.torus_position_error import position_error_norms


TOPOLOGY_DEFECTS = (
    "neighbor_duplicate_edge_count", "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count", "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count", "neighbor_unexpected_edge_count",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_rss() -> int:
    output = subprocess.check_output(
        ("/bin/ps", "-o", "rss=", "-p", str(os.getpid())), text=True
    ).strip()
    return int(output) * 1024


def vector_linf(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(left - right, dim=-1).max())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text())
    pilot = config["pilot"]
    frozen_gates = yaml.safe_load(
        (ROOT / "06_experiments/stage_01f2_mms_implementation/configs/preregistered_stage01f2.yml").read_text()
    )["gates"]
    state = initialize_mms_state(
        pilot["solution"], int(pilot["resolution"]),
        support_ratio=float(config["dense_reference"]["support_ratio"]),
    )
    initial_positions = state.positions.clone()
    physics = DynamicPhysicalParameters()
    state, evaluation = prepare_dynamic_state(state, physics)
    steps = int(round(float(pilot["t_final"]) / float(pilot["dt"])))
    assembly_defects: list[float] = []
    momentum_defects: list[float] = []
    internal_residuals: list[float] = []
    pair_residuals: list[float] = []
    topology_defects: list[int] = []
    rss_values: list[int] = []
    step_times: list[float] = []
    with torch.no_grad():
        for _ in range(steps):
            started = time.perf_counter()
            result = explicit_midpoint_sourced_step(
                state, dt=float(pilot["dt"]), parameters=physics,
                solution_id=pilot["solution"], start_evaluation=evaluation,
            )
            step_times.append(time.perf_counter() - started)
            rss_values.append(current_rss())
            for stage_state, stage_evaluation, external in (
                (state, result.start_evaluation, result.start_external_acceleration),
                (result.midpoint_state, result.midpoint_evaluation, result.midpoint_external_acceleration),
                (result.state, result.end_evaluation, result.midpoint_external_acceleration),
            ):
                audit = force_structure_audit(stage_state, stage_evaluation, physics)
                topology_defects.append(sum(int(audit[key]) for key in TOPOLOGY_DEFECTS))
                internal_residuals.append(float(audit["characteristic_normalized_total_internal_force"]))
                pair_residuals.append(max(
                    float(audit["pressure_relative_pair_force_residual"]),
                    float(audit["viscosity_relative_pair_force_residual"]),
                ))
                balance = force_balance(stage_state.masses, stage_evaluation.acceleration, external)
                assembly_defects.append(float(torch.linalg.vector_norm(balance["assembly_defect"])))
            momentum_defects.append(float(torch.linalg.vector_norm(result.momentum_defect)))
            state, evaluation = result.state, result.end_evaluation

    dense = np.load(STAGE / "references/dense_mms_b_three_level.npz")
    count = state.particle_count
    dense_final = dense["baseline"][-1]
    dense_position = torch.from_numpy(dense_final[:2 * count].reshape(count, 2).copy())
    dense_velocity = torch.from_numpy(dense_final[2 * count:].reshape(count, 2).copy())
    exact_position = torch.from_numpy(integrate_reference(
        initial_positions, [0.0, float(pilot["t_final"])],
        rtol=1e-12, atol=1e-14, max_step=3.125e-5,
    )[-1].copy())
    exact_wrapped = torch.remainder(exact_position + 1.0, 2.0) - 1.0
    exact_velocity = exact_fields("MMS_B", exact_wrapped, float(pilot["t_final"]))["velocity"]
    reference_position_error = position_error_norms(state.positions, dense_position)
    exact_position_error = position_error_norms(state.positions, exact_position)
    reference_velocity_linf = vector_linf(state.velocities, dense_velocity)
    exact_velocity_linf = vector_linf(state.velocities, exact_velocity)
    quarter = max(1, len(step_times) // 4)
    rss_first = statistics.median(rss_values[:quarter])
    rss_last = statistics.median(rss_values[-quarter:])
    time_ratio = statistics.median(step_times[-quarter:]) / statistics.median(step_times[:quarter])
    metrics = {
        "reference_position_linf": reference_position_error["Linf"],
        "reference_velocity_linf": reference_velocity_linf,
        "exact_position_linf": exact_position_error["Linf"],
        "exact_velocity_linf": exact_velocity_linf,
        "maximum_force_assembly_defect": max(assembly_defects),
        "maximum_momentum_defect": max(momentum_defects),
        "maximum_internal_force_residual": max(internal_residuals),
        "maximum_pair_force_residual": max(pair_residuals),
        "maximum_topology_defects": max(topology_defects),
        "maximum_current_rss_bytes": max(rss_values),
        "peak_rss_bytes": process_peak_rss_bytes(),
        "rss_quartile_absolute_increase_bytes": rss_last - rss_first,
        "rss_quartile_relative_increase": (rss_last - rss_first) / max(rss_first, 1),
        "step_time_final_first_quartile_ratio": time_ratio,
    }
    checks = {
        "position_velocity_finite": bool(torch.isfinite(state.positions).all() and torch.isfinite(state.velocities).all()),
        "exact_reference_errors_finite": all(math.isfinite(value) for key, value in metrics.items() if "error" in key or "linf" in key),
        "internal_external_balance": metrics["maximum_force_assembly_defect"] <= 1e-12 and metrics["maximum_momentum_defect"] <= frozen_gates["momentum_defect"] and metrics["maximum_internal_force_residual"] <= frozen_gates["internal_force_residual"] and metrics["maximum_pair_force_residual"] <= frozen_gates["pair_force_residual"],
        "topology_structural_audit": metrics["maximum_topology_defects"] == 0,
        "resource_policy": metrics["maximum_current_rss_bytes"] < frozen_gates["current_rss_bytes"] and metrics["peak_rss_bytes"] < frozen_gates["peak_rss_bytes"] and metrics["rss_quartile_absolute_increase_bytes"] <= frozen_gates["rss_quartile_absolute_increase_bytes"] and metrics["rss_quartile_relative_increase"] <= frozen_gates["rss_quartile_relative_increase"] and metrics["step_time_final_first_quartile_ratio"] <= frozen_gates["step_time_final_first_quartile_ratio"],
        "single_preregistered_configuration": steps == 40 and float(pilot["dt"]) == 2.5e-4,
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f3r.pilot.v1",
        "solution": pilot["solution"], "resolution": pilot["resolution"],
        "dt": pilot["dt"], "t_final": pilot["t_final"], "steps": steps,
        "comparison_reference": "dense baseline DOP853 at the final common physical time",
        "position_error_convention": "periodic minimum-image distance",
        "metrics": metrics, "checks": checks,
        "config_sha256": sha(CONFIG),
        "dense_reference_sha256": sha(STAGE / "references/dense_mms_b_three_level.npz"),
        "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip(),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(STAGE / "results/pilot_mms_b_n16.json", payload)
    print(json.dumps({"status": payload["status"]}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
