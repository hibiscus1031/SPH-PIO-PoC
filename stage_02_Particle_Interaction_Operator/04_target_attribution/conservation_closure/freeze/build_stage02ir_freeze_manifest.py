#!/usr/bin/env python3
"""Freeze Stage 02I-R read-only inputs before controlled recomputation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
OUTPUT_PATH = ATTR_ROOT / "conservation_closure/freeze/stage02ir_input_freeze_manifest.json"
TARGET_PATH = ATTR_ROOT / "qualified_spatial_targets/targets/spatial_target_candidates.json"

FROZEN_FILES = (
    STAGE_ROOT / "07_reports/stage02i_final_report.md",
    ATTR_ROOT / "qualified_spatial_targets/case_matrix/preregistered_stage02i_case_matrix.yaml",
    TARGET_PATH,
    ATTR_ROOT / "qualified_spatial_targets/attribution/six_component_attribution.json",
    ATTR_ROOT / "qualified_spatial_targets/attribution/resolution_attribution.json",
    ATTR_ROOT / "qualified_spatial_targets/attribution/support_attribution.json",
    ATTR_ROOT / "qualified_spatial_targets/attribution/disorder_audit.json",
    ATTR_ROOT / "qualified_spatial_targets/conservation/conservation_compatibility_audit.json",
    ATTR_ROOT / "qualified_spatial_targets/results/stage02i_eligibility_results.json",
    ATTR_ROOT / "acceptance/reference_acceptance_rules.yaml",
    ATTR_ROOT / "acceptance/reference_acceptance_results.json",
    STAGE_ROOT / "02_operator_design/constraints/pio_conservation_contract.md",
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
    targets = json.loads(TARGET_PATH.read_text(encoding="utf-8"))
    conservation = json.loads(
        (ATTR_ROOT / "qualified_spatial_targets/conservation/conservation_compatibility_audit.json").read_text(
            encoding="utf-8"
        )
    )
    eligibility = json.loads(
        (ATTR_ROOT / "qualified_spatial_targets/results/stage02i_eligibility_results.json").read_text(encoding="utf-8")
    )
    if targets["candidate_count"] != 7 or len(targets["candidates"]) != 7:
        raise RuntimeError("Stage 02I seven-target inventory is not frozen")
    if conservation["pair_force_compatible_count"] != 5 or conservation["node_residual_only_count"] != 2:
        raise RuntimeError("Stage 02I conservation counts changed")
    if eligibility["Stage02J_authorized"] is not False:
        raise RuntimeError("Stage 02I Stage 02J authorization changed")
    target_hashes = {
        row["candidate_id"]: sha256_bytes(canonical_bytes(row)) for row in targets["candidates"]
    }
    manifest = {
        "manifest_version": "stage02ir-input-freeze-1.0.0",
        "created_before_controlled_recomputation": True,
        "hash_algorithm": "sha256",
        "frozen_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in FROZEN_FILES},
        "seven_target_record_hashes": target_hashes,
        "candidate_discretization_target_count": 7,
        "pair_force_compatible_count": 5,
        "node_residual_only_count": 2,
        "Stage02J_authorized": False,
        "historical_record_overwrite_permitted": False,
        "target_projection_writeback_permitted": False,
    }
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"frozen_file_count": len(FROZEN_FILES), "target_record_count": len(target_hashes)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
