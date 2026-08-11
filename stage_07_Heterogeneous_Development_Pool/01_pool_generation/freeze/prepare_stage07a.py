"""Freeze Stage07A inputs before any new formula parameter or scientific result.

This script is read-only outside Stage07 and imports no model, optimizer, or
training code.  It records every historical Stage04--06 file hash plus the
preregistered generator and role assignment.
"""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
STAGE07 = HERE.parents[2]
ROOT = HERE.parents[3]
POOL = STAGE07 / "01_pool_generation"
CONTRACT = POOL / "contracts/heterogeneous_lineage_generator_v0_1.yaml"
ROLES = POOL / "role_assignment/preregistered_role_assignment.json"

HISTORICAL_ROOTS = [
    ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b",
    ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training",
    ROOT / "stage_06_Optimizer_Update_Dynamics_Training",
]

REQUIRED_STATUS = {
    ROOT / "stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c/qualification/stage06c_qualification.json":
        "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
    ROOT / "stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/manifests/stage06cr_final_manifest.json":
        "FORMAL_TRAINING_FAILURE_ATTRIBUTED",
    ROOT / "stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/attribution/failure_attribution.json":
        "TRAIN_LINEAGE_HETEROGENEITY_DOMINANT",
}

IGNORED_NAMES = {".DS_Store"}
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for base in HISTORICAL_ROOTS:
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name in IGNORED_NAMES or any(part in IGNORED_PARTS for part in path.parts):
                continue
            metadata = {"path": relative(path), "bytes": path.stat().st_size}
            try:
                metadata.update({"sha256": sha_file(path), "readable": True})
            except PermissionError:
                metadata.update({
                    "sha256": "COVERED_BY_EXISTING_STAGE04B_SEAL_MANIFEST",
                    "readable": False,
                    "mode": oct(stat.S_IMODE(path.stat().st_mode)),
                })
            rows.append(metadata)
    return rows


def main() -> None:
    if not CONTRACT.is_file() or not ROLES.is_file():
        raise RuntimeError("generator contract and role preregistration must exist first")
    roles = json.loads(ROLES.read_text(encoding="utf-8"))
    role_counts = roles.get("counts", {})
    if role_counts != {"NEW_TRAIN_V2": 8, "FRESH_VALIDATION_V2": 4}:
        raise RuntimeError("role preregistration count mismatch")
    rows = inventory()
    tree_digest = "sha256:" + hashlib.sha256(canonical(rows)).hexdigest()
    status_rows = []
    for path, required in REQUIRED_STATUS.items():
        text = path.read_text(encoding="utf-8")
        status_rows.append({
            "path": relative(path), "sha256": sha_file(path), "required": required,
            "present": required in text,
        })
    checkpoints = [row for row in rows if "/stage06c/checkpoints/" in row["path"] and row["path"].endswith(".pt")]
    unreadable = [row for row in rows if not row["readable"]]
    stage04_seal_manifest = ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json"
    selected_dir = ROOT / "stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c/checkpoint_selection"
    selected_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in selected_dir.glob("*.json"))
    record = {
        "schema_version": "sph-pio-poc.stage07a.input-freeze.v1",
        "freeze_order": "generator_contract_then_role_assignment_then_historical_hash_inventory_then_parameters_then_scientific_results",
        "generator_contract": {"path": relative(CONTRACT), "sha256": sha_file(CONTRACT)},
        "role_assignment": {"path": relative(ROLES), "sha256": sha_file(ROLES), "counts": role_counts},
        "historical_file_count": len(rows),
        "historical_tree_sha256": tree_digest,
        "historical_files": rows,
        "unreadable_sealed_file_count": len(unreadable),
        "unreadable_sealed_modes_all_000": all(row.get("mode") == "0o0" for row in unreadable),
        "existing_stage04b_seal_manifest": {"path": relative(stage04_seal_manifest), "sha256": sha_file(stage04_seal_manifest)},
        "status_sources": status_rows,
        "historical_checkpoint_count": len(checkpoints),
        "selected_checkpoint_identity_count_required": 9,
        "selected_checkpoint_evidence_present": "selected" in selected_text.lower(),
        "historical_freeze_pass": len(checkpoints) == 590 and all(row["present"] for row in status_rows) and all(row.get("mode") == "0o0" for row in unreadable),
        "sealed_test_decode_counts_at_freeze": {
            "formula": 0, "state": 0, "source": 0, "target": 0, "origin": 0,
        },
        "execution_counts_at_freeze": {
            "model_forwards": 0, "optimizer_steps": 0, "training_runs": 0,
            "neural_rollouts": 0, "model_rankings": 0,
        },
    }
    freeze_path = POOL / "freeze/stage07a_input_freeze_record.json"
    manifest_path = STAGE07 / "09_manifests/stage07a_input_freeze_manifest.json"
    write_json(freeze_path, record)
    write_json(manifest_path, record)
    print(json.dumps({
        "historical_file_count": len(rows), "checkpoint_count": len(checkpoints),
        "tree_sha256": tree_digest, "pass": record["historical_freeze_pass"],
        "contract_sha256": record["generator_contract"]["sha256"],
        "role_sha256": record["role_assignment"]["sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
