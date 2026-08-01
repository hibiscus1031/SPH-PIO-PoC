"""Serial, resumable coordinator for the Stage 01D-R2 subprocess campaign."""

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
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_storage_attribution.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
LOGS_ROOT = EXPERIMENT_ROOT / "logs"
WORKER = EXPERIMENT_ROOT / "stage01dr2_worker.py"
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
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _allowed_dirty_path(path: str) -> bool:
    prefixes = (
        "06_experiments/stage_01dr2_storage_attribution/results/",
        "06_experiments/stage_01dr2_storage_attribution/logs/",
        "06_experiments/stage_01dr2_storage_attribution/snapshots/",
        "06_experiments/stage_01dr2_storage_attribution/figures/",
        "07_reports/stage_01dr2_",
    )
    return path.startswith(prefixes)


def _assert_source_clean() -> None:
    output = subprocess.check_output(
        ("git", "status", "--porcelain", "--untracked-files=all"),
        cwd=PROJECT_ROOT,
        text=True,
    )
    unexpected = []
    for line in output.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not _allowed_dirty_path(path):
            unexpected.append(line)
    if unexpected:
        raise RuntimeError("source tree is not clean: " + " | ".join(unexpected))


class CampaignIndex:
    FIELDS = (
        "order",
        "run_id",
        "control",
        "repeat",
        "steps",
        "return_code",
        "worker_status",
        "elapsed_seconds",
        "pid",
        "process_reclaimed",
        "stdout_path",
        "stderr_path",
        "summary_path",
        "git_hash",
        "config_sha256",
    )

    def __init__(self, path: Path, *, resume: bool) -> None:
        self.path = path
        self.existing: dict[str, dict[str, str]] = {}
        if path.exists():
            if not resume:
                raise RuntimeError("campaign index exists; use --resume")
            with path.open(newline="", encoding="utf-8") as stream:
                self.existing = {row["run_id"]: row for row in csv.DictReader(stream)}
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.FIELDS, lineterminator="\n")
                writer.writeheader()

    def append(self, row: Mapping[str, Any]) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.FIELDS, lineterminator="\n")
            writer.writerow(dict(row))
            stream.flush()
        self.existing[str(row["run_id"])] = {key: str(value) for key, value in row.items()}


def _parse_spec(spec: str, configuration: Mapping[str, Any]) -> tuple[str, int, int, str]:
    control = spec[0]
    repeat = int(spec[1:])
    control_config = configuration["controls"][control]
    steps = int(control_config.get("steps", control_config.get("iterations")))
    run_id = f"stage01dr2_{control.lower()}_r{repeat}"
    return control, repeat, steps, run_id


def _run_one(
    *,
    order: int,
    control: str,
    repeat: int,
    steps: int,
    run_id: str,
    git_hash: str,
    config_hash: str,
) -> dict[str, Any]:
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    stdout_path = LOGS_ROOT / f"{run_id}_stdout.log"
    stderr_path = LOGS_ROOT / f"{run_id}_stderr.log"
    if stdout_path.exists() or stderr_path.exists():
        raise RuntimeError(f"refusing to overwrite logs for {run_id}")
    command = (
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
        "--steps",
        str(steps),
    )
    started = time.perf_counter()
    with stdout_path.open("x", encoding="utf-8") as stdout, stderr_path.open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=stdout, stderr=stderr, text=True)
        pid = int(process.pid)
        return_code = int(process.wait())
    elapsed = time.perf_counter() - started
    try:
        os.kill(pid, 0)
        reclaimed = False
    except ProcessLookupError:
        reclaimed = True
    summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
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
        "steps": steps,
        "return_code": return_code,
        "worker_status": summary.get("status", "MISSING"),
        "elapsed_seconds": f"{elapsed:.9f}",
        "pid": pid,
        "process_reclaimed": reclaimed,
        "stdout_path": stdout_path.relative_to(PROJECT_ROOT).as_posix(),
        "stderr_path": stderr_path.relative_to(PROJECT_ROOT).as_posix(),
        "summary_path": summary_path.relative_to(PROJECT_ROOT).as_posix(),
        "git_hash": git_hash,
        "config_sha256": config_hash,
    }


def _inventory_passed() -> bool:
    for repeat in (1, 2, 3):
        path = RESULTS_ROOT / "run_summaries" / f"stage01dr2_a_r{repeat}.json"
        if not path.exists():
            return False
        summary = json.loads(path.read_text(encoding="utf-8"))
        if not (
            summary.get("status") == "PASS"
            and summary.get("inventory_self_retention_pass") is True
            and int(summary.get("lightweight_tensor_count_delta", 1)) == 0
            and int(summary.get("lightweight_unique_storage_bytes_delta", 1)) == 0
        ):
            return False
    return True


def _primary_d_passed() -> bool:
    for repeat in (1, 2, 3):
        path = RESULTS_ROOT / "run_summaries" / f"stage01dr2_d_r{repeat}.json"
        if not path.exists():
            return False
        summary = json.loads(path.read_text(encoding="utf-8"))
        if summary.get("status") != "PASS" or int(summary.get("completed_steps", 0)) != 1000:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if SUMMARY_PATH.exists():
        if args.resume:
            print(SUMMARY_PATH.read_text(encoding="utf-8"), end="")
            return 0
        raise RuntimeError("campaign summary already exists")
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("campaign requires the sph-pio-poc environment")
    _assert_source_clean()
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    git_hash = _git_hash()
    config_hash = _sha256(CONFIG_PATH)
    index = CampaignIndex(INDEX_PATH, resume=args.resume)
    order_specs = list(configuration["primary_run_order"])
    stop_for_bias = False
    next_order = 1
    for next_order, spec in enumerate(order_specs, start=1):
        control, repeat, steps, run_id = _parse_spec(spec, configuration)
        if run_id in index.existing:
            continue
        if control != "A" and not _inventory_passed():
            stop_for_bias = True
            break
        row = _run_one(
            order=next_order,
            control=control,
            repeat=repeat,
            steps=steps,
            run_id=run_id,
            git_hash=git_hash,
            config_hash=config_hash,
        )
        index.append(row)
        print(json.dumps({"completed": run_id, "status": row["worker_status"], "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    confirmation_run = "stage01dr2_d_confirm_2000"
    if not stop_for_bias and _primary_d_passed() and confirmation_run not in index.existing:
        row = _run_one(
            order=len(order_specs) + 1,
            control="D",
            repeat=4,
            steps=int(configuration["controls"]["D"]["confirmation_steps"]),
            run_id=confirmation_run,
            git_hash=git_hash,
            config_hash=config_hash,
        )
        index.append(row)
        print(json.dumps({"completed": confirmation_run, "status": row["worker_status"], "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    rows = list(index.existing.values())
    _write_json(
        SUMMARY_PATH,
        {
            "schema_version": "sph-pio-poc.stage01dr2.campaign.v1",
            "git_hash": git_hash,
            "config_sha256": config_hash,
            "primary_expected": len(order_specs),
            "observed_runs": len(rows),
            "inventory_bias_stop": bool(stop_for_bias),
            "inventory_validation_pass": bool(_inventory_passed()),
            "primary_d_pass": bool(_primary_d_passed()),
            "confirmation_present": confirmation_run in index.existing,
            "all_observed_processes_reclaimed": all(row.get("process_reclaimed") in {True, "True"} for row in rows),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
