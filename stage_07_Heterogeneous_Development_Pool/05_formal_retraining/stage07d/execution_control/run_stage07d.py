"""Strict serial Stage07D campaign orchestrator; one fresh OS process per run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve(); D = HERE.parents[1]; S7 = HERE.parents[3]; ROOT = HERE.parents[4]
REPORTS = S7 / "08_reports"; MANIFESTS = S7 / "09_manifests"
PROTOCOL = "sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20700711, 20700712, 20700713)]

def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def incomplete(error: str, completed: list[dict], started: float) -> None:
    state = {"schema": "sph-pio-poc.stage07d.final.v1", "status": "FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE",
        "protocol_sha256": PROTOCOL, "completed_run_ids": [x["run_id"] for x in completed], "error": error,
        "formal_optimizer_steps": sum(x["optimizer_step_count"] for x in completed), "formal_training_runs": len(completed),
        "sealed_test_evaluations": 0, "rollouts": 0, "Stage07E_authorized": False,
        "wall_time_seconds": time.perf_counter() - started}
    write(MANIFESTS / "stage07d_final_manifest.json", state); write(D / "manifests/stage07d_final_manifest.json", state)
    (REPORTS / "stage07d_final_report.md").write_text(
        f"# Stage07D Final Report\n\nProtocol `{PROTOCOL}`. Completed runs: {', '.join(state['completed_run_ids']) or 'none'}. "
        f"Execution stopped without retry: `{error}`. Original sealed-test evaluations and rollouts remain zero. Stage07E is not authorized.\n\n"
        "**FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE**\n", encoding="utf-8")

def main() -> None:
    started = time.perf_counter(); completed = []
    freeze = json.loads((D / "freeze/stage07d_input_freeze_record.json").read_text())
    if not freeze["pass"] or freeze["protocol_sha256"] != PROTOCOL: raise SystemExit("Stage07D freeze is not ready")
    runner = D / "execution_control/run_stage07d_seed.py"
    try:
        for index, run_id in enumerate(RUN_IDS):
            summary_path = D / "runs" / run_id / "run_summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text())
                if not summary["formal_run_terminal"]: raise RuntimeError(f"nonterminal existing summary: {run_id}")
            else:
                process = subprocess.run([sys.executable, str(runner), "--run-id", run_id], cwd=ROOT)
                if process.returncode != 0: raise RuntimeError(f"formal run process failed without retry: {run_id}, exit={process.returncode}")
                summary = json.loads(summary_path.read_text())
            completed.append(summary)
            write(D / "execution_control/campaign_state.json", {"schema": "sph-pio-poc.stage07d.campaign-state.v1",
                "status": "RUNNING" if index < 8 else "RUNS_TERMINAL", "protocol_sha256": PROTOCOL,
                "completed_run_ids": [x["run_id"] for x in completed], "next_run_index": index + 1,
                "formal_optimizer_steps": sum(x["optimizer_step_count"] for x in completed),
                "formal_parameter_updates": sum(x["formal_parameter_update_count"] for x in completed),
                "formal_training_runs": len(completed), "sealed_test_evaluations": 0, "rollouts": 0})
        finalizer = D / "manifests/finalize_stage07d.py"
        process = subprocess.run([sys.executable, str(finalizer)], cwd=ROOT)
        if process.returncode != 0: raise RuntimeError(f"final evidence aggregation failed, exit={process.returncode}")
    except Exception as exc:
        incomplete(f"{type(exc).__name__}: {exc}", completed, started); raise

if __name__ == "__main__": main()
