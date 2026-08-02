"""Isolated no-grad RK2 held-out trajectory worker for Stage 01F3C."""

from __future__ import annotations

import argparse
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
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"
CONFIG = STAGE / "configs/preregistered_stage01f3c.yml"

from dynamic_solver.acceleration import (  # noqa: E402
    DynamicPhysicalParameters,
    force_structure_audit,
)
from dynamic_solver.diagnostics import process_peak_rss_bytes  # noqa: E402
from dynamic_solver.periodic_rollout import prepare_dynamic_state  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import (  # noqa: E402
    explicit_midpoint_sourced_step,
)


DEFECT_KEYS = (
    "neighbor_duplicate_edge_count",
    "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count",
    "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count",
    "neighbor_unexpected_edge_count",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_hash() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, text=True
    ).strip()


def current_rss() -> int:
    value = subprocess.check_output(
        ("/bin/ps", "-o", "rss=", "-p", str(os.getpid())), text=True
    ).strip()
    return int(value) * 1024


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def edge_set(evaluation: Any) -> set[int]:
    count = evaluation.neighborhood.particle_count
    return set(
        (evaluation.neighborhood.row * count + evaluation.neighborhood.col).tolist()
    )


def edge_hash(edges: set[int]) -> str:
    return hashlib.sha256(np.asarray(sorted(edges), dtype=np.int64).tobytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--solution", choices=("MMS_A", "MMS_B"), required=True)
    parser.add_argument("--resolution", type=int, required=True)
    parser.add_argument("--support-ratio", type=float, required=True)
    parser.add_argument("--dt", type=float, required=True)
    parser.add_argument("--t-final", type=float, required=True)
    parser.add_argument("--sample-count", type=int, required=True)
    args = parser.parse_args()
    if not args.run_id.startswith("f3c_ho_"):
        raise ValueError("Stage 01F3C held-out IDs must start with f3c_ho_")
    if not gc.isenabled():
        raise RuntimeError("default cyclic GC must remain enabled")
    steps = round(args.t_final / args.dt)
    if abs(steps * args.dt - args.t_final) > 1.0e-14:
        raise ValueError("dt must divide t_final")
    raw_sample_steps = np.linspace(0, steps, args.sample_count)
    sample_steps = np.rint(raw_sample_steps).astype(np.int64)
    if not np.allclose(raw_sample_steps, sample_steps, rtol=0.0, atol=1.0e-12):
        raise ValueError("dt is incompatible with the common physical-time grid")
    times = np.asarray([float(step * args.dt) for step in sample_steps])
    sample_lookup = {int(step): index for index, step in enumerate(sample_steps)}
    state = initialize_mms_state(
        args.solution, args.resolution, support_ratio=args.support_ratio
    )
    physics = DynamicPhysicalParameters()
    state, evaluation = prepare_dynamic_state(state, physics)
    arrays: dict[str, list[np.ndarray]] = {
        key: [] for key in ("positions", "velocities", "densities", "pressures")
    }
    checkpoint_edges: list[str] = []
    rss_values: list[int] = []
    step_times: list[float] = []
    max_pair = max_internal = max_assembly = max_momentum = max_energy_defect = 0.0
    max_viscous = -math.inf
    min_separation = math.inf
    max_topology = 0
    all_finite = True
    source_contract = True
    reciprocal_events = True
    topology_event_count = 0
    topology_sequence = hashlib.sha256()
    previous_edges = edge_set(evaluation)
    previous_energy = float(
        0.5 * torch.sum(state.masses[:, None] * state.velocities.square())
    )

    def sample() -> None:
        arrays["positions"].append(state.positions.numpy().copy())
        arrays["velocities"].append(state.velocities.numpy().copy())
        arrays["densities"].append(evaluation.densities.numpy().copy())
        arrays["pressures"].append(evaluation.pressures.numpy().copy())
        checkpoint_edges.append(edge_hash(edge_set(evaluation)))

    with torch.no_grad():
        sample()
        for step in range(1, steps + 1):
            started = time.perf_counter()
            result = explicit_midpoint_sourced_step(
                state,
                dt=args.dt,
                parameters=physics,
                solution_id=args.solution,
                start_evaluation=evaluation,
            )
            elapsed = time.perf_counter() - started
            step_times.append(elapsed)
            rss_values.append(current_rss())
            source_contract = source_contract and len(result.source_calls) == 2
            source_contract = source_contract and tuple(
                record.stage for record in result.source_calls
            ) == ("start", "midpoint")
            source_contract = source_contract and abs(
                result.source_calls[0].physical_time - state.time
            ) <= 1.0e-14
            source_contract = source_contract and abs(
                result.source_calls[1].physical_time - (state.time + 0.5 * args.dt)
            ) <= 1.0e-14
            audit = force_structure_audit(
                result.midpoint_state, result.midpoint_evaluation, physics
            )
            pair = max(
                float(audit["pressure_relative_pair_force_residual"]),
                float(audit["viscosity_relative_pair_force_residual"]),
            )
            internal = float(audit["characteristic_normalized_total_internal_force"])
            internal_force = torch.sum(
                result.midpoint_state.masses[:, None]
                * result.midpoint_evaluation.acceleration,
                dim=0,
            )
            external_force = torch.sum(
                result.midpoint_state.masses[:, None]
                * result.midpoint_external_acceleration,
                dim=0,
            )
            total_force = torch.sum(
                result.midpoint_state.masses[:, None]
                * (
                    result.midpoint_evaluation.acceleration
                    + result.midpoint_external_acceleration
                ),
                dim=0,
            )
            assembly = float(
                torch.linalg.vector_norm(total_force - internal_force - external_force)
            )
            momentum = float(torch.linalg.vector_norm(result.momentum_defect))
            energy = float(
                0.5
                * torch.sum(result.state.masses[:, None] * result.state.velocities.square())
            )
            total_acceleration = (
                result.midpoint_evaluation.acceleration
                + result.midpoint_external_acceleration
            )
            power = float(
                torch.sum(
                    result.midpoint_state.masses[:, None]
                    * result.midpoint_state.velocities
                    * total_acceleration
                )
            )
            energy_defect = abs((energy - previous_energy) - args.dt * power)
            previous_energy = energy
            nonself = result.midpoint_evaluation.neighborhood.nonself
            separation = float(
                result.midpoint_evaluation.neighborhood.distance[nonself].min()
            ) / (2.0 / args.resolution)
            topology = sum(int(audit[key]) for key in DEFECT_KEYS)
            all_finite = all_finite and bool(torch.isfinite(total_acceleration).all())
            max_pair = max(max_pair, pair)
            max_internal = max(max_internal, internal)
            max_assembly = max(max_assembly, assembly)
            max_momentum = max(max_momentum, momentum)
            max_energy_defect = max(max_energy_defect, energy_defect)
            max_viscous = max(max_viscous, float(audit["viscous_power"]))
            min_separation = min(min_separation, separation)
            max_topology = max(max_topology, topology)
            state, evaluation = result.state, result.end_evaluation
            current_edges = edge_set(evaluation)
            changed = previous_edges.symmetric_difference(current_edges)
            if changed:
                count = state.particle_count
                reciprocal_events = reciprocal_events and all(
                    ((key % count) * count + (key // count)) in changed for key in changed
                )
                topology_event_count += len(changed) // 2
                topology_sequence.update(f"{step}:".encode())
                topology_sequence.update(
                    np.asarray(sorted(changed), dtype=np.int64).tobytes()
                )
            previous_edges = current_edges
            if step in sample_lookup:
                sample()
    trajectory_path = STAGE / "results" / f"{args.run_id}_trajectory.npz"
    if trajectory_path.exists():
        raise RuntimeError(f"refusing to overwrite {trajectory_path.relative_to(ROOT)}")
    np.savez_compressed(
        trajectory_path,
        times=times,
        positions=np.stack(arrays["positions"]),
        velocities=np.stack(arrays["velocities"]),
        densities=np.stack(arrays["densities"]),
        pressures=np.stack(arrays["pressures"]),
        masses=state.masses.numpy(),
        edge_hashes=np.asarray(checkpoint_edges),
    )
    quarter = max(1, len(step_times) // 4)
    rss_first = statistics.median(rss_values[:quarter])
    rss_last = statistics.median(rss_values[-quarter:])
    time_ratio = statistics.median(step_times[-quarter:]) / max(
        statistics.median(step_times[:quarter]), 1.0e-30
    )
    gates = yaml.safe_load(CONFIG.read_text())["hard_gates"]
    checks = {
        "state_and_rhs_finite": all_finite
        and all(np.isfinite(np.stack(values)).all() for values in arrays.values()),
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
        "rss_quartile_absolute": rss_last - rss_first
        <= gates["rss_quartile_absolute_increase_bytes"],
        "rss_quartile_relative": (rss_last - rss_first) / max(rss_first, 1)
        <= gates["rss_quartile_relative_increase"],
        "step_time_q4_q1": time_ratio <= gates["step_time_q4_q1"],
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f3c.heldout-trajectory.v1",
        "run_id": args.run_id,
        "role": args.role,
        "solution": args.solution,
        "resolution": args.resolution,
        "support_ratio": args.support_ratio,
        "dt": args.dt,
        "steps": steps,
        "t_final": args.t_final,
        "sample_count": args.sample_count,
        "checks": checks,
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
        "unique_checkpoint_edge_identities": len(set(checkpoint_edges)),
        "maximum_current_rss_bytes": max(rss_values),
        "peak_rss_bytes": process_peak_rss_bytes(),
        "rss_quartile_absolute_increase_bytes": rss_last - rss_first,
        "rss_quartile_relative_increase": (rss_last - rss_first) / max(rss_first, 1),
        "step_time_q4_q1": time_ratio,
        "wall_time_seconds": sum(step_times),
        "trajectory_path": trajectory_path.relative_to(ROOT).as_posix(),
        "trajectory_sha256": sha(trajectory_path),
        "code_git_hash": git_hash(),
        "config_sha256": sha(CONFIG),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(STAGE / "run_summaries" / f"{args.run_id}.json", payload)
    print(json.dumps({"run_id": args.run_id, "status": payload["status"]}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
