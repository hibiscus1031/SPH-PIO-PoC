"""Serial parent coordinator for three isolated Stage 01D-P canaries."""

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

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_resource_policy.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
LOGS_ROOT = EXPERIMENT_ROOT / "logs"
WORKER_PATH = EXPERIMENT_ROOT / "stage01dp_worker.py"
INDEX_PATH = RESULTS_ROOT / "campaign_index.csv"
SUMMARY_PATH = RESULTS_ROOT / "campaign_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(dict(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def current_rss_bytes(pid: int | None = None) -> int:
    target = os.getpid() if pid is None else int(pid)
    try:
        output = subprocess.check_output(
            ("/bin/ps", "-o", "rss=", "-p", str(target)),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        output = ""
    return int(output) * 1024 if output else 0


def process_reclaimed(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return False
    except ProcessLookupError:
        return current_rss_bytes(pid) == 0


def is_scalar_summary(value: Any) -> bool:
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_scalar_summary(item) for key, item in value.items())
    return value is None or isinstance(value, (bool, int, float, str))


def planned_repeats(configuration: Mapping[str, Any]) -> tuple[int, ...]:
    return tuple(range(1, int(configuration["canary"]["repeats"]) + 1))


def _source_clean() -> None:
    output = subprocess.check_output(
        ("git", "status", "--porcelain", "--untracked-files=all"),
        cwd=PROJECT_ROOT,
        text=True,
    )
    allowed = (
        "06_experiments/stage_01dp_resource_policy/results/",
        "06_experiments/stage_01dp_resource_policy/logs/",
        "07_reports/stage_01dp_",
    )
    unexpected = [line for line in output.splitlines() if not line[3:].startswith(allowed)]
    if unexpected:
        raise RuntimeError("source tree is not clean: " + " | ".join(unexpected))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("Stage 01D-P requires the sph-pio-poc environment")
    if SUMMARY_PATH.exists():
        if args.resume:
            print(SUMMARY_PATH.read_text(encoding="utf-8"), end="")
            return 0
        raise RuntimeError("Stage 01D-P campaign already complete")
    _source_clean()
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    fields = (
        "order", "run_id", "repeat", "steps", "return_code", "worker_status",
        "elapsed_seconds", "pid", "process_reclaimed", "child_rss_absent",
        "parent_rss_before_bytes", "parent_rss_after_bytes", "parent_rss_growth_from_baseline_bytes",
        "parent_received_scalar_summary_only", "summary_path", "stdout_path", "stderr_path",
        "git_hash", "config_sha256",
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
    baseline_parent_rss = current_rss_bytes()
    config_hash = _sha256(CONFIG_PATH)
    git_hash = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()
    for order, repeat in enumerate(planned_repeats(configuration), start=1):
        run_id = f"stage01dp_canary_r{repeat}"
        if run_id in existing:
            continue
        LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        stdout_path = LOGS_ROOT / f"{run_id}_stdout.log"
        stderr_path = LOGS_ROOT / f"{run_id}_stderr.log"
        if stdout_path.exists() or stderr_path.exists():
            raise RuntimeError(f"refusing to overwrite logs for {run_id}")
        parent_before = current_rss_bytes()
        command = (sys.executable, str(WORKER_PATH), "--repeat", str(repeat))
        started = time.perf_counter()
        with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
            process = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=stdout, stderr=stderr, text=True)
            pid = int(process.pid)
            return_code = int(process.wait())
        elapsed = time.perf_counter() - started
        reclaimed = process_reclaimed(pid)
        child_absent = current_rss_bytes(pid) == 0
        parent_after = current_rss_bytes()
        summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
        child_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        scalar_only = is_scalar_summary(child_summary)
        row = {
            "order": order,
            "run_id": run_id,
            "repeat": repeat,
            "steps": int(configuration["canary"]["steps"]),
            "return_code": return_code,
            "worker_status": child_summary.get("status", "MISSING"),
            "elapsed_seconds": f"{elapsed:.9f}",
            "pid": pid,
            "process_reclaimed": reclaimed,
            "child_rss_absent": child_absent,
            "parent_rss_before_bytes": parent_before,
            "parent_rss_after_bytes": parent_after,
            "parent_rss_growth_from_baseline_bytes": parent_after - baseline_parent_rss,
            "parent_received_scalar_summary_only": scalar_only,
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
    maximum_parent_growth = max((int(row["parent_rss_growth_from_baseline_bytes"]) for row in rows), default=0)
    _write_json(
        SUMMARY_PATH,
        {
            "schema_version": "sph-pio-poc.stage01dp.campaign.v1",
            "git_hash": git_hash,
            "config_sha256": config_hash,
            "expected_processes": len(planned_repeats(configuration)),
            "observed_processes": len(rows),
            "pass_processes": sum(row.get("worker_status") == "PASS" for row in rows),
            "all_processes_reclaimed": all(row.get("process_reclaimed") in {True, "True"} for row in rows),
            "all_child_rss_absent": all(row.get("child_rss_absent") in {True, "True"} for row in rows),
            "all_parent_returns_scalar_only": all(row.get("parent_received_scalar_summary_only") in {True, "True"} for row in rows),
            "baseline_parent_rss_bytes": baseline_parent_rss,
            "maximum_parent_rss_growth_bytes": maximum_parent_growth,
            "serial_execution": True,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
