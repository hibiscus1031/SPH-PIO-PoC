"""Evaluate the preregistered Stage 01D-R memory campaign."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from audit_stage01d_freeze import audit as audit_stage01d_freeze


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_memory_diagnosis.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
FIGURE_ROOT = EXPERIMENT_ROOT / "figures"
SUMMARY_ROOT = RESULTS_ROOT / "run_summaries"
EXIT_ROOT = RESULTS_ROOT / "process_exit"
MEMORY_ROOT = RESULTS_ROOT / "memory_samples"
NUMERICAL_ROOT = RESULTS_ROOT / "numerical_samples"
RETENTION_ROOT = RESULTS_ROOT / "retention_samples"
WORKER_CONFIG_ROOT = RESULTS_ROOT / "run_configs"


ALLOWED_STATUSES = {
    "RESOURCE_PASS_ALLOCATOR_PLATEAU",
    "RESOURCE_PASS_AFTER_RETENTION_FIX",
    "RESOURCE_CONDITIONAL",
    "RESOURCE_FAIL_LINEAR_GROWTH",
    "RESOURCE_FAIL_UNRESOLVED",
}


def _git_hash() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()


def _source_tree_clean_for_analysis() -> tuple[bool, list[str]]:
    output = subprocess.check_output(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=PROJECT_ROOT,
        text=True,
    )
    allowed = (
        "06_experiments/stage_01dr_memory_diagnosis/results/",
        "06_experiments/stage_01dr_memory_diagnosis/logs/",
        "06_experiments/stage_01dr_memory_diagnosis/snapshots/",
        "06_experiments/stage_01dr_memory_diagnosis/figures/",
    )
    unexpected = [
        line
        for line in output.splitlines()
        if not line[3:].split(" -> ")[-1].startswith(allowed)
    ]
    return not unexpected, unexpected


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"non-object JSONL row at {path.name}:{line_number}")
        rows.append(value)
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _atomic_text(path: Path, value: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite immutable analysis: {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_text(
        path,
        json.dumps(
            dict(value),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
    )


def _atomic_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing empty analysis table: {path.name}")
    if path.exists():
        raise RuntimeError(f"refusing to overwrite immutable analysis: {_relative(path)}")
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(str(key))
                fieldnames.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _float(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"nonfinite numeric evidence: {value!r}")
    return result


def _theil_sen(x: Sequence[float], y: Sequence[float]) -> float:
    x_values = np.asarray(x, dtype=np.float64)
    y_values = np.asarray(y, dtype=np.float64)
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise RuntimeError("Theil-Sen slope requires at least two paired samples")
    left, right = np.triu_indices(len(x_values), k=1)
    delta_x = x_values[right] - x_values[left]
    valid = delta_x != 0.0
    if not bool(valid.any()):
        raise RuntimeError("Theil-Sen slope requires distinct x values")
    slopes = (y_values[right][valid] - y_values[left][valid]) / delta_x[valid]
    return float(np.median(slopes))


def _bootstrap_slope_interval(
    x: Sequence[float],
    y: Sequence[float],
    *,
    block_solver_steps: int,
    resamples: int,
    confidence_level: float,
    seed: int,
) -> tuple[float, float]:
    x_values = np.asarray(x, dtype=np.float64)
    y_values = np.asarray(y, dtype=np.float64)
    slope = _theil_sen(x_values, y_values)
    intercept = float(np.median(y_values - slope * x_values))
    residuals = y_values - (intercept + slope * x_values)
    cadence = float(np.median(np.diff(x_values)))
    block_length = max(1, int(round(block_solver_steps / cadence)))
    rng = np.random.default_rng(seed)
    left, right = np.triu_indices(len(x_values), k=1)
    delta_x = x_values[right] - x_values[left]
    slopes = np.empty(resamples, dtype=np.float64)
    for sample_index in range(resamples):
        sampled_indices: list[int] = []
        while len(sampled_indices) < len(residuals):
            start = int(rng.integers(0, len(residuals)))
            sampled_indices.extend(
                (start + offset) % len(residuals)
                for offset in range(block_length)
            )
        synthetic = (
            intercept
            + slope * x_values
            + residuals[np.asarray(sampled_indices[: len(residuals)])]
        )
        pair_slopes = (synthetic[right] - synthetic[left]) / delta_x
        slopes[sample_index] = np.median(pair_slopes)
    alpha = (1.0 - confidence_level) / 2.0
    return (
        float(np.quantile(slopes, alpha)),
        float(np.quantile(slopes, 1.0 - alpha)),
    )


def _series_growth(values: Sequence[float], steps: Sequence[float]) -> tuple[float, float, bool]:
    if len(values) < 2:
        return math.nan, math.nan, False
    slope = _theil_sen(steps, values)
    delta = float(values[-1] - values[0])
    return slope, delta, bool(slope > 0.0 and delta > 0.0)


def _consecutive_below(values: Sequence[float], *, threshold: float, count: int) -> bool:
    if len(values) < count:
        return False
    return any(
        all(value < threshold for value in values[index : index + count])
        for index in range(len(values) - count + 1)
    )


def _expected_run_ids(configuration: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    for resolution in (16, 32):
        run_id = f"stage01dr_frozen_regression_n{resolution}"
        expected[run_id] = {
            "kind": "numeric_regression",
            "order": resolution,
            "resolution": resolution,
            "variant": "NUMERIC_REGRESSION",
            "repeat": 1,
        }
    for entry in configuration["randomized_execution"]["qualifying_order"]:
        resolution = int(entry["resolution"])
        variant = str(entry["variant"])
        repeat = int(entry["repeat"])
        run_id = f"stage01dr_n{resolution}_v{variant.lower()}_r{repeat}"
        expected[run_id] = {
            "kind": "qualifying",
            "order": int(entry["order"]),
            "resolution": resolution,
            "variant": variant,
            "repeat": repeat,
        }
    sentinel_resolution = int(configuration["variants"]["D"]["resolution"])
    for entry in configuration["randomized_execution"]["sentinel_order"]:
        mode = str(entry["mode"])
        repeat = int(entry["repeat"])
        run_id = f"stage01dr_d_{mode}_n{sentinel_resolution}_r{repeat}"
        expected[run_id] = {
            "kind": "sentinel",
            "order": int(entry["order"]),
            "resolution": sentinel_resolution,
            "variant": "D",
            "repeat": repeat,
            "mode": mode,
        }
    return expected


def _numerical_gate(
    run_id: str,
    configuration: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    path = NUMERICAL_ROOT / f"{run_id}.csv"
    if not path.is_file():
        return False, {"numerical_rows": 0, "numerical_path": ""}
    rows = _read_csv(path)
    qualification = configuration["qualification"]
    topology = (
        "neighbor_duplicate_edge_count",
        "neighbor_missing_self_edge_count",
        "neighbor_nonreciprocal_nonself_edge_count",
        "neighbor_out_of_bounds_edge_count",
        "neighbor_omitted_strict_support_edge_count",
        "neighbor_unexpected_edge_count",
    )
    expected_steps = {
        int(value)
        for value in configuration["sampling"][
            "minimal_safety_audit_steps"
            if identity["variant"] == "A"
            else "stage01d_diagnostic_steps"
        ]
    }
    observed_steps = [int(row["step"]) for row in rows]
    row_identity_pass = bool(
        all(row.get("run_id") == run_id for row in rows)
        and set(observed_steps) == expected_steps
        and len(observed_steps) == len(set(observed_steps))
    )
    finite = bool(rows) and all(row["state_all_finite"] == "True" for row in rows)
    max_pair = max(
        max(
            _float(row["pressure_relative_pair_force_residual"]),
            _float(row["viscosity_relative_pair_force_residual"]),
        )
        for row in rows
    ) if rows else math.inf
    max_internal = max(
        (_float(row["relative_total_internal_force"]) for row in rows),
        default=math.inf,
    )
    max_viscous = max(
        (_float(row["viscous_power"]) for row in rows),
        default=math.inf,
    )
    max_momentum_drift = max(
        (_float(row["momentum_drift_normalized"]) for row in rows),
        default=math.inf,
    )
    min_separation = min(
        (_float(row["minimum_separation_over_dx"]) for row in rows),
        default=-math.inf,
    )
    topology_values = [
        _float(row[key]) for row in rows for key in topology
    ]
    topology_exact_zero = bool(
        topology_values
        and all(value == 0.0 and value.is_integer() for value in topology_values)
    )
    topology_max = max(topology_values, default=math.inf)
    passed = bool(
        row_identity_pass
        and finite
        and max_pair <= float(qualification["maximum_relative_pair_force_residual"])
        and max_internal
        <= float(qualification["maximum_characteristic_normalized_internal_force"])
        and max_viscous
        <= float(qualification["viscous_power_positive_absolute_tolerance"])
        and min_separation >= float(qualification["minimum_separation_over_dx"])
        and topology_exact_zero
    )
    return passed, {
        "numerical_rows": len(rows),
        "numerical_expected_rows": len(expected_steps),
        "numerical_identity_and_step_coverage_pass": row_identity_pass,
        "maximum_pair_force_residual": max_pair,
        "maximum_relative_total_internal_force": max_internal,
        "maximum_viscous_power": max_viscous,
        "maximum_momentum_drift_normalized": max_momentum_drift,
        "minimum_separation_over_dx": min_separation,
        "maximum_topology_defect_count": topology_max,
        "topology_values_exact_nonnegative_integers": topology_exact_zero,
        "numerical_path": _relative(path),
    }


def _run_metric(
    run_id: str,
    identity: Mapping[str, Any],
    configuration: Mapping[str, Any],
    *,
    config_hash: str,
    git_hash: str,
) -> dict[str, Any]:
    summary_path = SUMMARY_ROOT / f"{run_id}.json"
    exit_path = EXIT_ROOT / f"{run_id}.json"
    memory_path = MEMORY_ROOT / f"{run_id}.jsonl"
    retention_path = RETENTION_ROOT / f"{run_id}.csv"
    worker_config_path = WORKER_CONFIG_ROOT / f"{run_id}.json"
    if not all(
        path.is_file()
        for path in (
            summary_path,
            exit_path,
            memory_path,
            retention_path,
            worker_config_path,
        )
    ):
        raise RuntimeError(f"missing qualifying evidence for {run_id}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    process_exit = json.loads(exit_path.read_text(encoding="utf-8"))
    worker_config = json.loads(worker_config_path.read_text(encoding="utf-8"))
    samples = _read_jsonl(memory_path)
    retention_rows = _read_csv(retention_path)
    archive_only_failure_candidate = bool(
        identity["variant"] == "C"
        and summary.get("status") == "FAIL"
        and bool(summary.get("solver_completed"))
        and int(summary.get("completed_steps", -1))
        == int(summary.get("planned_steps", -2))
        and summary.get("failure_phase") == "archive"
    )
    if not samples:
        raise RuntimeError(f"empty memory evidence for {run_id}")
    worker_config_without_hash = dict(worker_config)
    recorded_resolved_hash = worker_config_without_hash.pop(
        "resolved_config_sha256", ""
    )
    recomputed_resolved_hash = hashlib.sha256(
        json.dumps(
            worker_config_without_hash,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    expected_sample_indices = list(range(len(samples)))
    expected_pid = int(process_exit.get("pid", -1))
    memory_contract = bool(
        all(
            row.get("schema_version")
            == "sph-pio-poc.stage01dr.memory-sample.v1"
            and int(row.get("pid", -1)) == expected_pid
            and int(row.get("particle_count", -1))
            == int(identity["resolution"]) ** 2
            and str(row.get("phase"))
            in set(configuration["sampling"]["process_phases"])
            and _float(row["current_rss_bytes"]) > 0.0
            and _float(row["current_vms_bytes"])
            >= _float(row["current_rss_bytes"])
            and _float(row["peak_rss_bytes"])
            >= _float(row["current_rss_bytes"])
            for row in samples
        )
        and all(
            _float(samples[index]["elapsed_seconds"])
            >= _float(samples[index - 1]["elapsed_seconds"])
            for index in range(1, len(samples))
        )
    )
    provenance = bool(
        summary.get("config_hash") == config_hash
        and summary.get("git_hash") == git_hash
        and process_exit.get("config_hash") == config_hash
        and process_exit.get("git_hash") == git_hash
        and worker_config.get("config_sha256") == config_hash
        and worker_config.get("git_hash") == git_hash
        and summary.get("run_id") == run_id
        and process_exit.get("run_id") == run_id
        and worker_config.get("run_id") == run_id
        and int(summary.get("resolution", -1)) == int(identity["resolution"])
        and int(process_exit.get("resolution", -1))
        == int(identity["resolution"])
        and int(worker_config.get("resolution", -1))
        == int(identity["resolution"])
        and str(summary.get("variant")) == str(identity["variant"])
        and str(process_exit.get("variant")) == str(identity["variant"])
        and str(worker_config.get("variant")) == str(identity["variant"])
        and int(process_exit.get("repeat", -1)) == int(identity["repeat"])
        and int(worker_config.get("repeat", -1)) == int(identity["repeat"])
        and process_exit.get("kind") == identity["kind"]
        and int(process_exit.get("order", -1)) == int(identity["order"])
        and str(process_exit.get("mode", "")) == ""
        and worker_config.get("mode") is None
        and int(summary.get("pid", -1)) == expected_pid
        and int(worker_config.get("pid", -1)) == expected_pid
        and recorded_resolved_hash == recomputed_resolved_hash
        and bool(summary.get("torch_no_grad"))
        and all(row.get("run_id") == run_id for row in samples)
        and [int(row.get("sample_index", -1)) for row in samples]
        == expected_sample_indices
        and memory_contract
    )
    pre_solver = [
        row
        for row in samples
        if row.get("phase") == "solver_step"
        and row.get("step") is not None
        and int(row["step"]) >= int(configuration["warmup"]["post_warmup_first_step"])
        and "pre_tensor_inventory" in str(row.get("note", ""))
    ]
    pre_solver.sort(key=lambda row: int(row["step"]))
    steps = [int(row["step"]) for row in pre_solver]
    rss = [_float(row["current_rss_bytes"]) for row in pre_solver]
    first_postwarmup = int(configuration["warmup"]["post_warmup_first_step"])
    last_postwarmup = int(configuration["warmup"]["post_warmup_last_step"])
    interval = int(configuration["sampling"]["solver_step_interval"])
    expected_steps = {
        step
        for step in range(0, last_postwarmup + 1, interval)
        if step >= first_postwarmup
    }
    expected_steps.update(
        int(step)
        for step in configuration["sampling"]["mandatory_solver_steps"]
        if first_postwarmup <= int(step) <= last_postwarmup
    )
    coverage_pass = set(steps) == expected_steps and len(steps) == len(set(steps))
    required_phase_step_pairs = {
        ("process_start", None),
        ("imports_complete", None),
        ("initial_state_complete", 0),
        ("first_neighborhood_complete", 0),
        ("warmup_complete", int(configuration["warmup"]["allocator_warmup_last_step"])),
        ("solver_step", first_postwarmup),
        ("solver_step", last_postwarmup),
        ("before_archive", last_postwarmup),
        ("after_archive", last_postwarmup),
        ("before_process_exit", last_postwarmup),
    }
    if archive_only_failure_candidate:
        required_phase_step_pairs.discard(("after_archive", last_postwarmup))
        required_phase_step_pairs.discard(
            ("before_process_exit", last_postwarmup)
        )
    observed_pre_phase_step_pairs = {
        (str(row.get("phase")), row.get("step"))
        for row in samples
        if "pre_tensor_inventory" in str(row.get("note", ""))
    }
    phase_coverage_pass = required_phase_step_pairs.issubset(
        observed_pre_phase_step_pairs
    )
    first_range = configuration["post_warmup_analysis"]["first_quartile_step_range"]
    final_range = configuration["post_warmup_analysis"]["final_quartile_step_range"]
    first_values = [
        value
        for step, value in zip(steps, rss)
        if int(first_range[0]) <= step <= int(first_range[1])
    ]
    final_values = [
        value
        for step, value in zip(steps, rss)
        if int(final_range[0]) <= step <= int(final_range[1])
    ]
    if not first_values or not final_values:
        raise RuntimeError(f"quartile RSS evidence missing for {run_id}")
    first_median = float(np.median(first_values))
    final_median = float(np.median(final_values))
    rss_delta = final_median - first_median
    rss_fraction = rss_delta / first_median
    rss_slope = _theil_sen(steps, rss)
    bootstrap = configuration["post_warmup_analysis"]["rss_positive_slope_significance"]
    stable_seed = int.from_bytes(hashlib.sha256(run_id.encode()).digest()[:4], "big")
    effective_bootstrap_seed = int(bootstrap["seed"]) + stable_seed
    rss_ci_low, rss_ci_high = _bootstrap_slope_interval(
        steps,
        rss,
        block_solver_steps=int(bootstrap["block_solver_steps"]),
        resamples=int(bootstrap["resamples"]),
        confidence_level=float(bootstrap["confidence_level"]),
        seed=effective_bootstrap_seed,
    )
    rss_by_step = dict(zip(steps, rss))
    window = int(configuration["post_warmup_analysis"]["rolling_window_steps"])
    rolling = [
        rss_by_step[step + window] - value
        for step, value in rss_by_step.items()
        if step + window in rss_by_step
    ]
    if not rolling:
        raise RuntimeError(f"rolling RSS evidence missing for {run_id}")

    inventory_rows = [
        row
        for row in samples
        if row.get("phase") == "solver_step"
        and row.get("step") is not None
        and int(row["step"]) >= 26
        and "post_tensor_inventory" in str(row.get("note", ""))
        and row.get("live_tensor_count") is not None
    ]
    inventory_rows.sort(key=lambda row: int(row["step"]))
    inventory_steps = [int(row["step"]) for row in inventory_rows]
    expected_inventory_steps = {
        int(step)
        for step in configuration["sampling"]["tensor_inventory_steps"]
        if first_postwarmup <= int(step) <= last_postwarmup
    }
    inventory_contract_pass = bool(
        set(inventory_steps) == expected_inventory_steps
        and len(inventory_steps) == len(set(inventory_steps))
        and all(
            int(row.get("tensor_inventory_error_count", -1)) == 0
            and _float(row["live_tensor_count"]) >= 0.0
            and _float(row["live_tensor_logical_bytes"]) >= 0.0
            and _float(row["live_tensor_unique_storage_bytes"]) >= 0.0
            for row in inventory_rows
        )
    )
    if not inventory_contract_pass:
        raise RuntimeError(f"tensor inventory contract incomplete for {run_id}")
    expected_retention_steps = {
        int(step)
        for step in configuration["sampling"]["tensor_inventory_steps"]
        if 0 <= int(step) <= last_postwarmup
    }
    solver_retention_rows = [
        row for row in retention_rows if row.get("phase") == "solver_step"
    ]
    release_retention_rows = [
        row
        for row in retention_rows
        if row.get("phase") == "after_solver_release"
    ]
    retention_contract_pass = bool(
        {int(row["step"]) for row in solver_retention_rows}
        == expected_retention_steps
        and len(solver_retention_rows) == len(expected_retention_steps)
        and (
            (
                archive_only_failure_candidate
                and len(release_retention_rows) == 0
            )
            or (
                not archive_only_failure_candidate
                and len(release_retention_rows) == 1
                and int(release_retention_rows[0]["step"])
                == last_postwarmup
            )
        )
        and all(int(row["alive_total"]) == 0 for row in retention_rows)
    )
    if not retention_contract_pass:
        raise RuntimeError(f"object-retention evidence incomplete for {run_id}")
    tensor_counts = [_float(row["live_tensor_count"]) for row in inventory_rows]
    tensor_bytes = [
        _float(row["live_tensor_unique_storage_bytes"])
        for row in inventory_rows
    ]
    tensor_count_slope, tensor_count_delta, tensor_count_positive = _series_growth(
        tensor_counts, inventory_steps
    )
    tensor_bytes_slope, tensor_bytes_delta, tensor_bytes_positive = _series_growth(
        tensor_bytes, inventory_steps
    )
    traced = [_float(row["tracemalloc_current_bytes"]) for row in pre_solver]
    trace_slope, trace_delta, _ = _series_growth(traced, steps)
    trace_floor = configuration["post_warmup_analysis"][
        "tracemalloc_sustained_growth_practical_floor"
    ]
    trace_positive = bool(
        trace_slope > float(trace_floor["robust_slope_minimum_bytes_per_step"])
        and trace_delta > float(trace_floor["final_minus_first_minimum_bytes"])
    )
    gc_values = [_float(row["gc_tracked_object_count"]) for row in pre_solver]
    gc_slope, gc_delta, _ = _series_growth(gc_values, steps)
    gc_floor = configuration["post_warmup_analysis"][
        "gc_tracked_object_sustained_growth_practical_floor"
    ]
    gc_positive = bool(
        gc_slope > float(gc_floor["robust_slope_minimum_objects_per_step"])
        and gc_delta > float(gc_floor["final_minus_first_minimum_objects"])
    )
    pressure_rows = [
        row
        for row in samples
        if row.get("system_memory_free_percent") is not None
        and "pre_tensor_inventory" in str(row.get("note", ""))
    ]
    pressure_values = [
        _float(row["system_memory_free_percent"]) for row in pressure_rows
    ]
    required_pressure_pairs = required_phase_step_pairs
    observed_pressure_pairs = {
        (str(row.get("phase")), row.get("step")) for row in pressure_rows
    }
    pressure_contract_pass = bool(
        required_pressure_pairs.issubset(observed_pressure_pairs)
        and all(0.0 <= value <= 100.0 for value in pressure_values)
    )
    if not pressure_contract_pass:
        raise RuntimeError(f"system-pressure evidence incomplete for {run_id}")
    qualification = configuration["qualification"]
    pressure_failure = _consecutive_below(
        pressure_values,
        threshold=float(qualification["system_memory_free_percentage_below"]),
        count=int(qualification["system_memory_pressure_consecutive_samples"]),
    )
    try:
        numerical_pass, numerical = _numerical_gate(
            run_id, configuration, identity
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as numerical_error:
        numerical_pass = False
        numerical = {
            "numerical_rows": 0,
            "numerical_path": "",
            "numerical_analysis_error": (
                f"{type(numerical_error).__name__}: {numerical_error}"
            ),
        }
    planned_steps = int(
        configuration["resolutions"][int(identity["resolution"])]["steps"]
    )
    completion_pass = bool(
        summary.get("status") == "PASS"
        and int(summary.get("completed_steps", -1)) == planned_steps
        and int(summary.get("planned_steps", -1)) == planned_steps
        and int(process_exit.get("return_code", -1)) == 0
    )
    reclamation_pass = bool(process_exit.get("process_absent_after_wait"))
    e_pass = bool(
        rss_delta
        <= float(configuration["post_warmup_analysis"]["rss_final_minus_first_maximum_bytes"])
        and rss_fraction
        <= float(
            configuration["post_warmup_analysis"][
                "rss_final_over_first_fractional_increase_maximum"
            ]
        )
    )
    f_pass = bool(
        rss_slope
        <= float(
            configuration["post_warmup_analysis"][
                "rss_robust_slope_maximum_bytes_per_step"
            ]
        )
    )
    max_current_rss = max(_float(row["current_rss_bytes"]) for row in samples)
    peak_rss = max(_float(row["peak_rss_bytes"]) for row in samples)
    rss_limit_pass = max_current_rss <= float(qualification["current_rss_stop_bytes"])
    archive_before = _float(summary.get("before_archive_current_rss_bytes", 0))
    archive_delta = _float(summary.get("archive_current_rss_delta_bytes", 0))
    archive_fraction = archive_delta / archive_before if archive_before > 0 else math.inf
    particle_count = int(summary.get("particle_count", int(identity["resolution"]) ** 2))
    step_wall_values = [
        _float(row["step_wall_seconds"])
        for row in pre_solver
        if row.get("step_wall_seconds") is not None
    ]
    mean_step_wall = (
        float(np.mean(step_wall_values)) if step_wall_values else None
    )
    final_edge_count = int(pre_solver[-1]["edge_count"])
    first_pre = pre_solver[0]
    final_pre = pre_solver[-1]

    def counter_delta(key: str) -> float | None:
        first_value = first_pre.get(key)
        final_value = final_pre.get(key)
        if first_value is None or final_value is None:
            return None
        return _float(final_value) - _float(first_value)

    rss_sustained_positive = bool(rss_slope > 0.0 and rss[-1] > rss[0])
    return {
        "run_id": run_id,
        **identity,
        "evaluable": True,
        "analysis_error": "",
        "status": summary.get("status"),
        "completed_steps": int(summary.get("completed_steps", -1)),
        "planned_steps": int(summary.get("planned_steps", -1)),
        "completion_pass": completion_pass,
        "provenance_pass": provenance,
        "sampling_coverage_pass": coverage_pass and phase_coverage_pass,
        "process_reclamation_pass": reclamation_pass,
        "numerical_pass": numerical_pass,
        "system_memory_pressure_pass": pressure_contract_pass and not pressure_failure,
        "rss_limit_pass": rss_limit_pass,
        "postwarmup_sample_count": len(pre_solver),
        "required_phase_coverage_pass": phase_coverage_pass,
        "first_quartile_rss_median_bytes": first_median,
        "final_quartile_rss_median_bytes": final_median,
        "final_minus_first_rss_bytes": rss_delta,
        "final_over_first_rss_fractional_increase": rss_fraction,
        "rss_theil_sen_bytes_per_step": rss_slope,
        "rss_bootstrap_ci95_lower_bytes_per_step": rss_ci_low,
        "rss_bootstrap_ci95_upper_bytes_per_step": rss_ci_high,
        "rss_bootstrap_effective_seed": effective_bootstrap_seed,
        "rss_sustained_positive": rss_sustained_positive,
        "rss_significantly_positive": bool(
            rss_sustained_positive and rss_ci_low > 0.0
        ),
        "rss_slope_limit_pass": f_pass,
        "rss_quartile_limit_pass": e_pass,
        "rolling_50_step_maximum_rss_increase_bytes": max(rolling),
        "maximum_current_rss_bytes": max_current_rss,
        "peak_rss_bytes": peak_rss,
        "postwarmup_vms_final_minus_first_bytes": (
            _float(final_pre["current_vms_bytes"])
            - _float(first_pre["current_vms_bytes"])
        ),
        "postwarmup_minor_page_fault_delta": counter_delta(
            "minor_page_faults"
        ),
        "postwarmup_major_page_fault_delta": counter_delta(
            "major_page_faults"
        ),
        "postwarmup_process_fault_delta": counter_delta("process_faults"),
        "postwarmup_process_pagein_delta": counter_delta("process_pageins"),
        "postwarmup_process_cow_fault_delta": counter_delta(
            "process_cow_faults"
        ),
        "maximum_tracemalloc_peak_bytes": max(
            _float(row["tracemalloc_peak_bytes"]) for row in samples
        ),
        "maximum_tracemalloc_internal_bytes": max(
            _float(row["tracemalloc_internal_bytes"]) for row in samples
        ),
        "tensor_inventory_sample_count": len(inventory_rows),
        "tensor_inventory_contract_pass": inventory_contract_pass,
        "retention_sample_count": len(retention_rows),
        "retention_contract_pass": retention_contract_pass,
        "maximum_watched_object_alive_count": max(
            int(row["alive_total"]) for row in retention_rows
        ),
        "system_pressure_sample_count": len(pressure_rows),
        "system_pressure_contract_pass": pressure_contract_pass,
        "tensor_count_theil_sen_per_step": tensor_count_slope,
        "tensor_count_final_minus_first": tensor_count_delta,
        "tensor_count_sustained_positive": tensor_count_positive,
        "tensor_bytes_theil_sen_per_step": tensor_bytes_slope,
        "tensor_bytes_final_minus_first": tensor_bytes_delta,
        "tensor_bytes_sustained_positive": tensor_bytes_positive,
        "tracemalloc_theil_sen_bytes_per_step": trace_slope,
        "tracemalloc_final_minus_first_bytes": trace_delta,
        "tracemalloc_sustained_positive": trace_positive,
        "gc_object_theil_sen_per_step": gc_slope,
        "gc_object_final_minus_first": gc_delta,
        "gc_object_sustained_positive": gc_positive,
        "archive_write_count": int(summary.get("archive_write_count", 0)),
        "archive_checkpoint_count": int(summary.get("archive_checkpoint_count", 0)),
        "archive_sha256": summary.get("archive_sha256", ""),
        "archive_bytes": int(summary.get("archive_bytes", 0)),
        "archive_uncompressed_array_bytes": int(
            summary.get("archive_uncompressed_array_bytes", 0)
        ),
        "before_archive_current_rss_bytes": summary.get(
            "before_archive_current_rss_bytes"
        ),
        "after_archive_current_rss_bytes": summary.get(
            "after_archive_current_rss_bytes"
        ),
        "peak_rss_through_archive_bytes": summary.get(
            "peak_rss_through_archive_bytes"
        ),
        "archive_current_rss_delta_bytes": archive_delta,
        "archive_current_rss_fraction": archive_fraction,
        "archive_path": summary.get("archive_path", ""),
        "solver_completed": bool(summary.get("solver_completed")),
        "last_completed_phase": summary.get("last_completed_phase", ""),
        "failure_class": summary.get("failure_class", ""),
        "failure_phase": summary.get("failure_phase", ""),
        "failure_evidence_path": summary.get("failure_evidence_path", ""),
        "particle_count": particle_count,
        "final_quartile_rss_bytes_per_particle": final_median / particle_count,
        "final_live_tensor_unique_storage_bytes": tensor_bytes[-1],
        "final_live_tensor_unique_storage_bytes_per_particle": (
            tensor_bytes[-1] / particle_count
        ),
        "mean_step_wall_seconds": mean_step_wall,
        "final_edge_count": final_edge_count,
        "final_edges_per_particle": final_edge_count / particle_count,
        "config_hash": config_hash,
        "git_hash": git_hash,
        "memory_sample_path": _relative(memory_path),
        "summary_path": _relative(summary_path),
        "process_exit_path": _relative(exit_path),
        "worker_config_path": _relative(worker_config_path),
        "retention_sample_path": _relative(retention_path),
        **numerical,
    }


def _incomplete_run_metric(
    run_id: str,
    identity: Mapping[str, Any],
    error: BaseException,
    configuration: Mapping[str, Any],
    *,
    config_hash: str,
    git_hash: str,
) -> dict[str, Any]:
    summary_path = SUMMARY_ROOT / f"{run_id}.json"
    exit_path = EXIT_ROOT / f"{run_id}.json"
    memory_path = MEMORY_ROOT / f"{run_id}.jsonl"
    worker_config_path = WORKER_CONFIG_ROOT / f"{run_id}.json"
    summary = (
        json.loads(summary_path.read_text(encoding="utf-8"))
        if summary_path.is_file()
        else {}
    )
    process_exit = (
        json.loads(exit_path.read_text(encoding="utf-8"))
        if exit_path.is_file()
        else {}
    )
    try:
        numerical_pass, numerical = _numerical_gate(
            run_id, configuration, identity
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as numerical_error:
        numerical_pass = False
        numerical = {
            "numerical_rows": 0,
            "numerical_path": "",
            "numerical_analysis_error": (
                f"{type(numerical_error).__name__}: {numerical_error}"
            ),
        }
    particle_count = int(identity["resolution"]) ** 2
    rendered_error = f"{type(error).__name__}: {error}"
    return {
        "run_id": run_id,
        **identity,
        "evaluable": False,
        "analysis_error": rendered_error,
        "status": summary.get("status", "EVIDENCE_INCOMPLETE"),
        "completed_steps": int(summary.get("completed_steps", -1)),
        "planned_steps": int(summary.get("planned_steps", -1)),
        "completion_pass": False,
        "provenance_pass": False,
        "sampling_coverage_pass": False,
        "process_reclamation_pass": bool(
            process_exit.get("process_absent_after_wait")
        ),
        "numerical_pass": numerical_pass,
        "system_memory_pressure_pass": False,
        "rss_limit_pass": False,
        "postwarmup_sample_count": 0,
        "first_quartile_rss_median_bytes": None,
        "final_quartile_rss_median_bytes": None,
        "final_minus_first_rss_bytes": None,
        "final_over_first_rss_fractional_increase": None,
        "rss_theil_sen_bytes_per_step": None,
        "rss_bootstrap_ci95_lower_bytes_per_step": None,
        "rss_bootstrap_ci95_upper_bytes_per_step": None,
        "rss_bootstrap_effective_seed": None,
        "rss_sustained_positive": False,
        "rss_significantly_positive": False,
        "rss_slope_limit_pass": False,
        "rss_quartile_limit_pass": False,
        "rolling_50_step_maximum_rss_increase_bytes": None,
        "maximum_current_rss_bytes": None,
        "peak_rss_bytes": None,
        "postwarmup_vms_final_minus_first_bytes": None,
        "postwarmup_minor_page_fault_delta": None,
        "postwarmup_major_page_fault_delta": None,
        "postwarmup_process_fault_delta": None,
        "postwarmup_process_pagein_delta": None,
        "postwarmup_process_cow_fault_delta": None,
        "maximum_tracemalloc_peak_bytes": None,
        "maximum_tracemalloc_internal_bytes": None,
        "tensor_inventory_sample_count": 0,
        "tensor_inventory_contract_pass": False,
        "retention_sample_count": 0,
        "retention_contract_pass": False,
        "maximum_watched_object_alive_count": None,
        "system_pressure_sample_count": 0,
        "system_pressure_contract_pass": False,
        "tensor_count_theil_sen_per_step": None,
        "tensor_count_final_minus_first": None,
        "tensor_count_sustained_positive": False,
        "tensor_bytes_theil_sen_per_step": None,
        "tensor_bytes_final_minus_first": None,
        "tensor_bytes_sustained_positive": False,
        "tracemalloc_theil_sen_bytes_per_step": None,
        "tracemalloc_final_minus_first_bytes": None,
        "tracemalloc_sustained_positive": False,
        "gc_object_theil_sen_per_step": None,
        "gc_object_final_minus_first": None,
        "gc_object_sustained_positive": False,
        "archive_write_count": int(summary.get("archive_write_count", 0)),
        "archive_checkpoint_count": int(
            summary.get("archive_checkpoint_count", 0)
        ),
        "archive_sha256": summary.get("archive_sha256", ""),
        "archive_bytes": summary.get("archive_bytes"),
        "archive_uncompressed_array_bytes": summary.get(
            "archive_uncompressed_array_bytes"
        ),
        "before_archive_current_rss_bytes": summary.get(
            "before_archive_current_rss_bytes"
        ),
        "after_archive_current_rss_bytes": summary.get(
            "after_archive_current_rss_bytes"
        ),
        "peak_rss_through_archive_bytes": summary.get(
            "peak_rss_through_archive_bytes"
        ),
        "archive_current_rss_delta_bytes": summary.get(
            "archive_current_rss_delta_bytes"
        ),
        "archive_current_rss_fraction": None,
        "archive_path": summary.get("archive_path", ""),
        "solver_completed": bool(summary.get("solver_completed")),
        "last_completed_phase": summary.get("last_completed_phase", ""),
        "failure_class": summary.get("failure_class", ""),
        "failure_phase": summary.get("failure_phase", ""),
        "failure_evidence_path": summary.get("failure_evidence_path", ""),
        "particle_count": particle_count,
        "final_quartile_rss_bytes_per_particle": None,
        "final_live_tensor_unique_storage_bytes": None,
        "final_live_tensor_unique_storage_bytes_per_particle": None,
        "mean_step_wall_seconds": summary.get("mean_step_wall_seconds"),
        "final_edge_count": summary.get("final_edge_count"),
        "final_edges_per_particle": None,
        "config_hash": config_hash,
        "git_hash": git_hash,
        "memory_sample_path": (
            _relative(memory_path) if memory_path.is_file() else ""
        ),
        "summary_path": (
            _relative(summary_path) if summary_path.is_file() else ""
        ),
        "process_exit_path": (
            _relative(exit_path) if exit_path.is_file() else ""
        ),
        "worker_config_path": (
            _relative(worker_config_path) if worker_config_path.is_file() else ""
        ),
        "retention_sample_path": "",
        **numerical,
    }


def _variant_rows(run_metrics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resolution in (16, 32):
        for variant in ("A", "B", "C"):
            selected = [
                row
                for row in run_metrics
                if int(row["resolution"]) == resolution and row["variant"] == variant
            ]
            trusted = [
                row
                for row in selected
                if bool(row.get("evaluable"))
                and bool(row.get("provenance_pass"))
                and bool(row.get("sampling_coverage_pass"))
                and bool(row.get("solver_completed"))
                and bool(row.get("numerical_pass"))
                and bool(row.get("system_memory_pressure_pass"))
                and bool(row.get("rss_limit_pass"))
            ]

            def median(key: str) -> float | None:
                values = [
                    float(row[key])
                    for row in trusted
                    if row.get(key) is not None
                ]
                return float(np.median(values)) if values else None

            rows.append(
                {
                    "resolution": resolution,
                    "variant": variant,
                    "repeat_count": len(selected),
                    "evaluable_count": sum(
                        bool(row.get("evaluable")) for row in selected
                    ),
                    "trusted_solver_repeat_count": len(trusted),
                    "completed_count": sum(bool(row["completion_pass"]) for row in selected),
                    "all_numerical_pass": all(bool(row["numerical_pass"]) for row in selected),
                    "all_sampling_pass": all(bool(row["sampling_coverage_pass"]) for row in selected),
                    "all_reclaimed": all(bool(row["process_reclamation_pass"]) for row in selected),
                    "all_rss_quartile_pass": all(bool(row["rss_quartile_limit_pass"]) for row in selected),
                    "all_rss_slope_pass": all(bool(row["rss_slope_limit_pass"]) for row in selected),
                    "median_final_quartile_rss_bytes": median(
                        "final_quartile_rss_median_bytes"
                    ),
                    "median_final_quartile_rss_bytes_per_particle": median(
                        "final_quartile_rss_bytes_per_particle"
                    ),
                    "median_final_live_tensor_bytes_per_particle": median(
                        "final_live_tensor_unique_storage_bytes_per_particle"
                    ),
                    "median_final_edge_count": median("final_edge_count"),
                    "median_final_edges_per_particle": median(
                        "final_edges_per_particle"
                    ),
                    "median_mean_step_wall_seconds": median(
                        "mean_step_wall_seconds"
                    ),
                    "median_rss_slope_bytes_per_step": median(
                        "rss_theil_sen_bytes_per_step"
                    ),
                    "median_postwarmup_rss_increment_bytes": median(
                        "final_minus_first_rss_bytes"
                    ),
                    "rss_over_limit_repeat_count": sum(
                        not bool(row["rss_slope_limit_pass"]) for row in trusted
                    ),
                    "rss_significant_positive_repeat_count": sum(
                        bool(row["rss_significantly_positive"]) for row in trusted
                    ),
                    "tensor_count_positive_repeat_count": sum(
                        bool(row["tensor_count_sustained_positive"]) for row in trusted
                    ),
                    "tensor_bytes_positive_repeat_count": sum(
                        bool(row["tensor_bytes_sustained_positive"]) for row in trusted
                    ),
                    "tracemalloc_positive_repeat_count": sum(
                        bool(row["tracemalloc_sustained_positive"]) for row in trusted
                    ),
                    "gc_object_positive_repeat_count": sum(
                        bool(row["gc_object_sustained_positive"]) for row in trusted
                    ),
                    "synchronized_rss_tensor_or_python_repeat_count": sum(
                        bool(row["rss_significantly_positive"])
                        and (
                            bool(row["tensor_count_sustained_positive"])
                            or bool(row["tensor_bytes_sustained_positive"])
                            or bool(row["tracemalloc_sustained_positive"])
                            or bool(row["gc_object_sustained_positive"])
                        )
                        for row in trusted
                    ),
                }
            )
    return rows


def _gate(
    gate: str,
    check: str,
    passed: bool,
    observed: Any,
    threshold: Any,
    source: str,
    detail: str = "",
) -> dict[str, Any]:
    def render(value: Any) -> str:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        return str(value)

    return {
        "gate": gate,
        "check": check,
        "passed": bool(passed),
        "observed": render(observed),
        "threshold": render(threshold),
        "source": source,
        "severity": "HARD",
        "detail": detail,
    }


def _numeric_regression_gate(
    expected: Mapping[str, Mapping[str, Any]],
    configuration: Mapping[str, Any],
    config_hash: str,
    git_hash: str,
) -> tuple[bool, dict[str, Any]]:
    row_count = 0
    bitwise = 0
    tolerance = 0
    identities = True
    for run_id, identity in expected.items():
        if identity["kind"] != "numeric_regression":
            continue
        summary_path = SUMMARY_ROOT / f"{run_id}.json"
        numerical_path = NUMERICAL_ROOT / f"{run_id}.csv"
        exit_path = EXIT_ROOT / f"{run_id}.json"
        worker_config_path = WORKER_CONFIG_ROOT / f"{run_id}.json"
        if not all(
            path.is_file()
            for path in (
                summary_path,
                numerical_path,
                exit_path,
                worker_config_path,
            )
        ):
            identities = False
            continue
        summary = json.loads(summary_path.read_text())
        process_exit = json.loads(exit_path.read_text())
        worker_config = json.loads(worker_config_path.read_text())
        rows = _read_csv(numerical_path)
        comparison = configuration["qualification"][
            "first_four_state_comparison"
        ]
        expected_pairs = {
            (int(step), str(field))
            for step in comparison["steps"]
            for field in comparison["fields"]
        }
        observed_pairs = [
            (int(row["step"]), str(row["field"])) for row in rows
        ]
        reference_path = PROJECT_ROOT / str(
            configuration["resolutions"][int(identity["resolution"])][
                "frozen_reference_archive"
            ]
        )
        per_run_contract = bool(
            len(rows) == len(expected_pairs)
            and set(observed_pairs) == expected_pairs
            and len(observed_pairs) == len(set(observed_pairs))
            and all(row.get("run_id") == run_id for row in rows)
            and all(row.get("shape_exact") == "True" for row in rows)
            and all(row.get("dtype_exact") == "True" for row in rows)
            and all(
                row.get("reference_path")
                == str(
                    configuration["resolutions"][int(identity["resolution"])][
                        "frozen_reference_archive"
                    ]
                )
                for row in rows
            )
            and reference_path.is_file()
            and all(
                row.get("reference_sha256") == _sha256(reference_path)
                for row in rows
            )
        )
        row_count += len(rows)
        bitwise += sum(row["bitwise_equal"] == "True" for row in rows)
        tolerance += sum(
            row["within_preregistered_tolerance"] == "True" for row in rows
        )
        identities = identities and per_run_contract and bool(
            summary.get("status") == "PASS"
            and summary.get("run_id") == run_id
            and summary.get("variant") == "NUMERIC_REGRESSION"
            and int(summary.get("resolution", -1))
            == int(identity["resolution"])
            and summary.get("config_hash") == config_hash
            and summary.get("git_hash") == git_hash
            and int(summary.get("pid", -1)) == int(process_exit.get("pid", -2))
            and process_exit.get("return_code") == 0
            and process_exit.get("process_absent_after_wait") is True
            and process_exit.get("kind") == "numeric_regression"
            and int(process_exit.get("resolution", -1))
            == int(identity["resolution"])
            and process_exit.get("config_hash") == config_hash
            and process_exit.get("git_hash") == git_hash
            and worker_config.get("config_sha256") == config_hash
            and worker_config.get("git_hash") == git_hash
            and worker_config.get("variant") == "NUMERIC_REGRESSION"
            and int(worker_config.get("pid", -1))
            == int(process_exit.get("pid", -2))
            and int(worker_config.get("resolution", -1))
            == int(identity["resolution"])
        )
    passed = bool(row_count == 40 and bitwise == 40 and tolerance == 40 and identities)
    return passed, {
        "row_count": row_count,
        "bitwise_equal_count": bitwise,
        "tolerance_pass_count": tolerance,
        "identity_pass": identities,
    }


def _campaign_order_gate(
    configuration: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    path = RESULTS_ROOT / "campaign_qualifying_index.csv"
    expected_ids = [
        (
            f"stage01dr_n{int(entry['resolution'])}_"
            f"v{str(entry['variant']).lower()}_r{int(entry['repeat'])}"
        )
        for entry in configuration["randomized_execution"]["qualifying_order"]
    ]
    if not path.is_file():
        return False, {
            "expected_run_count": len(expected_ids),
            "observed_run_count": 0,
            "order_exact": False,
            "serial_nonoverlap": False,
        }
    rows = _read_csv(path)
    observed_ids = [str(row.get("run_id", "")) for row in rows]
    order_exact = observed_ids == expected_ids
    config_hash = _sha256(CONFIG_PATH)
    git_hash = _git_hash()
    identity_exact = bool(
        len(rows) == len(configuration["randomized_execution"]["qualifying_order"])
        and all(
            row.get("kind") == "qualifying"
            and int(row.get("order", -1)) == int(entry["order"])
            and int(row.get("resolution", -1)) == int(entry["resolution"])
            and row.get("variant") == str(entry["variant"])
            and int(row.get("repeat", -1)) == int(entry["repeat"])
            and row.get("config_hash") == config_hash
            and row.get("git_hash") == git_hash
            and row.get("process_absent_after_wait") == "True"
            for row, entry in zip(
                rows,
                configuration["randomized_execution"]["qualifying_order"],
            )
        )
    )
    timestamps_present = all(
        row.get("started_unix_seconds") not in {None, ""}
        and row.get("ended_unix_seconds") not in {None, ""}
        for row in rows
    )
    serial_nonoverlap = bool(
        timestamps_present
        and all(
            _float(rows[index]["started_unix_seconds"])
            >= _float(rows[index - 1]["ended_unix_seconds"])
            for index in range(1, len(rows))
        )
    )
    return bool(order_exact and identity_exact and serial_nonoverlap), {
        "expected_run_count": len(expected_ids),
        "observed_run_count": len(rows),
        "order_exact": order_exact,
        "identity_exact": identity_exact,
        "serial_nonoverlap": serial_nonoverlap,
        "index_path": _relative(path),
    }


def _sentinel_gate(
    expected: Mapping[str, Mapping[str, Any]],
    config_hash: str,
    git_hash: str,
) -> tuple[bool, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for run_id, identity in expected.items():
        if identity["kind"] != "sentinel":
            continue
        summary_path = SUMMARY_ROOT / f"{run_id}.json"
        exit_path = EXIT_ROOT / f"{run_id}.json"
        memory_path = MEMORY_ROOT / f"{run_id}.jsonl"
        worker_config_path = WORKER_CONFIG_ROOT / f"{run_id}.json"
        if not all(
            path.is_file()
            for path in (
                summary_path,
                exit_path,
                memory_path,
                worker_config_path,
            )
        ):
            rows.append(
                {
                    "run_id": run_id,
                    "mode": identity["mode"],
                    "status": "EVIDENCE_INCOMPLETE",
                    "reachable_grad_graph_node_count": 0,
                    "final_positions_has_grad_fn": False,
                    "final_velocities_has_grad_fn": False,
                    "final_current_rss_bytes": 0,
                    "final_live_tensor_count": 0,
                    "final_live_tensor_unique_storage_bytes": 0,
                    "process_reclaimed": False,
                    "identity_pass": False,
                    "evidence_error": "missing sentinel artifact",
                }
            )
            continue
        summary = json.loads(summary_path.read_text())
        process_exit = json.loads(exit_path.read_text())
        worker_config = json.loads(worker_config_path.read_text())
        memory = _read_jsonl(memory_path)
        final_pre = [
            row
            for row in memory
            if row.get("phase") == "solver_step"
            and int(row.get("step", -1)) == 20
            and "pre_tensor_inventory" in str(row.get("note", ""))
        ]
        final_post = [
            row
            for row in memory
            if row.get("phase") == "solver_step"
            and int(row.get("step", -1)) == 20
            and "post_tensor_inventory" in str(row.get("note", ""))
        ]
        if len(final_pre) != 1 or len(final_post) != 1:
            rows.append(
                {
                    "run_id": run_id,
                    "mode": identity["mode"],
                    "status": "EVIDENCE_INCOMPLETE",
                    "reachable_grad_graph_node_count": int(
                        summary.get("reachable_grad_graph_node_count", 0)
                    ),
                    "final_positions_has_grad_fn": bool(
                        summary.get("final_positions_has_grad_fn")
                    ),
                    "final_velocities_has_grad_fn": bool(
                        summary.get("final_velocities_has_grad_fn")
                    ),
                    "final_current_rss_bytes": 0,
                    "final_live_tensor_count": 0,
                    "final_live_tensor_unique_storage_bytes": 0,
                    "process_reclaimed": bool(
                        process_exit.get("process_absent_after_wait")
                    ),
                    "identity_pass": False,
                    "evidence_error": "missing unique step-20 pre/post sample",
                }
            )
            continue
        final_pre_row = final_pre[0]
        final_post_row = final_post[0]
        rows.append(
            {
                "run_id": run_id,
                "mode": identity["mode"],
                "status": summary.get("status"),
                "reachable_grad_graph_node_count": int(
                    summary.get("reachable_grad_graph_node_count", -1)
                ),
                "final_positions_has_grad_fn": bool(
                    summary.get("final_positions_has_grad_fn")
                ),
                "final_velocities_has_grad_fn": bool(
                    summary.get("final_velocities_has_grad_fn")
                ),
                "final_current_rss_bytes": int(
                    final_pre_row["current_rss_bytes"]
                ),
                "final_live_tensor_count": int(
                    final_post_row["live_tensor_count"]
                ),
                "final_live_tensor_unique_storage_bytes": int(
                    final_post_row["live_tensor_unique_storage_bytes"]
                ),
                "process_reclaimed": bool(process_exit["process_absent_after_wait"]),
                "identity_pass": bool(
                    summary.get("run_id") == run_id
                    and summary.get("variant") == "D"
                    and summary.get("mode") == identity["mode"]
                    and int(summary.get("resolution", -1))
                    == int(identity["resolution"])
                    and summary.get("config_hash") == config_hash
                    and summary.get("git_hash") == git_hash
                    and int(summary.get("pid", -1))
                    == int(process_exit.get("pid", -2))
                    and process_exit.get("config_hash") == config_hash
                    and process_exit.get("git_hash") == git_hash
                    and process_exit.get("return_code") == 0
                    and process_exit.get("kind") == "sentinel"
                    and int(process_exit.get("order", -1))
                    == int(identity["order"])
                    and int(process_exit.get("repeat", -1))
                    == int(identity["repeat"])
                    and process_exit.get("mode") == identity["mode"]
                    and worker_config.get("config_sha256") == config_hash
                    and worker_config.get("git_hash") == git_hash
                    and worker_config.get("variant") == "D"
                    and worker_config.get("mode") == identity["mode"]
                    and int(worker_config.get("resolution", -1))
                    == int(identity["resolution"])
                    and int(worker_config.get("pid", -1))
                    == int(process_exit.get("pid", -2))
                    and [int(row.get("sample_index", -1)) for row in memory]
                    == list(range(len(memory)))
                    and all(
                        row.get("run_id") == run_id
                        and row.get("schema_version")
                        == "sph-pio-poc.stage01dr.memory-sample.v1"
                        and int(row.get("pid", -1))
                        == int(process_exit.get("pid", -2))
                        for row in memory
                    )
                ),
                "evidence_error": "",
            }
        )
    by_mode = {row["mode"]: row for row in rows}
    no_grad = by_mode.get("no_grad", {})
    grad = by_mode.get("grad_enabled", {})
    for row in rows:
        row["rss_delta_from_no_grad_bytes"] = int(
            row["final_current_rss_bytes"]
        ) - int(no_grad.get("final_current_rss_bytes", 0))
        row["live_tensor_count_delta_from_no_grad"] = int(
            row["final_live_tensor_count"]
        ) - int(no_grad.get("final_live_tensor_count", 0))
        row["live_tensor_bytes_delta_from_no_grad"] = int(
            row["final_live_tensor_unique_storage_bytes"]
        ) - int(no_grad.get("final_live_tensor_unique_storage_bytes", 0))
    passed = bool(
        len(rows) == 2
        and all(row["status"] == "PASS" for row in rows)
        and all(row["process_reclaimed"] for row in rows)
        and all(row["identity_pass"] for row in rows)
        and no_grad.get("reachable_grad_graph_node_count") == 0
        and not no_grad.get("final_positions_has_grad_fn")
        and not no_grad.get("final_velocities_has_grad_fn")
        and int(grad.get("reachable_grad_graph_node_count", 0)) > 0
        and (
            grad.get("final_positions_has_grad_fn")
            or grad.get("final_velocities_has_grad_fn")
        )
    )
    return passed, rows


def _archive_run_assessment(
    metric: Mapping[str, Any],
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    run_id = str(metric["run_id"])
    expected_snapshot = EXPERIMENT_ROOT / "snapshots" / f"{run_id}.npz"
    if metric["variant"] != "C":
        localized = bool(
            int(metric["archive_write_count"]) == 0
            and int(metric["archive_checkpoint_count"]) == 0
            and str(metric.get("archive_path", "")) == ""
            and not expected_snapshot.exists()
        )
        return {
            "run_id": run_id,
            "resolution": metric["resolution"],
            "repeat": metric["repeat"],
            "variant": metric["variant"],
            "solver_completed": bool(metric["solver_completed"]),
            "archive_only_failure": False,
            "archive_localized": localized,
            "archive_overhead_bounded": localized,
            "archive_contract_detail": "archive disabled",
        }

    qualification = configuration["qualification"]
    expected_steps = [
        int(value) for value in configuration["sampling"]["archive_checkpoint_steps"]
    ]
    archive_only_failure = bool(
        metric.get("status") == "FAIL"
        and bool(metric.get("solver_completed"))
        and int(metric.get("completed_steps", -1))
        == int(metric.get("planned_steps", -2))
        and metric.get("failure_phase") == "archive"
        and str(metric.get("failure_evidence_path", "")) != ""
    )
    if archive_only_failure:
        return {
            "run_id": run_id,
            "resolution": metric["resolution"],
            "repeat": metric["repeat"],
            "variant": metric["variant"],
            "solver_completed": True,
            "archive_only_failure": True,
            "archive_localized": True,
            "archive_overhead_bounded": False,
            "archive_contract_detail": "caught failure after 500 solver steps and before archive completion",
        }

    recorded_path = str(metric.get("archive_path", ""))
    relative_path = Path(recorded_path)
    path_contract = bool(
        recorded_path
        and not relative_path.is_absolute()
        and ".." not in relative_path.parts
    )
    archive_path = (PROJECT_ROOT / relative_path).resolve()
    expected_parent = (EXPERIMENT_ROOT / "snapshots").resolve()
    path_contract = bool(
        path_contract
        and archive_path.parent == expected_parent
        and archive_path == expected_snapshot.resolve()
        and archive_path.is_file()
    )
    array_contract = False
    if path_contract:
        try:
            with np.load(archive_path, allow_pickle=False) as archive:
                required_keys = {
                    "steps",
                    "times",
                    "positions",
                    "velocities",
                    "densities",
                    "pressures",
                }
                resolution = int(metric["resolution"])
                particle_count = resolution**2
                dt = float(configuration["resolutions"][resolution]["time_step"])
                array_contract = bool(
                    set(archive.files) == required_keys
                    and archive["steps"].dtype == np.dtype(np.int64)
                    and archive["steps"].tolist() == expected_steps
                    and np.array_equal(
                        archive["times"],
                        np.asarray(expected_steps, dtype=np.float64) * dt,
                    )
                    and archive["positions"].shape
                    == (len(expected_steps), particle_count, 2)
                    and archive["velocities"].shape
                    == (len(expected_steps), particle_count, 2)
                    and archive["densities"].shape
                    == (len(expected_steps), particle_count)
                    and archive["pressures"].shape
                    == (len(expected_steps), particle_count)
                    and all(
                        archive[key].dtype == np.dtype(np.float64)
                        and bool(np.isfinite(archive[key]).all())
                        for key in (
                            "times",
                            "positions",
                            "velocities",
                            "densities",
                            "pressures",
                        )
                    )
                )
        except (OSError, ValueError, KeyError):
            array_contract = False
    sha_contract = bool(
        path_contract
        and str(metric.get("archive_sha256", "")) == _sha256(archive_path)
        and int(metric.get("archive_bytes") or -1) == archive_path.stat().st_size
    )
    memory_rows = (
        _read_jsonl(PROJECT_ROOT / str(metric["memory_sample_path"]))
        if metric.get("memory_sample_path")
        else []
    )
    before_rows = [
        row
        for row in memory_rows
        if row.get("phase") == "before_archive"
        and "pre_tensor_inventory" in str(row.get("note", ""))
    ]
    after_rows = [
        row
        for row in memory_rows
        if row.get("phase") == "after_archive"
        and "pre_tensor_inventory" in str(row.get("note", ""))
    ]
    phase_contract = bool(
        len(before_rows) == 1
        and len(after_rows) == 1
        and int(before_rows[0]["current_rss_bytes"])
        == int(metric["before_archive_current_rss_bytes"])
        and int(after_rows[0]["current_rss_bytes"])
        == int(metric["after_archive_current_rss_bytes"])
    )
    localized = bool(
        metric.get("status") == "PASS"
        and bool(metric.get("completion_pass"))
        and int(metric["archive_write_count"]) == 1
        and int(metric["archive_checkpoint_count"]) == len(expected_steps)
        and path_contract
        and array_contract
        and sha_contract
        and phase_contract
        and bool(metric["rss_quartile_limit_pass"])
        and bool(metric["rss_slope_limit_pass"])
    )
    archive_delta = max(
        0.0, float(metric.get("archive_current_rss_delta_bytes") or 0.0)
    )
    before_rss = float(metric.get("before_archive_current_rss_bytes") or 0.0)
    archive_fraction = archive_delta / before_rss if before_rss > 0.0 else math.inf
    bounded = bool(
        localized
        and archive_delta
        <= float(
            qualification[
                "variant_c_archive_current_rss_increment_maximum_bytes"
            ]
        )
        and archive_fraction
        <= float(
            qualification[
                "variant_c_archive_current_rss_increment_fraction_maximum"
            ]
        )
    )
    return {
        "run_id": run_id,
        "resolution": metric["resolution"],
        "repeat": metric["repeat"],
        "variant": metric["variant"],
        "solver_completed": bool(metric["solver_completed"]),
        "archive_only_failure": False,
        "archive_localized": localized,
        "archive_overhead_bounded": bounded,
        "archive_current_rss_increment_bytes": archive_delta,
        "archive_current_rss_increment_fraction": archive_fraction,
        "archive_path_contract_pass": path_contract,
        "archive_array_contract_pass": array_contract,
        "archive_sha256_contract_pass": sha_contract,
        "archive_phase_contract_pass": phase_contract,
        "archive_contract_detail": "completed archive validation",
    }


def _save_figures(
    run_metrics: Sequence[Mapping[str, Any]],
    sentinel_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    colors = {"A": "#0072B2", "B": "#E69F00", "C": "#009E73"}
    for resolution in (16, 32):
        path = FIGURE_ROOT / f"stage01dr_n{resolution}_memory_curves.png"
        if path.exists():
            raise RuntimeError(f"refusing to overwrite figure: {_relative(path)}")
        figure, axis = plt.subplots(figsize=(8.0, 4.8), constrained_layout=True)
        for metric in run_metrics:
            if (
                int(metric["resolution"]) != resolution
                or not metric.get("memory_sample_path")
            ):
                continue
            memory_path = PROJECT_ROOT / str(metric["memory_sample_path"])
            if not memory_path.is_file():
                continue
            rows = _read_jsonl(memory_path)
            selected = [
                row
                for row in rows
                if row.get("phase") in {"solver_step", "warmup_complete"}
                and "pre_tensor_inventory" in str(row.get("note", ""))
                and row.get("step") is not None
            ]
            axis.plot(
                [int(row["step"]) for row in selected],
                [float(row["current_rss_bytes"]) / 1.0e6 for row in selected],
                color=colors[str(metric["variant"])],
                alpha=0.65,
                linewidth=1.2,
                label=f"{metric['variant']} r{metric['repeat']}",
            )
        axis.axvline(25, color="#666666", linestyle="--", linewidth=1.0)
        axis.set_xlabel("Solver step")
        axis.set_ylabel("Current RSS (MB, decimal)")
        axis.set_title(f"Stage 01D-R N={resolution}: current RSS")
        axis.grid(alpha=0.2)
        handles, labels = axis.get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        if unique:
            axis.legend(unique.values(), unique.keys(), ncol=3, fontsize=8)
        temporary = path.with_name(path.stem + ".tmp" + path.suffix)
        figure.savefig(temporary, dpi=180)
        plt.close(figure)
        temporary.replace(path)
        outputs.append(_relative(path))

    path = FIGURE_ROOT / "stage01dr_graph_sentinel.png"
    if path.exists():
        raise RuntimeError(f"refusing to overwrite figure: {_relative(path)}")
    figure, axes = plt.subplots(1, 2, figsize=(8.0, 3.8), constrained_layout=True)
    modes = [row["mode"] for row in sentinel_rows]
    axes[0].bar(modes, [row["final_current_rss_bytes"] / 1.0e6 for row in sentinel_rows])
    axes[0].set_ylabel("Current RSS at step 20 (MB)")
    axes[1].bar(modes, [row["reachable_grad_graph_node_count"] for row in sentinel_rows])
    axes[1].set_ylabel("Reachable grad graph nodes")
    for axis in axes:
        axis.tick_params(axis="x", rotation=15)
        axis.grid(axis="y", alpha=0.2)
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    figure.savefig(temporary, dpi=180)
    plt.close(figure)
    temporary.replace(path)
    outputs.append(_relative(path))
    return outputs


def _preflight_analysis_outputs() -> None:
    targets = [
        RESULTS_ROOT / "memory_run_metrics.csv",
        RESULTS_ROOT / "variant_summary.csv",
        RESULTS_ROOT / "diagnostics_overhead.csv",
        RESULTS_ROOT / "archive_assessment.csv",
        RESULTS_ROOT / "graph_sentinel_summary.csv",
        RESULTS_ROOT / "resource_gate_evidence.csv",
        RESULTS_ROOT / "stage01dr_resource_status.txt",
        RESULTS_ROOT / "analysis_summary.json",
        FIGURE_ROOT / "stage01dr_n16_memory_curves.png",
        FIGURE_ROOT / "stage01dr_n32_memory_curves.png",
        FIGURE_ROOT / "stage01dr_graph_sentinel.png",
    ]
    candidates: list[Path] = []
    for path in targets:
        candidates.append(path)
        candidates.append(path.with_name(path.name + ".tmp"))
        if path.suffix == ".png":
            candidates.append(path.with_name(path.stem + ".tmp" + path.suffix))
    existing = [path for path in candidates if path.exists()]
    if existing:
        raise RuntimeError(
            "refusing to overwrite existing analysis output: "
            + ", ".join(_relative(path) for path in existing)
        )


def _derive_resource_status(
    *,
    confirmed_linear: bool,
    hard_complete: bool,
    ambiguous_growth: bool,
    archive_localized: bool,
    isolated_overhead_only: bool,
    retention_fix_applied: bool,
    retention_fix_contract_pass: bool,
) -> str:
    if confirmed_linear:
        status = "RESOURCE_FAIL_LINEAR_GROWTH"
    elif not hard_complete or ambiguous_growth or not archive_localized:
        status = "RESOURCE_FAIL_UNRESOLVED"
    elif isolated_overhead_only:
        status = "RESOURCE_CONDITIONAL"
    elif retention_fix_applied and retention_fix_contract_pass:
        status = "RESOURCE_PASS_AFTER_RETENTION_FIX"
    else:
        status = "RESOURCE_PASS_ALLOCATOR_PLATEAU"
    if status not in ALLOWED_STATUSES:
        raise RuntimeError("derived an invalid Stage 01D-R status")
    return status


def _classify_repeated_n32_growth(
    variant_rows: Sequence[Mapping[str, Any]],
) -> tuple[bool, bool]:
    selected = [row for row in variant_rows if int(row["resolution"]) == 32]
    confirmed = any(
        int(row["rss_over_limit_repeat_count"]) >= 2
        or int(row["rss_significant_positive_repeat_count"]) >= 2
        or int(row["synchronized_rss_tensor_or_python_repeat_count"]) >= 2
        or int(row["tensor_count_positive_repeat_count"]) >= 2
        or int(row["tensor_bytes_positive_repeat_count"]) >= 2
        or int(row["tracemalloc_positive_repeat_count"]) >= 2
        or int(row["gc_object_positive_repeat_count"]) >= 2
        for row in selected
    )
    ambiguous = any(
        count == 1
        for row in selected
        for count in (
            int(row["rss_over_limit_repeat_count"]),
            int(row["rss_significant_positive_repeat_count"]),
            int(row["tensor_count_positive_repeat_count"]),
            int(row["tensor_bytes_positive_repeat_count"]),
            int(row["tracemalloc_positive_repeat_count"]),
            int(row["gc_object_positive_repeat_count"]),
        )
    )
    return confirmed, ambiguous


def main() -> int:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("status") != "PREREGISTERED_BEFORE_FIRST_STAGE_01DR_ROLLOUT":
        raise SystemExit("Stage 01D-R configuration is not preregistered")
    config_hash = _sha256(CONFIG_PATH)
    git_hash = _git_hash()
    qualification = configuration["qualification"]
    expected = _expected_run_ids(configuration)

    qualifying_identities = [
        identity for identity in expected.values() if identity["kind"] == "qualifying"
    ]
    expected_matrix = {
        (resolution, variant, repeat)
        for resolution in (16, 32)
        for variant in ("A", "B", "C")
        for repeat in (1, 2, 3)
    }
    observed_matrix = {
        (int(item["resolution"]), str(item["variant"]), int(item["repeat"]))
        for item in qualifying_identities
    }
    schedule_contract_pass = bool(
        len(qualifying_identities) == len(expected_matrix)
        and observed_matrix == expected_matrix
    )

    freeze_error = ""
    try:
        freeze_facts = audit_stage01d_freeze()
        freeze_pass = True
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        freeze_facts = {}
        freeze_pass = False
        freeze_error = f"{type(error).__name__}: {error}"
    source_tree_clean, source_changes = _source_tree_clean_for_analysis()
    campaign_order_pass, campaign_order_observed = _campaign_order_gate(
        configuration
    )

    run_metrics: list[dict[str, Any]] = []
    for run_id, identity in expected.items():
        if identity["kind"] != "qualifying":
            continue
        try:
            metric = _run_metric(
                run_id,
                identity,
                configuration,
                config_hash=config_hash,
                git_hash=git_hash,
            )
        except (OSError, KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
            metric = _incomplete_run_metric(
                run_id,
                identity,
                error,
                configuration,
                config_hash=config_hash,
                git_hash=git_hash,
            )
        run_metrics.append(metric)
    variant_rows = _variant_rows(run_metrics)

    try:
        regression_pass, regression_observed = _numeric_regression_gate(
            expected, configuration, config_hash, git_hash
        )
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
        regression_pass = False
        regression_observed = {
            "analysis_error": f"{type(error).__name__}: {error}"
        }
    try:
        sentinel_pass, sentinel_rows = _sentinel_gate(
            expected, config_hash, git_hash
        )
    except (OSError, KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
        sentinel_pass = False
        sentinel_rows = [
            {
                "run_id": run_id,
                "mode": identity["mode"],
                "status": "EVIDENCE_INCOMPLETE",
                "reachable_grad_graph_node_count": 0,
                "final_positions_has_grad_fn": False,
                "final_velocities_has_grad_fn": False,
                "final_current_rss_bytes": 0,
                "final_live_tensor_count": 0,
                "final_live_tensor_unique_storage_bytes": 0,
                "process_reclaimed": False,
                "identity_pass": False,
                "evidence_error": f"{type(error).__name__}: {error}",
            }
            for run_id, identity in expected.items()
            if identity["kind"] == "sentinel"
        ]

    n32_a = [row for row in run_metrics if row["resolution"] == 32 and row["variant"] == "A"]
    n32_b = [row for row in run_metrics if row["resolution"] == 32 and row["variant"] == "B"]
    n32_c = [row for row in run_metrics if row["resolution"] == 32 and row["variant"] == "C"]
    completion_a = sum(bool(row["completion_pass"]) for row in n32_a)
    completion_b = sum(bool(row["completion_pass"]) for row in n32_b)
    completion_c = sum(bool(row["completion_pass"]) for row in n32_c)
    n16_completion_count = sum(
        bool(row["completion_pass"])
        for row in run_metrics
        if row["resolution"] == 16
    )
    all_n16_complete = n16_completion_count == int(
        qualification["all_n16_variants_required_for_scale_control"]
    )
    numerical_pass = bool(run_metrics) and all(
        bool(row["numerical_pass"]) for row in run_metrics
    )
    finite_resource_pass = bool(run_metrics) and all(
        bool(row["system_memory_pressure_pass"])
        and bool(row["rss_limit_pass"])
        for row in run_metrics
    )
    raw_provenance_pass = bool(run_metrics) and all(
        bool(row["provenance_pass"])
        and bool(row["sampling_coverage_pass"])
        for row in run_metrics
    )
    provenance_pass = bool(
        raw_provenance_pass
        and schedule_contract_pass
        and campaign_order_pass
        and freeze_pass
        and source_tree_clean
    )
    e_pass = bool(run_metrics) and all(
        bool(row["rss_quartile_limit_pass"]) for row in run_metrics
    )
    f_pass = bool(run_metrics) and all(
        bool(row["rss_slope_limit_pass"]) for row in run_metrics
    )

    variant_growth = {
        (int(row["resolution"]), str(row["variant"])): row
        for row in variant_rows
    }
    tensor_growth_evidence_complete = True
    for row in variant_rows:
        required_trusted = (
            int(qualification["n32_variant_c_completed_required"])
            if int(row["resolution"]) == 32 and row["variant"] == "C"
            else int(configuration["repetitions"]["qualifying_repeats_per_resolution_variant"])
        )
        tensor_growth_evidence_complete = bool(
            tensor_growth_evidence_complete
            and int(row["trusted_solver_repeat_count"]) >= required_trusted
        )
    g_pass = bool(
        tensor_growth_evidence_complete
        and all(
            int(row["tensor_count_positive_repeat_count"]) < 2
            and int(row["tensor_bytes_positive_repeat_count"]) < 2
            for row in variant_rows
        )
    )

    overhead_rows: list[dict[str, Any]] = []
    h_pass = True
    for resolution in (16, 32):
        a_summary = variant_growth[(resolution, "A")]
        b_summary = variant_growth[(resolution, "B")]
        a_raw = a_summary.get("median_final_quartile_rss_bytes")
        b_raw = b_summary.get("median_final_quartile_rss_bytes")
        evidence_complete = bool(
            int(a_summary["trusted_solver_repeat_count"]) == 3
            and int(b_summary["trusted_solver_repeat_count"]) == 3
            and a_raw is not None
            and b_raw is not None
        )
        if evidence_complete:
            a_value = float(a_raw)
            b_value = float(b_raw)
            extra: float | None = max(0.0, b_value - a_value)
            fraction: float | None = extra / a_value
            passed = bool(
                extra <= float(qualification["variant_b_extra_memory_maximum_bytes"])
                and fraction
                <= float(qualification["variant_b_extra_memory_fraction_of_a_maximum"])
            )
        else:
            a_value = a_raw
            b_value = b_raw
            extra = None
            fraction = None
            passed = False
        h_pass = h_pass and passed
        overhead_rows.append(
            {
                "resolution": resolution,
                "evidence_complete": evidence_complete,
                "a_median_final_quartile_rss_bytes": a_value,
                "b_median_final_quartile_rss_bytes": b_value,
                "b_minus_a_bounded_extra_bytes": extra,
                "b_minus_a_fraction_of_a": fraction,
                "pass": passed,
            }
        )

    archive_rows: list[dict[str, Any]] = []
    for row in run_metrics:
        try:
            archive_rows.append(_archive_run_assessment(row, configuration))
        except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
            archive_rows.append(
                {
                    "run_id": row["run_id"],
                    "resolution": row["resolution"],
                    "repeat": row["repeat"],
                    "variant": row["variant"],
                    "solver_completed": bool(row.get("solver_completed")),
                    "archive_only_failure": False,
                    "archive_localized": False,
                    "archive_overhead_bounded": False,
                    "archive_contract_detail": (
                        f"{type(error).__name__}: {error}"
                    ),
                }
            )
    archive_localized = bool(archive_rows) and all(
        bool(row["archive_localized"]) for row in archive_rows
    )
    archive_overhead_bounded = bool(archive_rows) and all(
        bool(row["archive_overhead_bounded"]) for row in archive_rows
    )
    n32_c_archive_only_failures = sum(
        bool(row["archive_only_failure"])
        for row in archive_rows
        if int(row["resolution"]) == 32 and row["variant"] == "C"
    )
    if n32_c_archive_only_failures > 1:
        archive_localized = False

    reclaimed_count = 0
    for run_id in expected:
        path = EXIT_ROOT / f"{run_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            reclaimed_count += int(value.get("process_absent_after_wait") is True)
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    reclamation_pass = reclaimed_count == len(expected)

    fix_configuration = configuration.get("retention_fix_evidence", {})
    retention_fix_applied = bool(fix_configuration.get("applied", False))
    retention_fix_contract_pass = not retention_fix_applied
    if retention_fix_applied:
        required_fix_fields = (
            "permitted_class",
            "failing_reproducer_path",
            "regression_test_path",
            "before_curve_path",
            "after_curve_path",
            "separate_commit",
        )
        values_present = all(
            str(fix_configuration.get(key, "")).strip() for key in required_fix_fields
        )
        paths_valid = values_present and all(
            (PROJECT_ROOT / str(fix_configuration[key])).resolve().is_relative_to(PROJECT_ROOT)
            and (PROJECT_ROOT / str(fix_configuration[key])).is_file()
            for key in required_fix_fields[1:5]
        )
        commit_valid = False
        if values_present:
            completed = subprocess.run(
                ("git", "cat-file", "-e", f"{fix_configuration['separate_commit']}^{{commit}}"),
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
            )
            commit_valid = completed.returncode == 0
        retention_fix_contract_pass = bool(paths_valid and commit_valid)
        provenance_pass = provenance_pass and retention_fix_contract_pass

    qualifying_count = len(run_metrics)
    gates = [
        _gate("A", "n32_variant_a_required_complete", completion_a == int(qualification["n32_variant_a_completed_required"]), completion_a, qualification["n32_variant_a_completed_required"], "results/run_summaries/*.json"),
        _gate("B", "n32_variant_b_required_complete", completion_b == int(qualification["n32_variant_b_completed_required"]), completion_b, qualification["n32_variant_b_completed_required"], "results/run_summaries/*.json"),
        _gate("C", "n32_variant_c_minimum_complete", completion_c >= int(qualification["n32_variant_c_completed_required"]), completion_c, f">={qualification['n32_variant_c_completed_required']}", "results/run_summaries/*.json"),
        _gate("D", "all_numerical_topology_and_system_resource_gates", numerical_pass and finite_resource_pass, {"numerical": numerical_pass, "resource": finite_resource_pass}, {"numerical": True, "resource": True}, "results/numerical_samples/*.csv + results/memory_samples/*.jsonl"),
        _gate("E", "postwarmup_quartile_rss_bounds", e_pass, f"{sum(bool(row['rss_quartile_limit_pass']) for row in run_metrics)}/{qualifying_count}", f"{qualifying_count}/{qualifying_count}", "results/memory_run_metrics.csv"),
        _gate("F", "postwarmup_rss_slope_bounds", f_pass, f"{sum(bool(row['rss_slope_limit_pass']) for row in run_metrics)}/{qualifying_count}", f"{qualifying_count}/{qualifying_count}", "results/memory_run_metrics.csv"),
        _gate("G", "live_tensor_count_and_bytes_not_repeatedly_positive", g_pass, [{"resolution": row["resolution"], "variant": row["variant"], "trusted": row["trusted_solver_repeat_count"], "count_positive": row["tensor_count_positive_repeat_count"], "bytes_positive": row["tensor_bytes_positive_repeat_count"]} for row in variant_rows], "required trusted repeats and fewer than 2 positive repeats", "results/variant_summary.csv"),
        _gate("H", "variant_b_extra_memory_bounded", h_pass, overhead_rows, {"bytes": qualification["variant_b_extra_memory_maximum_bytes"], "fraction": qualification["variant_b_extra_memory_fraction_of_a_maximum"]}, "results/diagnostics_overhead.csv"),
        _gate("I", "variant_c_archive_localized_and_bounded", archive_localized and archive_overhead_bounded, {"localized": archive_localized, "bounded": archive_overhead_bounded, "n32_archive_only_failures": n32_c_archive_only_failures}, {"localized": True, "bounded": True, "archive_only_failures": "<=1"}, "results/archive_assessment.csv + snapshots/*.npz"),
        _gate("J", "all_child_processes_reclaimed", reclamation_pass, f"{reclaimed_count}/{len(expected)}", f"{len(expected)}/{len(expected)}", "results/process_exit/*.json"),
        _gate("P", "freeze_provenance_sampling_order_and_source_complete", provenance_pass, {"raw_worker_provenance": raw_provenance_pass, "schedule": schedule_contract_pass, "campaign_order": campaign_order_observed, "freeze": freeze_facts if freeze_pass else freeze_error, "source_tree_clean": source_tree_clean, "source_changes": source_changes, "retention_fix_contract": retention_fix_contract_pass}, True, "freeze manifest + run configs + campaign index + memory traces + git status"),
        _gate("N16", "all_n16_scale_controls_complete", all_n16_complete, n16_completion_count, qualification["all_n16_variants_required_for_scale_control"], "results/run_summaries/*.json"),
        _gate("REG", "frozen_first_four_state_regression", regression_pass, regression_observed, {"rows": 40, "bitwise": 40, "tolerance": 40}, "results/numerical_samples/stage01dr_frozen_regression_*.csv"),
        _gate("SENTINEL", "no_grad_vs_grad_graph_sentinel", sentinel_pass, sentinel_rows, "no_grad graph=0; grad-enabled graph>0; both reclaimed", "results/graph_sentinel_summary.csv"),
    ]

    confirmed_linear, ambiguous_growth = _classify_repeated_n32_growth(
        variant_rows
    )
    hard_complete = all(
        bool(row["passed"]) for row in gates if row["gate"] not in {"H", "I"}
    )
    isolated_overhead_only = bool(
        hard_complete
        and archive_localized
        and (not h_pass or not archive_overhead_bounded)
    )
    status = _derive_resource_status(
        confirmed_linear=confirmed_linear,
        hard_complete=hard_complete,
        ambiguous_growth=ambiguous_growth,
        archive_localized=archive_localized,
        isolated_overhead_only=isolated_overhead_only,
        retention_fix_applied=retention_fix_applied,
        retention_fix_contract_pass=retention_fix_contract_pass,
    )
    gates.append(
        {
            **_gate(
                "STATUS",
                "decision_valid_and_unique",
                True,
                status,
                sorted(ALLOWED_STATUSES),
                "configs/preregistered_memory_diagnosis.yml",
                detail=json.dumps(
                    {
                        "confirmed_linear": confirmed_linear,
                        "ambiguous_growth": ambiguous_growth,
                        "hard_complete": hard_complete,
                        "isolated_overhead_only": isolated_overhead_only,
                        "retention_fix_applied": retention_fix_applied,
                    },
                    sort_keys=True,
                ),
            ),
            "severity": "STATUS",
        }
    )

    _preflight_analysis_outputs()
    figures = _save_figures(run_metrics, sentinel_rows)
    _atomic_csv(RESULTS_ROOT / "memory_run_metrics.csv", run_metrics)
    _atomic_csv(RESULTS_ROOT / "variant_summary.csv", variant_rows)
    _atomic_csv(RESULTS_ROOT / "diagnostics_overhead.csv", overhead_rows)
    _atomic_csv(RESULTS_ROOT / "archive_assessment.csv", archive_rows)
    _atomic_csv(RESULTS_ROOT / "graph_sentinel_summary.csv", sentinel_rows)
    _atomic_csv(RESULTS_ROOT / "resource_gate_evidence.csv", gates)
    _atomic_text(RESULTS_ROOT / "stage01dr_resource_status.txt", status + "\n")
    analysis_summary = {
        "schema_version": "sph-pio-poc.stage01dr.analysis-summary.v1",
        "status": status,
        "old_stage01d_status": "V2_FAIL",
        "config_sha256": config_hash,
        "git_hash": git_hash,
        "qualifying_run_count": len(run_metrics),
        "evaluable_qualifying_run_count": sum(bool(row["evaluable"]) for row in run_metrics),
        "all_worker_count": len(expected),
        "confirmed_linear": confirmed_linear,
        "ambiguous_growth": ambiguous_growth,
        "hard_complete": hard_complete,
        "variant_b_overhead_pass": h_pass,
        "archive_localized": archive_localized,
        "archive_overhead_bounded": archive_overhead_bounded,
        "numeric_regression_pass": regression_pass,
        "graph_sentinel_pass": sentinel_pass,
        "process_reclamation_pass": reclamation_pass,
        "freeze_pass": freeze_pass,
        "campaign_order_pass": campaign_order_pass,
        "source_tree_clean": source_tree_clean,
        "retention_fix_applied": retention_fix_applied,
        "retention_fix_contract_pass": retention_fix_contract_pass,
        "figures": figures,
    }
    _atomic_json(RESULTS_ROOT / "analysis_summary.json", analysis_summary)
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
