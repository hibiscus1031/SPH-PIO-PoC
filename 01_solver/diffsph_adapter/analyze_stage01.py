#!/usr/bin/env python3
"""Aggregate and plot completed canonical Stage 01 Taylor--Green runs.

The analysis is intentionally independent of diffSPH and PyTorch: it consumes
only the CSV, JSON, and NPZ artifacts written by :mod:`run_tgv`.  Runs whose
stem contains ``pre-reference-fix`` are always excluded.  Wall-time stability
runs are aggregated under a separate role but never enter the six canonical
trend figures or canonical repeat comparisons.  Incomplete, inconsistent, or
non-finite artifacts are reported as skipped.

No values are synthesized.  If no valid canonical run exists, the command
fails before creating or replacing reports or figures.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIRECTORY = PROJECT_ROOT / "06_experiments/stage_01_tgv/raw"
DEFAULT_FIGURES_DIRECTORY = PROJECT_ROOT / "06_experiments/stage_01_tgv/figures"
DEFAULT_REPORTS_DIRECTORY = PROJECT_ROOT / "07_reports"

EXCLUDED_STEM_TOKENS = ("pre-reference-fix",)
NUMERICAL_SUFFIX = "_numerical.csv"

NUMERICAL_REQUIRED_COLUMNS = (
    "backend",
    "dtype",
    "resolution",
    "particle_count",
    "run_id",
    "seed",
    "step",
    "time",
    "dt",
    "velocity_relative_l2",
    "velocity_rmse",
    "total_kinetic_energy",
    "kinetic_energy_relative_error",
    "kinetic_energy_relative_initial",
    "momentum_x",
    "momentum_y",
    "relative_momentum_drift",
    "mean_density",
    "min_density",
    "max_density",
    "relative_density_fluctuation",
    "max_particle_speed",
    "has_nan_or_inf",
    "step_time_seconds",
)
NUMERICAL_FINITE_COLUMNS = (
    "step",
    "time",
    "dt",
    "velocity_relative_l2",
    "velocity_rmse",
    "total_kinetic_energy",
    "kinetic_energy_relative_error",
    "kinetic_energy_relative_initial",
    "momentum_x",
    "momentum_y",
    "relative_momentum_drift",
    "mean_density",
    "min_density",
    "max_density",
    "relative_density_fluctuation",
    "max_particle_speed",
    "step_time_seconds",
)
REPEAT_METRIC_COLUMNS = (
    "velocity_relative_l2",
    "velocity_rmse",
    "total_kinetic_energy",
    "kinetic_energy_relative_error",
    "kinetic_energy_relative_initial",
    "momentum_x",
    "momentum_y",
    "relative_momentum_drift",
    "mean_density",
    "min_density",
    "max_density",
    "relative_density_fluctuation",
    "max_particle_speed",
)
RUNTIME_REQUIRED_COLUMNS = (
    "backend",
    "resolution",
    "particle_count",
    "run_id",
    "record_type",
    "mean_step_seconds",
    "final_state_sha256",
)
TRAJECTORY_REQUIRED_KEYS = (
    "steps",
    "times",
    "positions",
    "velocities",
    "densities",
)


class AnalysisError(RuntimeError):
    """Raised when artifact truth is insufficient for safe aggregation."""


@dataclass(frozen=True)
class RunBundle:
    """Validated artifact set for one completed canonical or stability run."""

    stem: str
    role: str
    backend: str
    resolution: int
    particle_count: int
    run_id: str
    config: Mapping[str, Any]
    config_sha256: str
    numerical: pd.DataFrame
    runtime: pd.DataFrame
    trajectory: Mapping[str, np.ndarray]
    source_hashes: Mapping[str, str]
    final_state_sha256: str
    validation_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class DiscoveryResult:
    """Canonical discovery outcome, including explicit exclusions and errors."""

    runs: tuple[RunBundle, ...]
    excluded: tuple[str, ...]
    invalid: Mapping[str, str]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _sha256_json(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_config_hash(config: Mapping[str, Any]) -> str:
    """Hash repeat-defining metadata while ignoring only the run label."""

    normalized = dict(config)
    normalized.pop("run_id", None)
    return _sha256_json(normalized)


def _trajectory_state_hash(trajectory: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for key in ("positions", "velocities", "densities"):
        digest.update(np.ascontiguousarray(trajectory[key][-1]).tobytes())
    return digest.hexdigest()


def _truthy(series: pd.Series) -> pd.Series:
    """Interpret CSV booleans without treating the string ``"False"`` as true."""

    normalized = series.fillna("").astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "yes", "y"})


def _require_columns(
    frame: pd.DataFrame,
    required: Sequence[str],
    *,
    artifact: str,
) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise AnalysisError(f"{artifact} is missing required columns: {missing}")


def _single_identity(
    frame: pd.DataFrame,
    column: str,
    expected: Any,
    *,
    artifact: str,
) -> None:
    populated = frame[column].dropna()
    if populated.empty:
        raise AnalysisError(f"{artifact} has no populated {column!r}")
    values = populated.astype(str).unique()
    if len(values) != 1 or values[0] != str(expected):
        raise AnalysisError(
            f"{artifact} {column!r} must be {expected!r}; found {values.tolist()}"
        )


def _load_trajectory(path: Path) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            missing = sorted(set(TRAJECTORY_REQUIRED_KEYS) - set(archive.files))
            if missing:
                raise AnalysisError(
                    f"{path.name} is missing trajectory arrays: {missing}"
                )
            return {key: np.asarray(archive[key]) for key in TRAJECTORY_REQUIRED_KEYS}
    except (OSError, ValueError) as exc:
        raise AnalysisError(f"cannot read {path.name}: {exc}") from exc


def _validate_trajectory(
    trajectory: Mapping[str, np.ndarray],
    *,
    particle_count: int,
    expected_last_snapshot_step: int,
    numerical: pd.DataFrame,
    artifact: str,
) -> None:
    steps = trajectory["steps"]
    times = trajectory["times"]
    positions = trajectory["positions"]
    velocities = trajectory["velocities"]
    densities = trajectory["densities"]
    snapshot_count = len(steps)

    if steps.ndim != 1 or times.shape != steps.shape or snapshot_count == 0:
        raise AnalysisError(f"{artifact} has invalid steps/times arrays")
    if positions.shape != (snapshot_count, particle_count, 2):
        raise AnalysisError(
            f"{artifact} positions shape is {positions.shape}; expected "
            f"({snapshot_count}, {particle_count}, 2)"
        )
    if velocities.shape != positions.shape:
        raise AnalysisError(
            f"{artifact} velocity shape {velocities.shape} does not match positions"
        )
    if densities.shape != (snapshot_count, particle_count):
        raise AnalysisError(
            f"{artifact} densities shape is {densities.shape}; expected "
            f"({snapshot_count}, {particle_count})"
        )
    for key, array in trajectory.items():
        if not np.issubdtype(array.dtype, np.number) or not np.isfinite(array).all():
            raise AnalysisError(f"{artifact} array {key!r} contains non-finite data")
    if np.any(np.diff(steps) <= 0) or np.any(np.diff(times) < 0):
        raise AnalysisError(f"{artifact} snapshot steps/times are not monotonic")
    if int(steps[0]) != 0 or int(steps[-1]) != expected_last_snapshot_step:
        raise AnalysisError(
            f"{artifact} ends at snapshot step {int(steps[-1])}, expected "
            f"{expected_last_snapshot_step}"
        )

    numerical_steps = numerical["step"].to_numpy(dtype=np.int64)
    numerical_times = numerical["time"].to_numpy(dtype=np.float64)
    if not np.array_equal(steps.astype(np.int64), numerical_steps):
        raise AnalysisError(f"{artifact} snapshot steps do not match numerical CSV")
    if not np.allclose(times, numerical_times, rtol=1.0e-7, atol=1.0e-10):
        raise AnalysisError(f"{artifact} snapshot times do not match numerical CSV")


def _load_run(numerical_path: Path) -> RunBundle:
    stem = numerical_path.name[: -len(NUMERICAL_SUFFIX)]
    companions = {
        "config": numerical_path.with_name(f"{stem}_config.json"),
        "runtime": numerical_path.with_name(f"{stem}_runtime.csv"),
        "trajectory": numerical_path.with_name(f"{stem}_trajectory.npz"),
    }
    missing = [kind for kind, path in companions.items() if not path.is_file()]
    if missing:
        raise AnalysisError(f"missing companion artifacts: {missing}")

    try:
        config = json.loads(companions["config"].read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read {companions['config'].name}: {exc}") from exc
    if not isinstance(config, dict):
        raise AnalysisError(f"{companions['config'].name} must contain a JSON object")
    required_config = {
        "backend",
        "dtype",
        "resolution",
        "particle_count",
        "run_id",
        "seed",
        "target_dt",
        "total_steps",
        "scheme",
        "kernel",
        "n_h",
        "integration_scheme",
        "package_versions",
        "project_git_hash",
        "diffsph_commit",
        "diffsph_installed_python_tree_sha256",
        "torchcompactradius_installed_python_tree_sha256",
        "pytorch_mps_fallback_env",
    }
    missing_config = sorted(required_config - set(config))
    if missing_config:
        raise AnalysisError(f"config is missing required keys: {missing_config}")
    required_packages = {
        "torch",
        "numpy",
        "scipy",
        "diffSPH",
        "torchCompactRadius",
        "h5py",
        "PyYAML",
    }
    package_versions = config["package_versions"]
    if not isinstance(package_versions, Mapping):
        raise AnalysisError("config package_versions must be a mapping")
    missing_packages = sorted(required_packages - set(package_versions))
    if missing_packages:
        raise AnalysisError(
            f"config package_versions is missing: {missing_packages}"
        )
    if float(config["target_dt"]) <= 0:
        raise AnalysisError("config target_dt must be positive")
    if str(config["pytorch_mps_fallback_env"]) == "1":
        raise AnalysisError("config reports PYTORCH_ENABLE_MPS_FALLBACK=1")

    backend = str(config["backend"]).lower()
    resolution = int(config["resolution"])
    particle_count = int(config["particle_count"])
    run_id = str(config["run_id"])
    role = "stability" if "stability" in run_id.lower() else "canonical"
    expected_stem = f"{backend}_n{resolution}_{run_id}"
    if stem != expected_stem:
        raise AnalysisError(
            f"artifact stem {stem!r} does not match config identity {expected_stem!r}"
        )
    if backend not in {"cpu", "mps"}:
        raise AnalysisError(f"unsupported Stage 01 backend {backend!r}")
    if particle_count != resolution**2:
        raise AnalysisError(
            f"particle_count={particle_count} does not equal resolution^2"
        )

    try:
        numerical = pd.read_csv(numerical_path)
        runtime = pd.read_csv(companions["runtime"])
    except (OSError, pd.errors.ParserError) as exc:
        raise AnalysisError(f"cannot read run CSV: {exc}") from exc
    if numerical.empty or runtime.empty:
        raise AnalysisError("Stage 01 CSV artifacts must be non-empty")
    _require_columns(
        numerical, NUMERICAL_REQUIRED_COLUMNS, artifact=numerical_path.name
    )
    _require_columns(
        runtime, RUNTIME_REQUIRED_COLUMNS, artifact=companions["runtime"].name
    )

    for frame, artifact in (
        (numerical, numerical_path.name),
        (runtime, companions["runtime"].name),
    ):
        _single_identity(frame, "backend", backend, artifact=artifact)
        _single_identity(frame, "resolution", resolution, artifact=artifact)
        _single_identity(frame, "particle_count", particle_count, artifact=artifact)
        _single_identity(frame, "run_id", run_id, artifact=artifact)

    for column in NUMERICAL_FINITE_COLUMNS:
        try:
            numerical[column] = pd.to_numeric(numerical[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise AnalysisError(
                f"{numerical_path.name} column {column!r} is not numeric"
            ) from exc
        if not np.isfinite(numerical[column].to_numpy(dtype=np.float64)).all():
            raise AnalysisError(
                f"{numerical_path.name} column {column!r} contains NaN/Inf"
            )
    if _truthy(numerical["has_nan_or_inf"]).any():
        raise AnalysisError(f"{numerical_path.name} records NaN/Inf state")
    if (numerical["step"] < 0).any() or not numerical["step"].is_monotonic_increasing:
        raise AnalysisError(f"{numerical_path.name} has invalid step ordering")
    if numerical["step"].duplicated().any():
        raise AnalysisError(f"{numerical_path.name} contains duplicate metric steps")

    configured_steps = int(config["total_steps"])
    last_numerical_step = int(numerical.iloc[-1]["step"])
    if int(numerical.iloc[0]["step"]) != 0:
        raise AnalysisError(f"{numerical_path.name} does not begin at step zero")
    if role == "canonical" and last_numerical_step != configured_steps:
        raise AnalysisError(
            f"{numerical_path.name} ends at step "
            f"{last_numerical_step}, expected {configured_steps}"
        )

    summaries = runtime[runtime["record_type"].astype(str) == "summary"]
    if len(summaries) != 1:
        raise AnalysisError(
            f"{companions['runtime'].name} must contain exactly one summary row"
        )
    summary = summaries.iloc[0]
    if "measured_steps" not in runtime.columns or pd.isna(summary["measured_steps"]):
        raise AnalysisError("runtime summary lacks measured_steps")
    measured_steps = int(summary["measured_steps"])
    if role == "canonical" and measured_steps != configured_steps:
        raise AnalysisError(
            f"runtime measured_steps={summary['measured_steps']}, "
            f"expected {configured_steps}"
        )
    if role == "stability" and measured_steps < last_numerical_step:
        raise AnalysisError(
            f"stability measured_steps={measured_steps} is less than the last "
            f"recorded numerical step {last_numerical_step}"
        )
    for failure_column in ("pytorch_mps_fallback", "unsupported_operator"):
        if failure_column in runtime.columns and _truthy(
            pd.Series([summary[failure_column]])
        ).iloc[0]:
            raise AnalysisError(f"runtime summary reports {failure_column}=True")
    if "first_nonfinite_step" in runtime.columns and not pd.isna(
        summary["first_nonfinite_step"]
    ):
        raise AnalysisError("runtime summary records first_nonfinite_step")
    final_hash = str(summary["final_state_sha256"]).strip().lower()
    if len(final_hash) != 64 or any(
        character not in "0123456789abcdef" for character in final_hash
    ):
        raise AnalysisError("runtime summary has an invalid final_state_sha256")

    validation_metadata: dict[str, Any] = {}
    if role == "stability":
        stability_required = {
            "sustain_target_seconds",
            "total_wall_seconds",
            "first_nonfinite_step",
            "pytorch_mps_fallback",
            "unsupported_operator",
            "segment_end_seconds",
            "segment_steps",
        }
        missing_stability = sorted(stability_required - set(runtime.columns))
        if missing_stability:
            raise AnalysisError(
                "stability runtime is missing required columns: "
                f"{missing_stability}"
            )
        try:
            sustain_target = float(summary["sustain_target_seconds"])
            total_wall = float(summary["total_wall_seconds"])
        except (TypeError, ValueError) as exc:
            raise AnalysisError(
                "stability sustain_target_seconds and total_wall_seconds "
                "must be numeric"
            ) from exc
        if (
            not math.isfinite(sustain_target)
            or sustain_target <= 0
            or not math.isfinite(total_wall)
            or total_wall <= 0
        ):
            raise AnalysisError(
                "stability sustain target and total wall time must be finite "
                "and positive"
            )
        if total_wall + 1.0e-9 < sustain_target:
            raise AnalysisError(
                f"stability wall time {total_wall} s did not reach target "
                f"{sustain_target} s"
            )

        segments = runtime[runtime["record_type"].astype(str) == "segment"].copy()
        if segments.empty:
            raise AnalysisError("stability runtime has no segment rows")
        for column in ("segment_end_seconds", "segment_steps"):
            try:
                segments[column] = pd.to_numeric(
                    segments[column], errors="raise"
                )
            except (TypeError, ValueError) as exc:
                raise AnalysisError(
                    f"stability segment column {column!r} is not numeric"
                ) from exc
            if not np.isfinite(
                segments[column].to_numpy(dtype=np.float64)
            ).all():
                raise AnalysisError(
                    f"stability segment column {column!r} contains NaN/Inf"
                )
        segment_ends = segments["segment_end_seconds"].to_numpy(dtype=np.float64)
        segment_steps = segments["segment_steps"].to_numpy(dtype=np.float64)
        if (
            np.any(np.diff(segment_ends) <= 0)
            or segment_ends[0] <= 0
            or segment_ends[-1] > total_wall + 1.0e-6
        ):
            raise AnalysisError(
                "stability segment_end_seconds must increase within total wall time"
            )
        if np.any(segment_steps <= 0) or not np.allclose(
            segment_steps, np.round(segment_steps), rtol=0.0, atol=0.0
        ):
            raise AnalysisError(
                "stability segment_steps must be positive integers"
            )
        if int(np.sum(segment_steps)) != measured_steps:
            raise AnalysisError(
                "stability segment step sum does not equal measured_steps: "
                f"{int(np.sum(segment_steps))} != {measured_steps}"
            )
        validation_metadata = {
            "analysis_stability_configured_steps": configured_steps,
            "analysis_stability_measured_steps": measured_steps,
            "analysis_stability_last_numerical_step": last_numerical_step,
            "analysis_stability_sustain_target_seconds": sustain_target,
            "analysis_stability_total_wall_seconds": total_wall,
            "analysis_stability_wall_overrun_seconds": (
                total_wall - sustain_target
            ),
            "analysis_stability_target_met": True,
            "analysis_stability_segment_count": len(segments),
            "analysis_stability_segment_step_sum": int(np.sum(segment_steps)),
        }

    trajectory = _load_trajectory(companions["trajectory"])
    _validate_trajectory(
        trajectory,
        particle_count=particle_count,
        expected_last_snapshot_step=last_numerical_step,
        numerical=numerical,
        artifact=companions["trajectory"].name,
    )
    if role == "canonical":
        calculated_final_hash = _trajectory_state_hash(trajectory)
        if calculated_final_hash != final_hash:
            raise AnalysisError(
                "trajectory final-state hash does not match runtime summary: "
                f"{calculated_final_hash} != {final_hash}"
            )

    return RunBundle(
        stem=stem,
        role=role,
        backend=backend,
        resolution=resolution,
        particle_count=particle_count,
        run_id=run_id,
        config=config,
        config_sha256=_normalized_config_hash(config),
        numerical=numerical,
        runtime=runtime,
        trajectory=trajectory,
        source_hashes={
            "config": _sha256_file(companions["config"]),
            "numerical": _sha256_file(numerical_path),
            "runtime": _sha256_file(companions["runtime"]),
            "trajectory": _sha256_file(companions["trajectory"]),
        },
        final_state_sha256=final_hash,
        validation_metadata=validation_metadata,
    )


def discover_runs(raw_directory: Path) -> DiscoveryResult:
    """Discover and validate canonical and wall-time stability artifacts."""

    raw_directory = Path(raw_directory)
    if not raw_directory.is_dir():
        raise AnalysisError(f"raw directory does not exist: {raw_directory}")

    runs: list[RunBundle] = []
    excluded: list[str] = []
    invalid: dict[str, str] = {}
    for path in sorted(raw_directory.glob(f"*{NUMERICAL_SUFFIX}")):
        stem = path.name[: -len(NUMERICAL_SUFFIX)]
        if any(token in stem.lower() for token in EXCLUDED_STEM_TOKENS):
            excluded.append(stem)
            continue
        try:
            runs.append(_load_run(path))
        except AnalysisError as exc:
            invalid[stem] = str(exc)
    runs.sort(key=lambda run: (run.backend, run.resolution, run.run_id))
    return DiscoveryResult(tuple(runs), tuple(excluded), invalid)


def _repeat_audit(
    runs: Sequence[RunBundle],
    *,
    rtol: float,
    atol: float,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[RunBundle]] = {}
    for run in runs:
        groups.setdefault(run.config_sha256, []).append(run)

    result: dict[str, dict[str, Any]] = {}
    for config_hash, group in groups.items():
        group.sort(key=lambda run: run.run_id)
        repeat_count = len(group)
        audit: dict[str, Any] = {
            "analysis_repeat_group_sha256": config_hash,
            "analysis_repeat_count": repeat_count,
            "analysis_repeat_status": "NO_REPEAT",
            "analysis_repeat_time_grid_match": "",
            "analysis_repeat_final_state_hash_match": "",
            "analysis_repeat_metrics_within_tolerance": "",
            "analysis_repeat_max_abs_metric_difference": "",
            "analysis_repeat_mean_step_seconds_range": "",
            "analysis_repeat_mean_step_seconds_relative_range": "",
        }
        for metric in REPEAT_METRIC_COLUMNS:
            audit[f"analysis_repeat_max_abs_diff_{metric}"] = ""

        if repeat_count > 1:
            baseline = group[0].numerical
            baseline_steps = baseline["step"].to_numpy(dtype=np.int64)
            baseline_times = baseline["time"].to_numpy(dtype=np.float64)
            time_grid_match = all(
                np.array_equal(
                    candidate.numerical["step"].to_numpy(dtype=np.int64),
                    baseline_steps,
                )
                and np.allclose(
                    candidate.numerical["time"].to_numpy(dtype=np.float64),
                    baseline_times,
                    rtol=rtol,
                    atol=atol,
                )
                for candidate in group[1:]
            )
            metric_differences: dict[str, float] = {}
            metrics_within_tolerance = bool(time_grid_match)
            if time_grid_match:
                for metric in REPEAT_METRIC_COLUMNS:
                    stack = np.stack(
                        [
                            candidate.numerical[metric].to_numpy(dtype=np.float64)
                            for candidate in group
                        ]
                    )
                    difference = float(np.max(np.ptp(stack, axis=0)))
                    metric_differences[metric] = difference
                    metrics_within_tolerance = metrics_within_tolerance and all(
                        np.allclose(
                            candidate.numerical[metric].to_numpy(dtype=np.float64),
                            stack[0],
                            rtol=rtol,
                            atol=atol,
                        )
                        for candidate in group[1:]
                    )
            else:
                metric_differences = {
                    metric: math.nan for metric in REPEAT_METRIC_COLUMNS
                }
                metrics_within_tolerance = False

            final_hash_match = len(
                {candidate.final_state_sha256 for candidate in group}
            ) == 1
            mean_times = [
                float(
                    candidate.runtime[
                        candidate.runtime["record_type"].astype(str) == "summary"
                    ].iloc[0]["mean_step_seconds"]
                )
                for candidate in group
            ]
            runtime_range = max(mean_times) - min(mean_times)
            runtime_mean = sum(mean_times) / len(mean_times)
            relative_runtime_range = (
                runtime_range / abs(runtime_mean)
                if runtime_mean != 0
                else (0.0 if runtime_range == 0 else math.inf)
            )
            overall_metric_difference = (
                max(metric_differences.values())
                if time_grid_match
                else math.nan
            )
            if final_hash_match and metrics_within_tolerance:
                status = "EXACT_STATE_HASH_AND_METRICS_MATCH"
            elif metrics_within_tolerance:
                status = "METRICS_TOLERANCE_MATCH_STATE_HASH_DIFFERS"
            else:
                status = "REPEAT_DIFFERENCE"
            audit.update(
                {
                    "analysis_repeat_status": status,
                    "analysis_repeat_time_grid_match": time_grid_match,
                    "analysis_repeat_final_state_hash_match": final_hash_match,
                    "analysis_repeat_metrics_within_tolerance": (
                        metrics_within_tolerance
                    ),
                    "analysis_repeat_max_abs_metric_difference": (
                        overall_metric_difference
                    ),
                    "analysis_repeat_mean_step_seconds_range": runtime_range,
                    "analysis_repeat_mean_step_seconds_relative_range": (
                        relative_runtime_range
                    ),
                }
            )
            for metric, difference in metric_differences.items():
                audit[f"analysis_repeat_max_abs_diff_{metric}"] = difference

        for run in group:
            result[run.stem] = dict(audit)
    return result


def build_aggregate_frames(
    runs: Sequence[RunBundle],
    *,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build aggregate numerical/runtime frames with provenance and audit."""

    if not runs:
        raise AnalysisError("cannot aggregate an empty run collection")
    canonical_runs = [run for run in runs if run.role == "canonical"]
    repeat_audit = _repeat_audit(canonical_runs, rtol=rtol, atol=atol)
    numerical_frames: list[pd.DataFrame] = []
    runtime_frames: list[pd.DataFrame] = []
    for run in runs:
        provenance = {
            "analysis_role": run.role,
            "analysis_source_stem": run.stem,
            "analysis_config_sha256": run.config_sha256,
            "analysis_source_config_sha256": run.source_hashes["config"],
            "analysis_source_numerical_sha256": run.source_hashes["numerical"],
            "analysis_source_runtime_sha256": run.source_hashes["runtime"],
            "analysis_source_trajectory_sha256": run.source_hashes["trajectory"],
        }
        numerical = run.numerical.copy()
        runtime = run.runtime.copy()
        for key, value in provenance.items():
            numerical[key] = value
            runtime[key] = value
        for key, value in run.validation_metadata.items():
            numerical[key] = value
            runtime[key] = value
        run_repeat_audit = repeat_audit.get(
            run.stem,
            {
                "analysis_repeat_group_sha256": "",
                "analysis_repeat_count": "",
                "analysis_repeat_status": "NOT_APPLICABLE_STABILITY",
                "analysis_repeat_time_grid_match": "",
                "analysis_repeat_final_state_hash_match": "",
                "analysis_repeat_metrics_within_tolerance": "",
                "analysis_repeat_max_abs_metric_difference": "",
                "analysis_repeat_mean_step_seconds_range": "",
                "analysis_repeat_mean_step_seconds_relative_range": "",
                **{
                    f"analysis_repeat_max_abs_diff_{metric}": ""
                    for metric in REPEAT_METRIC_COLUMNS
                },
            },
        )
        for key, value in run_repeat_audit.items():
            runtime[key] = value
        numerical_frames.append(numerical)
        runtime_frames.append(runtime)

    numerical_result = pd.concat(numerical_frames, ignore_index=True, sort=False)
    numerical_result = numerical_result.sort_values(
        ["backend", "resolution", "run_id", "step"],
        kind="stable",
    ).reset_index(drop=True)
    runtime_result = pd.concat(runtime_frames, ignore_index=True, sort=False)
    if "segment_end_seconds" not in runtime_result.columns:
        runtime_result["segment_end_seconds"] = np.nan
    runtime_result["_record_order"] = (
        runtime_result["record_type"].astype(str).ne("summary").astype(int)
    )
    runtime_result = (
        runtime_result.sort_values(
            ["backend", "resolution", "run_id", "_record_order", "segment_end_seconds"],
            kind="stable",
            na_position="first",
        )
        .drop(columns="_record_order")
        .reset_index(drop=True)
    )
    return numerical_result, runtime_result


