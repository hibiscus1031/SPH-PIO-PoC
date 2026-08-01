"""Evaluate the preregistered Stage 01D-R4 semantic gates."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr4_weakref_semantics"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_weakref_semantics.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
R2_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution" / "results"
R3_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation" / "results"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _evidence_identity(configuration: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    expected = configuration["r2_r3_frozen_evidence"]
    paths = {
        "r2_edge_working_set_models.csv": R2_RESULTS / "edge_working_set_models.csv",
        "r2_weakref_lifetime_summary.csv": R2_RESULTS / "weakref_lifetime_summary.csv",
        "r3_control_summary.csv": R3_RESULTS / "control_summary.csv",
        "r3_gate_evidence.csv": R3_RESULTS / "r3_gate_evidence.csv",
        "r3_classification_correction.json": R3_RESULTS / "classification_correction.json",
        "r3_cutoff_shell_audit_summary.json": R3_RESULTS / "cutoff_shell_audit_summary.json",
    }
    rows: list[dict[str, Any]] = []
    identity = True
    for name, path in paths.items():
        observed = _sha256(path)
        passed = observed == str(expected[name])
        identity = identity and passed
        rows.append(
            {
                "evidence": name,
                "expected_sha256": expected[name],
                "observed_sha256": observed,
                "identity_pass": passed,
            }
        )
    models = _read_csv(paths["r2_edge_working_set_models.csv"])
    models_pass = len(models) == 4 and all(
        abs(float(row["total_edge_coefficient"]) - float(expected["required_beta_edge_bytes_per_edge"])) <= 1.0e-9
        and float(row["total_step_ci95_lower"]) <= 0.0 <= float(row["total_step_ci95_upper"])
        and abs(float(row["total_step_coefficient"])) <= float(expected["beta_step_absolute_limit_bytes_per_step"])
        and float(row["unknown_step_coefficient"]) == float(expected["gamma_step_required_bytes_per_step"])
        for row in models
    )
    r2_lifetime = _read_csv(paths["r2_weakref_lifetime_summary.csv"])
    r2_old_zero = all(
        int(row["maximum_old_survivor_storage_count"]) == 0
        and int(row["maximum_old_survivor_bytes"]) == 0
        for row in r2_lifetime
    )
    r3_controls = _read_csv(paths["r3_control_summary.csv"])
    r3_old_zero = all(
        int(row["maximum_old_survivor_storage_count"]) == 0
        and int(row["maximum_old_survivor_bytes"]) == 0
        for row in r3_controls
    )
    control_m_pass = len([row for row in r3_controls if row["control"] == "M" and _bool(row["pass"])]) == 3
    cutoff = _read_json(paths["r3_cutoff_shell_audit_summary.json"])
    cutoff_pass = bool(
        cutoff["edge_count_values"] == [82940, 82942, 82944]
        and cutoff["all_switches_on_q5_shell"]
        and cutoff["all_switches_near_cutoff"]
    )
    semantic_checks = {
        "r2_model_semantics": models_pass,
        "r2_old_survivor_zero": r2_old_zero,
        "r3_old_survivor_zero": r3_old_zero,
        "r3_control_m_3_of_3": control_m_pass,
        "r3_cutoff_shell_explanation": cutoff_pass,
    }
    rows.extend(
        {
            "evidence": f"semantic:{name}",
            "expected_sha256": "n/a",
            "observed_sha256": "n/a",
            "identity_pass": passed,
        }
        for name, passed in semantic_checks.items()
    )
    return rows, bool(identity and all(semantic_checks.values()))


def main() -> int:
    outputs = {
        "fixtures": RESULTS_ROOT / "fixture_summary.csv",
        "controls": RESULTS_ROOT / "control_f_semantic_summary.csv",
        "fifteen": RESULTS_ROOT / "fifteen_reference_identity.csv",
        "identity": RESULTS_ROOT / "evidence_identity.csv",
        "gates": RESULTS_ROOT / "r4_gate_evidence.csv",
        "analysis": RESULTS_ROOT / "analysis_summary.json",
        "status": RESULTS_ROOT / "stage01dr4_status.txt",
    }
    if any(path.exists() for path in outputs.values()):
        raise RuntimeError("R4 analysis outputs already exist")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    config_hash = _sha256(CONFIG_PATH)
    fixture_rows: list[dict[str, Any]] = []
    fixtures_pass = True
    retention_fixture_detected = True
    for repeat in (1, 2, 3):
        for fixture in configuration["fixtures"]["names"]:
            run_id = f"stage01dr4_fixture_{str(fixture).lower()}_r{repeat}"
            summary = _read_json(RESULTS_ROOT / "fixture_summaries" / f"{run_id}.json")
            exit_data = _read_json(RESULTS_ROOT / "process_exit" / f"{run_id}.json")
            expected_retention = bool(configuration["fixtures"]["expected_retention"][fixture])
            passed = bool(
                summary["status"] == "PASS"
                and bool(summary["expected_retention"]) == expected_retention
                and bool(summary["classified_correctly"])
                and exit_data["process_reclaimed"] is True
                and summary["config_sha256"] == config_hash
            )
            fixtures_pass = fixtures_pass and passed
            if fixture == "C":
                retention_fixture_detected = bool(
                    retention_fixture_detected
                    and int(summary["peak_old_survivor_storage_count"]) > 0
                    and int(summary["peak_same_slot_multigeneration_count"]) > 0
                )
            fixture_rows.append(
                {
                    "run_id": run_id,
                    "fixture": fixture,
                    "repeat": repeat,
                    "expected_retention": expected_retention,
                    "peak_current_persistent": summary["peak_current_persistent_reference_count"],
                    "peak_old_survivor_storage_count": summary["peak_old_survivor_storage_count"],
                    "peak_same_slot_multigeneration_count": summary["peak_same_slot_multigeneration_count"],
                    "process_reclaimed": exit_data["process_reclaimed"],
                    "pass": passed,
                }
            )
    control_rows: list[dict[str, Any]] = []
    control_pass = True
    retention_redetected = False
    canonical_rows: list[dict[str, str]] = []
    for repeat in (1, 2, 3):
        run_id = f"stage01dr4_f_r{repeat}"
        summary = _read_json(RESULTS_ROOT / "run_summaries" / f"{run_id}.json")
        semantic = _read_json(RESULTS_ROOT / "semantic_summaries" / f"{run_id}.json")
        audit = _read_csv(RESULTS_ROOT / "semantic_weakref_audit" / f"{run_id}.csv")
        ledger = _read_csv(RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv")
        exit_data = _read_json(RESULTS_ROOT / "process_exit" / f"{run_id}.json")
        unknown_delta = int(ledger[-1]["unknown_live_bytes"]) - int(ledger[0]["unknown_live_bytes"])
        explicit_referrers = int(summary["referrer_chain_count"])
        passed = bool(
            summary["status"] == "PASS"
            and int(summary["completed_steps"]) == int(configuration["control_f"]["steps"])
            and int(summary["unique_force_stage_edge_counts"]) == 1
            and int(summary["unique_force_stage_edge_identities"]) == 1
            and len(audit) == int(configuration["qualification"]["required_audited_age2_references_per_run"])
            and all(_bool(row["is_current_working_set"]) for row in audit)
            and all(not _bool(row["is_retired_reference"]) for row in audit)
            and int(semantic["maximum_semantic_old_survivor_storage_count"]) == 0
            and int(semantic["maximum_semantic_same_slot_multigeneration_count"]) == 0
            and unknown_delta == 0
            and explicit_referrers == 0
            and bool(summary["all_state_values_finite"])
            and exit_data["process_reclaimed"] is True
            and summary["config_sha256"] == config_hash
        )
        retention_redetected = bool(
            retention_redetected
            or int(semantic["maximum_semantic_old_survivor_storage_count"]) > 0
            or int(semantic["maximum_semantic_same_slot_multigeneration_count"]) > 0
            or explicit_referrers > 0
        )
        control_pass = control_pass and passed
        control_rows.append(
            {
                "run_id": run_id,
                "repeat": repeat,
                "completed_steps": summary["completed_steps"],
                "edge_count_values": json.dumps(summary["force_stage_edge_counts"], separators=(",", ":")),
                "unique_edge_identities": summary["unique_force_stage_edge_identities"],
                "age2_audited_references": len(audit),
                "current_persistent_references": sum(_bool(row["is_current_working_set"]) for row in audit),
                "retired_references": sum(_bool(row["is_retired_reference"]) for row in audit),
                "old_survivor_storage_count": semantic["maximum_semantic_old_survivor_storage_count"],
                "same_slot_multigeneration_count": semantic["maximum_semantic_same_slot_multigeneration_count"],
                "unknown_live_bytes_delta": unknown_delta,
                "explicit_referrer_chain_count": explicit_referrers,
                "state_finite": summary["all_state_values_finite"],
                "process_reclaimed": exit_data["process_reclaimed"],
                "pass": passed,
            }
        )
        if repeat == 1:
            canonical_rows = audit
    identity_rows, evidence_pass = _evidence_identity(configuration)
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    provenance_pass = bool(
        campaign["expected_processes"] == 15
        and campaign["observed_processes"] == 15
        and campaign["pass_processes"] == 15
        and campaign["all_processes_reclaimed"]
    )
    if retention_redetected:
        status = "R4_RETENTION_REDETECTED"
    elif not fixtures_pass or not retention_fixture_detected or not evidence_pass:
        status = "R4_GATE_VALIDATION_FAIL"
    elif control_pass and provenance_pass and len(canonical_rows) == 15:
        status = "R4_WEAKREF_GATE_SEMANTICS_CONFIRMED"
    else:
        status = "R4_UNRESOLVED"
    if status not in set(configuration["allowed_statuses"]):
        raise RuntimeError("R4 status is not preregistered")
    eligible = status in set(configuration["stage01d2_application_eligible_statuses"])
    gate_rows = [
        {"gate": "G1", "name": "fifteen_reference_identity", "passed": control_pass, "observed": f"{len(canonical_rows)}/15 canonical; F={sum(row['pass'] for row in control_rows)}/3", "required": "15/15 current, 0 retired; F 3/3"},
        {"gate": "G2", "name": "fixture_validation", "passed": fixtures_pass and retention_fixture_detected, "observed": f"{sum(row['pass'] for row in fixture_rows)}/12", "required": "12/12 including positive leak detection"},
        {"gate": "G3", "name": "frozen_evidence_identity", "passed": evidence_pass, "observed": f"{sum(row['identity_pass'] for row in identity_rows)}/{len(identity_rows)}", "required": f"{len(identity_rows)}/{len(identity_rows)}"},
        {"gate": "G4", "name": "process_and_provenance", "passed": provenance_pass, "observed": f"{campaign['pass_processes']}/15 reclaimed={campaign['all_processes_reclaimed']}", "required": "15/15, all reclaimed"},
        {"gate": "STATUS", "name": "unique_r4_status", "passed": True, "observed": status, "required": json.dumps(configuration["allowed_statuses"], separators=(",", ":"))},
    ]
    _write_csv(outputs["fixtures"], fixture_rows)
    _write_csv(outputs["controls"], control_rows)
    _write_csv(outputs["fifteen"], canonical_rows)
    _write_csv(outputs["identity"], identity_rows)
    _write_csv(outputs["gates"], gate_rows)
    analysis = {
        "schema_version": "sph-pio-poc.stage01dr4.analysis.v1",
        "config_sha256": config_hash,
        "status": status,
        "fifteen_reference_identity_pass": control_pass,
        "fixtures_pass": fixtures_pass and retention_fixture_detected,
        "retention_redetected": retention_redetected,
        "evidence_identity_pass": evidence_pass,
        "provenance_pass": provenance_pass,
        "stage01d2_application_eligible": eligible,
        "stage01d_status": "V2_FAIL",
        "stage01dr_status": "RESOURCE_FAIL_LINEAR_GROWTH",
        "stage01dr2_status": "ATTRIBUTION_UNRESOLVED",
        "stage01dr3_status": "R3_CONFIRMATION_UNRESOLVED",
        "stage01d2_started": False,
        "v3_started": False,
        "stage02_started": False,
    }
    _write_json(outputs["analysis"], analysis)
    outputs["status"].write_text(status + "\n", encoding="utf-8")
    print(json.dumps(analysis, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
