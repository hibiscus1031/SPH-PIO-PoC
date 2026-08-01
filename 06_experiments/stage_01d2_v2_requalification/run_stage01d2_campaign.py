"""Serial parent coordinator; children return scalar summaries and paths only."""

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

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01d2_v2_requalification"
CONFIG = ROOT / "configs" / "preregistered_stage01d2_v2.yml"
WORKER = ROOT / "stage01d2_worker.py"
AD_WORKER = ROOT / "stage01d2_ad_worker.py"
INDEX = ROOT / "results" / "campaign_index.csv"
PREREQ = ROOT / "results" / "prerequisite_summary.json"
LOGS = ROOT / "logs"

INDEX_COLUMNS = (
    "kind", "case_id", "phase", "pid", "return_code", "child_reclaimed",
    "child_rss_after_reap_bytes", "parent_rss_before_bytes", "parent_rss_after_bytes",
    "parent_rss_growth_from_campaign_start_bytes", "scalar_only_protocol", "result_path",
    "log_path", "config_sha256", "code_git_hash", "wall_time_seconds",
)


def rss(pid: int | None = None) -> int:
    target = os.getpid() if pid is None else pid
    result = subprocess.run(("/bin/ps", "-o", "rss=", "-p", str(target)), text=True, capture_output=True, check=False)
    return int(result.stdout.strip()) * 1024 if result.stdout.strip() else 0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_index(row: dict[str, Any]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    new = not INDEX.exists()
    with INDEX.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_COLUMNS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in INDEX_COLUMNS})


def run_child(*, kind: str, case_id: str, phase: str, command: list[str], result_path: Path, baseline_rss: int) -> bool:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{case_id}.log"
    if log.exists():
        raise RuntimeError(f"refusing to overwrite {log.relative_to(PROJECT_ROOT)}")
    before = rss()
    started = time.perf_counter()
    with log.open("x", encoding="utf-8") as stream:
        child = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True)
        pid = child.pid
        code = child.wait()
    after = rss()
    child_after = rss(pid)
    reclaimed = child_after == 0
    append_index({
        "kind": kind, "case_id": case_id, "phase": phase, "pid": pid,
        "return_code": code, "child_reclaimed": reclaimed,
        "child_rss_after_reap_bytes": child_after, "parent_rss_before_bytes": before,
        "parent_rss_after_bytes": after, "parent_rss_growth_from_campaign_start_bytes": after - baseline_rss,
        "scalar_only_protocol": True,
        "result_path": result_path.relative_to(PROJECT_ROOT).as_posix() if result_path.exists() else "",
        "log_path": log.relative_to(PROJECT_ROOT).as_posix(), "config_sha256": sha(CONFIG),
        "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip(),
        "wall_time_seconds": time.perf_counter() - started,
    })
    return code == 0 and reclaimed and result_path.exists()


def verify_identity(cfg: dict[str, Any]) -> dict[str, bool]:
    checks = {name: sha(PROJECT_ROOT / item["path"]) == item["sha256"] for name, item in cfg["frozen_identity"].items()}
    checks["stage01dp_manifest_rows_hash_match"] = all(
        sha(PROJECT_ROOT / row["path"]) == row["sha256"]
        for row in csv.DictReader((ROOT / "configs" / "stage01dp_frozen_sha256_manifest.csv").open(encoding="utf-8"))
    )
    checks["stage01dp_tag_target"] = subprocess.check_output(("git", "rev-list", "-n", "1", cfg["frozen_stage01dp"]["tag"]), cwd=PROJECT_ROOT, text=True).strip() == cfg["frozen_stage01dp"]["required_tag_target"]
    checks["r5_tag_target"] = subprocess.check_output(("git", "rev-list", "-n", "1", "stage-01dr5-bounded-gc-delay-confirmed"), cwd=PROJECT_ROOT, text=True).strip() == cfg["frozen_stage01dp"]["r5_tag_target"]
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("prerequisite", "main", "n48_smoke", "n48_full", "extended", "ad"))
    args = parser.parse_args()
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    baseline = rss()
    ok = True
    if args.phase == "prerequisite":
        if PREREQ.exists():
            raise SystemExit("refusing to overwrite prerequisite evidence")
        pytest_log = LOGS / "full_pytest.log"
        LOGS.mkdir(parents=True, exist_ok=True)
        if pytest_log.exists():
            raise SystemExit("refusing to overwrite pytest log")
        started = time.perf_counter()
        with pytest_log.open("x", encoding="utf-8") as stream:
            test = subprocess.run((sys.executable, "-m", "pytest", "-q"), cwd=PROJECT_ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True, check=False)
        identities = verify_identity(cfg)
        ok = test.returncode == 0 and all(identities.values())
        if ok:
            for run_id in cfg["prerequisites"]["trajectory_run_ids"]:
                ok = run_child(kind="trajectory", case_id=run_id, phase=args.phase, command=[sys.executable, str(WORKER), "--run-id", run_id], result_path=ROOT / "run_summaries" / f"{run_id}.json", baseline_rss=baseline) and ok
                if not ok:
                    break
        payload = {"schema_version": "sph-pio-poc.stage01d2.prerequisite.v1", "pytest_return_code": test.returncode, "pytest_wall_time_seconds": time.perf_counter() - started, "pytest_log_path": pytest_log.relative_to(PROJECT_ROOT).as_posix(), "identity_checks": identities, "trajectory_ids": cfg["prerequisites"]["trajectory_run_ids"], "status": "PASS" if ok else "FAIL", "config_sha256": sha(CONFIG)}
        PREREQ.parent.mkdir(parents=True, exist_ok=True)
        with PREREQ.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True); stream.write("\n")
    elif args.phase == "ad":
        for parameter in cfg["autograd_regression"]["parameters"]:
            for steps in cfg["autograd_regression"]["steps"]:
                case_id = f"{parameter}_steps{steps}"
                result_path = ROOT / "results" / "ad_cases" / f"{case_id}.json"
                if result_path.exists():
                    ok = json.loads(result_path.read_text(encoding="utf-8"))["status"] == "PASS" and ok
                    continue
                ok = run_child(kind="ad", case_id=case_id, phase="ad", command=[sys.executable, str(AD_WORKER), "--parameter", parameter, "--steps", str(steps)], result_path=result_path, baseline_rss=baseline) and ok
    else:
        for task in cfg["trajectory_matrix"]:
            if task["phase"] == args.phase:
                run_id = task["run_id"]
                result_path = ROOT / "run_summaries" / f"{run_id}.json"
                if result_path.exists():
                    ok = json.loads(result_path.read_text(encoding="utf-8"))["status"] == "PASS" and ok
                    continue
                case_ok = run_child(kind="trajectory", case_id=run_id, phase=args.phase, command=[sys.executable, str(WORKER), "--run-id", run_id], result_path=result_path, baseline_rss=baseline)
                ok = case_ok and ok
                if not case_ok and args.phase not in ("extended",):
                    break
    print(json.dumps({"phase": args.phase, "status": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