def _run_label(run: RunBundle) -> str:
    return f"{run.backend.upper()} {run.resolution}×{run.resolution} {run.run_id}"


def _plot_curve_pair(
    runs: Sequence[RunBundle],
    *,
    columns: tuple[str, str],
    labels: tuple[str, str],
    title: str,
    output: Path,
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), sharex=False)
    for run in runs:
        time = run.numerical["time"]
        label = _run_label(run)
        axes[0].plot(time, run.numerical[columns[0]], label=label, linewidth=1.4)
        axes[1].plot(time, run.numerical[columns[1]], label=label, linewidth=1.4)
    for axis, ylabel in zip(axes, labels):
        axis.set_xlabel("Simulation time")
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.25)
    axes[0].legend(fontsize=7)
    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight", format="png")
    plt.close(figure)


def _plot_single_curve(
    runs: Sequence[RunBundle],
    *,
    column: str,
    ylabel: str,
    title: str,
    output: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    for run in runs:
        axis.plot(
            run.numerical["time"],
            run.numerical[column],
            label=_run_label(run),
            linewidth=1.4,
        )
    axis.set_xlabel("Simulation time")
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight", format="png")
    plt.close(figure)


def _plot_runtime(runs: Sequence[RunBundle], output: Path) -> None:
    records: list[dict[str, Any]] = []
    for run in runs:
        summary = run.runtime[
            run.runtime["record_type"].astype(str) == "summary"
        ].iloc[0]
        records.append(
            {
                "backend": run.backend,
                "particle_count": run.particle_count,
                "run_id": run.run_id,
                "mean_step_seconds": float(summary["mean_step_seconds"]),
            }
        )
    data = pd.DataFrame(records)
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    for backend, backend_data in data.groupby("backend", sort=True):
        aggregate = (
            backend_data.groupby("particle_count")["mean_step_seconds"]
            .agg(["mean", "min", "max"])
            .sort_index()
        )
        x = aggregate.index.to_numpy(dtype=float)
        mean = aggregate["mean"].to_numpy(dtype=float)
        lower = mean - aggregate["min"].to_numpy(dtype=float)
        upper = aggregate["max"].to_numpy(dtype=float) - mean
        axis.errorbar(
            x,
            mean,
            yerr=np.vstack((lower, upper)),
            marker="o",
            capsize=4,
            linewidth=1.5,
            label=f"{backend.upper()} repeat mean/range",
        )
        individual = backend_data.sort_values("particle_count")
        axis.scatter(
            individual["particle_count"],
            individual["mean_step_seconds"],
            s=28,
            alpha=0.55,
            label=f"{backend.upper()} individual runs",
        )
    axis.set_xlabel("Particle count")
    axis.set_ylabel("Mean step time (s)")
    axis.set_title("Runtime scaling by backend")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight", format="png")
    plt.close(figure)


def _plot_final_velocity(runs: Sequence[RunBundle], output: Path) -> None:
    # One representative per backend/resolution keeps the field comparison
    # readable; repeat differences remain fully exposed in the aggregate CSV.
    representative: list[RunBundle] = []
    seen: set[tuple[str, int]] = set()
    for run in sorted(runs, key=lambda item: (item.backend, item.resolution, item.run_id)):
        identity = (run.backend, run.resolution)
        if identity not in seen:
            representative.append(run)
            seen.add(identity)

    panel_count = len(representative)
    columns = min(3, panel_count)
    rows = math.ceil(panel_count / columns)
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(4.2 * columns, 3.8 * rows),
        squeeze=False,
        layout="constrained",
    )
    all_speeds = np.concatenate(
        [
            np.linalg.norm(run.trajectory["velocities"][-1], axis=-1)
            for run in representative
        ]
    )
    color_min = float(np.min(all_speeds))
    color_max = float(np.max(all_speeds))
    if color_max <= color_min:
        color_max = color_min + np.finfo(float).eps

    scatter = None
    for index, run in enumerate(representative):
        axis = axes.flat[index]
        positions = run.trajectory["positions"][-1]
        velocities = run.trajectory["velocities"][-1]
        speed = np.linalg.norm(velocities, axis=-1)
        scatter = axis.scatter(
            positions[:, 0],
            positions[:, 1],
            c=speed,
            s=9,
            cmap="viridis",
            vmin=color_min,
            vmax=color_max,
            rasterized=True,
        )
        stride = max(1, math.ceil(len(positions) / 128))
        axis.quiver(
            positions[::stride, 0],
            positions[::stride, 1],
            velocities[::stride, 0],
            velocities[::stride, 1],
            color="black",
            alpha=0.55,
            angles="xy",
            scale_units="xy",
            scale=None,
            width=0.003,
        )
        axis.set_title(_run_label(run), fontsize=9)
        axis.set_xlabel("x")
        axis.set_ylabel("y")
        axis.set_aspect("equal", adjustable="box")
    for index in range(panel_count, rows * columns):
        axes.flat[index].set_visible(False)
    if scatter is not None:
        figure.colorbar(
            scatter,
            ax=[axis for axis in axes.flat],
            label="Speed magnitude",
            shrink=0.85,
            pad=0.02,
        )
    figure.suptitle("Final particle velocity fields")
    figure.savefig(output, dpi=180, format="png")
    plt.close(figure)


