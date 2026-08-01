"""One maximum-horizon Stage 01D-P operational canary subprocess."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping

import torch
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_resource_policy.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"

from dynamic_solver.acceleration import DynamicPhysicalParameters, force_structure_audit  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402
from resource_diagnostics.support_margin_control import lightweight_topology_invariants  # noqa: E402


SCHEMA = "sph-pio-poc.stage01dp.canary.v1"
TOPOLOGY_KEYS = (
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
    with path.open("x", encoding="utf-8") as stream:
        json.dump(dict(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {_relative(path)}")
    if not rows:
        raise ValueError("canary produced no scalar samples")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


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


def peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def system_available_memory_fraction() -> float:
    if sys.platform == "darwin":
        vm = subprocess.check_output(("/usr/bin/vm_stat",), text=True)
        page_size = 4096
        first = vm.splitlines()[0]
        if "page size of" in first:
            page_size = int(first.split("page size of", 1)[1].split("bytes", 1)[0].strip())
        pages: dict[str, int] = {}
        for line in vm.splitlines()[1:]:
            if ":" not in line:
                continue
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


def _finite(state: Any, evaluation: Any) -> bool:
    return all(
        bool(torch.isfinite(value).all())
        for value in (
            state.positions,
            state.velocities,
            state.densities,
            state.pressures,
            evaluation.densities,
            evaluation.pressures,
            evaluation.acceleration,
        )
    )


def _median(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot compute median of empty evidence")
    return float(statistics.median(values))


def run_canary(configuration: Mapping[str, Any], repeat: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    canary = configuration["canary"]
    sampling = configuration["sampling"]
    limits = configuration["qualification"]
    steps = int(canary["steps"])
    dt = float(canary["time_step"])
    scalar_interval = int(sampling["scalar_interval_steps"])
    structure_interval = int(sampling["full_structure_interval_steps"])
    mandatory = {int(value) for value in sampling["mandatory_steps"]}
    scalar_steps = set(range(0, steps + 1, scalar_interval)) | mandatory
    structure_steps = set(range(0, steps + 1, structure_interval)) | mandatory
    run_id = f"stage01dp_canary_r{repeat}"
    if not gc.isenabled():
        raise RuntimeError("default cyclic GC was not enabled at worker start")
    state = initialize_taylor_green_state(
        int(canary["resolution"]),
        support_ratio=float(canary["support_ratio"]),
        reference_density=float(canary["reference_density"]),
        velocity_amplitude=float(canary["velocity_amplitude"]),
        physical_viscosity=float(canary["physical_viscosity"]),
        sound_speed=float(canary["sound_speed"]),
        jitter_fraction=float(canary["jitter_fraction"]),
        seed=int(canary["seed"]),
        domain_minimum=tuple(float(value) for value in canary["domain_minimum"]),
        domain_maximum=tuple(float(value) for value in canary["domain_maximum"]),
    )
    parameters = DynamicPhysicalParameters(
        reference_density=float(state.densities.mean()),
        sound_speed=float(canary["sound_speed"]),
        physical_viscosity=float(canary["physical_viscosity"]),
    )
    rows: list[dict[str, Any]] = []
    step_times: list[float] = []
    all_finite = True
    gc_enabled_throughout = True
    maximum_light_duplicate = 0
    maximum_light_nonreciprocal = 0
    maximum_topology = {key: 0 for key in TOPOLOGY_KEYS}
    maximum_pressure_pair = 0.0
    maximum_viscosity_pair = 0.0
    maximum_internal = 0.0
    maximum_viscous_power = -math.inf
    positive_viscous_power_count = 0
    diagnostic_count = 0
    completed_steps = 0
    started = time.perf_counter()

    def sample(step: int, step_wall: float) -> None:
        nonlocal all_finite, gc_enabled_throughout
        nonlocal maximum_light_duplicate, maximum_light_nonreciprocal
        nonlocal maximum_pressure_pair, maximum_viscosity_pair, maximum_internal
        nonlocal maximum_viscous_power, positive_viscous_power_count, diagnostic_count
        finite = _finite(state, evaluation)
        all_finite = all_finite and finite
        gc_enabled = gc.isenabled()
        gc_enabled_throughout = gc_enabled_throughout and gc_enabled
        light = lightweight_topology_invariants(evaluation.neighborhood)
        maximum_light_duplicate = max(maximum_light_duplicate, int(light["duplicate_edge_count"]))
        maximum_light_nonreciprocal = max(maximum_light_nonreciprocal, int(light["nonreciprocal_edge_count"]))
        record: dict[str, Any] = {
            "schema_version": SCHEMA,
            "run_id": run_id,
            "step": step,
            "time": float(state.time),
            "state_all_finite": finite,
            "gc_enabled": gc_enabled,
            "grad_enabled": torch.is_grad_enabled(),
            "current_rss_bytes": current_rss_bytes(),
            "peak_rss_bytes": peak_rss_bytes(),
            "system_available_memory_fraction": system_available_memory_fraction(),
            "step_wall_seconds": step_wall,
            "edge_count": int(light["edge_count"]),
            "light_duplicate_edge_count": int(light["duplicate_edge_count"]),
            "light_nonreciprocal_edge_count": int(light["nonreciprocal_edge_count"]),
            "full_structure_audit": step in structure_steps,
        }
        if step in structure_steps:
            audit = force_structure_audit(state, evaluation, parameters)
            diagnostic_count += 1
            for key in TOPOLOGY_KEYS:
                maximum_topology[key] = max(maximum_topology[key], int(audit[key]))
                record[key] = int(audit[key])
            pressure = float(audit["pressure_relative_pair_force_residual"])
            viscosity = float(audit["viscosity_relative_pair_force_residual"])
            internal = float(audit["characteristic_normalized_total_internal_force"])
            viscous_power = float(audit["viscous_power"])
            maximum_pressure_pair = max(maximum_pressure_pair, pressure)
            maximum_viscosity_pair = max(maximum_viscosity_pair, viscosity)
            maximum_internal = max(maximum_internal, internal)
            maximum_viscous_power = max(maximum_viscous_power, viscous_power)
            if viscous_power > float(limits["viscous_power_positive_absolute_tolerance"]):
                positive_viscous_power_count += 1
            record.update(
                {
                    "pressure_relative_pair_force_residual": pressure,
                    "viscosity_relative_pair_force_residual": viscosity,
                    "relative_total_internal_force": internal,
                    "viscous_power": viscous_power,
                }
            )
        rows.append(record)

    with torch.no_grad():
        state, evaluation = prepare_dynamic_state(state, parameters)
        sample(0, 0.0)
        for step in range(1, steps + 1):
            tick = time.perf_counter()
            result = explicit_midpoint_dynamic_step(
                state,
                dt=dt,
                parameters=parameters,
                start_evaluation=evaluation,
            )
            step_wall = time.perf_counter() - tick
            state = result.state
            evaluation = result.end_evaluation
            del result
            step_times.append(step_wall)
            completed_steps = step
            if step in scalar_steps:
                sample(step, step_wall)
            else:
                finite = _finite(state, evaluation)
                all_finite = all_finite and finite
                gc_enabled_throughout = gc_enabled_throughout and gc.isenabled()
                light = lightweight_topology_invariants(evaluation.neighborhood)
                maximum_light_duplicate = max(maximum_light_duplicate, int(light["duplicate_edge_count"]))
                maximum_light_nonreciprocal = max(maximum_light_nonreciprocal, int(light["nonreciprocal_edge_count"]))
            if not all_finite:
                raise FloatingPointError(f"nonfinite state at step {step}")
            if peak_rss_bytes() >= int(limits["peak_rss_limit_bytes"]):
                raise MemoryError(f"peak RSS reached operational stop at step {step}")

    first_quarter_rss = [
        float(row["current_rss_bytes"])
        for row in rows
        if 0 < int(row["step"]) <= steps // 4
    ]
    final_quarter_rss = [
        float(row["current_rss_bytes"])
        for row in rows
        if int(row["step"]) > 3 * steps // 4
    ]
    first_rss_median = _median(first_quarter_rss)
    final_rss_median = _median(final_quarter_rss)
    rss_increase = final_rss_median - first_rss_median
    rss_relative = rss_increase / max(first_rss_median, 1.0)
    first_step_median = _median(step_times[: steps // 4])
    final_step_median = _median(step_times[3 * steps // 4 :])
    slowdown_ratio = final_step_median / max(first_step_median, sys.float_info.min)
    current_rss = current_rss_bytes()
    peak_rss = peak_rss_bytes()
    minimum_available = min(float(row["system_available_memory_fraction"]) for row in rows)
    topology_pass = (
        maximum_light_duplicate == 0
        and maximum_light_nonreciprocal == 0
        and all(value == 0 for value in maximum_topology.values())
    )
    pair_pass = max(maximum_pressure_pair, maximum_viscosity_pair) <= float(limits["maximum_relative_pair_force_residual"])
    internal_pass = maximum_internal <= float(limits["maximum_characteristic_normalized_internal_force"])
    viscous_pass = positive_viscous_power_count == 0
    rss_pass = current_rss < int(limits["current_rss_limit_bytes"]) and peak_rss < int(limits["peak_rss_limit_bytes"])
    rss_growth_pass = (
        rss_increase <= int(limits["final_quartile_rss_increase_limit_bytes"])
        and rss_relative <= float(limits["final_quartile_rss_relative_increase_limit"])
    )
    timing_pass = slowdown_ratio <= float(limits["step_time_final_to_first_quartile_ratio_limit"])
    system_memory_pass = minimum_available >= float(limits["minimum_system_available_memory_fraction"])
    final_time_pass = abs(float(state.time) - float(canary["final_time"])) <= float(limits["completed_time_absolute_tolerance"])
    no_grad_pass = all(not bool(row["grad_enabled"]) for row in rows)
    policy_gate_pass = all(
        (
            completed_steps == int(limits["completed_steps_required"]),
            final_time_pass,
            all_finite,
            topology_pass,
            pair_pass,
            internal_pass,
            viscous_pass,
            rss_pass,
            rss_growth_pass,
            timing_pass,
            system_memory_pass,
            gc_enabled_throughout,
            no_grad_pass,
        )
    )
    summary = {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "repeat": repeat,
        "status": "PASS" if policy_gate_pass else "FAIL",
        "policy_gate_pass": policy_gate_pass,
        "completed_steps": completed_steps,
        "planned_steps": steps,
        "final_time": float(state.time),
        "final_time_pass": final_time_pass,
        "state_all_finite": all_finite,
        "default_gc_enabled_throughout": gc_enabled_throughout,
        "torch_no_grad_throughout": no_grad_pass,
        "dynamic_neighborhood_reconstruction": True,
        "maximum_light_duplicate_edge_count": maximum_light_duplicate,
        "maximum_light_nonreciprocal_edge_count": maximum_light_nonreciprocal,
        "maximum_full_topology_defect_count": max(maximum_topology.values()),
        "topology_pass": topology_pass,
        "full_structure_diagnostic_count": diagnostic_count,
        "maximum_pressure_relative_pair_force_residual": maximum_pressure_pair,
        "maximum_viscosity_relative_pair_force_residual": maximum_viscosity_pair,
        "pair_force_residual_pass": pair_pass,
        "maximum_relative_total_internal_force": maximum_internal,
        "internal_force_pass": internal_pass,
        "maximum_viscous_power": maximum_viscous_power,
        "positive_viscous_power_count": positive_viscous_power_count,
        "viscous_power_pass": viscous_pass,
        "current_rss_bytes": current_rss,
        "peak_rss_bytes": peak_rss,
        "first_quartile_rss_median_bytes": first_rss_median,
        "final_quartile_rss_median_bytes": final_rss_median,
        "final_minus_first_quartile_rss_median_bytes": rss_increase,
        "final_to_first_quartile_rss_relative_increase": rss_relative,
        "rss_limits_pass": rss_pass,
        "rss_growth_pass": rss_growth_pass,
        "minimum_system_available_memory_fraction": minimum_available,
        "system_memory_pressure_pass": system_memory_pass,
        "first_quartile_step_time_median_seconds": first_step_median,
        "final_quartile_step_time_median_seconds": final_step_median,
        "final_to_first_quartile_step_time_ratio": slowdown_ratio,
        "step_time_pass": timing_pass,
        "mean_step_wall_seconds": float(statistics.mean(step_times)),
        "total_worker_wall_seconds": time.perf_counter() - started,
        "scalar_sample_count": len(rows),
        "tensor_or_state_archives_written": 0,
        "convergence_metrics_computed": False,
        "config_sha256": _sha256(CONFIG_PATH),
        "git_hash": _git_hash(),
    }
    return summary, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("Stage 01D-P requires the sph-pio-poc environment")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    run_id = f"stage01dp_canary_r{args.repeat}"
    summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
    sample_path = RESULTS_ROOT / "scalar_samples" / f"{run_id}.csv"
    failure_path = RESULTS_ROOT / "failures" / f"{run_id}.txt"
    if any(path.exists() for path in (summary_path, sample_path, failure_path)):
        raise RuntimeError(f"refusing to overwrite outputs for {run_id}")
    rows: list[dict[str, Any]] = []
    try:
        summary, rows = run_canary(configuration, args.repeat)
    except Exception as error:
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        failure_path.write_text(
            "".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"),
            encoding="utf-8",
        )
        summary = {
            "schema_version": SCHEMA,
            "run_id": run_id,
            "repeat": args.repeat,
            "status": "ERROR",
            "policy_gate_pass": False,
            "failure_type": type(error).__name__,
            "failure_message": str(error).replace(str(Path.home()), "<HOME>"),
            "failure_path": _relative(failure_path),
            "config_sha256": _sha256(CONFIG_PATH),
            "git_hash": _git_hash(),
        }
    if rows:
        _write_csv(sample_path, rows)
        summary["scalar_samples_path"] = _relative(sample_path)
    _write_json(summary_path, summary)
    print(json.dumps({"run_id": run_id, "status": summary["status"], "summary_path": _relative(summary_path)}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
