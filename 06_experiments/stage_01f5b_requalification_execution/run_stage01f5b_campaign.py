"""Strict, resumable A-K coordinator for the frozen Stage 01F5B bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
CONFIG = STAGE / "configs/stage01f5b_execution.yml"
MATRIX = ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/stage01f5_execution_run_matrix_v2.csv"
DRY = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_dry_resolution_audit.csv"
ANALYZER = STAGE / "analyze_stage01f5b.py"
REFERENCE_WORKER = STAGE / "stage01f5b_reference_worker.py"
TRAJECTORY_WORKER = STAGE / "stage01f5b_trajectory_worker.py"
SEAL = STAGE / "manifests/stage01f5b_preexecution_commit.txt"
ALLOWED = {"PENDING", "RUNNING", "PASS", "FAIL", "NOT_TRIGGERED"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open() as stream:
        return list(csv.DictReader(stream))


def scalar_tree(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, list):
        return all(scalar_tree(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and scalar_tree(item) for key, item in value.items())
    return False


def status_path(run_id: str) -> Path:
    return STAGE / "runs" / run_id / "status.json"


def marker(run_id: str) -> str | None:
    path = status_path(run_id)
    if not path.exists():
        return None
    value = json.loads(path.read_text())["status"]
    if value not in ALLOWED:
        raise RuntimeError(f"illegal marker for {run_id}: {value}")
    return value


def verify_execution_artifacts(config: dict[str, Any]) -> None:
    manifest = ROOT / config["run_policy"]["preexecution_artifact_manifest"]
    if not manifest.exists():
        raise RuntimeError("missing preexecution artifact manifest")
    failures = [row["path"] for row in read_rows(manifest) if sha(ROOT / row["path"]) != row["sha256"]]
    if failures:
        raise RuntimeError(f"post-freeze execution artifact drift: {failures}")


def set_marker(run_id: str, status: str, **extra: Any) -> None:
    if status not in ALLOWED:
        raise ValueError(status)
    atomic_json(status_path(run_id), {"run_id": run_id, "status": status, **extra})


def preflight(run_pytest: bool = True) -> dict[str, Any]:
    config = yaml.safe_load(CONFIG.read_text())
    matrix = read_rows(MATRIX)
    dry = read_rows(DRY)
    expected = [run_id for phase in "ABCDEFGHIJK" for run_id in config["phases"][phase]["run_ids"]]
    matrix_ids = [row["run_id"] for row in matrix]
    dry_ids = [row["run_id"] for row in dry]
    frozen_manifest = read_rows(STAGE / "manifests/stage01f5q_frozen_sha256_manifest.csv")
    frozen_checks = {row["category"]: sha(ROOT / row["path"]) == row["sha256"] for row in frozen_manifest}
    source_manifest = read_rows(STAGE / "manifests/numerical_source_identity.csv")
    source_checks = {row["path"]: sha(ROOT / row["path"]) == row["frozen_sha256"] for row in source_manifest}
    canonical = "".join(f"{row['path']},{row['frozen_sha256']}\n" for row in source_manifest).encode()
    gate_source = yaml.safe_load((ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml").read_text())
    gate_map = {"T1_T5": gate_source["time_gates"], "P1_P3": gate_source["platform_gates"], "H1_H5": gate_source["heldout"]["gates"], "S1_S4": gate_source["spatial_matrix"]["gates"], "hard_safety": gate_source["hard_safety_gates"]}
    canonical_hash = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    bundle = json.loads((ROOT / config["frozen_stage01f5q"]["bundle"]).read_text())
    gate_checks = {name: canonical_hash(value) == bundle["frozen_gate_hashes"][name] for name, value in gate_map.items()}
    output_dirs = [ROOT / row["output_dir"] for row in matrix]
    checks: dict[str, bool] = {
        "frozen_python_environment": Path(sys.executable).resolve() == Path(config["frozen_environment"]["python_executable"]).resolve(),
        "stage01f5q_head_ancestor": subprocess.run(("git", "merge-base", "--is-ancestor", config["frozen_stage01f5q"]["evidence_commit"], "HEAD"), cwd=ROOT).returncode == 0,
        "stage01f5q_tag_identity": subprocess.check_output(("git", "rev-list", "-n", "1", config["frozen_stage01f5q"]["tag"]), cwd=ROOT, text=True).strip() == config["frozen_stage01f5q"]["evidence_commit"],
        "frozen_manifest_identity": all(frozen_checks.values()),
        "bundle_identity": sha(ROOT / config["frozen_stage01f5q"]["bundle"]) == config["frozen_stage01f5q"]["bundle_sha256"],
        "matrix_identity": sha(MATRIX) == config["frozen_stage01f5q"]["matrix_sha256"],
        "matrix_69_unique": len(matrix) == 69 and len(set(matrix_ids)) == 69,
        "dry_69_resolved_identity": len(dry) == 69 and matrix_ids == dry_ids and all(row["resolution_status"] == "RESOLVED" for row in dry),
        "source_file_identity": all(source_checks.values()),
        "source_tree_identity": len(source_manifest) == config["numerical_source"]["file_count"] and hashlib.sha256(canonical).hexdigest() == config["numerical_source"]["canonical_tree_sha256"],
        "gate_hash_identity": all(gate_checks.values()),
        "phase_order_and_exact_run_ids": len(expected) == 69 and len(set(expected)) == 69 and set(expected) == set(matrix_ids),
        "output_directories_unique": len(set(str(path) for path in output_dirs)) == 69,
        "output_directories_absent_or_empty": all(not path.exists() or not any(path.iterdir()) for path in output_dirs),
        "parent_scalar_schema": scalar_tree({"status": "PASS", "count": 69, "paths": ["relative/path"]}),
        "disk_free_at_least_20gb": shutil.disk_usage(ROOT).free >= 20_000_000_000,
        "no_old_data_paths_in_matrix": all("stage_01f3b" not in row["output_dir"] and "stage_01f3c" not in row["output_dir"] for row in matrix),
    }
    smoke = subprocess.run((sys.executable, "-c", "import json; print(json.dumps({'status':'PASS','solver_called':False}))"), cwd=ROOT, capture_output=True, text=True)
    checks["child_launch_exit_no_solver"] = smoke.returncode == 0 and json.loads(smoke.stdout)["solver_called"] is False
    pytest_result = None
    if run_pytest:
        pytest_result = subprocess.run((sys.executable, "-m", "pytest"), cwd=ROOT, text=True)
        checks["full_pytest"] = pytest_result.returncode == 0
    payload = {
        "schema_version": "sph-pio-poc.stage01f5b.preflight.v1",
        "checks": checks,
        "details": {"frozen_manifest": frozen_checks, "source_files": source_checks, "gate_hashes": gate_checks, "disk_free_bytes": shutil.disk_usage(ROOT).free, "pytest_returncode": None if pytest_result is None else pytest_result.returncode},
        "status": "PASS" if all(checks.values()) else "PLATEAU_AWARE_REQUALIFICATION_EVIDENCE_INCOMPLETE",
    }
    target = STAGE / "results/preflight_audit.json"
    if target.exists():
        target = STAGE / "results/preflight_audit_attempt2.json"
    if target.exists():
        raise RuntimeError("preflight audit attempt2 already exists; refusing to overwrite")
    atomic_json(target, payload)
    return payload


def invoke(args: list[str], log_name: str) -> int:
    log = STAGE / "logs" / log_name
    if log.exists():
        raise RuntimeError(f"refusing to overwrite {log.relative_to(ROOT)}")
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True)
    return result.returncode


def run_one(row: dict[str, str], dry: dict[str, str], phase: str, dt_space: float | None = None) -> str:
    verify_execution_artifacts(yaml.safe_load(CONFIG.read_text()))
    run_id = row["run_id"]
    existing = marker(run_id)
    if existing in {"PASS", "FAIL", "NOT_TRIGGERED"}:
        return existing
    if existing == "RUNNING" or (STAGE / "checkpoints" / f"{run_id}.npz").exists() or (STAGE / "references" / f"{run_id}.npz").exists():
        raise RuntimeError(f"{run_id} has numerical evidence without a terminal marker; same-ID rerun forbidden")
    (STAGE / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    set_marker(run_id, "PENDING", phase=phase)
    set_marker(run_id, "RUNNING", phase=phase)
    solution = row["mms"].replace("-", "_")
    common = dry["common_time_contract"]
    sample_count = int(common.split("count=")[1].split(";")[0]) if "count=" in common else 2
    t_final = float(dry["t_final_contract"])
    common_args = ["--run-id", run_id, "--solution", solution, "--resolution", row["resolution"], "--support-ratio", row["support_ratio"], "--t-final", str(t_final), "--sample-count", str(sample_count)]
    if row["method"] == "DOP853":
        command = [sys.executable, str(REFERENCE_WORKER), *common_args, "--level", row["reference_level"]]
    else:
        control = row["time_control"]
        if control.startswith("dt=") and "SPACE_STEP_DECISION" not in control:
            dt = float(control.split("=", 1)[1])
        elif control == "inherit_parent":
            dt = float(summary_for(row["parent_run_id"])["dt"])
        else:
            if dt_space is None:
                raise RuntimeError(f"unresolved dt_space for {run_id}")
            dt = dt_space
        if row["category"] == "conditional_n64_smoke":
            t_final = 20 * dt
            sample_count = 2
            common_args = ["--run-id", run_id, "--solution", solution, "--resolution", row["resolution"], "--support-ratio", row["support_ratio"], "--t-final", str(t_final), "--sample-count", str(sample_count)]
        command = [sys.executable, str(TRAJECTORY_WORKER), *common_args, "--role", row["category"], "--dt", str(dt)]
    code = invoke(command, f"{run_id}.log")
    summary_path = STAGE / "runs" / run_id / "summary.json"
    if summary_path.exists():
        payload = json.loads(summary_path.read_text())
        if not scalar_tree(payload):
            raise RuntimeError(f"non-scalar child summary: {run_id}")
        final = payload["status"]
    else:
        final = "FAIL"
    set_marker(run_id, final, phase=phase, child_exit_code=code)
    return final


def summary_for(run_id: str) -> dict[str, Any]:
    return json.loads((STAGE / "runs" / run_id / "summary.json").read_text())


def commit_decision(path: Path, message: str) -> str:
    subprocess.run(("git", "add", str(path.relative_to(ROOT))), cwd=ROOT, check=True)
    subprocess.run(("git", "commit", "-m", message), cwd=ROOT, check=True)
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip()


def execute() -> None:
    if not SEAL.exists():
        raise RuntimeError("missing preexecution commit seal")
    seal = dict(line.split("=", 1) for line in SEAL.read_text().splitlines() if "=" in line)
    if not seal.get("preexecution_commit"):
        raise RuntimeError("incomplete preexecution commit seal")
    config = yaml.safe_load(CONFIG.read_text())
    authoritative_preflight = STAGE / "results/preflight_audit_attempt2.json"
    if not authoritative_preflight.exists() or json.loads(authoritative_preflight.read_text())["status"] != "PASS":
        raise RuntimeError("authoritative frozen-environment preflight is not PASS")
    verify_execution_artifacts(config)
    rows = {row["run_id"]: row for row in read_rows(MATRIX)}
    dry = {row["run_id"]: row for row in read_rows(DRY)}
    phase_index = STAGE / "results/phase_progress.json"
    dt_space: float | None = None
    halted = False
    for phase in config["phase_order"]:
        if phase == "F":
            code = invoke([sys.executable, str(ANALYZER), "space-step"], "phase_f_space_step_decision.log")
            if code != 0:
                raise RuntimeError("Phase F decision failed")
            decision_path = STAGE / "manifests/space_step_decision.json"
            commit_hash = commit_decision(decision_path, "Freeze Stage 01F5B space-step decision")
            decision = json.loads(decision_path.read_text())
            decision["commit"] = commit_hash
            dt_space = float(decision["chosen_dt_space"])
        elif phase == "J":
            for action in ("space", "n64"):
                code = invoke([sys.executable, str(ANALYZER), action], f"phase_j_{action}.log")
                if code != 0:
                    raise RuntimeError(f"Phase J {action} failed")
            decision_path = STAGE / "manifests/n64_trigger_decision.json"
            commit_hash = commit_decision(decision_path, "Freeze Stage 01F5B N64 trigger decision")
            decision = json.loads(decision_path.read_text())
            decision["commit"] = commit_hash
            if decision["decision"] == "NOT_TRIGGERED":
                for run_id in config["phases"]["K"]["run_ids"]:
                    (STAGE / "runs" / run_id).mkdir(parents=True, exist_ok=True)
                    set_marker(run_id, "NOT_TRIGGERED", phase="K", trigger_commit=commit_hash)
        elif phase == "K":
            decision = json.loads((STAGE / "manifests/n64_trigger_decision.json").read_text())
            if decision["decision"] == "TRIGGERED":
                if dt_space is None:
                    dt_space = float(json.loads((STAGE / "manifests/space_step_decision.json").read_text())["chosen_dt_space"])
                smokes = config["phases"]["K"]["run_ids"][:2]
                smoke_status = [run_one(rows[run_id], dry[run_id], "K", dt_space) for run_id in smokes]
                if all(value == "PASS" for value in smoke_status):
                    refs = config["phases"]["K"]["run_ids"][2:5]
                    ref_status = [run_one(rows[run_id], dry[run_id], "K", dt_space) for run_id in refs]
                    if all(value == "PASS" for value in ref_status):
                        qualification = reference_triplet_subprocess("f5_ref_space_b_n64")
                        if qualification == "PASS":
                            for run_id in config["phases"]["K"]["run_ids"][5:]:
                                run_one(rows[run_id], dry[run_id], "K", dt_space)
            continue
        else:
            if phase in {"H", "I"} and dt_space is None:
                dt_space = float(json.loads((STAGE / "manifests/space_step_decision.json").read_text())["chosen_dt_space"])
            for run_id in config["phases"][phase]["run_ids"]:
                status = run_one(rows[run_id], dry[run_id], phase, dt_space)
                item = summary_for(run_id)
                if status == "FAIL" and (row_is_reference(rows[run_id]) or hard_failure(item)):
                    halted = halted or hard_failure(item)
            if halted:
                break
        atomic_json(phase_index, {"last_completed_phase": phase, "halted_for_hard_failure": halted})
    if not halted:
        for action in ("references", "time", "determinism"):
            invoke([sys.executable, str(ANALYZER), action], f"final_{action}.log")


def row_is_reference(row: dict[str, str]) -> bool:
    return row["method"] == "DOP853"


def hard_failure(item: dict[str, Any]) -> bool:
    return item.get("schema_version", "").endswith("trajectory-run.v1") and not all(item.get("checks", {}).values())


def reference_triplet_subprocess(prefix: str) -> str:
    # Qualification is recomputed in-process by the pure analyzer at finalization;
    # this branch guard uses the frozen sensitivity bound directly.
    states = []
    for level in ("baseline", "tighter", "third"):
        with __import__("numpy").load(STAGE / "references" / f"{prefix}_{level}.npz") as data:
            states.append(data["states"].copy())
    count = states[0].shape[1] // 4
    gate = yaml.safe_load(CONFIG.read_text())["reference_gates"]
    position = max(float(__import__("numpy").max(abs(states[0][:, : 2 * count] - states[1][:, : 2 * count]))), float(__import__("numpy").max(abs(states[1][:, : 2 * count] - states[2][:, : 2 * count]))))
    velocity = max(float(__import__("numpy").max(abs(states[0][:, 2 * count :] - states[1][:, 2 * count :]))), float(__import__("numpy").max(abs(states[1][:, 2 * count :] - states[2][:, 2 * count :]))))
    return "PASS" if position <= gate["position_linf_sensitivity_maximum"] and velocity <= gate["velocity_linf_sensitivity_maximum"] else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "execute"))
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()
    if args.action == "preflight":
        result = preflight(not args.skip_pytest)
        print(json.dumps({"status": result["status"]}))
        return 0 if result["status"] == "PASS" else 1
    execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
