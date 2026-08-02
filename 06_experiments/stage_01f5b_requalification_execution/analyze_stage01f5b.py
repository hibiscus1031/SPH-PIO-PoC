"""Scalar/vector postprocessing for the frozen Stage 01F5B campaign.

This module never advances an SPH state and never calls the project RK2 integrator.
"""

from __future__ import annotations

import argparse
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
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
CONFIG = STAGE / "configs/stage01f5b_execution.yml"

from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from manufactured_solutions.exact_fields import solution_module  # noqa: E402
from manufactured_solutions.governing_equations import PARAMETERS  # noqa: E402
from manufactured_solutions.mms_a_reference import unwrapped_trajectory  # noqa: E402
from manufactured_solutions.mms_b_dop853_reference import integrate_reference  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def vector_rms(value: np.ndarray) -> float:
    if value.ndim >= 2 and value.shape[-1] == 2:
        return float(np.sqrt(np.mean(np.sum(value * value, axis=-1))))
    return float(np.sqrt(np.mean(value * value)))


def squared_norm(value: np.ndarray) -> float:
    if value.ndim >= 2 and value.shape[-1] == 2:
        return float(np.mean(np.sum(value * value, axis=-1)))
    return float(np.mean(value * value))


def metric(total: np.ndarray, space: np.ndarray, temporal: np.ndarray) -> dict[str, float | str]:
    total_sq = squared_norm(total)
    space_sq = squared_norm(space)
    time_sq = squared_norm(temporal)
    if total.shape[-1:] == (2,):
        dot = float(np.mean(np.sum(space * temporal, axis=-1)))
    else:
        dot = float(np.mean(space * temporal))
    cross = 2.0 * dot
    denominator = math.sqrt(max(space_sq * time_sq, 0.0))
    total_l2, space_l2, time_l2 = vector_rms(total), vector_rms(space), vector_rms(temporal)
    return {
        "total_l2": total_l2,
        "space_l2": space_l2,
        "time_l2": time_l2,
        "cross_term": cross,
        "cosine": dot / max(denominator, 1.0e-300),
        "total_squared_norm": total_sq,
        "reconstructed_squared_norm": space_sq + time_sq + cross,
        "reconstruction_absolute_residual": abs(total_sq - space_sq - time_sq - cross),
        "platform_approach": "above" if total_l2 > space_l2 else "below" if total_l2 < space_l2 else "equal",
    }


def fitted_order(dt: list[float], errors: list[float]) -> float:
    return float(np.polyfit(np.log(dt), np.log(errors), 1)[0])


def local_orders(errors: list[float]) -> list[float]:
    return [float(math.log(errors[i] / errors[i + 1], 2.0)) for i in range(len(errors) - 1)]


def strictly_decreasing(values: list[float]) -> bool:
    return all(values[i + 1] < values[i] for i in range(len(values) - 1))


def exact_fields(solution: str, resolution: int, support_ratio: float, times: np.ndarray) -> dict[str, np.ndarray]:
    initial = initialize_mms_state(solution, resolution, support_ratio=support_ratio)
    if solution == "MMS_A":
        unwrapped = np.stack([unwrapped_trajectory(initial.positions, float(t)).numpy() for t in times])
    else:
        unwrapped = integrate_reference(initial.positions, times, rtol=1.0e-13, atol=1.0e-15, max_step=7.8125e-6)
    module = solution_module(solution)
    velocity, density, pressure = [], [], []
    for time_value, position in zip(times, unwrapped):
        wrapped = torch.from_numpy(np.remainder(position + 1.0, 2.0) - 1.0)
        velocity.append(module.velocity(wrapped, float(time_value), PARAMETERS).numpy())
        density.append(module.density(wrapped, float(time_value), PARAMETERS).numpy())
        pressure.append(module.pressure(wrapped, float(time_value), PARAMETERS).numpy())
    return {"position": unwrapped, "velocity": np.stack(velocity), "density": np.stack(density), "pressure": np.stack(pressure)}


