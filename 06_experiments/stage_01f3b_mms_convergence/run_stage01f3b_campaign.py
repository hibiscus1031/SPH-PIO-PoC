"""Serial scalar-only coordinator for isolated Stage 01F3B workers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np
import torch
import yaml


ROOT = Path(__file__).resolve().parents[2]
SOLVER = ROOT / "01_solver"
sys.path.insert(0, str(SOLVER))
STAGE = ROOT / "06_experiments/stage_01f3b_mms_convergence"
CONFIG = STAGE / "configs/preregistered_stage01f3b.yml"
WORKER = STAGE / "stage01f3b_worker.py"
INDEX = STAGE / "results/campaign_index.csv"
LOGS = STAGE / "logs"
FIELDS = (
    "role", "run_id", "pid", "return_code", "child_reclaimed",
    "child_rss_after_reap_bytes", "parent_rss_before_bytes", "parent_rss_after_bytes",
    "parent_scalar_only", "result_path", "log_path", "wall_time_seconds",
    "config_sha256", "code_git_hash",
)

from dynamic_solver.acceleration import DynamicPhysicalParameters, evaluate_internal_acceleration
from dynamic_solver.sourced_acceleration import initialize_mms_state
from dynamic_solver.state import DynamicSPHState
from manufactured_solutions.dense_all_pairs_rhs import evaluate_dense_all_pairs
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_rss(pid: int | None = None) -> int:
    result = subprocess.run(
        ("/bin/ps", "-o", "rss=", "-p", str(os.getpid() if pid is None else pid)),
        capture_output=True, text=True,
    )
    return int(result.stdout.strip()) * 1024 if result.stdout.strip() else 0


def append_index(row: dict[str, Any]) -> None:
    new = not INDEX.exists()
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in FIELDS})


def scalar_tree(value: Any) -> bool:
    if isinstance(value, dict):
        return all(isinstance(key, str) and scalar_tree(item) for key, item in value.items())
    return isinstance(value, (str, int, float, bool, type(None)))


def run_child(run_id: str, role: str, command: list[str]) -> bool:
    result = STAGE / "run_summaries" / f"{run_id}.json"
    if result.exists():
        return json.loads(result.read_text())["status"] == "PASS"
    log = LOGS / f"{run_id}.log"
    if log.exists():
        raise RuntimeError(f"refusing to overwrite {log}")
    LOGS.mkdir(parents=True, exist_ok=True)
    before = current_rss(); started = time.perf_counter()
    with log.open("x", encoding="utf-8") as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True)
        pid = child.pid
        code = child.wait()
    child_after = current_rss(pid); after = current_rss()
    reclaimed = child_after == 0
    scalar = False
    status = "MISSING"
    if result.exists():
        payload = json.loads(result.read_text())
        scalar = scalar_tree(payload)
        status = payload.get("status", "MISSING")
    append_index({
        "role": role, "run_id": run_id, "pid": pid, "return_code": code,
        "child_reclaimed": reclaimed, "child_rss_after_reap_bytes": child_after,
        "parent_rss_before_bytes": before, "parent_rss_after_bytes": after,
        "parent_scalar_only": scalar,
        "result_path": result.relative_to(ROOT).as_posix() if result.exists() else "",
        "log_path": log.relative_to(ROOT).as_posix(),
        "wall_time_seconds": time.perf_counter() - started,
        "config_sha256": sha(CONFIG),
        "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip(),
    })
    return code == 0 and reclaimed and scalar and status == "PASS"


def dt_code(value: float) -> str:
    return f"{value:.8f}".split(".")[1].rstrip("0")


def task(run_id: str, role: str, solution: str, resolution: int, ratio: float, dt: float, t_final: float, samples: int) -> bool:
    command = [
        sys.executable, str(WORKER), "--run-id", run_id, "--role", role,
        "--solution", solution, "--resolution", str(resolution),
        "--support-ratio", repr(ratio), "--dt", repr(dt),
        "--t-final", repr(t_final), "--sample-count", str(samples),
    ]
    return run_child(run_id, role, command)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def frozen_identity(config: dict[str, Any]) -> dict[str, Any]:
    manifest = STAGE / "configs/stage01f3r_frozen_sha256_manifest.csv"
    with manifest.open() as stream:
        rows = list(csv.DictReader(stream))
    identities = {row["path"]: sha(ROOT / row["path"]) == row["sha256"] for row in rows}
    evaluator = json.loads((ROOT / config["frozen_stage01f3r"]["evaluator"]).read_text())
    historical = json.loads((ROOT / config["historical_stage01f3"]["evaluator"]).read_text())
    tag = subprocess.check_output(("git", "rev-list", "-n", "1", config["frozen_stage01f3r"]["tag"]), cwd=ROOT, text=True).strip()
    source = json.loads((ROOT / config["frozen_sources"]["source_evaluator"]).read_text())
    disabled = json.loads((ROOT / config["frozen_sources"]["source_disabled_evidence"]).read_text())
    return {
        "manifest_identity": identities,
        "manifest_identity_pass": all(identities.values()),
        "stage01f3r_evaluator_status": evaluator["status"],
        "stage01f3r_evaluator_pass": evaluator["status"] == config["frozen_stage01f3r"]["status"],
        "tag_target": tag, "tag_pass": tag == config["frozen_stage01f3r"]["evidence_commit"],
        "stage01f3_historical_status": historical["status"],
        "stage01f3_historical_pass": historical["status"] == config["historical_stage01f3"]["status"],
        "stage01f_source_status": source["status"], "stage01f_source_pass": source["status"] == "MMS_SPECIFICATION_PASS",
        "stage01f2_source_disabled_status": disabled["status"], "stage01f2_source_disabled_pass": disabled["status"] == "PASS",
        "dense_reference_qualification_pass": all(json.loads((ROOT / f"06_experiments/stage_01f3r_reference_qualification/results/mms_{letter}_reference_qualification.json").read_text())["status"] == "PASS" for letter in ("a", "b")),
    }


def sparse_dense_spotcheck() -> dict[str, Any]:
    cases = []
    ratio = (4.0 + 17.0 ** 0.5) / 2.0
    for solution in ("MMS_A", "MMS_B"):
        initial = initialize_mms_state(solution, 16, support_ratio=ratio)
        cases.append((solution, initial.positions, initial.velocities, initial.masses, initial.supports, 0.0))
    initial = initialize_mms_state("MMS_B", 16, support_ratio=ratio)
    old = np.load(ROOT / "06_experiments/stage_01f3_mms_convergence/references/semidiscrete_mms_b_n16_dop853.npz")
    count = initial.particle_count; value = old["baseline"][5]
    cases.append(("MMS_B", torch.from_numpy(value[:2 * count].reshape(count, 2).copy()), torch.from_numpy(value[2 * count:].reshape(count, 2).copy()), initial.masses, initial.supports, float(old["times"][5])))
    maxima = {"density_relative": 0.0, "pressure_relative": 0.0, "acceleration_relative": 0.0, "acceleration_absolute": 0.0}
    finite = True
    for solution, positions, velocities, masses, supports, physical_time in cases:
        wrapped = torch.remainder(positions + 1.0, 2.0) - 1.0
        state = DynamicSPHState(
            positions=wrapped, velocities=velocities, masses=masses,
            densities=torch.ones_like(masses), pressures=torch.zeros_like(masses), supports=supports,
            domain_min=torch.full((2,), -1.0, dtype=torch.float64), domain_max=torch.full((2,), 1.0, dtype=torch.float64), time=physical_time,
        )
        sparse = evaluate_internal_acceleration(state, DynamicPhysicalParameters())
        dense = evaluate_dense_all_pairs(solution, wrapped, velocities, masses, supports, physical_time)
        source = evaluate_mms_source(solution, wrapped, physical_time)
        def metrics(left: torch.Tensor, right: torch.Tensor) -> tuple[float, float]:
            absolute = float((left - right).abs().max()); relative = absolute / max(float(right.abs().max()), torch.finfo(torch.float64).tiny)
            return absolute, relative
        _, density_relative = metrics(sparse.densities, dense.density)
        _, pressure_relative = metrics(sparse.pressures, dense.pressure)
        acceleration_absolute, acceleration_relative = metrics(sparse.acceleration + source, dense.total_acceleration)
        maxima["density_relative"] = max(maxima["density_relative"], density_relative)
        maxima["pressure_relative"] = max(maxima["pressure_relative"], pressure_relative)
        maxima["acceleration_relative"] = max(maxima["acceleration_relative"], acceleration_relative)
        maxima["acceleration_absolute"] = max(maxima["acceleration_absolute"], acceleration_absolute)
        finite = finite and all(bool(torch.isfinite(item).all()) for item in (sparse.densities, sparse.pressures, sparse.acceleration, dense.total_acceleration))
    checks = {"finite": finite, "density": maxima["density_relative"] <= 1e-13, "pressure": maxima["pressure_relative"] <= 1e-13, "acceleration_relative": maxima["acceleration_relative"] <= 1e-11, "acceleration_absolute": maxima["acceleration_absolute"] <= 1e-12}
    return {"case_count": len(cases), "maxima": maxima, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def support_path(config: dict[str, Any]) -> None:
    path = STAGE / "results/support_path_preregistration.csv"
    if path.exists():
        return
    rows = []
    paths = (("increasing_neighbor", config["space"]["increasing_neighbor_path"]), ("fixed_ratio", {value: config["space"]["fixed_ratio"] for value in (16, 24, 32, 48)}))
    for path_name, mapping in paths:
        for resolution, ratio in mapping.items():
            resolution = int(resolution); ratio = float(ratio)
            state = initialize_mms_state("MMS_A", resolution, support_ratio=ratio)
            evaluation = evaluate_internal_acceleration(state, DynamicPhysicalParameters())
            dx = 2.0 / resolution; support = ratio * dx
            position = state.positions.numpy(); delta = position[:, None, :] - position[None, :, :]; delta = np.remainder(delta + 1.0, 2.0) - 1.0
            distances = np.linalg.norm(delta, axis=-1); unique = np.unique(np.round(distances[distances > 0], 15)); below = unique[unique < support]; above = unique[unique > support]
            lower = float(below.max()) if len(below) else 0.0; upper = float(above.min()) if len(above) else math.inf
            rows.append({"path": path_name, "resolution": resolution, "dx": dx, "support": support, "support_ratio": ratio, "initial_edge_count": evaluation.neighborhood.row.numel(), "nearest_lower_shell": lower, "nearest_upper_shell": upper, "cutoff_margin": min(support - lower, upper - support), "config_sha256": sha(CONFIG)})
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


def prerequisite(config: dict[str, Any]) -> bool:
    result_path = STAGE / "results/prerequisite_checks.json"
    if result_path.exists():
        return json.loads(result_path.read_text())["status"] == "PASS"
    LOGS.mkdir(parents=True, exist_ok=True)
    pytest_log = LOGS / "full_pytest.log"
    if pytest_log.exists():
        raise RuntimeError("refusing to overwrite full pytest log")
    with pytest_log.open("x", encoding="utf-8") as stream:
        pytest_result = subprocess.run((sys.executable, "-m", "pytest", "-q"), cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, text=True)
    identity = frozen_identity(config)
    spot = sparse_dense_spotcheck()
    static_checks = {
        "full_pytest": pytest_result.returncode == 0,
        "stage01f3r_manifest": identity["manifest_identity_pass"],
        "stage01f3r_evaluator": identity["stage01f3r_evaluator_pass"],
        "stage01f3r_tag": identity["tag_pass"],
        "stage01f3_historical_fail": identity["stage01f3_historical_pass"],
        "stage01f2_source_disabled": identity["stage01f2_source_disabled_pass"],
        "stage01f_source": identity["stage01f_source_pass"],
        "dense_reference_identity": identity["dense_reference_qualification_pass"],
        "sparse_dense_three_states": spot["status"] == "PASS",
    }
    if not all(static_checks.values()):
        write_json(result_path, {"identity": identity, "sparse_dense_spotcheck": spot, "checks": static_checks, "status": "FAIL"})
        return False
    ratio = config["semidiscrete_time"]["support_ratio"]
    smoke = all(task(f"f3b_prereq_smoke_{letter}", "prerequisite_smoke", solution, 16, ratio, 2.5e-4, 0.0025, 6) for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")))
    with INDEX.open() as stream:
        index_rows = [row for row in csv.DictReader(stream) if row["role"] == "prerequisite_smoke"]
    process_checks = {
        "smoke_10_steps": smoke,
        "child_reclaimed": len(index_rows) == 2 and all(row["child_reclaimed"] == "True" for row in index_rows),
        "parent_scalar_only": len(index_rows) == 2 and all(row["parent_scalar_only"] == "True" for row in index_rows),
    }
    support_path(config)
    write_json(result_path, {"identity": identity, "sparse_dense_spotcheck": spot, "checks": {**static_checks, **process_checks}, "status": "PASS" if all((*static_checks.values(), *process_checks.values())) else "FAIL"})
    return all((*static_checks.values(), *process_checks.values()))


def select_space_dt(config: dict[str, Any]) -> bool:
    output = STAGE / "results/space_dt_selection.json"
    if output.exists():
        return json.loads(output.read_text())["status"] == "PASS"
    comparisons = {}; use_fine = False
    for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
        coarse = json.loads((STAGE / "run_summaries" / f"f3b_isolate_{letter}_0000625.json").read_text())["final_metrics"]
        fine = json.loads((STAGE / "run_summaries" / f"f3b_isolate_{letter}_00003125.json").read_text())["final_metrics"]
        fields = ("labeled_position_l2", "labeled_velocity_l2", "labeled_density_l2", "labeled_pressure_l2")
        values = {field: abs(coarse[field] - fine[field]) / max(abs(fine[field]), 1e-30) for field in fields}
        comparisons[solution] = values
        use_fine = use_fine or max(values.values()) > config["space"]["isolation_relative_threshold"]
    selected = 3.125e-5 if use_fine else 6.25e-5
    write_json(output, {"schema_version": "sph-pio-poc.stage01f3b.space-dt-selection.v1", "comparisons": comparisons, "threshold": config["space"]["isolation_relative_threshold"], "selected_dt": selected, "status": "PASS"})
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("prerequisite", "semitime", "conttime", "isolation", "space", "fixed", "determinism", "n64"))
    args = parser.parse_args(); config = yaml.safe_load(CONFIG.read_text()); ok = True
    if args.phase == "prerequisite":
        ok = prerequisite(config)
    elif args.phase == "semitime":
        block = config["semidiscrete_time"]
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            for dt in block["dt"]:
                ok = task(f"f3b_sd_{letter}_{dt_code(dt)}", "semidiscrete_time", solution, block["resolution"], block["support_ratio"], dt, block["t_final"], block["sample_count"]) and ok
                if not ok: break
    elif args.phase == "conttime":
        block = config["continuous_time"]
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            for dt in block["dt"]:
                ok = task(f"f3b_ct_{letter}_{dt_code(dt)}", "continuous_time", solution, block["resolution"], block["support_ratio"], dt, block["t_final"], block["sample_count"]) and ok
                if not ok: break
    elif args.phase == "isolation":
        ratio = float(config["space"]["increasing_neighbor_path"][32])
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            for dt in config["space"]["candidate_dt"]:
                ok = task(f"f3b_isolate_{letter}_{dt_code(dt)}", "space_dt_isolation", solution, 32, ratio, dt, config["space"]["t_final"], config["space"]["sample_count"]) and ok
                if not ok: break
        if ok: ok = select_space_dt(config)
    elif args.phase in ("space", "fixed"):
        selected = json.loads((STAGE / "results/space_dt_selection.json").read_text())["selected_dt"]
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            for resolution in config["space"]["formal_resolutions"]:
                ratio = float(config["space"]["increasing_neighbor_path"][resolution]) if args.phase == "space" else float(config["space"]["fixed_ratio"])
                role = "space_consistency" if args.phase == "space" else "fixed_ratio_diagnostic"
                ok = task(f"f3b_{args.phase}_{letter}_n{resolution}", role, solution, resolution, ratio, selected, config["space"]["t_final"], config["space"]["sample_count"]) and ok
                if not ok: break
    elif args.phase == "determinism":
        selected = json.loads((STAGE / "results/space_dt_selection.json").read_text())["selected_dt"]
        finest = min(config["continuous_time"]["dt"])
        for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
            ok = task(f"f3b_repeat_ct_{letter}_{dt_code(finest)}", "determinism_repeat", solution, 32, config["continuous_time"]["support_ratio"], finest, 0.02, 21) and ok
            ok = task(f"f3b_repeat_space_{letter}_n32", "determinism_repeat", solution, 32, float(config["space"]["increasing_neighbor_path"][32]), selected, 0.02, 21) and ok
    elif args.phase == "n64":
        decision = json.loads((STAGE / "results/n64_decision.json").read_text())
        if decision["required"]:
            selected = json.loads((STAGE / "results/space_dt_selection.json").read_text())["selected_dt"]
            ratio = float(config["space"]["increasing_neighbor_path"][64])
            smoke_ok = True
            for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
                smoke_ok = task(f"f3b_n64_smoke_{letter}", "n64_smoke", solution, 64, ratio, selected, 20 * selected, 2) and smoke_ok
            with (STAGE / "results/support_path_preregistration.csv").open() as stream:
                support_rows = list(csv.DictReader(stream))
            margin = min(float(row["cutoff_margin"]) for row in support_rows if row["path"] == "increasing_neighbor" and int(row["resolution"]) == 64)
            smoke_summaries = [json.loads((STAGE / "run_summaries" / f"f3b_n64_smoke_{letter}.json").read_text()) for letter in ("a", "b")]
            estimated = max(item["wall_time_seconds"] for item in smoke_summaries) * round(0.02 / selected) / 20
            gate = config["space"]["conditional_n64"]
            preflight = smoke_ok and max(item["peak_rss_bytes"] for item in smoke_summaries) < gate["peak_rss_bytes"] and estimated < gate["estimated_wall_seconds"] and margin > gate["cutoff_margin"] and all(item["maximum_topology_structural_defects"] == 0 for item in smoke_summaries)
            write_json(STAGE / "results/n64_preflight.json", {"smoke_pass": smoke_ok, "peak_rss_bytes": max(item["peak_rss_bytes"] for item in smoke_summaries), "estimated_wall_seconds": estimated, "cutoff_margin": margin, "structural_defects": max(item["maximum_topology_structural_defects"] for item in smoke_summaries), "status": "PASS" if preflight else "FAIL"})
            if preflight:
                for letter, solution in (("a", "MMS_A"), ("b", "MMS_B")):
                    ok = task(f"f3b_space_{letter}_n64", "conditional_n64", solution, 64, ratio, selected, 0.02, 21) and ok
            else: ok = False
    print(json.dumps({"phase": args.phase, "status": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
