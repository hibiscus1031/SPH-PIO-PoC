"""Write immutable current-config gates for Stage 01D time and space phases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


EXPERIMENT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_ROOT.parents[1]
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

import run_dynamic_verification as runner  # noqa: E402


RESULTS_ROOT = EXPERIMENT_ROOT / "results"
METRICS = (
    "velocity_relative_l2",
    "modal_amplitude_error",
    "kinetic_energy_error",
)


def _read_samples(spec: runner.RunSpec) -> list[dict[str, str]]:
    path = runner._resolved_paths(spec.run_id)["sample"]
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"empty sample evidence: {path}")
    return rows


def _state(spec: runner.RunSpec) -> dict[str, np.ndarray]:
    path = runner._resolved_paths(spec.run_id)["state"]
    with np.load(path, allow_pickle=False) as archive:
        return {
            key: np.asarray(archive[key])
            for key in ("steps", "times", "velocities")
        }


def _endpoint(spec: runner.RunSpec) -> dict[str, float]:
    rows = _read_samples(spec)
    final = rows[-1]
    if int(final["step"]) != spec.steps:
        raise RuntimeError(f"incomplete endpoint: {spec.run_id}")
    if not math.isclose(
        float(final["time"]),
        spec.t_final,
        rel_tol=0.0,
        abs_tol=2.0e-14,
    ):
        raise RuntimeError(f"wrong endpoint time: {spec.run_id}")
    values = {metric: float(final[metric]) for metric in METRICS}
    if not all(math.isfinite(value) and value >= 0.0 for value in values.values()):
        raise RuntimeError(f"nonfinite endpoint metric: {spec.run_id}")
    return values


def _provenance(
    *,
    phase: str,
    specs: list[runner.RunSpec],
) -> dict[str, Any]:
    config_hash = hashlib.sha256(runner.CONFIG_PATH.read_bytes()).hexdigest()
    git_hash = runner._git_hash()
    if not all(runner._already_complete(spec, runner._load_configuration()) for spec in specs):
        raise RuntimeError(
            f"{phase} gate requires complete current-config/current-commit runs"
        )
    return {
        "stage": "01D",
        "phase": phase,
        "git_hash": git_hash,
        "master_preregistration_sha256": config_hash,
        "run_ids": [spec.run_id for spec in specs],
        "run_config_sha256": {
            spec.run_id: next(
                row["config_hash"]
                for row in runner._read_summary_rows()
                if row["run_id"] == spec.run_id
            )
            for spec in specs
        },
    }


def evaluate_time(configuration: dict[str, Any]) -> dict[str, Any]:
    specs = runner._specs_for_phase("time", configuration)
    specs.sort(key=lambda spec: spec.dt, reverse=True)
    result = _provenance(phase="time", specs=specs)
    endpoints = {spec.run_id: _endpoint(spec) for spec in specs}
    coarse = endpoints[specs[0].run_id]
    fine = endpoints[specs[-1].run_id]
    analytic_ratios = {
        metric: (
            fine[metric] / coarse[metric]
            if coarse[metric] > 0.0
            else None
        )
        for metric in METRICS
    }
    analytic_limit = float(
        configuration["time_convergence"]["credible_trend"][
            "analytic_endpoint_ratio_maximum_for_at_least_one_metric"
        ]
    )
    analytic_pass = any(
        value is not None and value <= analytic_limit
        for value in analytic_ratios.values()
    )

    states = {spec.run_id: _state(spec) for spec in specs}
    common_times = states[specs[0].run_id]["times"]
    common_time_exact = all(
        np.array_equal(states[spec.run_id]["times"], common_times)
        for spec in specs[1:]
    )
    expected_times = np.asarray(
        [step * specs[0].dt for step in runner._sample_steps(specs[0])],
        dtype=np.float64,
    )
    common_time_exact = bool(
        common_time_exact and np.array_equal(common_times, expected_times)
    )
    pair_rms: list[dict[str, Any]] = []
    for coarse_spec, fine_spec in zip(specs, specs[1:]):
        coarse_velocity = states[coarse_spec.run_id]["velocities"]
        fine_velocity = states[fine_spec.run_id]["velocities"]
        complete = bool(
            coarse_velocity.shape == fine_velocity.shape
            and np.isfinite(coarse_velocity).all()
            and np.isfinite(fine_velocity).all()
            and common_time_exact
        )
        trajectory_rms = None
        if complete:
            difference = coarse_velocity - fine_velocity
            per_time = np.sqrt(np.mean(np.sum(difference**2, axis=-1), axis=-1))
            trajectory_rms = math.sqrt(float(np.mean(per_time**2)))
        pair_rms.append(
            {
                "coarse_run_id": coarse_spec.run_id,
                "fine_run_id": fine_spec.run_id,
                "coarse_dt": coarse_spec.dt,
                "fine_dt": fine_spec.dt,
                "complete": complete,
                "trajectory_rms": trajectory_rms,
            }
        )
    self_ratio = None
    if (
        len(pair_rms) == 3
        and all(row["complete"] for row in pair_rms)
        and pair_rms[0]["trajectory_rms"] is not None
        and float(pair_rms[0]["trajectory_rms"]) > 0.0
    ):
        self_ratio = (
            float(pair_rms[-1]["trajectory_rms"])
            / float(pair_rms[0]["trajectory_rms"])
        )
    self_limit = float(
        configuration["time_convergence"]["credible_trend"][
            "self_convergence_finest_to_coarsest_ratio_maximum"
        ]
    )
    self_pass = self_ratio is not None and self_ratio <= self_limit
    phase_pass = bool(
        common_time_exact
        and all(row["complete"] for row in pair_rms)
        and (analytic_pass or self_pass)
    )
    result.update(
        {
            "endpoint_metrics": endpoints,
            "analytic_finest_to_coarsest_ratios": analytic_ratios,
            "analytic_ratio_limit": analytic_limit,
            "analytic_trend_pass": analytic_pass,
            "common_21_times_bitwise_equal": common_time_exact,
            "self_pair_trajectory_rms": pair_rms,
            "self_finest_to_coarsest_ratio": self_ratio,
            "self_ratio_limit": self_limit,
            "self_trend_pass": self_pass,
            "phase_gate_pass": phase_pass,
            "downstream_allowed": phase_pass,
        }
    )
    return result


def evaluate_space(configuration: dict[str, Any]) -> dict[str, Any]:
    specs = runner._specs_for_phase("space", configuration)
    specs.sort(key=lambda spec: spec.resolution)
    result = _provenance(phase="space", specs=specs)
    endpoints = {spec.run_id: _endpoint(spec) for spec in specs}
    dx = np.asarray([spec.dx for spec in specs], dtype=np.float64)
    metric_rows: dict[str, dict[str, Any]] = {}
    for metric in METRICS:
        errors = np.asarray(
            [endpoints[spec.run_id][metric] for spec in specs],
            dtype=np.float64,
        )
        finite_positive = bool(np.isfinite(errors).all() and np.all(errors > 0.0))
        slope = (
            float(np.polyfit(np.log(dx), np.log(errors), 1)[0])
            if finite_positive
            else None
        )
        metric_rows[metric] = {
            "errors_by_resolution": {
                str(spec.resolution): float(error)
                for spec, error in zip(specs, errors)
            },
            "fitted_log_error_log_dx_slope": slope,
            "strictly_monotone_decreasing": bool(
                finite_positive and np.all(errors[1:] < errors[:-1])
            ),
            "ratio_n32_over_n16": (
                float(errors[-1] / errors[0])
                if finite_positive and errors[0] > 0.0
                else None
            ),
            "finite_positive": finite_positive,
        }
    velocity = metric_rows["velocity_relative_l2"]
    ratio_limit = float(
        configuration["space_convergence"]["primary_trend"][
            "n32_to_n16_velocity_relative_L2_ratio_maximum"
        ]
    )
    all_finite = all(row["finite_positive"] for row in metric_rows.values())
    all_positive_slopes = all(
        row["fitted_log_error_log_dx_slope"] is not None
        and float(row["fitted_log_error_log_dx_slope"]) > 0.0
        for row in metric_rows.values()
    )
    velocity_ratio_pass = bool(
        velocity["ratio_n32_over_n16"] is not None
        and float(velocity["ratio_n32_over_n16"]) <= ratio_limit
    )
    primary_pass = bool(all_finite and all_positive_slopes and velocity_ratio_pass)
    nonworsening = bool(
        all_finite
        and all(
            row["fitted_log_error_log_dx_slope"] is not None
            and float(row["fitted_log_error_log_dx_slope"]) >= 0.0
            for row in metric_rows.values()
        )
        and velocity["ratio_n32_over_n16"] is not None
        and float(velocity["ratio_n32_over_n16"]) < 1.0
    )
    plateau = bool(nonworsening and not primary_pass)
    qualification = (
        "PASS"
        if primary_pass
        else "CONDITIONAL_PLATEAU"
        if plateau
        else "FAIL"
    )
    result.update(
        {
            "endpoint_metrics": endpoints,
            "metrics": metric_rows,
            "velocity_ratio_limit": ratio_limit,
            "primary_all_selected_slopes_positive": all_positive_slopes,
            "primary_velocity_ratio_pass": velocity_ratio_pass,
            "primary_space_pass": primary_pass,
            "space_plateau_conditional": plateau,
            "qualification": qualification,
            "phase_gate_pass": primary_pass,
            "downstream_allowed": primary_pass or plateau,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("time", "space"), required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    configuration = runner._load_configuration()
    result = (
        evaluate_time(configuration)
        if args.phase == "time"
        else evaluate_space(configuration)
    )
    output = args.output or RESULTS_ROOT / f"{args.phase}_phase_gate.json"
    runner._write_json_once_or_verify(output, result)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if bool(result["downstream_allowed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
