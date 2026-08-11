"""Stage 06B TRAIN/VALIDATION allowlist with sealed-test hard denial."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

import numpy as np

HERE = Path(__file__).resolve()
STAGE06B = HERE.parents[1]
STAGE06 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE05B = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b"
TRAIN_TRAJECTORY_ROOT = (STAGE04B / "exact_trajectories/train").resolve()
TRAIN_TARGET_ROOT = (STAGE05B / "target_records").resolve()
VALIDATION_ROOT = (STAGE04B / "access_control/validation_private").resolve()
SEALED_ROOT = (STAGE04B / "sealed_test/private").resolve()
TRAIN_LINEAGES = {"lcdf_01", "lcdf_04", "lcdf_05", "lcdf_06", "lcdf_07", "lcdf_08"}
VALIDATION_LINEAGES = {"lcdf_02", "lcdf_09"}
VALIDATION_N8 = re.compile(r"^(lcdf_(?:02|09))_variant_(?:low|main)_n8\.(?:npz|json)$")
TRAIN_TRAJECTORY = re.compile(r"^(lcdf_\d{2})_variant_(?:low|main)_n8\.(?:npz|json)$")
TRAIN_TARGET = re.compile(r"^(LCDF_\d{2})_VARIANT_(?:LOW|MAIN)_N8_O\d{2}\.(?:npz|json)$")
VALIDATION_ACTORS = {"validation_materializer", "validation_evaluator", "zero_step_preflight"}
TRAIN_ACTORS = {"trainer", "zero_step_preflight"}
EVENTS: list[dict[str, Any]] = []
COUNTS = {"train_state_decode_count": 0, "train_target_decode_count": 0,
          "validation_state_decode_count": 0, "validation_target_decode_count": 0,
          "validation_trajectory_metadata_decode_count": 0,
          "validation_formula_decode_count": 0, "sealed_formula_decode_count": 0,
          "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
          "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0}


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _protocol_hash() -> str:
    manifest = json.loads((STAGE06B / "manifests/stage06b_protocol_manifest.json").read_text())
    path = ROOT / manifest["protocol_path"]
    assert _sha(path.read_bytes()) == manifest["protocol_sha256"]
    return manifest["protocol_sha256"]


def _validation_released() -> bool:
    path = STAGE06B / "access_control/validation_release_record.json"
    if not path.exists(): return False
    row = json.loads(path.read_text())
    return row.get("protocol_sha256") == _protocol_hash() and row.get("released_after_protocol_freeze") is True


def _expected_private_hash(path: Path) -> str:
    manifest = json.loads((ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json").read_text())
    relative = str(path.relative_to(ROOT))
    return next(row["sha256"] for row in manifest["private_artifacts"] if row["path"] == relative)


def _read_validation(path: Path, actor: str) -> bytes:
    if actor not in VALIDATION_ACTORS or not _validation_released():
        raise PermissionError("Stage06B validation access denied before frozen-protocol release")
    if not path.is_relative_to(VALIDATION_ROOT): raise PermissionError("outside validation root")
    if path.name != "validation_parameters.json" and not VALIDATION_N8.fullmatch(path.name):
        raise PermissionError("Stage06B opens only N8 validation payloads")
    before = stat.S_IMODE(path.stat().st_mode)
    if before != 0: raise RuntimeError(f"unexpected validation private mode before reversible release: {before:o}")
    payload = b""
    try:
        os.chmod(path, stat.S_IRUSR)
        payload = path.read_bytes()
    finally:
        os.chmod(path, before)
    after = stat.S_IMODE(path.stat().st_mode)
    expected = _expected_private_hash(path)
    if _sha(payload) != expected: raise RuntimeError("validation payload hash mismatch")
    EVENTS.append({"actor": actor, "path": str(path.relative_to(ROOT)), "mode_before": before, "mode_after": after,
                   "permission_restored": after == before, "sha256": expected, "bytes_read": len(payload)})
    if path.name == "validation_parameters.json": COUNTS["validation_formula_decode_count"] += 1
    elif path.suffix == ".npz": COUNTS["validation_state_decode_count"] += 1
    else: COUNTS["validation_trajectory_metadata_decode_count"] += 1
    return payload


def read_for_actor(actor: str, path: str | Path) -> bytes:
    candidate = Path(path).resolve(strict=True)
    if candidate.is_relative_to(SEALED_ROOT):
        raise PermissionError("Stage06B sealed-test access denied before payload read")
    if candidate.is_relative_to(VALIDATION_ROOT): return _read_validation(candidate, actor)
    if candidate.is_relative_to(TRAIN_TRAJECTORY_ROOT):
        match = TRAIN_TRAJECTORY.fullmatch(candidate.name)
        if actor in TRAIN_ACTORS and match and match.group(1) in TRAIN_LINEAGES:
            COUNTS["train_state_decode_count"] += 1; return candidate.read_bytes()
    if candidate.is_relative_to(TRAIN_TARGET_ROOT):
        match = TRAIN_TARGET.fullmatch(candidate.name)
        if actor in TRAIN_ACTORS and match and match.group(1).lower() in TRAIN_LINEAGES:
            COUNTS["train_target_decode_count"] += 1; return candidate.read_bytes()
    raise PermissionError("Stage06B path/actor access denied before payload read")


def load_npz(actor: str, path: str | Path) -> dict[str, Any]:
    with np.load(io.BytesIO(read_for_actor(actor, path)), allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def load_json(actor: str, path: str | Path) -> dict[str, Any]:
    return json.loads(read_for_actor(actor, path).decode("utf-8"))
