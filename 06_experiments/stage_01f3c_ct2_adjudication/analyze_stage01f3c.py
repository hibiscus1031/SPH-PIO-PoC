"""Vector-level CT2 decomposition and held-out analysis for Stage 01F3C."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
import yaml


ROOT = Path(__file__).resolve().parents[2]
SOLVER = ROOT / "01_solver"
sys.path.insert(0, str(SOLVER))
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"
F3B = ROOT / "06_experiments/stage_01f3b_mms_convergence"
CONFIG = STAGE / "configs/preregistered_stage01f3c.yml"

from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from manufactured_solutions.exact_fields import solution_module  # noqa: E402
from manufactured_solutions.governing_equations import PARAMETERS  # noqa: E402
from manufactured_solutions.mms_a_reference import unwrapped_trajectory  # noqa: E402
from manufactured_solutions.mms_b_dop853_reference import integrate_reference  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, payload: dict[str, Any]) -> None:
    path = STAGE / "results" / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def dt_code(value: float) -> str:
    return f"{value:.8f}".split(".")[1].rstrip("0")


def vector_rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(value * value, axis=-1))))


def squared_norm(value: np.ndarray) -> float:
    return float(np.mean(np.sum(value * value, axis=-1)))


def cross_term(left: np.ndarray, right: np.ndarray) -> float:
    return float(2.0 * np.mean(np.sum(left * right, axis=-1)))


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    numerator = float(np.mean(np.sum(left * right, axis=-1)))
    denominator = math.sqrt(squared_norm(left) * squared_norm(right))
    return numerator / max(denominator, 1.0e-300)


def fitted_order(dt: list[float], error: list[float]) -> float:
    return float(np.polyfit(np.log(np.asarray(dt)), np.log(np.asarray(error)), 1)[0])


def strictly_decreasing(values: list[float]) -> bool:
    return all(values[index + 1] < values[index] for index in range(len(values) - 1))


def exact_velocities(
    solution: str, resolution: int, support_ratio: float, times: np.ndarray
) -> np.ndarray:
    initial = initialize_mms_state(solution, resolution, support_ratio=support_ratio)
    if solution == "MMS_A":
        exact_unwrapped = [unwrapped_trajectory(initial.positions, float(t)) for t in times]
    else:
        values = integrate_reference(
            initial.positions,
            times,
            rtol=1.0e-13,
            atol=1.0e-15,
            max_step=7.8125e-6,
        )
        exact_unwrapped = [torch.from_numpy(value.copy()) for value in values]
    module = solution_module(solution)
    velocities = []
    for time_value, position in zip(times, exact_unwrapped):
        wrapped = torch.remainder(position + 1.0, 2.0) - 1.0
        velocities.append(
            module.velocity(wrapped, float(time_value), PARAMETERS).numpy().copy()
        )
    return np.stack(velocities)


def metric_block(
    total: np.ndarray, space: np.ndarray, temporal: np.ndarray
) -> dict[str, float]:
    closure = total - space - temporal
    total_sq = squared_norm(total)
    space_sq = squared_norm(space)
    temporal_sq = squared_norm(temporal)
    cross = cross_term(space, temporal)
    reconstructed = space_sq + temporal_sq + cross
    scale = max(
        float(np.max(np.abs(total))),
        float(np.max(np.abs(space))),
        float(np.max(np.abs(temporal))),
        1.0e-300,
    )
    return {
        "total_l2": vector_rms(total),
        "space_l2": vector_rms(space),
        "temporal_l2": vector_rms(temporal),
        "cross_term_2_space_dot_temporal": cross,
        "cosine_space_temporal": cosine(space, temporal),
        "total_squared_norm": total_sq,
        "reconstructed_squared_norm": reconstructed,
        "squared_norm_reconstruction_absolute_residual": abs(total_sq - reconstructed),
        "maximum_absolute_vector_closure": float(np.max(np.abs(closure))),
        "maximum_relative_vector_closure": float(np.max(np.abs(closure))) / scale,
    }


def analyze_dataset(
    label: str,
    block: dict[str, Any],
    reference_id: str,
    trajectory_ids: list[str],
    solution: str,
    frozen: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    reference_path = STAGE / "references" / f"{reference_id}.npz"
    with np.load(reference_path) as reference:
        times = reference["times"].copy()
        count = int(reference["particle_count"])
        semidiscrete = reference["baseline"][:, 2 * count :].reshape(
            len(times), count, 2
        )
    exact = exact_velocities(
        solution, block["resolution"], block["support_ratio"], times
    )
    space = semidiscrete - exact
    rows = []
    vector_payload: dict[str, np.ndarray] = {
        "times": times,
        "exact_velocity": exact,
        "semidiscrete_velocity": semidiscrete,
        "e_space": space,
    }
    for dt, run_id in zip(block["dt"], trajectory_ids):
        if frozen:
            trajectory_path = F3B / "trajectory_states" / f"{run_id}.npz"
        else:
            trajectory_path = STAGE / "results" / f"{run_id}_trajectory.npz"
        with np.load(trajectory_path) as trajectory:
            numerical_times = trajectory["times"].copy()
            numerical = trajectory["velocities"].copy()
        if not np.array_equal(numerical_times, times):
            raise ValueError(f"time-grid mismatch for {run_id}")
        total = numerical - exact
        temporal = numerical - semidiscrete
        endpoint = metric_block(total[-1:], space[-1:], temporal[-1:])
        integrated = metric_block(total, space, temporal)
        rows.append(
            {
                "dt": dt,
                "run_id": run_id,
                "trajectory_path": trajectory_path.relative_to(ROOT).as_posix(),
                "trajectory_sha256": sha(trajectory_path),
                "endpoint": endpoint,
                "integrated_rms": integrated,
            }
        )
        code = dt_code(dt)
        vector_payload[f"e_total_{code}"] = total
        vector_payload[f"e_time_{code}"] = temporal
    vector_path = STAGE / "results" / f"{label}_{solution.lower()}_vectors.npz"
    if vector_path.exists():
        raise RuntimeError(f"refusing to overwrite {vector_path.relative_to(ROOT)}")
    np.savez_compressed(vector_path, **vector_payload)
    gates = config["decomposition_gates"]
    temporal_endpoint = [row["endpoint"]["temporal_l2"] for row in rows]
    temporal_integrated = [row["integrated_rms"]["temporal_l2"] for row in rows]
    endpoint_order = fitted_order(block["dt"], temporal_endpoint)
    integrated_order = fitted_order(block["dt"], temporal_integrated)
    max_closure_absolute = max(
        row[scope]["maximum_absolute_vector_closure"]
        for row in rows
        for scope in ("endpoint", "integrated_rms")
    )
    max_closure_relative = max(
        row[scope]["maximum_relative_vector_closure"]
        for row in rows
        for scope in ("endpoint", "integrated_rms")
    )
    coarse = rows[0]
    finest = rows[-1]
    endpoint_platform_distance = abs(
        finest["endpoint"]["total_l2"] - finest["endpoint"]["space_l2"]
    ) / max(finest["endpoint"]["space_l2"], 1.0e-300)
    total_endpoint = [row["endpoint"]["total_l2"] for row in rows]
    space_endpoint = [row["endpoint"]["space_l2"] for row in rows]
    below_platform = all(total < space_value for total, space_value in zip(total_endpoint, space_endpoint))
    platform_gap = [
        abs(total - space_value) for total, space_value in zip(total_endpoint, space_endpoint)
    ]
    checks = {
        "reference_status_pass": json.loads(
            (STAGE / "run_summaries" / f"{reference_id}.json").read_text()
        )["status"]
        == "PASS",
        "vector_closure_absolute": max_closure_absolute
        <= gates["closure_absolute"],
        "vector_closure_relative": max_closure_relative
        <= gates["closure_relative"],
        "temporal_endpoint_monotone": strictly_decreasing(temporal_endpoint),
        "temporal_integrated_monotone": strictly_decreasing(temporal_integrated),
        "temporal_endpoint_order": endpoint_order >= gates["temporal_fitted_order"],
        "temporal_integrated_order": integrated_order
        >= gates["temporal_fitted_order"],
        "coarse_negative_cross_endpoint": coarse["endpoint"][
            "cross_term_2_space_dot_temporal"
        ]
        < 0.0,
        "coarse_negative_cross_integrated": coarse["integrated_rms"][
            "cross_term_2_space_dot_temporal"
        ]
        < 0.0,
        "coarse_cross_explains_below_platform": coarse["endpoint"][
            "cross_term_2_space_dot_temporal"
        ]
        < 0.0
        and coarse["endpoint"]["total_squared_norm"]
        < coarse["endpoint"]["space_l2"] ** 2,
        "approaches_platform_from_below": below_platform
        and strictly_decreasing(platform_gap),
        "finest_platform_distance": endpoint_platform_distance
        <= gates["finest_platform_relative_distance"],
    }
    return {
        "solution": solution,
        "dataset": label,
        "resolution": block["resolution"],
        "support_ratio": block["support_ratio"],
        "t_final": block["t_final"],
        "sample_count": block["sample_count"],
        "rows": rows,
        "temporal_endpoint_errors": temporal_endpoint,
        "temporal_integrated_errors": temporal_integrated,
        "temporal_endpoint_fitted_order": endpoint_order,
        "temporal_integrated_fitted_order": integrated_order,
        "finest_endpoint_platform_relative_distance": endpoint_platform_distance,
        "maximum_absolute_vector_closure": max_closure_absolute,
        "maximum_relative_vector_closure": max_closure_relative,
        "checks": checks,
        "vector_evidence_path": vector_path.relative_to(ROOT).as_posix(),
        "vector_evidence_sha256": sha(vector_path),
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def self_difference_identity() -> dict[str, Any]:
    historical = json.loads(
        (F3B / "results/continuous_time_analysis.json").read_text()
    )
    cases = []
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        rows = historical["solutions"][solution]["rows"]
        for index in range(len(rows) - 1):
            with np.load(F3B / "trajectory_states" / f"{rows[index]['run_id']}.npz") as left:
                left_positions = left["positions"].copy()
                left_velocities = left["velocities"].copy()
            with np.load(F3B / "trajectory_states" / f"{rows[index + 1]['run_id']}.npz") as right:
                right_positions = right["positions"].copy()
                right_velocities = right["velocities"].copy()
            position_difference = np.remainder(
                left_positions - right_positions + 1.0, 2.0
            ) - 1.0
            recomputed_position = vector_rms(position_difference)
            recomputed_velocity = vector_rms(left_velocities - right_velocities)
            stored_position = rows[index]["position_successive_self_difference"]
            stored_velocity = rows[index]["velocity_successive_self_difference"]
            cases.append(
                {
                    "solution": solution,
                    "coarse_run": rows[index]["run_id"],
                    "fine_run": rows[index + 1]["run_id"],
                    "position_recomputed": recomputed_position,
                    "position_stored": stored_position,
                    "position_absolute_difference": abs(recomputed_position - stored_position),
                    "velocity_recomputed": recomputed_velocity,
                    "velocity_stored": stored_velocity,
                    "velocity_absolute_difference": abs(recomputed_velocity - stored_velocity),
                }
            )
    maximum = max(
        max(case["position_absolute_difference"], case["velocity_absolute_difference"])
        for case in cases
    )
    return {"cases": cases, "maximum_absolute_difference": maximum, "status": "PASS" if maximum <= 1.0e-15 else "FAIL"}


def resource_and_determinism(config: dict[str, Any]) -> dict[str, Any]:
    summaries = [
        json.loads(path.read_text())
        for path in sorted((STAGE / "run_summaries").glob("f3c_*.json"))
    ]
    with (STAGE / "results/campaign_index.csv").open() as stream:
        campaign = list(csv.DictReader(stream))
    deterministic_cases = []
    scalar_keys = (
        "maximum_pair_force_residual",
        "maximum_internal_force_residual",
        "maximum_assembly_defect",
        "maximum_momentum_update_defect",
        "maximum_kinetic_energy_update_defect",
        "maximum_viscous_power",
        "minimum_separation_over_dx",
        "maximum_topology_structural_defects",
        "dynamic_topology_event_count",
        "topology_event_sequence_sha256",
        "unique_checkpoint_edge_identities",
    )
    repeat_dt = config["heldout"]["deterministic_repeat_dt"]
    for letter in ("a", "b"):
        primary = f"f3c_ho_{letter}_{dt_code(repeat_dt)}"
        repeat = f"f3c_ho_repeat_{letter}_{dt_code(repeat_dt)}"
        a = json.loads((STAGE / "run_summaries" / f"{primary}.json").read_text())
        b = json.loads((STAGE / "run_summaries" / f"{repeat}.json").read_text())
        with np.load(ROOT / a["trajectory_path"]) as left, np.load(
            ROOT / b["trajectory_path"]
        ) as right:
            arrays_equal = all(
                np.array_equal(left[key], right[key])
                for key in (
                    "times",
                    "positions",
                    "velocities",
                    "densities",
                    "pressures",
                    "masses",
                    "edge_hashes",
                )
            )
        scalars_equal = all(a[key] == b[key] for key in scalar_keys)
        case_pass = arrays_equal and scalars_equal
        deterministic_cases.append(
            {
                "primary": primary,
                "repeat": repeat,
                "trajectory_bitwise_identity": arrays_equal,
                "audit_scalar_identity": scalars_equal,
                "status": "PASS" if case_pass else "FAIL",
            }
        )
    heldout_summaries = [item for item in summaries if item["run_id"].startswith("f3c_ho_")]
    reference_summaries = [item for item in summaries if item["run_id"].startswith("f3c_ref_")]
    checks = {
        "all_heldout_workers_pass": len(heldout_summaries) == 12
        and all(item["status"] == "PASS" for item in heldout_summaries),
        "all_references_pass": len(reference_summaries) == 4
        and all(item["status"] == "PASS" for item in reference_summaries),
        "all_children_reclaimed": len(campaign) == 16
        and all(row["child_reclaimed"] == "True" for row in campaign),
        "all_parent_scalar_only": len(campaign) == 16
        and all(row["parent_scalar_only"] == "True" for row in campaign),
        "determinism": all(case["status"] == "PASS" for case in deterministic_cases),
    }
    maxima_keys = (
        "maximum_pair_force_residual",
        "maximum_internal_force_residual",
        "maximum_assembly_defect",
        "maximum_momentum_update_defect",
        "maximum_kinetic_energy_update_defect",
        "maximum_viscous_power",
        "maximum_current_rss_bytes",
        "peak_rss_bytes",
        "rss_quartile_absolute_increase_bytes",
        "rss_quartile_relative_increase",
        "step_time_q4_q1",
    )
    maxima = {
        key: max(float(item[key]) for item in heldout_summaries) for key in maxima_keys
    }
    return {
        "trajectory_count": len(heldout_summaries),
        "reference_count": len(reference_summaries),
        "determinism_cases": deterministic_cases,
        "maxima": maxima,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=("n32", "heldout", "audit", "all"), required=True
    )
    args = parser.parse_args()
    config = yaml.safe_load(CONFIG.read_text())
    if args.phase in ("n32", "all"):
        solutions = {}
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            trajectories = [f"f3b_ct_{letter}_{dt_code(dt)}" for dt in config["n32"]["dt"]]
            solutions[solution] = analyze_dataset(
                "n32",
                config["n32"],
                f"f3c_ref_n32_{letter}",
                trajectories,
                solution,
                True,
                config,
            )
        identity = self_difference_identity()
        payload = {
            "schema_version": "sph-pio-poc.stage01f3c.n32-decomposition.v1",
            "solutions": solutions,
            "stage01f3b_self_difference_identity": identity,
            "status": "PASS"
            if identity["status"] == "PASS"
            and all(value["status"] == "PASS" for value in solutions.values())
            else "FAIL",
        }
        write_json("n32_error_decomposition.json", payload)
    if args.phase in ("heldout", "all"):
        solutions = {}
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            trajectories = [f"f3c_ho_{letter}_{dt_code(dt)}" for dt in config["heldout"]["dt"]]
            solutions[solution] = analyze_dataset(
                "heldout",
                config["heldout"],
                f"f3c_ref_heldout_{letter}",
                trajectories,
                solution,
                False,
                config,
            )
        payload = {
            "schema_version": "sph-pio-poc.stage01f3c.heldout-decomposition.v1",
            "common_time_grid": "11 noninterpolated times forced by held-out coarse dt",
            "solutions": solutions,
            "status": "PASS"
            if all(value["status"] == "PASS" for value in solutions.values())
            else "FAIL",
        }
        write_json("heldout_error_decomposition.json", payload)
    if args.phase in ("audit", "all"):
        write_json("resource_determinism_audit.json", resource_and_determinism(config))
    print(json.dumps({"phase": args.phase, "status": "COMPLETE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
