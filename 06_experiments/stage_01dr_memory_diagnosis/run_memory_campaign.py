"""Run the preregistered Stage 01D-R cases serially in fresh processes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from resource_diagnostics.rss_sampler import process_exists  # noqa: E402

from audit_stage01d_freeze import audit as audit_stage01d_freeze  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_memory_diagnosis.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
LOG_ROOT = EXPERIMENT_ROOT / "logs"
WORKER_PATH = (
    PROJECT_ROOT
    / "01_solver"
    / "resource_diagnostics"
    / "memory_variant_runner.py"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()


def _source_tree_changes() -> list[str]:
    output = subprocess.check_output(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=PROJECT_ROOT,
        text=True,
    )
    allowed = (
        "06_experiments/stage_01dr_memory_diagnosis/results/",
        "06_experiments/stage_01dr_memory_diagnosis/logs/",
        "06_experiments/stage_01dr_memory_diagnosis/snapshots/",
        "06_experiments/stage_01dr_memory_diagnosis/figures/",
    )
    changes: list[str] = []
    for line in output.splitlines():
        path = line[3:].split(" -> ")[-1]
        if not path.startswith(allowed):
            changes.append(line)
    return changes


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != value:
            raise RuntimeError(f"existing process evidence differs: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _run_id(job: dict[str, Any]) -> str:
    if job["kind"] == "numeric_regression":
        return f"stage01dr_frozen_regression_n{job['resolution']}"
    if job["kind"] == "sentinel":
        return (
            f"stage01dr_d_{job['mode']}_n{job['resolution']}_"
            f"r{job['repeat']}"
        )
    return (
        f"stage01dr_n{job['resolution']}_v{str(job['variant']).lower()}_"
        f"r{job['repeat']}"
    )


def _jobs(configuration: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    if phase in {"regression", "all"}:
        for resolution in (16, 32):
            selected.append(
                {
                    "kind": "numeric_regression",
                    "order": resolution,
                    "resolution": resolution,
                    "variant": "A",
                    "repeat": 1,
                    "mode": None,
                }
            )
    if phase in {"qualifying", "all"}:
        for entry in configuration["randomized_execution"]["qualifying_order"]:
            selected.append(
                {
                    "kind": "qualifying",
                    "order": int(entry["order"]),
                    "resolution": int(entry["resolution"]),
                    "variant": str(entry["variant"]),
                    "repeat": int(entry["repeat"]),
                    "mode": None,
                }
            )
    if phase in {"sentinel", "all"}:
        sentinel = configuration["variants"]["D"]
        for entry in configuration["randomized_execution"]["sentinel_order"]:
            selected.append(
                {
                    "kind": "sentinel",
                    "order": int(entry["order"]),
                    "resolution": int(sentinel["resolution"]),
                    "variant": "D",
                    "repeat": int(entry["repeat"]),
                    "mode": str(entry["mode"]),
                }
            )
    return selected


def _wait_for_absence(pid: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while process_exists(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def _worker_command(job: dict[str, Any]) -> list[str]:
    command = [
        sys.executable,
        str(WORKER_PATH),
        "--config",
        str(CONFIG_PATH),
        "--output-root",
        str(RESULTS_ROOT),
        "--resolution",
        str(job["resolution"]),
        "--repeat",
        str(job["repeat"]),
        "--variant",
        str(job["variant"]),
    ]
    if job["kind"] == "numeric_regression":
        command.append("--numeric-regression")
    if job["mode"] is not None:
        command.extend(("--mode", str(job["mode"])))
    return command


def _write_campaign_index(phase: str, rows: Iterable[dict[str, Any]]) -> None:
    path = RESULTS_ROOT / f"campaign_{phase}_index.csv"
    materialized = list(rows)
    if not materialized:
        return
    if path.exists():
        with path.open(newline="", encoding="utf-8") as stream:
            existing = list(csv.DictReader(stream))
        canonical = [
            {key: str(value) for key, value in row.items()}
            for row in materialized
        ]
        if existing != canonical:
            raise RuntimeError("existing campaign index differs")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(materialized[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(materialized)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("regression", "qualifying", "sentinel", "all"),
        required=True,
    )
    args = parser.parse_args()
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("status") != "PREREGISTERED_BEFORE_FIRST_STAGE_01DR_ROLLOUT":
        raise SystemExit("Stage 01D-R configuration is not preregistered")
    expected_environment = str(configuration["backend"]["python_environment"])
    if Path(sys.prefix).resolve().name != expected_environment:
        raise SystemExit(
            f"Stage 01D-R must run in isolated environment {expected_environment!r}"
        )
    audit_stage01d_freeze()
    changes = _source_tree_changes()
    if changes:
        raise SystemExit(
            "refusing Stage 01D-R campaign with source-tree changes: "
            + "; ".join(changes)
        )
    config_hash = _sha256(CONFIG_PATH)
    git_hash = _git_hash()
    jobs = _jobs(configuration, args.phase)
    index_rows: list[dict[str, Any]] = []
    all_passed = True
    for job in jobs:
        run_id = _run_id(job)
        summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
        exit_path = RESULTS_ROOT / "process_exit" / f"{run_id}.json"
        if summary_path.exists() and exit_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            exit_evidence = json.loads(exit_path.read_text(encoding="utf-8"))
            if (
                summary.get("config_hash") == config_hash
                and summary.get("git_hash") == git_hash
                and exit_evidence.get("config_hash") == config_hash
                and exit_evidence.get("git_hash") == git_hash
                and bool(exit_evidence.get("process_absent_after_wait"))
            ):
                print(f"{run_id}: SKIP immutable matching evidence")
                index_rows.append(exit_evidence)
                all_passed = all_passed and summary.get("status") == "PASS"
                continue
            raise SystemExit(f"existing evidence identity mismatch: {run_id}")
        if summary_path.exists() or exit_path.exists():
            raise SystemExit(f"incomplete existing worker evidence: {run_id}")

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        stdout_path = LOG_ROOT / f"{run_id}_stdout.log"
        stderr_path = LOG_ROOT / f"{run_id}_stderr.log"
        if stdout_path.exists() or stderr_path.exists():
            raise SystemExit(f"refusing to overwrite worker logs: {run_id}")
        started = time.time()
        with stdout_path.open("x", encoding="utf-8") as stdout_stream, stderr_path.open(
            "x", encoding="utf-8"
        ) as stderr_stream:
            process = subprocess.Popen(
                _worker_command(job),
                cwd=PROJECT_ROOT,
                stdout=stdout_stream,
                stderr=stderr_stream,
                text=True,
                shell=False,
            )
            pid = process.pid
            return_code = process.wait()
        ended = time.time()
        timeout = float(
            configuration["qualification"].get(
                "child_reclamation_timeout_seconds", 10.0
            )
        )
        absent = _wait_for_absence(pid, timeout)
        exit_evidence = {
            "run_id": run_id,
            "kind": job["kind"],
            "order": job["order"],
            "resolution": job["resolution"],
            "variant": job["variant"],
            "repeat": job["repeat"],
            "mode": "" if job["mode"] is None else job["mode"],
            "pid": pid,
            "return_code": return_code,
            "process_absent_after_wait": absent,
            "started_unix_seconds": started,
            "ended_unix_seconds": ended,
            "wall_seconds": ended - started,
            "config_hash": config_hash,
            "git_hash": git_hash,
            "stdout_log_path": stdout_path.relative_to(PROJECT_ROOT).as_posix(),
            "stderr_log_path": stderr_path.relative_to(PROJECT_ROOT).as_posix(),
        }
        _atomic_json(exit_path, exit_evidence)
        index_rows.append(exit_evidence)
        summary = (
            json.loads(summary_path.read_text(encoding="utf-8"))
            if summary_path.exists()
            else {}
        )
        passed = bool(
            return_code == 0
            and absent
            and summary.get("status") == "PASS"
        )
        all_passed = all_passed and passed
        print(
            f"{run_id}: {'PASS' if passed else 'FAIL'} "
            f"rc={return_code} reclaimed={absent} "
            f"wall={exit_evidence['wall_seconds']:.3f}s"
        )
        if (
            summary.get("failure_class") == "RESOURCE_SAFETY_STOP"
            or not absent
            or not summary_path.is_file()
            or return_code < 0
        ):
            break
    _write_campaign_index(args.phase, index_rows)
    return 0 if all_passed and len(index_rows) == len(jobs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
