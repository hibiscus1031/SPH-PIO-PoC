"""Strict Phase A/Phase B coordinator for Stage 01G execution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01g_validation_execution"
MATRIX = ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv"
G_MANIFEST = ROOT / "06_experiments/stage_01gp_preexecution_audit/manifests/stage01g_frozen_sha256_manifest.csv"
GE_MANIFEST = ROOT / "06_experiments/stage_01ge_evaluator_qualification/manifests/stage01ge_evaluator_sha256.csv"
SOURCE_MANIFEST = ROOT / "06_experiments/stage_01f5b_requalification_execution/manifests/numerical_source_identity.csv"
EXECUTION_MANIFEST = STAGE / "manifests/stage01g_execution_code_sha256_retry2.csv"
WORKER = STAGE / "stage01g_worker.py"
FROZEN_PYTHON = Path("/opt/miniconda3/envs/sph-pio-poc/bin/python").resolve()
PREFLIGHT_V2_COMMIT = "a07ef533a85cece78eed99ffd7f650757b33e838"
STAGE01G_COMMIT = "fa3c4f43625ec3436820d83c26947d47ed0ba5c8"
STAGE01G_TAG = "stage-01g-independent-validation-design-approved"
PHASES = {
    "A": (
        "g_shear_n24",
        "g_shear_n32",
        "g_shear_n48",
        "g_shear_n32_dt_half",
        "g_shear_n48_rep2",
    ),
    "B": (
        "g_acoustic_e5e3_n24",
        "g_acoustic_e5e3_n32",
        "g_acoustic_e5e3_n48",
        "g_acoustic_e5e3_n32_dt_half",
        "g_acoustic_e5e3_n48_rep2",
        "g_acoustic_e2p5e3_n48",
        "g_acoustic_e1e2_n48",
    ),
}
INDEX_COLUMNS = (
    "phase",
    "run_id",
    "attempt_id",
    "pid",
    "return_code",
    "status",
    "child_reclaimed",
    "parent_scalar_only",
    "stdout_log",
    "stderr_log",
    "wall_time_seconds",
    "code_git_hash",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def scalar_tree(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, dict):
        return all(isinstance(key, str) and scalar_tree(item) for key, item in value.items())
    return False


def verify_manifest(path: Path, expected_count: int, hash_key: str) -> bool:
    rows = read_csv(path)
    return len(rows) == expected_count and all(
        (ROOT / row["path"]).is_file() and sha256(ROOT / row["path"]) == row[hash_key]
        for row in rows
    )


def selected_status_path(run_id: str) -> Path:
    suffix = ".infra_retry2" if run_id == "g_shear_n24" else ""
    return STAGE / "runs" / run_id / f"status{suffix}.json"


def preflight(phase: str, infrastructure_retry: str = "") -> dict[str, Any]:
    matrix = read_csv(MATRIX)
    matrix_ids = [row["run_id"] for row in matrix]
    expected_ids = list(PHASES["A"] + PHASES["B"])
    output_dirs = {row["run_id"]: ROOT / row["future_output_directory"] for row in matrix}
    source_rows = read_csv(SOURCE_MANIFEST)
    preflight_paths = (
        "06_experiments/stage_01g_execution_preflight_v2",
        "07_reports/stage01g_preflight_v2_identity.md",
        "07_reports/stage01g_preflight_v2_evaluator.md",
        "07_reports/stage01g_preflight_v2_matrix.md",
        "07_reports/stage01g_preflight_v2_risk.md",
        "07_reports/stage01g_preflight_v2_final.md",
    )
    preflight_drift = subprocess.run(
        ("git", "diff", "--quiet", PREFLIGHT_V2_COMMIT, "--", *preflight_paths),
        cwd=ROOT,
    ).returncode
    authorization = json.loads(
        (ROOT / "06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json").read_text()
    )
    checks = {
        "frozen_python_environment": Path(sys.executable).resolve() == FROZEN_PYTHON,
        "preflight_v2_commit_is_ancestor": subprocess.run(
            ("git", "merge-base", "--is-ancestor", PREFLIGHT_V2_COMMIT, "HEAD"), cwd=ROOT
        ).returncode == 0,
        "preflight_v2_bundle_unchanged": preflight_drift == 0,
        "preflight_v2_authorized": authorization["unique_status"] == "INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED" and all(authorization["checks"].values()),
        "stage01g_tag_identity": git("cat-file", "-t", STAGE01G_TAG) == "tag" and git("rev-list", "-n", "1", STAGE01G_TAG) == STAGE01G_COMMIT,
        "stage01g_9_hash_identity": verify_manifest(G_MANIFEST, 9, "sha256"),
        "stage01ge_9_hash_identity": verify_manifest(GE_MANIFEST, 9, "sha256"),
        "numerical_source_103_hash_identity": len(source_rows) == 103 and all(sha256(ROOT / row["path"]) == row["frozen_sha256"] for row in source_rows),
        "execution_code_3_hash_identity": verify_manifest(EXECUTION_MANIFEST, 3, "sha256"),
        "exact_12_run_matrix": len(matrix) == 12 and matrix_ids == expected_ids and len(set(matrix_ids)) == 12,
        "unique_12_output_directories": len({str(path) for path in output_dirs.values()}) == 12,
        "phase_output_directories_available": all(
            (
                bool(infrastructure_retry)
                and phase == "A"
                and run_id == "g_shear_n24"
                and output_dirs[run_id].is_dir()
            )
            or not output_dirs[run_id].exists()
            for run_id in PHASES[phase]
        ),
        "worker_exists": WORKER.is_file(),
        "parent_scalar_contract": scalar_tree({"run_id": "x", "status": "PASS", "failure_type": ""}),
    }
    if infrastructure_retry:
        predecessor_suffix = "" if infrastructure_retry == "infra_retry1" else ".infra_retry1"
        predecessor_type = "TypeError" if infrastructure_retry == "infra_retry1" else "KeyError"
        predecessor = STAGE / "runs/g_shear_n24" / f"summary{predecessor_suffix}.json"
        checks["predecessor_infrastructure_failure_preserved"] = (
            phase == "A"
            and predecessor.exists()
            and json.loads(predecessor.read_text()).get("failure_type") == predecessor_type
            and not (STAGE / "checkpoints" / f"g_shear_n24{predecessor_suffix}.npz").exists()
            and not (STAGE / "references" / f"g_shear_n24{predecessor_suffix}.npz").exists()
            and not (STAGE / "runs/g_shear_n24" / f"evaluator_result{predecessor_suffix}.json").exists()
        )
    if phase == "B":
        checks["phase_a_completed_first"] = all(
            selected_status_path(run_id).exists()
            and json.loads(selected_status_path(run_id).read_text())["status"] == "PASS"
            for run_id in PHASES["A"]
        )
    return {
        "phase": phase,
        "infrastructure_retry": infrastructure_retry or None,
        "checks": checks,
        "overall_status": "PASS" if all(checks.values()) else "FAIL",
        "code_git_hash": git("rev-parse", "HEAD"),
        "benchmark_runs_started_by_this_preflight": 0,
    }


def append_index(row: dict[str, Any]) -> None:
    path = STAGE / "manifests/stage01g_campaign_index_retry2.csv"
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_COLUMNS, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("A", "B"), required=True)
    retries = parser.add_mutually_exclusive_group()
    retries.add_argument("--infrastructure-retry1", action="store_true")
    retries.add_argument("--infrastructure-retry2", action="store_true")
    args = parser.parse_args()
    phase = args.phase
    infrastructure_retry = "infra_retry2" if args.infrastructure_retry2 else "infra_retry1" if args.infrastructure_retry1 else ""
    if infrastructure_retry and phase != "A":
        raise ValueError("a preserved infrastructure retry applies only to Phase A")
    audit = preflight(phase, infrastructure_retry)
    result_suffix = f"_{infrastructure_retry}" if infrastructure_retry else ""
    audit_path = STAGE / "results" / f"stage01g_phase_{phase.lower()}_preflight{result_suffix}.json"
    if audit_path.exists():
        raise RuntimeError(f"refusing to overwrite {audit_path.relative_to(ROOT)}")
    atomic_json(audit_path, audit)
    print(json.dumps({"phase": phase, "preflight": audit["overall_status"]}), flush=True)
    if audit["overall_status"] != "PASS":
        return 2

    phase_rows: list[dict[str, Any]] = []
    for ordinal, run_id in enumerate(PHASES[phase], start=1):
        attempt_id = infrastructure_retry if infrastructure_retry and run_id == "g_shear_n24" else "canonical"
        artifact_suffix = f".{attempt_id}" if attempt_id != "canonical" else ""
        run_dir = STAGE / "runs" / run_id
        if run_dir.exists() and attempt_id == "canonical":
            raise RuntimeError(f"refusing to overwrite {run_dir.relative_to(ROOT)}")
        if not run_dir.exists():
            run_dir.mkdir(parents=True)
        stdout_path = STAGE / "logs" / f"{run_id}{artifact_suffix}.stdout.log"
        stderr_path = STAGE / "logs" / f"{run_id}{artifact_suffix}.stderr.log"
        if stdout_path.exists() or stderr_path.exists():
            raise RuntimeError("refusing to overwrite an existing run log")
        started = time.perf_counter()
        print(json.dumps({"phase": phase, "ordinal": ordinal, "run_id": run_id, "event": "LAUNCH"}), flush=True)
        command = [str(FROZEN_PYTHON), str(WORKER), "--run-id", run_id]
        if attempt_id != "canonical":
            command.extend(("--attempt-id", attempt_id))
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        atomic_json(
            run_dir / f"status{artifact_suffix}.json",
            {"phase": phase, "run_id": run_id, "attempt_id": attempt_id, "status": "RUNNING", "pid": process.pid},
        )
        last_heartbeat = started
        while process.poll() is None:
            time.sleep(5.0)
            now = time.perf_counter()
            if now - last_heartbeat >= 60.0:
                print(
                    json.dumps(
                        {"phase": phase, "run_id": run_id, "event": "RUNNING", "elapsed_seconds": round(now - started, 1)}
                    ),
                    flush=True,
                )
                last_heartbeat = now
        stdout, stderr = process.communicate()
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        nonempty = [line for line in stdout.splitlines() if line.strip()]
        child = json.loads(nonempty[-1]) if nonempty else {"run_id": run_id, "status": "FAIL", "failure_type": "MissingScalarResult", "failure_message": "worker produced no scalar result"}
        scalar = scalar_tree(child)
        reclaimed = process.poll() is not None
        status = "PASS" if process.returncode == 0 and child.get("status") == "PASS" and scalar and reclaimed else "FAIL"
        wall = time.perf_counter() - started
        marker = {
            "phase": phase,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "status": status,
            "pid": process.pid,
            "return_code": process.returncode,
            "child_reclaimed": reclaimed,
            "parent_scalar_only": scalar,
            "wall_time_seconds": wall,
        }
        atomic_json(run_dir / f"status{artifact_suffix}.json", marker)
        index_row = {
            "phase": phase,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "pid": process.pid,
            "return_code": process.returncode,
            "status": status,
            "child_reclaimed": reclaimed,
            "parent_scalar_only": scalar,
            "stdout_log": stdout_path.relative_to(ROOT).as_posix(),
            "stderr_log": stderr_path.relative_to(ROOT).as_posix(),
            "wall_time_seconds": wall,
            "code_git_hash": git("rev-parse", "HEAD"),
        }
        append_index(index_row)
        phase_rows.append(index_row)
        print(json.dumps({"phase": phase, "run_id": run_id, "event": "COMPLETE", "status": status, "wall_time_seconds": round(wall, 3)}), flush=True)
        if status != "PASS":
            break

    phase_status = "PASS" if len(phase_rows) == len(PHASES[phase]) and all(row["status"] == "PASS" for row in phase_rows) else "FAIL"
    phase_result = {
        "phase": phase,
        "infrastructure_retry": infrastructure_retry or None,
        "expected_run_ids": list(PHASES[phase]),
        "executed_run_ids": [row["run_id"] for row in phase_rows],
        "run_count": len(phase_rows),
        "all_children_reclaimed": bool(phase_rows) and all(row["child_reclaimed"] for row in phase_rows),
        "all_parent_aggregation_scalar_only": bool(phase_rows) and all(row["parent_scalar_only"] for row in phase_rows),
        "status": phase_status,
        "code_git_hash": git("rev-parse", "HEAD"),
    }
    phase_result_path = STAGE / "results" / f"stage01g_phase_{phase.lower()}_execution{result_suffix}.json"
    if phase_result_path.exists():
        raise RuntimeError(f"refusing to overwrite {phase_result_path.relative_to(ROOT)}")
    atomic_json(phase_result_path, phase_result)
    print(json.dumps({"phase": phase, "status": phase_status, "run_count": len(phase_rows)}), flush=True)
    return 0 if phase_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
