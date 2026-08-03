"""Single-step, non-qualification infrastructure smoke for Stage 01G-R."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any

import torch
import yaml


ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair"
CONFIG = STAGE / "configs/stage01gr_repair.yml"
OUTPUT = STAGE / "results/stage01gr_smoke_worker_result.json"
FAILURE = STAGE / "results/stage01gr_smoke_worker_failure.txt"
sys.path.insert(0, str(ROOT / "01_solver"))

from dynamic_solver.acceleration import DynamicPhysicalParameters, force_structure_audit  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.state import DynamicSPHState  # noqa: E402
from structure_preserving.neighborhood import periodic_cartesian_layout, wrap_periodic  # noqa: E402


RUN_ID = "g_shear_n24_infra_smoke"
EXPECTED_STEP_FIELDS = {"state", "start_evaluation", "midpoint_evaluation", "end_evaluation"}


def write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def initial_state(cfg: dict[str, Any]) -> tuple[DynamicSPHState, float]:
    smoke = cfg["smoke"]
    bindings = cfg["explicit_runner_bindings"]
    positions, dx, _ = periodic_cartesian_layout(
        int(smoke["N"]),
        jitter_fraction=float(bindings["layout_jitter_fraction"]),
        seed=int(bindings["layout_seed"]),
        dtype=torch.float64,
        domain_minimum=tuple(float(value) for value in bindings["domain_minimum"]),
        domain_maximum=tuple(float(value) for value in bindings["domain_maximum"]),
    )
    count = int(smoke["N"]) ** 2
    velocities = torch.stack(
        (float(smoke["U_s"]) * torch.sin(2.0 * math.pi * positions[:, 1]), torch.zeros(count, dtype=torch.float64)),
        dim=-1,
    )
    return DynamicSPHState(
        positions=positions,
        velocities=velocities,
        masses=torch.full((count,), dx**2, dtype=torch.float64),
        densities=torch.ones(count, dtype=torch.float64),
        pressures=torch.zeros(count, dtype=torch.float64),
        supports=torch.full((count,), float(smoke["H_over_dx"]) * dx, dtype=torch.float64),
        domain_min=torch.tensor(bindings["domain_minimum"], dtype=torch.float64),
        domain_max=torch.tensor(bindings["domain_maximum"], dtype=torch.float64),
        time=0.0,
    ), dx


def diagnostic_midpoint_state(
    state: DynamicSPHState, result: Any, dt: float
) -> DynamicSPHState:
    """Reconstruct diagnostic-only midpoint state; never feed it to the solver."""
    positions = wrap_periodic(
        state.positions + 0.5 * dt * state.velocities,
        state.domain_min,
        state.domain_max,
    )
    velocities = state.velocities + 0.5 * dt * result.start_evaluation.acceleration
    return state.with_updates(
        positions=positions,
        velocities=velocities,
        densities=result.midpoint_evaluation.densities,
        pressures=result.midpoint_evaluation.pressures,
        time=state.time + 0.5 * dt,
    )


def main() -> int:
    if OUTPUT.exists() or FAILURE.exists():
        raise RuntimeError("refusing to overwrite Stage 01G-R smoke evidence")
    started = time.perf_counter()
    status = "FAIL"
    failure_type = ""
    failure_message = ""
    try:
        cfg = yaml.safe_load(CONFIG.read_text())
        smoke = cfg["smoke"]
        if RUN_ID != cfg["stage"]["smoke_run_id"] or int(smoke["steps"]) > 1:
            raise RuntimeError("smoke identity or step ceiling drift")
        if not gc.isenabled():
            raise RuntimeError("default cyclic GC must be enabled")
        if Path(sys.executable).resolve() != Path(cfg["frozen_inputs"]["python_executable"]).resolve():
            raise RuntimeError("smoke worker is not using the frozen environment")
        with torch.no_grad():
            state, dx = initial_state(cfg)
            parameters = DynamicPhysicalParameters(
                reference_density=float(smoke["rho0"]),
                sound_speed=float(smoke["c_s"]),
                physical_viscosity=float(smoke["nu"]),
            )
            state, evaluation = prepare_dynamic_state(state, parameters)
            result = explicit_midpoint_dynamic_step(
                state,
                dt=float(smoke["dt"]),
                parameters=parameters,
                start_evaluation=evaluation,
            )
            result_fields = set(result.__dataclass_fields__)
            midpoint = diagnostic_midpoint_state(state, result, float(smoke["dt"]))
            audit = force_structure_audit(midpoint, result.midpoint_evaluation, parameters)
            required_diagnostics = {
                "pressure_relative_pair_force_residual",
                "viscosity_relative_pair_force_residual",
                "characteristic_normalized_total_internal_force",
                "viscous_power",
                "neighbor_duplicate_edge_count",
                "neighbor_nonreciprocal_nonself_edge_count",
            }
            nonself = result.midpoint_evaluation.neighborhood.nonself
            minimum_separation = float(result.midpoint_evaluation.neighborhood.distance[nonself].min()) / dx
            checks = {
                "run_id_exact": RUN_ID == "g_shear_n24_infra_smoke",
                "steps_at_most_one": int(smoke["steps"]) == 1,
                "solver_entry_completed": result.state.time == float(smoke["dt"]),
                "dynamic_step_schema": result_fields == EXPECTED_STEP_FIELDS,
                "diagnostic_midpoint_reconstructed": midpoint.time == 0.5 * float(smoke["dt"]),
                "diagnostic_schema": required_diagnostics.issubset(audit),
                "state_cpu_float64": result.state.positions.device.type == "cpu" and result.state.positions.dtype == torch.float64,
                "default_gc": gc.isenabled(),
                "torch_no_grad": not torch.is_grad_enabled(),
                "state_finite": all(bool(torch.isfinite(value).all()) for value in (result.state.positions, result.state.velocities, result.end_evaluation.densities, result.end_evaluation.pressures)),
                "minimum_separation_positive": minimum_separation > 0.0,
                "benchmark_metrics_absent": smoke["benchmark_metrics"] is False,
                "evaluator_qualification_absent": smoke["evaluator_qualification"] is False,
                "v2_evidence_absent": smoke["v2_evidence"] is False,
            }
        status = "PASS" if all(checks.values()) else "FAIL"
        payload = {
            "schema_version": "sph-pio-poc.stage01gr.smoke.v1",
            "run_id": RUN_ID,
            "status": status,
            "pid": os.getpid(),
            "steps": 1,
            "solver_entry": "PASS" if checks["solver_entry_completed"] else "FAIL",
            "diagnostic_initialization": "PASS" if checks["diagnostic_schema"] else "FAIL",
            "output_schema": "PASS",
            "type_error": False,
            "key_error": False,
            "attribute_error": False,
            "benchmark_metrics_generated": False,
            "evaluator_qualification_performed": False,
            "v2_evidence_generated": False,
            "device": "cpu",
            "dtype": "float64",
            "default_gc": True,
            "torch_no_grad": True,
            "minimum_separation_over_dx": minimum_separation,
            "diagnostic_key_count": len(audit),
            "wall_time_seconds": time.perf_counter() - started,
            "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
            "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip(),
        }
        write_json(OUTPUT, payload)
    except Exception as error:
        failure_type = type(error).__name__
        failure_message = str(error).replace(str(Path.home()), "<HOME>")
        FAILURE.write_text("".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"))
        if not OUTPUT.exists():
            write_json(OUTPUT, {
                "schema_version": "sph-pio-poc.stage01gr.smoke.v1",
                "run_id": RUN_ID,
                "status": "FAIL",
                "failure_type": failure_type,
                "failure_message": failure_message,
                "type_error": isinstance(error, TypeError),
                "key_error": isinstance(error, KeyError),
                "attribute_error": isinstance(error, AttributeError),
                "wall_time_seconds": time.perf_counter() - started,
            })
        status = "FAIL"
    print(json.dumps({"run_id": RUN_ID, "status": status, "failure_type": failure_type, "failure_message": failure_message}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
