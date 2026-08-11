#!/usr/bin/env python3
"""Freeze Stage 02J-R historical and preregistered inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATA_ROOT = STAGE_ROOT / "05_dataset/controlled_multifamily_pair_scope_v0_2"
J_ROOT = STAGE_ROOT / "05_dataset/controlled_regular_pair_scope_v0_1"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
OUTPUT = DATA_ROOT / "freeze/stage02jr_input_freeze_manifest.json"
PREREG = DATA_ROOT / "family_design/family_preregistration.yaml"
FORMULAS = DATA_ROOT / "family_design/analytic_family_definitions.py"

ROLE_PATHS = {
    "stage02j_final_report": STAGE_ROOT / "07_reports/stage02j_final_report.md",
    "stage02j_dataset_manifest": J_ROOT / "manifests/stage02j_dataset_manifest.json",
    "stage02j_leakage_graph": J_ROOT / "leakage/leakage_graph.json",
    "stage02j_split_feasibility": J_ROOT / "splits/split_feasibility.json",
    "stage02j_normalization_specification": J_ROOT / "normalization/prospective_normalization_contract.yaml",
    "stage02j_eligibility_results": J_ROOT / "eligibility/record_eligibility_results.json",
    "stage02ir_architecture_scope": ATTR_ROOT / "conservation_closure/architecture_scope/architecture_scope_decision.json",
    "stage02i_seven_targets": ATTR_ROOT / "qualified_spatial_targets/targets/spatial_target_candidates.json",
    "stage02h_acceptance_rules": ATTR_ROOT / "acceptance/reference_acceptance_rules.yaml",
    "stage02h_acceptance_results": ATTR_ROOT / "acceptance/reference_acceptance_results.json",
    "stage02b_schema": STAGE_ROOT / "03_dataset/schema/pio_dataset_schema.json",
    "stage02b_eligibility": STAGE_ROOT / "03_dataset/eligibility/label_eligibility_rules.yaml",
    "stage02b_split": STAGE_ROOT / "03_dataset/splitting/split_strategy.md",
    "stage02b_leakage": STAGE_ROOT / "03_dataset/splitting/split_strategy.md",
    "stage02b_uncertainty": STAGE_ROOT / "03_dataset/uncertainty/uncertainty_contract.md",
    "stage02a_conservation": STAGE_ROOT / "02_operator_design/constraints/pio_conservation_contract.md",
    "stage02j_extension_schema": J_ROOT / "schema/stage02j_graph_record_schema.json",
    "stage02j_feature_permission": J_ROOT / "schema/feature_permission_table.yaml",
    "stage02j_serializer_contract": J_ROOT / "schema/canonical_serialization_contract.yaml",
    "stage02j_serializer_implementation": J_ROOT / "manifests/run_stage02j_controlled_dataset.py",
    "stage02jr_family_preregistration": PREREG,
    "stage02jr_analytic_definitions": FORMULAS,
}


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"No-overwrite contract: {OUTPUT}")
    dataset = json.loads((J_ROOT / "manifests/stage02j_dataset_manifest.json").read_text())
    eligibility = json.loads((J_ROOT / "eligibility/record_eligibility_results.json").read_text())
    leakage = json.loads((J_ROOT / "leakage/leakage_graph.json").read_text())
    split = json.loads((J_ROOT / "splits/split_feasibility.json").read_text())
    normalization = yaml.safe_load((J_ROOT / "normalization/prospective_normalization_contract.yaml").read_text())
    if dataset["sample_count"] != 5 or leakage["connected_component_count"] != 1:
        raise RuntimeError("Stage 02J record/leakage history changed")
    if eligibility["verdict_counts"] != {"diagnostic": 5, "eligible_for_future_training": 0, "rejected": 0}:
        raise RuntimeError("Stage 02J eligibility history changed")
    if split["formal_train_validation_test_split_exists"] or normalization["fitted_statistics_created"]:
        raise RuntimeError("Stage 02J split/normalization history changed")
    if dataset["Stage02K_authorized"] is not False:
        raise RuntimeError("Stage 02K historical authorization changed")
    prereg = yaml.safe_load(PREREG.read_text())
    if prereg["split_assignment"] != {
        "future_train": ["FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A"],
        "future_validation": ["FAMILY_DIAGONAL_B"],
        "future_test": ["FAMILY_MIXED_C"],
    }:
        raise RuntimeError("Preregistered split roles changed")
    canonical_records = {}
    for row in dataset["records"]:
        path = REPO_ROOT / row["canonical_record_path"]
        actual = digest(path.read_bytes())
        if actual != row["canonical_record_sha256"]:
            raise RuntimeError(f"Stage 02J canonical record changed: {row['case_id']}")
        canonical_records[row["case_id"]] = {"path": row["canonical_record_path"], "sha256": actual}
    result = {
        "manifest_version": "stage02jr-input-freeze-0.2.0",
        "created_before_family_preflight_and_new_acceleration": True,
        "frozen_roles": {
            role: {"path": str(path.relative_to(REPO_ROOT)), "sha256": digest(path.read_bytes())}
            for role, path in ROLE_PATHS.items()
        },
        "five_existing_canonical_records": canonical_records,
        "family_formula_hashes": {
            row["family_id"]: digest(canonical(row.get("formulas", {"source": row["source_lineage"]})))
            for row in prereg["families"]
        },
        "prefrozen_split_assignment": prereg["split_assignment"],
        "historical_stage02j": {
            "leakage_components": 1,
            "diagnostic": 5,
            "eligible": 0,
            "normalization_fitted": False,
            "Stage02K_authorized": False,
        },
        "historical_overwrite_permitted": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"frozen_roles": len(ROLE_PATHS), "canonical_records": len(canonical_records), "family_formulas": 4}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
