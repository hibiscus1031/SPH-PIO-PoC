"""Serial scalar-only coordinator for isolated Stage 01F3C workers."""

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


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"
CONFIG = STAGE / "configs/preregistered_stage01f3c.yml"
REFERENCE_WORKER = STAGE / "stage01f3c_reference_worker.py"
TRAJECTORY_WORKER = STAGE / "stage01f3c_trajectory_worker.py"
INDEX = STAGE / "results/campaign_index.csv"
LOGS = STAGE / "logs"
FIELDS = (
    "role",
    "run_id",
    "pid",
    "return_code",
    "child_reclaimed",
    "child_rss_after_reap_bytes",
    "parent_rss_before_bytes",
    "parent_rss_after_bytes",
    "parent_scalar_only",
    "result_path",
    "log_path",
    "wall_time_seconds",
    "config_sha256",
    "code_git_hash",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_rss(pid: int | None = None) -> int:
    result = subprocess.run(
        ("/bin/ps", "-o", "rss=", "-p", str(os.getpid() if pid is None else pid)),
        capture_output=True,
        text=True,
        check=False,
    )
    return int(result.stdout.strip()) * 1024 if result.stdout.strip() else 0


def scalar_tree(value: Any) -> bool:
    if isinstance(value, dict):
        return all(isinstance(key, str) and scalar_tree(item) for key, item in value.items())
    if isinstance(value, list):
        return all(scalar_tree(item) for item in value)
    return isinstance(value, (str, int, float, bool, type(None)))


def append_index(row: dict[str, Any]) -> None:
    new = not INDEX.exists()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in FIELDS})


def run_child(run_id: str, role: str, command: list[str]) -> bool:
    summary = STAGE / "run_summaries" / f"{run_id}.json"
    if summary.exists():
        return json.loads(summary.read_text())["status"] == "PASS"
    log = LOGS / f"{run_id}.log"
    if log.exists():
        raise RuntimeError(f"refusing to overwrite {log.relative_to(ROOT)}")
    before = current_rss()
    started = time.perf_counter()
    with log.open("x", encoding="utf-8") as stream:
        child = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
        )
        pid = child.pid
        return_code = child.wait()
    child_after = current_rss(pid)
    after = current_rss()
    reclaimed = child_after == 0
    scalar = False
    status = "MISSING"
    if summary.exists():
        payload = json.loads(summary.read_text())
        scalar = scalar_tree(payload)
        status = payload.get("status", "MISSING")
    append_index(
        {
            "role": role,
            "run_id": run_id,
            "pid": pid,
            "return_code": return_code,
            "child_reclaimed": reclaimed,
            "child_rss_after_reap_bytes": child_after,
            "parent_rss_before_bytes": before,
            "parent_rss_after_bytes": after,
            "parent_scalar_only": scalar,
            "result_path": summary.relative_to(ROOT).as_posix() if summary.exists() else "",
            "log_path": log.relative_to(ROOT).as_posix(),
            "wall_time_seconds": time.perf_counter() - started,
            "config_sha256": sha(CONFIG),
            "code_git_hash": subprocess.check_output(
                ("git", "rev-parse", "HEAD"), cwd=ROOT, text=True
            ).strip(),
        }
    )
    return return_code == 0 and reclaimed and scalar and status == "PASS"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def prerequisite(config: dict[str, Any]) -> bool:
    output = STAGE / "results/prerequisite_checks.json"
    if output.exists():
        return json.loads(output.read_text())["status"] == "PASS"
    frozen = config["frozen_stage01f3b"]
    manifest_path = ROOT / frozen["manifest"]
    with manifest_path.open() as stream:
        manifest = list(csv.DictReader(stream))
    identities = {
        row["path"]: sha(ROOT / row["path"]) == row["sha256"] for row in manifest
    }
    evaluator = json.loads((ROOT / frozen["evaluator"]).read_text())
    tag_commit = subprocess.check_output(
        ("git", "rev-list", "-n", "1", frozen["tag"]), cwd=ROOT, text=True
    ).strip()
    checks = {
        "head_is_frozen_evidence_commit": subprocess.check_output(
            ("git", "rev-parse", "HEAD^{}"), cwd=ROOT, text=True
        ).strip()
        != "" and subprocess.run(
            ("git", "merge-base", "--is-ancestor", frozen["evidence_commit"], "HEAD"),
            cwd=ROOT,
            check=False,
        ).returncode
        == 0,
        "historical_status_identity": evaluator["status"] == frozen["status"],
        "tag_identity": tag_commit == frozen["evidence_commit"],
        "manifest_identity": all(identities.values()),
        "continuous_time_only_scope": not config["scope"]["reruns_full_space_matrix"]
        and not config["scope"]["recomputes_stage01f3b_gci"],
        "no_downstream_or_training": not any(
            config["scope"][key]
            for key in (
                "stage01f3d_started",
                "stage01g_started",
                "v3_started",
                "stage02_started",
                "training_started",
                "labels_generated",
            )
        ),
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01f3c.prerequisite.v1",
        "frozen_commit": frozen["evidence_commit"],
        "frozen_status": evaluator["status"],
        "tag_commit": tag_commit,
        "manifest_identities": identities,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    write_json(output, payload)
    return payload["status"] == "PASS"


def reference_task(
    run_id: str, solution: str, block: dict[str, Any]
) -> bool:
    return run_child(
        run_id,
        "semidiscrete_reference",
        [
            sys.executable,
            str(REFERENCE_WORKER),
            "--run-id",
            run_id,
            "--solution",
            solution,
            "--resolution",
            str(block["resolution"]),
            "--support-ratio",
            repr(block["support_ratio"]),
            "--t-final",
            repr(block["t_final"]),
            "--sample-count",
            str(block["sample_count"]),
        ],
    )


def dt_code(value: float) -> str:
    return f"{value:.8f}".split(".")[1].rstrip("0")


def heldout_task(
    run_id: str,
    role: str,
    solution: str,
    block: dict[str, Any],
    dt: float,
) -> bool:
    return run_child(
        run_id,
        role,
        [
            sys.executable,
            str(TRAJECTORY_WORKER),
            "--run-id",
            run_id,
            "--role",
            role,
            "--solution",
            solution,
            "--resolution",
            str(block["resolution"]),
            "--support-ratio",
            repr(block["support_ratio"]),
            "--dt",
            repr(dt),
            "--t-final",
            repr(block["t_final"]),
            "--sample-count",
            str(block["sample_count"]),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=("prerequisite", "reference", "heldout", "all"), required=True
    )
    args = parser.parse_args()
    config = yaml.safe_load(CONFIG.read_text())
    ok = True
    if args.phase in ("prerequisite", "all"):
        ok = prerequisite(config) and ok
    if args.phase in ("reference", "all"):
        for label, block_name in (("n32", "n32"), ("heldout", "heldout")):
            block = config[block_name]
            for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
                ok = reference_task(f"f3c_ref_{label}_{letter}", solution, block) and ok
    if args.phase in ("heldout", "all"):
        block = config["heldout"]
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            for dt in block["dt"]:
                run_id = f"f3c_ho_{letter}_{dt_code(dt)}"
                ok = heldout_task(run_id, "heldout", solution, block, dt) and ok
            repeat_dt = block["deterministic_repeat_dt"]
            repeat_id = f"f3c_ho_repeat_{letter}_{dt_code(repeat_dt)}"
            ok = heldout_task(
                repeat_id, "heldout_deterministic_repeat", solution, block, repeat_dt
            ) and ok
    print(json.dumps({"phase": args.phase, "status": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
