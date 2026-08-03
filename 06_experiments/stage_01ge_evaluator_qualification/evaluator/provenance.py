"""Read-only provenance and SHA-256 helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


FROZEN_STAGE01G_CONFIG_SHA256 = "5025492f21f6b00c33ebc9533d27fbf632668945cba6a6a4a10df115c9ff1fe1"
FROZEN_STAGE01G_METRICS_SHA256 = "655bfceb2339adfd07d9a4c724cbb66410210a76b865f6edcc0d6a74c7b9b042"
FROZEN_STAGE01G_RUN_MATRIX_SHA256 = "ad79c1e7ea7af026222accc4ea8adff716c067b379954ca77697e475e5e0ba12"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha256_bytes(payload)


def verify_frozen_inputs(config_path: str | Path, metrics_path: str | Path, matrix_path: str | Path) -> dict[str, bool]:
    return {
        "stage01g_config": sha256_file(config_path) == FROZEN_STAGE01G_CONFIG_SHA256,
        "stage01g_metrics": sha256_file(metrics_path) == FROZEN_STAGE01G_METRICS_SHA256,
        "stage01g_run_matrix": sha256_file(matrix_path) == FROZEN_STAGE01G_RUN_MATRIX_SHA256,
    }


def build_evaluation_provenance(
    trajectory: Any,
    reference: Any,
    metadata: Any,
    config_sha256: str,
) -> dict[str, str]:
    if config_sha256 != FROZEN_STAGE01G_CONFIG_SHA256:
        raise ValueError("trajectory metadata is not bound to the frozen Stage 01G config")
    return {
        "trajectory_sha256": canonical_json_sha256(trajectory),
        "reference_sha256": canonical_json_sha256(reference),
        "metadata_sha256": canonical_json_sha256(metadata),
        "config_sha256": config_sha256,
    }
