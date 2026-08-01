"""Adjudicate the preregistered Stage 01D-P operational policy gates."""

from __future__ import annotations

import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_resource_policy.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
CAMPAIGN_INDEX = RESULTS_ROOT / "campaign_index.csv"
CAMPAIGN_SUMMARY = RESULTS_ROOT / "campaign_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(dict(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def classify_policy(facts: Mapping[str, bool]) -> str:
    if not facts["evidence_complete"]:
        return "POLICY_EVIDENCE_INCOMPLETE"
    if facts["all_operational_gates_pass"]:
        return "POLICY_PASS_ISOLATED_DEFAULT_GC"
    if facts["complete_finite_topology_safe_reclaimable"]:
        return "POLICY_CONDITIONAL_REDUCED_SCOPE"
    return "POLICY_FAIL_OPERATIONAL_ENVELOPE"


def main() -> int:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    evidence_rows: list[dict[str, Any]] = []
    evidence_identity = True
    for name, specification in configuration["read_only_evidence"].items():
        path = PROJECT_ROOT / specification["path"]
        observed = _sha256(path) if path.exists() else "MISSING"
        passed = observed == str(specification["sha256"])
        evidence_identity = evidence_identity and passed
        evidence_rows.append(
            {
                "evidence": name,
                "path": specification["path"],
                "expected_sha256": specification["sha256"],
                "observed_sha256": observed,
                "identity_pass": passed,
            }
        )

    primary_path = PROJECT_ROOT / configuration["read_only_evidence"]["stage01d_primary_config"]["path"]
    primary = yaml.safe_load(primary_path.read_text(encoding="utf-8"))
    final_time = Decimal(str(primary["primary_tgv"]["final_time"]))
    time_steps = [Decimal(str(value)) for value in primary["time_convergence"]["time_steps"]]
    minimum_dt = min(time_steps)
    planned_steps_decimal = final_time / minimum_dt
    planned_steps = int(planned_steps_decimal)
    exact_integer = planned_steps_decimal == Decimal(planned_steps)
    r5_gc_path = PROJECT_ROOT / configuration["read_only_evidence"]["r5_gc_mode_summary"]["path"]
    r5_gc_rows = _read_csv(r5_gc_path)
    default_horizons = sorted({int(row["steps"]) for row in r5_gc_rows if row["mode"] == "G1"})
    r5_horizon = min(default_horizons) if default_horizons else 0
    horizon_pass = (
        exact_integer
        and planned_steps == int(configuration["evidence_horizon"]["maximum_planned_formal_trajectory_steps"])
        and r5_horizon >= planned_steps
        and r5_horizon == int(configuration["evidence_horizon"]["r5_default_gc_evidence_steps"])
    )
    horizon_rows = [
        {
            "source": "Stage 01D primary/time-convergence configuration",
            "final_time": str(final_time),
            "minimum_dt": str(minimum_dt),
            "trajectory_steps": planned_steps,
            "repeat_count": "n/a",
            "pass": exact_integer and planned_steps == 1600,
        },
        {
            "source": "Stage 01D-R5 G1 default-GC evidence",
            "final_time": "n/a",
            "minimum_dt": "n/a",
            "trajectory_steps": r5_horizon,
            "repeat_count": sum(row["mode"] == "G1" for row in r5_gc_rows),
            "pass": r5_horizon >= planned_steps,
        },
    ]

    campaign_exists = CAMPAIGN_INDEX.exists() and CAMPAIGN_SUMMARY.exists()
    campaign_rows = _read_csv(CAMPAIGN_INDEX) if CAMPAIGN_INDEX.exists() else []
    campaign = _read_json(CAMPAIGN_SUMMARY) if CAMPAIGN_SUMMARY.exists() else {}
    expected_runs = int(configuration["canary"]["repeats"])
    summaries: list[dict[str, Any]] = []
    missing_summaries: list[str] = []
    for repeat in range(1, expected_runs + 1):
        run_id = f"stage01dp_canary_r{repeat}"
        path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
        if path.exists():
            summaries.append(_read_json(path))
        else:
            missing_summaries.append(run_id)
    canary_rows = [
        {
            "run_id": row["run_id"],
            "status": row["status"],
            "completed_steps": row.get("completed_steps", 0),
            "final_time": row.get("final_time", ""),
            "finite": row.get("state_all_finite", False),
            "default_gc": row.get("default_gc_enabled_throughout", False),
            "no_grad": row.get("torch_no_grad_throughout", False),
            "topology_pass": row.get("topology_pass", False),
            "max_pressure_pair_residual": row.get("maximum_pressure_relative_pair_force_residual", ""),
            "max_viscosity_pair_residual": row.get("maximum_viscosity_relative_pair_force_residual", ""),
            "max_viscous_power": row.get("maximum_viscous_power", ""),
            "current_rss_bytes": row.get("current_rss_bytes", ""),
            "peak_rss_bytes": row.get("peak_rss_bytes", ""),
            "rss_quartile_increase_bytes": row.get("final_minus_first_quartile_rss_median_bytes", ""),
            "rss_relative_increase": row.get("final_to_first_quartile_rss_relative_increase", ""),
            "step_time_ratio": row.get("final_to_first_quartile_step_time_ratio", ""),
            "minimum_system_available_fraction": row.get("minimum_system_available_memory_fraction", ""),
            "policy_gate_pass": row.get("policy_gate_pass", False),
        }
        for row in summaries
    ]
    process_rows = [
        {
            "run_id": row["run_id"],
            "return_code": row["return_code"],
            "pid": row["pid"],
            "process_reclaimed": row["process_reclaimed"],
            "child_rss_absent": row["child_rss_absent"],
            "parent_rss_growth_from_baseline_bytes": row["parent_rss_growth_from_baseline_bytes"],
            "scalar_summary_only": row["parent_received_scalar_summary_only"],
            "summary_path": row["summary_path"],
        }
        for row in campaign_rows
    ]
    config_hash = _sha256(CONFIG_PATH)
    source_identity = bool(campaign) and campaign.get("config_sha256") == config_hash and all(
        row.get("config_sha256") == config_hash and row.get("git_hash") == campaign.get("git_hash")
        for row in summaries
    )
    r5_status_path = PROJECT_ROOT / configuration["read_only_evidence"]["r5_status"]["path"]
    r5_status_pass = r5_status_path.read_text(encoding="utf-8").strip() == "R5_BOUNDED_GC_DELAY_CONFIRMED"
    campaign_complete = (
        campaign_exists
        and len(campaign_rows) == expected_runs
        and len(summaries) == expected_runs
        and not missing_summaries
        and int(campaign.get("expected_processes", -1)) == expected_runs
        and int(campaign.get("observed_processes", -1)) == expected_runs
    )
    process_reclaim_pass = (
        campaign_complete
        and _bool(campaign.get("all_processes_reclaimed"))
        and _bool(campaign.get("all_child_rss_absent"))
        and all(_bool(row["process_reclaimed"]) and _bool(row["child_rss_absent"]) for row in campaign_rows)
    )
    scalar_return_pass = campaign_complete and _bool(campaign.get("all_parent_returns_scalar_only")) and all(
        _bool(row["parent_received_scalar_summary_only"]) for row in campaign_rows
    )
    parent_rss_pass = campaign_complete and int(campaign.get("maximum_parent_rss_growth_bytes", 10**30)) <= int(
        configuration["qualification"]["maximum_parent_rss_growth_bytes"]
    )
    canary_operational_pass = campaign_complete and all(_bool(row.get("policy_gate_pass")) for row in summaries)
    all_operational = (
        evidence_identity
        and horizon_pass
        and r5_status_pass
        and source_identity
        and canary_operational_pass
        and process_reclaim_pass
        and scalar_return_pass
        and parent_rss_pass
    )
    safe_core = campaign_complete and all(
        int(row.get("completed_steps", 0)) == int(configuration["canary"]["steps"])
        and _bool(row.get("state_all_finite"))
        and _bool(row.get("topology_pass"))
        and _bool(row.get("pair_force_residual_pass"))
        and _bool(row.get("internal_force_pass"))
        and _bool(row.get("viscous_power_pass"))
        and _bool(row.get("system_memory_pressure_pass"))
        and _bool(row.get("default_gc_enabled_throughout"))
        and _bool(row.get("torch_no_grad_throughout"))
        for row in summaries
    )
    evidence_complete = evidence_identity and horizon_pass and r5_status_pass and source_identity and campaign_complete
    complete_safe_reclaimable = (
        evidence_complete
        and safe_core
        and process_reclaim_pass
        and scalar_return_pass
        and parent_rss_pass
    )
    facts = {
        "evidence_complete": evidence_complete,
        "all_operational_gates_pass": all_operational,
        "complete_finite_topology_safe_reclaimable": complete_safe_reclaimable,
    }
    status = classify_policy(facts)
    allowed = set(configuration["status_policy"]["allowed"])
    if status not in allowed:
        raise RuntimeError("policy classifier produced a non-preregistered state")
    stage01d2_eligible = status == "POLICY_PASS_ISOLATED_DEFAULT_GC"
    gates = [
        {"gate": "P1", "name": "read_only_evidence_identity", "passed": evidence_identity and r5_status_pass, "observed": f"sha={sum(_bool(row['identity_pass']) for row in evidence_rows)}/{len(evidence_rows)} r5_status={r5_status_pass}", "required": "all identities and frozen R5 status"},
        {"gate": "P2", "name": "evidence_horizon", "passed": horizon_pass, "observed": f"R5={r5_horizon} planned={planned_steps}", "required": "R5 default-GC horizon >= planned maximum"},
        {"gate": "P3", "name": "maximum_horizon_canaries", "passed": canary_operational_pass, "observed": f"{sum(_bool(row.get('policy_gate_pass')) for row in summaries)}/{expected_runs}", "required": "3/3 operational gates"},
        {"gate": "P4", "name": "subprocess_reclamation", "passed": process_reclaim_pass and scalar_return_pass and parent_rss_pass, "observed": f"reclaimed={process_reclaim_pass} scalar={scalar_return_pass} parent_rss={parent_rss_pass}", "required": "3/3 exited, no child RSS, scalar-only return, bounded parent"},
        {"gate": "P5", "name": "default_gc_no_grad_no_collect_policy", "passed": campaign_complete and all(_bool(row.get('default_gc_enabled_throughout')) and _bool(row.get('torch_no_grad_throughout')) for row in summaries), "observed": f"runs={len(summaries)}", "required": "default GC enabled and no_grad for all canaries"},
        {"gate": "STATUS", "name": "unique_policy_status", "passed": True, "observed": status, "required": json.dumps(sorted(allowed), separators=(",", ":"))},
    ]

    _write_csv(RESULTS_ROOT / "evidence_identity.csv", evidence_rows)
    _write_csv(RESULTS_ROOT / "evidence_horizon.csv", horizon_rows)
    _write_csv(RESULTS_ROOT / "canary_summary.csv", canary_rows)
    _write_csv(RESULTS_ROOT / "subprocess_audit.csv", process_rows)
    _write_csv(RESULTS_ROOT / "policy_gate_evidence.csv", gates)
    _write_json(
        RESULTS_ROOT / "analysis_summary.json",
        {
            "schema_version": "sph-pio-poc.stage01dp.analysis.v1",
            "status": status,
            "config_sha256": config_hash,
            "evidence_identity_pass": evidence_identity,
            "r5_status_identity_pass": r5_status_pass,
            "source_identity_pass": source_identity,
            "planned_maximum_trajectory_steps": planned_steps,
            "r5_default_gc_evidence_steps": r5_horizon,
            "horizon_pass": horizon_pass,
            "canary_operational_pass": canary_operational_pass,
            "process_reclamation_pass": process_reclaim_pass,
            "scalar_return_pass": scalar_return_pass,
            "parent_rss_pass": parent_rss_pass,
            "stage01d2_design_application_eligible": stage01d2_eligible,
            "stage01d2_started": False,
            "v3_started": False,
            "stage02_started": False,
            "canary_is_v2_convergence_data": False,
            "historical_statuses": configuration["historical_statuses"],
            "r5_tag_target": subprocess.check_output(
                ("git", "rev-parse", "stage-01dr5-bounded-gc-delay-confirmed^{}"),
                cwd=PROJECT_ROOT,
                text=True,
            ).strip(),
        },
    )
    status_path = RESULTS_ROOT / "stage01dp_status.txt"
    if status_path.exists():
        raise RuntimeError("refusing to overwrite Stage 01D-P status")
    with status_path.open("x", encoding="utf-8") as stream:
        stream.write(status + "\n")
    print(json.dumps({"status": status, "stage01d2_design_application_eligible": stage01d2_eligible}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
