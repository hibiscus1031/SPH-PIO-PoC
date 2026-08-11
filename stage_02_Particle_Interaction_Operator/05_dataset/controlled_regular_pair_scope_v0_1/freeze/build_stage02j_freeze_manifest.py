#!/usr/bin/env python3
"""Create the immutable Stage 02J input manifest before materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATA_ROOT = STAGE_ROOT / "05_dataset/controlled_regular_pair_scope_v0_1"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
OUTPUT = DATA_ROOT / "freeze/stage02j_input_freeze_manifest.json"
TARGETS = ATTR_ROOT / "qualified_spatial_targets/targets/spatial_target_candidates.json"
IR_FREEZE = ATTR_ROOT / "conservation_closure/freeze/stage02ir_input_freeze_manifest.json"

AUTHORIZED = [
    "i_res_n12_h26_regular",
    "i_anchor_n16_h26_regular",
    "i_res_n20_h26_regular",
    "i_sup_n16_h22_regular",
    "i_sup_n16_h30_regular",
]
JITTER = ["i_dis_n16_h26_jitter05", "i_dis_n16_h26_jitter10"]

FROZEN_ROLES = {
    "stage02ir_final_report": STAGE_ROOT / "07_reports/stage02ir_final_report.md",
    "stage02ir_architecture_scope_decision": ATTR_ROOT
    / "conservation_closure/architecture_scope/architecture_scope_decision.json",
    "stage02ir_qualification": ATTR_ROOT / "conservation_closure/qualification/stage02ir_qualification.json",
    "stage02i_final_report": STAGE_ROOT / "07_reports/stage02i_final_report.md",
    "stage02i_case_matrix": ATTR_ROOT
    / "qualified_spatial_targets/case_matrix/preregistered_stage02i_case_matrix.yaml",
    "stage02i_seven_target_records": TARGETS,
    "stage02i_six_component_attribution": ATTR_ROOT
    / "qualified_spatial_targets/attribution/six_component_attribution.json",
    "stage02i_conservation_compatibility": ATTR_ROOT
    / "qualified_spatial_targets/conservation/conservation_compatibility_audit.json",
    "fourier_analytic_reference_evidence": ATTR_ROOT
    / "conservation_closure/particle_quadrature/reference_pair_conservation_comparison.json",
    "stage02b_dataset_schema": STAGE_ROOT / "03_dataset/schema/pio_dataset_schema.json",
    "stage02b_eligibility_rules": STAGE_ROOT / "03_dataset/eligibility/label_eligibility_rules.yaml",
    "stage02b_split_rules": STAGE_ROOT / "03_dataset/splitting/split_strategy.md",
    "stage02b_leakage_rules": STAGE_ROOT / "03_dataset/splitting/split_strategy.md",
    "stage02b_uncertainty_contract": STAGE_ROOT / "03_dataset/uncertainty/uncertainty_contract.md",
    "stage02i_historical_eligibility": ATTR_ROOT
    / "qualified_spatial_targets/results/stage02i_eligibility_results.json",
    "stage02ir_target_hash_freeze": IR_FREEZE,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"No-overwrite contract: {OUTPUT}")
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    target_map = {row["candidate_id"]: row for row in targets["candidates"]}
    if list(target_map) != targets["preregistered_case_ids"] or len(target_map) != 7:
        raise RuntimeError("Stage 02I target inventory is not the frozen seven-case order")
    if set(target_map) != set(AUTHORIZED + JITTER):
        raise RuntimeError("Stage 02I target identities do not match Stage 02J scope")

    ir_freeze = json.loads(IR_FREEZE.read_text(encoding="utf-8"))
    record_hashes = {
        case_id: digest_bytes(canonical_bytes(target_map[case_id])) for case_id in AUTHORIZED + JITTER
    }
    for case_id, actual in record_hashes.items():
        if ir_freeze["seven_target_record_hashes"][case_id] != actual:
            raise RuntimeError(f"Stage 02I record hash changed: {case_id}")

    architecture = json.loads(
        FROZEN_ROLES["stage02ir_architecture_scope_decision"].read_text(encoding="utf-8")
    )
    qualification = json.loads(FROZEN_ROLES["stage02ir_qualification"].read_text(encoding="utf-8"))
    historical = json.loads(FROZEN_ROLES["stage02i_historical_eligibility"].read_text(encoding="utf-8"))
    if architecture["decision"] != "PAIR_ONLY_REGULAR_SCOPE":
        raise RuntimeError("Stage 02I-R architecture scope is not pair-only regular")
    if qualification["authorized_candidate_ids"] != AUTHORIZED:
        raise RuntimeError("Stage 02I-R authorized list changed")
    if historical["Stage02J_authorized"] is not False:
        raise RuntimeError("Historical Stage 02I authorization was overwritten")

    role_hashes = {
        role: {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": file_hash(path),
        }
        for role, path in FROZEN_ROLES.items()
    }
    manifest = {
        "manifest_version": "stage02j-input-freeze-0.1.0",
        "created_before_record_materialization": True,
        "hash_algorithm": "sha256",
        "frozen_roles": role_hashes,
        "authorized_regular_target_ids": AUTHORIZED,
        "authorized_regular_target_record_hashes": {case_id: record_hashes[case_id] for case_id in AUTHORIZED},
        "jitter_diagnostic_ids": JITTER,
        "jitter_target_record_hashes": {case_id: record_hashes[case_id] for case_id in JITTER},
        "sample_unit": "complete_particle_graph",
        "expected_sample_count": 5,
        "historical_stage02i_Stage02J_authorization": False,
        "stage02ir_limited_future_authorization": "five_regular_candidates_only",
        "historical_overwrite_permitted": False,
    }
    OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"frozen_role_count": len(role_hashes), "record_hash_count": len(record_hashes)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
