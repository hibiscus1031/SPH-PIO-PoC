"""Evaluate the preregistered Stage 01D2 evidence without changing it."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01d2_v2_requalification"
CONFIG = ROOT / "configs" / "preregistered_stage01d2_v2.yml"
RESULTS = ROOT / "results"


def read_summary(run_id: str) -> dict[str, Any]:
    return json.loads((ROOT / "run_summaries" / f"{run_id}.json").read_text(encoding="utf-8"))


def ratio(a: float, b: float) -> float:
    return float(a / b) if b != 0 else math.inf


def slope(dx: list[float], errors: list[float]) -> float:
    return float(np.polyfit(np.log(dx), np.log(errors), 1)[0]) if all(math.isfinite(x) and x > 0 for x in errors) else math.nan


def self_difference(run_a: str, run_b: str) -> tuple[float, list[float]]:
    a = np.load(ROOT / "trajectory_states" / f"{run_a}.npz")
    b = np.load(ROOT / "trajectory_states" / f"{run_b}.npz")
    if not np.allclose(a["times"], b["times"], rtol=0, atol=1e-13):
        raise ValueError("self-convergence checkpoints differ")
    values = [float(np.linalg.norm(x-y) / max(np.linalg.norm(y), 1e-30)) for x,y in zip(a["velocities"], b["velocities"])]
    return values[-1], values


def classify_status(e: dict[str, Any]) -> str:
    if not e["evidence_complete"]:
        return "STAGE01D2_EVIDENCE_INCOMPLETE"
    hard = not all((e["prerequisite_pass"], e["conservation_pass"], e["resource_pass"], e["ad_pass"], e["disorder_status"] != "D_FAIL", e["mach_complete"]))
    if hard:
        return "STAGE01D2_V2_REQUALIFICATION_FAIL"
    if e["time_pass"] and e["space_pass"] and e["disorder_status"] in ("D_PASS", "D_CONDITIONAL") and e["provenance_pass"]:
        return "STAGE01D2_V2_REQUALIFIED_PASS"
    if e["time_pass"] and e["provenance_pass"]:
        return "STAGE01D2_V2_REQUALIFIED_CONDITIONAL"
    return "STAGE01D2_V2_REQUALIFICATION_FAIL"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["empty"], lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    mandatory = [row["run_id"] for row in cfg["trajectory_matrix"] if row["phase"] in ("prerequisite", "main", "extended")]
    trajectory_complete = all((ROOT / "run_summaries" / f"{x}.json").exists() for x in mandatory)
    optional_n48 = [cfg["n48_policy"]["smoke_run_id"], cfg["n48_policy"]["full_run_id"]]
    actual_ids = mandatory + [run for run in optional_n48 if (ROOT / "run_summaries" / f"{run}.json").exists()]
    rows = {run: read_summary(run) for run in actual_ids} if trajectory_complete else {}
    prereq = json.loads((RESULTS / "prerequisite_summary.json").read_text()) if (RESULTS / "prerequisite_summary.json").exists() else {"status": "MISSING"}

    time_rows = [rows[x] for x in cfg["time_study"]["run_ids"]] if trajectory_complete else []
    time_velocity = [float(x["final_velocity_relative_l2"]) for x in time_rows]
    time_modal = [abs(float(x["final_modal_amplitude_error"])) for x in time_rows]
    coarse_self, coarse_series = self_difference(cfg["time_study"]["run_ids"][0], cfg["time_study"]["run_ids"][1]) if trajectory_complete else (math.nan, [])
    fine_self, fine_series = self_difference(cfg["time_study"]["run_ids"][2], cfg["time_study"]["run_ids"][3]) if trajectory_complete else (math.nan, [])
    t = {
        "T1": bool(time_rows) and all(x["status"] == "PASS" for x in time_rows),
        "T2": bool(time_rows) and time_velocity[-1] <= time_velocity[0],
        "T3": bool(time_rows) and time_modal[-1] <= time_modal[0],
        "T4": bool(time_rows) and min(ratio(time_velocity[-1], time_velocity[0]), ratio(time_modal[-1], time_modal[0]), ratio(fine_self, coarse_self)) <= 0.8,
    }
    time_table = [{"run_id": x["run_id"], "dt": x["dt"], "velocity_relative_l2": x["final_velocity_relative_l2"], "modal_error": abs(float(x["final_modal_amplitude_error"])), "kinetic_energy_error": x["final_kinetic_energy_error"], "peak_rss_bytes": x["peak_rss_bytes"], "wall_time_seconds": x["wall_time_seconds"], "status": x["status"]} for x in time_rows]

    space_rows = [rows[x] for x in cfg["space_study"]["run_ids"]] if trajectory_complete else []
    sve = [float(x["final_velocity_relative_l2"]) for x in space_rows]
    sme = [abs(float(x["final_modal_amplitude_error"])) for x in space_rows]
    ske = [abs(float(x["final_kinetic_energy_error"])) for x in space_rows]
    dx = [2/n for n in cfg["space_study"]["resolutions"]]
    svs, sms = (slope(dx, sve), slope(dx, sme)) if space_rows else (math.nan, math.nan)
    s = {
        "S1": bool(space_rows) and all(x["status"] == "PASS" for x in space_rows),
        "S2": bool(space_rows) and sve[-1] < sve[0], "S3": bool(space_rows) and sme[-1] < sme[0],
        "S4": bool(space_rows) and svs > 0 and sms > 0,
        "S5": bool(space_rows) and ratio(sve[-1], sve[0]) <= 0.9,
        "S6": bool(space_rows) and ratio(ske[-1], ske[0]) <= 1.1,
    }
    monotone = bool(space_rows) and sve[0] > sve[1] > sve[2] and sme[0] > sme[1] > sme[2]
    order_v = [math.log(sve[i]/sve[i+1]) / math.log(dx[i]/dx[i+1]) for i in (0,1)] if monotone else []
    order_m = [math.log(sme[i]/sme[i+1]) / math.log(dx[i]/dx[i+1]) for i in (0,1)] if monotone else []
    gci = monotone and max(abs(order_v[0]-order_v[1]), abs(order_m[0]-order_m[1])) <= 0.25
    space_table = [{"run_id": x["run_id"], "resolution": x["resolution"], "support_ratio": x["support_ratio"], "velocity_relative_l2": x["final_velocity_relative_l2"], "modal_error": abs(float(x["final_modal_amplitude_error"])), "kinetic_energy_error": x["final_kinetic_energy_error"], "status": x["status"]} for x in space_rows]

    support_ids = list(dict.fromkeys(cfg["support_family_comparison"]["constant_neighbor_run_ids"] + cfg["support_family_comparison"]["increasing_neighbor_run_ids"]))
    support_table = [{"run_id": rows[x]["run_id"], "family": rows[x]["support_family"], "resolution": rows[x]["resolution"], "support_ratio": rows[x]["support_ratio"], "velocity_relative_l2": rows[x]["final_velocity_relative_l2"], "modal_error": abs(float(rows[x]["final_modal_amplitude_error"])), "kinetic_energy_error": rows[x]["final_kinetic_energy_error"], "density_fluctuation": rows[x]["final_density_fluctuation_relative_rms"], "wall_time_seconds": rows[x]["wall_time_seconds"], "mean_edge_count": rows[x]["mean_edge_count"], "peak_rss_bytes": rows[x]["peak_rss_bytes"]} for x in support_ids] if trajectory_complete else []

    disorder_ids = [cfg["disorder_study"]["regular_run_id"]] + cfg["disorder_study"]["jitter_05_run_ids"] + cfg["disorder_study"]["jitter_10_run_ids"]
    disorder_rows = [rows[x] for x in disorder_ids] if trajectory_complete else []
    reg_ok = bool(disorder_rows) and disorder_rows[0]["status"] == "PASS"; j05_ok = bool(disorder_rows) and all(x["status"] == "PASS" for x in disorder_rows[1:4]); j10_ok = bool(disorder_rows) and all(x["status"] == "PASS" for x in disorder_rows[4:])
    multiplier = statistics.median(float(x["final_velocity_relative_l2"]) for x in disorder_rows[4:]) / float(disorder_rows[0]["final_velocity_relative_l2"]) if disorder_rows and all(x["final_velocity_relative_l2"] is not None for x in disorder_rows[4:]) else math.inf
    disorder_status = "D_PASS" if reg_ok and j05_ok and j10_ok and multiplier <= 2 else ("D_CONDITIONAL" if reg_ok and j05_ok else "D_FAIL")
    disorder_table = [{"run_id": x["run_id"], "layout": x["layout"], "seed": x["seed"], "status": x["status"], "velocity_relative_l2": x["final_velocity_relative_l2"], "modal_error": abs(float(x["final_modal_amplitude_error"])), "kinetic_energy_error": x["final_kinetic_energy_error"], "density_fluctuation": x["final_density_fluctuation_relative_rms"], "momentum_drift": x["maximum_momentum_drift_normalized"], "minimum_separation_over_dx": x["minimum_separation_over_dx"], "mean_neighbor_count": x["mean_neighbor_count"], "peak_rss_bytes": x["peak_rss_bytes"], "failure_type": x["failure_type"]} for x in disorder_rows]

    mach_rows = [rows[x] for x in cfg["mach_study"]["run_ids"]] if trajectory_complete else []
    mach_complete = bool(mach_rows) and all(x["status"] == "PASS" for x in mach_rows)
    densities = [float(x["final_density_fluctuation_relative_rms"]) for x in mach_rows]
    mach_nonworsening = mach_complete and densities[0] >= densities[1] >= densities[2]
    mach_table = [{"run_id": x["run_id"], "sound_speed": x["sound_speed"], "nominal_mach": x["nominal_mach"], "velocity_relative_l2": x["final_velocity_relative_l2"], "modal_error": abs(float(x["final_modal_amplitude_error"])), "density_fluctuation": x["final_density_fluctuation_relative_rms"], "maximum_mach": x["maximum_mach"], "maximum_pressure_absolute": x["maximum_pressure_absolute"], "acoustic_cfl_maximum": x["acoustic_cfl_maximum"], "wall_time_seconds": x["wall_time_seconds"], "peak_rss_bytes": x["peak_rss_bytes"], "status": x["status"]} for x in mach_rows]

    accepted = list(rows.values())
    conservation = bool(accepted) and all(x["numerical_and_topology_pass"] for x in accepted)
    campaign_rows = list(csv.DictReader((RESULTS / "campaign_index.csv").open())) if (RESULTS / "campaign_index.csv").exists() else []
    resource = bool(accepted) and all(x["resource_policy_pass"] for x in accepted) and all(x["child_reclaimed"] == "True" and int(x["parent_rss_growth_from_campaign_start_bytes"]) <= int(cfg["resource_gates"]["maximum_parent_rss_growth_bytes"]) for x in campaign_rows)
    ad_paths = list((RESULTS / "ad_cases").glob("*.json")); ad_rows = [json.loads(x.read_text()) for x in sorted(ad_paths)]
    ad_pass = len(ad_rows) == 20 and all(x["status"] == "PASS" for x in ad_rows)
    n48_primary = json.loads((RESULTS / "n48_primary_decision.json").read_text()) if (RESULTS / "n48_primary_decision.json").exists() else {}
    n48_smoke = json.loads((RESULTS / "n48_smoke_decision.json").read_text()) if (RESULTS / "n48_smoke_decision.json").exists() else {}
    n48_complete = bool(n48_primary) and (not n48_primary.get("n48_smoke_authorized") or ((ROOT / "run_summaries" / f"{cfg['n48_policy']['smoke_run_id']}.json").exists() and bool(n48_smoke) and (not n48_smoke.get("n48_full_authorized") or (ROOT / "run_summaries" / f"{cfg['n48_policy']['full_run_id']}.json").exists())))
    evidence_complete = trajectory_complete and n48_complete and len(ad_rows) == 20 and prereq["status"] in ("PASS", "FAIL") and (RESULTS / "campaign_index.csv").exists()
    evaluation = {"schema_version": "sph-pio-poc.stage01d2.evaluation.v1", "prerequisite_pass": prereq["status"] == "PASS", "time_gates": t, "time_pass": all(t.values()), "space_gates": s, "space_pass": all(s[k] for k in ("S1","S2","S3","S4","S5")), "space_slope_velocity": svs, "space_slope_modal": sms, "gci_justified": gci, "gci_statement": "GCI justified" if gci else "GCI not justified", "disorder_status": disorder_status, "jitter10_median_velocity_error_multiplier": multiplier, "mach_complete": mach_complete, "mach_density_nonworsening": mach_nonworsening, "conservation_pass": conservation, "resource_pass": resource, "ad_pass": ad_pass, "ad_completed_cases": len(ad_rows), "provenance_pass": prereq["status"] == "PASS", "evidence_complete": evidence_complete, "canary_rows_used": 0, "v3_started": False, "stage02_started": False, "time_velocity_errors": time_velocity, "time_modal_errors": time_modal, "time_self_difference_coarse": coarse_self, "time_self_difference_fine": fine_self, "time_self_difference_series_coarse": coarse_series, "time_self_difference_series_fine": fine_series}
    evaluation["final_status"] = classify_status(evaluation)
    RESULTS.mkdir(parents=True, exist_ok=True)
    for name, table in (("time_results.csv", time_table), ("space_results.csv", space_table), ("support_family_results.csv", support_table), ("disorder_results.csv", disorder_table), ("mach_results.csv", mach_table), ("autograd_results.csv", ad_rows)):
        write_csv(RESULTS / name, table)
    path = RESULTS / "stage01d2_evaluation.json"
    if path.exists(): raise RuntimeError("refusing to overwrite evaluation")
    path.write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(evaluation["final_status"])
    return 0


if __name__ == "__main__": raise SystemExit(main())