def checkpoint(run_id: str) -> dict[str, np.ndarray]:
    with np.load(STAGE / "checkpoints" / f"{run_id}.npz") as data:
        return {key: data[key].copy() for key in data.files}


def summary(run_id: str) -> dict[str, Any]:
    return json.loads((STAGE / "runs" / run_id / "summary.json").read_text())


def reference(run_id: str) -> tuple[np.ndarray, np.ndarray, int]:
    with np.load(STAGE / "references" / f"{run_id}.npz") as data:
        return data["times"].copy(), data["states"].copy(), int(data["particle_count"])


def reference_triplet(prefix: str) -> dict[str, Any]:
    levels = {}
    for level in ("baseline", "tighter", "third"):
        run_id = f"{prefix}_{level}"
        times, states, count = reference(run_id)
        levels[level] = states
    blocks = {}
    for field, cut in (("position", slice(None, 2 * count)), ("velocity", slice(2 * count, None))):
        bt = (levels["baseline"][:, cut] - levels["tighter"][:, cut]).reshape(len(times), count, 2)
        tt = (levels["tighter"][:, cut] - levels["third"][:, cut]).reshape(len(times), count, 2)
        blocks[field] = {
            "baseline_tighter_endpoint": vector_rms(bt[-1:]),
            "baseline_tighter_integrated": vector_rms(bt),
            "tighter_third_endpoint": vector_rms(tt[-1:]),
            "tighter_third_integrated": vector_rms(tt),
            "uncertainty_endpoint": max(vector_rms(bt[-1:]), vector_rms(tt[-1:])),
            "uncertainty_integrated": max(vector_rms(bt), vector_rms(tt)),
            "linf": max(float(np.max(np.abs(bt))), float(np.max(np.abs(tt)))),
        }
    run_checks = [summary(f"{prefix}_{level}")["status"] == "PASS" for level in ("baseline", "tighter", "third")]
    gates = yaml.safe_load(CONFIG.read_text())["reference_gates"]
    checks = {
        "three_runs_pass": all(run_checks),
        "position_sensitivity": blocks["position"]["linf"] <= gates["position_linf_sensitivity_maximum"],
        "velocity_sensitivity": blocks["velocity"]["linf"] <= gates["velocity_linf_sensitivity_maximum"],
    }
    return {"prefix": prefix, "fields": blocks, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def qualify_references() -> dict[str, Any]:
    prefixes = ["f5_ref_main_a", "f5_ref_main_b", "f5_ref_hold_a", "f5_ref_hold_b"]
    prefixes += [f"f5_ref_space_b_n{n}" for n in (16, 24, 32, 48) if (STAGE / "references" / f"f5_ref_space_b_n{n}_baseline.npz").exists()]
    if (STAGE / "references/f5_ref_space_b_n64_baseline.npz").exists():
        prefixes.append("f5_ref_space_b_n64")
    items = {prefix: reference_triplet(prefix) for prefix in prefixes}
    payload = {"schema_version": "sph-pio-poc.stage01f5b.reference-qualification.v1", "items": items, "status": "PASS" if all(x["status"] == "PASS" for x in items.values()) else "FAIL"}
    write_once(STAGE / "results/reference_qualification.json", payload)
    return payload


def time_case(label: str, solution: str, run_ids: list[str], reference_prefix: str) -> dict[str, Any]:
    ref_times, semistates, count = reference(f"{reference_prefix}_baseline")
    semidiscrete = {"position": semistates[:, : 2 * count].reshape(len(ref_times), count, 2), "velocity": semistates[:, 2 * count :].reshape(len(ref_times), count, 2)}
    first = summary(run_ids[0])
    exact = exact_fields(solution, first["resolution"], first["support_ratio"], ref_times)
    uncertainty = reference_triplet(reference_prefix)["fields"]
    dts, rows = [], []
    for run_id in run_ids:
        data = checkpoint(run_id)
        if not np.array_equal(data["times"], ref_times):
            raise ValueError(f"time grid mismatch: {run_id}")
        dts.append(summary(run_id)["dt"])
        fields = {}
        for field, key in (("position", "unwrapped_positions"), ("velocity", "velocities")):
            numerical = data[key]
            total = numerical - exact[field]
            space = semidiscrete[field] - exact[field]
            temporal = numerical - semidiscrete[field]
            fields[field] = {"endpoint": metric(total[-1:], space[-1:], temporal[-1:]), "integrated": metric(total, space, temporal)}
        rows.append({"run_id": run_id, "dt": dts[-1], "fields": fields})
    combinations = {}
    for field in ("position", "velocity"):
        for norm in ("endpoint", "integrated"):
            name = f"{field}_{norm}"
            errors = [row["fields"][field][norm]["time_l2"] for row in rows]
            total = [row["fields"][field][norm]["total_l2"] for row in rows]
            space = rows[-1]["fields"][field][norm]["space_l2"]
            orders = local_orders(errors)
            self_diffs = []
            key = "unwrapped_positions" if field == "position" else "velocities"
            for left, right in zip(run_ids[:-1], run_ids[1:]):
                delta = checkpoint(left)[key] - checkpoint(right)[key]
                self_diffs.append(vector_rms(delta[-1:] if norm == "endpoint" else delta))
            floor = uncertainty[field][f"uncertainty_{norm}"]
            combinations[name] = {
                "time_errors": errors,
                "total_errors": total,
                "space_platform": space,
                "fitted_order": fitted_order(dts, errors),
                "local_orders": orders,
                "finest_three_local_order_median": float(np.median(orders[-2:])),
                "points_above_20x_reference_floor": sum(error > 20.0 * floor for error in errors),
                "reference_uncertainty_floor": floor,
                "successive_self_differences": self_diffs,
                "self_difference_finest_coarsest_ratio": self_diffs[-1] / max(self_diffs[0], 1.0e-300),
                "finest_total_platform_relative_distance": abs(total[-1] - space) / max(space, 1.0e-300),
                "finest_time_space_ratio": errors[-1] / max(space, 1.0e-300),
                "total_boundedness_ratio": max(total) / max(total[0], space, 1.0e-300),
            }
    cfg = yaml.safe_load(CONFIG.read_text())
    checks = {
        "T1": all(strictly_decreasing(x["time_errors"]) for x in combinations.values()),
        "T2": all(x["fitted_order"] >= cfg["time_gates"]["T2"]["fitted_order_minimum"] for x in combinations.values()),
        "T3": all(1.70 <= x["finest_three_local_order_median"] <= 2.30 for x in combinations.values()),
        "T4": all(x["points_above_20x_reference_floor"] >= 4 for x in combinations.values()),
        "T5": all(x["self_difference_finest_coarsest_ratio"] <= 0.30 for x in combinations.values()),
        "P1": all(x["finest_total_platform_relative_distance"] <= 0.01 for x in combinations.values()),
        "P2": all(x["finest_time_space_ratio"] <= 0.01 for x in combinations.values()),
        "P3": all(np.isfinite(x["total_errors"]).all() and x["total_boundedness_ratio"] <= 2.0 for x in combinations.values()),
    }
    return {"label": label, "solution": solution, "dts": dts, "rows": rows, "combinations": combinations, "checks": checks}


def analyze_time() -> dict[str, Any]:
    dt_names = ["dt1e3", "dt5e4", "dt2p5e4", "dt1p25e4", "dt6p25e5"]
    cases = {}
    for kind, prefix, nref in (("main", "main", "main"), ("heldout", "hold", "hold")):
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            key = f"{kind}_{solution}"
            cases[key] = time_case(kind, solution, [f"f5_{prefix}_{letter}_{code}" for code in dt_names], f"f5_ref_{nref}_{letter}")
    main = [case for key, case in cases.items() if key.startswith("main_")]
    held = [case for key, case in cases.items() if key.startswith("heldout_")]
    main_checks = {gate: all(case["checks"][gate] for case in main) for gate in ("T1", "T2", "T3", "T4", "T5", "P1", "P2", "P3")}
    held_checks = {
        "H1": all(case["checks"]["T1"] for case in held),
        "H2": all(case["checks"]["T2"] for case in held),
        "H3": all(case["checks"]["P1"] for case in held),
        "H4": all(case["checks"]["P2"] for case in held),
    }
    payload = {"schema_version": "sph-pio-poc.stage01f5b.time-analysis.v1", "cases": cases, "main_checks": main_checks, "heldout_checks": held_checks}
    write_once(STAGE / "results/time_and_platform_analysis.json", payload)
    return payload


def endpoint_exact_errors(run_id: str) -> dict[str, float]:
    data = checkpoint(run_id)
    item = summary(run_id)
    exact = exact_fields(item["solution"], item["resolution"], item["support_ratio"], data["times"])
    return {
        "position": vector_rms(data["unwrapped_positions"][-1:] - exact["position"][-1:]),
        "velocity": vector_rms(data["velocities"][-1:] - exact["velocity"][-1:]),
        "density": vector_rms(data["densities"][-1:] - exact["density"][-1:]),
        "pressure": vector_rms(data["pressures"][-1:] - exact["pressure"][-1:]),
    }


def decide_space_step() -> dict[str, Any]:
    config = yaml.safe_load(CONFIG.read_text())
    comparisons = {}
    for letter in ("a", "b"):
        coarse = endpoint_exact_errors(f"f5_space_iso_{letter}_dt6p25e5")
        fine = endpoint_exact_errors(f"f5_space_iso_{letter}_dt3p125e5")
        for field in ("position", "velocity", "density", "pressure"):
            comparisons[f"MMS_{letter.upper()}_{field}"] = {
                "dt_6p25e5_error": coarse[field],
                "dt_3p125e5_error": fine[field],
                "relative_change": abs(coarse[field] - fine[field]) / max(fine[field], 1.0e-300),
            }
    maximum = max(item["relative_change"] for item in comparisons.values())
    triggered = maximum > config["space_step_decision"]["relative_change_trigger"]
    chosen = config["space_step_decision"]["if_triggered" if triggered else "otherwise"]
    payload = {
        "schema_version": "sph-pio-poc.stage01f5b.space-step-decision.v1",
        "comparisons": comparisons,
        "maximum_relative_change": maximum,
        "selection_rule": "choose 3.125e-5 iff any of eight relative changes is >0.10; otherwise choose 6.25e-5",
        "triggered": triggered,
        "chosen_dt_space": chosen["dt_space"],
        "formal_space_steps": chosen["steps"],
        "t_final": 0.02,
        "config_sha256": sha(CONFIG),
        "source_commit": config["numerical_source"]["frozen_commit"],
        "decision_timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "immutable": True,
    }
    write_once(STAGE / "manifests/space_step_decision.json", payload)
    return payload


def analyze_determinism() -> dict[str, Any]:
    pairs = [(x, f"{x}_rep2") for x in ("f5_main_a_dt6p25e5", "f5_main_b_dt6p25e5", "f5_hold_a_dt6p25e5", "f5_hold_b_dt6p25e5", "f5_space_a_n32", "f5_space_b_n32")]
    array_keys = ("positions", "unwrapped_positions", "velocities", "densities", "pressures", "masses", "edge_hashes", "times")
    scalar_keys = ("maximum_pair_force_residual", "maximum_internal_force_residual", "maximum_assembly_defect", "maximum_momentum_update_defect", "maximum_kinetic_energy_update_defect", "maximum_viscous_power", "minimum_separation_over_dx", "maximum_topology_structural_defects", "dynamic_topology_event_count", "topology_event_sequence_sha256", "unique_checkpoint_edge_identities")
    rows = []
    for base, repeat in pairs:
        left, right = checkpoint(base), checkpoint(repeat)
        array_checks = {key: np.array_equal(left[key], right[key]) for key in array_keys}
        ls, rs = summary(base), summary(repeat)
        scalar_checks = {key: ls[key] == rs[key] for key in scalar_keys}
        rows.append({"base": base, "repeat": repeat, "array_checks": array_checks, "scalar_checks": scalar_checks, "status": "PASS" if all(array_checks.values()) and all(scalar_checks.values()) else "FAIL"})
    payload = {"schema_version": "sph-pio-poc.stage01f5b.determinism.v1", "pairs": rows, "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL"}
    write_once(STAGE / "results/determinism.json", payload)
    return payload


def analyze_space() -> dict[str, Any]:
    decision = json.loads((STAGE / "manifests/space_step_decision.json").read_text())
    cases = {}
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        rows = []
        for n in (16, 24, 32, 48):
            run_id = f"f5_space_{letter}_n{n}"
            rows.append({"run_id": run_id, "N": n, "dx": 2.0 / n, "errors": endpoint_exact_errors(run_id), "hard_status": summary(run_id)["status"]})
        fields = {}
        for field in ("position", "velocity", "density", "pressure"):
            errors = [row["errors"][field] for row in rows]
            orders = [float(math.log(errors[i] / errors[i + 1]) / math.log(rows[i + 1]["N"] / rows[i]["N"])) for i in range(3)]
            fields[field] = {"errors": errors, "local_orders": orders, "n48_n32_ratio": errors[-1] / max(errors[-2], 1.0e-300), "global_slope": fitted_order([row["dx"] for row in rows], errors)}
        checks = {
            "S1": all(row["hard_status"] == "PASS" for row in rows),
            "S2": all(item["errors"][-1] < item["errors"][0] for item in fields.values()),
            "S3": all(strictly_decreasing(item["errors"]) for item in fields.values()),
            "S4": all(item["global_slope"] > 0.0 for item in fields.values()),
        }
        cases[solution] = {"rows": rows, "fields": fields, "checks": checks}
    checks = {gate: all(case["checks"][gate] for case in cases.values()) for gate in ("S1", "S2", "S3", "S4")}
    payload = {"schema_version": "sph-pio-poc.stage01f5b.spatial-analysis.v1", "path_claim": "increasing-neighbor consistency-path convergence", "fixed_stencil_single_h_claim": False, "space_step_decision": decision, "cases": cases, "checks": checks}
    write_once(STAGE / "results/spatial_analysis.json", payload)
    return payload


def decide_n64() -> dict[str, Any]:
    spatial = json.loads((STAGE / "results/spatial_analysis.json").read_text())
    trigger_rows = []
    for solution, case in spatial["cases"].items():
        for field, item in case["fields"].items():
            orders = item["local_orders"]
            nonmonotone = not strictly_decreasing(item["errors"])
            ratio = item["n48_n32_ratio"] > 0.95
            sign = not (all(order > 0.0 for order in orders) or all(order < 0.0 for order in orders))
            changes = [abs(orders[i + 1] - orders[i]) / max(abs(orders[i]), 1.0e-300) for i in range(len(orders) - 1)]
            unclear = any(change > 0.25 for change in changes)
            trigger_rows.append({"solution": solution, "field": field, "any_primary_error_nonmonotone": nonmonotone, "n48_n32_ratio_greater_than_0p95": ratio, "local_order_sign_inconsistent": sign, "near_asymptotic_entry_unclear": unclear, "local_order_relative_changes": changes})
    triggered = any(any(row[key] for key in ("any_primary_error_nonmonotone", "n48_n32_ratio_greater_than_0p95", "local_order_sign_inconsistent", "near_asymptotic_entry_unclear")) for row in trigger_rows)
    payload = {"schema_version": "sph-pio-poc.stage01f5b.n64-trigger.v1", "trigger_rows": trigger_rows, "decision": "TRIGGERED" if triggered else "NOT_TRIGGERED", "immutable": True, "decision_timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "config_sha256": sha(CONFIG)}
    write_once(STAGE / "manifests/n64_trigger_decision.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("references", "time", "space-step", "determinism", "space", "n64"))
    action = parser.parse_args().action
    result = {"references": qualify_references, "time": analyze_time, "space-step": decide_space_step, "determinism": analyze_determinism, "space": analyze_space, "n64": decide_n64}[action]()
    print(json.dumps({"action": action, "status": result.get("status", result.get("decision", "COMPLETE"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
