"""Serial parent coordinator for isolated Stage 01F2 workers."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
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
STAGE = ROOT / "06_experiments" / "stage_01f2_mms_implementation"
CONFIG = STAGE / "configs" / "preregistered_stage01f2.yml"
WORKER = STAGE / "stage01f2_worker.py"
INDEX = STAGE / "results" / "campaign_index.csv"
LOGS = STAGE / "logs"
SOLVER = ROOT / "01_solver"
if str(SOLVER) not in sys.path:
    sys.path.insert(0, str(SOLVER))

from manufactured_solutions.governing_equations import PARAMETERS  # noqa: E402
from manufactured_solutions.particle_initialization import regular_initialization  # noqa: E402


INDEX_FIELDS = (
    "kind", "case_id", "pid", "return_code", "child_reclaimed",
    "child_rss_after_reap_bytes", "parent_rss_before_bytes", "parent_rss_after_bytes",
    "scalar_only_summary", "result_path", "log_path", "config_sha256",
    "code_git_hash", "wall_time_seconds",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rss(pid: int | None = None) -> int:
    target = os.getpid() if pid is None else pid
    result = subprocess.run(
        ("/bin/ps", "-o", "rss=", "-p", str(target)), text=True,
        capture_output=True, check=False,
    )
    return int(result.stdout.strip()) * 1024 if result.stdout.strip() else 0


def append_index(row: dict[str, Any]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    new = not INDEX.exists()
    with INDEX.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_FIELDS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in INDEX_FIELDS})


def run_child(kind: str, case_id: str, command: list[str], result_path: Path) -> bool:
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))["status"] == "PASS"
    log = LOGS / f"{case_id}.log"
    if log.exists():
        raise RuntimeError(f"refusing to overwrite {log.relative_to(ROOT)}")
    LOGS.mkdir(parents=True, exist_ok=True)
    before = rss()
    started = time.perf_counter()
    with log.open("x", encoding="utf-8") as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True)
        pid = child.pid
        code = child.wait()
    after = rss()
    child_after = rss(pid)
    reclaimed = child_after == 0
    scalar_only = False
    if result_path.exists():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        scalar_only = all(not isinstance(value, (list, tuple)) for value in payload.values())
    append_index({
        "kind": kind, "case_id": case_id, "pid": pid, "return_code": code,
        "child_reclaimed": reclaimed, "child_rss_after_reap_bytes": child_after,
        "parent_rss_before_bytes": before, "parent_rss_after_bytes": after,
        "scalar_only_summary": scalar_only,
        "result_path": result_path.relative_to(ROOT).as_posix() if result_path.exists() else "",
        "log_path": log.relative_to(ROOT).as_posix(), "config_sha256": sha(CONFIG),
        "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip(),
        "wall_time_seconds": time.perf_counter() - started,
    })
    return code == 0 and reclaimed and scalar_only and result_path.exists()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def freeze_and_mass_audit(cfg: dict[str, Any]) -> bool:
    manifest = STAGE / "configs" / "stage01f_frozen_sha256_manifest.csv"
    identity = {
        row["path"]: sha(ROOT / row["path"]) == row["sha256"]
        for row in csv.DictReader(manifest.open(encoding="utf-8"))
    }
    tag_target = subprocess.check_output(
        ("git", "rev-list", "-n", "1", cfg["frozen_stage01f"]["tag"]),
        cwd=ROOT, text=True,
    ).strip()
    evaluation = json.loads((ROOT / "06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json").read_text())
    frozen = cfg["physics"]
    parameter_checks = {
        "rho0": PARAMETERS.rho0 == frozen["rho0"],
        "sound_speed": PARAMETERS.sound_speed == frozen["sound_speed"],
        "viscosity": PARAMETERS.viscosity == frozen["viscosity"],
        "wave_number": PARAMETERS.wave_number == frozen["wave_number"],
        "density_amplitude": PARAMETERS.density_amplitude == frozen["density_amplitude"],
        "translation_speed": PARAMETERS.translation_speed == frozen["translation_speed"],
        "decay_rate": PARAMETERS.decay_rate == frozen["decay_rate"],
        "vortex_amplitude": PARAMETERS.vortex_amplitude == frozen["vortex_amplitude"],
    }
    freeze_payload = {
        "schema_version": "sph-pio-poc.stage01f2.freeze.v1",
        "manifest_checks": identity, "parameter_checks": parameter_checks,
        "tag_target": tag_target,
        "tag_target_pass": tag_target == cfg["frozen_stage01f"]["evidence_commit"],
        "stage01f_status": evaluation["status"],
        "stage01f_status_pass": evaluation["status"] == "MMS_SPECIFICATION_PASS",
    }
    freeze_payload["status"] = "PASS" if all(identity.values()) and all(parameter_checks.values()) and freeze_payload["tag_target_pass"] and freeze_payload["stage01f_status_pass"] else "FAIL"
    write_json(STAGE / "results" / "stage01f_freeze_audit.json", freeze_payload)
    mass_rows = []
    for solution in ("MMS_A", "MMS_B"):
        for resolution in (16, 32):
            initialized = regular_initialization(solution, resolution)
            mass_rows.append({
                "solution_id": solution, "resolution": resolution,
                "total_mass": float(initialized.mass.sum()),
                "total_mass_exact_four": float(initialized.mass.sum()) == 4.0,
                "masses_fixed_during_rollout": initialized.masses_fixed_during_rollout,
                "analytic_density_overwrites_numerical_density": initialized.analytic_density_overwrites_numerical_density,
            })
    mass_payload = {
        "schema_version": "sph-pio-poc.stage01f2.mass-initialization.v1",
        "cases": mass_rows,
        "stage01f_particle_initialization_sha256": sha(ROOT / "06_experiments/stage_01f_mms_design/results/particle_initialization_audit.csv"),
        "status": "PASS" if all(row["total_mass_exact_four"] and row["masses_fixed_during_rollout"] and not row["analytic_density_overwrites_numerical_density"] for row in mass_rows) else "FAIL",
    }
    write_json(STAGE / "results" / "mass_initialization_summary.json", mass_payload)
    return freeze_payload["status"] == "PASS" and mass_payload["status"] == "PASS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("freeze", "zero", "reference", "mms", "ad", "all"), required=True)
    args = parser.parse_args()
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    ok = True
    phases = ("freeze", "zero", "reference", "mms", "ad") if args.phase == "all" else (args.phase,)
    for phase in phases:
        if phase == "freeze":
            freeze_path = STAGE / "results" / "stage01f_freeze_audit.json"
            if freeze_path.exists():
                ok = json.loads(freeze_path.read_text())["status"] == "PASS" and ok
            else:
                ok = freeze_and_mass_audit(cfg) and ok
        elif phase == "zero":
            for task in cfg["zero_source_regression"]:
                result = STAGE / "results" / f"zero_source_{task['run_id']}.json"
                ok = run_child("zero", task["run_id"], [sys.executable, str(WORKER), "--kind", "zero", "--run-id", task["run_id"]], result) and ok
                if not ok:
                    break
        elif phase == "reference":
            for resolution in (16, 32):
                result = STAGE / "results" / f"mms_b_n{resolution}_reference_summary.json"
                ok = run_child("reference", f"mms_b_n{resolution}_reference", [sys.executable, str(WORKER), "--kind", "reference", "--resolution", str(resolution)], result) and ok
                if not ok:
                    break
        elif phase == "mms":
            for task in cfg["mms_runs"]:
                result = STAGE / "run_summaries" / f"{task['run_id']}.json"
                ok = run_child("mms", task["run_id"], [sys.executable, str(WORKER), "--kind", "mms", "--run-id", task["run_id"]], result) and ok
                if not ok:
                    break
        elif phase == "ad":
            result = STAGE / "results" / "source_ad_fd_v2_summary.json"
            ok = run_child("ad", "source_ad_fd", [sys.executable, str(WORKER), "--kind", "ad"], result) and ok
        if not ok:
            break
    print(json.dumps({"phase": args.phase, "status": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
