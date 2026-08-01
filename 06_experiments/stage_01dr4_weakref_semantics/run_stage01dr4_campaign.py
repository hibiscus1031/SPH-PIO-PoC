"""Serial coordinator for the 12 fixtures and three short Control F replays."""

from __future__ import annotations

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
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr4_weakref_semantics"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_weakref_semantics.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
LOGS_ROOT = EXPERIMENT_ROOT / "logs"
FIXTURE_WORKER = EXPERIMENT_ROOT / "stage01dr4_fixture_worker.py"
CONTROL_WORKER = EXPERIMENT_ROOT / "stage01dr4_control_f_worker.py"
INDEX_PATH = RESULTS_ROOT / "campaign_index.csv"
SUMMARY_PATH = RESULTS_ROOT / "campaign_summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        "06_experiments/stage_01dr4_weakref_semantics/results/",
        "06_experiments/stage_01dr4_weakref_semantics/logs/",
        "07_reports/stage_01dr4_",
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


def _run(
    *,
    order: int,
    run_id: str,
    kind: str,
    repeat: int,
    command: tuple[str, ...],
    summary_path: Path,
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
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    exit_path = RESULTS_ROOT / "process_exit" / f"{run_id}.json"
    process_reclaimed = _reclaimed(pid)
    _write_json(
        exit_path,
        {
            "run_id": run_id,
            "pid": pid,
            "return_code": return_code,
            "process_reclaimed": process_reclaimed,
            "elapsed_seconds": elapsed,
        },
    )
    return {
        "order": order,
        "run_id": run_id,
        "kind": kind,
        "repeat": repeat,
        "return_code": return_code,
        "worker_status": summary.get("status", "MISSING"),
        "elapsed_seconds": f"{elapsed:.9f}",
        "pid": pid,
        "process_reclaimed": process_reclaimed,
        "summary_path": summary_path.relative_to(PROJECT_ROOT).as_posix(),
        "stdout_path": stdout_path.relative_to(PROJECT_ROOT).as_posix(),
        "stderr_path": stderr_path.relative_to(PROJECT_ROOT).as_posix(),
        "git_hash": git_hash,
        "config_sha256": config_hash,
    }


def main() -> int:
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("R4 campaign requires sph-pio-poc")
    if SUMMARY_PATH.exists() or INDEX_PATH.exists():
        raise RuntimeError("R4 campaign outputs already exist")
    _assert_source_clean()
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    git_hash = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()
    config_hash = _sha256(CONFIG_PATH)
    tasks: list[tuple[str, str, int, tuple[str, ...], Path]] = []
    for repeat in (1, 2, 3):
        for fixture in configuration["fixtures"]["names"]:
            run_id = f"stage01dr4_fixture_{str(fixture).lower()}_r{repeat}"
            tasks.append(
                (
                    run_id,
                    f"fixture_{fixture}",
                    repeat,
                    (sys.executable, str(FIXTURE_WORKER), "--fixture", str(fixture), "--repeat", str(repeat)),
                    RESULTS_ROOT / "fixture_summaries" / f"{run_id}.json",
                )
            )
    for repeat in (1, 2, 3):
        run_id = f"stage01dr4_f_r{repeat}"
        tasks.append(
            (
                run_id,
                "control_F",
                repeat,
                (sys.executable, str(CONTROL_WORKER), "--repeat", str(repeat)),
                RESULTS_ROOT / "run_summaries" / f"{run_id}.json",
            )
        )
    fields = (
        "order", "run_id", "kind", "repeat", "return_code", "worker_status",
        "elapsed_seconds", "pid", "process_reclaimed", "summary_path",
        "stdout_path", "stderr_path", "git_hash", "config_sha256",
    )
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
    rows: list[dict[str, Any]] = []
    for order, (run_id, kind, repeat, command, summary_path) in enumerate(tasks, start=1):
        row = _run(
            order=order,
            run_id=run_id,
            kind=kind,
            repeat=repeat,
            command=command,
            summary_path=summary_path,
            git_hash=git_hash,
            config_hash=config_hash,
        )
        rows.append(row)
        with INDEX_PATH.open("a", newline="", encoding="utf-8") as stream:
            csv.DictWriter(stream, fieldnames=fields, lineterminator="\n").writerow(row)
        print(json.dumps({"completed": run_id, "status": row["worker_status"]}), flush=True)
    _write_json(
        SUMMARY_PATH,
        {
            "schema_version": "sph-pio-poc.stage01dr4.campaign.v1",
            "git_hash": git_hash,
            "config_sha256": config_hash,
            "expected_processes": len(tasks),
            "observed_processes": len(rows),
            "pass_processes": sum(row["worker_status"] == "PASS" for row in rows),
            "all_processes_reclaimed": all(row["process_reclaimed"] for row in rows),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
