"""Stage 05B payload allowlist; denial occurs before byte reads or NPZ decode."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve()
STAGE05B = HERE.parents[1]
ROOT = HERE.parents[4]
TRAIN_ROOT = (
    ROOT
    / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/exact_trajectories/train"
).resolve()
ALLOWED_LINEAGES = {"lcdf_01", "lcdf_04", "lcdf_05", "lcdf_06", "lcdf_07", "lcdf_08"}
ALLOWED_VARIANTS = {"variant_low", "variant_main"}
ALLOWED_RESOLUTIONS = {8, 12, 16}
NAME = re.compile(r"^(lcdf_\d{2})_(variant_(?:low|main))_n(8|12|16)\.(npz|json)$")


def _authorized(path: str | Path) -> Path:
    candidate = Path(path)
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(TRAIN_ROOT):
        raise PermissionError("Stage05B access denied before payload read: outside TRAIN root")
    match = NAME.fullmatch(resolved.name)
    if match is None:
        raise PermissionError("Stage05B access denied before payload read: filename outside frozen schema")
    lineage, variant, resolution, _suffix = match.groups()
    if lineage not in ALLOWED_LINEAGES or variant not in ALLOWED_VARIANTS or int(resolution) not in ALLOWED_RESOLUTIONS:
        raise PermissionError("Stage05B access denied before payload read: role or stratum not authorized")
    return resolved


def read_train_bytes(path: str | Path) -> bytes:
    return _authorized(path).read_bytes()


def load_train_npz(path: str | Path) -> dict[str, Any]:
    payload = read_train_bytes(path)
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def load_train_json(path: str | Path) -> dict[str, Any]:
    import json
    return json.loads(read_train_bytes(path).decode("utf-8"))
