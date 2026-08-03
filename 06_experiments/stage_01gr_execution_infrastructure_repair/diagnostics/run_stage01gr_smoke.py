"""Independent-child coordinator for the one-step Stage 01G-R smoke."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair"
CONFIG = STAGE / "configs/stage01gr_repair.yml"
WORKER = STAGE / "diagnostics/stage01gr_smoke_worker.py"
RESULT = STAGE / "results/stage01gr_minimal_smoke.json"
STDOUT = STAGE / "diagnostics/stage01gr_smoke.stdout.txt"
STDERR = STAGE / "diagnostics/stage01gr_smoke.stderr.txt"


def scalar_tree(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, dict):
        return all(isinstance(key, str) and scalar_tree(item) for key, item in value.items())
    return False


def main() -> int:
    if any(path.exists() for path in (RESULT, STDOUT, STDERR)):
        raise RuntimeError("refusing to overwrite Stage 01G-R smoke process evidence")
    cfg = yaml.safe_load(CONFIG.read_text())
    python = Path(cfg["frozen_inputs"]["python_executable"]).resolve()
    started = time.perf_counter()
    process = subprocess.Popen(
        (str(python), str(WORKER)),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = process.communicate()
    elapsed = time.perf_counter() - started
    STDOUT.write_text(stdout)
    STDERR.write_text(stderr)
    lines = [line for line in stdout.splitlines() if line.strip()]
    child = json.loads(lines[-1]) if lines else {"status": "FAIL", "failure_type": "MissingScalarResult"}
    scalar = scalar_tree(child)
    reclaimed = process.poll() is not None
    worker_result = STAGE / "results/stage01gr_smoke_worker_result.json"
    worker = json.loads(worker_result.read_text()) if worker_result.exists() else {}
    status = "PASS" if (
        process.returncode == 0
        and child.get("status") == "PASS"
        and worker.get("status") == "PASS"
        and scalar
        and reclaimed
    ) else "FAIL"
    payload = {
        "schema_version": "sph-pio-poc.stage01gr.smoke-process.v1",
        "run_id": "g_shear_n24_infra_smoke",
        "status": status,
        "child_pid": process.pid,
        "return_code": process.returncode,
        "child_reclaimed": reclaimed,
        "parent_scalar_only": scalar,
        "solver_entry": worker.get("solver_entry", "FAIL"),
        "diagnostic_initialization": worker.get("diagnostic_initialization", "FAIL"),
        "output_schema": worker.get("output_schema", "FAIL"),
        "type_error": worker.get("type_error", False),
        "key_error": worker.get("key_error", False),
        "attribute_error": worker.get("attribute_error", False),
        "steps": worker.get("steps", 0),
        "formal_benchmark": False,
        "benchmark_metrics_generated": False,
        "evaluator_qualification_performed": False,
        "v2_evidence_generated": False,
        "wall_time_seconds": elapsed,
        "worker_result": worker_result.relative_to(ROOT).as_posix() if worker_result.exists() else "",
        "stdout_path": STDOUT.relative_to(ROOT).as_posix(),
        "stderr_path": STDERR.relative_to(ROOT).as_posix(),
    }
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"run_id": payload["run_id"], "status": status, "steps": payload["steps"]}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
