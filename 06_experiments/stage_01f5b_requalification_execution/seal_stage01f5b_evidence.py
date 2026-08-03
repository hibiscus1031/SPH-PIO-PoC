"""Write the final no-overwrite SHA-256 inventory for Stage 01F5B evidence."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
OUTPUT = STAGE / "manifests/stage01f5b_final_evidence_sha256.csv"

EXTERNAL_EVIDENCE = (
    ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/stage01f5_execution_run_matrix_v2.csv",
    ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/n64_dependency_dag.json",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/configs/formal_space_common_times.csv",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/configs/formal_space_horizon_amendment.yml",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/manifests/stage01f5_execution_bundle_v3.json",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/manifests/stage01f5p_frozen_sha256_manifest.csv",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/manifests/stage01f5q_space_parameter_binding.csv",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_dry_resolution_audit.csv",
    ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_evaluation.json",
    ROOT / "07_reports/stage_01f5q_final_report.md",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def classification(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if relative.startswith("07_reports/stage_01f5b_"):
        return "stage01f5b_report"
    if relative.startswith("tests/test_stage01f5b_"):
        return "stage01f5b_test"
    if path in EXTERNAL_EVIDENCE:
        return "frozen_input"
    if "/checkpoints/" in f"/{relative}":
        return "checkpoint"
    if "/references/" in f"/{relative}":
        return "reference"
    if "/logs/" in f"/{relative}":
        return "log"
    if "/runs/" in f"/{relative}":
        return "run_evidence"
    if "/results/" in f"/{relative}":
        return "aggregate_result"
    if "/manifests/" in f"/{relative}":
        return "manifest"
    return "stage01f5b_implementation"


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite {OUTPUT.relative_to(ROOT)}")
    paths = {
        path
        for path in STAGE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path != OUTPUT
    }
    paths.update(ROOT.glob("07_reports/stage_01f5b_*.md"))
    paths.update(ROOT.glob("tests/test_stage01f5b_*.py"))
    paths.update(EXTERNAL_EVIDENCE)
    missing = [path for path in EXTERNAL_EVIDENCE if not path.exists()]
    if missing:
        raise RuntimeError(f"missing frozen evidence: {[path.relative_to(ROOT).as_posix() for path in missing]}")
    with OUTPUT.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("path", "bytes", "sha256", "classification"), lineterminator="\n")
        writer.writeheader()
        for path in sorted(paths):
            writer.writerow(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                    "classification": classification(path),
                }
            )
    print(f"sealed {len(paths)} files: {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
