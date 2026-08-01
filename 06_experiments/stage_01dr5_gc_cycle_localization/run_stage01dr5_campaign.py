"""Resumable serial coordinator for the 24 Stage 01D-R5 workers."""

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
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr5_gc_cycle_localization"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_gc_cycle_localization.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
LOGS_ROOT = EXPERIMENT_ROOT / "logs"
WORKER = EXPERIMENT_ROOT / "stage01dr5_worker.py"
INDEX_PATH = RESULTS_ROOT / "campaign_index.csv"
SUMMARY_PATH = RESULTS_ROOT / "campaign_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_clean() -> None:
    output = subprocess.check_output(("git", "status", "--porcelain", "--untracked-files=all"), cwd=PROJECT_ROOT, text=True)
    allowed = (
        "06_experiments/stage_01dr5_gc_cycle_localization/results/",
        "06_experiments/stage_01dr5_gc_cycle_localization/logs/",
        "06_experiments/stage_01dr5_gc_cycle_localization/figures/",
        "07_reports/stage_01dr5_",
    )
    unexpected = [line for line in output.splitlines() if not line[3:].startswith(allowed)]
    if unexpected:
        raise RuntimeError("source tree is not clean: " + " | ".join(unexpected))


def _reclaimed(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("R5 campaign requires sph-pio-poc")
    if SUMMARY_PATH.exists():
        if args.resume:
            print(SUMMARY_PATH.read_text(encoding="utf-8"), end="")
            return 0
        raise RuntimeError("R5 campaign already complete")
    _source_clean()
    fields = (
        "order", "run_id", "mode", "repeat", "steps", "return_code", "worker_status",
        "elapsed_seconds", "pid", "process_reclaimed", "summary_path", "stdout_path",
        "stderr_path", "git_hash", "config_sha256",
    )
    existing: dict[str, dict[str, str]] = {}
    if INDEX_PATH.exists():
        if not args.resume:
            raise RuntimeError("campaign index exists; use --resume")
        with INDEX_PATH.open(newline="", encoding="utf-8") as stream:
            existing = {row["run_id"]: row for row in csv.DictReader(stream)}
    else:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INDEX_PATH.open("x", newline="", encoding="utf-8") as stream:
            csv.DictWriter(stream, fieldnames=fields, lineterminator="\n").writeheader()
    tasks: list[tuple[str, int]] = [("L1", 1)]
    for repeat in (1, 2, 3):
        tasks.extend((mode, repeat) for mode in ("G1", "G2", "G3"))
    for repeat in (1, 2, 3):
        tasks.extend((mode, repeat) for mode in ("I0", "I1", "I2", "I3", "I4"))
    git_hash = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()
    config_hash = _sha256(CONFIG_PATH)
    for order, (mode, repeat) in enumerate(tasks, start=1):
        run_id = f"stage01dr5_{mode.lower()}_r{repeat}"
        if run_id in existing:
            continue
        LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        stdout_path = LOGS_ROOT / f"{run_id}_stdout.log"
        stderr_path = LOGS_ROOT / f"{run_id}_stderr.log"
        if stdout_path.exists() or stderr_path.exists():
            raise RuntimeError(f"refusing to overwrite logs for {run_id}")
        command = (sys.executable, str(WORKER), "--mode", mode, "--repeat", str(repeat))
        started = time.perf_counter()
        with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
            process = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=stdout, stderr=stderr, text=True)
            pid = int(process.pid)
            return_code = int(process.wait())
        elapsed = time.perf_counter() - started
        summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        row = {
            "order": order,
            "run_id": run_id,
            "mode": mode,
            "repeat": repeat,
            "steps": 200 if mode == "L1" else (2000 if mode.startswith("G") else 500),
            "return_code": return_code,
            "worker_status": summary.get("status", "MISSING"),
            "elapsed_seconds": f"{elapsed:.9f}",
            "pid": pid,
            "process_reclaimed": _reclaimed(pid),
            "summary_path": summary_path.relative_to(PROJECT_ROOT).as_posix(),
            "stdout_path": stdout_path.relative_to(PROJECT_ROOT).as_posix(),
            "stderr_path": stderr_path.relative_to(PROJECT_ROOT).as_posix(),
            "git_hash": git_hash,
            "config_sha256": config_hash,
        }
        with INDEX_PATH.open("a", newline="", encoding="utf-8") as stream:
            csv.DictWriter(stream, fieldnames=fields, lineterminator="\n").writerow(row)
        existing[run_id] = {key: str(value) for key, value in row.items()}
        print(json.dumps({"completed": run_id, "status": row["worker_status"], "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    rows = list(existing.values())
    _write_json(
        SUMMARY_PATH,
        {
            "schema_version": "sph-pio-poc.stage01dr5.campaign.v1",
            "git_hash": git_hash,
            "config_sha256": config_hash,
            "expected_processes": len(tasks),
            "observed_processes": len(rows),
            "pass_processes": sum(row.get("worker_status") == "PASS" for row in rows),
            "all_processes_reclaimed": all(row.get("process_reclaimed") in {True, "True"} for row in rows),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
