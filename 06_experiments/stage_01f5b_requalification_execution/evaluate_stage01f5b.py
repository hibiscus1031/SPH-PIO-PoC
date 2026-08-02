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
    status_csv = STAGE / "results/run_status_table.csv"
    if status_csv.exists():
        raise RuntimeError("refusing to overwrite run status table")
    with status_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("run_id", "category", "conditional", "status"))
        writer.writeheader()
        for row in rows:
            writer.writerow({"run_id": row["run_id"], "category": row["category"], "conditional": row["conditional"], "status": statuses[row["run_id"]]})
    if missing:
        payload = {"schema_version": "sph-pio-poc.stage01f5b.evaluation.v1", "missing_evidence": missing, "run_statuses": statuses, "unique_status": "PLATEAU_AWARE_MMS_REQUALIFICATION_EVIDENCE_INCOMPLETE"}
        write_once(STAGE / "results/stage01f5b_evaluation.json", payload)
        return 0
    evidence = {name: load(path) for name, path in required.items()}
    config = yaml.safe_load(CONFIG.read_text())
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
        branch_pass = all(statuses[run_id] == "NOT_TRIGGERED" for run_id in conditional_ids)
    else:
        branch_pass = all(statuses[run_id] == "PASS" for run_id in conditional_ids)
    provenance = {
        "config_sha256": sha(CONFIG),
        "matrix_sha256": sha(MATRIX),
        "space_step_immutable": evidence["space_step"].get("immutable") is True,
        "n64_decision_immutable": evidence["n64"].get("immutable") is True,
        "all_summaries_have_hashes": all((STAGE / "runs" / run_id / "summary.json").exists() and "config_sha256" in load(STAGE / "runs" / run_id / "summary.json") for run_id, state in statuses.items() if state == "PASS"),
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
    known_failure = any(status == "FAIL" for status in statuses.values()) or any(not value for key, value in gate_blocks.items() if key != "unconditional_complete")
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
