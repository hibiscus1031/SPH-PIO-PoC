"""Audit the frozen Stage 01C tree without modifying any frozen file."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FROZEN_COMMIT = "275fafbb8c8e7ca4fd7384a8ff46b33215b34ced"
OUTPUT_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01d_fixed_physics_tgv"
    / "results"
    / "stage01c_sha256_manifest.csv"
)


def _git(*arguments: str) -> bytes:
    return subprocess.check_output(
        ("git", *arguments),
        cwd=PROJECT_ROOT,
    )


def _selected(path: str) -> bool:
    return (
        path.startswith("01_solver/structure_preserving/")
        or path.startswith("06_experiments/stage_01c_")
        or path.startswith("07_reports/stage_01c_")
        or path.startswith("tests/test_stage01c_")
    )


def _category(path: str) -> str:
    if path.startswith("07_reports/"):
        return "report"
    if "/configs/" in path:
        return "config"
    if "/results/" in path:
        return "machine_evidence"
    if path.endswith(".py"):
        return "code"
    return "figure_or_other"


def main() -> None:
    tracked = _git(
        "ls-tree",
        "-r",
        "--name-only",
        FROZEN_COMMIT,
    ).decode("utf-8").splitlines()
    paths = sorted(path for path in tracked if _selected(path))
    if not paths:
        raise RuntimeError("Stage 01C manifest selection is empty")

    rows: list[dict[str, str]] = []
    for relative in paths:
        frozen = _git("show", f"{FROZEN_COMMIT}:{relative}")
        current_path = PROJECT_ROOT / relative
        if not current_path.is_file():
            current = b""
            exists = False
        else:
            current = current_path.read_bytes()
            exists = True
        frozen_hash = hashlib.sha256(frozen).hexdigest()
        current_hash = hashlib.sha256(current).hexdigest() if exists else ""
        rows.append(
            {
                "category": _category(relative),
                "path": relative,
                "frozen_commit": FROZEN_COMMIT,
                "frozen_sha256": frozen_hash,
                "current_sha256": current_hash,
                "exists": str(exists),
                "matches_frozen_commit": str(exists and current_hash == frozen_hash),
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    failed = [row["path"] for row in rows if row["matches_frozen_commit"] != "True"]
    print(f"audited_files={len(rows)}")
    print(f"mismatches={len(failed)}")
    print(f"output={OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    if failed:
        raise RuntimeError(f"Stage 01C frozen-file mismatch: {failed}")


if __name__ == "__main__":
    main()
