"""One independent no-grad Stage 01D2 dynamic trajectory worker."""

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
from typing import Any, Mapping

import numpy as np
import torch
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01d2_v2_requalification"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_stage01d2_v2.yml"
SAMPLES_ROOT = EXPERIMENT_ROOT / "trajectory_samples"
STATES_ROOT = EXPERIMENT_ROOT / "trajectory_states"
SUMMARIES_ROOT = EXPERIMENT_ROOT / "run_summaries"
FAILURES_ROOT = EXPERIMENT_ROOT / "results" / "failures"

from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.diagnostics import (  # noqa: E402
    DYNAMIC_DIAGNOSTIC_COLUMNS,
    collect_dynamic_diagnostics,
    kinetic_energy,
    ordered_diagnostic_row,
    process_peak_rss_bytes,
    tgv_exact_kinetic_energy,
    tgv_exact_modal_amplitude,
    tgv_modal_basis,
)
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state, taylor_green_velocity  # noqa: E402
from structure_preserving.kernels import divergence_from_vector_gradient, quadratic_weighted_least_squares  # noqa: E402
from structure_preserving.neighborhood import minimum_image  # noqa: E402


SCHEMA = "sph-pio-poc.stage01d2.trajectory.v1"
TOPOLOGY_COLUMNS = (
    "neighbor_duplicate_edge_count",
    "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count",
    "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count",
    "neighbor_unexpected_edge_count",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    def finite_or_null(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: finite_or_null(nested) for key, nested in item.items()}
        if isinstance(item, (list, tuple)):
            return [finite_or_null(nested) for nested in item]
        if isinstance(item, float) and not math.isfinite(item):
            return None
        return item

    with path.open("x", encoding="utf-8") as stream:
        json.dump(finite_or_null(dict(value)), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_samples(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=DYNAMIC_DIAGNOSTIC_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(ordered_diagnostic_row(row))


def _write_states(
    path: Path,
    *,
    steps: list[int],
    times: list[float],
    positions: list[np.ndarray],
    velocities: list[np.ndarray],
) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {_relative(path)}")
    if not steps:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    if temporary.exists():
        raise RuntimeError(f"stale state archive temporary exists: {temporary.name}")
    np.savez_compressed(
        temporary,
        steps=np.asarray(steps, dtype=np.int64),
        times=np.asarray(times, dtype=np.float64),
        positions=np.stack(positions),
        velocities=np.stack(velocities),
    )
    temporary.replace(path)


def current_rss_bytes(pid: int | None = None) -> int:
    target = os.getpid() if pid is None else int(pid)
    try:
        output = subprocess.check_output(
            ("/bin/ps", "-o", "rss=", "-p", str(target)),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        output = ""
    return int(output) * 1024 if output else 0


def system_available_memory_fraction() -> float:
    if sys.platform == "darwin":
        vm = subprocess.check_output(("/usr/bin/vm_stat",), text=True)
        page_size = 4096
        first = vm.splitlines()[0]
        if "page size of" in first:
            page_size = int(first.split("page size of", 1)[1].split("bytes", 1)[0].strip())
        pages: dict[str, int] = {}
        for line in vm.splitlines()[1:]:
            if ":" in line:
                key, raw = line.split(":", 1)
                pages[key.strip()] = int(raw.strip().rstrip("."))
        available_pages = sum(
            pages.get(key, 0)
            for key in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable")
        )
        total = int(subprocess.check_output(("/usr/sbin/sysctl", "-n", "hw.memsize"), text=True).strip())
        return float(available_pages * page_size / total)
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        values: dict[str, int] = {}
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])
        return float(values["MemAvailable"] / values["MemTotal"])
    return 1.0


def _angular_momentum(positions: torch.Tensor, velocities: torch.Tensor, masses: torch.Tensor) -> torch.Tensor:
    return torch.sum(masses * (positions[:, 0] * velocities[:, 1] - positions[:, 1] * velocities[:, 0]))


def _divergence_l2(velocity: torch.Tensor, masses: torch.Tensor, density: torch.Tensor, neighborhood: Any) -> float:
    volume = masses / density
    gradient, _, _ = quadratic_weighted_least_squares(neighborhood, velocity, volume)
    divergence = divergence_from_vector_gradient(gradient)
    return float(torch.sqrt(torch.mean(divergence.square())))


def _selected_steps(steps: int, count: int) -> tuple[int, ...]:
    return tuple(int(value) for value in np.unique(np.linspace(0, steps, min(count, steps + 1), dtype=np.int64)))


def _median(values: list[float]) -> float:
    if not values:
        raise ValueError("empty quartile evidence")
    return float(statistics.median(values))


def _maximum(rows: list[dict[str, Any]], key: str, default: float = math.nan) -> float:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else default


def _minimum(rows: list[dict[str, Any]], key: str, default: float = math.nan) -> float:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else default


def _task(configuration: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    matches = [dict(row) for row in configuration["trajectory_matrix"] if row["run_id"] == run_id]
    if len(matches) != 1:
        raise ValueError(f"run_id must identify exactly one preregistered trajectory: {run_id}")
    return matches[0]


def run_trajectory(configuration: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    run_id = str(task["run_id"])
    sample_path = SAMPLES_ROOT / f"{run_id}.csv"
    state_path = STATES_ROOT / f"{run_id}.npz"
    summary_path = SUMMARIES_ROOT / f"{run_id}.json"
    failure_path = FAILURES_ROOT / f"{run_id}.txt"
    if any(path.exists() for path in (sample_path, state_path, summary_path, failure_path)):
        raise RuntimeError(f"refusing to overwrite outputs for {run_id}")
    if not gc.isenabled():
        raise RuntimeError("default cyclic GC is disabled at trajectory start")
    config_hash = _sha256(CONFIG_PATH)
    git_hash = _git_hash()
    physics = configuration["physics"]
    resource_limits = configuration["resource_gates"]
    dynamic_limits = configuration["dynamic_gates"]
    steps = int(task["steps"])
    dt = float(task["dt"])
    dx = 2.0 / int(task["resolution"])
    selected = set(_selected_steps(steps, int(configuration["sampling"]["common_physical_times"])))
    records: list[dict[str, Any]] = []
    archive_steps: list[int] = []
    archive_times: list[float] = []
    archive_positions: list[np.ndarray] = []
    archive_velocities: list[np.ndarray] = []
    step_times: list[float] = []
    completed_steps = 0
    failure_type = ""
    failure_message = ""
    started = time.perf_counter()
    state: Any = None
    evaluation: Any = None
    initial_positions: Any = None
    initial_density: Any = None
    current_rss_samples: list[float] = []
    system_available_samples: list[float] = []
    try:
        with torch.no_grad():
            state = initialize_taylor_green_state(
                int(task["resolution"]),
                support_ratio=float(task["support_ratio"]),
                reference_density=float(physics["reference_density"]),
                velocity_amplitude=float(physics["velocity_amplitude"]),
                physical_viscosity=float(physics["physical_viscosity"]),
                sound_speed=float(task["sound_speed"]),
                jitter_fraction=float(task["jitter_fraction"]),
                seed=int(task["seed"]),
                domain_minimum=tuple(float(value) for value in physics["domain_minimum"]),
                domain_maximum=tuple(float(value) for value in physics["domain_maximum"]),
            )
            if bool(task["zero_flow"]):
                state = state.with_updates(velocities=torch.zeros_like(state.velocities), pressures=torch.zeros_like(state.pressures))
                eos_reference_density = float(state.densities.mean())
            else:
                eos_reference_density = float(physics["reference_density"])
            parameters = DynamicPhysicalParameters(
                reference_density=eos_reference_density,
                sound_speed=float(task["sound_speed"]),
                physical_viscosity=float(physics["physical_viscosity"]),
            )
            state, evaluation = prepare_dynamic_state(state, parameters)
            initial_positions = state.positions.detach().clone()
            initial_density = evaluation.densities.detach().clone()
            unwrapped_positions = state.positions.detach().clone()
            reference_momentum = torch.sum(state.masses[:, None] * state.velocities, dim=0)
            reference_angular = _angular_momentum(unwrapped_positions, state.velocities, state.masses)
            initial_energy = kinetic_energy(state.velocities, state.masses)
            sample_index = 0
            for step in range(steps + 1):
                if step in selected:
                    rss = current_rss_bytes()
                    available = system_available_memory_fraction()
                    current_rss_samples.append(float(rss))
                    system_available_samples.append(float(available))
                    if bool(task["zero_flow"]):
                        exact_velocity = torch.zeros_like(state.velocities)
                        modal_basis = None
                        exact_amplitude = None
                        exact_energy = 0.0
                    else:
                        exact_velocity = taylor_green_velocity(
                            state.positions,
                            state.time,
                            velocity_amplitude=float(physics["velocity_amplitude"]),
                            physical_viscosity=float(physics["physical_viscosity"]),
                        )
                        modal_basis = tgv_modal_basis(state.positions)
                        exact_amplitude = tgv_exact_modal_amplitude(
                            state.time,
                            initial_velocity=float(physics["velocity_amplitude"]),
                            kinematic_viscosity=float(physics["physical_viscosity"]),
                        )
                        exact_energy = tgv_exact_kinetic_energy(
                            state.time,
                            initial_kinetic_energy=initial_energy,
                            kinematic_viscosity=float(physics["physical_viscosity"]),
                        )
                    record = collect_dynamic_diagnostics(
                        positions=state.positions,
                        velocity=state.velocities,
                        mass=state.masses,
                        density=evaluation.densities,
                        pressure=evaluation.pressures,
                        sound_speed=float(task["sound_speed"]),
                        neighborhood=evaluation.neighborhood,
                        physical_viscosity=float(physics["physical_viscosity"]),
                        assembled_acceleration=evaluation.acceleration,
                        time=state.time,
                        exact_velocity=exact_velocity,
                        modal_basis=modal_basis,
                        exact_modal_amplitude=exact_amplitude,
                        exact_kinetic_energy=exact_energy,
                        reference_density=eos_reference_density,
                        reference_momentum=reference_momentum,
                        reference_angular_momentum=reference_angular,
                        characteristic_velocity=float(physics["velocity_amplitude"]),
                        characteristic_length=float(physics["domain_length"]),
                        angular_momentum_positions=unwrapped_positions,
                        velocity_divergence_l2=_divergence_l2(state.velocities, state.masses, evaluation.densities, evaluation.neighborhood),
                        run_id=run_id,
                        config_hash=config_hash,
                        git_hash=git_hash,
                        sample_index=sample_index,
                        step=step,
                        dt=dt,
                        wall_clock_seconds=time.perf_counter() - started,
                        step_times_seconds=step_times,
                        peak_rss_bytes=process_peak_rss_bytes(),
                        viscous_power_positive_absolute_tolerance=float(dynamic_limits["viscous_power_positive_absolute_tolerance"]),
                    )
                    record["current_rss_bytes"] = rss
                    record["system_memory_free_percent"] = 100.0 * available
                    if bool(task["zero_flow"]):
                        record["position_drift_linf"] = float((state.positions - initial_positions).abs().max())
                        record["velocity_linf"] = float(state.velocities.abs().max())
                        record["relative_density_drift"] = float((evaluation.densities - initial_density).abs().max() / initial_density.abs().max())
                    records.append(record)
                    archive_steps.append(step)
                    archive_times.append(float(state.time))
                    archive_positions.append(state.positions.detach().cpu().numpy().copy())
                    archive_velocities.append(state.velocities.detach().cpu().numpy().copy())
                    sample_index += 1
                    topology_defect = max(int(record[column]) for column in TOPOLOGY_COLUMNS)
                    pair_residual = max(float(record["pressure_relative_pair_force_residual"]), float(record["viscosity_relative_pair_force_residual"]))
                    internal_residual = max(float(record["relative_total_internal_force"]), float(record["assembled_relative_internal_force"]))
                    separation_ratio = float(record["minimum_separation"]) / dx
                    hard_failure = ""
                    if not bool(record["state_all_finite"]):
                        hard_failure = "nonfinite state"
                    elif topology_defect != int(dynamic_limits["topology_defect_count_required"]):
                        hard_failure = f"topology defect count {topology_defect}"
                    elif pair_residual > float(dynamic_limits["maximum_relative_pair_force_residual"]):
                        hard_failure = f"pair residual {pair_residual}"
                    elif internal_residual > float(dynamic_limits["maximum_normalized_internal_force_residual"]):
                        hard_failure = f"internal residual {internal_residual}"
                    elif float(record["accumulated_viscous_power"]) > float(dynamic_limits["viscous_power_positive_absolute_tolerance"]):
                        hard_failure = f"positive viscous power {record['accumulated_viscous_power']}"
                    elif separation_ratio < float(dynamic_limits["minimum_separation_over_dx"]):
                        hard_failure = f"minimum separation/dx {separation_ratio}"
                    elif rss >= int(resource_limits["current_rss_limit_bytes"]):
                        hard_failure = f"current RSS {rss}"
                    elif process_peak_rss_bytes() >= int(resource_limits["peak_rss_limit_bytes"]):
                        hard_failure = f"peak RSS {process_peak_rss_bytes()}"
                    elif available < float(resource_limits["minimum_system_available_memory_fraction"]):
                        hard_failure = f"system available fraction {available}"
                    if bool(task["zero_flow"]):
                        zero = configuration["prerequisites"]["zero_flow_tolerances"]
                        zero_failures = [
                            name
                            for name, observed in (
                                ("position_drift_linf", float(record["position_drift_linf"])),
                                ("velocity_linf", float(record["velocity_linf"])),
                                ("pressure_absolute_maximum", float(record["pressure_absolute_maximum"])),
                                ("relative_density_drift", float(record["relative_density_drift"])),
                            )
                            if observed > float(zero[name])
                        ]
                        if zero_failures:
                            hard_failure = "zero-flow gates: " + ",".join(zero_failures)
                    if hard_failure:
                        raise RuntimeError(hard_failure)
                if step == steps:
                    break
                previous_position = state.positions
                tick = time.perf_counter()
                result = explicit_midpoint_dynamic_step(state, dt=dt, parameters=parameters, start_evaluation=evaluation)
                step_times.append(time.perf_counter() - tick)
                displacement = minimum_image(result.state.positions - previous_position, state.domain_extent)
                unwrapped_positions = unwrapped_positions + displacement
                state = result.state.with_updates(time=(step + 1) * dt)
                evaluation = result.end_evaluation
                del result
                completed_steps = step + 1
                if not all(bool(torch.isfinite(value).all()) for value in (state.positions, state.velocities, evaluation.densities, evaluation.pressures)):
                    raise FloatingPointError(f"nonfinite accepted state at step {completed_steps}")
                if not gc.isenabled():
                    raise RuntimeError(f"cyclic GC disabled during trajectory at step {completed_steps}")
    except Exception as error:
        failure_type = type(error).__name__
        failure_message = str(error).replace(str(Path.home()), "<HOME>")
        rendered = "".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>")
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        failure_path.write_text(rendered, encoding="utf-8")

    _write_samples(sample_path, records)
    _write_states(
        state_path,
        steps=archive_steps,
        times=archive_times,
        positions=archive_positions,
        velocities=archive_velocities,
    )
    first_step = step_times[: max(1, steps // 4)]
    final_step = step_times[3 * steps // 4 :] if step_times else []
    first_rss = current_rss_samples[1 : max(2, len(current_rss_samples) // 4 + 1)]
    final_rss = current_rss_samples[max(0, 3 * len(current_rss_samples) // 4) :]
    first_step_median = _median(first_step) if first_step else math.nan
    final_step_median = _median(final_step) if final_step else math.nan
    step_ratio = final_step_median / first_step_median if first_step_median > 0.0 else math.inf
    first_rss_median = _median(first_rss) if first_rss else math.nan
    final_rss_median = _median(final_rss) if final_rss else math.nan
    rss_delta = final_rss_median - first_rss_median
    rss_relative = rss_delta / max(first_rss_median, 1.0)
    final = records[-1] if records else {}
    maximum_topology_defect = max((_maximum(records, column, 0.0) for column in TOPOLOGY_COLUMNS), default=0.0)
    maximum_pair_residual = max(
        _maximum(records, "pressure_relative_pair_force_residual", math.inf),
        _maximum(records, "viscosity_relative_pair_force_residual", math.inf),
    )
    maximum_internal_residual = max(
        _maximum(records, "relative_total_internal_force", math.inf),
        _maximum(records, "assembled_relative_internal_force", math.inf),
    )
    current_rss = current_rss_bytes()
    peak_rss = process_peak_rss_bytes()
    resource_pass = bool(records) and all(
        (
            current_rss < int(resource_limits["current_rss_limit_bytes"]),
            peak_rss < int(resource_limits["peak_rss_limit_bytes"]),
            rss_delta <= int(resource_limits["quartile_rss_increase_limit_bytes"]),
            rss_relative <= float(resource_limits["quartile_rss_relative_increase_limit"]),
            step_ratio <= float(resource_limits["step_time_quartile_ratio_limit"]),
            min(system_available_samples, default=0.0) >= float(resource_limits["minimum_system_available_memory_fraction"]),
        )
    )
    numerical_pass = bool(records) and all(
        (
            completed_steps == steps,
            bool(final.get("state_all_finite", False)),
            maximum_topology_defect == 0,
            maximum_pair_residual <= float(dynamic_limits["maximum_relative_pair_force_residual"]),
            maximum_internal_residual <= float(dynamic_limits["maximum_normalized_internal_force_residual"]),
            _maximum(records, "accumulated_viscous_power", math.inf) <= float(dynamic_limits["viscous_power_positive_absolute_tolerance"]),
            _minimum(records, "minimum_separation", 0.0) / dx >= float(dynamic_limits["minimum_separation_over_dx"]),
        )
    )
    if not resource_pass and not failure_type:
        failure_type = "ResourceGateFailure"
        failure_message = "post-trajectory resource quartile gate failed"
    status = "PASS" if not failure_type and resource_pass and numerical_pass else "FAIL"
    summary = {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "pid": os.getpid(),
        "phase": task["phase"],
        "roles": task["roles"],
        "status": status,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "resolution": int(task["resolution"]),
        "particle_count": int(task["resolution"]) ** 2,
        "support_family": task["support_family"],
        "support_ratio": float(task["support_ratio"]),
        "dt": dt,
        "steps": steps,
        "completed_steps": completed_steps,
        "t_final": float(task["t_final"]),
        "final_time": float(state.time) if state is not None else math.nan,
        "sound_speed": float(task["sound_speed"]),
        "nominal_mach": float(physics["velocity_amplitude"]) / float(task["sound_speed"]),
        "layout": task["layout"],
        "jitter_fraction": float(task["jitter_fraction"]),
        "seed": int(task["seed"]),
        "zero_flow": bool(task["zero_flow"]),
        "default_gc_enabled_throughout": gc.isenabled(),
        "torch_no_grad_forward": True,
        "dynamic_neighborhood_reconstruction": True,
        "sample_count": len(records),
        "checkpoint_count": len(archive_steps),
        "final_velocity_error_l1": final.get("velocity_error_l1"),
        "final_velocity_relative_l2": final.get("velocity_relative_l2"),
        "final_velocity_error_linf": final.get("velocity_error_linf"),
        "final_modal_amplitude": final.get("modal_amplitude"),
        "final_modal_amplitude_error": final.get("modal_amplitude_error"),
        "final_kinetic_energy_error": final.get("kinetic_energy_error"),
        "final_density_fluctuation_relative_rms": final.get("density_fluctuation_relative_rms"),
        "maximum_density_fluctuation_relative_rms": _maximum(records, "density_fluctuation_relative_rms"),
        "maximum_mach": _maximum(records, "maximum_mach"),
        "maximum_pressure_absolute": _maximum(records, "pressure_absolute_maximum"),
        "maximum_momentum_drift_normalized": _maximum(records, "momentum_drift_normalized"),
        "maximum_angular_momentum_drift_normalized": _maximum(records, "angular_momentum_drift_normalized"),
        "maximum_velocity_divergence_l2": _maximum(records, "velocity_divergence_l2"),
        "minimum_separation_over_dx": _minimum(records, "minimum_separation") / dx,
        "mean_neighbor_count": float(statistics.mean(float(row["neighbor_count_mean"]) for row in records)) if records else math.nan,
        "mean_edge_count": float(statistics.mean(float(row["neighbor_edge_count"]) for row in records)) if records else math.nan,
        "maximum_topology_defect_count": maximum_topology_defect,
        "maximum_pair_force_residual": maximum_pair_residual,
        "maximum_normalized_internal_force_residual": maximum_internal_residual,
        "maximum_viscous_power": _maximum(records, "accumulated_viscous_power"),
        "numerical_and_topology_pass": numerical_pass,
        "current_rss_bytes": current_rss,
        "peak_rss_bytes": peak_rss,
        "first_quartile_rss_median_bytes": first_rss_median,
        "final_quartile_rss_median_bytes": final_rss_median,
        "quartile_rss_increase_bytes": rss_delta,
        "quartile_rss_relative_increase": rss_relative,
        "mean_step_time_seconds": float(statistics.mean(step_times)) if step_times else math.nan,
        "first_quartile_step_time_median_seconds": first_step_median,
        "final_quartile_step_time_median_seconds": final_step_median,
        "step_time_quartile_ratio": step_ratio,
        "minimum_system_available_memory_fraction": min(system_available_samples, default=0.0),
        "wall_time_seconds": time.perf_counter() - started,
        "resource_policy_pass": resource_pass,
        "acoustic_cfl_maximum": dt * (float(task["sound_speed"]) + _maximum(records, "maximum_speed", 0.0)) / dx,
        "position_drift_linf": final.get("position_drift_linf"),
        "velocity_linf": final.get("velocity_linf"),
        "pressure_absolute_maximum": final.get("pressure_absolute_maximum"),
        "relative_density_drift": final.get("relative_density_drift"),
        "trajectory_samples_path": _relative(sample_path),
        "trajectory_states_path": _relative(state_path) if state_path.exists() else "",
        "failure_path": _relative(failure_path) if failure_path.exists() else "",
        "config_sha256": config_hash,
        "code_git_hash": git_hash,
        "stage01dp_canary_data_used": False,
        "convergence_metric_role": task["roles"],
    }
    _write_json(summary_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("Stage 01D2 requires the sph-pio-poc environment")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    summary = run_trajectory(configuration, _task(configuration, args.run_id))
    print(json.dumps({"run_id": summary["run_id"], "status": summary["status"], "summary_path": _relative(SUMMARIES_ROOT / f"{args.run_id}.json")}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
