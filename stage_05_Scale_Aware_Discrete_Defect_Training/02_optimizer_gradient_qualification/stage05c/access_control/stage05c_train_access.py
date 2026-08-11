"""Stage 05C dual-root TRAIN allowlist; all other payloads are denied before read."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import numpy as np


HERE=Path(__file__).resolve(); STAGE05C=HERE.parents[1]; STAGE05=HERE.parents[3]; ROOT=HERE.parents[4]
TRAJECTORY_ROOT=(ROOT/"stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/exact_trajectories/train").resolve()
TARGET_ROOT=(STAGE05/"01_defect_target_qualification/stage05b/target_records").resolve()
ALLOWED={"lcdf_01","lcdf_04","lcdf_05","lcdf_06","lcdf_07","lcdf_08"}
TRAJECTORY=re.compile(r"^(lcdf_\d{2})_(variant_(?:low|main))_n(8|12|16)\.(npz|json)$")
TARGET=re.compile(r"^(LCDF_\d{2})_(VARIANT_(?:LOW|MAIN))_N8_O(\d{2})\.(npz|json)$")


def _authorized(path:str|Path)->Path:
    resolved=Path(path).resolve(strict=True)
    if resolved.is_relative_to(TRAJECTORY_ROOT):
        match=TRAJECTORY.fullmatch(resolved.name)
        if match and match.group(1) in ALLOWED: return resolved
    if resolved.is_relative_to(TARGET_ROOT):
        match=TARGET.fullmatch(resolved.name)
        if match and match.group(1).lower() in ALLOWED and int(match.group(3))<32: return resolved
    raise PermissionError("Stage05C access denied before payload read")


def read_bytes(path:str|Path)->bytes: return _authorized(path).read_bytes()
def load_npz(path:str|Path)->dict[str,Any]:
    with np.load(io.BytesIO(read_bytes(path)),allow_pickle=False) as archive: return {k:archive[k] for k in archive.files}
def load_json(path:str|Path)->dict[str,Any]: return json.loads(read_bytes(path).decode("utf-8"))
