"""Immutable bindings for the Stage 01G formal execution reapplication."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "06_experiments/stage_01g_validation_execution"
APPLICATION = STAGE / "reapplication_01"
ATTEMPT_ID = "reapplication_01"
MATRIX = ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv"
CONFIG = ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"
METRICS = ROOT / "07_reports/stage_01g_validation_metrics.md"
G_MANIFEST = ROOT / "06_experiments/stage_01gp_preexecution_audit/manifests/stage01g_frozen_sha256_manifest.csv"
GE_MANIFEST = ROOT / "06_experiments/stage_01ge_evaluator_qualification/manifests/stage01ge_evaluator_sha256.csv"
SOURCE_MANIFEST = ROOT / "06_experiments/stage_01f5b_requalification_execution/manifests/numerical_source_identity.csv"
GR_CODE_MANIFEST = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair/manifests/stage01gr_repair_code_sha256.csv"
GR_EVIDENCE_MANIFEST = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair/manifests/stage01gr_evidence_sha256.csv"
GR_EVALUATION = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair/results/stage01gr_evaluation.json"
PREFLIGHT_V2 = ROOT / "06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json"
PREFLIGHT_RESULT = APPLICATION / "stage01g_execution_preflight_final.json"
PREFLIGHT_REPORT = ROOT / "07_reports/stage01g_execution_preflight_final.md"
FROZEN_PYTHON = Path("/opt/miniconda3/envs/sph-pio-poc/bin/python").resolve()

STAGE01G_COMMIT = "fa3c4f43625ec3436820d83c26947d47ed0ba5c8"
STAGE01GP_COMMIT = "c58c6ce4e7798a708adee32af984209aca064a95"
STAGE01GE_COMMIT = "1641ff5f05fa91b8faed49a91edf062f4a90db07"
STAGE01GR_COMMIT = "d4d253be91becdac39f1894a7a010b9b61571055"
STAGE01G_TAG = "stage-01g-independent-validation-design-approved"
CONFIG_SHA256 = "5025492f21f6b00c33ebc9533d27fbf632668945cba6a6a4a10df115c9ff1fe1"
MATRIX_SHA256 = "ad79c1e7ea7af026222accc4ea8adff716c067b379954ca77697e475e5e0ba12"
METRICS_SHA256 = "655bfceb2339adfd07d9a4c724cbb66410210a76b865f6edcc0d6a74c7b9b042"

SHEAR_IDS = (
    "g_shear_n24", "g_shear_n32", "g_shear_n48",
    "g_shear_n32_dt_half", "g_shear_n48_rep2",
)
ACOUSTIC_IDS = (
    "g_acoustic_e5e3_n24", "g_acoustic_e5e3_n32", "g_acoustic_e5e3_n48",
    "g_acoustic_e5e3_n32_dt_half", "g_acoustic_e5e3_n48_rep2",
    "g_acoustic_e2p5e3_n48", "g_acoustic_e1e2_n48",
)
ALL_IDS = SHEAR_IDS + ACOUSTIC_IDS
CODE_FILES = (
    APPLICATION / "stage01g_reapplication_contract.py",
    APPLICATION / "stage01g_reapplication_preflight.py",
    APPLICATION / "stage01g_reapplication_worker.py",
    APPLICATION / "run_stage01g_reapplication.py",
    APPLICATION / "evaluate_stage01g_reapplication.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_new(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_text_new(path: Path, payload: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()


def verify_manifest(path: Path, expected_count: int, hash_field: str) -> bool:
    rows = read_csv(path)
    return len(rows) == expected_count and all(
        (ROOT / row["path"]).is_file() and sha256(ROOT / row["path"]) == row[hash_field]
        for row in rows
    )


def matrix_rows() -> list[dict[str, str]]:
    rows = read_csv(MATRIX)
    if len(rows) != 12 or tuple(row["run_id"] for row in rows) != ALL_IDS:
        raise ValueError("frozen run matrix is not the exact ordered 12-run identity")
    if len({row["run_id"] for row in rows}) != 12:
        raise ValueError("frozen run IDs are not unique")
    return rows


def matrix_row(run_id: str) -> dict[str, str]:
    matches = [row for row in matrix_rows() if row["run_id"] == run_id]
    if len(matches) != 1 or matches[0]["stage01g_status"] != "PREREGISTERED_NOT_EXECUTED":
        raise ValueError(f"invalid frozen run identity: {run_id}")
    return matches[0]


def attempt_run_dir(run_id: str) -> Path:
    return STAGE / "runs" / run_id / ATTEMPT_ID


def checkpoint_path(run_id: str) -> Path:
    return STAGE / "checkpoints" / f"{run_id}.{ATTEMPT_ID}.npz"


def reference_path(run_id: str) -> Path:
    return STAGE / "references" / f"{run_id}.{ATTEMPT_ID}.npz"


def evaluator_path(run_id: str) -> Path:
    return STAGE / "evaluator_results" / f"{run_id}.{ATTEMPT_ID}.json"


def log_paths(run_id: str) -> tuple[Path, Path]:
    base = STAGE / "logs" / f"{run_id}.{ATTEMPT_ID}"
    return Path(str(base) + ".stdout.log"), Path(str(base) + ".stderr.log")


def execution_code_hashes() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in CODE_FILES}


def frozen_python_guard() -> None:
    if Path(sys.executable).resolve() != FROZEN_PYTHON:
        raise RuntimeError("formal execution requires the frozen sph-pio-poc Python environment")


def preflight_code_guard() -> None:
    evidence = read_json(PREFLIGHT_RESULT)
    expected = evidence["execution_code_sha256"]
    if execution_code_hashes() != expected:
        raise RuntimeError("formal execution adapter identity drift after final preflight")
    if evidence["overall_status"] != "PASS":
        raise RuntimeError("final execution preflight is not PASS")
