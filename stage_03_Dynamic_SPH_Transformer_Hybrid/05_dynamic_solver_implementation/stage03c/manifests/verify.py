"""Read-only verifier for Stage 03C manifest file hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verify_manifest(root: Path, manifest_path: Path, groups: tuple[str, ...]) -> dict[str, bool]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    for group in groups:
        for item in manifest.get(group, []):
            path = root / item["path"]
            actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            checks[item["path"]] = actual == item["sha256"]
    return checks

