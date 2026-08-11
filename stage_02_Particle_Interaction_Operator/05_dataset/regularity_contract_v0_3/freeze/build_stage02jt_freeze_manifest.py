#!/usr/bin/env python3
"""Freeze Stage 02J-T historical evidence and prospective inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_3"
OUT = ROOT / "freeze/stage02jt_input_freeze_manifest.json"

REQUIRED = [
    "stage_02_Particle_Interaction_Operator/07_reports/stage02js_final_report.md",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/contract_design/regularity_contract_v0_2.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/development_audit/original_gate_reproduction.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/development_audit/development_regularity_audit.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/negative_controls/negative_control_audit.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/invariance/invariance_audit.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/heldout_validation/heldout_release_gate.json",
    "stage_02_Particle_Interaction_Operator/07_reports/stage02js_heldout_validation.md",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/new_family_target_candidates.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/family_design/analytic_family_definitions.py",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/acceptance/reference_acceptance_rules.yaml",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/conservation_closure/freeze/stage02ir_scope_and_decision_rules.yaml",
    "stage_02_Particle_Interaction_Operator/03_dataset/splitting/split_strategy.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/uncertainty/uncertainty_contract.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/eligibility/label_eligibility_rules.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/contract_design/v03_candidate_preregistration.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/blind_generator_freeze.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/generate_blind_families.py",
]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(OUT)
    missing = [name for name in REQUIRED if not (REPO / name).is_file()]
    if missing:
        raise FileNotFoundError(missing)
    history = {}
    for base in (REPO / "stage_01_verification", STAGE):
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if "05_dataset/regularity_contract_v0_3" in path.as_posix():
                continue
            history[str(path.relative_to(REPO))] = sha(path)
    manifest = {
        "manifest_version": "stage02jt-input-freeze-0.3.0",
        "required_inputs": {name: sha(REPO / name) for name in REQUIRED},
        "historical_file_hashes_before_stage02jt": history,
        "historical_file_count": len(history),
        "candidate_preregistration_hash": sha(ROOT / "contract_design/v03_candidate_preregistration.yaml"),
        "blind_generator_source_hash": sha(ROOT / "blind_family_generator/generate_blind_families.py"),
        "blind_generator_freeze_hash": sha(ROOT / "blind_family_generator/blind_generator_freeze.yaml"),
        "historical_statuses": {
            "stage02jr": "MULTIFAMILY_CONTROLLED_DATASET_NOT_READY",
            "stage02js": "VERSIONED_MULTIFAMILY_DATASET_NOT_READY",
            "v0_2_qualified_candidate_count": 0,
            "stage02k_authorized": False,
        },
        "manual_override_permitted": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"historical_file_count": len(history), "candidate_hash": manifest["candidate_preregistration_hash"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
