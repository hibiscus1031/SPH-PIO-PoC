"""Freeze Stage08A contract and historical authorization before candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from typing import Any

HERE = Path(__file__).resolve(); DESIGN = HERE.parents[1]; STAGE08 = HERE.parents[2]; ROOT = HERE.parents[3]
CONTRACT = DESIGN / "contracts/systematic_coverage_v3_contract_v0_1.yaml"
STAGE07 = ROOT / "stage_07_Heterogeneous_Development_Pool"
ATTRIBUTION = STAGE07 / "05_formal_retraining/stage07dr/hypothesis_outcome/failure_attribution.json"
ROUTE = STAGE07 / "05_formal_retraining/stage07dr/route_decision/unique_route_decision.json"
STAGE07D = STAGE07 / "05_formal_retraining/stage07d/qualification/stage07d_qualification.json"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def inventory() -> list[dict[str, Any]]:
    rows = []
    for base in (ROOT / "stage_04_Local_Causal_Dynamic_Training", ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training",
                 ROOT / "stage_06_Optimizer_Update_Dynamics_Training", STAGE07):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.name == ".DS_Store": continue
            row = {"path": relative(path), "bytes": path.stat().st_size, "mode": oct(stat.S_IMODE(path.stat().st_mode))}
            try:
                row.update({"sha256": sha_file(path), "readable": True})
            except PermissionError:
                row.update({"sha256": "PRESERVED_BY_PRIOR_SEAL_MANIFEST", "readable": False})
            rows.append(row)
    return rows


def main() -> None:
    if not CONTRACT.is_file(): raise RuntimeError("coverage contract must exist before freeze")
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8")); route = json.loads(ROUTE.read_text(encoding="utf-8"))
    stage07d = json.loads(STAGE07D.read_text(encoding="utf-8"))
    authorization = {
        "Stage07D_status": stage07d.get("status"),
        "Stage07D_R_status": attribution.get("status"), "BRANCH_B_OUTCOME": attribution.get("BRANCH_B_OUTCOME"),
        "D1_primary_attribution": attribution.get("per_arm", {}).get("D1", {}).get("primary_attribution"),
        "D2_primary_attribution": attribution.get("per_arm", {}).get("D2", {}).get("primary_attribution"),
        "D3_primary_attribution": attribution.get("per_arm", {}).get("D3", {}).get("primary_attribution"),
        "NEXT_ROUTE": attribution.get("NEXT_ROUTE"), "Stage07E_authorized": attribution.get("Stage07E_authorized"),
        "route_requires_new_validation_v3": route.get("requires_new_validation_v3")}
    expected = {"Stage07D_status": "FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
                "Stage07D_R_status": "TRAIN_V2_RETRAINING_FAILURE_ATTRIBUTED", "BRANCH_B_OUTCOME": "NOT_SUPPORTED",
                "D1_primary_attribution": "HELD_OUT_H2_SUPPORT_GAP_DOMINANT",
                "D2_primary_attribution": "HELD_OUT_H2_SUPPORT_GAP_DOMINANT",
                "D3_primary_attribution": "HELD_OUT_H2_SUPPORT_GAP_DOMINANT", "NEXT_ROUTE": "SYSTEMATIC_COVERAGE_V3",
                "Stage07E_authorized": False, "route_requires_new_validation_v3": True}
    if authorization != expected: raise RuntimeError(f"Stage07 authorization mismatch: {authorization}")
    rows = inventory(); tree = "sha256:" + hashlib.sha256(canonical(rows)).hexdigest()
    original_sealed = [row for row in rows if any(name in row["path"].lower() for name in ("lcdf_03", "lcdf_10")) and not row["readable"]]
    record = {"schema_version": "sph-pio-poc.stage08a.input-freeze.v1",
              "freeze_order": "coverage_contract_then_historical_inventory_then_candidate_parameters_then_candidate_results_then_role_selection",
              "contract": {"path": relative(CONTRACT), "sha256": sha_file(CONTRACT)},
              "authorization": authorization, "authorization_sources": {"attribution": {"path": relative(ATTRIBUTION), "sha256": sha_file(ATTRIBUTION)},
              "route": {"path": relative(ROUTE), "sha256": sha_file(ROUTE)}, "stage07d": {"path": relative(STAGE07D), "sha256": sha_file(STAGE07D)}},
              "final_development_cycle": True, "historical_files": rows, "historical_file_count": len(rows),
              "historical_tree_sha256": tree, "original_sealed_unreadable_file_count": len(original_sealed),
              "original_sealed_modes_all_000": bool(original_sealed) and all(row["mode"] == "0o0" for row in original_sealed),
              "original_sealed_decode_counts": {"formula": 0, "state": 0, "source": 0, "target": 0, "origin": 0, "evaluation": 0},
              "execution_counts": {"model_instances": 0, "model_forwards": 0, "optimizer_instances": 0,
              "optimizer_steps": 0, "parameter_updates": 0, "training_runs": 0}, "historical_freeze_pass": True}
    freeze_path = DESIGN / "freeze/stage08a_input_freeze_record.json"
    manifest_path = STAGE08 / "09_manifests/stage08a_input_freeze_manifest.json"
    write_json(freeze_path, record); write_json(manifest_path, record)
    print(json.dumps({"pass": True, "contract_sha256": record["contract"]["sha256"],
                      "historical_file_count": len(rows), "historical_tree_sha256": tree,
                      "original_sealed_mode_000": record["original_sealed_modes_all_000"]}, indent=2))


if __name__ == "__main__": main()
