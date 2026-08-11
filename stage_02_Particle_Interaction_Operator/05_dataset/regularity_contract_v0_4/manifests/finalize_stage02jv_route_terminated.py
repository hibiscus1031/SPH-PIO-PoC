#!/usr/bin/env python3
"""Finalize the v0.4 invariance failure and terminate the hard-gate route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_4"
FREEZE_PATH = ROOT / "freeze/stage02jv_input_freeze_manifest.json"
GATE_PATH = ROOT / "contract_design/v04_development_gate.json"


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
    if gate["final_v04_contract_generation_authorized"]:
        raise RuntimeError("Route-termination finalizer requires a failed scientific gate")
    common = {
        "candidate_preregistration_hash": freeze["candidate_preregistration_hash"],
        "blocking_reason_code": "DIRECTION_ONLY_SMOOTH_P_MAG_AMPLITUDE_INVARIANCE_FAIL",
        "manual_override_permitted": False,
    }
    write(ROOT / "contract_design/v04_contract_nonqualification.json", {
        **common, "candidate_id": "attribution_contract_v0_4", "single_candidate_preregistered": True,
        "metric_sweep_used": False, "final_contract_generated": False,
        "regularity_contract_v0_4_hash": None, "threshold_or_factor_modified": False,
    })
    write(ROOT / "blind_materialization/blind_materialization_status.json", {
        **common, "frozen_generator_source_hash": freeze["blind_generator_source_hash"],
        "frozen_generator_freeze_hash": freeze["blind_generator_freeze_hash"],
        "blind_formulas_materialized": False, "formula_count": 0, "family_replacement_used": False,
        "status": "NOT_EXECUTED_NO_FINAL_V04_CONTRACT_HASH",
    })
    write(ROOT / "blind_reference/blind_reference_status.json", {
        **common, "families_evaluated": 0, "physical_bound_qualified": 0,
        "reference_qualified": 0, "status": "NOT_EXECUTED_BLIND_FORMULAS_NOT_MATERIALIZED",
    })
    write(ROOT / "blind_conservation/blind_conservation_status.json", {
        **common, "families_evaluated": 0, "total_force_qualified": 0,
        "antisymmetric_representability_qualified": 0, "status": "NOT_EXECUTED_BLIND_REFERENCE_NOT_AVAILABLE",
    })
    write(ROOT / "blind_regularity/blind_regularity_status.json", {
        **common, "families_evaluated": 0, "families_3_of_3_PASS": 0,
        "status": "NOT_EXECUTED_BLIND_CONSERVATION_NOT_AVAILABLE",
    })
    write(ROOT / "auxiliary_transfer/auxiliary_transfer_status.json", {
        **common, "DIAGONAL_B_status": "historical_nonblind_auxiliary_only_not_executed",
        "MIXED_C_status": "historical_nonblind_auxiliary_only_not_executed",
        "counted_in_v04_qualification": False, "status": "NOT_EXECUTED_REQUIRES_4_OF_4_BLIND_PASS",
    })
    write(ROOT / "manifests/route_termination_decision.json", {
        **common, "final_status": "REGULARITY_HARD_GATE_ROUTE_TERMINATED",
        "v0_5_design_permitted": False,
        "historical_contracts_retained": ["v0.1", "v0.2", "v0.3_candidate", "v0.4_candidate"],
        "regularity_future_role": "diagnostic_only",
        "regularity_may_replace_dataset_eligibility": False,
        "stage02ju_authorized": False, "stage02k_authorized": False,
        "dataset_materialized": False, "model_generated": False, "training_performed": False,
    })
    mismatches = []
    for relative, expected in freeze["historical_file_hashes_before_stage02jv"].items():
        path = REPO / relative; actual = sha(path) if path.is_file() else None
        if actual != expected: mismatches.append({"path": relative, "expected": expected, "actual": actual})
    write(ROOT / "manifests/historical_integrity_verification.json", {
        "verification_version": "stage02jv-historical-integrity-0.4.0",
        "expected_file_count": freeze["historical_file_count"],
        "verified_file_count": freeze["historical_file_count"] - len(mismatches),
        "mismatches": mismatches, "all_historical_hashes_unchanged": not mismatches,
        "stage01_modified": any(row["path"].startswith("stage_01_verification/") for row in mismatches),
    })
    print(json.dumps({"contract_generated": False, "blind_formulas": 0, "route_terminated": True, "historical_unchanged": not mismatches}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