FIGURE_FILENAMES = (
    "velocity_error_vs_time.png",
    "kinetic_energy_vs_time.png",
    "momentum_drift_vs_time.png",
    "density_fluctuation_vs_time.png",
    "runtime_vs_particle_count.png",
    "final_velocity_field.png",
)


def create_figures(runs: Sequence[RunBundle], output_directory: Path) -> None:
    """Create all six required figures from validated raw artifacts."""

    if not runs:
        raise AnalysisError("cannot plot an empty run collection")
    output_directory.mkdir(parents=True, exist_ok=True)
    _plot_curve_pair(
        runs,
        columns=("velocity_relative_l2", "velocity_rmse"),
        labels=("Relative velocity L2 error", "Velocity RMSE"),
        title="Velocity error versus time",
        output=output_directory / FIGURE_FILENAMES[0],
    )
    _plot_curve_pair(
        runs,
        columns=("total_kinetic_energy", "kinetic_energy_relative_error"),
        labels=("Total kinetic energy", "Relative energy error"),
        title="Kinetic energy versus time",
        output=output_directory / FIGURE_FILENAMES[1],
    )
    _plot_single_curve(
        runs,
        column="relative_momentum_drift",
        ylabel="Relative momentum drift",
        title="Momentum drift versus time",
        output=output_directory / FIGURE_FILENAMES[2],
    )
    _plot_single_curve(
        runs,
        column="relative_density_fluctuation",
        ylabel="Relative density fluctuation",
        title="Density fluctuation versus time",
        output=output_directory / FIGURE_FILENAMES[3],
    )
    _plot_runtime(runs, output_directory / FIGURE_FILENAMES[4])
    _plot_final_velocity(runs, output_directory / FIGURE_FILENAMES[5])


