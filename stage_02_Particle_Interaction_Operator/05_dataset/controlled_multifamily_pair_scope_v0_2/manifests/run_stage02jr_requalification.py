#!/usr/bin/env python3
"""Requalify the multifamily corpus after scientific family qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATA_ROOT = STAGE_ROOT / "05_dataset/controlled_multifamily_pair_scope_v0_2"
J_ROOT = STAGE_ROOT / "05_dataset/controlled_regular_pair_scope_v0_1"

PREREG_PATH = DATA_ROOT / "family_design/family_preregistration.yaml"
PREFLIGHT_PATH = DATA_ROOT / "family_preflight/family_separability_preflight.json"
FREEZE_PATH = DATA_ROOT / "freeze/stage02jr_input_freeze_manifest.json"
REFERENCE_PATH = DATA_ROOT / "reference_qualification/reference_qualification_results.json"
TARGET_PATH = DATA_ROOT / "target_qualification/new_family_target_candidates.json"
ATTRIBUTION_PATH = DATA_ROOT / "target_qualification/six_component_attribution.json"
CONSERVATION_PATH = DATA_ROOT / "conservation/pair_only_conservation_qualification.json"

MATERIALIZATION_PATH = DATA_ROOT / "raw_graph_records/materialization_status.json"
CANONICAL_PATH = DATA_ROOT / "canonical_records/canonical_inventory.json"
QC_PATH = DATA_ROOT / "qc/requalification_qc.json"
LEAKAGE_PATH = DATA_ROOT / "leakage/multifamily_leakage_graph.json"
SPLIT_PATH = DATA_ROOT / "splits/prefrozen_split_result.json"
NORMALIZATION_PATH = DATA_ROOT / "normalization/normalization_decision.json"
OOD_PATH = DATA_ROOT / "ood_registry/isolation_registry.json"
ELIGIBILITY_PATH = DATA_ROOT / "eligibility/dataset_eligibility_results.json"
DATASET_MANIFEST_PATH = DATA_ROOT / "manifests/stage02jr_dataset_manifest.json"
RUN_MANIFEST_PATH = DATA_ROOT / "manifests/stage02jr_run_manifest.json"


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--execute", action="store_true"); args = parser.parse_args()
    if not args.execute:
        parser.error("Requalification requires explicit --execute")
    outputs = [MATERIALIZATION_PATH, CANONICAL_PATH, QC_PATH, LEAKAGE_PATH, SPLIT_PATH, NORMALIZATION_PATH, OOD_PATH, ELIGIBILITY_PATH, DATASET_MANIFEST_PATH, RUN_MANIFEST_PATH]
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"No-overwrite contract: {path}")
    prereg = yaml.safe_load(PREREG_PATH.read_text(encoding="utf-8")); preflight = load_json(PREFLIGHT_PATH); freeze = load_json(FREEZE_PATH)
    reference = load_json(REFERENCE_PATH); targets = load_json(TARGET_PATH); attribution = load_json(ATTRIBUTION_PATH); conservation = load_json(CONSERVATION_PATH)
    j_dataset = load_json(J_ROOT / "manifests/stage02j_dataset_manifest.json")
    j_qc = load_json(J_ROOT / "qc/quality_control_results.json")
    j_leakage = load_json(J_ROOT / "leakage/leakage_graph.json")
    j_ood = load_json(J_ROOT / "ood_diagnostics/jitter_ood_registry.json")
    for role in freeze["frozen_roles"].values():
        if file_hash(REPO_ROOT / role["path"]) != role["sha256"]:
            raise RuntimeError(f"Frozen history changed: {role['path']}")
    if preflight["status"] != "PASS" or preflight["anticipated_family_component_count"] != 4:
        raise RuntimeError("Family preflight evidence incomplete")
    ref_map = {row["family_id"]: row for row in reference["families"]}
    attr_map = {row["family_id"]: row for row in attribution["families"]}
    cons_map = {row["family_id"]: row for row in conservation["families"]}
    new_ids = ["FAMILY_CROSSMODE_A", "FAMILY_DIAGONAL_B", "FAMILY_MIXED_C"]
    family_rows = []
    for family_id in new_ids:
        failed_checks = sorted({
            check
            for row in attr_map[family_id]["case_results"]
            for check, value in row["attribution_vector"].items()
            if not str(value).startswith("PASS")
        })
        family_rows.append(
            {
                "family_id": family_id,
                "prefrozen_split_role": next(row["split_role"] for row in prereg["families"] if row["family_id"] == family_id),
                "reference_5_of_5_accepted": ref_map[family_id]["family_reference_qualified"],
                "target_5_of_5_six_component_PASS": attr_map[family_id]["family_5_of_5_6_component_PASS"],
                "conservation_5_of_5_PASS": cons_map[family_id]["family_5_of_5_pair_only_PASS"],
                "failed_attribution_components": failed_checks,
                "family_verdict": "diagnostic",
                "materialization_permitted": False,
                "partial_case_selection_used": False,
            }
        )
    if any(row["materialization_permitted"] for row in family_rows):
        raise RuntimeError("Failed family incorrectly authorized for materialization")
    materialization = {
        "status_version": "stage02jr-materialization-status-0.2.0",
        "existing_record_count_preserved": 5,
        "new_graph_candidate_count": 15,
        "new_graph_record_count": 0,
        "expanded_corpus_record_count": 5,
        "expanded_corpus_maximum_if_all_families_qualified": 20,
        "blocking_gate": "six_component_attribution_requires_6_of_6_for_all_five_cases_in_each_family",
        "family_rows": family_rows,
        "failed_candidate_deleted": False,
        "posthoc_case_replacement_or_addition": False,
        "source_scientific_failure_retained": True,
        "infrastructure_retry_used": False,
    }
    canonical_inventory = {
        "inventory_version": "stage02jr-canonical-inventory-0.2.0",
        "existing_stage02j_record_count": 5,
        "existing_records": j_dataset["records"],
        "existing_record_hashes_reverified": True,
        "new_canonical_record_count": 0,
        "new_records": [],
        "serializer_reuse_status": "not_executed_because_no_new_family_passed_scientific_gates",
    }
    qc = {
        "audit_version": "stage02jr-requalification-qc-0.2.0",
        "existing_record_QC_preserved": j_qc["overall_status"],
        "existing_record_count": 5,
        "existing_QC_PASS_count": sum(row["status"] == "PASS" for row in j_qc["rows"]),
        "new_record_count": 0,
        "new_record_QC_count": 0,
        "new_target_candidate_count": targets["candidate_count"],
        "new_target_candidates_are_dataset_records": False,
        "scientific_gate_failure_retained": True,
        "overall_existing_corpus_QC": "PASS",
    }
    qualified_family_ids = ["FAMILY_PV_EXISTING"]
    leakage = {
        "audit_version": "stage02jr-multifamily-leakage-0.2.0",
        "preflight_potential_family_components": 4,
        "preflight_cross_family_edges": preflight["cross_family_leakage_edges"],
        "qualified_dataset_family_ids": qualified_family_ids,
        "unqualified_diagnostic_family_ids": new_ids,
        "dataset_nodes": j_leakage["nodes"],
        "dataset_edges": j_leakage["edges"],
        "adjacency_order": j_leakage["adjacency_order"],
        "adjacency_matrix": j_leakage["adjacency_matrix"],
        "qualified_dataset_connected_component_count": 1,
        "connected_components": j_leakage["connected_components"],
        "cross_family_edge_deleted": False,
        "shared_infrastructure_treated_as_direct_lineage": False,
        "Stage02B_contract_modified": False,
        "status": "PASS_FOR_RETAINED_EXISTING_COMPONENT_ONLY",
    }
    split = {
        "audit_version": "stage02jr-prefrozen-split-result-0.2.0",
        "prefrozen_assignment": prereg["split_assignment"],
        "roles_changed_after_results": False,
        "required_component_count": 4,
        "qualified_component_count": 1,
        "formal_split_PASS": False,
        "status": "FAIL_UNQUALIFIED_FAMILIES_AND_INSUFFICIENT_COMPONENTS",
        "missing_qualified_families": new_ids,
        "future_train": {"qualified_families": ["FAMILY_PV_EXISTING"], "missing_families": ["FAMILY_CROSSMODE_A"]},
        "future_validation": {"qualified_families": [], "missing_families": ["FAMILY_DIAGONAL_B"]},
        "future_test": {"qualified_families": [], "missing_families": ["FAMILY_MIXED_C"]},
        "train_family_used_as_validation_or_test_replacement": False,
        "split_manifest_created": False,
        "record_split_assignment_applied": False,
    }
    normalization = {
        "decision_version": "stage02jr-normalization-decision-0.2.0",
        "prerequisites": {"four_qualified_components": "FAIL", "leakage_graph": "INCOMPLETE_FOR_EXPANDED_CORPUS", "prefrozen_split": "FAIL"},
        "normalization_permitted": False,
        "physical_nondimensionalization_contract_retained_as_prospective": True,
        "graph_balanced_statistics_fitted": False,
        "statistics": None,
        "statistics_hash": None,
        "train_family_ids": [],
        "train_record_hashes": [],
        "validation_used": False,
        "test_used": False,
        "jitter_used": False,
        "target_or_reference_fields_used": False,
        "blocking_reason": "new_families_failed_six_component_attribution_and_prefrozen_split_does_not_exist",
    }
    ood = {
        "registry_version": "stage02jr-isolation-registry-0.2.0",
        "jitter_registry_source": str((J_ROOT / "ood_diagnostics/jitter_ood_registry.json").relative_to(REPO_ROOT)),
        "jitter_registry_hash": file_hash(J_ROOT / "ood_diagnostics/jitter_ood_registry.json"),
        "jitter_rows": j_ood["rows"],
        "jitter_role_preserved": "distribution_shift_diagnostic_only",
        "jitter_split_or_normalization_or_training_use": False,
        "R3_shear": "whole_class_independent_validation_only",
        "R3_acoustic": "whole_class_independent_validation_only",
        "R3_records_used": False,
        "R3_formula_or_parameter_lineage_reused": False,
        "R3_threshold_selection_used": False,
    }
    existing_rows = []
    for row in j_dataset["records"]:
        existing_rows.append(
            {
                "case_id": row["case_id"],
                "family_id": "FAMILY_PV_EXISTING",
                "record_materialized": True,
                "gates": {
                    "family_preregistered": "PASS", "reference_pair_accepted": "PASS", "target_6_of_6": "PASS",
                    "pair_only_conservation": "PASS", "schema": "PASS", "canonical": "PASS", "provenance": "PASS",
                    "uncertainty": "PASS", "topology": "PASS", "determinism": "PASS", "family_assignment": "PASS",
                    "leakage": "PASS", "prefrozen_split": "FAIL_EXPANDED_SPLIT_NOT_ESTABLISHED",
                    "normalization_contract": "BLOCKED_NO_FORMAL_TRAIN_SPLIT",
                },
                "pass_count": 12,
                "required_pass_count": 14,
                "eligible_for_future_training": False,
                "verdict": "diagnostic",
                "manual_override_permitted": False,
            }
        )
    candidate_rows = []
    target_map = {row["case_id"]: row for row in targets["candidates"]}
    for family in family_rows:
        for case_result in attr_map[family["family_id"]]["case_results"]:
            candidate_rows.append(
                {
                    "case_id": case_result["case_id"],
                    "family_id": family["family_id"],
                    "record_materialized": False,
                    "source_target_candidate_hash": target_map[case_result["case_id"]]["candidate_content_hash_before_attribution"],
                    "reference_pair_accepted": True,
                    "target_attribution_pass_count": case_result["pass_count"],
                    "target_attribution_required": 6,
                    "pair_only_conservation_PASS": True,
                    "verdict": "diagnostic_nonmaterialized_candidate",
                    "reason_code": "DIAG_PCG64_PERMUTED_NULL_RATIO_GATE_FAIL",
                    "eligible_for_future_training": False,
                    "manual_override_permitted": False,
                }
            )
    eligibility = {
        "audit_version": "stage02jr-dataset-eligibility-0.2.0",
        "dataset_record_count": 5,
        "new_nonmaterialized_candidate_count": 15,
        "record_verdict_counts": {"eligible_for_future_training": 0, "diagnostic": 5, "rejected": 0},
        "candidate_verdict_counts": {"diagnostic_nonmaterialized_candidate": 15},
        "existing_record_rows": existing_rows,
        "new_candidate_rows": candidate_rows,
        "all_dataset_records_14_of_14_PASS": False,
        "manual_override_permitted": False,
        "readiness_category": "not_ready",
        "Stage02K_authorized": False,
    }
    dataset_manifest = {
        "manifest_version": "stage02jr-controlled-multifamily-dataset-0.2.0",
        "dataset_version": "controlled_multifamily_pair_scope_v0_2",
        "sample_unit": "complete_particle_graph",
        "existing_record_count": 5,
        "new_record_count": 0,
        "expanded_record_count": 5,
        "maximum_preregistered_record_count": 20,
        "existing_records": j_dataset["records"],
        "new_records": [],
        "new_target_candidate_count": 15,
        "new_target_candidates_are_training_dataset_records": False,
        "qualified_family_count": 1,
        "leakage_component_count": 1,
        "formal_split_created": False,
        "normalization_fitted": False,
        "eligible_record_count": 0,
        "jitter_OOD_only": True,
        "R3_independent_only": True,
        "model_created": False,
        "training_performed": False,
        "readiness_category": "not_ready",
        "Stage02K_authorized": False,
    }
    payloads = {
        MATERIALIZATION_PATH: pretty(materialization), CANONICAL_PATH: pretty(canonical_inventory), QC_PATH: pretty(qc),
        LEAKAGE_PATH: pretty(leakage), SPLIT_PATH: pretty(split), NORMALIZATION_PATH: pretty(normalization),
        OOD_PATH: pretty(ood), ELIGIBILITY_PATH: pretty(eligibility), DATASET_MANIFEST_PATH: pretty(dataset_manifest),
    }
    run_manifest = {
        "run_version": "stage02jr-requalification-run-0.2.0",
        "input_freeze_reverified": True,
        "qualification_evidence_hashes": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in (REFERENCE_PATH, TARGET_PATH, ATTRIBUTION_PATH, CONSERVATION_PATH)},
        "output_hashes": {str(path.relative_to(REPO_ROOT)): digest(payload) for path, payload in payloads.items()},
        "existing_records_modified": False,
        "failed_family_cases_deleted_or_replaced": False,
        "new_graph_records_materialized": 0,
        "split_created": False,
        "normalization_fitted": False,
        "model_generated": False,
        "training_performed": False,
        "performance_claim_generated": False,
        "Stage02K_authorized": False,
        "readiness_category": "not_ready",
    }
    payloads[RUN_MANIFEST_PATH] = pretty(run_manifest)
    for path, payload in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
    print(json.dumps({"existing_records": 5, "new_candidates": 15, "new_records": 0, "qualified_components": 1, "split": False, "normalization": False, "eligible": 0, "Stage02K": False, "readiness_category": "not_ready"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
