#!/usr/bin/env python3
"""Freeze read-only Stage 02I inputs before any target evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
OUTPUT_PATH = STAGE_ROOT / "04_target_attribution/qualified_spatial_targets/freeze/stage02i_input_freeze_manifest.json"

FROZEN_FILES = (
    STAGE_ROOT / "07_reports/stage02h_final_report.md",
    STAGE_ROOT / "04_target_attribution/reference_fidelity/reference_candidate_matrix.yaml",
    STAGE_ROOT / "04_target_attribution/reference_fidelity/reference_candidate_results.json",
    STAGE_ROOT / "04_target_attribution/bias_analysis/reference_bias_analysis.json",
    STAGE_ROOT / "04_target_attribution/r2s_comparison/cross_reference_audit.json",
    STAGE_ROOT / "04_target_attribution/acceptance/reference_acceptance_rules.yaml",
    STAGE_ROOT / "04_target_attribution/acceptance/reference_acceptance_results.json",
    STAGE_ROOT / "04_target_attribution/qualification_closure/attribution_closure.json",
    STAGE_ROOT / "03_dataset/schema/pio_dataset_schema.json",
    STAGE_ROOT / "03_dataset/eligibility/label_eligibility_rules.yaml",
    STAGE_ROOT / "03_dataset/splitting/split_strategy.md",
    STAGE_ROOT / "03_dataset/uncertainty/uncertainty_contract.md",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def main() -> int:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"No-overwrite contract: {OUTPUT_PATH}")
    acceptance = json.loads(
        (STAGE_ROOT / "04_target_attribution/acceptance/reference_acceptance_results.json").read_text(encoding="utf-8")
    )
    expected_accepted = ["H_REF_FOURIER2", "H_REF_ANALYTIC"]
    expected_diagnostic = ["H_REF_QWLS2_INCUMBENT", "H_REF_CWLS3"]
    accepted = acceptance["summary"]["accepted_candidate_ids"]
    diagnostic = [row["candidate_id"] for row in acceptance["results"] if row["verdict"] == "diagnostic"]
    if accepted != expected_accepted or diagnostic != expected_diagnostic:
        raise RuntimeError(f"Stage 02H reference identities changed: accepted={accepted}, diagnostic={diagnostic}")

    candidate_results_path = STAGE_ROOT / "04_target_attribution/reference_fidelity/reference_candidate_results.json"
    candidate_results = json.loads(candidate_results_path.read_text(encoding="utf-8"))
    accepted_records = [
        row for row in candidate_results["records"] if row["candidate_id"] in expected_accepted
    ]
    evidence_hashes = {
        f"{row['candidate_id']}::{row['case_id']}": sha256_bytes(canonical_bytes(row)) for row in accepted_records
    }
    if len(evidence_hashes) != 12:
        raise RuntimeError(f"Expected 12 accepted-reference evidence records, got {len(evidence_hashes)}")

    manifest = {
        "manifest_version": "stage02i-input-freeze-1.0.0",
        "created_before_stage02i_target_evaluation": True,
        "hash_algorithm": "sha256",
        "frozen_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in FROZEN_FILES},
        "stage02h_accepted_reference_ids": expected_accepted,
        "stage02h_diagnostic_reference_ids": expected_diagnostic,
        "accepted_reference_six_case_evidence_hashes": evidence_hashes,
        "accepted_reference_evidence_count": len(evidence_hashes),
        "diagnostic_candidate_deletion_permitted": False,
        "stage02h_acceptance_modification_permitted": False,
        "threshold_modification_permitted": False,
        "Stage02G_attribution_closure_overwrite_permitted": False,
        "Stage02B_contract_overwrite_permitted": False,
    }
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"frozen_file_count": len(FROZEN_FILES), "accepted_evidence_count": len(evidence_hashes)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
