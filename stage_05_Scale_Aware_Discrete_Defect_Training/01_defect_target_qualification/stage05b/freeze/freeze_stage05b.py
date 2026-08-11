"""Freeze Stage 05B inputs and the complete 384-origin plan without payload decode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve()
STAGE05B = HERE.parents[1]
STAGE05 = HERE.parents[3]
ROOT = HERE.parents[4]
CONTRACT = STAGE05B / "contracts/conservative_discrete_defect_target_contract_v0_1.yaml"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
lineages = contract["formal_population"]["lineages"]
variants = contract["formal_population"]["variants"]
origins = [
    {"lineage": lineage, "variant": variant, "resolution": 8, "origin": origin,
     "origin_id": f"{lineage}_{variant}_N8_O{origin:02d}"}
    for lineage in lineages for variant in variants for origin in range(32)
]
inventory = {
    "schema": "sph-pio-poc.stage05b.preregistered-origin-inventory.v1",
    "frozen_before_train_payload_decode": True,
    "formal_resolution": 8,
    "formal_origin_count": len(origins),
    "origins": origins,
    "canonical_origin_list_sha256": "sha256:" + hashlib.sha256(canonical(origins)).hexdigest(),
    "resolution_diagnostics": {
        "resolutions": [12, 16], "variants": ["VARIANT_MAIN"], "origins": list(range(32)),
        "lineages": lineages, "role": "diagnostic_only", "count": 384,
    },
}
inventory_path = STAGE05B / "train_origin_inventory/preregistered_origin_inventory.json"
write_json(inventory_path, inventory)

input_relpaths = [
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05a_final_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05a_contract_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05a_final_report.md",
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05a_defect_formulation.md",
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05a_scale_and_loss_contract.md",
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05a_gradient_qualification_strategy.md",
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05a_data_and_seal_strategy.md",
    "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_role_assignment_manifest.json",
    "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_trajectory_manifest.json",
    "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json",
    "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cs_final_manifest.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/rk2_core/solver.py",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/rk2_core/independent_functional.py",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/baseline_d0/state.py",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/graph_rebuild/graph.py",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/pair_force_head/head.py",
    "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/formula_templates/stage04b_reference_core.py",
    "stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04c/qualification/run_stage04c_qualification.py",
]
inputs = []
for relpath in input_relpaths:
    path = ROOT / relpath
    inputs.append({"path": relpath, "sha256": sha(path), "size_bytes": path.stat().st_size})

freeze = {
    "schema": "sph-pio-poc.stage05b.freeze-record.v1",
    "contract_path": str(CONTRACT.relative_to(ROOT)),
    "contract_sha256": sha(CONTRACT),
    "contract_size_bytes": CONTRACT.stat().st_size,
    "origin_inventory_path": str(inventory_path.relative_to(ROOT)),
    "origin_inventory_sha256": sha(inventory_path),
    "access_module_path": str((STAGE05B / "access_control/stage05b_train_access.py").relative_to(ROOT)),
    "access_module_sha256": sha(STAGE05B / "access_control/stage05b_train_access.py"),
    "authorization_verified": json.loads((STAGE05 / "09_manifests/stage05a_final_manifest.json").read_text())["terminal_status"]
        == "SCALE_AWARE_DISCRETE_DEFECT_TRAINING_CONTRACT_COMPLETE",
    "frozen_before_first_train_state_or_target_array_decode": True,
    "train_state_array_decode_count_at_freeze": 0,
    "target_array_decode_count_at_freeze": 0,
    "inputs": inputs,
    "historical_files_modified": 0,
}
write_json(STAGE05B / "freeze/stage05b_freeze_record.json", freeze)
print(json.dumps({"contract_sha256": freeze["contract_sha256"], "origins": len(origins), "authorization": freeze["authorization_verified"]}))
