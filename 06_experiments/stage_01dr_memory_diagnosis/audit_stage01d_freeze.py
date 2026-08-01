"""Verify the immutable Stage 01D evidence boundary for Stage 01D-R."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_memory_diagnosis.yml"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ("git", *args),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()


def audit() -> dict[str, object]:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    frozen = configuration["frozen_stage_01d"]
    formal = str(frozen["formal_run_commit"])
    evidence = str(frozen["final_evidence_commit"])
    if _git("cat-file", "-t", formal) != "commit":
        raise RuntimeError("formal Stage 01D run commit is missing")
    if _git("cat-file", "-t", evidence) != "commit":
        raise RuntimeError("final Stage 01D evidence commit is missing")
    tag = str(frozen["annotated_tag"])
    if _git("cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise RuntimeError("Stage 01D freeze tag is not annotated")
    tag_target = _git("rev-list", "-n", "1", tag)
    if tag_target != str(frozen["required_tag_target"]):
        raise RuntimeError("Stage 01D freeze tag target mismatch")
    status_path = (
        PROJECT_ROOT
        / "06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt"
    )
    if status_path.read_bytes() != b"V2_FAIL\n":
        raise RuntimeError("frozen Stage 01D status changed")

    manifest_path = PROJECT_ROOT / str(frozen["sha256_manifest"])
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != int(frozen["expected_manifest_rows"]):
        raise RuntimeError("Stage 01D freeze manifest row-count mismatch")
    mismatches: list[str] = []
    categories: dict[str, int] = {}
    for row in rows:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            mismatches.append(row["path"])
            continue
        path = PROJECT_ROOT / relative
        categories[row["category"]] = categories.get(row["category"], 0) + 1
        if not path.is_file():
            mismatches.append(row["path"])
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"] or path.stat().st_size != int(row["bytes"]):
            mismatches.append(row["path"])
    if mismatches:
        raise RuntimeError(
            "frozen Stage 01D evidence mismatch: " + ", ".join(mismatches)
        )
    expected_categories = {
        "report": 8,
        "status": 1,
        "gate_evidence": 1,
        "run_summary": 1,
        "failure_stack": 1,
        "state_archive": 3,
    }
    if categories != expected_categories:
        raise RuntimeError("Stage 01D freeze manifest category mismatch")
    return {
        "formal_run_commit": formal,
        "final_evidence_commit": evidence,
        "tag": tag,
        "tag_target": tag_target,
        "manifest_rows": len(rows),
        "mismatches": 0,
        "categories": categories,
        "old_status": "V2_FAIL",
    }


def main() -> int:
    result = audit()
    print(f"manifest_rows={result['manifest_rows']}")
    print(f"mismatches={result['mismatches']}")
    print(f"tag_target={result['tag_target']}")
    print(f"old_status={result['old_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
