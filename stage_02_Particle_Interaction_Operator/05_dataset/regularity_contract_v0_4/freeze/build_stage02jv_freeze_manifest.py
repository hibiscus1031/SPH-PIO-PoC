#!/usr/bin/env python3
"""Freeze all Stage 02J-V historical and prospective inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_4"
OUT = ROOT / "freeze/stage02jv_input_freeze_manifest.json"

REQUIRED = [
    "stage_02_Particle_Interaction_Operator/07_reports/stage02jt_final_report.md",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/contract_design/v03_candidate_preregistration.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/decomposition/development_metric_decomposition.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/control_semantics/signflip_semantics.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/statistical_calibration/control_calibration.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/decomposition/v03_invariance.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/generate_blind_families.py",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/blind_generator_freeze.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/contract_design/regularity_contract_v0_2.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/new_family_target_candidates.json",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/acceptance/reference_acceptance_rules.yaml",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/conservation_closure/freeze/stage02ir_scope_and_decision_rules.yaml",
    "stage_02_Particle_Interaction_Operator/03_dataset/splitting/split_strategy.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/uncertainty/uncertainty_contract.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/eligibility/label_eligibility_rules.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_4/contract_design/v04_candidate_preregistration.yaml",
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
            if "05_dataset/regularity_contract_v0_4" in path.as_posix():
                continue
            history[str(path.relative_to(REPO))] = sha(path)
    manifest = {
        "manifest_version": "stage02jv-input-freeze-0.4.0",
        "required_inputs": {name: sha(REPO / name) for name in REQUIRED},
        "historical_file_hashes_before_stage02jv": history,
        "historical_file_count": len(history),
        "candidate_preregistration_hash": sha(ROOT / "contract_design/v04_candidate_preregistration.yaml"),
        "blind_generator_source_hash": sha(REPO / REQUIRED[6]),
        "blind_generator_freeze_hash": sha(REPO / REQUIRED[7]),
        "historical_statuses": {
            "stage02js": "VERSIONED_MULTIFAMILY_DATASET_NOT_READY",
            "stage02jt": "REGULARITY_GATE_V03_NOT_QUALIFIED",
            "v03_final_contract": "NOT_GENERATED",
            "stage02ju_authorized": False,
            "stage02k_authorized": False,
        },
        "blind_formulas_accessed": False,
        "manual_override_permitted": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"historical_file_count": len(history), "candidate_hash": manifest["candidate_preregistration_hash"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
