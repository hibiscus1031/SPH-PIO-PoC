"""Final unique-status evaluator for Stage 01F5B."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
CONFIG = STAGE / "configs/stage01f5b_execution.yml"
MATRIX = ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/stage01f5_execution_run_matrix_v2.csv"
PREEXECUTION_ARTIFACTS = STAGE / "manifests/preexecution_artifact_manifest.csv"
POSTEXECUTION_AMENDMENT = STAGE / "manifests/postexecution_evaluator_amendment.json"
INFRA_ORIGINAL = "f5_n64_smoke_a"
INFRA_RETRY = "f5_n64_smoke_a_infra_retry1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def marker(run_id: str) -> str:
    path = STAGE / "runs" / run_id / "status.json"
    return load(path)["status"] if path.exists() else "MISSING"


def evaluator_amendment_provenance() -> tuple[dict[str, Any], bool]:
    amendment = load(POSTEXECUTION_AMENDMENT) if POSTEXECUTION_AMENDMENT.exists() else {}
    with PREEXECUTION_ARTIFACTS.open() as stream:
        preexecution_rows = list(csv.DictReader(stream))
    evaluator_path = Path(__file__).resolve().relative_to(ROOT).as_posix()
    recorded_before = next((row["sha256"] for row in preexecution_rows if row["path"] == evaluator_path), None)
    checks = {
        "manifest_present": bool(amendment),
        "preexecution_sha_matches_frozen_manifest": amendment.get("preexecution_evaluator_sha256") == recorded_before,
        "postexecution_sha_matches_current_evaluator": amendment.get("postexecution_evaluator_sha256") == sha(Path(__file__)),
        "scope_is_infrastructure_retry_reconciliation_only": amendment.get("scope") == "infrastructure_retry_reconciliation_only",
        "numerical_execution_was_complete": amendment.get("numerical_execution_complete") is True,
        "no_scientific_gate_or_threshold_change": amendment.get("scientific_gate_or_threshold_change") is False,
        "no_numerical_source_runner_config_change": amendment.get("numerical_source_runner_config_change") is False,
    }
    return {**amendment, "checks": checks}, all(checks.values())


def infrastructure_retry_reconciliation(config: dict[str, Any], space_step: dict[str, Any]) -> dict[str, Any]:
    """Validate the single protocol-authorized, non-numerical smoke retry.

    This does not change a scientific gate.  It preserves the original FAIL and
    only supplies the effective predecessor state used by the frozen N64 DAG.
    """
    original_dir = STAGE / "runs" / INFRA_ORIGINAL
    retry_dir = STAGE / "runs" / INFRA_RETRY
    failure_path = original_dir / "infrastructure_failure.json"
    original_status_path = original_dir / "status.json"
    retry_status_path = retry_dir / "status.json"
    retry_summary_path = retry_dir / "summary.json"
    retry_checkpoint = STAGE / "checkpoints" / f"{INFRA_RETRY}.npz"
    original_numerical_outputs = [
        original_dir / "summary.json",
        STAGE / "checkpoints" / f"{INFRA_ORIGINAL}.npz",
        STAGE / "references" / f"{INFRA_ORIGINAL}.npz",
    ]
    retry_siblings = sorted(path.parent.name for path in (STAGE / "runs").glob(f"{INFRA_ORIGINAL}_infra_retry*/status.json"))

    required_paths = (failure_path, original_status_path, retry_status_path, retry_summary_path, retry_checkpoint)
    if not all(path.exists() for path in required_paths):
        return {
            "original_run_id": INFRA_ORIGINAL,
            "retry_run_id": INFRA_RETRY,
            "eligible": False,
            "checks": {"required_evidence_complete": False},
        }

    failure = load(failure_path)
    original_status = load(original_status_path)
    retry_status = load(retry_status_path)
    retry_summary = load(retry_summary_path)
    chosen_dt = float(space_step["chosen_dt_space"])
    checks = {
        "required_evidence_complete": True,
        "classification_is_pure_non_solver_infrastructure": failure.get("classification") == "PURE_INFRASTRUCTURE_NON_SOLVER_ORCHESTRATION",
        "solver_worker_not_launched": failure.get("solver_worker_launched") is False,
        "no_numerical_state_generated": failure.get("numerical_state_generated") is False and original_status.get("numerical_state_generated") is False,
        "original_evidence_retained": failure.get("original_evidence_retained") is True,
        "original_raw_status_is_fail": original_status.get("status") == "FAIL",
        "retry_authorization_matches": failure.get("retry_authorized") == INFRA_RETRY and original_status.get("retry_run_id") == INFRA_RETRY,
        "exactly_one_retry_id": retry_siblings == [INFRA_RETRY],
        "original_has_no_numerical_outputs": not any(path.exists() for path in original_numerical_outputs),
        "retry_raw_status_is_pass": retry_status.get("status") == "PASS" and retry_summary.get("status") == "PASS",
        "retry_parameters_match_frozen_smoke": (
            retry_summary.get("solution") == "MMS_A"
            and retry_summary.get("resolution") == 64
            and math.isclose(float(retry_summary.get("support_ratio", math.nan)), 6.041381265149109, rel_tol=0.0, abs_tol=0.0)
            and retry_summary.get("steps") == 20
            and math.isclose(float(retry_summary.get("dt", math.nan)), chosen_dt, rel_tol=0.0, abs_tol=0.0)
            and math.isclose(float(retry_summary.get("t_final", math.nan)), 20.0 * chosen_dt, rel_tol=0.0, abs_tol=0.0)
            and retry_summary.get("config_sha256") == sha(CONFIG)
        ),
        "retry_checkpoint_present": retry_checkpoint.exists(),
        "frozen_retry_policy_unchanged": config["n64_branch"]["smoke_steps"] == 20,
    }
    return {
        "original_run_id": INFRA_ORIGINAL,
        "retry_run_id": INFRA_RETRY,
        "original_raw_status": original_status.get("status"),
        "retry_raw_status": retry_status.get("status"),
        "effective_predecessor_status": "PASS" if all(checks.values()) else "FAIL",
        "eligible": all(checks.values()),
        "checks": checks,
        "original_failure_sha256": sha(failure_path),
        "retry_summary_sha256": sha(retry_summary_path),
        "retry_checkpoint_sha256": sha(retry_checkpoint),
    }


def gci_assessment(spatial: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for solution, case in spatial["cases"].items():
        output[solution] = {}
        for field, item in case["fields"].items():
            errors, orders = item["errors"], item["local_orders"]
            monotone = all(errors[i + 1] < errors[i] for i in range(len(errors) - 1))
            same_sign = all(order > 0 for order in orders) or all(order < 0 for order in orders)
            changes = [abs(orders[i + 1] - orders[i]) / max(abs(orders[i]), 1.0e-300) for i in range(len(orders) - 1)]
            finite_extrapolation = math.isfinite(errors[-1] + (errors[-1] - errors[-2]) / max((48 / 32) ** max(orders[-1], 1.0e-12) - 1.0, 1.0e-300))
            qualified = monotone and same_sign and all(change <= 0.25 for change in changes) and finite_extrapolation
            output[solution][field] = {
                "qualified": qualified,
                "local_order_relative_changes": changes,
                "statement": "GCI applies only to the preregistered increasing-neighbor consistency path and is not a fixed-stencil single-h GCI." if qualified else "GCI not justified",
            }
    return output


def main() -> int:
    required = {
        "preflight": STAGE / "results/preflight_audit_attempt2.json",
        "references": STAGE / "results/reference_qualification.json",
        "time": STAGE / "results/time_and_platform_analysis.json",
        "space": STAGE / "results/spatial_analysis.json",
        "determinism": STAGE / "results/determinism.json",
        "space_step": STAGE / "manifests/space_step_decision.json",
        "n64": STAGE / "manifests/n64_trigger_decision.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    with MATRIX.open() as stream:
        rows = list(csv.DictReader(stream))
    statuses = {row["run_id"]: marker(row["run_id"]) for row in rows}
    if missing:
        payload = {"schema_version": "sph-pio-poc.stage01f5b.evaluation.v1", "missing_evidence": missing, "run_statuses": statuses, "unique_status": "PLATEAU_AWARE_MMS_REQUALIFICATION_EVIDENCE_INCOMPLETE"}
        write_once(STAGE / "results/stage01f5b_evaluation.json", payload)
        return 0
    evidence = {name: load(path) for name, path in required.items()}
    config = yaml.safe_load(CONFIG.read_text())
    evaluator_amendment, evaluator_amendment_valid = evaluator_amendment_provenance()
    reconciliation = infrastructure_retry_reconciliation(config, evidence["space_step"])
    effective_statuses = dict(statuses)
    if reconciliation["eligible"]:
        effective_statuses[INFRA_ORIGINAL] = reconciliation["effective_predecessor_status"]
    status_csv = STAGE / "results/run_status_table.csv"
    if status_csv.exists():
        raise RuntimeError("refusing to overwrite run status table")
    with status_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("run_id", "category", "conditional", "status", "effective_status"))
        writer.writeheader()
        for row in rows:
            writer.writerow({"run_id": row["run_id"], "category": row["category"], "conditional": row["conditional"], "status": statuses[row["run_id"]], "effective_status": effective_statuses[row["run_id"]]})
        writer.writerow({"run_id": INFRA_RETRY, "category": "conditional_n64_smoke_infrastructure_retry", "conditional": "true", "status": marker(INFRA_RETRY), "effective_status": marker(INFRA_RETRY)})
    unconditional = [row["run_id"] for row in rows if row["conditional"] == "false"]
    unconditional_complete = all(statuses[run_id] in {"PASS", "FAIL"} for run_id in unconditional)
    hard_runs_pass = all(statuses[run_id] == "PASS" for run_id in unconditional)
    reference_pass = evidence["references"]["status"] == "PASS"
    main_checks = evidence["time"]["main_checks"]
    held_checks = dict(evidence["time"]["heldout_checks"])
    held_checks["H5"] = reference_pass and evidence["determinism"]["status"] == "PASS" and all(statuses[run_id] == "PASS" for run_id in unconditional if "hold_" in run_id)
    spatial_checks = evidence["space"]["checks"]
    decision = evidence["n64"]["decision"]
    conditional_ids = [row["run_id"] for row in rows if row["conditional"] == "true"]
    if decision == "NOT_TRIGGERED":
        branch_pass = all(effective_statuses[run_id] == "NOT_TRIGGERED" for run_id in conditional_ids)
    else:
        branch_pass = all(effective_statuses[run_id] == "PASS" for run_id in conditional_ids)
    provenance = {
        "config_sha256": sha(CONFIG),
        "matrix_sha256": sha(MATRIX),
        "space_step_immutable": evidence["space_step"].get("immutable") is True,
        "n64_decision_immutable": evidence["n64"].get("immutable") is True,
        "all_summaries_have_hashes": all((STAGE / "runs" / run_id / "summary.json").exists() and "config_sha256" in load(STAGE / "runs" / run_id / "summary.json") for run_id, state in statuses.items() if state == "PASS"),
        "authorized_infrastructure_retry_provenance": reconciliation["eligible"],
        "postexecution_evaluator_amendment": evaluator_amendment_valid,
    }
    gate_blocks = {
        "preflight": evidence["preflight"]["status"] == "PASS",
        "unconditional_complete": unconditional_complete,
        "all_unconditional_hard_and_reference_runs_pass": hard_runs_pass,
        "reference_qualification": reference_pass,
        "T1_T5_P1_P3": all(main_checks.values()),
        "H1_H5": all(held_checks.values()),
        "space_step_decision": evidence["space_step"].get("immutable") is True,
        "S1_S4": all(spatial_checks.values()),
        "determinism": evidence["determinism"]["status"] == "PASS",
        "n64_branch": branch_pass,
        "provenance": all(provenance.values()),
    }
    unreconciled_failures = [run_id for run_id, status in statuses.items() if status == "FAIL" and effective_statuses[run_id] != "PASS"]
    known_failure = bool(unreconciled_failures) or any(not value for key, value in gate_blocks.items() if key != "unconditional_complete")
    incomplete = not unconditional_complete or any(status in {"MISSING", "PENDING", "RUNNING"} for status in statuses.values())
    if all(gate_blocks.values()):
        unique = "PLATEAU_AWARE_MMS_REQUALIFICATION_PASS"
    elif known_failure:
        unique = "PLATEAU_AWARE_MMS_REQUALIFICATION_FAIL"
    elif incomplete:
        unique = "PLATEAU_AWARE_MMS_REQUALIFICATION_EVIDENCE_INCOMPLETE"
    else:
        unique = "PLATEAU_AWARE_MMS_REQUALIFICATION_EVIDENCE_INCOMPLETE"
    payload = {
        "schema_version": "sph-pio-poc.stage01f5b.evaluation.v1",
        "run_statuses": statuses,
        "effective_run_statuses": effective_statuses,
        "infrastructure_retry_reconciliation": reconciliation,
        "postexecution_evaluator_amendment": evaluator_amendment,
        "unreconciled_failures": unreconciled_failures,
        "gate_blocks": gate_blocks,
        "main_checks": main_checks,
        "heldout_checks": held_checks,
        "spatial_checks": spatial_checks,
        "n64_decision": decision,
        "provenance": provenance,
        "gci": gci_assessment(evidence["space"]),
        "stage01g_application_eligible": unique == "PLATEAU_AWARE_MMS_REQUALIFICATION_PASS",
        "stage01g_started": False,
        "v3_started": False,
        "stage02_started": False,
        "training_started": False,
        "labels_generated": False,
        "unique_status": unique,
    }
    write_once(STAGE / "results/stage01f5b_evaluation.json", payload)
    print(unique)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
