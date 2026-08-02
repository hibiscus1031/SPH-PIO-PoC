"""Isolated no-grad trajectory worker for Stage 01F3B."""

from __future__ import annotations

import argparse
import csv
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
sys.path.insert(0, str(SOLVER))
STAGE = ROOT / "06_experiments/stage_01f3b_mms_convergence"
CONFIG = STAGE / "configs/preregistered_stage01f3b.yml"

from dynamic_solver.acceleration import DynamicPhysicalParameters, force_structure_audit
from dynamic_solver.diagnostics import process_peak_rss_bytes
from dynamic_solver.periodic_rollout import prepare_dynamic_state
from dynamic_solver.sourced_acceleration import initialize_mms_state
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.field_at_numerical_position_error import field_at_numerical_position_error
from manufactured_solutions.governing_equations import PARAMETERS
from manufactured_solutions.labeled_particle_error import labeled_state_error
from manufactured_solutions.mms_a_reference import unwrapped_trajectory
from manufactured_solutions.mms_b_dop853_reference import integrate_reference
from structure_preserving.neighborhood import tensor_sha256


DEFECT_KEYS = (
    "neighbor_duplicate_edge_count", "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count", "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count", "neighbor_unexpected_edge_count",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip()


def rss() -> int:
    value = subprocess.check_output(("/bin/ps", "-o", "rss=", "-p", str(os.getpid())), text=True).strip()
    return int(value) * 1024


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def flatten(prefix: str, values: dict[str, dict[str, float]]) -> dict[str, float]:
    return {f"{prefix}_{field}_{norm.lower()}": value for field, norms in values.items() for norm, value in norms.items()}


def edge_keys(evaluation: Any) -> set[int]:
    count = evaluation.neighborhood.particle_count
    return set((evaluation.neighborhood.row * count + evaluation.neighborhood.col).tolist())


def edge_identity(evaluation: Any) -> str:
    return tensor_sha256(torch.stack((evaluation.neighborhood.row, evaluation.neighborhood.col)))


def exact_trajectory(solution: str, initial: torch.Tensor, times: list[float]) -> tuple[list[torch.Tensor], float]:
    if solution == "MMS_A":
        return [unwrapped_trajectory(initial, value) for value in times], 0.0
    baseline = integrate_reference(initial, times, rtol=1e-12, atol=1e-14, max_step=3.125e-5)
    tighter = integrate_reference(initial, times, rtol=1e-13, atol=1e-15, max_step=1.5625e-5)
    uncertainty = float(np.max(np.abs(baseline - tighter)))
    return [torch.from_numpy(value.copy()) for value in baseline], uncertainty


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--solution", required=True, choices=("MMS_A", "MMS_B"))
    parser.add_argument("--resolution", required=True, type=int)
    parser.add_argument("--support-ratio", required=True, type=float)
    parser.add_argument("--dt", required=True, type=float)
    parser.add_argument("--t-final", required=True, type=float)
    parser.add_argument("--sample-count", required=True, type=int)
    args = parser.parse_args()
    if not args.run_id.startswith("f3b_"):
        raise ValueError("Stage 01F3B run IDs must start with f3b_")
    if not gc.isenabled():
        raise RuntimeError("default cyclic GC must remain enabled")
    steps = round(args.t_final / args.dt)
    if abs(steps * args.dt - args.t_final) > 1e-14:
        raise ValueError("dt must divide t_final")
    raw_samples = np.linspace(0, steps, args.sample_count)
    sample_steps = np.rint(raw_samples).astype(np.int64)
    if not np.allclose(raw_samples, sample_steps, rtol=0, atol=1e-12):
        raise ValueError("dt is incompatible with the common physical-time grid")
    times = [float(step * args.dt) for step in sample_steps]
    state = initialize_mms_state(args.solution, args.resolution, support_ratio=args.support_ratio)
    initial_positions = state.positions.clone()
    exact_unwrapped, trajectory_uncertainty = exact_trajectory(args.solution, initial_positions, times)
    exact_wrapped = [torch.remainder(value + 1.0, 2.0) - 1.0 for value in exact_unwrapped]
    physics = DynamicPhysicalParameters()
    state, evaluation = prepare_dynamic_state(state, physics)
    numerical_unwrapped = state.positions.clone()
    samples: list[dict[str, Any]] = []
    arrays: dict[str, list[np.ndarray]] = {key: [] for key in ("unwrapped_positions", "positions", "velocities", "densities", "pressures")}
    checkpoint_hashes: list[str] = []
    sample_lookup = {int(step): index for index, step in enumerate(sample_steps)}
    rss_values: list[int] = []
    step_times: list[float] = []
    max_pair = max_internal = max_assembly = max_momentum = max_energy_defect = 0.0
    max_viscous = -math.inf
    min_separation = math.inf
    max_topology = 0
    all_rhs_finite = True
    source_contract = True
    topology_event_count = 0
    reciprocal_events = True
    topology_sequence = hashlib.sha256()
    prior_edges = edge_keys(evaluation)
    previous_energy = float(0.5 * torch.sum(state.masses[:, None] * state.velocities.square()))
    latest_momentum = 0.0
    latest_energy_defect = 0.0

    def sample(step: int, index: int, current_rss: int, peak: int, elapsed: float) -> None:
        module = solution_module(args.solution)
        exact_position = exact_wrapped[index]
        exact_velocity = module.velocity(exact_position, state.time, PARAMETERS)
        exact_density = module.density(exact_position, state.time, PARAMETERS)
        exact_pressure = module.pressure(exact_position, state.time, PARAMETERS)
        labeled = labeled_state_error(
            numerical_positions=state.positions, exact_positions=exact_position,
            numerical_velocity=state.velocities, exact_velocity=exact_velocity,
            numerical_density=evaluation.densities, exact_density=exact_density,
            numerical_pressure=evaluation.pressures, exact_pressure=exact_pressure,
        )
        field = field_at_numerical_position_error(
            args.solution, state.positions, state.time, state.velocities,
            evaluation.densities, evaluation.pressures,
        )
        audit = force_structure_audit(state, evaluation, physics)
        external = evaluate_mms_source(args.solution, state.positions, state.time)
        internal_force = torch.sum(state.masses[:, None] * evaluation.acceleration, dim=0)
        external_force = torch.sum(state.masses[:, None] * external, dim=0)
        total_force = torch.sum(state.masses[:, None] * (evaluation.acceleration + external), dim=0)
        assembly = float(torch.linalg.vector_norm(total_force - internal_force - external_force))
        external_power = float(torch.sum(state.masses[:, None] * state.velocities * external))
        nonself = evaluation.neighborhood.nonself
        periodic_unwrapped_error = numerical_unwrapped - exact_unwrapped[index]
        periodic_unwrapped_error = torch.remainder(periodic_unwrapped_error + 1.0, 2.0) - 1.0
        unwrapped_l2 = float(torch.sqrt(torch.mean(torch.sum(periodic_unwrapped_error.square(), dim=-1))))
        row = {
            "run_id": args.run_id, "role": args.role, "solution": args.solution,
            "resolution": args.resolution, "support_ratio": args.support_ratio,
            "dt": args.dt, "step": step, "time": state.time,
            **flatten("labeled", labeled), **flatten("field", field),
            "unwrapped_periodic_position_l2": unwrapped_l2,
            "pressure_pair_residual": float(audit["pressure_relative_pair_force_residual"]),
            "viscosity_pair_residual": float(audit["viscosity_relative_pair_force_residual"]),
            "normalized_internal_force_residual": float(audit["characteristic_normalized_total_internal_force"]),
            "internal_force_x": float(internal_force[0]), "internal_force_y": float(internal_force[1]),
            "external_force_x": float(external_force[0]), "external_force_y": float(external_force[1]),
            "total_force_x": float(total_force[0]), "total_force_y": float(total_force[1]),
            "assembly_defect": assembly, "momentum_update_defect": latest_momentum,
            "viscous_power": float(audit["viscous_power"]), "external_power": external_power,
            "kinetic_energy_update_defect": latest_energy_defect,
            "edge_count": int(audit["neighbor_edge_count"]), "edge_hash": edge_identity(evaluation),
            "topology_structural_defects": sum(int(audit[key]) for key in DEFECT_KEYS),
            "minimum_separation_over_dx": float(evaluation.neighborhood.distance[nonself].min()) / (2.0 / args.resolution),
            "current_rss_bytes": current_rss, "peak_rss_bytes": peak,
            "step_time_seconds": elapsed,
        }
        samples.append(row)
        arrays["unwrapped_positions"].append(numerical_unwrapped.numpy().copy())
        arrays["positions"].append(state.positions.numpy().copy())
        arrays["velocities"].append(state.velocities.numpy().copy())
        arrays["densities"].append(evaluation.densities.numpy().copy())
        arrays["pressures"].append(evaluation.pressures.numpy().copy())
        checkpoint_hashes.append(row["edge_hash"])

    with torch.no_grad():
        initial_rss = rss()
        sample(0, 0, initial_rss, process_peak_rss_bytes(), 0.0)
        for step in range(1, steps + 1):
            started = time.perf_counter()
            result = explicit_midpoint_sourced_step(
                state, dt=args.dt, parameters=physics, solution_id=args.solution,
                start_evaluation=evaluation,
            )
            elapsed = time.perf_counter() - started
            step_times.append(elapsed)
            rss_values.append(rss())
            source_contract = source_contract and len(result.source_calls) == 2
            source_contract = source_contract and tuple(record.stage for record in result.source_calls) == ("start", "midpoint")
            source_contract = source_contract and abs(result.source_calls[0].physical_time - state.time) <= 1e-14
            source_contract = source_contract and abs(result.source_calls[1].physical_time - (state.time + 0.5 * args.dt)) <= 1e-14
            numerical_unwrapped = numerical_unwrapped + args.dt * result.midpoint_state.velocities
            audit = force_structure_audit(result.midpoint_state, result.midpoint_evaluation, physics)
            pair = max(float(audit["pressure_relative_pair_force_residual"]), float(audit["viscosity_relative_pair_force_residual"]))
            internal = float(audit["characteristic_normalized_total_internal_force"])
            internal_force = torch.sum(result.midpoint_state.masses[:, None] * result.midpoint_evaluation.acceleration, dim=0)
            external_force = torch.sum(result.midpoint_state.masses[:, None] * result.midpoint_external_acceleration, dim=0)
            total_force = torch.sum(result.midpoint_state.masses[:, None] * (result.midpoint_evaluation.acceleration + result.midpoint_external_acceleration), dim=0)
            assembly = float(torch.linalg.vector_norm(total_force - internal_force - external_force))
            latest_momentum = float(torch.linalg.vector_norm(result.momentum_defect))
            energy = float(0.5 * torch.sum(result.state.masses[:, None] * result.state.velocities.square()))
            total_acceleration = result.midpoint_evaluation.acceleration + result.midpoint_external_acceleration
            power = float(torch.sum(result.midpoint_state.masses[:, None] * result.midpoint_state.velocities * total_acceleration))
            latest_energy_defect = abs((energy - previous_energy) - args.dt * power)
            previous_energy = energy
            nonself = result.midpoint_evaluation.neighborhood.nonself
            separation = float(result.midpoint_evaluation.neighborhood.distance[nonself].min()) / (2.0 / args.resolution)
            topology = sum(int(audit[key]) for key in DEFECT_KEYS)
            all_rhs_finite = all_rhs_finite and bool(torch.isfinite(total_acceleration).all())
            max_pair = max(max_pair, pair); max_internal = max(max_internal, internal)
            max_assembly = max(max_assembly, assembly); max_momentum = max(max_momentum, latest_momentum)
            max_energy_defect = max(max_energy_defect, latest_energy_defect)
            max_viscous = max(max_viscous, float(audit["viscous_power"]))
            min_separation = min(min_separation, separation); max_topology = max(max_topology, topology)
            state, evaluation = result.state, result.end_evaluation
            current_edges = edge_keys(evaluation)
            changed = prior_edges.symmetric_difference(current_edges)
            if changed:
                count = state.particle_count
                reciprocal = all(((key % count) * count + (key // count)) in changed for key in changed)
                reciprocal_events = reciprocal_events and reciprocal
                topology_event_count += len(changed) // 2
                topology_sequence.update(f"{step}:".encode())
                topology_sequence.update(np.asarray(sorted(changed), dtype=np.int64).tobytes())
            prior_edges = current_edges
            if step in sample_lookup:
                sample(step, sample_lookup[step], rss_values[-1], process_peak_rss_bytes(), elapsed)

    sample_path = STAGE / "trajectory_samples" / f"{args.run_id}.csv"
    state_path = STAGE / "trajectory_states" / f"{args.run_id}.npz"
    write_csv(sample_path, samples)
    np.savez_compressed(
        state_path, times=np.asarray(times),
        unwrapped_positions=np.stack(arrays["unwrapped_positions"]),
        positions=np.stack(arrays["positions"]), velocities=np.stack(arrays["velocities"]),
        densities=np.stack(arrays["densities"]), pressures=np.stack(arrays["pressures"]),
        masses=state.masses.numpy(), edge_hashes=np.asarray(checkpoint_hashes),
    )
    quarter = max(1, len(step_times) // 4)
    rss_first = statistics.median(rss_values[:quarter]); rss_last = statistics.median(rss_values[-quarter:])
    time_ratio = statistics.median(step_times[-quarter:]) / max(statistics.median(step_times[:quarter]), 1e-30)
    gates = yaml.safe_load(CONFIG.read_text())["hard_gates"]
    checks = {
        "state_and_rhs_finite": all_rhs_finite and all(math.isfinite(float(value)) for row in samples for value in row.values() if isinstance(value, (float, int))),
        "source_two_calls_per_step": source_contract,
        "pair_force": max_pair <= gates["pair_force_residual"],
        "internal_force": max_internal <= gates["internal_force_residual"],
        "assembly": max_assembly <= gates["assembly_defect"],
        "momentum": max_momentum <= gates["momentum_update_defect"],
        "viscous_power": max_viscous <= gates["viscous_power_positive_tolerance"],
        "topology_structural": max_topology == gates["topology_defects"],
        "topology_switches_reciprocal": reciprocal_events,
        "minimum_separation": min_separation >= gates["minimum_separation_over_dx"],
        "cyclic_gc_enabled": gc.isenabled(),
        "current_rss": max(rss_values) < gates["current_rss_bytes"],
        "peak_rss": process_peak_rss_bytes() < gates["peak_rss_bytes"],
        "rss_quartile_absolute": rss_last - rss_first <= gates["rss_quartile_absolute_increase_bytes"],
        "rss_quartile_relative": (rss_last - rss_first) / max(rss_first, 1) <= gates["rss_quartile_relative_increase"],
        "step_time_q4_q1": time_ratio <= gates["step_time_q4_q1"],
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f3b.trajectory.v1",
        "run_id": args.run_id, "role": args.role, "solution": args.solution,
        "resolution": args.resolution, "support_ratio": args.support_ratio,
        "dt": args.dt, "steps": steps, "t_final": args.t_final,
        "sample_count": args.sample_count, "checks": checks,
        "maximum_pair_force_residual": max_pair,
        "maximum_internal_force_residual": max_internal,
        "maximum_assembly_defect": max_assembly,
        "maximum_momentum_update_defect": max_momentum,
        "maximum_kinetic_energy_update_defect": max_energy_defect,
        "maximum_viscous_power": max_viscous,
        "minimum_separation_over_dx": min_separation,
        "maximum_topology_structural_defects": max_topology,
        "dynamic_topology_event_count": topology_event_count,
        "topology_event_sequence_sha256": topology_sequence.hexdigest(),
        "unique_checkpoint_edge_identities": len(set(checkpoint_hashes)),
        "trajectory_reference_sensitivity_upper_bound": trajectory_uncertainty,
        "maximum_current_rss_bytes": max(rss_values),
        "peak_rss_bytes": process_peak_rss_bytes(),
        "rss_quartile_absolute_increase_bytes": rss_last - rss_first,
        "rss_quartile_relative_increase": (rss_last - rss_first) / max(rss_first, 1),
        "step_time_q4_q1": time_ratio,
        "wall_time_seconds": sum(step_times),
        "initial_metrics": samples[0], "final_metrics": samples[-1],
        "trajectory_path": state_path.relative_to(ROOT).as_posix(), "trajectory_sha256": sha(state_path),
        "samples_path": sample_path.relative_to(ROOT).as_posix(), "samples_sha256": sha(sample_path),
        "code_git_hash": git_hash(), "config_sha256": sha(CONFIG),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(STAGE / "run_summaries" / f"{args.run_id}.json", payload)
    print(json.dumps({"status": payload["status"], "run_id": args.run_id}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
