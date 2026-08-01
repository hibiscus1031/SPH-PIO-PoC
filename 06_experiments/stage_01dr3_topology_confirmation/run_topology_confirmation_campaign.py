"""Serial coordinator for the Stage 01D-R3 cutoff/F/M campaign."""

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
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_topology_confirmation.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
LOGS_ROOT = EXPERIMENT_ROOT / "logs"
WORKER = EXPERIMENT_ROOT / "stage01dr3_worker.py"
CUTOFF_AUDIT = EXPERIMENT_ROOT / "run_cutoff_shell_audit.py"
INDEX_PATH = RESULTS_ROOT / "campaign_index.csv"
SUMMARY_PATH = RESULTS_ROOT / "campaign_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_source_clean() -> None:
    output = subprocess.check_output(
        ("git", "status", "--porcelain", "--untracked-files=all"),
        cwd=PROJECT_ROOT,
        text=True,
    )
    allowed = (
        "06_experiments/stage_01dr3_topology_confirmation/results/",
        "06_experiments/stage_01dr3_topology_confirmation/logs/",
        "06_experiments/stage_01dr3_topology_confirmation/figures/",
        "07_reports/stage_01dr3_",
    )
    unexpected = [line for line in output.splitlines() if not line[3:].startswith(allowed)]
    if unexpected:
        raise RuntimeError("source tree is not clean: " + " | ".join(unexpected))


def _process_reclaimed(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True


def _run_subprocess(
    *,
    order: int,
    run_id: str,
    control: str,
    repeat: int,
    command: tuple[str, ...],
    git_hash: str,
    config_hash: str,
) -> dict[str, Any]:
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    stdout_path = LOGS_ROOT / f"{run_id}_stdout.log"
    stderr_path = LOGS_ROOT / f"{run_id}_stderr.log"
    if stdout_path.exists() or stderr_path.exists():
        raise RuntimeError(f"refusing to overwrite logs for {run_id}")
    started = time.perf_counter()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=stdout, stderr=stderr, text=True)
        pid = int(process.pid)
        return_code = int(process.wait())
    elapsed = time.perf_counter() - started
    reclaimed = _process_reclaimed(pid)
    if control == "T1":
        status = "PASS" if return_code == 0 else "FAIL"
        summary_path = RESULTS_ROOT / "cutoff_shell_audit_summary.json"
    else:
        summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        status = str(summary.get("status", "MISSING"))
    exit_path = RESULTS_ROOT / "process_exit" / f"{run_id}.json"
    _write_json(
        exit_path,
        {
            "run_id": run_id,
            "pid": pid,
            "return_code": return_code,
            "process_reclaimed": reclaimed,
            "elapsed_seconds": elapsed,
        },
    )
    return {
        "order": order,
        "run_id": run_id,
        "control": control,
        "repeat": repeat,
        "steps": 1000 if control == "T1" else 2000,
        "return_code": return_code,
        "worker_status": status,
        "elapsed_seconds": f"{elapsed:.9f}",
        "pid": pid,
        "process_reclaimed": reclaimed,
        "stdout_path": stdout_path.relative_to(PROJECT_ROOT).as_posix(),
        "stderr_path": stderr_path.relative_to(PROJECT_ROOT).as_posix(),
        "summary_path": summary_path.relative_to(PROJECT_ROOT).as_posix(),
        "git_hash": git_hash,
        "config_sha256": config_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if SUMMARY_PATH.exists():
        if args.resume:
            print(SUMMARY_PATH.read_text(encoding="utf-8"), end="")
            return 0
        raise RuntimeError("campaign already complete")
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("campaign requires sph-pio-poc environment")
    _assert_source_clean()
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    git_hash = _git_hash()
    config_hash = _sha256(CONFIG_PATH)
    existing: dict[str, dict[str, str]] = {}
    fields = (
        "order", "run_id", "control", "repeat", "steps", "return_code",
        "worker_status", "elapsed_seconds", "pid", "process_reclaimed",
        "stdout_path", "stderr_path", "summary_path", "git_hash", "config_sha256",
    )
    if INDEX_PATH.exists():
        if not args.resume:
            raise RuntimeError("campaign index exists; use --resume")
        with INDEX_PATH.open(newline="", encoding="utf-8") as stream:
            existing = {row["run_id"]: row for row in csv.DictReader(stream)}
    else:
        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INDEX_PATH.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()

    def append(row: Mapping[str, Any]) -> None:
        with INDEX_PATH.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writerow(dict(row))
            stream.flush()
        existing[str(row["run_id"])] = {key: str(value) for key, value in row.items()}

    tasks: list[tuple[str, str, int, tuple[str, ...]]] = [
        (
            "stage01dr3_cutoff_replay",
            "T1",
            1,
            (sys.executable, str(CUTOFF_AUDIT)),
        )
    ]
    for spec in configuration["run_order"]:
        control = str(spec)[0]
        repeat = int(str(spec)[1:])
        run_id = f"stage01dr3_{control.lower()}_r{repeat}"
        tasks.append(
            (
                run_id,
                control,
                repeat,
                (
                    sys.executable,
                    str(WORKER),
                    "--config",
                    str(CONFIG_PATH),
                    "--output-root",
                    str(RESULTS_ROOT),
                    "--control",
                    control,
                    "--repeat",
                    str(repeat),
                ),
            )
        )
    for order, (run_id, control, repeat, command) in enumerate(tasks, start=1):
        if run_id in existing:
            continue
        row = _run_subprocess(
            order=order,
            run_id=run_id,
            control=control,
            repeat=repeat,
            command=command,
            git_hash=git_hash,
            config_hash=config_hash,
        )
        append(row)
        print(json.dumps({"completed": run_id, "status": row["worker_status"], "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    rows = list(existing.values())
    _write_json(
        SUMMARY_PATH,
        {
            "schema_version": "sph-pio-poc.stage01dr3.campaign.v1",
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
