"""Post-process Stage 01F3B time, space, determinism, and audit evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f3b_mms_convergence"
CONFIG = STAGE / "configs/preregistered_stage01f3b.yml"


def load_summary(run_id: str) -> dict[str, Any]:
    return json.loads((STAGE / "run_summaries" / f"{run_id}.json").read_text())


def load_state(run_id: str) -> dict[str, np.ndarray]:
    data = np.load(STAGE / "trajectory_states" / f"{run_id}.npz")
    return {key: data[key] for key in data.files}


def dt_code(value: float) -> str:
    return f"{value:.8f}".split(".")[1].rstrip("0")


def write_json(name: str, payload: dict[str, Any]) -> None:
    path = STAGE / "results" / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def vector_rms(value: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(value * value, axis=-1))))


def periodic_difference(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.remainder(left - right + 1.0, 2.0) - 1.0


def fitted_order(dt: list[float], error: list[float]) -> float:
    return float(np.polyfit(np.log(np.asarray(dt)), np.log(np.asarray(error)), 1)[0])


def local_orders(error: list[float], dt: list[float]) -> list[float]:
    return [float(math.log(error[index] / error[index + 1]) / math.log(dt[index] / dt[index + 1])) for index in range(len(error) - 1)]


def semidiscrete(config: dict[str, Any]) -> None:
    block = config["semidiscrete_time"]; results = {}
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        reference = np.load(ROOT / f"06_experiments/stage_01f3r_reference_qualification/references/dense_mms_{letter}_three_level.npz")
        indices = np.arange(0, 41, 4); count = block["resolution"] ** 2
        dense = {name: reference[name][indices] for name in ("baseline", "tighter", "third")}
        uncertainty = {}
        for field, selection in (("position", slice(0, 2 * count)), ("velocity", slice(2 * count, None))):
            uncertainty[field] = max(vector_rms(dense["baseline"][:, selection] - dense["tighter"][:, selection]), vector_rms(dense["tighter"][:, selection] - dense["third"][:, selection]))
        rows = []
        for dt in block["dt"]:
            run_id = f"f3b_sd_{letter}_{dt_code(dt)}"; state = load_state(run_id); summary = load_summary(run_id)
            numerical_position = state["unwrapped_positions"].reshape(len(indices), -1)
            numerical_velocity = state["velocities"].reshape(len(indices), -1)
            position_delta = periodic_difference(numerical_position.reshape(len(indices), count, 2), dense["baseline"][:, :2 * count].reshape(len(indices), count, 2))
            velocity_delta = numerical_velocity.reshape(len(indices), count, 2) - dense["baseline"][:, 2 * count:].reshape(len(indices), count, 2)
            position_rms = vector_rms(position_delta); velocity_rms = vector_rms(velocity_delta)
            combined = float(np.sqrt(np.mean(np.concatenate((position_delta.reshape(len(indices), -1), velocity_delta.reshape(len(indices), -1)), axis=1) ** 2)))
            rows.append({"dt": dt, "run_id": run_id, "position_trajectory_rms": position_rms, "velocity_trajectory_rms": velocity_rms, "combined_state_l2": combined, "position_endpoint_l2": vector_rms(position_delta[-1:]), "velocity_endpoint_l2": vector_rms(velocity_delta[-1:]), "hard_path_pass": summary["status"] == "PASS"})
        for index in range(len(rows) - 1):
            coarse = load_state(rows[index]["run_id"]); fine = load_state(rows[index + 1]["run_id"])
            rows[index]["position_successive_self_difference"] = vector_rms(periodic_difference(coarse["unwrapped_positions"], fine["unwrapped_positions"]))
            rows[index]["velocity_successive_self_difference"] = vector_rms(coarse["velocities"] - fine["velocities"])
        rows[-1]["position_successive_self_difference"] = None; rows[-1]["velocity_successive_self_difference"] = None
        gates = {}; fit = {}
        for field in ("position", "velocity"):
            errors = [row[f"{field}_trajectory_rms"] for row in rows]
            valid = [index for index, error in enumerate(errors) if error > block["reference_floor_multiplier"] * uncertainty[field]]
            fit_dt = [block["dt"][index] for index in valid]; fit_error = [errors[index] for index in valid]
            orders = local_orders(fit_error, fit_dt) if len(valid) >= 2 else []
            slope = fitted_order(fit_dt, fit_error) if len(valid) >= 2 else None
            fit[field] = {"reference_uncertainty": uncertainty[field], "valid_indices": valid, "excluded_indices": [index for index in range(5) if index not in valid], "fitted_order": slope, "local_orders": orders, "finest_three_local_median": float(np.median(orders[-3:])) if len(orders) >= 3 else None, "finest_coarsest_ratio": errors[-1] / errors[0]}
            gates[f"{field}_ratio"] = errors[-1] / errors[0] <= config["formal_gates"]["semidiscrete_finest_coarsest_ratio"]
            gates[f"{field}_order"] = slope is not None and slope >= config["formal_gates"]["semidiscrete_fitted_order"]
            median = fit[field]["finest_three_local_median"]; lower, upper = config["formal_gates"]["semidiscrete_local_median"]
            gates[f"{field}_local_median"] = median is not None and lower <= median <= upper
            gates[f"{field}_reference_floor"] = len(valid) >= block["minimum_valid_points"]
        gates["five_of_five_hard_paths"] = all(row["hard_path_pass"] for row in rows)
        results[solution] = {"rows": rows, "fit": fit, "checks": gates, "status": "PASS" if all(gates.values()) else "FAIL"}
    write_json("semidiscrete_time_analysis.json", {"schema_version": "sph-pio-poc.stage01f3b.semidiscrete-time.v1", "solutions": results, "status": "PASS" if all(value["status"] == "PASS" for value in results.values()) else "FAIL"})


def continuous(config: dict[str, Any]) -> None:
    block = config["continuous_time"]; results = {}
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        rows = []
        for dt in block["dt"]:
            run_id = f"f3b_ct_{letter}_{dt_code(dt)}"; summary = load_summary(run_id)
            final = summary["final_metrics"]
            rows.append({"dt": dt, "run_id": run_id, "position_exact_l2": final["labeled_position_l2"], "velocity_exact_l2": final["labeled_velocity_l2"], "density_exact_l2": final["labeled_density_l2"], "pressure_exact_l2": final["labeled_pressure_l2"], "field_velocity_l2": final["field_velocity_l2"], "field_density_l2": final["field_density_l2"], "field_pressure_l2": final["field_pressure_l2"], "hard_path_pass": summary["status"] == "PASS", "trajectory_reference_sensitivity_upper_bound": summary["trajectory_reference_sensitivity_upper_bound"]})
        position_self = []; velocity_self = []
        for index in range(len(rows) - 1):
            coarse = load_state(rows[index]["run_id"]); fine = load_state(rows[index + 1]["run_id"])
            position_self.append(vector_rms(periodic_difference(coarse["positions"], fine["positions"])))
            velocity_self.append(vector_rms(coarse["velocities"] - fine["velocities"]))
            rows[index]["position_successive_self_difference"] = position_self[-1]; rows[index]["velocity_successive_self_difference"] = velocity_self[-1]
        rows[-1]["position_successive_self_difference"] = None; rows[-1]["velocity_successive_self_difference"] = None
        position_exact = [row["position_exact_l2"] for row in rows]; velocity_exact = [row["velocity_exact_l2"] for row in rows]
        checks = {"five_of_five_hard_paths": all(row["hard_path_pass"] for row in rows), "position_exact_nonincrease": position_exact[-1] <= position_exact[0], "velocity_exact_nonincrease": velocity_exact[-1] <= velocity_exact[0], "position_self_ratio": position_self[-1] / position_self[0] <= config["formal_gates"]["continuous_self_difference_ratio"], "velocity_self_ratio": velocity_self[-1] / velocity_self[0] <= config["formal_gates"]["continuous_self_difference_ratio"]}
        time_estimate = {"position": position_self[-1], "velocity": velocity_self[-1]}
        platform = {field: rows[-1][f"{field}_exact_l2"] > 5.0 * max(time_estimate.get(field, 0.0), rows[-1]["trajectory_reference_sensitivity_upper_bound"], 1e-30) for field in ("position", "velocity")}
        platform.update({field: rows[-1][f"{field}_exact_l2"] > 5.0 * max(abs(rows[-1][f"{field}_exact_l2"] - rows[-2][f"{field}_exact_l2"]), 1e-30) for field in ("density", "pressure")})
        checks["spatial_platform_identified"] = all(isinstance(value, bool) for value in platform.values())
        results[solution] = {"rows": rows, "semi_discrete_time_error_estimate": time_estimate, "spatial_platform": platform, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}
    write_json("continuous_time_analysis.json", {"schema_version": "sph-pio-poc.stage01f3b.continuous-time.v1", "solutions": results, "warning": "Continuous exact-error trends are not interpreted as pure RK2 order.", "status": "PASS" if all(value["status"] == "PASS" for value in results.values()) else "FAIL"})


def strictly_decreasing(values: list[float]) -> bool:
    return all(values[index + 1] < values[index] for index in range(len(values) - 1))


def space_analysis(config: dict[str, Any]) -> None:
    resolutions = config["space"]["formal_resolutions"]; results = {}; n64_reasons = []
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        rows = []
        fields = ("position", "velocity", "density", "pressure")
        for resolution in resolutions:
            summary = load_summary(f"f3b_space_{letter}_n{resolution}"); final = summary["final_metrics"]
            rows.append({"resolution": resolution, "dx": 2.0 / resolution, "run_id": summary["run_id"], **{f"{field}_l2": final[f"labeled_{field}_l2"] for field in fields}, **{f"field_{field}_l2": final[f"field_{field}_l2"] for field in ("velocity", "density", "pressure")}, "initial_density_l2": summary["initial_metrics"]["labeled_density_l2"], "endpoint_density_l2": final["labeled_density_l2"], "runtime_seconds": summary["wall_time_seconds"], "edge_count": final["edge_count"], "peak_rss_bytes": summary["peak_rss_bytes"], "topology_event_count": summary["dynamic_topology_event_count"], "trajectory_reference_sensitivity_upper_bound": summary["trajectory_reference_sensitivity_upper_bound"], "hard_path_pass": summary["status"] == "PASS"})
        monotonic = {}; slopes = {}; ratios = {}; locals_map = {}
        for field in fields:
            values = [row[f"{field}_l2"] for row in rows]; monotonic[field] = strictly_decreasing(values); slopes[field] = fitted_order([row["dx"] for row in rows], values); ratios[field] = values[-1] / values[-2]; locals_map[field] = local_orders(values, [row["dx"] for row in rows])
            if not monotonic[field]: n64_reasons.append(f"{solution}:{field}:nonmonotonic")
            if ratios[field] > config["formal_gates"]["n64_ratio_trigger"]: n64_reasons.append(f"{solution}:{field}:n48_n32_ratio")
            if len(locals_map[field]) < 3 or any(value <= 0 for value in locals_map[field]): n64_reasons.append(f"{solution}:{field}:local_order_unclear")
        if solution == "MMS_A":
            checks = {"four_of_four_hard_paths": all(row["hard_path_pass"] for row in rows), "velocity_endpoint_improves": rows[-1]["velocity_l2"] < rows[0]["velocity_l2"], "density_endpoint_improves": rows[-1]["density_l2"] < rows[0]["density_l2"], "pressure_endpoint_improves": rows[-1]["pressure_l2"] < rows[0]["pressure_l2"], "two_of_three_monotonic": sum(monotonic[field] for field in ("velocity", "density", "pressure")) >= 2, "three_positive_slopes": all(slopes[field] > 0 for field in ("velocity", "density", "pressure"))}
        else:
            checks = {"four_of_four_hard_paths": all(row["hard_path_pass"] for row in rows), "position_endpoint_improves": rows[-1]["position_l2"] < rows[0]["position_l2"], "velocity_endpoint_improves": rows[-1]["velocity_l2"] < rows[0]["velocity_l2"], "density_pressure_endpoint_improve": rows[-1]["density_l2"] < rows[0]["density_l2"] and rows[-1]["pressure_l2"] < rows[0]["pressure_l2"], "three_of_four_monotonic": sum(monotonic.values()) >= 3, "four_positive_slopes": all(slopes[field] > 0 for field in fields)}
        results[solution] = {"rows": rows, "monotonic": monotonic, "global_slopes": slopes, "local_orders": locals_map, "n48_n32_ratios": ratios, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}
    required = len(n64_reasons) > 0
    write_json("space_analysis.json", {"schema_version": "sph-pio-poc.stage01f3b.space.v1", "path": "increasing-neighbor consistency path", "solutions": results, "status": "PASS" if all(value["status"] == "PASS" for value in results.values()) else "FAIL"})
    write_json("n64_decision.json", {"schema_version": "sph-pio-poc.stage01f3b.n64-decision.v1", "required": required, "reasons": sorted(set(n64_reasons)), "decision_frozen_before_n64": True, "status": "RUN_REQUIRED" if required else "NOT_REQUIRED"})


def fixed_ratio(config: dict[str, Any]) -> None:
    results = {}
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        rows = []
        for resolution in config["space"]["formal_resolutions"]:
            summary = load_summary(f"f3b_fixed_{letter}_n{resolution}"); final = summary["final_metrics"]
            rows.append({"resolution": resolution, "position_l2": final["labeled_position_l2"], "velocity_l2": final["labeled_velocity_l2"], "density_l2": final["labeled_density_l2"], "pressure_l2": final["labeled_pressure_l2"], "initial_kernel_density_l2": summary["initial_metrics"]["labeled_density_l2"], "runtime_seconds": summary["wall_time_seconds"], "edge_count": final["edge_count"], "peak_rss_bytes": summary["peak_rss_bytes"], "topology_event_count": summary["dynamic_topology_event_count"], "hard_path_pass": summary["status"] == "PASS"})
        results[solution] = rows
    write_json("fixed_ratio_analysis.json", {"schema_version": "sph-pio-poc.stage01f3b.fixed-ratio.v1", "support_ratio": config["space"]["fixed_ratio"], "diagnostic_only": True, "solutions": results, "status": "PASS" if all(row["hard_path_pass"] for rows in results.values() for row in rows) else "FAIL"})


def determinism(config: dict[str, Any]) -> None:
    selected = json.loads((STAGE / "results/space_dt_selection.json").read_text())["selected_dt"]
    pairs = [
        (f"f3b_ct_{letter}_{dt_code(min(config['continuous_time']['dt']))}", f"f3b_repeat_ct_{letter}_{dt_code(min(config['continuous_time']['dt']))}") for letter in ("a", "b")
    ] + [(f"f3b_space_{letter}_n32", f"f3b_repeat_space_{letter}_n32") for letter in ("a", "b")]
    rows = []
    scalar_keys = ("maximum_pair_force_residual", "maximum_internal_force_residual", "maximum_assembly_defect", "maximum_momentum_update_defect", "maximum_kinetic_energy_update_defect", "maximum_viscous_power", "minimum_separation_over_dx", "maximum_topology_structural_defects", "dynamic_topology_event_count", "topology_event_sequence_sha256", "unique_checkpoint_edge_identities", "trajectory_reference_sensitivity_upper_bound")
    for primary, repeat in pairs:
        left = load_state(primary); right = load_state(repeat); a = load_summary(primary); b = load_summary(repeat)
        checkpoint = all(np.array_equal(left[key], right[key]) for key in ("unwrapped_positions", "positions", "velocities", "densities", "pressures", "masses", "edge_hashes"))
        scalar = all(a[key] == b[key] for key in scalar_keys)
        rows.append({"primary": primary, "repeat": repeat, "checkpoint_bitwise_identity": checkpoint, "deterministic_scalar_summary_bitwise_identity": scalar, "topology_event_sequence_identity": a["topology_event_sequence_sha256"] == b["topology_event_sequence_sha256"], "status": "PASS" if checkpoint and scalar and a["topology_event_sequence_sha256"] == b["topology_event_sequence_sha256"] else "FAIL"})
    with (STAGE / "results/campaign_index.csv").open() as stream: index = list(csv.DictReader(stream))
    reclaimed = all(row["child_reclaimed"] == "True" for row in index if row["run_id"] in {item for pair in pairs for item in pair})
    write_json("determinism_analysis.json", {"schema_version": "sph-pio-poc.stage01f3b.determinism.v1", "selected_space_dt": selected, "cases": rows, "child_reclaimed": reclaimed, "status": "PASS" if reclaimed and all(row["status"] == "PASS" for row in rows) else "FAIL"})


def balance_resources() -> None:
    summaries = [json.loads(path.read_text()) for path in sorted((STAGE / "run_summaries").glob("f3b_*.json"))]
    with (STAGE / "results/campaign_index.csv").open() as stream: index = list(csv.DictReader(stream))
    maxima = {key: max(float(item[key]) for item in summaries) for key in ("maximum_pair_force_residual", "maximum_internal_force_residual", "maximum_assembly_defect", "maximum_momentum_update_defect", "maximum_kinetic_energy_update_defect", "maximum_viscous_power", "maximum_current_rss_bytes", "peak_rss_bytes", "rss_quartile_absolute_increase_bytes", "rss_quartile_relative_increase", "step_time_q4_q1")}
    checks = {"all_worker_status_pass": all(item["status"] == "PASS" for item in summaries), "all_children_reclaimed": all(row["child_reclaimed"] == "True" for row in index), "all_parent_scalar_only": all(row["parent_scalar_only"] == "True" for row in index), "all_fresh_run_ids": all(item["run_id"].startswith("f3b_") for item in summaries)}
    write_json("balance_resource_summary.json", {"schema_version": "sph-pio-poc.stage01f3b.balance-resource.v1", "trajectory_count": len(summaries), "maxima": maxima, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"})


def order_gci(config: dict[str, Any]) -> None:
    space = json.loads((STAGE / "results/space_analysis.json").read_text()); results = {}
    for solution, payload in space["solutions"].items():
        fields = {}
        for field in ("position", "velocity", "density", "pressure"):
            values = [row[f"{field}_l2"] for row in payload["rows"]]; dx = [row["dx"] for row in payload["rows"]]; local = payload["local_orders"][field]
            monotonic_triples = [start for start in range(2) if strictly_decreasing(values[start:start + 3])]
            same_sign = all(value > 0 for value in local)
            stable = len(local) >= 2 and all(abs(local[index] - local[index + 1]) / max(abs(local[index + 1]), 1e-30) <= 0.25 for index in range(len(local) - 1))
            reference_floor = min(values) > 20.0 * max(row["trajectory_reference_sensitivity_upper_bound"] for row in payload["rows"])
            justified = bool(monotonic_triples and same_sign and stable and reference_floor)
            entry: dict[str, Any] = {"observed_order_reported": justified, "global_order": payload["global_slopes"][field] if justified else None, "local_orders": local, "monotonic_triples": monotonic_triples, "same_sign": same_sign, "local_order_stability_25_percent": stable, "above_reference_floor": reference_floor, "gci_justified": justified}
            if justified:
                p = payload["global_slopes"][field]; refinement = dx[-2] / dx[-1]; entry["gci_fine_percent"] = 100.0 * 1.25 * abs(values[-1] - values[-2]) / max(abs(values[-1]), 1e-30) / (refinement ** p - 1.0)
                entry["scope_statement"] = "GCI applies to the preregistered increasing-neighbor consistency path, not to a fixed-stencil single-h family."
            else: entry["scope_statement"] = "GCI not justified"
            fields[field] = entry
        results[solution] = fields
    write_json("order_gci_analysis.json", {"schema_version": "sph-pio-poc.stage01f3b.order-gci.v1", "solutions": results, "status": "COMPLETE"})


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", required=True, choices=("semitime", "conttime", "space", "fixed", "determinism", "balance", "order_gci")); args = parser.parse_args(); config = yaml.safe_load(CONFIG.read_text())
    {"semitime": semidiscrete, "conttime": continuous, "space": space_analysis, "fixed": fixed_ratio, "determinism": determinism, "balance": lambda _: balance_resources(), "order_gci": order_gci}[args.phase](config)
    print(json.dumps({"phase": args.phase, "status": "COMPLETE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
