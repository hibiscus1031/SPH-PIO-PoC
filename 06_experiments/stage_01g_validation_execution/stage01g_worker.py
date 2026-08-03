"""One isolated Stage 01G independent-validation benchmark run.

This execution adapter is intentionally separate from the frozen solver and
the frozen evaluator.  It binds one preregistered run row to those components,
retains complete trajectory/reference evidence, and returns only a scalar JSON
message to its parent process.
"""

from __future__ import annotations

import argparse
import csv
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
import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01g_validation_execution"
MATRIX = ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv"
CONFIG = ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"
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
from structure_preserving.neighborhood import periodic_cartesian_layout  # noqa: E402


CONFIG_SHA256 = "5025492f21f6b00c33ebc9533d27fbf632668945cba6a6a4a10df115c9ff1fe1"
METRIC_SHA256 = "655bfceb2339adfd07d9a4c724cbb66410210a76b865f6edcc0d6a74c7b9b042"
RUN_MATRIX_SHA256 = "ad79c1e7ea7af026222accc4ea8adff716c067b379954ca77697e475e5e0ba12"
FROZEN_PYTHON = Path("/opt/miniconda3/envs/sph-pio-poc/bin/python").resolve()
DEFECT_KEYS = (
    "neighbor_duplicate_edge_count",
    "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count",
    "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count",
    "neighbor_unexpected_edge_count",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip()


def current_rss_bytes() -> int:
    value = subprocess.check_output(
        ("/bin/ps", "-o", "rss=", "-p", str(os.getpid())), text=True
    ).strip()
    return int(value) * 1024


def write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def matrix_row(run_id: str) -> dict[str, str]:
    with MATRIX.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    matches = [row for row in rows if row["run_id"] == run_id]
    if len(rows) != 12 or len(matches) != 1:
        raise ValueError("run ID is not uniquely preregistered in the frozen 12-run matrix")
    row = matches[0]
    if row["stage01g_status"] != "PREREGISTERED_NOT_EXECUTED":
        raise ValueError("frozen run status is not PREREGISTERED_NOT_EXECUTED")
    expected = STAGE / "runs" / run_id
    if (ROOT / row["future_output_directory"]).resolve() != expected.resolve():
        raise ValueError("run output path differs from the frozen matrix")
    return row


def initial_state(row: dict[str, str]) -> tuple[DynamicSPHState, float, torch.Tensor]:
    resolution = int(row["N"])
    support_ratio = float(row["H_over_dx"])
    positions, dx, _ = periodic_cartesian_layout(
        resolution,
        dtype=torch.float64,
        domain_minimum=(-1.0, -1.0),
        domain_maximum=(1.0, 1.0),
    )
    count = resolution * resolution
    supports = torch.full((count,), support_ratio * dx, dtype=torch.float64)
    densities = torch.ones(count, dtype=torch.float64)
    pressures = torch.zeros(count, dtype=torch.float64)
    if row["benchmark"] == "shear":
        masses = torch.full((count,), dx**2, dtype=torch.float64)
        velocities = torch.stack(
            (0.5 * torch.sin((2.0 * math.pi) * positions[:, 1]), torch.zeros(count, dtype=torch.float64)),
            dim=-1,
        )
    elif row["benchmark"] == "acoustic":
        epsilon = float(row["epsilon"])
        exact_initial_density = 1.0 + epsilon * torch.cos(math.pi * positions[:, 0])
        masses = exact_initial_density * dx**2
        velocities = torch.zeros((count, 2), dtype=torch.float64)
    else:
        raise ValueError("unknown frozen benchmark")
    state = DynamicSPHState(
        positions=positions,
        velocities=velocities,
        masses=masses,
        densities=densities,
        pressures=pressures,
        supports=supports,
        domain_min=torch.tensor([-1.0, -1.0], dtype=torch.float64),
        domain_max=torch.tensor([1.0, 1.0], dtype=torch.float64),
        time=0.0,
    )
    return state, dx, positions.clone()


def reference_fields(
    benchmark: str,
    time_value: float,
    numerical_positions: torch.Tensor,
    initial_positions: torch.Tensor,
    epsilon: float | None,
) -> dict[str, list[Any]]:
    if benchmark == "shear":
        wave_number = 2.0 * math.pi
        viscosity = 0.02
        amplitude = 0.5
        decay = math.exp(-viscosity * wave_number**2 * time_value)
        y0 = initial_positions[:, 1]
        velocity_x = amplitude * torch.sin(wave_number * y0) * decay
        displacement = (
            amplitude
            * torch.sin(wave_number * y0)
            * (1.0 - decay)
            / (viscosity * wave_number**2)
        )
        positions = initial_positions.clone()
        positions[:, 0] += displacement
        velocities = torch.stack((velocity_x, torch.zeros_like(velocity_x)), dim=-1)
        density = torch.ones(initial_positions.shape[0], dtype=torch.float64)
        pressure = torch.zeros_like(density)
    else:
        if epsilon is None:
            raise ValueError("acoustic reference requires epsilon")
        positions = numerical_positions.clone()
        x = positions[:, 0]
        omega = 20.0 * math.pi
        density = 1.0 + epsilon * torch.cos(math.pi * x) * math.cos(omega * time_value)
        velocity_x = 20.0 * epsilon * torch.sin(math.pi * x) * math.sin(omega * time_value)
        velocities = torch.stack((velocity_x, torch.zeros_like(velocity_x)), dim=-1)
        pressure = 20.0**2 * (density - 1.0)
    return {
        "position": positions.tolist(),
        "velocity": velocities.tolist(),
        "density": density.tolist(),
        "pressure": pressure.tolist(),
    }


def tensor_content_sha256(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(arrays):
        value = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(str(value.dtype).encode("ascii") + b"\0")
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_id = args.run_id
    run_dir = STAGE / "runs" / run_id
    failure_path = run_dir / "failure.txt"
    summary_path = run_dir / "summary.json"
    evaluator_path = run_dir / "evaluator_result.json"
    provenance_path = run_dir / "provenance.json"
    checkpoint_path = STAGE / "checkpoints" / f"{run_id}.npz"
    reference_path = STAGE / "references" / f"{run_id}.npz"
    status = "FAIL"
    failure_type = ""
    failure_message = ""
    wall_started = time.perf_counter()

    try:
        if Path(sys.executable).resolve() != FROZEN_PYTHON:
            raise RuntimeError("worker is not running in the frozen sph-pio-poc environment")
        if not gc.isenabled():
            raise RuntimeError("default cyclic GC must remain enabled")
        if sha256(CONFIG) != CONFIG_SHA256 or sha256(MATRIX) != RUN_MATRIX_SHA256:
            raise RuntimeError("frozen Stage 01G config or matrix identity drift")
        if sha256(ROOT / "07_reports/stage_01g_validation_metrics.md") != METRIC_SHA256:
            raise RuntimeError("frozen Stage 01G metric contract identity drift")
        if any(path.exists() for path in (summary_path, evaluator_path, provenance_path, checkpoint_path, reference_path)):
            raise RuntimeError("refusing to overwrite existing run evidence")

        row = matrix_row(run_id)
        benchmark = row["benchmark"]
        resolution = int(row["N"])
        dt = float(row["dt"])
        t_final = float(row["t_final"])
        epsilon = None if not row["epsilon"] else float(row["epsilon"])
        steps = round(t_final / dt)
        if steps < 1 or abs(steps * dt - t_final) > 1.0e-14:
            raise ValueError("frozen dt must exactly divide t_final")
        common_times = (
            [0.0, 0.025, 0.05, 0.10, 0.15, 0.20]
            if benchmark == "shear"
            else [0.0, 0.025, 0.05, 0.075, 0.10]
        )
        sample_steps = [round(value / dt) for value in common_times]
        if any(abs(step * dt - value) > 1.0e-14 for step, value in zip(sample_steps, common_times)):
            raise ValueError("frozen dt is incompatible with common times")

        state, dx, initial_positions = initial_state(row)
        parameters = DynamicPhysicalParameters(
            reference_density=1.0,
            sound_speed=20.0,
            physical_viscosity=0.02 if benchmark == "shear" else 0.0,
        )
        numerical_arrays: dict[str, list[np.ndarray]] = {
            name: [] for name in ("positions", "unwrapped_positions", "velocities", "densities", "pressures")
        }
        reference_arrays: dict[str, list[np.ndarray]] = {
            name: [] for name in ("positions", "velocities", "densities", "pressures")
        }
        samples: list[dict[str, Any]] = []
        rss_values: list[int] = []
        step_times: list[float] = []
        max_pair = 0.0
        max_internal = 0.0
        max_assembly = 0.0
        max_momentum = 0.0
        max_viscous_power = -math.inf
        max_topology = 0
        min_separation = math.inf
        all_finite = True
        gc_enabled_throughout = True
        unwrapped = state.positions.clone()

        def capture(time_value: float, current_state: DynamicSPHState, evaluation: Any) -> None:
            reference = reference_fields(
                benchmark,
                time_value,
                current_state.positions,
                initial_positions,
                epsilon,
            )
            numerical = {
                "position": current_state.positions.tolist(),
                "velocity": current_state.velocities.tolist(),
                "density": evaluation.densities.tolist(),
                "pressure": evaluation.pressures.tolist(),
            }
            samples.append({"time": time_value, "numerical": numerical, "reference": reference})
            numerical_arrays["positions"].append(current_state.positions.numpy().copy())
            numerical_arrays["unwrapped_positions"].append(unwrapped.numpy().copy())
            numerical_arrays["velocities"].append(current_state.velocities.numpy().copy())
            numerical_arrays["densities"].append(evaluation.densities.numpy().copy())
            numerical_arrays["pressures"].append(evaluation.pressures.numpy().copy())
            for key in reference_arrays:
                reference_arrays[key].append(np.asarray(reference[key], dtype=np.float64))

        with torch.no_grad():
            state, evaluation = prepare_dynamic_state(state, parameters)
            capture(0.0, state, evaluation)
            sample_lookup = {step: time_value for step, time_value in zip(sample_steps, common_times)}
            for step in range(1, steps + 1):
                tick = time.perf_counter()
                result = explicit_midpoint_dynamic_step(
                    state, dt=dt, parameters=parameters, start_evaluation=evaluation
                )
                elapsed = time.perf_counter() - tick
                step_times.append(elapsed)
                rss_values.append(current_rss_bytes())
                gc_enabled_throughout = gc_enabled_throughout and gc.isenabled()

                audit = force_structure_audit(result.midpoint_state, result.midpoint_evaluation, parameters)
                max_pair = max(
                    max_pair,
                    float(audit["pressure_relative_pair_force_residual"]),
                    float(audit["viscosity_relative_pair_force_residual"]),
                )
                max_internal = max(max_internal, float(audit["characteristic_normalized_total_internal_force"]))
                assembly = torch.linalg.vector_norm(
                    result.midpoint_evaluation.total_force
                    - result.midpoint_evaluation.pressure_force
                    - result.midpoint_evaluation.viscosity_force
                )
                max_assembly = max(max_assembly, float(assembly))
                old_momentum = torch.sum(state.masses[:, None] * state.velocities, dim=0)
                new_momentum = torch.sum(result.state.masses[:, None] * result.state.velocities, dim=0)
                midpoint_force = torch.sum(result.midpoint_evaluation.total_force, dim=0)
                momentum_defect = torch.linalg.vector_norm(new_momentum - old_momentum - dt * midpoint_force)
                max_momentum = max(max_momentum, float(momentum_defect))
                max_viscous_power = max(max_viscous_power, float(audit["viscous_power"]))
                max_topology = max(max_topology, sum(int(audit[key]) for key in DEFECT_KEYS))
                nonself = result.midpoint_evaluation.neighborhood.nonself
                separation = float(result.midpoint_evaluation.neighborhood.distance[nonself].min()) / dx
                min_separation = min(min_separation, separation)
                all_finite = all_finite and all(
                    bool(torch.isfinite(value).all())
                    for value in (
                        result.state.positions,
                        result.state.velocities,
                        result.end_evaluation.densities,
                        result.end_evaluation.pressures,
                    )
                )
                unwrapped = unwrapped + dt * result.midpoint_state.velocities
                state, evaluation = result.state, result.end_evaluation
                if step in sample_lookup:
                    capture(sample_lookup[step], state, evaluation)

        if len(samples) != len(common_times):
            raise RuntimeError("common-time evidence is incomplete")
        quarter = max(1, len(step_times) // 4)
        rss_q1 = statistics.median(rss_values[:quarter])
        rss_q4 = statistics.median(rss_values[-quarter:])
        time_q1 = statistics.median(step_times[:quarter])
        time_q4 = statistics.median(step_times[-quarter:])
        maximum_current_rss = max(rss_values)
        peak_rss = process_peak_rss_bytes()
        rss_ratio = rss_q4 / max(rss_q1, 1)
        time_ratio = time_q4 / max(time_q1, 1.0e-30)
        diagnostics = {
            "hard_safety": {
                "pair_force_residual": max_pair,
                "normalized_internal_force_residual": max_internal,
                "force_assembly_defect": max_assembly,
                "momentum_update_defect": max_momentum,
                "viscous_power_positive_tolerance": max_viscous_power,
                "structural_topology_defects": max_topology,
                "minimum_separation_over_dx": min_separation,
                "current_rss_bytes": maximum_current_rss,
                "peak_rss_bytes": peak_rss,
                "rss_q4_minus_q1_bytes": rss_q4 - rss_q1,
                "rss_q4_over_q1": rss_ratio,
                "step_time_q4_over_q1": time_ratio,
                "source_call_count": 0,
            },
            "topology": {"status": "PASS" if max_topology == 0 else "FAIL", "maximum_structural_defects": max_topology},
            "resource": {
                "independent_child_process": True,
                "cyclic_gc_default": gc_enabled_throughout,
                "torch_no_grad": True,
                "in_loop_gc_collect": False,
                "parent_scalar_only": True,
                "child_fully_reclaimed": True,
                "current_rss_bytes": maximum_current_rss,
                "peak_rss_bytes": peak_rss,
                "rss_q4_minus_q1_bytes": rss_q4 - rss_q1,
                "rss_q4_over_q1": rss_ratio,
                "step_time_q4_over_q1": time_ratio,
            },
            "determinism": {"status": "CAPTURED_FOR_CROSS_RUN_COMPARISON"},
            "viscous_power": max_viscous_power,
        }
        metadata: dict[str, Any] = {
            "run_id": run_id,
            "benchmark": benchmark,
            "N": resolution,
            "H_over_dx": float(row["H_over_dx"]),
            "dt": dt,
            "t_final": t_final,
            "domain_length": 2.0,
            "rho0": 1.0,
            "c_s": 20.0,
            "config_sha256": CONFIG_SHA256,
            "nu": 0.02 if benchmark == "shear" else 0.0,
            "claim": "viscous_transverse_shear_wave_periodic_validation" if benchmark == "shear" else "linear-acoustic-regime_validation",
        }
        if benchmark == "shear":
            metadata.update({"U_s": 0.5, "k_s": 2.0 * math.pi})
        else:
            metadata.update({"epsilon": epsilon, "k_a": math.pi})
        dataset = {
            "metadata": metadata,
            "samples": samples,
            "weights": [dx**2] * (resolution * resolution),
            "diagnostics": diagnostics,
        }
        evaluator_result = evaluate_shear(dataset) if benchmark == "shear" else evaluate_acoustic(dataset)

        numerical_np = {key: np.stack(value) for key, value in numerical_arrays.items()}
        reference_np = {key: np.stack(value) for key, value in reference_arrays.items()}
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            checkpoint_path,
            times=np.asarray(common_times, dtype=np.float64),
            masses=state.masses.numpy(),
            **numerical_np,
        )
        np.savez_compressed(
            reference_path,
            times=np.asarray(common_times, dtype=np.float64),
            **reference_np,
        )
        write_json(evaluator_path, evaluator_result)
        trajectory_payload = [{"time": sample["time"], "numerical": sample["numerical"]} for sample in samples]
        reference_payload = [{"time": sample["time"], "reference": sample["reference"]} for sample in samples]
        provenance = build_evaluation_provenance(
            trajectory_payload, reference_payload, metadata, CONFIG_SHA256
        )
        provenance.update(
            {
                "run_id": run_id,
                "code_git_hash": git_hash(),
                "run_matrix_sha256": RUN_MATRIX_SHA256,
                "metric_contract_sha256": METRIC_SHA256,
                "checkpoint_file_sha256": sha256_file(checkpoint_path),
                "reference_file_sha256": sha256_file(reference_path),
                "evaluator_result_sha256": sha256_file(evaluator_path),
                "trajectory_content_sha256": tensor_content_sha256(numerical_np),
                "reference_content_sha256": tensor_content_sha256(reference_np),
                "python_executable": str(Path(sys.executable).resolve()),
                "python_version": sys.version.split()[0],
                "torch_version": torch.__version__,
                "numpy_version": np.__version__,
                "device": "cpu",
                "dtype": "float64",
            }
        )
        write_json(provenance_path, provenance)

        hard = diagnostics["hard_safety"]
        checks = {
            "all_finite": all_finite,
            "pair_force": hard["pair_force_residual"] <= 1.0e-12,
            "internal_force": hard["normalized_internal_force_residual"] <= 1.0e-10,
            "force_assembly": hard["force_assembly_defect"] <= 1.0e-10,
            "momentum_update": hard["momentum_update_defect"] <= 1.0e-10,
            "viscous_power": hard["viscous_power_positive_tolerance"] <= 1.0e-12,
            "topology": hard["structural_topology_defects"] == 0,
            "minimum_separation": hard["minimum_separation_over_dx"] >= 0.25,
            "current_rss": hard["current_rss_bytes"] < 2_000_000_000,
            "peak_rss": hard["peak_rss_bytes"] < 4_000_000_000,
            "rss_absolute": hard["rss_q4_minus_q1_bytes"] <= 250_000_000,
            "rss_relative": hard["rss_q4_over_q1"] <= 1.50,
            "step_time": hard["step_time_q4_over_q1"] <= 1.30,
            "source_free": hard["source_call_count"] == 0,
            "default_gc": gc_enabled_throughout,
            "cpu_float64": state.positions.device.type == "cpu" and state.positions.dtype == torch.float64,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        summary = {
            "schema_version": "sph-pio-poc.stage01g.run-summary.v1",
            "run_id": run_id,
            "benchmark": benchmark,
            "status": status,
            "pid": os.getpid(),
            "resolution": resolution,
            "support_ratio": float(row["H_over_dx"]),
            "dt": dt,
            "steps": steps,
            "t_final": t_final,
            "sample_count": len(samples),
            "all_hard_safety_checks_pass": all(checks.values()),
            "maximum_pair_force_residual": max_pair,
            "maximum_normalized_internal_force_residual": max_internal,
            "maximum_force_assembly_defect": max_assembly,
            "maximum_momentum_update_defect": max_momentum,
            "maximum_viscous_power": max_viscous_power,
            "maximum_structural_topology_defects": max_topology,
            "minimum_separation_over_dx": min_separation,
            "maximum_current_rss_bytes": maximum_current_rss,
            "peak_rss_bytes": peak_rss,
            "rss_q4_minus_q1_bytes": rss_q4 - rss_q1,
            "rss_q4_over_q1": rss_ratio,
            "step_time_q4_over_q1": time_ratio,
            "wall_time_seconds": time.perf_counter() - wall_started,
            "checkpoint_path": checkpoint_path.relative_to(ROOT).as_posix(),
            "reference_path": reference_path.relative_to(ROOT).as_posix(),
            "evaluator_result_path": evaluator_path.relative_to(ROOT).as_posix(),
            "provenance_path": provenance_path.relative_to(ROOT).as_posix(),
            "code_git_hash": git_hash(),
            "config_sha256": CONFIG_SHA256,
            "failure_type": "",
            "failure_message": "",
        }
        write_json(summary_path, summary)
    except Exception as error:
        failure_type = type(error).__name__
        failure_message = str(error).replace(str(Path.home()), "<HOME>")
        if not failure_path.exists():
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text(
                "".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"),
                encoding="utf-8",
            )
        if not summary_path.exists():
            write_json(
                summary_path,
                {
                    "schema_version": "sph-pio-poc.stage01g.run-summary.v1",
                    "run_id": run_id,
                    "status": "FAIL",
                    "failure_type": failure_type,
                    "failure_message": failure_message,
                    "wall_time_seconds": time.perf_counter() - wall_started,
                    "code_git_hash": git_hash(),
                    "config_sha256": CONFIG_SHA256,
                },
            )
        status = "FAIL"

    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": status,
                "failure_type": failure_type,
                "failure_message": failure_message,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
