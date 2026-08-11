"""Stage 04C development-data allowlist for the frozen Stage 04B pool.

Only TRAIN_LINEAGE payloads under exact_trajectories/train are readable.
Validation and sealed-test payloads are rejected before an OS-level read.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve()
STAGE04B = HERE.parents[1]
TRAIN_ROOT = (STAGE04B / "exact_trajectories" / "train").resolve()


def _authorized(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(TRAIN_ROOT):
        raise PermissionError("Stage04C access denied: only TRAIN_LINEAGE payloads are authorized")
    return resolved


def read_train_bytes(path: str | Path) -> bytes:
    return _authorized(Path(path)).read_bytes()


def load_train_npz(path: str | Path) -> dict[str, Any]:
    payload = read_train_bytes(path)
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}
