#!/usr/bin/env python3
"""Finalize Stage 02J-T when the development structured gate fails."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_3"
FREEZE_PATH = ROOT / "freeze/stage02jt_input_freeze_manifest.json"
GATE_PATH = ROOT / "contract_design/v03_development_gate.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    freeze = load(FREEZE_PATH); gate = load(GATE_PATH)
    if gate["v03_contract_generation_authorized"]:
        raise RuntimeError("Blocked finalizer cannot run when contract generation is authorized")
    common = {
        "candidate_preregistration_hash": freeze["candidate_preregistration_hash"],
        "blocking_reason_code": "DEVELOPMENT_STRUCTURED_TARGET_FAIL_CROSSMODE_A_N12_P_MAG",
        "manual_override_permitted": False,
    }
    write(ROOT / "contract_design/v03_contract_nonqualification.json", {
        **common, "candidate_id": "attribution_contract_v0_3",
        "single_candidate_preregistered": True, "metric_sweep_used": False,
        "final_contract_generated": False, "regularity_contract_v0_3_hash": None,
        "reason": "final_contract_generation_requires_all_development_control_invariance_gates_PASS",
    })
    write(ROOT / "blind_family_generator/blind_generation_status.json", {
        **common, "generator_code_frozen": True, "generator_source_hash": freeze["blind_generator_source_hash"],
        "generator_freeze_hash": freeze["blind_generator_freeze_hash"],
        "blind_family_formulas_materialized": False, "formula_count": 0,
        "family_replacement_used": False, "status": "NOT_EXECUTED_NO_V03_CONTRACT_HASH",
    })
    write(ROOT / "blind_reference_qualification/blind_reference_qualification_status.json", {
        **common, "blind_family_count_evaluated": 0, "reference_qualified_count": 0,
        "positivity_or_Mach_evaluated": False, "status": "NOT_EXECUTED_BLIND_FORMULAS_NOT_MATERIALIZED",
    })
    write(ROOT / "blind_target_qualification/blind_target_qualification_status.json", {
        **common, "blind_target_count_generated": 0, "conservation_qualified_family_count": 0,
        "regularity_qualified_family_count": 0, "status": "NOT_EXECUTED_BLIND_REFERENCE_GATE_NOT_AVAILABLE",
    })
    write(ROOT / "blind_transfer/blind_transfer_decision.json", {
        **common, "blind_family_required_count": 4, "blind_family_evaluated_count": 0,
        "blind_family_3_of_3_PASS_count": 0, "DIAGONAL_B_MIXED_C_counted_as_blind": False,
        "stage02ju_authorized": False, "dataset_materialized": False,
        "model_generated": False, "training_performed": False,
    })
    mismatches = []
    for relative, expected in freeze["historical_file_hashes_before_stage02jt"].items():
        path = REPO / relative
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    integrity = {
        "verification_version": "stage02jt-historical-integrity-0.3.0",
        "expected_file_count": freeze["historical_file_count"],
        "verified_file_count": freeze["historical_file_count"] - len(mismatches),
        "mismatches": mismatches, "all_historical_hashes_unchanged": not mismatches,
        "stage01_modified": any(row["path"].startswith("stage_01_verification/") for row in mismatches),
    }
    write(ROOT / "manifests/historical_integrity_verification.json", integrity)
    print(json.dumps({"contract_generated": False, "blind_formulas": 0, "historical_unchanged": not mismatches, "stage02ju": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
