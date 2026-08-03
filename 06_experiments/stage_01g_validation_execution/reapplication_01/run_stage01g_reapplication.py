"""Sequential independent-child coordinator for Stage 01G reapplication_01."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stage01g_reapplication_contract import (  # noqa: E402
    ACOUSTIC_IDS, ATTEMPT_ID, FROZEN_PYTHON, PREFLIGHT_RESULT, ROOT,
    SHEAR_IDS, STAGE, attempt_run_dir, frozen_python_guard, log_paths,
    preflight_code_guard, read_json, write_json_new,
)

WORKER = HERE / "stage01g_reapplication_worker.py"
INDEX = STAGE / "manifests/stage01g_campaign_index_reapplication_01.csv"
PHASE_RESULTS = {
    "A": STAGE / "results/stage01g_phase_a_execution_reapplication_01.json",
    "B": STAGE / "results/stage01g_phase_b_execution_reapplication_01.json",
}
PHASES = {"A": SHEAR_IDS, "B": ACOUSTIC_IDS}
INDEX_FIELDS = (
    "phase", "ordinal", "run_id", "attempt_id", "pid", "return_code",
    "status", "child_reclaimed", "parent_scalar_only", "stdout_log",
    "stderr_log", "wall_time_seconds",
)


def scalar_tree(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, dict):
        return all(isinstance(key, str) and scalar_tree(item) for key, item in value.items())
    return False


def append_index(row: dict[str, Any]) -> None:
    exists = INDEX.exists()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_FIELDS, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("A", "B"), required=True)
    args = parser.parse_args()
    phase = args.phase
    frozen_python_guard()
    preflight_code_guard()
    if PHASE_RESULTS[phase].exists():
        raise RuntimeError(f"refusing to overwrite Phase {phase} execution evidence")
    preflight = read_json(PREFLIGHT_RESULT)
    if preflight["overall_status"] != "PASS":
        raise RuntimeError("benchmark prohibited because final preflight did not pass")
    if phase == "A" and INDEX.exists():
        raise RuntimeError("Phase A campaign index already exists")
    if phase == "B":
        phase_a = read_json(PHASE_RESULTS["A"]) if PHASE_RESULTS["A"].exists() else {}
        if phase_a.get("status") != "COMPLETE" or tuple(phase_a.get("executed_run_ids", ())) != SHEAR_IDS:
            raise RuntimeError("Phase B cannot start before complete ordered Phase A evidence")

    rows: list[dict[str, Any]] = []
    phase_failure = False
    for ordinal, run_id in enumerate(PHASES[phase], start=1):
        run_dir = attempt_run_dir(run_id)
        stdout_path, stderr_path = log_paths(run_id)
        if run_dir.exists() or stdout_path.exists() or stderr_path.exists():
            raise RuntimeError(f"refusing to overwrite output for {run_id}")
        run_dir.mkdir(parents=True)
        write_json_new(run_dir / "status_running.json", {
            "phase": phase, "run_id": run_id, "attempt_id": ATTEMPT_ID,
            "status": "RUNNING", "parent_pid": os.getpid(),
        })
        started = time.perf_counter()
        print(json.dumps({"phase": phase, "ordinal": ordinal, "run_id": run_id, "event": "LAUNCH"}), flush=True)
        process = subprocess.Popen(
            (str(FROZEN_PYTHON), str(WORKER), "--run-id", run_id),
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        last_heartbeat = started
        while process.poll() is None:
            time.sleep(5.0)
            now = time.perf_counter()
            if now - last_heartbeat >= 55.0:
                print(json.dumps({"phase": phase, "run_id": run_id, "event": "RUNNING", "elapsed_seconds": round(now - started, 1)}), flush=True)
                last_heartbeat = now
        stdout, stderr = process.communicate()
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        lines = [line for line in stdout.splitlines() if line.strip()]
        try:
            child = json.loads(lines[-1]) if lines else {}
        except json.JSONDecodeError:
            child = {}
        scalar = scalar_tree(child) and bool(child)
        reclaimed = process.poll() is not None
        complete = process.returncode == 0 and child.get("status") == "EVIDENCE_COMPLETE" and child.get("run_id") == run_id and scalar and reclaimed
        status = "EVIDENCE_COMPLETE" if complete else "INFRASTRUCTURE_FAILURE"
        wall = time.perf_counter() - started
        marker = {
            "phase": phase, "ordinal": ordinal, "run_id": run_id,
            "attempt_id": ATTEMPT_ID, "pid": process.pid,
            "return_code": process.returncode, "status": status,
            "child_reclaimed": reclaimed, "parent_scalar_only": scalar,
            "wall_time_seconds": wall,
        }
        write_json_new(run_dir / "status_final.json", marker)
        append_index({
            **marker,
            "stdout_log": stdout_path.relative_to(ROOT).as_posix(),
            "stderr_log": stderr_path.relative_to(ROOT).as_posix(),
        })
        rows.append(marker)
        print(json.dumps({"phase": phase, "run_id": run_id, "event": "COMPLETE", "status": status, "wall_time_seconds": round(wall, 3)}), flush=True)
        if not complete:
            phase_failure = True
            break

    phase_status = "COMPLETE" if not phase_failure and len(rows) == len(PHASES[phase]) else "EVIDENCE_INCOMPLETE"
    payload = {
        "schema_version": "sph-pio-poc.stage01g.phase-execution.v1",
        "phase": phase, "attempt_id": ATTEMPT_ID,
        "expected_run_ids": list(PHASES[phase]),
        "executed_run_ids": [row["run_id"] for row in rows],
        "run_statuses": {row["run_id"]: row["status"] for row in rows},
        "all_children_reclaimed": bool(rows) and all(row["child_reclaimed"] for row in rows),
        "all_parent_aggregation_scalar_only": bool(rows) and all(row["parent_scalar_only"] for row in rows),
        "status": phase_status,
    }
    write_json_new(PHASE_RESULTS[phase], payload)
    print(json.dumps({"phase": phase, "status": phase_status, "run_count": len(rows)}), flush=True)
    return 0 if phase_status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