def _write_csv_atomically(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        prefix=f".{destination.stem}-",
        dir=destination.parent,
        delete=False,
        newline="",
    ) as handle:
        temporary = Path(handle.name)
        frame.to_csv(handle, index=False)
    try:
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def analyze(
    raw_directory: Path,
    reports_directory: Path,
    figures_directory: Path,
    *,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Aggregate both roles while plotting canonical short runs only.

    Outputs are replaced only after all six figures have been generated in a
    temporary directory.  Thus an analysis or plotting failure does not leave
    a partially refreshed figure set.  Stability summary, segment, and fixed
    interval numerical rows enter the CSV outputs, but not repeat comparisons
    or figures.  ``dry_run`` validates both roles without writing anything.
    """

    if rtol < 0 or atol < 0:
        raise ValueError("rtol and atol must be non-negative")
    discovery = discover_runs(raw_directory)
    if not discovery.runs:
        details = {
            "excluded": list(discovery.excluded),
            "invalid": dict(discovery.invalid),
        }
        raise AnalysisError(
            "no valid Stage 01 runs were found; existing outputs were not "
            f"modified. Details: {json.dumps(details, sort_keys=True)}"
        )
    canonical_runs = tuple(
        run for run in discovery.runs if run.role == "canonical"
    )
    stability_runs = tuple(
        run for run in discovery.runs if run.role == "stability"
    )
    numerical, runtime = build_aggregate_frames(
        discovery.runs, rtol=rtol, atol=atol
    )
    summary = {
        "valid_run_count": len(discovery.runs),
        "valid_runs": [run.stem for run in discovery.runs],
        "canonical_run_count": len(canonical_runs),
        "canonical_runs": [run.stem for run in canonical_runs],
        "stability_run_count": len(stability_runs),
        "stability_runs": [run.stem for run in stability_runs],
        "figure_runs": [run.stem for run in canonical_runs],
        "excluded_runs": list(discovery.excluded),
        "invalid_runs": dict(discovery.invalid),
        "repeat_status": {
            run.stem: runtime.loc[
                runtime["analysis_source_stem"] == run.stem,
                "analysis_repeat_status",
            ].iloc[0]
            for run in discovery.runs
        },
        "dry_run": dry_run,
    }
    if dry_run:
        return summary
    if not canonical_runs:
        raise AnalysisError(
            "no valid canonical short run is available for the six required "
            "figures; existing outputs were not modified"
        )

    reports_directory = Path(reports_directory)
    figures_directory = Path(figures_directory)
    reports_directory.mkdir(parents=True, exist_ok=True)
    figures_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".stage01-analysis-",
        dir=figures_directory,
    ) as temporary_name:
        temporary_figures = Path(temporary_name)
        create_figures(canonical_runs, temporary_figures)
        missing_figures = [
            filename
            for filename in FIGURE_FILENAMES
            if not (temporary_figures / filename).is_file()
        ]
        if missing_figures:
            raise AnalysisError(
                f"figure generation did not produce: {missing_figures}"
            )
        _write_csv_atomically(
            numerical,
            reports_directory / "stage_01_numerical_metrics.csv",
        )
        _write_csv_atomically(
            runtime,
            reports_directory / "stage_01_runtime_metrics.csv",
        )
        for filename in FIGURE_FILENAMES:
            os.replace(temporary_figures / filename, figures_directory / filename)

    summary.update(
        {
            "numerical_rows": len(numerical),
            "runtime_rows": len(runtime),
            "numerical_csv": _display_path(
                reports_directory / "stage_01_numerical_metrics.csv"
            ),
            "runtime_csv": _display_path(
                reports_directory / "stage_01_runtime_metrics.csv"
            ),
            "figures": [
                _display_path(figures_directory / filename)
                for filename in FIGURE_FILENAMES
            ],
        }
    )
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate validated canonical and stability Stage 01 runs, then "
            "create six canonical-only diagnostic figures."
        )
    )
    parser.add_argument("--raw-directory", type=Path, default=DEFAULT_RAW_DIRECTORY)
    parser.add_argument(
        "--reports-directory", type=Path, default=DEFAULT_REPORTS_DIRECTORY
    )
    parser.add_argument(
        "--figures-directory", type=Path, default=DEFAULT_FIGURES_DIRECTORY
    )
    parser.add_argument("--rtol", type=float, default=1.0e-6)
    parser.add_argument("--atol", type=float, default=1.0e-8)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and audit repeats without writing reports or figures",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = analyze(
            args.raw_directory,
            args.reports_directory,
            args.figures_directory,
            rtol=args.rtol,
            atol=args.atol,
            dry_run=args.dry_run,
        )
    except AnalysisError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
