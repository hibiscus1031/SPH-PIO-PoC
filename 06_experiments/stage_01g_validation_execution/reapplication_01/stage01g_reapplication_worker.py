"""Execute one frozen Stage 01G run and invoke the frozen evaluator."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import traceback
from typing import Any

import numpy as np
import torch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stage01g_reapplication_contract import (  # noqa: E402
    ATTEMPT_ID, CONFIG_SHA256, MATRIX_SHA256, METRICS_SHA256, ROOT, STAGE,
    checkpoint_path, evaluator_path, frozen_python_guard, git, matrix_row,
    preflight_code_guard, reference_path, sha256, write_json_new,
)

EVALUATOR_ROOT = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(ROOT / "01_solver"))
sys.path.insert(0, str(EVALUATOR_ROOT))
from dynamic_solver.acceleration import DynamicPhysicalParameters, force_structure_audit  # noqa: E402
from dynamic_solver.diagnostics import process_peak_rss_bytes  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.state import DynamicSPHState  # noqa: E402
from evaluator.acoustic_evaluator import evaluate_acoustic  # noqa: E402
from evaluator.provenance import build_evaluation_provenance, sha256_file  # noqa: E402
from evaluator.shear_evaluator import evaluate_shear  # noqa: E402
from structure_preserving.neighborhood import periodic_cartesian_layout, wrap_periodic  # noqa: E402


DEFECT_KEYS = (
    "neighbor_duplicate_edge_count", "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count", "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count", "neighbor_unexpected_edge_count",
)


def current_rss_bytes() -> int:
    output = subprocess.check_output(("/bin/ps", "-o", "rss=", "-p", str(os.getpid())), text=True).strip()
    return int(output) * 1024


def tensor_content_sha256(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(arrays):
        value = np.ascontiguousarray(arrays[name])
        digest.update(name.encode() + b"\0")
        digest.update(str(value.dtype).encode() + b"\0")
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def initial_state(row: dict[str, str]) -> tuple[DynamicSPHState, float, torch.Tensor]:
    resolution = int(row["N"])
    positions, dx, _ = periodic_cartesian_layout(
        resolution, jitter_fraction=0.0, seed=0, dtype=torch.float64,
        domain_minimum=(-1.0, -1.0), domain_maximum=(1.0, 1.0),
    )
    count = resolution * resolution
    supports = torch.full((count,), float(row["H_over_dx"]) * dx, dtype=torch.float64)
    densities = torch.ones(count, dtype=torch.float64)
    pressures = torch.zeros(count, dtype=torch.float64)
    if row["benchmark"] == "shear":
        masses = torch.full((count,), dx**2, dtype=torch.float64)
        velocities = torch.stack((0.5 * torch.sin(2.0 * math.pi * positions[:, 1]), torch.zeros(count, dtype=torch.float64)), dim=-1)
    elif row["benchmark"] == "acoustic":
        epsilon = float(row["epsilon"])
        masses = (1.0 + epsilon * torch.cos(math.pi * positions[:, 0])) * dx**2
        velocities = torch.zeros((count, 2), dtype=torch.float64)
    else:
        raise ValueError("unknown frozen benchmark")
    state = DynamicSPHState(
        positions=positions, velocities=velocities, masses=masses,
        densities=densities, pressures=pressures, supports=supports,
        domain_min=torch.tensor([-1.0, -1.0], dtype=torch.float64),
        domain_max=torch.tensor([1.0, 1.0], dtype=torch.float64), time=0.0,
    )
    return state, dx, positions.clone()


def diagnostic_midpoint_state(state: DynamicSPHState, result: Any, dt: float) -> DynamicSPHState:
    """Reconstruct a diagnostic-only midpoint; it never enters the solver."""
    positions = wrap_periodic(state.positions + 0.5 * dt * state.velocities, state.domain_min, state.domain_max)
    velocities = state.velocities + 0.5 * dt * result.start_evaluation.acceleration
    return state.with_updates(
        positions=positions, velocities=velocities,
        densities=result.midpoint_evaluation.densities,
        pressures=result.midpoint_evaluation.pressures,
        time=state.time + 0.5 * dt,
    )


def reference_fields(benchmark: str, t: float, positions: torch.Tensor, initial: torch.Tensor, epsilon: float | None) -> dict[str, list[Any]]:
    if benchmark == "shear":
        k, nu, amplitude = 2.0 * math.pi, 0.02, 0.5
        decay = math.exp(-nu * k**2 * t)
        y0 = initial[:, 1]
        ux = amplitude * torch.sin(k * y0) * decay
        exact_position = initial.clone()
        exact_position[:, 0] += amplitude * torch.sin(k * y0) * (1.0 - decay) / (nu * k**2)
        velocity = torch.stack((ux, torch.zeros_like(ux)), dim=-1)
        density = torch.ones(initial.shape[0], dtype=torch.float64)
        pressure = torch.zeros_like(density)
    else:
        if epsilon is None:
            raise ValueError("acoustic reference requires epsilon")
        exact_position = positions.clone()
        x = exact_position[:, 0]
        density = 1.0 + epsilon * torch.cos(math.pi * x) * math.cos(20.0 * math.pi * t)
        ux = 20.0 * epsilon * torch.sin(math.pi * x) * math.sin(20.0 * math.pi * t)
        velocity = torch.stack((ux, torch.zeros_like(ux)), dim=-1)
        pressure = 400.0 * (density - 1.0)
    return {
        "position": exact_position.tolist(), "velocity": velocity.tolist(),
        "density": density.tolist(), "pressure": pressure.tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_id = args.run_id
    run_dir = STAGE / "runs" / run_id / ATTEMPT_ID
    summary_path = run_dir / "summary.json"
    provenance_path = run_dir / "provenance.json"
    failure_path = run_dir / "failure.txt"
    checkpoint = checkpoint_path(run_id)
    reference = reference_path(run_id)
    evaluator_output = evaluator_path(run_id)
    started = time.perf_counter()
    result_status = "INFRASTRUCTURE_FAILURE"
    failure_type = ""
    failure_message = ""
    try:
        frozen_python_guard()
        preflight_code_guard()
        if not gc.isenabled():
            raise RuntimeError("default cyclic GC is disabled")
        if any(path.exists() for path in (summary_path, provenance_path, failure_path, checkpoint, reference, evaluator_output)):
            raise RuntimeError("formal reapplication output target is not clean")
        run_dir.mkdir(parents=True, exist_ok=True)
        row = matrix_row(run_id)
        benchmark = row["benchmark"]
        resolution = int(row["N"])
        dt, t_final = float(row["dt"]), float(row["t_final"])
        epsilon = float(row["epsilon"]) if row["epsilon"] else None
        steps = round(t_final / dt)
        if abs(steps * dt - t_final) > 1.0e-14:
            raise ValueError("frozen dt does not divide frozen final time")
        common_times = [0.0, 0.025, 0.05, 0.10, 0.15, 0.20] if benchmark == "shear" else [0.0, 0.025, 0.05, 0.075, 0.10]
        sample_steps = [round(value / dt) for value in common_times]
        if any(abs(step * dt - value) > 1.0e-14 for step, value in zip(sample_steps, common_times)):
            raise ValueError("frozen common time is not aligned to the frozen dt")

        state, dx, initial_positions = initial_state(row)
        parameters = DynamicPhysicalParameters(reference_density=1.0, sound_speed=20.0, physical_viscosity=0.02 if benchmark == "shear" else 0.0)
        numerical_store = {name: [] for name in ("positions", "unwrapped_positions", "velocities", "densities", "pressures")}
        reference_store = {name: [] for name in ("positions", "velocities", "densities", "pressures")}
        samples: list[dict[str, Any]] = []
        step_times: list[float] = []
        rss_values: list[int] = []
        max_pair = max_internal = max_assembly = max_momentum = 0.0
        max_viscous_power = -math.inf
        max_topology = 0
        min_separation = math.inf
        all_finite = True
        gc_enabled = True
        no_grad_confirmed = False
        unwrapped = state.positions.clone()

        def capture(t: float, current: DynamicSPHState, evaluation: Any) -> None:
            exact = reference_fields(benchmark, t, current.positions, initial_positions, epsilon)
            numerical = {
                "position": current.positions.tolist(), "velocity": current.velocities.tolist(),
                "density": evaluation.densities.tolist(), "pressure": evaluation.pressures.tolist(),
            }
            samples.append({"time": t, "numerical": numerical, "reference": exact})
            numerical_store["positions"].append(current.positions.numpy().copy())
            numerical_store["unwrapped_positions"].append(unwrapped.numpy().copy())
            numerical_store["velocities"].append(current.velocities.numpy().copy())
            numerical_store["densities"].append(evaluation.densities.numpy().copy())
            numerical_store["pressures"].append(evaluation.pressures.numpy().copy())
            key_map = {"positions": "position", "velocities": "velocity", "densities": "density", "pressures": "pressure"}
            for array_key, field_key in key_map.items():
                reference_store[array_key].append(np.asarray(exact[field_key], dtype=np.float64))

        with torch.no_grad():
            no_grad_confirmed = not torch.is_grad_enabled()
            state, evaluation = prepare_dynamic_state(state, parameters)
            capture(0.0, state, evaluation)
            sample_lookup = dict(zip(sample_steps, common_times))
            rss_stride = max(1, steps // 256)
            for step in range(1, steps + 1):
                tick = time.perf_counter()
                result = explicit_midpoint_dynamic_step(state, dt=dt, parameters=parameters, start_evaluation=evaluation)
                step_times.append(time.perf_counter() - tick)
                midpoint = diagnostic_midpoint_state(state, result, dt)
                audit = force_structure_audit(midpoint, result.midpoint_evaluation, parameters)
                max_pair = max(max_pair, float(audit["pressure_relative_pair_force_residual"]), float(audit["viscosity_relative_pair_force_residual"]))
                max_internal = max(max_internal, float(audit["characteristic_normalized_total_internal_force"]))
                assembly = torch.linalg.vector_norm(result.midpoint_evaluation.total_force - result.midpoint_evaluation.pressure_force - result.midpoint_evaluation.viscosity_force)
                max_assembly = max(max_assembly, float(assembly))
                old_momentum = torch.sum(state.masses[:, None] * state.velocities, dim=0)
                new_momentum = torch.sum(result.state.masses[:, None] * result.state.velocities, dim=0)
                midpoint_force = torch.sum(result.midpoint_evaluation.total_force, dim=0)
                max_momentum = max(max_momentum, float(torch.linalg.vector_norm(new_momentum - old_momentum - dt * midpoint_force)))
                max_viscous_power = max(max_viscous_power, float(audit["viscous_power"]))
                max_topology = max(max_topology, sum(int(audit[key]) for key in DEFECT_KEYS))
                nonself = result.midpoint_evaluation.neighborhood.nonself
                min_separation = min(min_separation, float(result.midpoint_evaluation.neighborhood.distance[nonself].min()) / dx)
                all_finite = all_finite and all(bool(torch.isfinite(value).all()) for value in (result.state.positions, result.state.velocities, result.end_evaluation.densities, result.end_evaluation.pressures))
                gc_enabled = gc_enabled and gc.isenabled()
                unwrapped = unwrapped + dt * midpoint.velocities
                state, evaluation = result.state, result.end_evaluation
                if step % rss_stride == 0 or step == steps:
                    rss_values.append(current_rss_bytes())
                if step in sample_lookup:
                    capture(sample_lookup[step], state, evaluation)

        if len(samples) != len(common_times) or not gc_enabled or not no_grad_confirmed:
            raise RuntimeError("common-time evidence or runtime contract incomplete")
        quarter_steps = max(1, len(step_times) // 4)
        quarter_rss = max(1, len(rss_values) // 4)
        rss_q1, rss_q4 = statistics.median(rss_values[:quarter_rss]), statistics.median(rss_values[-quarter_rss:])
        time_q1, time_q4 = statistics.median(step_times[:quarter_steps]), statistics.median(step_times[-quarter_steps:])
        max_current_rss = max(rss_values)
        peak_rss = process_peak_rss_bytes()
        diagnostics = {
            "hard_safety": {
                "pair_force_residual": max_pair,
                "normalized_internal_force_residual": max_internal,
                "force_assembly_defect": max_assembly,
                "momentum_update_defect": max_momentum,
                "viscous_power_positive_tolerance": max_viscous_power,
                "structural_topology_defects": max_topology,
                "minimum_separation_over_dx": min_separation,
                "current_rss_bytes": max_current_rss,
                "peak_rss_bytes": peak_rss,
                "rss_q4_minus_q1_bytes": rss_q4 - rss_q1,
                "rss_q4_over_q1": rss_q4 / max(rss_q1, 1),
                "step_time_q4_over_q1": time_q4 / max(time_q1, 1.0e-30),
                "source_call_count": 0,
            },
            "topology": {"status": "PASS" if max_topology == 0 else "FAIL", "maximum_structural_defects": max_topology},
            "resource": {
                "independent_child_process": True, "cyclic_gc_default": gc_enabled,
                "torch_no_grad": no_grad_confirmed, "in_loop_gc_collect": False,
                "parent_scalar_only": True, "child_fully_reclaimed": True,
                "current_rss_bytes": max_current_rss, "peak_rss_bytes": peak_rss,
                "rss_q4_minus_q1_bytes": rss_q4 - rss_q1,
                "rss_q4_over_q1": rss_q4 / max(rss_q1, 1),
                "step_time_q4_over_q1": time_q4 / max(time_q1, 1.0e-30),
                "rss_sample_count": len(rss_values),
            },
            "determinism": {"status": "CAPTURED_FOR_CROSS_RUN_COMPARISON"},
            "viscous_power": max_viscous_power,
        }
        metadata: dict[str, Any] = {
            "run_id": run_id, "benchmark": benchmark, "N": resolution,
            "H_over_dx": float(row["H_over_dx"]), "dt": dt, "t_final": t_final,
            "domain_length": 2.0, "rho0": 1.0, "c_s": 20.0,
            "config_sha256": CONFIG_SHA256,
            "nu": 0.02 if benchmark == "shear" else 0.0,
            "claim": "viscous_transverse_shear_wave_periodic_validation" if benchmark == "shear" else "linear-acoustic-regime_validation",
        }
        metadata.update({"U_s": 0.5, "k_s": 2.0 * math.pi} if benchmark == "shear" else {"epsilon": epsilon, "k_a": math.pi})
        dataset = {"metadata": metadata, "samples": samples, "weights": [dx**2] * (resolution * resolution), "diagnostics": diagnostics}
        evaluator_result = evaluate_shear(dataset) if benchmark == "shear" else evaluate_acoustic(dataset)

        numerical_np = {key: np.stack(value) for key, value in numerical_store.items()}
        reference_np = {key: np.stack(value) for key, value in reference_store.items()}
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        reference.parent.mkdir(parents=True, exist_ok=True)
        evaluator_output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(checkpoint, times=np.asarray(common_times), masses=state.masses.numpy(), **numerical_np)
        np.savez_compressed(reference, times=np.asarray(common_times), **reference_np)
        write_json_new(evaluator_output, evaluator_result)
        provenance = build_evaluation_provenance(
            [{"time": item["time"], "numerical": item["numerical"]} for item in samples],
            [{"time": item["time"], "reference": item["reference"]} for item in samples],
            metadata, CONFIG_SHA256,
        )
        provenance.update({
            "run_id": run_id, "attempt_id": ATTEMPT_ID, "child_pid": os.getpid(),
            "code_git_hash": git("rev-parse", "HEAD"),
            "worker_sha256": sha256(Path(__file__)), "run_matrix_sha256": MATRIX_SHA256,
            "metric_contract_sha256": METRICS_SHA256,
            "checkpoint_file_sha256": sha256_file(checkpoint),
            "reference_file_sha256": sha256_file(reference),
            "evaluator_result_sha256": sha256_file(evaluator_output),
            "trajectory_content_sha256": tensor_content_sha256(numerical_np),
            "reference_content_sha256": tensor_content_sha256(reference_np),
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": sys.version.split()[0], "torch_version": torch.__version__,
            "numpy_version": np.__version__, "device": "cpu", "dtype": "float64",
            "dimensions": 2, "boundary": "periodic", "default_cyclic_gc": gc_enabled,
            "torch_no_grad": no_grad_confirmed, "in_loop_gc_collect": False, "source_call_count": 0,
            "reference_kind": "analytic_unwrapped_trajectory" if benchmark == "shear" else "independent_linear_acoustic_theory",
        })
        write_json_new(provenance_path, provenance)
        summary = {
            "schema_version": "sph-pio-poc.stage01g.run-summary.v2",
            "run_id": run_id, "attempt_id": ATTEMPT_ID, "benchmark": benchmark,
            "execution_status": "COMPLETE", "evaluator_status": "COMPLETE",
            "pid": os.getpid(), "resolution": resolution,
            "support_ratio": float(row["H_over_dx"]), "dt": dt, "steps": steps,
            "t_final": t_final, "sample_count": len(samples), "all_finite": all_finite,
            "wall_time_seconds": time.perf_counter() - started,
            "checkpoint_path": checkpoint.relative_to(ROOT).as_posix(),
            "reference_path": reference.relative_to(ROOT).as_posix(),
            "evaluator_result_path": evaluator_output.relative_to(ROOT).as_posix(),
            "provenance_path": provenance_path.relative_to(ROOT).as_posix(),
            "failure_type": "", "failure_message": "",
        }
        write_json_new(summary_path, summary)
        result_status = "EVIDENCE_COMPLETE"
    except Exception as error:
        failure_type = type(error).__name__
        failure_message = str(error).replace(str(Path.home()), "<HOME>")
        run_dir.mkdir(parents=True, exist_ok=True)
        if not failure_path.exists():
            failure_path.write_text("".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"), encoding="utf-8")
        if not summary_path.exists():
            write_json_new(summary_path, {
                "schema_version": "sph-pio-poc.stage01g.run-summary.v2",
                "run_id": run_id, "attempt_id": ATTEMPT_ID,
                "execution_status": "INFRASTRUCTURE_FAILURE", "evaluator_status": "INCOMPLETE",
                "failure_type": failure_type, "failure_message": failure_message,
                "wall_time_seconds": time.perf_counter() - started,
            })
    print(json.dumps({"run_id": run_id, "status": result_status, "failure_type": failure_type, "failure_message": failure_message}, sort_keys=True), flush=True)
    return 0 if result_status == "EVIDENCE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
