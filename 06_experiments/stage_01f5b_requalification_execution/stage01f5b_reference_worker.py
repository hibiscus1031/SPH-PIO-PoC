"""One-level isolated production-sparse DOP853 worker for Stage 01F5B."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
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
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
CONFIG = STAGE / "configs/stage01f5b_execution.yml"

from dynamic_solver.acceleration import (  # noqa: E402
    DynamicPhysicalParameters,
    evaluate_internal_acceleration,
    force_structure_audit,
)
from dynamic_solver.diagnostics import process_peak_rss_bytes  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from dynamic_solver.state import DynamicSPHState  # noqa: E402
from manufactured_solutions.dense_all_pairs_rhs import evaluate_dense_all_pairs  # noqa: E402
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source  # noqa: E402
from manufactured_solutions.mms_b_dop853_reference import parameter_hash  # noqa: E402
from manufactured_solutions.semidiscrete_reference import (  # noqa: E402
    SemidiscreteReference,
    integrate_semidiscrete_dop853,
)
from structure_preserving.neighborhood import wrap_periodic  # noqa: E402


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
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def state_from_vector(value: np.ndarray, time_value: float, initial: DynamicSPHState) -> tuple[DynamicSPHState, torch.Tensor, torch.Tensor]:
    count = initial.particle_count
    unwrapped = torch.from_numpy(value[: 2 * count].reshape(count, 2))
    velocity = torch.from_numpy(value[2 * count :].reshape(count, 2))
    state = DynamicSPHState(
        positions=wrap_periodic(unwrapped, initial.domain_min, initial.domain_max),
        velocities=velocity,
        masses=initial.masses,
        densities=torch.ones_like(initial.densities),
        pressures=torch.zeros_like(initial.pressures),
        supports=initial.supports,
        domain_min=initial.domain_min,
        domain_max=initial.domain_max,
        time=float(time_value),
    )
    return state, unwrapped, velocity


def edge_set(evaluation: Any) -> set[int]:
    count = evaluation.neighborhood.particle_count
    return set((evaluation.neighborhood.row * count + evaluation.neighborhood.col).tolist())


def integrate_path(solution: str, initial: DynamicSPHState, times: np.ndarray, settings: dict[str, float]) -> tuple[SemidiscreteReference, dict[str, Any]]:
    count = initial.particle_count
    physics = DynamicPhysicalParameters()
    y0 = np.concatenate((initial.positions.numpy().reshape(-1), initial.velocities.numpy().reshape(-1)))
    edge_counts: set[int] = set()
    edge_hashes: set[str] = set()
    maximum_defects = 0
    switching_transitions = 0
    reciprocal_switching = True
    previous_edges: set[int] | None = None
    rhs_calls = 0

    def rhs(time_value: float, value: np.ndarray) -> np.ndarray:
        nonlocal maximum_defects, switching_transitions, reciprocal_switching, previous_edges, rhs_calls
        state, _, velocity = state_from_vector(value, time_value, initial)
        with torch.no_grad():
            evaluation = evaluate_internal_acceleration(state, physics)
            source = evaluate_mms_source(solution, state.positions, time_value)
            audit = force_structure_audit(state, evaluation, physics)
        maximum_defects = max(maximum_defects, sum(int(audit[key]) for key in DEFECT_KEYS))
        edges = edge_set(evaluation)
        edge_counts.add(len(edges))
        edge_hashes.add(hashlib.sha256(np.asarray(sorted(edges), dtype=np.int64).tobytes()).hexdigest())
        if previous_edges is not None:
            changed = previous_edges.symmetric_difference(edges)
            if changed:
                switching_transitions += 1
                reciprocal_switching = reciprocal_switching and all(((key % count) * count + (key // count)) in changed for key in changed)
        previous_edges = edges
        rhs_calls += 1
        return np.concatenate((velocity.numpy().reshape(-1), (evaluation.acceleration + source).numpy().reshape(-1)))

    reference = integrate_semidiscrete_dop853(rhs, y0, times, **settings)
    return reference, {
        "rhs_calls": rhs_calls,
        "unique_edge_counts": sorted(edge_counts),
        "unique_edge_identity_count": len(edge_hashes),
        "switching_transition_count": switching_transitions,
        "maximum_structural_defects": maximum_defects,
        "reciprocal_switching": reciprocal_switching,
    }


def sparse_dense_audit(solution: str, initial: DynamicSPHState, reference: SemidiscreteReference, sample_count: int) -> dict[str, Any]:
    physics = DynamicPhysicalParameters()
    indices = np.unique(np.rint(np.linspace(0, len(reference.times) - 1, sample_count)).astype(int))
    rows = []
    for index in indices:
        state, _, velocity = state_from_vector(reference.states[index], float(reference.times[index]), initial)
        with torch.no_grad():
            sparse = evaluate_internal_acceleration(state, physics)
            source = evaluate_mms_source(solution, state.positions, float(reference.times[index]))
            dense = evaluate_dense_all_pairs(solution, state.positions, velocity, state.masses, state.supports, float(reference.times[index]))
        difference = sparse.acceleration + source - dense.total_acceleration
        rows.append({
            "sample_index": int(index),
            "time": float(reference.times[index]),
            "absolute": float(torch.max(torch.abs(difference))),
            "relative": float(torch.linalg.vector_norm(difference) / max(float(torch.linalg.vector_norm(dense.total_acceleration)), 1.0e-30)),
        })
    return {
        "sample_count": len(rows),
        "samples": rows,
        "maximum_absolute_difference": max(row["absolute"] for row in rows),
        "maximum_relative_difference": max(row["relative"] for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--solution", choices=("MMS_A", "MMS_B"), required=True)
    parser.add_argument("--resolution", type=int, required=True)
    parser.add_argument("--support-ratio", type=float, required=True)
    parser.add_argument("--t-final", type=float, required=True)
    parser.add_argument("--sample-count", type=int, required=True)
    parser.add_argument("--level", choices=("baseline", "tighter", "third"), required=True)
    args = parser.parse_args()
    if not args.run_id.startswith("f5_ref_"):
        raise ValueError("Stage 01F5B reference IDs must start with f5_ref_")
    if not gc.isenabled():
        raise RuntimeError("default cyclic GC must remain enabled")
    config = yaml.safe_load(CONFIG.read_text())
    times = np.linspace(0.0, args.t_final, args.sample_count, dtype=np.float64)
    initial = initialize_mms_state(args.solution, args.resolution, support_ratio=args.support_ratio)
    started = time.perf_counter()
    reference, topology = integrate_path(args.solution, initial, times, config["reference_levels"][args.level])
    sparse_dense = sparse_dense_audit(args.solution, initial, reference, config["reference_gates"]["minimum_sparse_dense_states"])
    output = STAGE / "references" / f"{args.run_id}.npz"
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output.relative_to(ROOT)}")
    np.savez_compressed(output, times=times, states=reference.states, particle_count=initial.particle_count, level=np.asarray(args.level))
    gates = config["reference_gates"]
    checks = {
        "all_states_finite": bool(np.isfinite(reference.states).all()),
        "topology_structural": topology["maximum_structural_defects"] == gates["structural_topology_defects"],
        "topology_switching_reciprocal": topology["reciprocal_switching"],
        "sparse_dense_sample_count": sparse_dense["sample_count"] >= gates["minimum_sparse_dense_states"],
        "sparse_dense_absolute": sparse_dense["maximum_absolute_difference"] <= gates["sparse_dense_acceleration_absolute_maximum"],
        "sparse_dense_relative": sparse_dense["maximum_relative_difference"] <= gates["sparse_dense_acceleration_relative_maximum"],
        "cyclic_gc_enabled": gc.isenabled(),
        "peak_rss": process_peak_rss_bytes() < config["hard_gates"]["peak_rss_bytes"],
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f5b.reference-run.v1",
        "run_id": args.run_id,
        "solution": args.solution,
        "resolution": args.resolution,
        "support_ratio": args.support_ratio,
        "t_final": args.t_final,
        "sample_count": args.sample_count,
        "reference_level": args.level,
        "integrator": "scipy.integrate.solve_ivp:DOP853",
        "statistics": {"nfev": reference.nfev, "njev": reference.njev, "nlu": reference.nlu, "rtol": reference.rtol, "atol": reference.atol, "max_step": reference.max_step},
        "topology": topology,
        "sparse_dense_audit": sparse_dense,
        "checks": checks,
        "parameter_sha256": parameter_hash(),
        "code_git_hash": git_hash(),
        "config_sha256": sha(CONFIG),
        "reference_path": output.relative_to(ROOT).as_posix(),
        "reference_sha256": sha(output),
        "peak_rss_bytes": process_peak_rss_bytes(),
        "wall_time_seconds": time.perf_counter() - started,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(STAGE / "runs" / args.run_id / "summary.json", payload)
    print(json.dumps({"run_id": args.run_id, "status": payload["status"]}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
