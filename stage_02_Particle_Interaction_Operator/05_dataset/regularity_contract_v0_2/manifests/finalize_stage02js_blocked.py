#!/usr/bin/env python3
"""Finalize Stage 02J-S after the preregistered development gate remains closed."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_2"
AUDIT_PATH = ROOT / "manifests/run_stage02js_regularity_audit.py"
FREEZE_PATH = ROOT / "freeze/stage02js_input_freeze_manifest.json"
RELEASE_PATH = ROOT / "heldout_validation/heldout_release_gate.json"
PREREG_PATH = STAGE / "05_dataset/controlled_multifamily_pair_scope_v0_2/family_design/family_preregistration.yaml"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite finalization: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def module() -> Any:
    spec = importlib.util.spec_from_file_location("stage02js_audit_finalizer", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(AUDIT_PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main() -> int:
    freeze = load_json(FREEZE_PATH)
    release = load_json(RELEASE_PATH)
    if release["heldout_access_authorized"]:
        raise RuntimeError("This finalizer is only valid for a closed held-out gate")
    audit = module()
    contexts = {case_id: audit.context_from_record(case_id) for case_id in audit.PV_CASES}
    contexts.update(audit.new_contexts(("FAMILY_CROSSMODE_A",)))
    rows = audit.original_gate_rows(contexts)
    original = {
        "audit_version": "stage02js-v0.1-development-reproduction-0.2.0",
        "seed": 20260207, "threshold_max": 0.8,
        "requested_total_case_count": 20, "executed_case_count": len(rows),
        "executed_scope": ["FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A"],
        "heldout_scope_not_executed": ["FAMILY_DIAGONAL_B", "FAMILY_MIXED_C"],
        "heldout_nonexecution_reason": "negative_control_gate_FAIL_before_heldout_release",
        "rows": rows,
        "all_available_historical_comparisons_exact": all(row["exact_reproduction_status"] == "PASS" for row in rows),
        "v0_1_result_preserved": True, "v0_1_corrected_or_deleted": False,
        "full_20_case_exact_reproduction_complete": False,
    }
    write(ROOT / "development_audit/original_gate_reproduction.json", original)

    prereg = yaml.safe_load(PREREG_PATH.read_text(encoding="utf-8"))
    role_map = {row["family_id"]: row["split_role"] for row in prereg["families"]}
    decisions = []
    for family_id, prefix in audit.FAMILY_PREFIX.items():
        for group, entries in prereg["case_template"].items():
            for entry in entries:
                case_id = f"{prefix}_{entry['case_suffix']}"
                if family_id == "FAMILY_CROSSMODE_A":
                    reason = "v0_2_global_negative_control_discrimination_FAIL"
                    evidence = "development_metrics_computed_but_contract_not_valid_for_upgrade"
                else:
                    reason = "heldout_gate_closed_not_evaluated"
                    evidence = "target_arrays_not_opened_after_failed_development_gate"
                decisions.append({
                    "case_id": case_id, "family_id": family_id, "prefrozen_split_role": role_map[family_id],
                    "historical_status_v0_1": "diagnostic_nonmaterialized_candidate_v0_1",
                    "historical_candidate_discretization_target": False,
                    "candidate_discretization_target_v0_2": False,
                    "v0_2_decision": "NOT_UPGRADED", "reason_code": reason, "evidence_scope": evidence,
                    "manual_override_permitted": False,
                })
    requalification = {
        "decision_version": "stage02js-versioned-requalification-blocked-0.2.0",
        "contract_hash": freeze["contract_hash"], "decision_count": len(decisions), "decisions": decisions,
        "all_three_new_families_5_of_5_PASS": False,
        "candidate_discretization_target_v0_2_count": 0,
        "v0_1_fields_overwritten": False, "partial_case_selection_used": False,
    }
    write(ROOT / "requalification/versioned_target_requalification.json", requalification)

    common = {
        "contract_hash": freeze["contract_hash"], "heldout_access_authorized": False,
        "blocking_reason_code": "NEGATIVE_CONTROL_DISCRIMINATION_FAIL",
        "manual_override_permitted": False,
    }
    write(ROOT / "materialization/materialization_decision.json", {
        **common, "dataset_version": "controlled_multifamily_pair_scope_v0_3",
        "materialization_authorized": False, "new_graph_records_materialized": 0,
        "existing_graph_records_preserved": 5, "total_full_graph_records": 5,
        "controlled_multifamily_pair_scope_v0_2_modified": False,
    })
    write(ROOT / "leakage/leakage_execution_status.json", {
        **common, "leakage_graph_executed": False, "expected_component_count_if_materialized": 4,
        "observed_component_count": None, "status": "NOT_EXECUTED_UPSTREAM_GATE_CLOSED",
    })
    write(ROOT / "splits/prefrozen_split_status.json", {
        **common, "roles_preserved": {
            "future_train": ["FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A"],
            "future_validation": ["FAMILY_DIAGONAL_B"], "future_test": ["FAMILY_MIXED_C"],
        },
        "split_executed": False, "particle_edge_or_patch_split_used": False,
        "status": "NOT_EXECUTED_NO_20_RECORD_CORPUS",
    })
    write(ROOT / "normalization/train_only_normalization_status.json", {
        **common, "normalization_fitted": False, "train_graph_count": 0,
        "validation_or_test_used": False, "target_or_reference_used": False,
        "statistics_hash": None, "status": "NOT_EXECUTED_SPLIT_NOT_AVAILABLE",
    })
    write(ROOT / "eligibility/dataset_eligibility_results.json", {
        **common, "record_count_in_v0_3": 0, "eligible_for_future_training_count": 0,
        "new_candidate_count": 15, "new_candidate_status": "diagnostic_nonmaterialized_candidate_v0_1",
        "jitter_record_count": 2, "jitter_status": "distribution_shift_diagnostic_only",
        "R3_shear_acoustic_status": "independent_validation_only",
        "fourteen_of_fourteen_not_evaluated_because": "no_v0_3_records_materialized",
        "stage02k_authorized": False,
    })

    mismatches = []
    for relative, expected in freeze["historical_file_hashes_before_stage02js"].items():
        path = REPO / relative
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    history = {
        "verification_version": "stage02js-historical-integrity-0.2.0",
        "expected_file_count": freeze["historical_file_count"],
        "verified_file_count": freeze["historical_file_count"] - len(mismatches),
        "mismatches": mismatches, "all_historical_hashes_unchanged": not mismatches,
        "stage01_modified": any(row["path"].startswith("stage_01_verification/") for row in mismatches),
    }
    write(ROOT / "manifests/historical_integrity_verification.json", history)
    print(json.dumps({"original_executed": len(rows), "new_qualified": 0, "materialized": 0, "historical_unchanged": not mismatches}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
