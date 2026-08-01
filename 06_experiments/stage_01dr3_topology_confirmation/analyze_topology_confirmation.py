"""Evaluate preregistered T1--T5 gates without refitting R2 models."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_topology_confirmation.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
FIGURES_ROOT = EXPERIMENT_ROOT / "figures"
R2_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution" / "results"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool(value: Any) -> bool:
    return str(value).lower() == "true"


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


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _r2_identity(configuration: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    expected = configuration["r2_frozen_evidence"]
    rows: list[dict[str, Any]] = []
    hashes_pass = True
    for filename in (
        "edge_working_set_models.csv",
        "weakref_lifetime_summary.csv",
        "numerical_regression_summary.csv",
        "attribution_gate_evidence.csv",
    ):
        path = R2_RESULTS / filename
        observed = _sha256(path)
        passed = observed == str(expected[filename])
        hashes_pass = hashes_pass and passed
        rows.append(
            {
                "filename": filename,
                "expected_sha256": expected[filename],
                "observed_sha256": observed,
                "identity_pass": passed,
            }
        )
    models = _read_csv(R2_RESULTS / "edge_working_set_models.csv")
    model_pass = len(models) == 4
    for row in models:
        model_pass = bool(
            model_pass
            and abs(float(row["total_edge_coefficient"]) - float(expected["required_beta_edge_bytes_per_edge"])) <= 1.0e-9
            and abs(float(row["total_step_coefficient"])) <= float(expected["beta_step_absolute_limit_bytes_per_step"])
            and float(row["total_step_ci95_lower"]) <= 0.0 <= float(row["total_step_ci95_upper"])
            and abs(float(row["unknown_step_coefficient"])) <= float(expected["gamma_step_absolute_limit_bytes_per_step"])
            and float(row["unknown_step_ci95_lower"]) <= 0.0 <= float(row["unknown_step_ci95_upper"])
        )
    lifetime = [
        row
        for row in _read_csv(R2_RESULTS / "weakref_lifetime_summary.csv")
        if row["control"] == "D"
    ]
    lifetime_pass = len(lifetime) == 4 and all(
        int(row["maximum_old_survivor_bytes"]) == 0
        and int(row["maximum_old_survivor_storage_count"]) == 0
        for row in lifetime
    )
    numerical = _read_csv(R2_RESULTS / "numerical_regression_summary.csv")
    numerical_pass = len(numerical) == 4 and all(
        int(row["rows"]) == int(expected["required_numerical_bitwise_rows_per_run"])
        and int(row["bitwise_and_finite_rows"]) == int(expected["required_numerical_bitwise_rows_per_run"])
        and float(row["maximum_absolute_difference"]) == 0.0
        and _bool(row["pass"])
        for row in numerical
    )
    rows.extend(
        (
            {"filename": "semantic:model_thresholds", "expected_sha256": "n/a", "observed_sha256": "n/a", "identity_pass": model_pass},
            {"filename": "semantic:D_old_survivor_zero", "expected_sha256": "n/a", "observed_sha256": "n/a", "identity_pass": lifetime_pass},
            {"filename": "semantic:numerical_bitwise", "expected_sha256": "n/a", "observed_sha256": "n/a", "identity_pass": numerical_pass},
        )
    )
    return rows, bool(hashes_pass and model_pass and lifetime_pass and numerical_pass)


def _control_analysis(configuration: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, bool], bool]:
    qualification = configuration["qualification"]
    rows: list[dict[str, Any]] = []
    passes: dict[str, bool] = {}
    retention_signal = False
    expected_config_hash = _sha256(CONFIG_PATH)
    for control in ("F", "M"):
        control_pass = True
        for repeat in (1, 2, 3):
            run_id = f"stage01dr3_{control.lower()}_r{repeat}"
            summary = _read_json(RESULTS_ROOT / "run_summaries" / f"{run_id}.json")
            ledger = _read_csv(RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv")
            lifetime = [
                row
                for row in _read_csv(RESULTS_ROOT / "weakref_lifetime" / f"{run_id}.csv")
                if _bool(row["gc_collected"])
            ]
            exit_data = _read_json(RESULTS_ROOT / "process_exit" / f"{run_id}.json")
            run_config = _read_json(RESULTS_ROOT / "run_configs" / f"{run_id}.json")
            tensor_delta = int(ledger[-1]["live_tensor_count"]) - int(ledger[0]["live_tensor_count"])
            unknown_delta = int(ledger[-1]["unknown_live_bytes"]) - int(ledger[0]["unknown_live_bytes"])
            maximum_old_bytes = max(int(row["old_survivor_bytes"]) for row in lifetime)
            maximum_old_count = max(int(row["old_survivor_storage_count"]) for row in lifetime)
            maximum_same_slot = max(int(row["same_slot_multiple_generation_count"]) for row in lifetime)
            maximum_age2 = max(int(row["age2_alive_tensor_reference_count"]) for row in lifetime)
            referrer_count = int(summary["referrer_chain_count"])
            topology_pass = bool(
                int(summary["unique_force_stage_edge_counts"]) == int(qualification["required_unique_edge_counts"])
                and int(summary["unique_force_stage_edge_identities"]) == int(qualification["required_unique_edge_identities"])
                and int(summary["maximum_duplicate_edge_count"]) == 0
                and int(summary["maximum_nonreciprocal_edge_count"]) == 0
            )
            if control == "M":
                topology_pass = bool(
                    topology_pass
                    and int(summary["maximum_omitted_strict_support_edge_count"]) == 0
                    and int(summary["maximum_unexpected_edge_count"]) == 0
                    and float(summary["minimum_dimensionless_cutoff_margin"])
                    > float(configuration["support_margin_geometry"]["minimum_allowed_dimensionless_margin"])
                )
            lifetime_pass = bool(
                maximum_old_bytes == 0
                and maximum_old_count == 0
                and maximum_same_slot == 0
                and maximum_age2 == 0
                and referrer_count == 0
            )
            memory_pass = tensor_delta == 0 and unknown_delta == 0
            provenance_pass = bool(
                run_config["config_sha256"] == expected_config_hash
                and run_config["git_hash"] == summary["git_hash"]
                and exit_data["process_reclaimed"] is True
            )
            finite_pass = bool(summary["all_state_values_finite"])
            completed = bool(
                summary["status"] == "PASS"
                and int(summary["completed_steps"]) == 2000
            )
            passed = bool(
                completed
                and topology_pass
                and lifetime_pass
                and memory_pass
                and provenance_pass
                and finite_pass
            )
            retention_signal = bool(
                retention_signal
                or maximum_old_bytes > 0
                or maximum_old_count > 0
                or maximum_same_slot > 0
                or referrer_count > 0
                or unknown_delta > 0
            )
            control_pass = control_pass and passed
            rows.append(
                {
                    "run_id": run_id,
                    "control": control,
                    "repeat": repeat,
                    "completed_steps": summary["completed_steps"],
                    "unique_edge_counts": summary["unique_force_stage_edge_counts"],
                    "unique_edge_identities": summary["unique_force_stage_edge_identities"],
                    "edge_count_values": json.dumps(summary["force_stage_edge_counts"], separators=(",", ":")),
                    "live_tensor_count_delta": tensor_delta,
                    "unknown_live_bytes_delta": unknown_delta,
                    "maximum_old_survivor_bytes": maximum_old_bytes,
                    "maximum_old_survivor_storage_count": maximum_old_count,
                    "maximum_same_slot_multiple_generation_count": maximum_same_slot,
                    "maximum_age2_alive_tensor_reference_count": maximum_age2,
                    "referrer_chain_count": referrer_count,
                    "minimum_dimensionless_cutoff_margin": summary["minimum_dimensionless_cutoff_margin"],
                    "maximum_duplicate_edge_count": summary["maximum_duplicate_edge_count"],
                    "maximum_nonreciprocal_edge_count": summary["maximum_nonreciprocal_edge_count"],
                    "maximum_omitted_strict_support_edge_count": summary["maximum_omitted_strict_support_edge_count"],
                    "maximum_unexpected_edge_count": summary["maximum_unexpected_edge_count"],
                    "state_finite": finite_pass,
                    "process_reclaimed": exit_data["process_reclaimed"],
                    "provenance_pass": provenance_pass,
                    "pass": passed,
                }
            )
        passes[control] = control_pass
    return rows, passes, retention_signal


def _figures(control_rows: list[dict[str, Any]]) -> None:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    cutoff_path = FIGURES_ROOT / "stage01dr3_cutoff_edge_sequence.png"
    margin_path = FIGURES_ROOT / "stage01dr3_control_margins.png"
    if cutoff_path.exists() or margin_path.exists():
        raise RuntimeError("R3 figures already exist")
    sequence = _read_csv(RESULTS_ROOT / "cutoff_edge_count_sequence.csv")
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.plot(
        [int(row["step"]) for row in sequence],
        [int(row["edge_count"]) for row in sequence],
        linewidth=1.2,
        color="#4477AA",
    )
    ax.set_xlabel("zero-flow replay step")
    ax.set_ylabel("directed edge count")
    ax.set_yticks((82940, 82942, 82944))
    fig.tight_layout()
    fig.savefig(cutoff_path, dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.bar(
        [row["run_id"] for row in control_rows],
        [float(row["minimum_dimensionless_cutoff_margin"]) for row in control_rows],
        color=["#EE6677" if row["control"] == "F" else "#228833" for row in control_rows],
    )
    ax.set_ylabel("minimum |r/dx - H/dx|")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(margin_path, dpi=180)
    plt.close(fig)


def main() -> int:
    outputs = (
        RESULTS_ROOT / "r2_evidence_identity.csv",
        RESULTS_ROOT / "control_summary.csv",
        RESULTS_ROOT / "r3_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dr3_status.txt",
    )
    if any(path.exists() for path in outputs):
        raise RuntimeError("R3 analysis outputs already exist")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cutoff = _read_json(RESULTS_ROOT / "cutoff_shell_audit_summary.json")
    t1 = bool(
        cutoff["edge_count_values"] == [82940, 82942, 82944]
        and cutoff["all_switches_on_q5_shell"]
        and cutoff["all_switches_near_cutoff"]
        and cutoff["r2_c_sample_identity_pass"]
        and cutoff["all_state_values_finite"]
    )
    r2_rows, t4 = _r2_identity(configuration)
    control_rows, control_pass, retention_signal = _control_analysis(configuration)
    t2 = bool(control_pass["F"])
    t3 = bool(control_pass["M"])
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    t5 = bool(
        campaign["expected_processes"] == 7
        and campaign["observed_processes"] == 7
        and campaign["pass_processes"] == 7
        and campaign["all_processes_reclaimed"]
        and all(bool(row["state_finite"]) and bool(row["provenance_pass"]) for row in control_rows)
        and t4
    )
    if retention_signal:
        status = "R3_RETENTION_SIGNAL_DETECTED"
    elif not (t2 and t3):
        status = "R3_TOPOLOGY_CONTROL_FAIL"
    elif t1 and t2 and t3 and t4 and t5:
        status = "R3_WORKING_SET_ATTRIBUTION_CONFIRMED"
    else:
        status = "R3_CONFIRMATION_UNRESOLVED"
    if status not in set(configuration["allowed_statuses"]):
        raise RuntimeError("R3 status is not preregistered")
    eligible = status in set(configuration["stage01d2_application_eligible_statuses"])
    gate_rows = [
        {"gate": "T1", "name": "cutoff_shell_diagnosis", "passed": t1, "observed": json.dumps(cutoff["edge_count_values"], separators=(",", ":")), "required": "q=5 cutoff switches explain 82940/82942/82944"},
        {"gate": "T2", "name": "frozen_topology_control", "passed": t2, "observed": f"{sum(row['pass'] for row in control_rows if row['control']=='F')}/3", "required": "3/3"},
        {"gate": "T3", "name": "support_margin_control", "passed": t3, "observed": f"{sum(row['pass'] for row in control_rows if row['control']=='M')}/3", "required": "3/3"},
        {"gate": "T4", "name": "r2_dynamic_evidence_identity", "passed": t4, "observed": f"{sum(row['identity_pass'] for row in r2_rows)}/{len(r2_rows)}", "required": f"{len(r2_rows)}/{len(r2_rows)}"},
        {"gate": "T5", "name": "numerical_and_provenance", "passed": t5, "observed": f"{campaign['pass_processes']}/7 reclaimed={campaign['all_processes_reclaimed']}", "required": "7/7, finite, identity complete"},
        {"gate": "STATUS", "name": "unique_r3_status", "passed": True, "observed": status, "required": json.dumps(configuration["allowed_statuses"], separators=(",", ":"))},
    ]
    _write_csv(outputs[0], r2_rows)
    _write_csv(outputs[1], control_rows)
    _write_csv(outputs[2], gate_rows)
    summary = {
        "schema_version": "sph-pio-poc.stage01dr3.analysis.v1",
        "config_sha256": _sha256(CONFIG_PATH),
        "status": status,
        "t1_cutoff_shell_pass": t1,
        "t2_frozen_topology_pass": t2,
        "t3_support_margin_pass": t3,
        "t4_r2_identity_pass": t4,
        "t5_numerical_provenance_pass": t5,
        "retention_signal_detected": retention_signal,
        "stage01d2_application_eligible": eligible,
        "stage01d_status": "V2_FAIL",
        "stage01dr_status": "RESOURCE_FAIL_LINEAR_GROWTH",
        "stage01dr2_status": "ATTRIBUTION_UNRESOLVED",
        "stage01d2_started": False,
        "v3_started": False,
        "stage02_started": False,
    }
    _write_json(outputs[3], summary)
    _write_text(outputs[4], status + "\n")
    _figures(control_rows)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
