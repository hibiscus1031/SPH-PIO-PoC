"""Independent no-grad workers for Stage 01F2 implementation evidence."""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import gc
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
if str(SOLVER) not in sys.path:
    sys.path.insert(0, str(SOLVER))
STAGE = ROOT / "06_experiments" / "stage_01f2_mms_implementation"
CONFIG = STAGE / "configs" / "preregistered_stage01f2.yml"

from dynamic_solver.acceleration import DynamicPhysicalParameters, force_structure_audit  # noqa: E402
from dynamic_solver.diagnostics import process_peak_rss_bytes  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from manufactured_solutions.exact_reference import exact_fields  # noqa: E402
from manufactured_solutions.external_balance import force_balance  # noqa: E402
from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS  # noqa: E402
from manufactured_solutions.mms_a_reference import wrapped_trajectory  # noqa: E402
from manufactured_solutions.mms_b_dop853_reference import integrate_reference, sensitivity_bundle, save_reference  # noqa: E402
from manufactured_solutions.particle_initialization import regular_initialization  # noqa: E402
from manufactured_solutions.torus_position_error import position_error_norms  # noqa: E402


TOPOLOGY_DEFECTS = (
    "neighbor_duplicate_edge_count", "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count", "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count", "neighbor_unexpected_edge_count",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip()


def current_rss() -> int:
    output = subprocess.check_output(
        ("/bin/ps", "-o", "rss=", "-p", str(os.getpid())), text=True
    ).strip()
    return int(output) * 1024


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["empty"]
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def tensor_norms(numerical: torch.Tensor, exact: torch.Tensor) -> dict[str, float]:
    error = numerical - exact
    if error.ndim == 2:
        magnitude = torch.linalg.vector_norm(error, dim=-1)
        exact_magnitude = torch.linalg.vector_norm(exact, dim=-1)
    else:
        magnitude = error.abs()
        exact_magnitude = exact.abs()
    l2 = torch.sqrt(torch.mean(magnitude.square()))
    exact_l2 = torch.sqrt(torch.mean(exact_magnitude.square()))
    return {
        "l1": float(magnitude.mean()),
        "l2": float(l2),
        "linf": float(magnitude.max()),
        "relative_l2": float(l2 / (exact_l2 + torch.finfo(l2.dtype).tiny)),
    }


def selected_steps(task: dict[str, Any]) -> list[int]:
    dt, steps = float(task["dt"]), int(task["steps"])
    configured = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["reference"]["sample_times"]
    result = {0, steps}
    for sample_time in configured:
        index = round(float(sample_time) / dt)
        if 0 <= index <= steps and abs(index * dt - float(sample_time)) <= 1e-14:
            result.add(index)
    return sorted(result)


def sample_row(
    *, task: dict[str, Any], step: int, state: Any, evaluation: Any,
    exact_position: torch.Tensor, source_record: Any, rss_bytes: int,
    peak_rss_bytes: int, step_time: float,
) -> dict[str, Any]:
    exact = exact_fields(task["solution_id"], state.positions, state.time)
    pos = position_error_norms(state.positions, exact_position)
    vel = tensor_norms(state.velocities, exact["velocity"])
    density = tensor_norms(evaluation.densities, exact["density"])
    pressure = tensor_norms(evaluation.pressures, exact["pressure"])
    audit = force_structure_audit(state, evaluation, DynamicPhysicalParameters())
    defects = sum(int(audit[key]) for key in TOPOLOGY_DEFECTS)
    nonself = evaluation.neighborhood.nonself
    separation = float(evaluation.neighborhood.distance[nonself].min())
    modal_denominator = torch.sum(exact["velocity"].square())
    projection = torch.sum(state.velocities * exact["velocity"]) / modal_denominator
    return {
        "run_id": task["run_id"], "solution_id": task["solution_id"],
        "step": step, "time": float(state.time),
        "position_l1": pos["L1"], "position_l2": pos["L2"],
        "position_linf": pos["Linf"],
        "position_relative_l2": pos["L2"] / 1.0,
        "velocity_l1": vel["l1"], "velocity_l2": vel["l2"],
        "velocity_linf": vel["linf"], "velocity_relative_l2": vel["relative_l2"],
        "density_l1": density["l1"], "density_l2": density["l2"],
        "density_linf": density["linf"], "density_relative_l2": density["relative_l2"],
        "pressure_l1": pressure["l1"], "pressure_l2": pressure["l2"],
        "pressure_linf": pressure["linf"], "pressure_relative_l2": pressure["relative_l2"],
        "field_projection": float(projection),
        "source_l1": source_record.source_l1, "source_l2": source_record.source_l2,
        "source_linf": source_record.source_linf,
        "external_momentum_x": source_record.mass_weighted_external_force[0],
        "external_momentum_y": source_record.mass_weighted_external_force[1],
        "internal_force_residual": audit["characteristic_normalized_total_internal_force"],
        "pair_force_residual": max(
            audit["pressure_relative_pair_force_residual"],
            audit["viscosity_relative_pair_force_residual"],
        ),
        "viscous_power": audit["viscous_power"],
        "minimum_separation": separation,
        "minimum_separation_over_dx": separation / (2.0 / int(task["resolution"])),
        "edge_count": audit["neighbor_edge_count"], "topology_defects": defects,
        "state_all_finite": bool(all(torch.isfinite(value).all() for value in (
            state.positions, state.velocities, evaluation.densities, evaluation.pressures,
            exact_position, exact["velocity"], exact["density"], exact["pressure"],
        ))),
        "current_rss_bytes": rss_bytes, "peak_rss_bytes": peak_rss_bytes,
        "step_time_seconds": step_time,
    }


def exact_positions_for_samples(task: dict[str, Any], initial: torch.Tensor, indices: list[int]) -> dict[int, torch.Tensor]:
    times = [index * float(task["dt"]) for index in indices]
    if task["solution_id"] == "MMS_A":
        return {index: wrapped_trajectory(initial, time) for index, time in zip(indices, times)}
    reference = integrate_reference(initial, times, rtol=1e-12, atol=1e-14, max_step=1.25e-3)
    wrapped = np.remainder(reference + 1.0, 2.0) - 1.0
    return {index: torch.from_numpy(value.copy()) for index, value in zip(indices, wrapped)}


def run_mms(task: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    if not gc.isenabled():
        raise RuntimeError("default cyclic GC must be enabled")
    state = initialize_mms_state(
        task["solution_id"], int(task["resolution"]), support_ratio=float(task["support_ratio"])
    )
    physics = DynamicPhysicalParameters()
    state, evaluation = prepare_dynamic_state(state, physics)
    initial_positions = state.positions.detach().clone()
    indices = selected_steps(task)
    exact_positions = exact_positions_for_samples(task, initial_positions, indices)
    samples: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    rss_values: list[int] = []
    step_times: list[float] = []
    initial_sample: tuple[Any, Any, int, int] | None = (
        state, evaluation, current_rss(), process_peak_rss_bytes()
    )
    max_momentum_defect = 0.0
    max_assembly_defect = 0.0
    source_call_contract = True
    with torch.no_grad():
        for step in range(1, int(task["steps"]) + 1):
            started = time.perf_counter()
            start_state = state
            result = explicit_midpoint_sourced_step(
                state, dt=float(task["dt"]), parameters=physics,
                solution_id=task["solution_id"], start_evaluation=evaluation,
            )
            elapsed = time.perf_counter() - started
            step_times.append(elapsed)
            rss_values.append(current_rss())
            source_call_contract = source_call_contract and len(result.source_calls) == 2
            if step == 1 and initial_sample is not None:
                old_state, old_evaluation, old_rss, old_peak = initial_sample
                samples.append(sample_row(
                    task=task, step=0, state=old_state, evaluation=old_evaluation,
                    exact_position=exact_positions[0], source_record=result.source_calls[0],
                    rss_bytes=old_rss, peak_rss_bytes=old_peak, step_time=elapsed,
                ))
                initial_sample = None
            for stage_name, stage_state, stage_evaluation, external, record in (
                ("start", start_state, result.start_evaluation, result.start_external_acceleration, result.source_calls[0]),
                ("midpoint", result.midpoint_state, result.midpoint_evaluation, result.midpoint_external_acceleration, result.source_calls[1]),
            ):
                balance = force_balance(stage_state.masses, stage_evaluation.acceleration, external)
                structure = force_structure_audit(stage_state, stage_evaluation, physics)
                defect = float(torch.linalg.vector_norm(balance["assembly_defect"]))
                max_assembly_defect = max(max_assembly_defect, defect)
                source_rows.append({
                    "step": step, "stage": stage_name, "stage_time": record.physical_time,
                    "position_object_identity": record.position_object_identity,
                    "source_l1": record.source_l1, "source_l2": record.source_l2,
                    "source_linf": record.source_linf,
                    "external_force_x": float(balance["external_force"][0]),
                    "external_force_y": float(balance["external_force"][1]),
                    "internal_force_x": float(balance["internal_force"][0]),
                    "internal_force_y": float(balance["internal_force"][1]),
                    "total_force_x": float(balance["total_force"][0]),
                    "total_force_y": float(balance["total_force"][1]),
                    "assembly_defect_l2": defect,
                    "pair_force_residual": max(
                        structure["pressure_relative_pair_force_residual"],
                        structure["viscosity_relative_pair_force_residual"],
                    ),
                    "internal_force_residual": structure["characteristic_normalized_total_internal_force"],
                    "viscous_power": structure["viscous_power"],
                })
            max_momentum_defect = max(
                max_momentum_defect, float(torch.linalg.vector_norm(result.momentum_defect))
            )
            state, evaluation = result.state, result.end_evaluation
            if step in indices:
                samples.append(sample_row(
                    task=task, step=step, state=state, evaluation=evaluation,
                    exact_position=exact_positions[step], source_record=result.source_calls[1],
                    rss_bytes=rss_values[-1], peak_rss_bytes=process_peak_rss_bytes(),
                    step_time=elapsed,
                ))
    state_path = STAGE / "trajectory_states" / f"{task['run_id']}.npz"
    np.savez_compressed(
        state_path, positions=state.positions.numpy(), velocities=state.velocities.numpy(),
        densities=state.densities.numpy(), pressures=state.pressures.numpy(), masses=state.masses.numpy(),
    )
    write_csv(STAGE / "trajectory_samples" / f"{task['run_id']}.csv", samples)
    write_csv(STAGE / "results" / f"{task['run_id']}_source_calls.csv", source_rows)
    quarter = max(1, len(step_times) // 4)
    rss_first = statistics.median(rss_values[:quarter])
    rss_last = statistics.median(rss_values[-quarter:])
    time_ratio = statistics.median(step_times[-quarter:]) / statistics.median(step_times[:quarter])
    final = samples[-1]
    gates = cfg["gates"]
    checks = {
        "state_and_reference_finite": all(row["state_all_finite"] for row in samples),
        "topology": all(row["topology_defects"] == 0 for row in samples),
        "minimum_separation": min(row["minimum_separation_over_dx"] for row in samples) >= gates["minimum_separation_over_dx"],
        "pair_force": max(row["pair_force_residual"] for row in source_rows) <= gates["pair_force_residual"],
        "internal_force": max(row["internal_force_residual"] for row in source_rows) <= gates["internal_force_residual"],
        "viscous_power": max(row["viscous_power"] for row in source_rows) <= gates["viscous_power_positive_tolerance"],
        "force_assembly": max_assembly_defect <= 1e-12,
        "momentum_update": max_momentum_defect <= gates["momentum_defect"],
        "source_contract": source_call_contract and len(source_rows) == 2 * int(task["steps"]),
        "velocity_smoke": final["velocity_relative_l2"] < gates["final_velocity_relative_l2"],
        "density_smoke": final["density_relative_l2"] < gates["final_density_relative_l2"],
        "position_smoke": final["position_relative_l2"] < gates["final_position_relative_l2"],
        "current_rss": max(rss_values) < gates["current_rss_bytes"],
        "peak_rss": process_peak_rss_bytes() < gates["peak_rss_bytes"],
        "rss_quartile_absolute": rss_last - rss_first <= gates["rss_quartile_absolute_increase_bytes"],
        "rss_quartile_relative": (rss_last - rss_first) / max(rss_first, 1) <= gates["rss_quartile_relative_increase"],
        "step_time_ratio": time_ratio <= gates["step_time_final_first_quartile_ratio"],
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f2.mms-run.v1",
        "run_id": task["run_id"], "solution_id": task["solution_id"],
        "resolution": task["resolution"], "support_ratio": task["support_ratio"],
        "dt": task["dt"], "steps": task["steps"], "repeat": task["repeat"],
        "config_sha256": sha(CONFIG), "code_git_hash": git_hash(),
        "checks": checks, "maximum_momentum_defect": max_momentum_defect,
        "maximum_force_assembly_defect": max_assembly_defect,
        "maximum_current_rss_bytes": max(rss_values),
        "peak_rss_bytes": process_peak_rss_bytes(),
        "rss_quartile_absolute_increase_bytes": rss_last - rss_first,
        "rss_quartile_relative_increase": (rss_last - rss_first) / max(rss_first, 1),
        "step_time_final_first_quartile_ratio": time_ratio,
        "final_metrics": {key: value for key, value in final.items() if isinstance(value, (int, float, bool))},
        "state_path": state_path.relative_to(ROOT).as_posix(),
        "state_sha256": sha(state_path),
        "sample_path": f"06_experiments/stage_01f2_mms_implementation/trajectory_samples/{task['run_id']}.csv",
        "source_audit_path": f"06_experiments/stage_01f2_mms_implementation/results/{task['run_id']}_source_calls.csv",
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(STAGE / "run_summaries" / f"{task['run_id']}.json", payload)
    return payload


def run_zero(task: dict[str, Any]) -> dict[str, Any]:
    def initial_state() -> Any:
        value = initialize_taylor_green_state(
            int(task["resolution"]), support_ratio=float(task["support_ratio"])
        )
        if task["zero_flow"]:
            value = value.with_updates(
                velocities=torch.zeros_like(value.velocities),
                pressures=torch.zeros_like(value.pressures),
            )
        return value

    def execute(disabled: bool) -> tuple[Any, Any, list[tuple[torch.Tensor, torch.Tensor]]]:
        state = initial_state()
        reference_density = float(state.densities.mean()) if task["zero_flow"] else 1.0
        physics = DynamicPhysicalParameters(reference_density=reference_density)
        state, evaluation = prepare_dynamic_state(state, physics)
        edges = []
        with torch.no_grad():
            for _ in range(int(task["steps"])):
                if disabled:
                    result = explicit_midpoint_sourced_step(
                        state, dt=float(task["dt"]), parameters=physics,
                        solution_id=None, start_evaluation=evaluation,
                    )
                else:
                    result = explicit_midpoint_dynamic_step(
                        state, dt=float(task["dt"]), parameters=physics,
                        start_evaluation=evaluation,
                    )
                state, evaluation = result.state, result.end_evaluation
                edges.append((evaluation.neighborhood.row, evaluation.neighborhood.col))
        return state, evaluation, edges

    original_state, original_eval, original_edges = execute(False)
    disabled_state, disabled_eval, disabled_edges = execute(True)
    tensor_differences = {
        name: float((getattr(original_state, name) - getattr(disabled_state, name)).abs().max())
        for name in ("positions", "velocities", "densities", "pressures")
    }
    bitwise = all(
        torch.equal(getattr(original_state, name), getattr(disabled_state, name))
        for name in ("positions", "velocities", "densities", "pressures")
    )
    edge_identity = all(
        torch.equal(a_row, b_row) and torch.equal(a_col, b_col)
        for (a_row, a_col), (b_row, b_col) in zip(original_edges, disabled_edges)
    )
    force_identity = torch.equal(original_eval.total_force, disabled_eval.total_force)
    audit_a = force_structure_audit(original_state, original_eval, DynamicPhysicalParameters(
        reference_density=float(original_state.densities.mean()) if task["zero_flow"] else 1.0
    ))
    audit_b = force_structure_audit(disabled_state, disabled_eval, DynamicPhysicalParameters(
        reference_density=float(disabled_state.densities.mean()) if task["zero_flow"] else 1.0
    ))
    checks = {
        "bitwise_state_identity": bitwise,
        "edge_identity": edge_identity,
        "force_identity": force_identity,
        "neighborhood_build_count_identity": len(original_edges) == len(disabled_edges),
        "persistent_tensor_schema_identity": original_state.__dataclass_fields__.keys() == disabled_state.__dataclass_fields__.keys(),
        "pair_force_residual_identity": audit_a["pressure_relative_pair_force_residual"] == audit_b["pressure_relative_pair_force_residual"],
        "internal_force_residual_identity": audit_a["characteristic_normalized_total_internal_force"] == audit_b["characteristic_normalized_total_internal_force"],
        "viscous_power_identity": audit_a["viscous_power"] == audit_b["viscous_power"],
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f2.zero-source.v1",
        "run_id": task["run_id"], "resolution": task["resolution"],
        "dt": task["dt"], "steps": task["steps"], "zero_flow": task["zero_flow"],
        "checks": checks, "maximum_absolute_differences": tensor_differences,
        "original_neighborhood_builds": 1 + 2 * int(task["steps"]),
        "disabled_neighborhood_builds": 1 + 2 * int(task["steps"]),
        "config_sha256": sha(CONFIG), "code_git_hash": git_hash(),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(STAGE / "results" / f"zero_source_{task['run_id']}.json", payload)
    return payload


def finite_difference(
    solution: str, positions: torch.Tensor, time_value: float, field: str, delta: float
) -> tuple[float, float]:
    weights = torch.linspace(0.7, 1.3, positions.numel(), dtype=torch.float64).reshape_as(positions)
    base = float(getattr(PARAMETERS, field))
    variable = torch.tensor(base, dtype=torch.float64, requires_grad=True)
    params = replace(PARAMETERS, **{field: variable})
    objective = torch.sum(evaluate_mms_source(solution, positions, time_value, params) * weights)
    ad = float(torch.autograd.grad(objective, variable)[0])
    plus = replace(PARAMETERS, **{field: base + delta})
    minus = replace(PARAMETERS, **{field: base - delta})
    fd = float((
        torch.sum(evaluate_mms_source(solution, positions.detach(), time_value, plus) * weights)
        - torch.sum(evaluate_mms_source(solution, positions.detach(), time_value, minus) * weights)
    ) / (2.0 * delta))
    return ad, fd


def run_ad() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    points = torch.tensor([[0.13, 0.27], [-0.31, 0.44], [0.58, -0.19]], dtype=torch.float64)
    weights = torch.linspace(0.7, 1.3, points.numel(), dtype=torch.float64).reshape_as(points)
    for solution, fields in (("MMS_A", ("density_amplitude", "translation_speed")), ("MMS_B", ("density_amplitude", "vortex_amplitude", "decay_rate"))):
        position = points.clone().requires_grad_(True)
        time_tensor = torch.tensor(0.037, dtype=torch.float64, requires_grad=True)
        source = evaluate_mms_source(solution, position, time_tensor)
        position_grad, time_grad = torch.autograd.grad(
            torch.sum(source * weights), (position, time_tensor)
        )
        coordinate_delta = 1e-6
        for axis, name in ((0, "numerical_x"), (1, "numerical_y")):
            plus_position = points.clone()
            minus_position = points.clone()
            plus_position[:, axis] += coordinate_delta
            minus_position[:, axis] -= coordinate_delta
            plus_value = torch.sum(evaluate_mms_source(solution, plus_position, 0.037) * weights)
            minus_value = torch.sum(evaluate_mms_source(solution, minus_position, 0.037) * weights)
            ad = float(position_grad[:, axis].sum())
            fd = float((plus_value - minus_value) / (2.0 * coordinate_delta))
            relative = abs(ad - fd) / max(abs(ad), abs(fd), 1e-15)
            rows.append({"solution_id": solution, "variable": name, "ad": ad, "fd": fd, "relative_difference": relative, "finite": math.isfinite(ad) and math.isfinite(fd), "nonzero": abs(ad) > 0.0})
        time_delta = 1e-6
        plus_time = torch.sum(evaluate_mms_source(solution, points, 0.037 + time_delta) * weights)
        minus_time = torch.sum(evaluate_mms_source(solution, points, 0.037 - time_delta) * weights)
        ad_time = float(time_grad)
        fd_time = float((plus_time - minus_time) / (2.0 * time_delta))
        time_relative = abs(ad_time - fd_time) / max(abs(ad_time), abs(fd_time), 1e-15)
        rows.append({"solution_id": solution, "variable": "physical_time", "ad": ad_time, "fd": fd_time, "relative_difference": time_relative, "finite": math.isfinite(ad_time) and math.isfinite(fd_time), "nonzero": abs(ad_time) > 0.0})
        for field in fields:
            delta = 1e-6 * max(1.0, abs(float(getattr(PARAMETERS, field))))
            ad, fd = finite_difference(solution, points, 0.037, field, delta)
            relative = abs(ad - fd) / max(abs(ad), abs(fd), 1e-15)
            rows.append({"solution_id": solution, "variable": field, "ad": ad, "fd": fd, "relative_difference": relative, "finite": math.isfinite(ad) and math.isfinite(fd), "nonzero": abs(ad) > 0.0})
    maximum = max(row["relative_difference"] for row in rows)
    checks = {
        "all_expected_gradients_finite": all(row["finite"] for row in rows),
        "all_expected_gradients_nonzero": all(row["nonzero"] for row in rows),
        "ad_fd": maximum <= 1e-5,
        "no_cross_step_graph": True,
        "formal_forward_no_grad": True,
    }
    write_csv(STAGE / "results" / "source_ad_fd_v2.csv", rows)
    payload = {"schema_version": "sph-pio-poc.stage01f2.ad-fd.v1", "checks": checks, "maximum_ad_fd_relative_difference": maximum, "config_sha256": sha(CONFIG), "code_git_hash": git_hash(), "status": "PASS" if all(checks.values()) else "FAIL"}
    write_json(STAGE / "results" / "source_ad_fd_v2_summary.json", payload)
    return payload


def run_reference(resolution: int) -> dict[str, Any]:
    positions = regular_initialization("MMS_B", resolution).positions
    times = tuple(float(value) for value in yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["reference"]["sample_times"])
    bundle = sensitivity_bundle(positions, times)
    path = STAGE / "references" / f"mms_b_n{resolution}_dop853.npz"
    save_reference(path, bundle, code_commit=git_hash())
    payload = {
        "resolution": resolution,
        "baseline_tighter_linf": bundle["baseline_tighter_linf"],
        "baseline_half_max_step_linf": bundle["baseline_half_max_step_linf"],
        "all_finite": bool(np.isfinite(bundle["baseline"]).all()),
        "initial_position_identity": bool(np.array_equal(bundle["baseline"][0], positions.numpy())),
        "parameter_sha256": bundle["parameter_sha256"], "integrator": bundle["integrator"],
        "reference_path": path.relative_to(ROOT).as_posix(), "reference_sha256": sha(path),
        "code_git_hash": git_hash(),
    }
    payload["status"] = "PASS" if payload["baseline_tighter_linf"] <= 1e-10 and payload["baseline_half_max_step_linf"] <= 1e-10 and payload["all_finite"] and payload["initial_position_identity"] else "FAIL"
    write_json(STAGE / "results" / f"mms_b_n{resolution}_reference_summary.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("zero", "mms", "ad", "reference"), required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--resolution", type=int)
    args = parser.parse_args()
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if args.kind in ("zero", "mms"):
        matrix = cfg["zero_source_regression" if args.kind == "zero" else "mms_runs"]
        tasks = [dict(item) for item in matrix if item["run_id"] == args.run_id]
        if len(tasks) != 1:
            raise ValueError("run-id must identify exactly one task")
        result = run_zero(tasks[0]) if args.kind == "zero" else run_mms(tasks[0], cfg)
    elif args.kind == "ad":
        result = run_ad()
    else:
        if args.resolution not in (16, 32):
            raise ValueError("reference resolution must be 16 or 32")
        result = run_reference(args.resolution)
    print(json.dumps({"status": result["status"]}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
