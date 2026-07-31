"""Evaluate Stage 01D machine evidence without running any trajectory.

This program is intentionally a pure post-processor.  It reads the
pre-registered configuration and already-written CSV/NPZ evidence, applies
the frozen gates, and writes LF-terminated machine tables.  Missing files,
ambiguous run selections, unknown statuses, and schema mismatches are errors;
they are never interpreted as numerical passes.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
PREREGISTRATION_PATH = (
    EXPERIMENT_ROOT
    / "configs"
    / "preregistered_primary_tgv.yml"
)
ALLOWED_FINAL_STATUSES = ("V2_PASS", "V2_CONDITIONAL", "V2_FAIL")
ACCEPTED_RUN_STATUSES = frozenset(
    {
        "ACCEPTED",
        "COMPLETE",
        "COMPLETED",
        "OK",
        "PASS",
        "PASSED",
        "SUCCESS",
    }
)
NONACCEPTED_RUN_STATUSES = frozenset(
    {
        "ABORTED",
        "BLOCKED",
        "FAIL",
        "FAILED",
        "SKIP",
        "SKIPPED",
        "STOPPED",
    }
)

# This is an evaluator qualification rule, frozen before dynamic results are
# inspected.  It does not compute GCI.  It only permits a future GCI flag when
# both adjacent positive observed orders agree to 25% relative or 0.25
# absolute, whichever is less restrictive.
ASYMPTOTIC_ORDER_RELATIVE_DIFFERENCE_MAX = 0.25
ASYMPTOTIC_ORDER_ABSOLUTE_DIFFERENCE_MAX = 0.25

FLOAT_TIME_ATOL = 2.0e-12


class EvidenceError(RuntimeError):
    """Raised when machine evidence is absent, ambiguous, or malformed."""


@dataclass(frozen=True)
class TrajectoryState:
    path: Path
    times: np.ndarray
    velocities: np.ndarray


@dataclass(frozen=True)
class EvidenceBundle:
    project_root: Path
    experiment_root: Path
    results_root: Path
    configuration: dict[str, Any]
    run_summary_path: Path
    run_summary: pd.DataFrame
    samples: dict[str, pd.DataFrame]
    sample_paths: dict[str, Path]
    states: dict[str, TrajectoryState | None]
    integrator_path: Path
    integrator: pd.DataFrame
    dynamic_autograd_path: Path
    dynamic_autograd: pd.DataFrame
    stage01c_regression_path: Path
    stage01c_regression: pd.DataFrame
    stage01c_baseline_path: Path
    stage01c_baseline: pd.DataFrame


@dataclass(frozen=True)
class EvaluationProducts:
    integrator_rows: list[dict[str, Any]]
    time_rows: list[dict[str, Any]]
    space_rows: list[dict[str, Any]]
    disorder_rows: list[dict[str, Any]]
    mach_rows: list[dict[str, Any]]
    gate_rows: list[dict[str, Any]]
    status: str


def _normal_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _nested(
    record: Mapping[str, Any],
    *keys: str,
) -> Any:
    current: Any = record
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        if not isinstance(current, Mapping) or key not in current:
            raise EvidenceError(
                "preregistration is missing key "
                + ".".join(traversed)
            )
        current = current[key]
    return current


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceError(f"missing preregistration YAML: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise EvidenceError(
            f"cannot parse preregistration YAML {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise EvidenceError(
            f"preregistration YAML must contain a mapping: {path}"
        )
    return value


def _read_csv(
    path: Path,
    *,
    label: str,
    allow_empty: bool = False,
) -> pd.DataFrame:
    if not path.is_file():
        raise EvidenceError(f"missing {label}: {path}")
    try:
        frame = pd.read_csv(path, float_precision="round_trip")
    except Exception as error:
        raise EvidenceError(f"cannot read {label} {path}: {error}") from error
    if frame.empty and not allow_empty:
        raise EvidenceError(f"{label} is empty: {path}")
    duplicates = frame.columns[frame.columns.duplicated()].tolist()
    if duplicates:
        raise EvidenceError(
            f"{label} has duplicate columns {duplicates}: {path}"
        )
    return frame


def _first_existing(paths: Sequence[Path], *, label: str) -> Path:
    found = [path for path in paths if path.is_file()]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise EvidenceError(
            f"ambiguous {label}; multiple candidates exist: {found}"
        )
    raise EvidenceError(
        f"missing {label}; checked: {[str(path) for path in paths]}"
    )


def _column_name(
    frame: pd.DataFrame,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
    source: str,
) -> str | None:
    candidates = [canonical, *aliases]
    exact = [name for name in candidates if name in frame.columns]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        first = frame[exact[0]]
        if all(first.equals(frame[name]) for name in exact[1:]):
            return exact[0]
        raise EvidenceError(
            f"{source} contains conflicting aliases for {canonical}: {exact}"
        )
    normalized = {_normal_token(name): name for name in frame.columns}
    matches = [
        normalized[_normal_token(name)]
        for name in candidates
        if _normal_token(name) in normalized
    ]
    matches = list(dict.fromkeys(matches))
    if len(matches) == 1:
        return matches[0]
    if required:
        raise EvidenceError(
            f"{source} is missing required column {canonical!r}; "
            f"accepted aliases={candidates}"
        )
    return None


def _series(
    frame: pd.DataFrame,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
    source: str,
) -> pd.Series | None:
    name = _column_name(
        frame,
        canonical,
        aliases,
        required=required,
        source=source,
    )
    return None if name is None else frame[name]


def _numeric(
    frame: pd.DataFrame,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
    source: str,
) -> np.ndarray | None:
    values = _series(
        frame,
        canonical,
        aliases,
        required=required,
        source=source,
    )
    if values is None:
        return None
    converted = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    invalid = values.notna().to_numpy() & ~np.isfinite(converted)
    if invalid.any():
        indices = frame.index[invalid].tolist()[:8]
        raise EvidenceError(
            f"{source}.{canonical} contains nonnumeric/nonfinite values "
            f"at rows {indices}"
        )
    return converted


def _parse_bool(value: Any, *, context: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and value in (0, 1):
        return bool(value)
    token = _normal_token(value)
    if token in {"true", "t", "yes", "y", "1", "pass", "passed"}:
        return True
    if token in {"false", "f", "no", "n", "0", "fail", "failed"}:
        return False
    raise EvidenceError(f"cannot parse boolean {value!r} for {context}")


def _bool_values(
    frame: pd.DataFrame,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
    source: str,
) -> np.ndarray | None:
    values = _series(
        frame,
        canonical,
        aliases,
        required=required,
        source=source,
    )
    if values is None:
        return None
    return np.asarray(
        [
            _parse_bool(value, context=f"{source}.{canonical}")
            for value in values.tolist()
        ],
        dtype=bool,
    )


def _accepted_status(value: Any, *, run_id: str) -> bool:
    token = _normal_token(value).upper()
    if token in ACCEPTED_RUN_STATUSES:
        return True
    if token in NONACCEPTED_RUN_STATUSES:
        return False
    raise EvidenceError(
        f"run {run_id!r} has unknown status {value!r}; "
        f"accepted={sorted(ACCEPTED_RUN_STATUSES)}, "
        f"nonaccepted={sorted(NONACCEPTED_RUN_STATUSES)}"
    )


def _canonical_protocol(value: Any) -> str:
    token = _normal_token(value)
    aliases = {
        "zero": "zero_flow",
        "zero_equilibrium": "zero_flow",
        "zero_flow_equilibrium": "zero_flow",
        "zero_flow": "zero_flow",
        "time": "time_convergence",
        "time_refinement": "time_convergence",
        "time_convergence": "time_convergence",
        "space": "space_convergence",
        "spatial_convergence": "space_convergence",
        "space_convergence": "space_convergence",
        "support_comparison": "support_family_comparison",
        "support_family": "support_family_comparison",
        "support_family_comparison": "support_family_comparison",
        "disorder": "disorder_robustness",
        "disorder_robustness": "disorder_robustness",
        "mach": "mach_sensitivity",
        "model_form": "mach_sensitivity",
        "mach_sensitivity": "mach_sensitivity",
        "smoke_16": "smoke_n16",
        "smoke_n16": "smoke_n16",
        "smoke_32": "smoke_n32",
        "smoke_n32": "smoke_n32",
    }
    return aliases.get(token, token)


def _canonical_support_family(value: Any) -> str:
    token = _normal_token(value)
    if token in {
        "increasing",
        "increasing_neighbor",
        "increasing_neighbors",
        "consistency",
    }:
        return "increasing_neighbor"
    if token in {
        "constant",
        "constant_neighbor",
        "constant_neighbors",
    }:
        return "constant_neighbor"
    return token


def _canonical_layout(value: Any) -> str:
    token = _normal_token(value)
    aliases = {
        "regular": "regular",
        "cartesian": "regular",
        "jitter5": "jitter_05",
        "jitter_5": "jitter_05",
        "jitter_05": "jitter_05",
        "jitter05": "jitter_05",
        "jitter10": "jitter_10",
        "jitter_10": "jitter_10",
    }
    return aliases.get(token, token)


def _resolve_recorded_path(
    value: Any,
    *,
    project_root: Path,
    experiment_root: Path,
    default_candidates: Sequence[Path],
    label: str,
) -> Path:
    if value is not None and not pd.isna(value) and str(value).strip():
        recorded = Path(str(value))
        candidates = (
            [recorded]
            if recorded.is_absolute()
            else [
                project_root / recorded,
                experiment_root / recorded,
            ]
        )
        return _first_existing(candidates, label=label)
    return _first_existing(default_candidates, label=label)


def _npz_array(
    archive: np.lib.npyio.NpzFile,
    names: Sequence[str],
    *,
    path: Path,
) -> np.ndarray:
    found = [name for name in names if name in archive.files]
    if len(found) != 1:
        raise EvidenceError(
            f"{path} must contain exactly one of {list(names)}; "
            f"found={found}, keys={archive.files}"
        )
    return np.asarray(archive[found[0]])


def _read_state(path: Path) -> TrajectoryState:
    try:
        with np.load(path, allow_pickle=False) as archive:
            times = _npz_array(
                archive,
                ("times", "time", "sample_times"),
                path=path,
            ).astype(float, copy=False)
            velocities = _npz_array(
                archive,
                ("velocities", "velocity", "sample_velocities"),
                path=path,
            ).astype(float, copy=False)
    except EvidenceError:
        raise
    except Exception as error:
        raise EvidenceError(f"cannot read trajectory state {path}: {error}") from error
    if times.ndim != 1 or times.size == 0:
        raise EvidenceError(f"{path}: times must have nonempty shape [samples]")
    if velocities.ndim != 3 or velocities.shape[2] != 2:
        raise EvidenceError(
            f"{path}: velocities must have shape [samples, particles, 2]"
        )
    if velocities.shape[0] != times.size:
        raise EvidenceError(
            f"{path}: time/velocity sample counts differ "
            f"({times.size} != {velocities.shape[0]})"
        )
    if not np.isfinite(times).all():
        raise EvidenceError(f"{path}: state times contain NaN/Inf")
    if np.any(np.diff(times) < 0.0):
        raise EvidenceError(f"{path}: state times are not nondecreasing")
    return TrajectoryState(
        path=path,
        times=times,
        velocities=velocities,
    )


def load_evidence(
    *,
    project_root: Path = PROJECT_ROOT,
    experiment_root: Path = EXPERIMENT_ROOT,
) -> EvidenceBundle:
    """Read and structurally validate every required Stage 01D input."""

    project_root = project_root.resolve()
    experiment_root = experiment_root.resolve()
    results_root = experiment_root / "results"
    configuration = _load_yaml(
        experiment_root
        / "configs"
        / "preregistered_primary_tgv.yml"
    )
    run_summary_path = results_root / "run_summary.csv"
    summary = _read_csv(run_summary_path, label="Stage 01D run summary")
    summary_source = str(run_summary_path)
    run_id_column = _column_name(
        summary,
        "run_id",
        source=summary_source,
    )
    assert run_id_column is not None
    run_ids = summary[run_id_column].astype(str)
    if (run_ids.str.strip() == "").any():
        raise EvidenceError(f"{run_summary_path}: blank run_id")
    if run_ids.duplicated().any():
        duplicate_ids = run_ids[run_ids.duplicated(keep=False)].tolist()
        raise EvidenceError(
            f"{run_summary_path}: duplicate run_id values {duplicate_ids}"
        )
    summary = summary.copy()
    summary["_run_id"] = run_ids
    protocol = _series(
        summary,
        "protocol",
        ("experiment", "branch", "run_type"),
        source=summary_source,
    )
    status = _series(
        summary,
        "status",
        ("run_status",),
        source=summary_source,
    )
    assert protocol is not None and status is not None
    summary["_protocol"] = [
        _canonical_protocol(value) for value in protocol.tolist()
    ]
    summary["_accepted"] = [
        _accepted_status(value, run_id=run_id)
        for value, run_id in zip(status.tolist(), run_ids.tolist())
    ]
    support = _series(
        summary,
        "support_family",
        ("method_id", "support_method"),
        required=False,
        source=summary_source,
    )
    summary["_support_family"] = (
        ""
        if support is None
        else [
            _canonical_support_family(value)
            for value in support.fillna("").tolist()
        ]
    )
    layout = _series(
        summary,
        "layout",
        ("particle_layout",),
        required=False,
        source=summary_source,
    )
    summary["_layout"] = (
        ""
        if layout is None
        else [
            _canonical_layout(value)
            for value in layout.fillna("").tolist()
        ]
    )

    sample_path_column = _column_name(
        summary,
        "sample_table_path",
        ("trajectory_sample_path", "samples_path"),
        required=False,
        source=summary_source,
    )
    state_path_column = _column_name(
        summary,
        "state_path",
        ("trajectory_state_path", "trajectory_states_path"),
        required=False,
        source=summary_source,
    )
    samples: dict[str, pd.DataFrame] = {}
    sample_paths: dict[str, Path] = {}
    states: dict[str, TrajectoryState | None] = {}
    for _, row in summary.iterrows():
        run_id = str(row["_run_id"])
        sample_value = (
            row[sample_path_column] if sample_path_column is not None else None
        )
        sample_path = _resolve_recorded_path(
            sample_value,
            project_root=project_root,
            experiment_root=experiment_root,
            default_candidates=(
                results_root / "trajectory_samples" / f"{run_id}.csv",
                experiment_root / "trajectory_samples" / f"{run_id}.csv",
            ),
            label=f"trajectory sample CSV for run {run_id}",
        )
        sample = _read_csv(
            sample_path,
            label=f"trajectory sample CSV for run {run_id}",
            allow_empty=not bool(row["_accepted"]),
        )
        sample_run_id = _series(
            sample,
            "run_id",
            required=False,
            source=str(sample_path),
        )
        if sample_run_id is not None and not (
            sample_run_id.astype(str) == run_id
        ).all():
            raise EvidenceError(
                f"{sample_path}: run_id column does not equal {run_id!r}"
            )
        samples[run_id] = sample
        sample_paths[run_id] = sample_path

        state_value = (
            row[state_path_column] if state_path_column is not None else None
        )
        state_defaults = (
            results_root / "trajectory_states" / f"{run_id}.npz",
            experiment_root / "trajectory_states" / f"{run_id}.npz",
        )
        if bool(row["_accepted"]):
            state_path = _resolve_recorded_path(
                state_value,
                project_root=project_root,
                experiment_root=experiment_root,
                default_candidates=state_defaults,
                label=f"trajectory state NPZ for run {run_id}",
            )
            states[run_id] = _read_state(state_path)
        else:
            if (
                state_value is not None
                and not pd.isna(state_value)
                and str(state_value).strip()
            ):
                recorded_state = Path(str(state_value))
                state_candidates = (
                    [recorded_state]
                    if recorded_state.is_absolute()
                    else [
                        project_root / recorded_state,
                        experiment_root / recorded_state,
                    ]
                )
            else:
                state_candidates = list(state_defaults)
            found_states = [
                candidate
                for candidate in state_candidates
                if candidate.is_file()
            ]
            if len(found_states) > 1:
                raise EvidenceError(
                    f"ambiguous trajectory state NPZ for failed run "
                    f"{run_id}: {found_states}"
                )
            states[run_id] = (
                _read_state(found_states[0]) if found_states else None
            )

    integrator_path = _first_existing(
        (
            project_root
            / "06_experiments"
            / "stage_01d_integrator_verification"
            / "results"
            / "integrator_verification.csv",
            project_root
            / "06_experiments"
            / "stage_01d_integrator_verification"
            / "results"
            / "integrator_order.csv",
        ),
        label="Stage 01D integrator verification CSV",
    )
    dynamic_autograd_path = _first_existing(
        (
            results_root / "dynamic_autograd_fd.csv",
            project_root
            / "06_experiments"
            / "stage_01d_autograd"
            / "results"
            / "dynamic_autograd_fd.csv",
        ),
        label="Stage 01D dynamic autograd CSV",
    )
    stage01c_regression_path = _first_existing(
        (
            results_root / "stage01c_autograd_regression.csv",
        ),
        label="current Stage 01C autograd regression CSV",
    )
    stage01c_baseline_path = (
        project_root
        / "06_experiments"
        / "stage_01c_autograd"
        / "results"
        / "native_autograd_fd.csv"
    )
    return EvidenceBundle(
        project_root=project_root,
        experiment_root=experiment_root,
        results_root=results_root,
        configuration=configuration,
        run_summary_path=run_summary_path,
        run_summary=summary,
        samples=samples,
        sample_paths=sample_paths,
        states=states,
        integrator_path=integrator_path,
        integrator=_read_csv(
            integrator_path,
            label="Stage 01D integrator verification CSV",
        ),
        dynamic_autograd_path=dynamic_autograd_path,
        dynamic_autograd=_read_csv(
            dynamic_autograd_path,
            label="Stage 01D dynamic autograd CSV",
        ),
        stage01c_regression_path=stage01c_regression_path,
        stage01c_regression=_read_csv(
            stage01c_regression_path,
            label="current Stage 01C autograd regression CSV",
        ),
        stage01c_baseline_path=stage01c_baseline_path,
        stage01c_baseline=_read_csv(
            stage01c_baseline_path,
            label="frozen Stage 01C native autograd baseline CSV",
        ),
    )


SAMPLE_NUMERIC_ALIASES: dict[str, tuple[str, ...]] = {
    "step": ("step_index",),
    "time": ("physical_time", "t"),
    "velocity_error_l1": ("velocity_L1", "velocity_l1_error"),
    "velocity_relative_l2": (
        "velocity_relative_L2",
        "velocity_l2_relative_error",
    ),
    "velocity_error_linf": ("velocity_Linf", "velocity_linf_error"),
    "modal_amplitude_error": (
        "modal_amplitude_absolute_error",
        "tgv_modal_amplitude_error",
    ),
    "kinetic_energy_error": (
        "kinetic_energy_absolute_error",
        "energy_absolute_error",
    ),
    "density_fluctuation_relative_rms": (
        "relative_density_fluctuation_rms",
        "density_relative_rms",
    ),
    "maximum_mach": ("max_mach", "maximum_mach_number"),
    "maximum_speed": ("max_speed",),
    "momentum_drift_absolute": ("absolute_momentum_drift",),
    "momentum_drift_normalized": (
        "characteristic_normalized_momentum_drift",
        "relative_momentum_drift",
    ),
    "angular_momentum_drift_absolute": (
        "angular_momentum_drift",
        "absolute_angular_momentum_drift",
    ),
    "minimum_separation": (
        "minimum_particle_separation",
        "min_separation",
    ),
    "neighbor_count_mean": ("neighbor_mean",),
    "neighbor_count_min": ("neighbor_min",),
    "neighbor_count_max": ("neighbor_max",),
    "pressure_relative_pair_force_residual": (
        "pressure_pair_relative_residual",
    ),
    "viscosity_relative_pair_force_residual": (
        "viscosity_pair_relative_residual",
    ),
    "relative_total_internal_force": (
        "characteristic_normalized_total_internal_force",
        "normalized_total_internal_force",
    ),
    "assembled_relative_internal_force": (
        "assembled_characteristic_normalized_internal_force",
    ),
    "assembly_force_consistency_relative_linf": (
        "assembly_consistency_relative_linf",
    ),
    "accumulated_viscous_power": (
        "viscous_power",
        "discrete_viscous_power",
    ),
    "pair_direct_viscous_power": ("direct_viscous_power",),
    "peak_rss_bytes": ("maximum_rss_bytes",),
    "current_rss_bytes": (
        "rss_bytes",
        "current_resident_set_bytes",
    ),
    "memory_free_percentage": (
        "memory_pressure_free_percentage",
        "system_memory_free_percent",
    ),
    "thermal_slowdown_fraction": (
        "second_half_step_time_increase_fraction",
    ),
    "wall_clock_seconds": ("runtime_seconds", "wall_seconds"),
    "pressure_absolute_maximum": ("maximum_absolute_pressure", "max_abs_pressure"),
    "neighbor_duplicate_edge_count": ("duplicate_edge_count",),
    "neighbor_missing_self_edge_count": ("missing_self_edge_count",),
    "neighbor_nonreciprocal_nonself_edge_count": (
        "nonreciprocal_nonself_edge_count",
        "nonreciprocal_edge_count",
    ),
    "neighbor_out_of_bounds_edge_count": ("out_of_bounds_edge_count",),
    "neighbor_omitted_strict_support_edge_count": (
        "omitted_strict_support_edge_count",
        "strict_support_omission_count",
    ),
    "neighbor_unexpected_edge_count": ("unexpected_edge_count",),
    "position_drift_linf": ("position_drift", "maximum_position_drift"),
    "velocity_linf": ("maximum_velocity_linf", "velocity_absolute_maximum"),
    "relative_density_drift": (
        "density_drift_relative",
        "maximum_relative_density_drift",
        "density_drift",
    ),
}

TOPOLOGY_SAMPLE_COLUMNS = (
    "neighbor_duplicate_edge_count",
    "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count",
    "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count",
    "neighbor_unexpected_edge_count",
)

ANALYTIC_METRICS = (
    "velocity_error_l1",
    "velocity_relative_l2",
    "velocity_error_linf",
    "modal_amplitude_error",
    "kinetic_energy_error",
)

CONVERGENCE_METRICS = (
    "velocity_relative_l2",
    "modal_amplitude_error",
    "kinetic_energy_error",
)


def _sample_numeric(
    sample: pd.DataFrame,
    canonical: str,
    *,
    path: Path,
    required: bool = True,
) -> np.ndarray | None:
    return _numeric(
        sample,
        canonical,
        SAMPLE_NUMERIC_ALIASES.get(canonical, ()),
        required=required,
        source=str(path),
    )


def _summary_column(
    bundle: EvidenceBundle,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
) -> str | None:
    return _column_name(
        bundle.run_summary,
        canonical,
        aliases,
        required=required,
        source=str(bundle.run_summary_path),
    )


def _row_number(
    row: pd.Series,
    bundle: EvidenceBundle,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
) -> float | None:
    column = _summary_column(
        bundle,
        canonical,
        aliases,
        required=required,
    )
    if column is None or pd.isna(row[column]):
        if required:
            raise EvidenceError(
                f"run {row['_run_id']}: missing numeric {canonical}"
            )
        return None
    try:
        value = float(row[column])
    except (TypeError, ValueError) as error:
        raise EvidenceError(
            f"run {row['_run_id']}: invalid {canonical}={row[column]!r}"
        ) from error
    if not math.isfinite(value):
        raise EvidenceError(
            f"run {row['_run_id']}: nonfinite {canonical}={value}"
        )
    return value


def _row_text(
    row: pd.Series,
    bundle: EvidenceBundle,
    canonical: str,
    aliases: Sequence[str] = (),
    *,
    required: bool = True,
) -> str | None:
    column = _summary_column(
        bundle,
        canonical,
        aliases,
        required=required,
    )
    if column is None or pd.isna(row[column]) or not str(row[column]).strip():
        if required:
            raise EvidenceError(
                f"run {row['_run_id']}: missing text {canonical}"
            )
        return None
    return str(row[column]).strip()


def _isclose(value: float, expected: float) -> bool:
    return math.isclose(
        value,
        expected,
        rel_tol=2.0e-12,
        abs_tol=FLOAT_TIME_ATOL,
    )


def _finite_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _select_one(
    frame: pd.DataFrame,
    mask: np.ndarray | pd.Series,
    *,
    description: str,
) -> pd.Series:
    selected = frame.loc[np.asarray(mask, dtype=bool)]
    if len(selected) != 1:
        ids = selected["_run_id"].astype(str).tolist()
        raise EvidenceError(
            f"expected exactly one run for {description}; "
            f"found {len(selected)}: {ids}"
        )
    return selected.iloc[0]


def _matching_time_index(
    times: np.ndarray,
    target: float,
    *,
    context: str,
) -> int:
    matches = np.flatnonzero(
        np.isclose(times, target, rtol=2.0e-12, atol=FLOAT_TIME_ATOL)
    )
    if matches.size != 1:
        raise EvidenceError(
            f"{context}: expected exactly one sample at t={target:.17g}; "
            f"found {matches.size}"
        )
    return int(matches[0])


def _endpoint_metrics(
    bundle: EvidenceBundle,
    row: pd.Series,
    *,
    final_time: float,
    allow_last_available: bool = False,
) -> dict[str, Any]:
    run_id = str(row["_run_id"])
    sample = bundle.samples[run_id]
    path = bundle.sample_paths[run_id]
    incomplete_allowed = bool(
        allow_last_available or not bool(row["_accepted"])
    )
    optional_metrics = (
        "density_fluctuation_relative_rms",
        "maximum_mach",
        "maximum_speed",
        "momentum_drift_absolute",
        "momentum_drift_normalized",
        "angular_momentum_drift_absolute",
        "minimum_separation",
        "neighbor_count_mean",
        "neighbor_count_min",
        "neighbor_count_max",
        "pressure_absolute_maximum",
        "wall_clock_seconds",
        "peak_rss_bytes",
    )
    if sample.empty:
        if not incomplete_allowed:
            raise EvidenceError(
                f"accepted run {run_id} has no trajectory samples: {path}"
            )
        result: dict[str, Any] = {
            "run_id": run_id,
            "accepted": False,
            "sample_count": 0,
            "requested_final_time": final_time,
            "requested_endpoint_sample_present": False,
            "endpoint_time": None,
            "final_time": None,
            "endpoint_is_requested_final": False,
            "partial_trajectory": True,
            "state_reaches_endpoint": False,
            "state_reaches_requested_final": False,
            "available_trajectory_finite": False,
            "trajectory_finite": False,
        }
        for metric in (*ANALYTIC_METRICS, *optional_metrics):
            result[metric] = None
        return result
    times = _sample_numeric(sample, "time", path=path)
    assert times is not None
    if np.any(np.diff(times) < 0.0):
        raise EvidenceError(f"run {run_id} ({path}): sample times decrease")
    analytic_values: dict[str, np.ndarray] = {}
    available = np.isfinite(times)
    for metric in ANALYTIC_METRICS:
        values = _sample_numeric(sample, metric, path=path)
        assert values is not None
        analytic_values[metric] = values
        available &= np.isfinite(values)
    requested_matches = np.flatnonzero(
        np.isclose(
            times,
            final_time,
            rtol=2.0e-12,
            atol=FLOAT_TIME_ATOL,
        )
    )
    if requested_matches.size > 1:
        raise EvidenceError(
            f"run {run_id} ({path}): expected at most one sample at "
            f"t={final_time:.17g}; found {requested_matches.size}"
        )
    requested_endpoint_present = requested_matches.size == 1
    if requested_endpoint_present and available[int(requested_matches[0])]:
        endpoint = int(requested_matches[0])
        endpoint_is_requested_final = True
    elif incomplete_allowed:
        usable = np.flatnonzero(
            available
            & (
                (times < final_time)
                | np.isclose(
                    times,
                    final_time,
                    rtol=2.0e-12,
                    atol=FLOAT_TIME_ATOL,
                )
            )
        )
        if usable.size == 0 and not bool(row["_accepted"]):
            result = {
                "run_id": run_id,
                "accepted": False,
                "sample_count": int(len(sample)),
                "requested_final_time": final_time,
                "requested_endpoint_sample_present": (
                    requested_endpoint_present
                ),
                "endpoint_time": None,
                "final_time": None,
                "endpoint_is_requested_final": False,
                "partial_trajectory": True,
                "state_reaches_endpoint": False,
                "state_reaches_requested_final": False,
                "available_trajectory_finite": False,
                "trajectory_finite": False,
            }
            for metric in (*ANALYTIC_METRICS, *optional_metrics):
                result[metric] = None
            return result
        if usable.size == 0:
            raise EvidenceError(
                f"run {run_id} ({path}): no finite analytic sample at or "
                f"before requested t={final_time:.17g}"
            )
        endpoint = int(usable[-1])
        endpoint_is_requested_final = bool(
            requested_endpoint_present
            and endpoint == int(requested_matches[0])
        )
    else:
        endpoint = _matching_time_index(
            times,
            final_time,
            context=f"run {run_id} ({path})",
        )
        endpoint_is_requested_final = True
    result: dict[str, Any] = {
        "run_id": run_id,
        "accepted": bool(row["_accepted"]),
        "sample_count": int(len(sample)),
        "requested_final_time": final_time,
        "requested_endpoint_sample_present": requested_endpoint_present,
        "endpoint_time": float(times[endpoint]),
        "final_time": float(times[endpoint]),
        "endpoint_is_requested_final": endpoint_is_requested_final,
        "partial_trajectory": not endpoint_is_requested_final,
    }
    for metric in ANALYTIC_METRICS:
        result[metric] = float(analytic_values[metric][endpoint])
    for metric in optional_metrics:
        values = _sample_numeric(
            sample,
            metric,
            path=path,
            required=False,
        )
        if values is None:
            result[metric] = None
        else:
            value = float(values[endpoint])
            result[metric] = value if math.isfinite(value) else None
    state_finite = _bool_values(
        sample,
        "state_all_finite",
        ("finite", "all_finite"),
        required=False,
        source=str(path),
    )
    numeric_finite = all(
        np.isfinite(values).all() for values in analytic_values.values()
    )
    state = bundle.states[run_id]
    if state is None:
        state_reaches_endpoint = False
        state_reaches_requested_final = False
        state_velocities_finite = False
    else:
        state_reaches_endpoint = bool(
            np.any(
                np.isclose(
                    state.times,
                    float(times[endpoint]),
                    rtol=2.0e-12,
                    atol=FLOAT_TIME_ATOL,
                )
            )
        )
        state_reaches_requested_final = bool(
            np.any(
                np.isclose(
                    state.times,
                    final_time,
                    rtol=2.0e-12,
                    atol=FLOAT_TIME_ATOL,
                )
            )
        )
        state_velocities_finite = bool(
            np.isfinite(state.velocities).all()
        )
    result["state_reaches_endpoint"] = state_reaches_endpoint
    result["state_reaches_requested_final"] = (
        state_reaches_requested_final
    )
    result["available_trajectory_finite"] = bool(
        numeric_finite
        and (state_finite is None or state_finite.all())
        and state_velocities_finite
        and state_reaches_endpoint
    )
    result["trajectory_finite"] = bool(
        row["_accepted"]
        and endpoint_is_requested_final
        and result["available_trajectory_finite"]
        and state_reaches_requested_final
    )
    return result


def _strictly_decreases(values: Sequence[float]) -> bool:
    return all(
        fine < coarse
        for coarse, fine in zip(values, values[1:])
    )


def _observed_order(
    coarse_error: float,
    fine_error: float,
    coarse_spacing: float,
    fine_spacing: float,
) -> float | None:
    if (
        not all(
            math.isfinite(value)
            for value in (
                coarse_error,
                fine_error,
                coarse_spacing,
                fine_spacing,
            )
        )
        or coarse_error <= 0.0
        or fine_error <= 0.0
        or coarse_spacing <= fine_spacing
        or fine_spacing <= 0.0
    ):
        return None
    return math.log(coarse_error / fine_error) / math.log(
        coarse_spacing / fine_spacing
    )


def evaluate_integrator(
    bundle: EvidenceBundle,
) -> tuple[list[dict[str, Any]], bool]:
    """Apply both independent explicit-midpoint order gates."""

    frame = bundle.integrator
    source = str(bundle.integrator_path)
    problem_series = _series(frame, "problem", source=source)
    dt_values = _numeric(frame, "dt", source=source)
    errors = _numeric(
        frame,
        "error_L2",
        ("absolute_error", "error_l2"),
        source=source,
    )
    assert problem_series is not None
    assert dt_values is not None and errors is not None
    expected_steps = [
        float(value)
        for value in _nested(
            bundle.configuration,
            "integrator",
            "time_steps",
        )
    ]
    qualification = _nested(
        bundle.configuration,
        "integrator",
        "qualification",
    )
    fitted_minimum = float(qualification["fitted_order_minimum"])
    finest_minimum = float(
        qualification["finest_pair_observed_order_minimum"]
    )
    required_problems = (
        "scalar_decay",
        "coupled_damped_oscillator",
    )
    rows: list[dict[str, Any]] = []
    for problem in required_problems:
        mask = problem_series.astype(str).map(_normal_token) == problem
        subset_dt = dt_values[mask.to_numpy()]
        subset_errors = errors[mask.to_numpy()]
        ordering = np.argsort(-subset_dt)
        subset_dt = subset_dt[ordering]
        subset_errors = subset_errors[ordering]
        dt_complete = (
            len(subset_dt) == len(expected_steps)
            and all(
                any(_isclose(float(actual), expected) for actual in subset_dt)
                for expected in expected_steps
            )
        )
        finite_positive = bool(
            np.isfinite(subset_errors).all()
            and np.all(subset_errors > 0.0)
        )
        decreases = bool(
            finite_positive
            and len(subset_errors) == len(expected_steps)
            and _strictly_decreases(subset_errors.tolist())
        )
        fitted_order = (
            float(np.polyfit(np.log(subset_dt), np.log(subset_errors), 1)[0])
            if dt_complete and finite_positive
            else None
        )
        finest_order = (
            _observed_order(
                float(subset_errors[-2]),
                float(subset_errors[-1]),
                float(subset_dt[-2]),
                float(subset_dt[-1]),
            )
            if len(subset_errors) >= 2
            else None
        )
        passed = bool(
            dt_complete
            and finite_positive
            and decreases
            and fitted_order is not None
            and fitted_order >= fitted_minimum
            and finest_order is not None
            and finest_order >= finest_minimum
        )
        rows.append(
            {
                "problem": problem,
                "method": "explicit_midpoint_rk2",
                "required_dt_count": len(expected_steps),
                "observed_dt_count": int(len(subset_dt)),
                "all_required_dt_present": dt_complete,
                "all_errors_finite_positive": finite_positive,
                "every_error_level_decreases": decreases,
                "fitted_order": fitted_order,
                "fitted_order_minimum": fitted_minimum,
                "finest_pair_observed_order": finest_order,
                "finest_pair_order_minimum": finest_minimum,
                "pass": passed,
                "source": str(
                    bundle.integrator_path.relative_to(bundle.project_root)
                ),
            }
        )
    unknown = sorted(
        set(problem_series.astype(str).map(_normal_token))
        - set(required_problems)
    )
    if unknown:
        raise EvidenceError(
            f"{bundle.integrator_path}: unexpected ODE problems {unknown}"
        )
    return rows, all(bool(row["pass"]) for row in rows)


def _summary_numeric_values(
    bundle: EvidenceBundle,
    canonical: str,
    aliases: Sequence[str] = (),
) -> np.ndarray:
    values = _numeric(
        bundle.run_summary,
        canonical,
        aliases,
        source=str(bundle.run_summary_path),
    )
    assert values is not None
    return values


def _time_run_rows(bundle: EvidenceBundle) -> list[pd.Series]:
    config = _nested(bundle.configuration, "time_convergence")
    expected_dts = [float(value) for value in config["time_steps"]]
    expected_resolution = int(config["resolution"])
    expected_support = float(config["support_ratio"])
    expected_family = _canonical_support_family(config["support_family"])
    resolutions = _summary_numeric_values(bundle, "resolution", ("N",))
    dts = _summary_numeric_values(bundle, "dt", ("time_step",))
    supports = _summary_numeric_values(
        bundle,
        "support_ratio",
        ("H_over_dx", "h_dx"),
    )
    rows: list[pd.Series] = []
    for expected_dt in expected_dts:
        mask = (
            (bundle.run_summary["_protocol"] == "time_convergence")
            & (resolutions == expected_resolution)
            & np.isclose(
                dts,
                expected_dt,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & np.isclose(
                supports,
                expected_support,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & (
                bundle.run_summary["_support_family"]
                == expected_family
            )
        )
        rows.append(
            _select_one(
                bundle.run_summary,
                mask,
                description=(
                    "time convergence "
                    f"N={expected_resolution}, H/dx={expected_support}, "
                    f"dt={expected_dt}"
                ),
            )
        )
    rows.sort(
        key=lambda row: float(
            _row_number(row, bundle, "dt", ("time_step",))
        ),
        reverse=True,
    )
    return rows


def _state_velocity_at_times(
    state: TrajectoryState,
    expected_times: np.ndarray,
    *,
    run_id: str,
) -> tuple[np.ndarray, np.ndarray]:
    selected: list[np.ndarray] = []
    available: list[bool] = []
    particle_shape = state.velocities.shape[1:]
    for target in expected_times:
        matches = np.flatnonzero(
            np.isclose(
                state.times,
                target,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
        )
        if matches.size == 1:
            selected.append(state.velocities[int(matches[0])])
            available.append(True)
        elif matches.size == 0:
            selected.append(np.full(particle_shape, np.nan))
            available.append(False)
        else:
            raise EvidenceError(
                f"state {run_id}: duplicate samples near t={target:.17g}"
            )
    return np.stack(selected), np.asarray(available, dtype=bool)


def evaluate_time_convergence(
    bundle: EvidenceBundle,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build analytic endpoints and all 21-time consecutive-dt differences."""

    config = _nested(bundle.configuration, "time_convergence")
    final_time = float(config["final_time"])
    requested_samples = int(
        _nested(
            bundle.configuration,
            "sampling",
            "requested_uniform_samples_per_trajectory",
        )
    )
    if requested_samples != 21:
        raise EvidenceError(
            "Stage 01D evaluator is preregistered for exactly 21 "
            f"uniform trajectory samples, not {requested_samples}"
        )
    expected_times = np.linspace(0.0, final_time, requested_samples)
    run_rows = _time_run_rows(bundle)
    endpoint_records: list[dict[str, Any]] = []
    endpoint_by_run: dict[str, dict[str, Any]] = {}
    for row in run_rows:
        run_id = str(row["_run_id"])
        dt = float(_row_number(row, bundle, "dt", ("time_step",)))
        endpoint = _endpoint_metrics(
            bundle,
            row,
            final_time=final_time,
        )
        endpoint["dt"] = dt
        endpoint_by_run[run_id] = endpoint
        endpoint_records.append(endpoint)

    analytic_ratios: dict[str, float | None] = {}
    for metric in CONVERGENCE_METRICS:
        coarse = _finite_float_or_none(endpoint_records[0][metric])
        fine = _finite_float_or_none(endpoint_records[-1][metric])
        analytic_ratios[metric] = (
            fine / coarse
            if coarse is not None and fine is not None and coarse > 0.0
            else None
        )
    analytic_limit = float(
        _nested(
            bundle.configuration,
            "time_convergence",
            "credible_trend",
            "analytic_endpoint_ratio_maximum_for_at_least_one_metric",
        )
    )
    analytic_pass = any(
        value is not None and value <= analytic_limit
        for value in analytic_ratios.values()
    )

    rows: list[dict[str, Any]] = []
    previous_modal_error: float | None = None
    previous_dt: float | None = None
    for endpoint in endpoint_records:
        dt = float(endpoint["dt"])
        modal_error = _finite_float_or_none(
            endpoint["modal_amplitude_error"]
        )
        modal_order = (
            _observed_order(
                previous_modal_error,
                modal_error,
                previous_dt,
                dt,
            )
            if modal_error is not None
            and previous_modal_error is not None
            and previous_dt is not None
            else None
        )
        previous_ratios: dict[str, float | None] = {}
        if rows:
            previous_endpoint = endpoint_records[len(rows) - 1]
            for metric in CONVERGENCE_METRICS:
                denominator = _finite_float_or_none(
                    previous_endpoint[metric]
                )
                numerator = _finite_float_or_none(endpoint[metric])
                previous_ratios[metric] = (
                    numerator / denominator
                    if denominator is not None
                    and numerator is not None
                    and denominator > 0.0
                    else None
                )
        rows.append(
            {
                "record_type": "analytic_endpoint",
                "run_id": endpoint["run_id"],
                "coarse_run_id": None,
                "fine_run_id": None,
                "dt": dt,
                "coarse_dt": None,
                "fine_dt": None,
                "time": final_time,
                "velocity_error_l1": endpoint["velocity_error_l1"],
                "velocity_relative_l2": endpoint["velocity_relative_l2"],
                "velocity_error_linf": endpoint["velocity_error_linf"],
                "modal_amplitude_error": endpoint["modal_amplitude_error"],
                "kinetic_energy_error": endpoint["kinetic_energy_error"],
                "modal_observed_order": modal_order,
                "velocity_self_l2": None,
                "self_pair_trajectory_rms": None,
                "self_pair_final_l2": None,
                "self_pair_observed_order": None,
                "velocity_endpoint_ratio_to_previous_dt": (
                    previous_ratios.get("velocity_relative_l2")
                ),
                "modal_endpoint_ratio_to_previous_dt": (
                    previous_ratios.get("modal_amplitude_error")
                ),
                "energy_endpoint_ratio_to_previous_dt": (
                    previous_ratios.get("kinetic_energy_error")
                ),
                "trajectory_finite": endpoint["trajectory_finite"],
                "sample_count": endpoint["sample_count"],
                "common_time_available": None,
                "analytic_platform_at_this_refinement": (
                    None
                    if not previous_ratios
                    else all(
                        value is not None and value > analytic_limit
                        for value in previous_ratios.values()
                    )
                ),
            }
        )
        previous_modal_error = modal_error
        previous_dt = dt

    pair_aggregates: list[dict[str, Any]] = []
    self_rows: list[dict[str, Any]] = []
    for coarse_row, fine_row in zip(run_rows, run_rows[1:]):
        coarse_id = str(coarse_row["_run_id"])
        fine_id = str(fine_row["_run_id"])
        coarse_dt = float(
            _row_number(coarse_row, bundle, "dt", ("time_step",))
        )
        fine_dt = float(
            _row_number(fine_row, bundle, "dt", ("time_step",))
        )
        differences = np.full(requested_samples, np.nan, dtype=float)
        coarse_state = bundle.states[coarse_id]
        fine_state = bundle.states[fine_id]
        if coarse_state is not None and fine_state is not None:
            coarse_velocity, coarse_available = _state_velocity_at_times(
                coarse_state,
                expected_times,
                run_id=coarse_id,
            )
            fine_velocity, fine_available = _state_velocity_at_times(
                fine_state,
                expected_times,
                run_id=fine_id,
            )
            if coarse_velocity.shape != fine_velocity.shape:
                raise EvidenceError(
                    "time self-convergence requires identical particle "
                    f"arrays: {coarse_id} {coarse_velocity.shape} != "
                    f"{fine_id} {fine_velocity.shape}"
                )
            available = coarse_available & fine_available
            for index in np.flatnonzero(available):
                difference = coarse_velocity[index] - fine_velocity[index]
                if np.isfinite(difference).all():
                    differences[index] = math.sqrt(
                        float(np.mean(np.sum(difference**2, axis=-1)))
                    )
        finite_mask = np.isfinite(differences)
        complete = bool(finite_mask.all())
        trajectory_rms = (
            math.sqrt(float(np.mean(differences**2)))
            if complete
            else None
        )
        final_l2 = (
            float(differences[-1]) if math.isfinite(differences[-1]) else None
        )
        pair = {
            "coarse_run_id": coarse_id,
            "fine_run_id": fine_id,
            "coarse_dt": coarse_dt,
            "fine_dt": fine_dt,
            "trajectory_rms": trajectory_rms,
            "final_l2": final_l2,
            "complete": complete,
        }
        pair_aggregates.append(pair)
        for index, time in enumerate(expected_times):
            self_rows.append(
                {
                    "record_type": "velocity_self_difference",
                    "run_id": None,
                    "coarse_run_id": coarse_id,
                    "fine_run_id": fine_id,
                    "dt": None,
                    "coarse_dt": coarse_dt,
                    "fine_dt": fine_dt,
                    "time": float(time),
                    "velocity_error_l1": None,
                    "velocity_relative_l2": None,
                    "velocity_error_linf": None,
                    "modal_amplitude_error": None,
                    "kinetic_energy_error": None,
                    "modal_observed_order": None,
                    "velocity_self_l2": (
                        float(differences[index])
                        if math.isfinite(differences[index])
                        else None
                    ),
                    "self_pair_trajectory_rms": trajectory_rms,
                    "self_pair_final_l2": final_l2,
                    "self_pair_observed_order": None,
                    "velocity_endpoint_ratio_to_previous_dt": None,
                    "modal_endpoint_ratio_to_previous_dt": None,
                    "energy_endpoint_ratio_to_previous_dt": None,
                    "trajectory_finite": (
                        endpoint_by_run[coarse_id]["trajectory_finite"]
                        and endpoint_by_run[fine_id]["trajectory_finite"]
                    ),
                    "sample_count": None,
                    "common_time_available": bool(finite_mask[index]),
                    "analytic_platform_at_this_refinement": None,
                }
            )

    for pair_index, pair in enumerate(pair_aggregates):
        order = None
        if pair_index > 0:
            previous = pair_aggregates[pair_index - 1]
            if (
                previous["trajectory_rms"] is not None
                and pair["trajectory_rms"] is not None
            ):
                order = _observed_order(
                    float(previous["trajectory_rms"]),
                    float(pair["trajectory_rms"]),
                    float(previous["coarse_dt"]),
                    float(pair["coarse_dt"]),
                )
        pair["observed_order"] = order
        for row in self_rows:
            if (
                row["coarse_run_id"] == pair["coarse_run_id"]
                and row["fine_run_id"] == pair["fine_run_id"]
            ):
                row["self_pair_observed_order"] = order

    self_ratio = None
    if (
        len(pair_aggregates) == 3
        and pair_aggregates[0]["trajectory_rms"] is not None
        and pair_aggregates[-1]["trajectory_rms"] is not None
        and float(pair_aggregates[0]["trajectory_rms"]) > 0.0
    ):
        self_ratio = (
            float(pair_aggregates[-1]["trajectory_rms"])
            / float(pair_aggregates[0]["trajectory_rms"])
        )
    self_limit = float(
        _nested(
            bundle.configuration,
            "time_convergence",
            "credible_trend",
            "self_convergence_finest_to_coarsest_ratio_maximum",
        )
    )
    self_pass = self_ratio is not None and self_ratio <= self_limit
    all_four_finite = bool(
        len(endpoint_records) == 4
        and all(
            bool(endpoint["trajectory_finite"])
            for endpoint in endpoint_records
        )
        and all(bool(pair["complete"]) for pair in pair_aggregates)
    )
    credible = bool(all_four_finite and (analytic_pass or self_pass))
    platform = bool(
        all_four_finite
        and not analytic_pass
        and not self_pass
    )
    facts = {
        "execution_status": "COMPLETE",
        "not_run_reason": "",
        "run_count": len(run_rows),
        "all_four_trajectories_finite": all_four_finite,
        "analytic_endpoint_ratios": analytic_ratios,
        "analytic_ratio_limit": analytic_limit,
        "analytic_trend_pass": analytic_pass,
        "self_finest_to_coarsest_ratio": self_ratio,
        "self_ratio_limit": self_limit,
        "self_trend_pass": self_pass,
        "credible_trend_pass": credible,
        "platform_detected": platform,
        "common_time_count": requested_samples,
    }
    for row in rows + self_rows:
        row["velocity_analytic_finest_to_coarsest_ratio"] = (
            analytic_ratios["velocity_relative_l2"]
        )
        row["modal_analytic_finest_to_coarsest_ratio"] = (
            analytic_ratios["modal_amplitude_error"]
        )
        row["energy_analytic_finest_to_coarsest_ratio"] = (
            analytic_ratios["kinetic_energy_error"]
        )
        row["self_finest_to_coarsest_ratio"] = self_ratio
        row["analytic_trend_pass"] = analytic_pass
        row["self_trend_pass"] = self_pass
        row["credible_time_trend_pass"] = credible
        row["time_platform_detected"] = platform
    return rows + self_rows, facts


def _space_family_runs(
    bundle: EvidenceBundle,
    *,
    family: str,
) -> list[pd.Series]:
    space_config = _nested(bundle.configuration, "space_convergence")
    comparison = _nested(
        bundle.configuration,
        "support_family_comparison",
    )
    target_dt = float(space_config["time_step"])
    target_final = float(space_config["final_time"])
    resolutions = [int(value) for value in comparison["resolutions"]]
    ratio_key = (
        "increasing_neighbor_ratios"
        if family == "increasing_neighbor"
        else "constant_neighbor_ratios"
    )
    ratios = {
        int(key): float(value)
        for key, value in comparison[ratio_key].items()
    }
    summary_resolutions = _summary_numeric_values(
        bundle,
        "resolution",
        ("N",),
    )
    summary_dts = _summary_numeric_values(
        bundle,
        "dt",
        ("time_step",),
    )
    summary_final = _summary_numeric_values(
        bundle,
        "t_final",
        ("final_time",),
    )
    summary_support = _summary_numeric_values(
        bundle,
        "support_ratio",
        ("H_over_dx", "h_dx"),
    )
    selected: list[pd.Series] = []
    for resolution in resolutions:
        protocol = (
            "space_convergence"
            if family == "increasing_neighbor"
            else "support_family_comparison"
        )
        base = (
            (summary_resolutions == resolution)
            & np.isclose(
                summary_dts,
                target_dt,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & np.isclose(
                summary_final,
                target_final,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & np.isclose(
                summary_support,
                ratios[resolution],
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & (bundle.run_summary["_support_family"] == family)
            & (bundle.run_summary["_layout"] == "regular")
        )
        mask = base & (bundle.run_summary["_protocol"] == protocol)
        if int(np.asarray(mask).sum()) == 0 and family == "increasing_neighbor":
            # A runner may reuse the support-comparison increasing-family
            # trajectory instead of writing a duplicate physical run.
            mask = base & (
                bundle.run_summary["_protocol"]
                == "support_family_comparison"
            )
        selected.append(
            _select_one(
                bundle.run_summary,
                mask,
                description=(
                    f"{family} spatial run N={resolution}, "
                    f"H/dx={ratios[resolution]}"
                ),
            )
        )
    return selected


def _near_asymptotic(
    first_order: float | None,
    second_order: float | None,
    *,
    monotone: bool,
) -> bool:
    if (
        not monotone
        or first_order is None
        or second_order is None
        or first_order <= 0.0
        or second_order <= 0.0
    ):
        return False
    difference = abs(first_order - second_order)
    relative_allowance = (
        ASYMPTOTIC_ORDER_RELATIVE_DIFFERENCE_MAX
        * max(abs(first_order), abs(second_order))
    )
    allowance = max(
        ASYMPTOTIC_ORDER_ABSOLUTE_DIFFERENCE_MAX,
        relative_allowance,
    )
    return difference <= allowance


def evaluate_space_convergence(
    bundle: EvidenceBundle,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fit primary/family slopes and emit a guarded GCI-eligibility flag."""

    space_config = _nested(bundle.configuration, "space_convergence")
    final_time = float(space_config["final_time"])
    primary_resolutions = [
        int(value) for value in space_config["primary_resolutions"]
    ]
    if primary_resolutions != [16, 24, 32]:
        raise EvidenceError(
            "evaluator expects preregistered primary resolutions [16,24,32]"
        )
    rows: list[dict[str, Any]] = []
    facts: dict[str, Any] = {}
    endpoints_by_family: dict[str, list[dict[str, Any]]] = {}
    for family in ("increasing_neighbor", "constant_neighbor"):
        family_runs = _space_family_runs(bundle, family=family)
        endpoints: list[dict[str, Any]] = []
        for run in family_runs:
            endpoint = _endpoint_metrics(
                bundle,
                run,
                final_time=final_time,
            )
            endpoint["resolution"] = int(
                _row_number(run, bundle, "resolution", ("N",))
            )
            endpoint["support_ratio"] = float(
                _row_number(
                    run,
                    bundle,
                    "support_ratio",
                    ("H_over_dx", "h_dx"),
                )
            )
            endpoints.append(endpoint)
        endpoints.sort(key=lambda item: int(item["resolution"]))
        endpoints_by_family[family] = endpoints
        resolutions = [int(item["resolution"]) for item in endpoints]
        spacings = [2.0 / resolution for resolution in resolutions]
        for metric in CONVERGENCE_METRICS:
            errors = [
                (
                    float(value)
                    if (value := _finite_float_or_none(item[metric]))
                    is not None
                    else math.nan
                )
                for item in endpoints
            ]
            finite_positive = bool(
                all(math.isfinite(error) and error > 0.0 for error in errors)
            )
            fitted_slope = (
                float(
                    np.polyfit(
                        np.log(np.asarray(spacings)),
                        np.log(np.asarray(errors)),
                        1,
                    )[0]
                )
                if finite_positive
                else None
            )
            pair_order_16_24 = (
                _observed_order(
                    errors[0],
                    errors[1],
                    spacings[0],
                    spacings[1],
                )
                if len(errors) >= 2
                else None
            )
            pair_order_24_32 = (
                _observed_order(
                    errors[1],
                    errors[2],
                    spacings[1],
                    spacings[2],
                )
                if len(errors) >= 3
                else None
            )
            monotone = bool(
                finite_positive and _strictly_decreases(errors)
            )
            near_asymptotic = _near_asymptotic(
                pair_order_16_24,
                pair_order_24_32,
                monotone=monotone,
            )
            ratio_n32_n16 = (
                errors[2] / errors[0]
                if finite_positive and errors[0] > 0.0
                else None
            )
            rows.append(
                {
                    "support_family": family,
                    "metric": metric,
                    "run_id_n16": endpoints[0]["run_id"],
                    "run_id_n24": endpoints[1]["run_id"],
                    "run_id_n32": endpoints[2]["run_id"],
                    "support_ratio_n16": endpoints[0]["support_ratio"],
                    "support_ratio_n24": endpoints[1]["support_ratio"],
                    "support_ratio_n32": endpoints[2]["support_ratio"],
                    "error_n16": errors[0],
                    "error_n24": errors[1],
                    "error_n32": errors[2],
                    "ratio_n32_over_n16": ratio_n32_n16,
                    "fitted_log_error_log_dx_slope": fitted_slope,
                    "pair_order_n16_n24": pair_order_16_24,
                    "pair_order_n24_n32": pair_order_24_32,
                    "all_errors_finite_positive": finite_positive,
                    "strictly_monotone_decreasing": monotone,
                    "near_asymptotic_order_agreement": near_asymptotic,
                    "asymptotic_relative_order_tolerance": (
                        ASYMPTOTIC_ORDER_RELATIVE_DIFFERENCE_MAX
                    ),
                    "asymptotic_absolute_order_tolerance": (
                        ASYMPTOTIC_ORDER_ABSOLUTE_DIFFERENCE_MAX
                    ),
                    "gci_eligible": bool(monotone and near_asymptotic),
                    "gci_computed": False,
                }
            )

    increasing = [
        row
        for row in rows
        if row["support_family"] == "increasing_neighbor"
    ]
    velocity_row = next(
        row for row in increasing if row["metric"] == "velocity_relative_l2"
    )
    ratio_limit = float(
        _nested(
            bundle.configuration,
            "space_convergence",
            "primary_trend",
            "n32_to_n16_velocity_relative_L2_ratio_maximum",
        )
    )
    slopes_positive = all(
        row["fitted_log_error_log_dx_slope"] is not None
        and float(row["fitted_log_error_log_dx_slope"]) > 0.0
        for row in increasing
    )
    velocity_ratio_pass = bool(
        velocity_row["ratio_n32_over_n16"] is not None
        and float(velocity_row["ratio_n32_over_n16"]) <= ratio_limit
    )
    all_primary_finite = all(
        bool(row["all_errors_finite_positive"]) for row in increasing
    ) and all(
        bool(item["trajectory_finite"])
        for item in endpoints_by_family["increasing_neighbor"]
    )
    primary_pass = bool(
        all_primary_finite and slopes_positive and velocity_ratio_pass
    )
    nonworsening = bool(
        all_primary_finite
        and all(
            row["fitted_log_error_log_dx_slope"] is not None
            and float(row["fitted_log_error_log_dx_slope"]) >= 0.0
            for row in increasing
        )
        and velocity_row["ratio_n32_over_n16"] is not None
        and float(velocity_row["ratio_n32_over_n16"]) < 1.0
    )
    plateau_conditional = bool(nonworsening and not primary_pass)
    support_complete = bool(
        len(rows) == 6
        and all(
            bool(item["trajectory_finite"])
            for family_endpoints in endpoints_by_family.values()
            for item in family_endpoints
        )
    )
    facts.update(
        {
            "execution_status": "COMPLETE",
            "not_run_reason": "",
            "primary_all_finite": all_primary_finite,
            "primary_all_selected_slopes_positive": slopes_positive,
            "primary_velocity_n32_n16_ratio": (
                velocity_row["ratio_n32_over_n16"]
            ),
            "primary_velocity_ratio_limit": ratio_limit,
            "primary_velocity_ratio_pass": velocity_ratio_pass,
            "primary_space_pass": primary_pass,
            "primary_nonworsening": nonworsening,
            "space_plateau_conditional": plateau_conditional,
            "support_family_comparison_complete": support_complete,
        }
    )
    return rows, facts


def evaluate_zero_flow(bundle: EvidenceBundle) -> dict[str, Any]:
    """Apply the preregistered 100-step zero-flow equilibrium gate."""

    config = _nested(bundle.configuration, "zero_flow")
    resolution = int(config["resolution"])
    dt = float(config["time_step"])
    steps = int(config["steps"])
    resolutions = _summary_numeric_values(bundle, "resolution", ("N",))
    dts = _summary_numeric_values(bundle, "dt", ("time_step",))
    row = _select_one(
        bundle.run_summary,
        (bundle.run_summary["_protocol"] == "zero_flow")
        & (resolutions == resolution)
        & np.isclose(
            dts,
            dt,
            rtol=2.0e-12,
            atol=FLOAT_TIME_ATOL,
        ),
        description=f"zero flow N={resolution}, dt={dt}",
    )
    run_id = str(row["_run_id"])
    sample = bundle.samples[run_id]
    path = bundle.sample_paths[run_id]
    pressure_tolerance = float(config["pressure_linf_tolerance"])
    if sample.empty:
        return {
            "run_id": run_id,
            "accepted": False,
            "required_steps": steps,
            "observed_sample_count": 0,
            "step_complete": False,
            "position_drift_linf_max": math.inf,
            "position_drift_tolerance": float(
                config["position_drift_tolerance"]
            ),
            "velocity_linf_max": math.inf,
            "velocity_linf_tolerance": float(
                config["velocity_linf_tolerance"]
            ),
            "pressure_absolute_maximum": math.inf,
            "pressure_linf_tolerance": pressure_tolerance,
            "pressure_pass": False,
            "relative_density_drift_max": math.inf,
            "relative_density_drift_tolerance": float(
                config["relative_density_drift_tolerance"]
            ),
            "all_state_values_finite": False,
            "topology_maxima": {
                column: math.inf for column in TOPOLOGY_SAMPLE_COLUMNS
            },
            "topology_pass": False,
            "failure_class": _row_text(
                row,
                bundle,
                "failure_class",
                ("stop_class",),
                required=False,
            ),
            "failure_reason": _row_text(
                row,
                bundle,
                "failure_reason",
                ("stop_reason",),
                required=False,
            ),
            "pass": False,
        }
    position = _sample_numeric(
        sample,
        "position_drift_linf",
        path=path,
    )
    velocity = _sample_numeric(sample, "velocity_linf", path=path)
    pressure = _sample_numeric(
        sample,
        "pressure_absolute_maximum",
        path=path,
    )
    density = _sample_numeric(
        sample,
        "relative_density_drift",
        path=path,
    )
    assert position is not None and velocity is not None
    assert pressure is not None and density is not None
    finite_flags = _bool_values(
        sample,
        "state_all_finite",
        ("finite", "all_finite"),
        required=False,
        source=str(path),
    )
    topology_maxima: dict[str, float] = {}
    for column in TOPOLOGY_SAMPLE_COLUMNS:
        values = _sample_numeric(sample, column, path=path)
        assert values is not None
        topology_maxima[column] = float(np.max(values))
    observed_steps = _sample_numeric(
        sample,
        "step",
        path=path,
        required=False,
    )
    step_complete = bool(
        len(sample) >= steps + 1
        and (
            observed_steps is None
            or (
                np.nanmin(observed_steps) <= 0.0
                and np.nanmax(observed_steps) >= steps
            )
        )
    )
    position_max = float(np.max(position))
    velocity_max = float(np.max(velocity))
    pressure_max = float(np.max(pressure))
    density_max = float(np.max(density))
    topology_pass = all(value == 0.0 for value in topology_maxima.values())
    finite_pass = bool(
        np.isfinite(position).all()
        and np.isfinite(velocity).all()
        and np.isfinite(pressure).all()
        and np.isfinite(density).all()
        and (finite_flags is None or finite_flags.all())
        and bundle.states[run_id] is not None
        and np.isfinite(bundle.states[run_id].velocities).all()
    )
    passed = bool(
        row["_accepted"]
        and step_complete
        and finite_pass
        and position_max <= float(config["position_drift_tolerance"])
        and velocity_max <= float(config["velocity_linf_tolerance"])
        and pressure_max <= pressure_tolerance
        and density_max <= float(config["relative_density_drift_tolerance"])
        and topology_pass
    )
    return {
        "run_id": run_id,
        "accepted": bool(row["_accepted"]),
        "required_steps": steps,
        "observed_sample_count": len(sample),
        "step_complete": step_complete,
        "position_drift_linf_max": position_max,
        "position_drift_tolerance": float(
            config["position_drift_tolerance"]
        ),
        "velocity_linf_max": velocity_max,
        "velocity_linf_tolerance": float(
            config["velocity_linf_tolerance"]
        ),
        "pressure_absolute_maximum": pressure_max,
        "pressure_linf_tolerance": pressure_tolerance,
        "pressure_pass": pressure_max <= pressure_tolerance,
        "relative_density_drift_max": density_max,
        "relative_density_drift_tolerance": float(
            config["relative_density_drift_tolerance"]
        ),
        "all_state_values_finite": finite_pass,
        "topology_maxima": topology_maxima,
        "topology_pass": topology_pass,
        "pass": passed,
    }


def evaluate_dynamic_conservation(
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    """Audit every sample belonging to every accepted trajectory."""

    config = _nested(
        bundle.configuration,
        "dynamic_conservation_thresholds",
    )
    pair_limit = float(config["maximum_relative_pair_force_residual"])
    total_limit = float(
        config[
            "maximum_characteristic_normalized_internal_force_residual"
        ]
    )
    power_limit = float(
        config["viscous_power_positive_absolute_tolerance"]
    )
    accepted_rows = bundle.run_summary[bundle.run_summary["_accepted"]]
    if accepted_rows.empty:
        return {
            "execution_status": "NOT_RUN",
            "not_run_reason": (
                "no accepted trajectory samples exist after the retained "
                "hard-gate failure"
            ),
            "accepted_run_count": 0,
            "accepted_sample_count": 0,
            "all_values_finite": False,
            "pair_limit": pair_limit,
            "pressure_pair_maximum": math.inf,
            "pressure_pair_maximum_run_id": None,
            "pressure_pair_pass": False,
            "viscosity_pair_maximum": math.inf,
            "viscosity_pair_maximum_run_id": None,
            "viscosity_pair_pass": False,
            "total_force_limit": total_limit,
            "total_force_maximum": math.inf,
            "total_force_maximum_run_id": None,
            "total_force_pass": False,
            "assembled_total_force_maximum": math.inf,
            "assembled_total_force_maximum_run_id": None,
            "assembled_total_force_pass": False,
            "assembly_consistency_maximum": math.inf,
            "assembly_consistency_maximum_run_id": None,
            "assembly_consistency_limit": (
                64.0
                * (
                    np.finfo(np.float64).eps
                    if _normal_token(
                        _nested(
                            bundle.configuration,
                            "backend",
                            "dtype",
                        )
                    )
                    == "float64"
                    else np.finfo(np.float32).eps
                )
            ),
            "assembly_consistency_pass": False,
            "accumulated_power_maximum": math.inf,
            "accumulated_power_maximum_run_id": None,
            "direct_power_maximum": None,
            "direct_power_maximum_run_id": None,
            "power_positive_absolute_limit": power_limit,
            "viscous_power_pass": False,
            "topology_maxima": {
                column: {"maximum": None, "run_id": None}
                for column in TOPOLOGY_SAMPLE_COLUMNS
            },
            "topology_pass": False,
            "pass": False,
        }
    maxima: dict[str, tuple[float, str]] = {}
    all_finite = True
    total_samples = 0
    topology_maxima = {
        column: (0.0, "")
        for column in TOPOLOGY_SAMPLE_COLUMNS
    }
    required_metrics = (
        "pressure_relative_pair_force_residual",
        "viscosity_relative_pair_force_residual",
        "relative_total_internal_force",
        "assembled_relative_internal_force",
        "assembly_force_consistency_relative_linf",
        "accumulated_viscous_power",
    )
    for _, row in accepted_rows.iterrows():
        run_id = str(row["_run_id"])
        sample = bundle.samples[run_id]
        path = bundle.sample_paths[run_id]
        total_samples += len(sample)
        for metric in required_metrics:
            values = _sample_numeric(sample, metric, path=path)
            assert values is not None
            if not np.isfinite(values).all():
                all_finite = False
                observed = float("inf")
            else:
                observed = float(np.max(values))
            previous = maxima.get(metric)
            if previous is None or observed > previous[0]:
                maxima[metric] = (observed, run_id)
        direct = _sample_numeric(
            sample,
            "pair_direct_viscous_power",
            path=path,
            required=False,
        )
        if direct is not None:
            observed = (
                float(np.max(direct))
                if np.isfinite(direct).all()
                else float("inf")
            )
            metric = "pair_direct_viscous_power"
            previous = maxima.get(metric)
            if previous is None or observed > previous[0]:
                maxima[metric] = (observed, run_id)
        finite_flags = _bool_values(
            sample,
            "state_all_finite",
            ("finite", "all_finite"),
            required=False,
            source=str(path),
        )
        if finite_flags is not None and not finite_flags.all():
            all_finite = False
        if not np.isfinite(bundle.states[run_id].velocities).all():
            all_finite = False
        for column in TOPOLOGY_SAMPLE_COLUMNS:
            values = _sample_numeric(sample, column, path=path)
            assert values is not None
            observed = (
                float(np.max(values))
                if np.isfinite(values).all()
                else float("inf")
            )
            if observed > topology_maxima[column][0]:
                topology_maxima[column] = (observed, run_id)

    pressure_pair_pass = bool(
        maxima["pressure_relative_pair_force_residual"][0] <= pair_limit
    )
    viscosity_pair_pass = bool(
        maxima["viscosity_relative_pair_force_residual"][0] <= pair_limit
    )
    total_force_pass = bool(
        maxima["relative_total_internal_force"][0] <= total_limit
    )
    assembled_force_pass = bool(
        maxima["assembled_relative_internal_force"][0] <= total_limit
    )
    dtype_name = _normal_token(
        _nested(bundle.configuration, "backend", "dtype")
    )
    if dtype_name == "float64":
        assembly_limit = 64.0 * np.finfo(np.float64).eps
    elif dtype_name == "float32":
        assembly_limit = 64.0 * np.finfo(np.float32).eps
    else:
        raise EvidenceError(f"unsupported backend dtype {dtype_name!r}")
    assembly_consistency_pass = bool(
        maxima["assembly_force_consistency_relative_linf"][0]
        <= assembly_limit
    )
    accumulated_power_pass = bool(
        maxima["accumulated_viscous_power"][0] <= power_limit
    )
    direct_power_pass = bool(
        "pair_direct_viscous_power" not in maxima
        or maxima["pair_direct_viscous_power"][0] <= power_limit
    )
    topology_pass = all(
        observed == 0.0
        for observed, _ in topology_maxima.values()
    )
    passed = bool(
        all_finite
        and pressure_pair_pass
        and viscosity_pair_pass
        and total_force_pass
        and assembled_force_pass
        and assembly_consistency_pass
        and accumulated_power_pass
        and direct_power_pass
        and topology_pass
    )
    return {
        "execution_status": "COMPLETE",
        "not_run_reason": "",
        "accepted_run_count": len(accepted_rows),
        "accepted_sample_count": total_samples,
        "all_values_finite": all_finite,
        "pressure_pair_maximum": maxima[
            "pressure_relative_pair_force_residual"
        ][0],
        "pressure_pair_maximum_run_id": maxima[
            "pressure_relative_pair_force_residual"
        ][1],
        "viscosity_pair_maximum": maxima[
            "viscosity_relative_pair_force_residual"
        ][0],
        "viscosity_pair_maximum_run_id": maxima[
            "viscosity_relative_pair_force_residual"
        ][1],
        "pair_limit": pair_limit,
        "pressure_pair_pass": pressure_pair_pass,
        "viscosity_pair_pass": viscosity_pair_pass,
        "total_force_maximum": maxima[
            "relative_total_internal_force"
        ][0],
        "total_force_maximum_run_id": maxima[
            "relative_total_internal_force"
        ][1],
        "total_force_limit": total_limit,
        "total_force_pass": total_force_pass,
        "assembled_total_force_maximum": maxima[
            "assembled_relative_internal_force"
        ][0],
        "assembled_total_force_maximum_run_id": maxima[
            "assembled_relative_internal_force"
        ][1],
        "assembled_total_force_pass": assembled_force_pass,
        "assembly_consistency_maximum": maxima[
            "assembly_force_consistency_relative_linf"
        ][0],
        "assembly_consistency_maximum_run_id": maxima[
            "assembly_force_consistency_relative_linf"
        ][1],
        "assembly_consistency_limit": assembly_limit,
        "assembly_consistency_pass": assembly_consistency_pass,
        "accumulated_power_maximum": maxima[
            "accumulated_viscous_power"
        ][0],
        "accumulated_power_maximum_run_id": maxima[
            "accumulated_viscous_power"
        ][1],
        "direct_power_maximum": (
            maxima.get("pair_direct_viscous_power", (None, None))[0]
        ),
        "direct_power_maximum_run_id": (
            maxima.get("pair_direct_viscous_power", (None, None))[1]
        ),
        "power_positive_absolute_limit": power_limit,
        "viscous_power_pass": (
            accumulated_power_pass and direct_power_pass
        ),
        "topology_maxima": topology_maxima,
        "topology_pass": topology_pass,
        "pass": passed,
    }


def _raw_numeric(
    frame: pd.DataFrame,
    canonical: str,
    *,
    source: str,
) -> np.ndarray:
    """Parse required numeric AD evidence while retaining NaN/Inf as data."""

    values = _series(frame, canonical, source=source)
    assert values is not None
    try:
        return pd.to_numeric(values, errors="raise").to_numpy(dtype=float)
    except Exception as error:
        raise EvidenceError(
            f"{source}.{canonical} contains nonnumeric values: {error}"
        ) from error


def _exact_text_column(
    frame: pd.DataFrame,
    canonical: str,
    expected: str,
    *,
    source: str,
) -> bool:
    values = _series(frame, canonical, source=source)
    assert values is not None
    return bool(
        values.notna().all()
        and (values.astype(str).to_numpy() == expected).all()
    )


def _exact_numeric_column(
    frame: pd.DataFrame,
    canonical: str,
    expected: float,
    *,
    source: str,
) -> bool:
    values = _raw_numeric(frame, canonical, source=source)
    return bool(np.isfinite(values).all() and (values == expected).all())


def _autograd_case_metadata(
    frame: pd.DataFrame,
    path: Path,
) -> dict[tuple[str, int], tuple[float, float]]:
    source = str(path)
    parameters_series = _series(frame, "parameter", source=source)
    assert parameters_series is not None
    if (
        parameters_series.isna().any()
        or (parameters_series.astype(str).str.strip() == "").any()
    ):
        raise EvidenceError(f"{source}.parameter contains missing values")
    raw_steps = _raw_numeric(frame, "steps", source=source)
    if not (
        np.isfinite(raw_steps).all()
        and (raw_steps == np.rint(raw_steps)).all()
    ):
        raise EvidenceError(f"{source}.steps must contain exact integers")
    parameter_values = _raw_numeric(
        frame,
        "parameter_value",
        source=source,
    )
    finite_difference_steps = _raw_numeric(
        frame,
        "finite_difference_step",
        source=source,
    )
    keys = list(
        zip(
            parameters_series.astype(str).tolist(),
            raw_steps.astype(int).tolist(),
        )
    )
    if len(set(keys)) != len(keys):
        raise EvidenceError(f"{source}: duplicate parameter/steps rows")
    return {
        key: (float(parameter_value), float(fd_step))
        for key, parameter_value, fd_step in zip(
            keys,
            parameter_values,
            finite_difference_steps,
        )
    }


def _evaluate_autograd_table(
    frame: pd.DataFrame,
    path: Path,
    *,
    expected_parameters: set[str] | None,
    expected_steps: set[int],
    short_steps: set[int],
    short_relative_limit: float,
    machine_epsilon: float,
) -> dict[str, Any]:
    source = str(path)
    parameter = _series(frame, "parameter", source=source)
    assert parameter is not None
    if (
        parameter.isna().any()
        or (parameter.astype(str).str.strip() == "").any()
    ):
        raise EvidenceError(f"{source}.parameter contains missing values")
    steps_values = _raw_numeric(frame, "steps", source=source)
    declared_finite = _bool_values(frame, "finite", source=source)
    declared_nonzero = _bool_values(frame, "nonzero", source=source)
    declared_relative = _raw_numeric(
        frame,
        "relative_difference",
        source=source,
    )
    declared_threshold = _bool_values(
        frame,
        "AD_FD_threshold_applies",
        source=source,
    )
    declared_status = _series(frame, "status", source=source)
    topology_claim = _bool_values(
        frame,
        "topology_differentiability_claimed",
        source=source,
    )
    loss = _raw_numeric(frame, "loss", source=source)
    autograd_gradient = _raw_numeric(
        frame,
        "autograd_gradient",
        source=source,
    )
    gradient_norm = _raw_numeric(
        frame,
        "gradient_norm",
        source=source,
    )
    finite_difference_gradient = _raw_numeric(
        frame,
        "finite_difference_gradient",
        source=source,
    )
    assert declared_finite is not None
    assert declared_nonzero is not None
    assert declared_threshold is not None
    assert declared_status is not None
    assert topology_claim is not None

    parameters = parameter.astype(str).to_numpy()
    steps_integral = bool(
        np.isfinite(steps_values).all()
        and (steps_values == np.rint(steps_values)).all()
    )
    steps = np.full(len(frame), np.iinfo(np.int64).min, dtype=np.int64)
    valid_steps = np.isfinite(steps_values) & (
        steps_values == np.rint(steps_values)
    )
    steps[valid_steps] = steps_values[valid_steps].astype(np.int64)

    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        denominator = np.maximum(
            np.maximum(
                np.abs(autograd_gradient),
                np.abs(finite_difference_gradient),
            ),
            1.0e-12,
        )
        computed_relative = (
            np.abs(autograd_gradient - finite_difference_gradient)
            / denominator
        )
    computed_finite = (
        np.isfinite(loss)
        & np.isfinite(autograd_gradient)
        & np.isfinite(finite_difference_gradient)
        & np.isfinite(computed_relative)
    )
    computed_nonzero = np.abs(autograd_gradient) > machine_epsilon
    computed_threshold = np.isin(steps, list(short_steps))
    computed_status = (
        computed_finite
        & computed_nonzero
        & (
            (~computed_threshold)
            | (computed_relative <= short_relative_limit)
        )
    )
    relative_match = np.isclose(
        declared_relative,
        computed_relative,
        rtol=32.0 * machine_epsilon,
        atol=0.0,
        equal_nan=True,
    )
    gradient_norm_match = np.isclose(
        gradient_norm,
        np.abs(autograd_gradient),
        rtol=32.0 * machine_epsilon,
        atol=0.0,
        equal_nan=True,
    )
    finite_match = declared_finite == computed_finite
    nonzero_match = declared_nonzero == computed_nonzero
    threshold_match = declared_threshold == computed_threshold
    expected_status = np.where(computed_status, "PASS", "FAIL")
    status_match = (
        declared_status.astype(str).str.strip().to_numpy()
        == expected_status
    )
    declaration_consistency = (
        relative_match
        & gradient_norm_match
        & finite_match
        & nonzero_match
        & threshold_match
        & status_match
    )

    actual_parameters = set(parameters.tolist())
    parameter_pass = (
        len(actual_parameters) == 4
        if expected_parameters is None
        else actual_parameters == expected_parameters
    )
    combinations = set(zip(parameters.tolist(), steps.tolist()))
    expected_combinations = {
        (name, step)
        for name in (
            actual_parameters
            if expected_parameters is None
            else expected_parameters
        )
        for step in expected_steps
    }
    expected_row_count = len(expected_combinations)
    matrix_complete = bool(
        len(frame) == expected_row_count
        and parameter_pass
        and steps_integral
        and set(steps.tolist()) == expected_steps
        and combinations == expected_combinations
    )
    short_mask = np.isin(steps, list(short_steps))
    long_mask = steps == max(expected_steps)
    expected_short_count = len(
        actual_parameters
        if expected_parameters is None
        else expected_parameters
    ) * len(short_steps)
    expected_long_count = len(
        actual_parameters
        if expected_parameters is None
        else expected_parameters
    )
    short_pass = bool(
        short_mask.sum() == expected_short_count
        and computed_finite[short_mask].all()
        and computed_nonzero[short_mask].all()
        and np.isfinite(computed_relative[short_mask]).all()
        and (
            computed_relative[short_mask] <= short_relative_limit
        ).all()
    )
    long_pass = bool(
        long_mask.sum() == expected_long_count
        and computed_finite[long_mask].all()
        and computed_nonzero[long_mask].all()
    )
    status_pass_count = int(computed_status.sum())
    declared_status_pass_count = int(
        (declared_status.astype(str).str.strip() == "PASS").sum()
    )
    topology_disclaimed = bool((~topology_claim).all())
    declarations_match_raw = bool(declaration_consistency.all())
    passed = bool(
        matrix_complete
        and short_pass
        and long_pass
        and status_pass_count == expected_row_count
        and declarations_match_raw
        and topology_disclaimed
    )
    return {
        "row_count": len(frame),
        "status_pass_count": status_pass_count,
        "declared_status_pass_count": declared_status_pass_count,
        "parameters": sorted(actual_parameters),
        "steps": sorted(
            int(value)
            for value in set(steps.tolist())
            if value != np.iinfo(np.int64).min
        ),
        "steps_are_exact_integers": steps_integral,
        "matrix_complete": matrix_complete,
        "short_row_count": int(short_mask.sum()),
        "short_maximum_relative_difference": (
            float(np.max(computed_relative[short_mask]))
            if short_mask.any()
            and np.isfinite(computed_relative[short_mask]).all()
            else None
        ),
        "short_relative_limit": short_relative_limit,
        "short_pass": short_pass,
        "step_16_row_count": int(long_mask.sum()),
        "step_16_finite_nonzero_pass": long_pass,
        "finite_declaration_match": bool(finite_match.all()),
        "nonzero_declaration_match": bool(nonzero_match.all()),
        "relative_difference_recomputed_match": bool(
            relative_match.all()
        ),
        "gradient_norm_recomputed_match": bool(
            gradient_norm_match.all()
        ),
        "threshold_declaration_match": bool(threshold_match.all()),
        "status_recomputed_match": bool(status_match.all()),
        "declaration_consistency_pass": declarations_match_raw,
        "declaration_mismatch_rows": np.flatnonzero(
            ~declaration_consistency
        ).astype(int).tolist(),
        "topology_differentiability_disclaimed": topology_disclaimed,
        "pass": passed,
        "source": str(path),
    }


def evaluate_autograd(bundle: EvidenceBundle) -> dict[str, Any]:
    """Require current Stage 01C 20/20 and full-dynamic 20/20."""

    config = _nested(bundle.configuration, "dynamic_autograd")
    steps = {int(value) for value in config["steps"]}
    parameters = {
        _normal_token(value)
        for value in config["parameters"].keys()
    }
    short_steps = {1, 3, 5, 8}
    limit = float(
        config["qualification"][
            "short_steps_maximum_AD_FD_relative_difference"
        ]
    )
    dtype_name = _normal_token(
        _nested(bundle.configuration, "backend", "dtype")
    )
    if dtype_name == "float64":
        machine_epsilon = float(np.finfo(np.float64).eps)
    elif dtype_name == "float32":
        machine_epsilon = float(np.finfo(np.float32).eps)
    else:
        raise EvidenceError(f"unsupported backend dtype {dtype_name!r}")
    topology_preregistered_false = (
        config["qualification"]["topology_differentiability_claimed"]
        is False
    )
    actual_config_hash = hashlib.sha256(
        (
            bundle.experiment_root
            / "configs"
            / "preregistered_primary_tgv.yml"
        ).read_bytes()
    ).hexdigest()
    git_column = _summary_column(bundle, "git_hash")
    assert git_column is not None
    summary_git_hashes = sorted(
        set(bundle.run_summary[git_column].astype(str).tolist())
    )
    expected_git_hash = (
        summary_git_hashes[0] if len(summary_git_hashes) == 1 else None
    )

    baseline_stage01c = _evaluate_autograd_table(
        bundle.stage01c_baseline,
        bundle.stage01c_baseline_path,
        expected_parameters=None,
        expected_steps=steps,
        short_steps=short_steps,
        short_relative_limit=limit,
        machine_epsilon=machine_epsilon,
    )
    baseline_parameters = set(baseline_stage01c["parameters"])
    dynamic = _evaluate_autograd_table(
        bundle.dynamic_autograd,
        bundle.dynamic_autograd_path,
        expected_parameters=parameters,
        expected_steps=steps,
        short_steps=short_steps,
        short_relative_limit=limit,
        machine_epsilon=machine_epsilon,
    )
    current_stage01c = _evaluate_autograd_table(
        bundle.stage01c_regression,
        bundle.stage01c_regression_path,
        expected_parameters=baseline_parameters,
        expected_steps=steps,
        short_steps=short_steps,
        short_relative_limit=limit,
        machine_epsilon=machine_epsilon,
    )
    dynamic_source = str(bundle.dynamic_autograd_path)
    dynamic_parameter = _series(
        bundle.dynamic_autograd,
        "parameter",
        source=dynamic_source,
    )
    dynamic_values = _raw_numeric(
        bundle.dynamic_autograd,
        "parameter_value",
        source=dynamic_source,
    )
    dynamic_fd_steps = _raw_numeric(
        bundle.dynamic_autograd,
        "finite_difference_step",
        source=dynamic_source,
    )
    assert dynamic_parameter is not None
    dynamic_parameter_metadata_pass = True
    for parameter_name, parameter_config in config["parameters"].items():
        mask = dynamic_parameter.astype(str).to_numpy() == parameter_name
        dynamic_parameter_metadata_pass = bool(
            dynamic_parameter_metadata_pass
            and int(mask.sum()) == len(steps)
            and np.isfinite(dynamic_values[mask]).all()
            and (
                dynamic_values[mask]
                == float(parameter_config["base_value"])
            ).all()
            and np.isfinite(dynamic_fd_steps[mask]).all()
            and (
                dynamic_fd_steps[mask]
                == float(parameter_config["finite_difference_step"])
            ).all()
        )
    dynamic_metadata_checks = {
        "parameter_values_and_fd_steps_exact": (
            dynamic_parameter_metadata_pass
        ),
        "resolution_exact": _exact_numeric_column(
            bundle.dynamic_autograd,
            "resolution",
            float(config["resolution"]),
            source=dynamic_source,
        ),
        "support_ratio_exact": _exact_numeric_column(
            bundle.dynamic_autograd,
            "support_ratio",
            float(config["support_ratio"]),
            source=dynamic_source,
        ),
        "time_step_exact": _exact_numeric_column(
            bundle.dynamic_autograd,
            "time_step",
            float(config["time_step"]),
            source=dynamic_source,
        ),
        "gradient_scope_exact": _exact_text_column(
            bundle.dynamic_autograd,
            "gradient_scope",
            "rebuilt_neighbor_indices_continuous_tensor_value_path",
            source=dynamic_source,
        ),
        "density_scalar_scope_exact": _exact_text_column(
            bundle.dynamic_autograd,
            "density_scalar_scope",
            "EOS_reference_density_only_with_fixed_baseline_masses",
            source=dynamic_source,
        ),
        "git_hash_exact": bool(
            expected_git_hash is not None
            and _exact_text_column(
                bundle.dynamic_autograd,
                "git_hash",
                expected_git_hash,
                source=dynamic_source,
            )
        ),
        "config_sha256_exact": _exact_text_column(
            bundle.dynamic_autograd,
            "config_sha256",
            actual_config_hash,
            source=dynamic_source,
        ),
    }
    dynamic["metadata_checks"] = dynamic_metadata_checks
    dynamic["metadata_pass"] = bool(
        all(dynamic_metadata_checks.values())
    )
    dynamic["numerical_pass"] = bool(dynamic["pass"])
    dynamic["pass"] = bool(
        dynamic["numerical_pass"]
        and dynamic["metadata_pass"]
        and topology_preregistered_false
    )

    current_source = str(bundle.stage01c_regression_path)
    current_metadata_checks = {
        "regression_context_exact": _exact_text_column(
            bundle.stage01c_regression,
            "regression_context",
            "stage01d_no_regression_check",
            source=current_source,
        ),
        "gradient_scope_exact": _exact_text_column(
            bundle.stage01c_regression,
            "gradient_scope",
            "fixed_neighbor_indices_and_geometry_value_path",
            source=current_source,
        ),
        "git_hash_exact": bool(
            expected_git_hash is not None
            and _exact_text_column(
                bundle.stage01c_regression,
                "git_hash",
                expected_git_hash,
                source=current_source,
            )
        ),
        "stage01d_config_sha256_exact": _exact_text_column(
            bundle.stage01c_regression,
            "stage01d_config_sha256",
            actual_config_hash,
            source=current_source,
        ),
    }
    current_stage01c["metadata_checks"] = current_metadata_checks
    current_stage01c["metadata_pass"] = bool(
        all(current_metadata_checks.values())
    )
    current_stage01c["numerical_pass"] = bool(
        current_stage01c["pass"]
    )
    current_stage01c["pass"] = bool(
        current_stage01c["numerical_pass"]
        and current_stage01c["metadata_pass"]
        and topology_preregistered_false
    )

    current_case_metadata = _autograd_case_metadata(
        bundle.stage01c_regression,
        bundle.stage01c_regression_path,
    )
    baseline_case_metadata = _autograd_case_metadata(
        bundle.stage01c_baseline,
        bundle.stage01c_baseline_path,
    )
    current_keys = set(current_case_metadata)
    baseline_keys = set(baseline_case_metadata)
    case_metadata_match = (
        current_case_metadata == baseline_case_metadata
    )
    baseline_crosscheck = bool(
        baseline_stage01c["pass"]
        and current_keys == baseline_keys
        and case_metadata_match
    )
    passed = bool(
        dynamic["pass"]
        and current_stage01c["pass"]
        and baseline_crosscheck
        and topology_preregistered_false
    )
    return {
        "dynamic": dynamic,
        "current_stage01c": current_stage01c,
        "frozen_stage01c_baseline": baseline_stage01c,
        "stage01c_parameter_step_keys_match_baseline": (
            current_keys == baseline_keys
        ),
        "stage01c_parameter_values_and_fd_steps_match_baseline": (
            case_metadata_match
        ),
        "baseline_crosscheck_pass": baseline_crosscheck,
        "expected_git_hash": expected_git_hash,
        "observed_run_summary_git_hashes": summary_git_hashes,
        "actual_stage01d_config_sha256": actual_config_hash,
        "topology_differentiability_preregistered_false": (
            topology_preregistered_false
        ),
        "pass": passed,
    }


def _run_topology_pass(
    bundle: EvidenceBundle,
    run_id: str,
) -> bool:
    sample = bundle.samples[run_id]
    path = bundle.sample_paths[run_id]
    if sample.empty:
        return False
    for column in TOPOLOGY_SAMPLE_COLUMNS:
        values = _sample_numeric(sample, column, path=path)
        assert values is not None
        if not np.isfinite(values).all() or np.any(values != 0.0):
            return False
    return True


def _run_core_sample_gates(
    bundle: EvidenceBundle,
    row: pd.Series,
) -> dict[str, Any]:
    run_id = str(row["_run_id"])
    sample = bundle.samples[run_id]
    path = bundle.sample_paths[run_id]
    conservation = _nested(
        bundle.configuration,
        "dynamic_conservation_thresholds",
    )
    resource = _nested(bundle.configuration, "resource_stopping")
    summary_rss_column = _summary_column(
        bundle,
        "peak_rss_bytes",
        ("maximum_rss_bytes",),
    )
    assert summary_rss_column is not None
    summary_peak_rss = _finite_float_or_none(row[summary_rss_column])
    summary_peak_rss_finite = summary_peak_rss is not None
    cluster_limit = float(
        _nested(
            bundle.configuration,
            "particle_clustering_diagnostic",
            "minimum_separation_over_dx",
        )
    )
    if sample.empty:
        return {
            "evidence_available": False,
            "finite_pass": False,
            "topology_pass": False,
            "pressure_pair_pass": False,
            "viscosity_pair_pass": False,
            "total_force_pass": False,
            "assembled_total_force_pass": False,
            "assembly_consistency_pass": False,
            "viscous_power_pass": False,
            "sample_peak_rss_bytes": None,
            "summary_peak_rss_bytes": summary_peak_rss,
            "summary_peak_rss_finite": summary_peak_rss_finite,
            "effective_peak_rss_bytes": summary_peak_rss,
            "rss_pass": False,
            "thermal_pass": False,
            "memory_pressure_pass": False,
            "memory_growth_pass": False,
            "minimum_separation_over_dx": None,
            "minimum_separation_over_dx_limit": cluster_limit,
            "clustering_pass": False,
            "pass": False,
        }
    resolution = int(
        _row_number(row, bundle, "resolution", ("N",))
    )
    dx = 2.0 / resolution
    pressure = _sample_numeric(
        sample,
        "pressure_relative_pair_force_residual",
        path=path,
    )
    viscosity = _sample_numeric(
        sample,
        "viscosity_relative_pair_force_residual",
        path=path,
    )
    total_force = _sample_numeric(
        sample,
        "relative_total_internal_force",
        path=path,
    )
    assembled_force = _sample_numeric(
        sample,
        "assembled_relative_internal_force",
        path=path,
    )
    assembly_consistency = _sample_numeric(
        sample,
        "assembly_force_consistency_relative_linf",
        path=path,
    )
    power = _sample_numeric(
        sample,
        "accumulated_viscous_power",
        path=path,
    )
    rss = _sample_numeric(sample, "peak_rss_bytes", path=path)
    thermal = _sample_numeric(
        sample,
        "thermal_slowdown_fraction",
        path=path,
    )
    separation = _sample_numeric(
        sample,
        "minimum_separation",
        path=path,
    )
    finite_flags = _bool_values(
        sample,
        "state_all_finite",
        ("finite", "all_finite"),
        required=False,
        source=str(path),
    )
    assert pressure is not None
    assert viscosity is not None
    assert total_force is not None
    assert assembled_force is not None
    assert assembly_consistency is not None
    assert power is not None and rss is not None and separation is not None
    sample_peak_rss = (
        float(np.max(rss)) if np.isfinite(rss).all() else None
    )
    effective_peak_rss = (
        max(sample_peak_rss, summary_peak_rss)
        if sample_peak_rss is not None
        and summary_peak_rss is not None
        else (
            sample_peak_rss
            if sample_peak_rss is not None
            else summary_peak_rss
        )
    )
    finite_pass = bool(
        np.isfinite(pressure).all()
        and np.isfinite(viscosity).all()
        and np.isfinite(total_force).all()
        and np.isfinite(assembled_force).all()
        and np.isfinite(assembly_consistency).all()
        and np.isfinite(power).all()
        and np.isfinite(rss).all()
        and summary_peak_rss_finite
        and np.isfinite(separation).all()
        and (finite_flags is None or finite_flags.all())
        and bundle.states[run_id] is not None
        and np.isfinite(bundle.states[run_id].velocities).all()
    )
    topology_pass = _run_topology_pass(bundle, run_id)
    pair_limit = float(
        conservation["maximum_relative_pair_force_residual"]
    )
    total_limit = float(
        conservation[
            "maximum_characteristic_normalized_internal_force_residual"
        ]
    )
    power_limit = float(
        conservation["viscous_power_positive_absolute_tolerance"]
    )
    rss_limit = int(resource["peak_rss_bytes"])
    thermal_limit = float(
        resource["second_half_mean_step_time_increase_fraction"]
    )
    dtype_name = _normal_token(
        _nested(bundle.configuration, "backend", "dtype")
    )
    if dtype_name == "float64":
        assembly_limit = 64.0 * np.finfo(np.float64).eps
    elif dtype_name == "float32":
        assembly_limit = 64.0 * np.finfo(np.float32).eps
    else:
        raise EvidenceError(f"unsupported backend dtype {dtype_name!r}")
    minimum_ratio = float(np.min(separation / dx))
    resource_policy = _resource_policy_for_run(bundle, row)
    result = {
        "evidence_available": True,
        "finite_pass": finite_pass,
        "topology_pass": topology_pass,
        "pressure_pair_pass": bool(np.max(pressure) <= pair_limit),
        "viscosity_pair_pass": bool(np.max(viscosity) <= pair_limit),
        "total_force_pass": bool(np.max(total_force) <= total_limit),
        "assembled_total_force_pass": bool(
            np.max(assembled_force) <= total_limit
        ),
        "assembly_consistency_pass": bool(
            np.max(assembly_consistency) <= assembly_limit
        ),
        "viscous_power_pass": bool(np.max(power) <= power_limit),
        "sample_peak_rss_bytes": sample_peak_rss,
        "summary_peak_rss_bytes": summary_peak_rss,
        "summary_peak_rss_finite": summary_peak_rss_finite,
        "effective_peak_rss_bytes": effective_peak_rss,
        "rss_pass": bool(
            summary_peak_rss_finite
            and sample_peak_rss is not None
            and effective_peak_rss is not None
            and effective_peak_rss <= rss_limit
        ),
        "thermal_pass": bool(
            thermal is not None
            and np.isfinite(thermal).any()
            and np.nanmax(thermal) <= thermal_limit
        ),
        "memory_pressure_pass": bool(
            resource_policy["evidence_complete"]
            and resource_policy["sustained_memory_pressure"] is False
        ),
        "memory_growth_pass": bool(
            resource_policy["evidence_complete"]
            and resource_policy["memory_growth_with_step"] is False
        ),
        "minimum_separation_over_dx": minimum_ratio,
        "minimum_separation_over_dx_limit": cluster_limit,
        "clustering_pass": minimum_ratio >= cluster_limit,
    }
    result["pass"] = bool(
        row["_accepted"] and all(bool(value) for key, value in result.items()
        if key.endswith("_pass"))
    )
    return result


def _aggregate(values: Sequence[float]) -> dict[str, float | None]:
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not np.isfinite(array).all():
        return {
            "mean": None,
            "std": None,
            "median": None,
            "maximum": None,
        }
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array, ddof=1)) if array.size > 1 else 0.0,
        "median": float(np.median(array)),
        "maximum": float(np.max(array)),
    }


def evaluate_disorder(
    bundle: EvidenceBundle,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aggregate the fixed seven-run dynamic disorder matrix."""

    config = _nested(bundle.configuration, "disorder_robustness")
    resolution = int(config["resolution"])
    dt = float(config["time_step"])
    support_ratio = float(config["support_ratio"])
    final_time = float(config["final_time"])
    expected_layouts = {
        _canonical_layout(layout): [int(seed) for seed in seeds]
        for layout, seeds in config["layouts"].items()
    }
    resolutions = _summary_numeric_values(bundle, "resolution", ("N",))
    dts = _summary_numeric_values(bundle, "dt", ("time_step",))
    supports = _summary_numeric_values(
        bundle,
        "support_ratio",
        ("H_over_dx", "h_dx"),
    )
    seeds = _summary_numeric_values(bundle, "seed", ("random_seed",))
    selected: dict[str, list[tuple[pd.Series, dict[str, Any]]]] = {
        layout: [] for layout in expected_layouts
    }
    for layout, layout_seeds in expected_layouts.items():
        for seed in layout_seeds:
            mask = (
                (
                    bundle.run_summary["_protocol"]
                    == "disorder_robustness"
                )
                & (bundle.run_summary["_layout"] == layout)
                & (resolutions == resolution)
                & np.isclose(
                    dts,
                    dt,
                    rtol=2.0e-12,
                    atol=FLOAT_TIME_ATOL,
                )
                & np.isclose(
                    supports,
                    support_ratio,
                    rtol=2.0e-12,
                    atol=FLOAT_TIME_ATOL,
                )
                & (seeds == seed)
            )
            row = _select_one(
                bundle.run_summary,
                mask,
                description=f"disorder {layout}, seed={seed}",
            )
            endpoint = _endpoint_metrics(
                bundle,
                row,
                final_time=final_time,
                allow_last_available=True,
            )
            endpoint["seed"] = seed
            endpoint["topology_pass"] = _run_topology_pass(
                bundle,
                str(row["_run_id"]),
            )
            endpoint["core_gates"] = _run_core_sample_gates(
                bundle,
                row,
            )
            endpoint["case_pass"] = bool(
                row["_accepted"]
                and endpoint["trajectory_finite"]
                and endpoint["topology_pass"]
                and endpoint["core_gates"]["pass"]
            )
            endpoint["failure_class"] = _row_text(
                row,
                bundle,
                "failure_class",
                ("stop_class",),
                required=False,
            )
            endpoint["failure_reason"] = _row_text(
                row,
                bundle,
                "failure_reason",
                ("stop_reason",),
                required=False,
            )
            endpoint["failure_evidence_path"] = _row_text(
                row,
                bundle,
                "failure_evidence_path",
                ("failure_path",),
                required=False,
            )
            selected[layout].append((row, endpoint))

    rows: list[dict[str, Any]] = []
    layout_passes: dict[str, bool] = {}
    velocity_multiplier_text = " ".join(
        str(value)
        for value in config["insufficient_robustness_if"]
    )
    multiplier_matches = re.findall(
        r"(?:exceeds?|超过)\s*([0-9]+(?:\.[0-9]+)?)\s*"
        r"(?:times?|倍)",
        velocity_multiplier_text,
        flags=re.IGNORECASE,
    )
    if len(multiplier_matches) != 1:
        raise EvidenceError(
            "cannot extract unique 10% jitter velocity-error multiplier "
            "from disorder_robustness.insufficient_robustness_if"
        )
    velocity_multiplier = float(multiplier_matches[0])
    for layout, cases in selected.items():
        endpoints = [endpoint for _, endpoint in cases]
        accepted_count = sum(bool(row["_accepted"]) for row, _ in cases)
        finite_count = sum(
            bool(endpoint["trajectory_finite"]) for endpoint in endpoints
        )
        available_finite_count = sum(
            bool(endpoint["available_trajectory_finite"])
            for endpoint in endpoints
        )
        topology_count = sum(
            bool(endpoint["topology_pass"]) for endpoint in endpoints
        )
        core_gate_count = sum(
            bool(endpoint["core_gates"]["pass"]) for endpoint in endpoints
        )
        layout_pass = bool(
            len(cases) == len(expected_layouts[layout])
            and accepted_count == len(cases)
            and finite_count == len(cases)
            and topology_count == len(cases)
            and core_gate_count == len(cases)
        )
        layout_passes[layout] = layout_pass
        metric_aggregates = {
            metric: _aggregate(
                [
                    float(endpoint[metric])
                    for endpoint in endpoints
                    if endpoint[metric] is not None
                    and math.isfinite(float(endpoint[metric]))
                ]
            )
            for metric in (
                "velocity_relative_l2",
                "modal_amplitude_error",
                "kinetic_energy_error",
                "density_fluctuation_relative_rms",
                "momentum_drift_normalized",
                "minimum_separation",
                "neighbor_count_mean",
                "neighbor_count_min",
                "neighbor_count_max",
            )
        }
        failed_times: list[float] = []
        failed_cases = [
            (run, endpoint)
            for run, endpoint in cases
            if not bool(endpoint["case_pass"])
        ]
        for run, endpoint in failed_cases:
            if endpoint["failure_class"] is None:
                endpoint["failure_class"] = (
                    "PARTIAL_TRAJECTORY"
                    if endpoint["partial_trajectory"]
                    else "EVALUATOR_GATE_FAILURE"
                )
            if endpoint["failure_reason"] is None:
                failed_gates = sorted(
                    key
                    for key, value in endpoint["core_gates"].items()
                    if key.endswith("_pass") and not bool(value)
                )
                endpoint["failure_reason"] = (
                    "no complete requested endpoint"
                    if endpoint["partial_trajectory"]
                    else "failed evaluator gates: "
                    + ",".join(failed_gates)
                )
            if bool(run["_accepted"]):
                continue
            failure_time = _row_number(
                run,
                bundle,
                "first_failure_time",
                ("failure_time",),
                required=False,
            )
            if failure_time is not None:
                failed_times.append(failure_time)
        output: dict[str, Any] = {
            "layout": layout,
            "expected_seed_count": len(expected_layouts[layout]),
            "observed_seed_count": len(cases),
            "seeds": ";".join(
                str(value) for value in expected_layouts[layout]
            ),
            "accepted_count": accepted_count,
            "finite_count": finite_count,
            "available_finite_count": available_finite_count,
            "topology_pass_count": topology_count,
            "core_gate_pass_count": core_gate_count,
            "summary_peak_rss_finite_count": sum(
                bool(endpoint["core_gates"]["summary_peak_rss_finite"])
                for endpoint in endpoints
            ),
            "maximum_sample_peak_rss_bytes": max(
                (
                    float(value)
                    for value in (
                        endpoint["core_gates"]["sample_peak_rss_bytes"]
                        for endpoint in endpoints
                    )
                    if value is not None
                ),
                default=None,
            ),
            "maximum_summary_post_archive_peak_rss_bytes": max(
                (
                    float(value)
                    for value in (
                        endpoint["core_gates"]["summary_peak_rss_bytes"]
                        for endpoint in endpoints
                    )
                    if value is not None
                ),
                default=None,
            ),
            "maximum_effective_peak_rss_bytes": max(
                (
                    float(value)
                    for value in (
                        endpoint["core_gates"]["effective_peak_rss_bytes"]
                        for endpoint in endpoints
                    )
                    if value is not None
                ),
                default=None,
            ),
            "requested_endpoint_count": sum(
                bool(endpoint["endpoint_is_requested_final"])
                for endpoint in endpoints
            ),
            "partial_run_count": sum(
                bool(endpoint["partial_trajectory"])
                for endpoint in endpoints
            ),
            "partial_run_ids": [
                endpoint["run_id"]
                for endpoint in endpoints
                if endpoint["partial_trajectory"]
            ],
            "last_available_times": {
                str(endpoint["run_id"]): endpoint["endpoint_time"]
                for endpoint in endpoints
            },
            "failure_count": len(failed_cases),
            "failure_run_ids": [
                endpoint["run_id"] for _, endpoint in failed_cases
            ],
            "failure_classes": {
                str(endpoint["run_id"]): endpoint["failure_class"]
                for _, endpoint in failed_cases
            },
            "failure_reasons": {
                str(endpoint["run_id"]): endpoint["failure_reason"]
                for _, endpoint in failed_cases
            },
            "failure_evidence_paths": {
                str(endpoint["run_id"]): endpoint[
                    "failure_evidence_path"
                ]
                for _, endpoint in failed_cases
            },
            "first_failure_time": (
                min(failed_times) if failed_times else None
            ),
            "layout_pass": layout_pass,
            "minimum_separation_over_dx": (
                min(
                    float(value)
                    for value in (
                        endpoint["core_gates"][
                            "minimum_separation_over_dx"
                        ]
                        for endpoint in endpoints
                    )
                    if value is not None
                    and math.isfinite(float(value))
                )
                if any(
                    endpoint["core_gates"][
                        "minimum_separation_over_dx"
                    ]
                    is not None
                    and math.isfinite(
                        float(
                            endpoint["core_gates"][
                                "minimum_separation_over_dx"
                            ]
                        )
                    )
                    for endpoint in endpoints
                )
                else None
            ),
        }
        for metric, aggregate in metric_aggregates.items():
            for statistic, value in aggregate.items():
                output[f"{metric}_{statistic}"] = value
        rows.append(output)

    complete = all(
        len(selected[layout]) == len(seeds_for_layout)
        for layout, seeds_for_layout in expected_layouts.items()
    )
    unsampled_failure_run_ids = [
        str(endpoint["run_id"])
        for cases in selected.values()
        for _, endpoint in cases
        if endpoint["endpoint_time"] is None
    ]
    sampled_failure_evidence_complete = (
        len(unsampled_failure_run_ids) == 0
    )
    regular_pass = bool(layout_passes.get("regular", False))
    jitter_05_pass = bool(layout_passes.get("jitter_05", False))
    regular_velocity_values = [
        float(endpoint["velocity_relative_l2"])
        for _, endpoint in selected["regular"]
        if endpoint["velocity_relative_l2"] is not None
        and math.isfinite(float(endpoint["velocity_relative_l2"]))
    ]
    jitter_10_velocity_values = [
        float(endpoint["velocity_relative_l2"])
        for _, endpoint in selected["jitter_10"]
        if endpoint["velocity_relative_l2"] is not None
        and math.isfinite(float(endpoint["velocity_relative_l2"]))
    ]
    regular_velocity = (
        max(regular_velocity_values) if regular_velocity_values else None
    )
    jitter_10_velocity = (
        max(jitter_10_velocity_values)
        if jitter_10_velocity_values
        else None
    )
    if regular_velocity is None or jitter_10_velocity is None:
        velocity_ratio = None
    elif regular_velocity > 0.0:
        velocity_ratio = jitter_10_velocity / regular_velocity
    else:
        velocity_ratio = (
            0.0 if jitter_10_velocity == 0.0 else float("inf")
        )
    jitter_10_velocity_pass = bool(
        velocity_ratio is not None
        and math.isfinite(velocity_ratio)
        and velocity_ratio <= velocity_multiplier
    )
    jitter_10_pass = bool(
        layout_passes.get("jitter_10", False)
        and jitter_10_velocity_pass
    )
    robustness_pass = bool(
        complete and regular_pass and jitter_05_pass and jitter_10_pass
    )
    facts = {
        "execution_status": "COMPLETE",
        "not_run_reason": "",
        "complete": complete,
        "regular_pass": regular_pass,
        "jitter_05_pass": jitter_05_pass,
        "jitter_10_pass": jitter_10_pass,
        "jitter_10_max_velocity_relative_l2": jitter_10_velocity,
        "regular_velocity_relative_l2": regular_velocity,
        "jitter_10_to_regular_velocity_ratio": velocity_ratio,
        "jitter_10_velocity_ratio_limit": velocity_multiplier,
        "jitter_10_velocity_ratio_pass": jitter_10_velocity_pass,
        "robustness_pass": robustness_pass,
        "sampled_failure_evidence_complete": (
            sampled_failure_evidence_complete
        ),
        "unsampled_failure_run_ids": unsampled_failure_run_ids,
        "conditional_jitter_robustness": bool(
            complete
            and regular_pass
            and jitter_05_pass
            and not jitter_10_pass
            and sampled_failure_evidence_complete
        ),
    }
    return rows, facts


def evaluate_mach(
    bundle: EvidenceBundle,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Quantify the three preregistered sound-speed/model-form runs."""

    config = _nested(bundle.configuration, "mach_sensitivity")
    resolution = int(config["resolution"])
    dt = float(config["time_step"])
    support_ratio = float(config["support_ratio"])
    final_time = float(config["final_time"])
    expected_sound_speeds = [
        float(value) for value in config["sound_speeds"]
    ]
    expected_nominal_mach = [
        float(value) for value in config["nominal_mach_numbers"]
    ]
    u0 = float(_nested(bundle.configuration, "primary_tgv", "U0"))
    resolutions = _summary_numeric_values(bundle, "resolution", ("N",))
    dts = _summary_numeric_values(bundle, "dt", ("time_step",))
    supports = _summary_numeric_values(
        bundle,
        "support_ratio",
        ("H_over_dx", "h_dx"),
    )
    sound_speeds = _summary_numeric_values(
        bundle,
        "sound_speed",
        ("c_s", "cs"),
    )
    rows: list[dict[str, Any]] = []
    all_pass = True
    for expected_cs, expected_ma in zip(
        expected_sound_speeds,
        expected_nominal_mach,
    ):
        if not _isclose(u0 / expected_cs, expected_ma):
            raise EvidenceError(
                "preregistered sound speed and nominal Mach disagree: "
                f"c_s={expected_cs}, Ma={expected_ma}"
            )
        mask = (
            (bundle.run_summary["_protocol"] == "mach_sensitivity")
            & (bundle.run_summary["_layout"] == "regular")
            & (resolutions == resolution)
            & np.isclose(
                dts,
                dt,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & np.isclose(
                supports,
                support_ratio,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & np.isclose(
                sound_speeds,
                expected_cs,
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
        )
        run = _select_one(
            bundle.run_summary,
            mask,
            description=f"Mach sensitivity c_s={expected_cs}",
        )
        endpoint = _endpoint_metrics(
            bundle,
            run,
            final_time=final_time,
        )
        core_gates = _run_core_sample_gates(bundle, run)
        maximum_speed = endpoint["maximum_speed"]
        acoustic_cfl = (
            dt * (expected_cs + float(maximum_speed)) / (2.0 / resolution)
            if maximum_speed is not None
            else None
        )
        run_pass = bool(
            run["_accepted"]
            and endpoint["trajectory_finite"]
            and endpoint["density_fluctuation_relative_rms"] is not None
            and endpoint["maximum_mach"] is not None
            and endpoint["pressure_absolute_maximum"] is not None
            and endpoint["wall_clock_seconds"] is not None
            and core_gates["pass"]
        )
        all_pass = all_pass and run_pass
        rows.append(
            {
                "run_id": endpoint["run_id"],
                "sound_speed": expected_cs,
                "nominal_mach": expected_ma,
                "velocity_relative_l2": endpoint["velocity_relative_l2"],
                "density_fluctuation_relative_rms": endpoint[
                    "density_fluctuation_relative_rms"
                ],
                "maximum_mach": endpoint["maximum_mach"],
                "pressure_absolute_maximum": endpoint[
                    "pressure_absolute_maximum"
                ],
                "wall_clock_seconds": endpoint["wall_clock_seconds"],
                "peak_rss_bytes": endpoint["peak_rss_bytes"],
                "acoustic_cfl": acoustic_cfl,
                "accepted": bool(run["_accepted"]),
                "trajectory_finite": endpoint["trajectory_finite"],
                "core_gate_pass": core_gates["pass"],
                "core_finite_pass": core_gates["finite_pass"],
                "core_topology_pass": core_gates["topology_pass"],
                "core_pressure_pair_pass": core_gates[
                    "pressure_pair_pass"
                ],
                "core_viscosity_pair_pass": core_gates[
                    "viscosity_pair_pass"
                ],
                "core_total_force_pass": core_gates[
                    "total_force_pass"
                ],
                "core_assembled_total_force_pass": core_gates[
                    "assembled_total_force_pass"
                ],
                "core_assembly_consistency_pass": core_gates[
                    "assembly_consistency_pass"
                ],
                "core_viscous_power_pass": core_gates[
                    "viscous_power_pass"
                ],
                "core_sample_peak_rss_bytes": core_gates[
                    "sample_peak_rss_bytes"
                ],
                "core_summary_post_archive_peak_rss_bytes": core_gates[
                    "summary_peak_rss_bytes"
                ],
                "core_effective_peak_rss_bytes": core_gates[
                    "effective_peak_rss_bytes"
                ],
                "core_rss_pass": core_gates["rss_pass"],
                "core_thermal_pass": core_gates["thermal_pass"],
                "core_memory_pressure_pass": core_gates[
                    "memory_pressure_pass"
                ],
                "core_memory_growth_pass": core_gates[
                    "memory_growth_pass"
                ],
                "minimum_separation_over_dx": core_gates[
                    "minimum_separation_over_dx"
                ],
                "core_clustering_pass": core_gates["clustering_pass"],
                "run_pass": run_pass,
            }
        )
    rows.sort(key=lambda item: float(item["sound_speed"]))
    velocity_errors = [
        float(row["velocity_relative_l2"])
        for row in rows
        if row["velocity_relative_l2"] is not None
        and math.isfinite(float(row["velocity_relative_l2"]))
    ]
    density_errors = [
        float(row["density_fluctuation_relative_rms"])
        for row in rows
        if row["density_fluctuation_relative_rms"] is not None
        and math.isfinite(
            float(row["density_fluctuation_relative_rms"])
        )
    ]
    velocity_improves = bool(
        len(velocity_errors) == 3
        and _strictly_decreases(velocity_errors)
    )
    density_improves = bool(
        len(density_errors) == 3
        and _strictly_decreases(density_errors)
    )
    for row in rows:
        row["velocity_error_improves_as_mach_decreases"] = velocity_improves
        row["density_fluctuation_improves_as_mach_decreases"] = (
            density_improves
        )
        row["weak_compressibility_model_form_classification"] = (
            "VELOCITY_ERROR_DECREASES_WITH_MACH"
            if velocity_improves
            else "WEAK_COMPRESSIBILITY_NOT_PRIMARY_VELOCITY_ERROR"
        )
    facts = {
        "execution_status": "COMPLETE",
        "not_run_reason": "",
        "complete_and_quantified": bool(len(rows) == 3 and all_pass),
        "velocity_error_improves_as_mach_decreases": velocity_improves,
        "density_fluctuation_improves_as_mach_decreases": density_improves,
        "weak_compressibility_error_dominance_supported": bool(
            velocity_improves
        ),
        # This is a machine decision from the preregistered three-point
        # velocity trend, not a run-summary declaration.
        "model_form_dominant_declared": velocity_improves,
    }
    return rows, facts


def _optional_summary_bool(
    bundle: EvidenceBundle,
    canonical: str,
    aliases: Sequence[str] = (),
) -> np.ndarray | None:
    return _bool_values(
        bundle.run_summary,
        canonical,
        aliases,
        required=False,
        source=str(bundle.run_summary_path),
    )


def _failure_text(row: pd.Series, bundle: EvidenceBundle) -> str:
    parts: list[str] = []
    for canonical, aliases in (
        ("failure_class", ("stop_class",)),
        ("failure_reason", ("stop_reason",)),
    ):
        value = _row_text(
            row,
            bundle,
            canonical,
            aliases,
            required=False,
        )
        if value:
            parts.append(value)
    return " ".join(parts)


def _smoke_gate(bundle: EvidenceBundle) -> dict[str, Any]:
    resolutions = _summary_numeric_values(bundle, "resolution", ("N",))
    dts = _summary_numeric_values(bundle, "dt", ("time_step",))
    supports = _summary_numeric_values(
        bundle,
        "support_ratio",
        ("H_over_dx", "h_dx"),
    )
    results: dict[str, bool] = {}
    run_ids: dict[str, str | None] = {}
    branch_status: dict[str, str] = {}
    for label, protocol in (("n16", "smoke_n16"), ("n32", "smoke_n32")):
        config = _nested(bundle.configuration, "smoke_tests", label)
        mask = (
            (bundle.run_summary["_protocol"] == protocol)
            & (resolutions == int(config["resolution"]))
            & np.isclose(
                dts,
                float(config["time_step"]),
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
            & np.isclose(
                supports,
                float(config["support_ratio"]),
                rtol=2.0e-12,
                atol=FLOAT_TIME_ATOL,
            )
        )
        count = int(np.asarray(mask, dtype=bool).sum())
        if count == 0:
            run_ids[label] = None
            results[label] = False
            branch_status[label] = "NOT_RUN"
            continue
        row = _select_one(
            bundle.run_summary,
            mask,
            description=f"{label} smoke test",
        )
        run_id = str(row["_run_id"])
        run_ids[label] = run_id
        endpoint = _endpoint_metrics(
            bundle,
            row,
            final_time=float(config["final_time"]),
        )
        core = _run_core_sample_gates(bundle, row)
        results[label] = bool(
            row["_accepted"]
            and endpoint["trajectory_finite"]
            and core["pass"]
        )
        branch_status[label] = "COMPLETE"
    observed = sum(run_id is not None for run_id in run_ids.values())
    execution_status = (
        "COMPLETE"
        if observed == 2
        else ("NOT_RUN" if observed == 0 else "PARTIAL")
    )
    return {
        "run_ids": run_ids,
        "branch_status": branch_status,
        "execution_status": execution_status,
        "observed_run_count": observed,
        "expected_run_count": 2,
        "not_run_reason": (
            ""
            if execution_status == "COMPLETE"
            else "smoke phase stopped or was blocked by a prior hard gate"
        ),
        "n16_pass": results["n16"],
        "n32_pass": results["n32"],
        "pass": all(results.values()),
    }


def _summary_row_bool(
    bundle: EvidenceBundle,
    row: pd.Series,
    canonical: str,
    aliases: Sequence[str] = (),
) -> bool | None:
    column = _summary_column(
        bundle,
        canonical,
        aliases,
        required=False,
    )
    if column is None or pd.isna(row[column]):
        return None
    return _parse_bool(
        row[column],
        context=f"run {row['_run_id']}.{canonical}",
    )


def _has_consecutive_true(values: np.ndarray, count: int) -> bool:
    if count <= 0:
        raise ValueError("consecutive count must be positive")
    run = 0
    for value in values.astype(bool):
        run = run + 1 if value else 0
        if run >= count:
            return True
    return False


def _resource_policy_for_run(
    bundle: EvidenceBundle,
    row: pd.Series,
) -> dict[str, Any]:
    """Use summary flags or recompute revision-3 resource windows."""

    run_id = str(row["_run_id"])
    sample = bundle.samples[run_id]
    path = bundle.sample_paths[run_id]
    resource = _nested(bundle.configuration, "resource_stopping")
    pressure_policy = resource["sustained_memory_pressure_policy"]
    growth_policy = resource["memory_growth_policy"]
    pressure_flag = _summary_row_bool(
        bundle,
        row,
        "sustained_memory_pressure",
        ("memory_pressure",),
    )
    growth_flag = _summary_row_bool(
        bundle,
        row,
        "memory_growth_with_step",
        ("step_memory_growth",),
    )
    pressure_source = "run_summary_flag"
    growth_source = "run_summary_flag"
    if pressure_flag is None:
        free = _sample_numeric(
            sample,
            "memory_free_percentage",
            path=path,
            required=False,
        )
        if free is None or not np.isfinite(free).all():
            pressure_source = "missing"
        else:
            below = free < float(pressure_policy["free_percentage_below"])
            pressure_flag = _has_consecutive_true(
                below,
                int(pressure_policy["consecutive_samples"]),
            )
            pressure_source = "recomputed_sample_series"
    if growth_flag is None:
        current_rss = _sample_numeric(
            sample,
            "current_rss_bytes",
            path=path,
            required=False,
        )
        if current_rss is None or not np.isfinite(current_rss).all():
            growth_source = "missing"
        else:
            increase_count = int(
                growth_policy["consecutive_strict_increases"]
            )
            window_size = increase_count + 1
            minimum_absolute = float(
                growth_policy["minimum_absolute_increase_bytes"]
            )
            minimum_fractional = float(
                growth_policy["minimum_fractional_increase"]
            )
            growth_flag = False
            for start in range(0, len(current_rss) - window_size + 1):
                window = current_rss[start : start + window_size]
                strictly_increases = bool(np.all(np.diff(window) > 0.0))
                absolute = float(window[-1] - window[0])
                fractional = (
                    absolute / float(window[0])
                    if window[0] > 0.0
                    else math.inf
                )
                if (
                    strictly_increases
                    and absolute >= minimum_absolute
                    and fractional >= minimum_fractional
                ):
                    growth_flag = True
                    break
            growth_source = "recomputed_sample_series"
    evidence_complete = pressure_flag is not None and growth_flag is not None
    return {
        "sustained_memory_pressure": pressure_flag,
        "memory_growth_with_step": growth_flag,
        "pressure_source": pressure_source,
        "growth_source": growth_source,
        "evidence_complete": evidence_complete,
        "pass": bool(
            evidence_complete
            and not pressure_flag
            and not growth_flag
        ),
    }


def evaluate_resources_and_clustering(
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    """Apply global RSS, thermal, finite-state, and 0.25*dx gates."""

    resource = _nested(bundle.configuration, "resource_stopping")
    rss_limit = int(resource["peak_rss_bytes"])
    thermal_limit = float(
        resource["second_half_mean_step_time_increase_fraction"]
    )
    wall_limit = float(
        resource["projected_single_experiment_seconds_without_checkpoint"]
    )
    separation_limit = float(
        _nested(
            bundle.configuration,
            "particle_clustering_diagnostic",
            "minimum_separation_over_dx",
        )
    )
    global_rss = -math.inf
    global_rss_run = ""
    global_sample_rss = -math.inf
    global_sample_rss_run = ""
    global_summary_rss = -math.inf
    global_summary_rss_run = ""
    global_thermal = -math.inf
    global_thermal_run = ""
    minimum_ratio = math.inf
    minimum_ratio_run = ""
    thermal_complete = True
    all_states_finite = True
    hard_states_finite = True
    excessive_wall_without_checkpoint = False
    core_nonaccepted: list[str] = []
    unexplained_failures: list[str] = []
    checkpoint_flags = _optional_summary_bool(
        bundle,
        "checkpoint_enabled",
        ("has_checkpoint",),
    )
    pressure_flagged: list[str] = []
    growth_flagged: list[str] = []
    resource_policy_missing: list[str] = []
    hard_rss_failed: list[str] = []
    summary_rss_missing: list[str] = []
    archive_rss_failure_class_run_ids: list[str] = []
    hard_thermal_failed: list[str] = []
    hard_pressure_flagged: list[str] = []
    hard_growth_flagged: list[str] = []
    hard_resource_policy_missing: list[str] = []
    for position, (_, row) in enumerate(bundle.run_summary.iterrows()):
        run_id = str(row["_run_id"])
        protocol = str(row["_protocol"])
        hard_scope = protocol != "disorder_robustness"
        sample = bundle.samples[run_id]
        path = bundle.sample_paths[run_id]
        summary_rss_column = _summary_column(
            bundle,
            "peak_rss_bytes",
            ("maximum_rss_bytes",),
        )
        assert summary_rss_column is not None
        summary_peak_rss = _finite_float_or_none(
            row[summary_rss_column]
        )
        if summary_peak_rss is None:
            summary_rss_missing.append(run_id)
        elif summary_peak_rss > global_summary_rss:
            global_summary_rss = summary_peak_rss
            global_summary_rss_run = run_id
        if sample.empty:
            rss = np.asarray([], dtype=float)
            thermal = np.asarray([], dtype=float)
            separation = np.asarray([], dtype=float)
        else:
            rss = _sample_numeric(sample, "peak_rss_bytes", path=path)
            thermal = _sample_numeric(
                sample,
                "thermal_slowdown_fraction",
                path=path,
            )
            separation = _sample_numeric(
                sample,
                "minimum_separation",
                path=path,
            )
            assert rss is not None and thermal is not None
            assert separation is not None
        sample_peak_rss = (
            float(np.max(rss))
            if rss.size > 0 and np.isfinite(rss).all()
            else None
        )
        if sample_peak_rss is None:
            all_states_finite = False
            if hard_scope:
                hard_states_finite = False
        else:
            if sample_peak_rss > global_sample_rss:
                global_sample_rss = sample_peak_rss
                global_sample_rss_run = run_id
        effective_peak_rss = (
            max(sample_peak_rss, summary_peak_rss)
            if sample_peak_rss is not None
            and summary_peak_rss is not None
            else (
                sample_peak_rss
                if sample_peak_rss is not None
                else summary_peak_rss
            )
        )
        if effective_peak_rss is not None:
            if effective_peak_rss > global_rss:
                global_rss = effective_peak_rss
                global_rss_run = run_id
            # RSS is a machine-safety gate, including disorder runs.  A
            # post-archive getrusage peak cannot be downgraded to a jitter
            # robustness conditional.
            if effective_peak_rss > rss_limit:
                hard_rss_failed.append(run_id)
        finite_thermal = thermal[np.isfinite(thermal)]
        if finite_thermal.size == 0:
            thermal_complete = False
            if hard_scope:
                hard_thermal_failed.append(run_id)
        else:
            maximum = float(np.max(finite_thermal))
            if maximum > global_thermal:
                global_thermal = maximum
                global_thermal_run = run_id
            if hard_scope and maximum > thermal_limit:
                hard_thermal_failed.append(run_id)
        resolution = int(
            _row_number(row, bundle, "resolution", ("N",))
        )
        ratio = (
            float(np.nanmin(separation / (2.0 / resolution)))
            if separation.size > 0
            and np.isfinite(separation).any()
            else math.nan
        )
        if not math.isfinite(ratio):
            all_states_finite = False
            if hard_scope:
                hard_states_finite = False
        elif ratio < minimum_ratio:
            minimum_ratio = ratio
            minimum_ratio_run = run_id
        state = bundle.states[run_id]
        if state is None or not np.isfinite(state.velocities).all():
            all_states_finite = False
            if hard_scope:
                hard_states_finite = False
        finite_flags = (
            None
            if sample.empty
            else _bool_values(
                sample,
                "state_all_finite",
                ("finite", "all_finite"),
                required=False,
                source=str(path),
            )
        )
        if finite_flags is not None and not finite_flags.all():
            all_states_finite = False
            if hard_scope:
                hard_states_finite = False

        wall = _row_number(
            row,
            bundle,
            "wall_clock_seconds",
            ("runtime_seconds", "wall_seconds"),
            required=False,
        )
        checkpoint = (
            bool(checkpoint_flags[position])
            if checkpoint_flags is not None
            else False
        )
        if wall is not None and wall > wall_limit and not checkpoint:
            excessive_wall_without_checkpoint = True

        policy = _resource_policy_for_run(bundle, row)
        if not bool(policy["evidence_complete"]):
            resource_policy_missing.append(run_id)
            if hard_scope:
                hard_resource_policy_missing.append(run_id)
        if policy["sustained_memory_pressure"] is True:
            pressure_flagged.append(run_id)
            if hard_scope:
                hard_pressure_flagged.append(run_id)
        if policy["memory_growth_with_step"] is True:
            growth_flagged.append(run_id)
            if hard_scope:
                hard_growth_flagged.append(run_id)

        if not bool(row["_accepted"]) and protocol != "disorder_robustness":
            core_nonaccepted.append(run_id)
        failure = _normal_token(_failure_text(row, bundle))
        if "rss_limit_archive" in failure:
            archive_rss_failure_class_run_ids.append(run_id)
        if protocol != "disorder_robustness" and any(
            token in failure
            for token in (
                "nan",
                "inf",
                "nonfinite",
                "blowup",
                "explosion",
                "unknown",
                "unexplained",
            )
        ):
            unexplained_failures.append(run_id)

    rss_pass = not hard_rss_failed and not summary_rss_missing
    thermal_pass = bool(
        not hard_thermal_failed
    )
    clustering_pass = minimum_ratio >= separation_limit
    pressure_pass = (
        not hard_pressure_flagged
        and not hard_resource_policy_missing
    )
    memory_growth_pass = (
        not hard_growth_flagged
        and not hard_resource_policy_missing
    )
    passed = bool(
        rss_pass
        and thermal_pass
        and clustering_pass
        and hard_states_finite
        and pressure_pass
        and memory_growth_pass
        and not excessive_wall_without_checkpoint
        and not core_nonaccepted
        and not unexplained_failures
    )
    return {
        "peak_rss_bytes": global_rss,
        "peak_rss_run_id": global_rss_run,
        "sample_peak_rss_bytes": global_sample_rss,
        "sample_peak_rss_run_id": global_sample_rss_run,
        "summary_peak_rss_bytes": global_summary_rss,
        "summary_peak_rss_run_id": global_summary_rss_run,
        "peak_rss_limit_bytes": rss_limit,
        "rss_pass": rss_pass,
        "summary_peak_rss_missing_or_nonfinite_run_ids": (
            summary_rss_missing
        ),
        "archive_rss_failure_class_run_ids": (
            archive_rss_failure_class_run_ids
        ),
        "maximum_thermal_slowdown_fraction": global_thermal,
        "maximum_thermal_slowdown_run_id": global_thermal_run,
        "thermal_slowdown_limit": thermal_limit,
        "thermal_evidence_complete": thermal_complete,
        "thermal_pass": thermal_pass,
        "minimum_separation_over_dx": minimum_ratio,
        "minimum_separation_over_dx_run_id": minimum_ratio_run,
        "minimum_separation_over_dx_limit": separation_limit,
        "clustering_pass": clustering_pass,
        "all_states_finite": all_states_finite,
        "hard_scope_states_finite": hard_states_finite,
        "hard_scope_rss_failed_run_ids": hard_rss_failed,
        "hard_scope_thermal_failed_run_ids": hard_thermal_failed,
        "no_sustained_memory_pressure": pressure_pass,
        "no_step_memory_growth": memory_growth_pass,
        "sustained_memory_pressure_run_ids": pressure_flagged,
        "memory_growth_run_ids": growth_flagged,
        "resource_policy_missing_run_ids": resource_policy_missing,
        "hard_scope_resource_policy_missing_run_ids": (
            hard_resource_policy_missing
        ),
        "no_excessive_wall_time_without_checkpoint": (
            not excessive_wall_without_checkpoint
        ),
        "core_nonaccepted_run_ids": core_nonaccepted,
        "unexplained_failure_run_ids": unexplained_failures,
        "pass": passed,
    }


def _existing_recorded_paths(
    bundle: EvidenceBundle,
    canonical: str,
    aliases: Sequence[str],
    *,
    required_column: bool,
) -> tuple[int, int]:
    column = _summary_column(
        bundle,
        canonical,
        aliases,
        required=required_column,
    )
    if column is None:
        return (0, len(bundle.run_summary))
    present = 0
    missing = 0
    for value in bundle.run_summary[column].tolist():
        if pd.isna(value) or not str(value).strip():
            missing += 1
            continue
        path = Path(str(value))
        candidates = (
            [path]
            if path.is_absolute()
            else [
                bundle.project_root / path,
                bundle.experiment_root / path,
            ]
        )
        if any(candidate.is_file() for candidate in candidates):
            present += 1
        else:
            missing += 1
    return present, missing


def evaluate_provenance(bundle: EvidenceBundle) -> dict[str, Any]:
    """Check hashes, logs, sample/state tables, and failure evidence."""

    expected_prerequisites = [
        "independent scalar and coupled-ODE integrator verification",
        "100-step regular zero-flow equilibrium",
    ]
    execution_order = _nested(bundle.configuration, "execution_order")
    execution_order_pass = bool(
        isinstance(execution_order, list)
        and execution_order[:2] == expected_prerequisites
    )
    preregistration_status_pass = (
        bundle.configuration.get("status")
        == "PREREGISTERED_BEFORE_FIRST_STAGE_01D_TGV_RUN"
    )
    revision_value = _nested(
        bundle.configuration,
        "preregistration_revision",
        "revision",
    )
    revision_pass = bool(
        isinstance(revision_value, int)
        and not isinstance(revision_value, bool)
        and revision_value >= 5
    )
    config_hash_column = _summary_column(
        bundle,
        "config_hash",
        ("config_sha256",),
    )
    git_hash_column = _summary_column(bundle, "git_hash")
    assert config_hash_column is not None and git_hash_column is not None
    config_hashes = bundle.run_summary[config_hash_column].astype(str)
    git_hashes = bundle.run_summary[git_hash_column].astype(str)
    hashes_complete = bool(
        (config_hashes.str.fullmatch(r"[0-9a-fA-F]{64}")).all()
        and (git_hashes.str.fullmatch(r"[0-9a-fA-F]{7,40}")).all()
    )
    unique_git_hashes = sorted(set(git_hashes.tolist()))
    git_identity_pass = bool(
        hashes_complete and len(unique_git_hashes) == 1
    )
    expected_git_hash = (
        unique_git_hashes[0] if git_identity_pass else None
    )
    config_path_column = _summary_column(
        bundle,
        "config_path",
        ("resolved_config_path",),
    )
    dirty_column = _summary_column(
        bundle,
        "source_tree_dirty",
        ("git_dirty",),
    )
    assert config_path_column is not None and dirty_column is not None
    master_hash = hashlib.sha256(
        (
            bundle.experiment_root
            / "configs"
            / "preregistered_primary_tgv.yml"
        ).read_bytes()
    ).hexdigest()
    integrator_source = str(bundle.integrator_path)
    integrator_config_hash = _series(
        bundle.integrator,
        "config_sha256",
        source=integrator_source,
    )
    integrator_git_hash = _series(
        bundle.integrator,
        "git_hash",
        source=integrator_source,
    )
    assert integrator_config_hash is not None
    assert integrator_git_hash is not None
    integrator_identity_pass = bool(
        (integrator_config_hash.astype(str).to_numpy() == master_hash).all()
        and expected_git_hash is not None
        and (
            integrator_git_hash.astype(str).to_numpy()
            == expected_git_hash
        ).all()
    )
    verified_configs = 0
    config_mismatches: list[str] = []
    relative_paths_only = True
    for _, row in bundle.run_summary.iterrows():
        run_id = str(row["_run_id"])
        recorded_path = Path(str(row[config_path_column]))
        relative_paths_only = (
            relative_paths_only and not recorded_path.is_absolute()
        )
        resolved_path = (
            recorded_path
            if recorded_path.is_absolute()
            else bundle.project_root / recorded_path
        )
        try:
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))
            recorded_resolved_hash = payload.pop(
                "resolved_config_sha256"
            )
            computed_hash = hashlib.sha256(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            matches = (
                computed_hash == str(row[config_hash_column])
                == str(recorded_resolved_hash)
                and str(payload["git_hash"]) == str(row[git_hash_column])
                and str(payload["master_preregistration_sha256"])
                == master_hash
            )
        except Exception:
            matches = False
        if matches:
            verified_configs += 1
        else:
            config_mismatches.append(run_id)
    source_dirty = _bool_values(
        bundle.run_summary,
        str(dirty_column),
        required=True,
        source=str(bundle.run_summary_path),
    )
    assert source_dirty is not None
    source_trees_clean = bool((~source_dirty).all())
    for canonical, aliases in (
        ("sample_table_path", ("trajectory_sample_path",)),
        ("state_path", ("trajectory_state_path",)),
        ("stdout_log_path", ("stdout_path",)),
        ("stderr_log_path", ("stderr_path",)),
        ("failure_evidence_path", ("failure_path",)),
    ):
        column = _summary_column(
            bundle,
            canonical,
            aliases,
            required=canonical != "failure_evidence_path",
        )
        if column is not None:
            for value in bundle.run_summary[column].tolist():
                if pd.isna(value) or not str(value).strip():
                    continue
                relative_paths_only = (
                    relative_paths_only
                    and not Path(str(value)).is_absolute()
                )
    stdout_present, stdout_missing = _existing_recorded_paths(
        bundle,
        "stdout_log_path",
        ("stdout_path",),
        required_column=True,
    )
    stderr_present, stderr_missing = _existing_recorded_paths(
        bundle,
        "stderr_log_path",
        ("stderr_path",),
        required_column=True,
    )
    failed = bundle.run_summary[~bundle.run_summary["_accepted"]]
    failure_column = _summary_column(
        bundle,
        "failure_evidence_path",
        ("failure_path",),
        required=not failed.empty,
    )
    failure_present = 0
    failure_missing = 0
    if not failed.empty and failure_column is not None:
        for value in failed[failure_column].tolist():
            if pd.isna(value) or not str(value).strip():
                failure_missing += 1
                continue
            path = Path(str(value))
            candidates = (
                [path]
                if path.is_absolute()
                else [
                    bundle.project_root / path,
                    bundle.experiment_root / path,
                ]
            )
            if any(candidate.is_file() for candidate in candidates):
                failure_present += 1
            else:
                failure_missing += 1
    logs_complete = stdout_missing == 0 and stderr_missing == 0
    failures_complete = failure_missing == 0
    passed = bool(
        hashes_complete
        and git_identity_pass
        and integrator_identity_pass
        and execution_order_pass
        and preregistration_status_pass
        and revision_pass
        and verified_configs == len(bundle.run_summary)
        and source_trees_clean
        and relative_paths_only
        and logs_complete
        and failures_complete
    )
    return {
        "run_count": len(bundle.run_summary),
        "actual_master_preregistration_sha256": master_hash,
        "preregistration_status_exact": preregistration_status_pass,
        "preregistration_revision": revision_value,
        "preregistration_revision_at_least_5": revision_pass,
        "execution_order_first_two": (
            execution_order[:2]
            if isinstance(execution_order, list)
            else execution_order
        ),
        "prerequisite_execution_order_pass": execution_order_pass,
        "config_and_git_hashes_complete": hashes_complete,
        "unique_run_git_hashes": unique_git_hashes,
        "run_git_identity_pass": git_identity_pass,
        "expected_git_hash": expected_git_hash,
        "integrator_identity_pass": integrator_identity_pass,
        "resolved_config_verified_count": verified_configs,
        "resolved_config_mismatch_run_ids": config_mismatches,
        "source_trees_clean": source_trees_clean,
        "recorded_paths_relative_only": relative_paths_only,
        "sample_table_count": len(bundle.samples),
        "trajectory_state_count": sum(
            state is not None for state in bundle.states.values()
        ),
        "missing_trajectory_state_run_ids": sorted(
            run_id
            for run_id, state in bundle.states.items()
            if state is None
        ),
        "stdout_log_present_count": stdout_present,
        "stdout_log_missing_count": stdout_missing,
        "stderr_log_present_count": stderr_present,
        "stderr_log_missing_count": stderr_missing,
        "failed_run_count": len(failed),
        "failure_evidence_present_count": failure_present,
        "failure_evidence_missing_count": failure_missing,
        "pass": passed,
    }


class _GateEvidence:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(
        self,
        *,
        gate: str,
        check: str,
        passed: bool,
        observed: Any,
        threshold: Any,
        source: str,
        severity: str = "HARD",
        detail: str = "",
    ) -> None:
        self.rows.append(
            {
                "gate": gate,
                "check": check,
                "passed": bool(passed),
                "observed": observed,
                "threshold": threshold,
                "source": source,
                "severity": severity,
                "detail": detail,
            }
        )


def _relative_source(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _build_gate_evidence(
    bundle: EvidenceBundle,
    *,
    integrator_rows: list[dict[str, Any]],
    integrator_pass: bool,
    zero: dict[str, Any],
    conservation: dict[str, Any],
    time: dict[str, Any],
    space: dict[str, Any],
    autograd: dict[str, Any],
    disorder: dict[str, Any],
    mach: dict[str, Any],
    smoke: dict[str, Any],
    resources: dict[str, Any],
    provenance: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence = _GateEvidence()
    conservation_not_run = (
        conservation.get("execution_status") == "NOT_RUN"
    )
    time_not_run = time.get("execution_status") == "NOT_RUN"
    space_not_run = space.get("execution_status") == "NOT_RUN"
    disorder_not_run = disorder.get("execution_status") == "NOT_RUN"
    mach_not_run = mach.get("execution_status") == "NOT_RUN"
    smoke_not_run = smoke.get("execution_status") == "NOT_RUN"
    space_plateau_eligible = bool(
        space.get("conditional_space_plateau_eligible", False)
    )
    model_form_eligible = bool(
        mach.get("conditional_model_form_eligible", False)
    )
    space_primary_severity = (
        "NOT_RUN"
        if space_not_run
        else ("CONDITIONAL" if space_plateau_eligible else "HARD")
    )
    for row in integrator_rows:
        evidence.add(
            gate="I",
            check=f"{row['problem']}_second_order",
            passed=bool(row["pass"]),
            observed={
                "fitted_order": row["fitted_order"],
                "finest_pair_order": row[
                    "finest_pair_observed_order"
                ],
                "decreases": row["every_error_level_decreases"],
            },
            threshold={
                "fitted_order_minimum": row["fitted_order_minimum"],
                "finest_pair_order_minimum": row[
                    "finest_pair_order_minimum"
                ],
            },
            source=row["source"],
        )
    evidence.add(
        gate="I",
        check="both_ode_integrator_gates",
        passed=integrator_pass,
        observed=f"{sum(bool(row['pass']) for row in integrator_rows)}/2",
        threshold="2/2",
        source=_relative_source(
            bundle.integrator_path,
            bundle.project_root,
        ),
    )

    zero_source = _relative_source(
        bundle.sample_paths[str(zero["run_id"])],
        bundle.project_root,
    )
    for check, observed_key, threshold_key in (
        (
            "position_drift",
            "position_drift_linf_max",
            "position_drift_tolerance",
        ),
        (
            "velocity_linf",
            "velocity_linf_max",
            "velocity_linf_tolerance",
        ),
        (
            "pressure_linf",
            "pressure_absolute_maximum",
            "pressure_linf_tolerance",
        ),
        (
            "relative_density_drift",
            "relative_density_drift_max",
            "relative_density_drift_tolerance",
        ),
    ):
        evidence.add(
            gate="Z",
            check=check,
            passed=float(zero[observed_key]) <= float(zero[threshold_key]),
            observed=zero[observed_key],
            threshold=f"<= {zero[threshold_key]}",
            source=zero_source,
        )
    evidence.add(
        gate="Z",
        check="zero_flow_100_steps_and_topology",
        passed=bool(zero["pass"]),
        observed={
            "sample_count": zero["observed_sample_count"],
            "step_complete": zero["step_complete"],
            "topology": zero["topology_maxima"],
            "finite": zero["all_state_values_finite"],
        },
        threshold={
            "required_steps": zero["required_steps"],
            "topology_counts": 0,
        },
        source=zero_source,
        detail=str(
            _nested(
                bundle.configuration,
                "zero_flow",
                "eos_reference_density",
            )
        ),
    )

    conservation_source = "results/trajectory_samples/*.csv"
    conservation_checks = (
        (
            "pressure_pair_residual",
            conservation["pressure_pair_pass"],
            conservation["pressure_pair_maximum"],
            conservation["pair_limit"],
        ),
        (
            "viscosity_pair_residual",
            conservation["viscosity_pair_pass"],
            conservation["viscosity_pair_maximum"],
            conservation["pair_limit"],
        ),
        (
            "reconstructed_total_internal_force",
            conservation["total_force_pass"],
            conservation["total_force_maximum"],
            conservation["total_force_limit"],
        ),
        (
            "assembled_mass_weighted_internal_force",
            conservation["assembled_total_force_pass"],
            conservation["assembled_total_force_maximum"],
            conservation["total_force_limit"],
        ),
        (
            "assembly_force_consistency",
            conservation["assembly_consistency_pass"],
            conservation["assembly_consistency_maximum"],
            conservation["assembly_consistency_limit"],
        ),
        (
            "viscous_power_nonpositive",
            conservation["viscous_power_pass"],
            max(
                float(conservation["accumulated_power_maximum"]),
                float(
                    conservation["direct_power_maximum"]
                    if conservation["direct_power_maximum"] is not None
                    else -math.inf
                ),
            ),
            conservation["power_positive_absolute_limit"],
        ),
    )
    for check, passed, observed, threshold in conservation_checks:
        evidence.add(
            gate="C",
            check=check,
            passed=bool(passed),
            observed="NOT_RUN" if conservation_not_run else observed,
            threshold=f"<= {threshold}",
            source=conservation_source,
            severity="NOT_RUN" if conservation_not_run else "HARD",
            detail=(
                conservation.get("not_run_reason", "")
                if conservation_not_run
                else ""
            ),
        )
    evidence.add(
        gate="C",
        check="all_accepted_samples_finite_and_topology_exact",
        passed=bool(
            conservation["all_values_finite"]
            and conservation["topology_pass"]
        ),
        observed=(
            "NOT_RUN"
            if conservation_not_run
            else {
                "accepted_runs": conservation["accepted_run_count"],
                "accepted_samples": conservation[
                    "accepted_sample_count"
                ],
                "topology": conservation["topology_maxima"],
            }
        ),
        threshold="all finite; every topology defect count = 0",
        source=conservation_source,
        severity="NOT_RUN" if conservation_not_run else "HARD",
        detail=(
            conservation.get("not_run_reason", "")
            if conservation_not_run
            else ""
        ),
    )

    evidence.add(
        gate="T",
        check="four_time_trajectories_finite",
        passed=bool(time["all_four_trajectories_finite"]),
        observed=(
            "NOT_RUN"
            if time_not_run
            else time["all_four_trajectories_finite"]
        ),
        threshold=True,
        source="results/time_convergence_metrics.csv",
        severity="NOT_RUN" if time_not_run else "HARD",
        detail=time.get("not_run_reason", "") if time_not_run else "",
    )
    evidence.add(
        gate="T",
        check="analytic_endpoint_credible_decrease",
        passed=bool(time["analytic_trend_pass"]),
        observed=(
            "NOT_RUN"
            if time_not_run
            else time["analytic_endpoint_ratios"]
        ),
        threshold=(
            "at least one selected finest/coarsest ratio <= "
            f"{time['analytic_ratio_limit']}"
        ),
        source="results/time_convergence_metrics.csv",
        severity="NOT_RUN" if time_not_run else "ALTERNATIVE",
        detail=time.get("not_run_reason", "") if time_not_run else "",
    )
    evidence.add(
        gate="T",
        check="velocity_self_convergence_credible_decrease",
        passed=bool(time["self_trend_pass"]),
        observed=(
            "NOT_RUN"
            if time_not_run
            else time["self_finest_to_coarsest_ratio"]
        ),
        threshold=f"<= {time['self_ratio_limit']}",
        source="results/time_convergence_metrics.csv",
        severity="NOT_RUN" if time_not_run else "ALTERNATIVE",
        detail=time.get("not_run_reason", "") if time_not_run else "",
    )
    evidence.add(
        gate="T",
        check="analytic_or_self_time_trend",
        passed=bool(time["credible_trend_pass"]),
        observed=(
            "NOT_RUN"
            if time_not_run
            else {
                "analytic": time["analytic_trend_pass"],
                "self": time["self_trend_pass"],
                "platform": time["platform_detected"],
            }
        ),
        threshold="analytic OR self trend passes",
        source="results/time_convergence_metrics.csv",
        severity="NOT_RUN" if time_not_run else "HARD",
        detail=time.get("not_run_reason", "") if time_not_run else "",
    )

    evidence.add(
        gate="S",
        check="primary_selected_spatial_slopes_positive",
        passed=bool(space["primary_all_selected_slopes_positive"]),
        observed=(
            "NOT_RUN"
            if space_not_run
            else space["primary_all_selected_slopes_positive"]
        ),
        threshold="all three fitted slopes > 0",
        source="results/space_convergence_metrics.csv",
        severity=space_primary_severity,
        detail=(
            space.get("not_run_reason", "")
            if space_not_run
            else (
                "time gate passed and finite spatial evidence is "
                "nonworsening but below the primary pass threshold"
                if space_plateau_eligible
                else ""
            )
        ),
    )
    evidence.add(
        gate="S",
        check="primary_velocity_n32_over_n16",
        passed=bool(space["primary_velocity_ratio_pass"]),
        observed=(
            "NOT_RUN"
            if space_not_run
            else space["primary_velocity_n32_n16_ratio"]
        ),
        threshold=f"<= {space['primary_velocity_ratio_limit']}",
        source="results/space_convergence_metrics.csv",
        severity=space_primary_severity,
        detail=(
            space.get("not_run_reason", "")
            if space_not_run
            else (
                "time gate passed and finite spatial evidence is "
                "nonworsening but below the primary pass threshold"
                if space_plateau_eligible
                else ""
            )
        ),
    )
    evidence.add(
        gate="S",
        check="primary_space_gate",
        passed=bool(space["primary_space_pass"]),
        observed=(
            "NOT_RUN"
            if space_not_run
            else {
                "all_finite": space["primary_all_finite"],
                "nonworsening": space["primary_nonworsening"],
                "plateau": space["space_plateau_conditional"],
            }
        ),
        threshold="positive slopes and velocity N32/N16 gate",
        source="results/space_convergence_metrics.csv",
        severity=space_primary_severity,
        detail=(
            space.get("not_run_reason", "")
            if space_not_run
            else (
                "registered space-plateau conditional exemption"
                if space_plateau_eligible
                else ""
            )
        ),
    )
    evidence.add(
        gate="S",
        check="conditional_time_pass_space_plateau",
        passed=space_plateau_eligible,
        observed=(
            "NOT_RUN"
            if space_not_run
            else {
                "eligible": space_plateau_eligible,
                "time_complete": (
                    time.get("execution_status") == "COMPLETE"
                ),
                "time_finite": time[
                    "all_four_trajectories_finite"
                ],
                "time_credible": time["credible_trend_pass"],
                "space_complete": (
                    space.get("execution_status") == "COMPLETE"
                ),
                "primary_space_pass": space["primary_space_pass"],
                "primary_nonworsening": space[
                    "primary_nonworsening"
                ],
                "plateau": space["space_plateau_conditional"],
                "support_complete": space[
                    "support_family_comparison_complete"
                ],
            }
        ),
        threshold=(
            "time complete/finite/credible; space complete; primary "
            "nonworsening plateau; support evidence complete"
        ),
        source=(
            "results/time_convergence_metrics.csv + "
            "results/space_convergence_metrics.csv"
        ),
        severity="NOT_RUN" if space_not_run else "STATUS",
        detail=space.get("not_run_reason", "") if space_not_run else "",
    )
    evidence.add(
        gate="S",
        check="both_support_families_complete",
        passed=bool(space["support_family_comparison_complete"]),
        observed=(
            "NOT_RUN"
            if space_not_run
            else space["support_family_comparison_complete"]
        ),
        threshold="3 regular trajectories per support family",
        source="results/space_convergence_metrics.csv",
        severity="NOT_RUN" if space_not_run else "HARD",
        detail=space.get("not_run_reason", "") if space_not_run else "",
    )

    for label, result in (
        ("dynamic_current_20_of_20", autograd["dynamic"]),
        ("stage01c_current_regression_20_of_20", autograd["current_stage01c"]),
        (
            "stage01c_frozen_baseline_20_of_20",
            autograd["frozen_stage01c_baseline"],
        ),
    ):
        evidence.add(
            gate="AD",
            check=label,
            passed=bool(result["pass"]),
            observed={
                "pass_count": result["status_pass_count"],
                "row_count": result["row_count"],
                "short_max_relative_difference": result[
                    "short_maximum_relative_difference"
                ],
                "step16": result["step_16_finite_nonzero_pass"],
                "raw_recomputed_declarations": result[
                    "declaration_consistency_pass"
                ],
                "topology_disclaimed": result[
                    "topology_differentiability_disclaimed"
                ],
                "metadata_pass": result.get("metadata_pass", True),
            },
            threshold=(
                "20/20 recomputed from raw AD/FD; short <= 0.01; "
                "step16 finite nonzero; topology false; metadata exact"
            ),
            source=_relative_source(
                Path(result["source"]),
                bundle.project_root,
            ),
        )
    evidence.add(
        gate="AD",
        check="current_stage01c_matches_frozen_case_keys",
        passed=bool(autograd["baseline_crosscheck_pass"]),
        observed={
            "parameter_step_keys_match": autograd[
                "stage01c_parameter_step_keys_match_baseline"
            ],
            "parameter_values_and_fd_steps_match": autograd[
                "stage01c_parameter_values_and_fd_steps_match_baseline"
            ],
        },
        threshold={
            "parameter_step_keys_match": True,
            "parameter_values_and_fd_steps_match": True,
        },
        source=(
            "results/stage01c_autograd_regression.csv + "
            "stage_01c_autograd/results/native_autograd_fd.csv"
        ),
    )

    evidence.add(
        gate="SMOKE",
        check="n16_and_n32_smoke",
        passed=bool(smoke["pass"]),
        observed=(
            "NOT_RUN"
            if smoke_not_run
            else {
                "n16": smoke["n16_pass"],
                "n32": smoke["n32_pass"],
                "run_ids": smoke["run_ids"],
                "execution_status": smoke["execution_status"],
            }
        ),
        threshold="both pass complete core sample gates",
        source="results/trajectory_samples/*.csv",
        severity="NOT_RUN" if smoke_not_run else "HARD",
        detail=smoke.get("not_run_reason", "") if smoke_not_run else "",
    )
    evidence.add(
        gate="D",
        check="regular_disorder_control",
        passed=bool(disorder["regular_pass"]),
        observed=(
            "NOT_RUN" if disorder_not_run else disorder["regular_pass"]
        ),
        threshold=True,
        source="results/disorder_summary.csv",
        severity="NOT_RUN" if disorder_not_run else "HARD",
        detail=(
            disorder.get("not_run_reason", "")
            if disorder_not_run
            else ""
        ),
    )
    evidence.add(
        gate="D",
        check="jitter_05_disorder_control",
        passed=bool(disorder["jitter_05_pass"]),
        observed=(
            "NOT_RUN" if disorder_not_run else disorder["jitter_05_pass"]
        ),
        threshold=True,
        source="results/disorder_summary.csv",
        severity="NOT_RUN" if disorder_not_run else "HARD",
        detail=(
            disorder.get("not_run_reason", "")
            if disorder_not_run
            else ""
        ),
    )
    evidence.add(
        gate="D",
        check="jitter_10_velocity_error_multiplier",
        passed=bool(disorder["jitter_10_velocity_ratio_pass"]),
        observed=(
            "NOT_RUN"
            if disorder_not_run
            else disorder["jitter_10_to_regular_velocity_ratio"]
        ),
        threshold=f"<= {disorder['jitter_10_velocity_ratio_limit']}",
        source="results/disorder_summary.csv",
        severity="NOT_RUN" if disorder_not_run else "CONDITIONAL",
        detail=(
            disorder.get("not_run_reason", "")
            if disorder_not_run
            else ""
        ),
    )
    evidence.add(
        gate="D",
        check="all_disorder_layouts_robust",
        passed=bool(disorder["robustness_pass"]),
        observed=(
            "NOT_RUN"
            if disorder_not_run
            else {
                "regular": disorder["regular_pass"],
                "jitter_05": disorder["jitter_05_pass"],
                "jitter_10": disorder["jitter_10_pass"],
            }
        ),
        threshold="all pre-registered runs pass core and clustering gates",
        source="results/disorder_summary.csv",
        severity="NOT_RUN" if disorder_not_run else "CONDITIONAL",
        detail=(
            disorder.get("not_run_reason", "")
            if disorder_not_run
            else ""
        ),
    )
    evidence.add(
        gate="D",
        check="conditional_disorder_regular_and_jitter05_only",
        passed=bool(
            disorder["robustness_pass"]
            or disorder["conditional_jitter_robustness"]
        ),
        observed=(
            "NOT_RUN"
            if disorder_not_run
            else {
                "complete": disorder["complete"],
                "regular": disorder["regular_pass"],
                "jitter_05": disorder["jitter_05_pass"],
                "jitter_10": disorder["jitter_10_pass"],
                "sampled_failure_evidence_complete": disorder[
                    "sampled_failure_evidence_complete"
                ],
                "unsampled_failure_run_ids": disorder[
                    "unsampled_failure_run_ids"
                ],
                "conditional_eligible": disorder[
                    "conditional_jitter_robustness"
                ],
            }
        ),
        threshold=(
            "PASS if all layouts pass; CONDITIONAL only if regular and "
            "5% pass while 10% fails with sampled failure evidence"
        ),
        source="results/disorder_summary.csv",
        severity="NOT_RUN" if disorder_not_run else "STATUS",
        detail=(
            disorder.get("not_run_reason", "")
            if disorder_not_run
            else ""
        ),
    )
    evidence.add(
        gate="M",
        check="three_mach_runs_quantified",
        passed=bool(mach["complete_and_quantified"]),
        observed=(
            "NOT_RUN"
            if mach_not_run
            else {
                "velocity_improves": mach[
                    "velocity_error_improves_as_mach_decreases"
                ],
                "density_improves": mach[
                    "density_fluctuation_improves_as_mach_decreases"
                ],
                "dominant_declared": mach[
                    "model_form_dominant_declared"
                ],
            }
        ),
        threshold="all c_s={10,20,40} finite with error/density/cost evidence",
        source="results/mach_summary.csv",
        severity="NOT_RUN" if mach_not_run else "HARD",
        detail=mach.get("not_run_reason", "") if mach_not_run else "",
    )
    evidence.add(
        gate="M",
        check="conditional_quantified_model_form_error_dominant",
        passed=model_form_eligible,
        observed=(
            "NOT_RUN"
            if mach_not_run
            else {
                "eligible": model_form_eligible,
                "complete_and_core_pass": mach[
                    "complete_and_quantified"
                ],
                "velocity_strictly_improves_as_mach_decreases": mach[
                    "velocity_error_improves_as_mach_decreases"
                ],
                "dominance_supported": mach[
                    "weak_compressibility_error_dominance_supported"
                ],
            }
        ),
        threshold=(
            "three complete/core-passing Mach runs and a strict velocity-"
            "error decrease as Mach decreases"
        ),
        source="results/mach_summary.csv",
        severity="NOT_RUN" if mach_not_run else "STATUS",
        detail=mach.get("not_run_reason", "") if mach_not_run else "",
    )

    for check, passed, observed, threshold in (
        (
            "peak_rss",
            resources["rss_pass"],
            {
                "effective_peak_rss_bytes": resources[
                    "peak_rss_bytes"
                ],
                "sample_peak_rss_bytes": resources[
                    "sample_peak_rss_bytes"
                ],
                "summary_post_archive_peak_rss_bytes": resources[
                    "summary_peak_rss_bytes"
                ],
                "summary_missing_or_nonfinite_run_ids": resources[
                    "summary_peak_rss_missing_or_nonfinite_run_ids"
                ],
                "archive_rss_failure_class_run_ids": resources[
                    "archive_rss_failure_class_run_ids"
                ],
            },
            resources["peak_rss_limit_bytes"],
        ),
        (
            "thermal_slowdown",
            resources["thermal_pass"],
            resources["maximum_thermal_slowdown_fraction"],
            resources["thermal_slowdown_limit"],
        ),
        (
            "minimum_separation_over_dx",
            resources["clustering_pass"],
            resources["minimum_separation_over_dx"],
            resources["minimum_separation_over_dx_limit"],
        ),
    ):
        evidence.add(
            gate="R",
            check=check,
            passed=bool(passed),
            observed=observed,
            threshold=(
                f">= {threshold}"
                if check == "minimum_separation_over_dx"
                else f"<= {threshold}"
            ),
            source="results/run_summary.csv + trajectory_samples/*.csv",
        )
    pressure_policy = _nested(
        bundle.configuration,
        "resource_stopping",
        "sustained_memory_pressure_policy",
    )
    growth_policy = _nested(
        bundle.configuration,
        "resource_stopping",
        "memory_growth_policy",
    )
    evidence.add(
        gate="R",
        check="sustained_memory_pressure_policy",
        passed=bool(resources["no_sustained_memory_pressure"]),
        observed={
            "flagged_runs": resources[
                "sustained_memory_pressure_run_ids"
            ],
            "missing_runs": resources["resource_policy_missing_run_ids"],
        },
        threshold={
            "free_percentage_below": pressure_policy[
                "free_percentage_below"
            ],
            "consecutive_samples": pressure_policy[
                "consecutive_samples"
            ],
            "allowed_flagged_runs": 0,
        },
        source="run_summary flags or trajectory sample memory series",
    )
    evidence.add(
        gate="R",
        check="sustained_current_rss_growth_policy",
        passed=bool(resources["no_step_memory_growth"]),
        observed={
            "flagged_runs": resources["memory_growth_run_ids"],
            "missing_runs": resources["resource_policy_missing_run_ids"],
        },
        threshold={
            "consecutive_strict_increases": growth_policy[
                "consecutive_strict_increases"
            ],
            "minimum_absolute_increase_bytes": growth_policy[
                "minimum_absolute_increase_bytes"
            ],
            "minimum_fractional_increase": growth_policy[
                "minimum_fractional_increase"
            ],
            "allowed_flagged_runs": 0,
        },
        source="run_summary flags or trajectory sample current RSS series",
    )
    evidence.add(
        gate="R",
        check="resource_and_unexplained_failure_gate",
        passed=bool(resources["pass"]),
        observed={
            "hard_scope_states_finite": resources[
                "hard_scope_states_finite"
            ],
            "core_nonaccepted": resources["core_nonaccepted_run_ids"],
            "unexplained": resources["unexplained_failure_run_ids"],
            "memory_pressure_ok": resources[
                "no_sustained_memory_pressure"
            ],
            "memory_growth_ok": resources["no_step_memory_growth"],
        },
        threshold="all preregistered resource stop conditions clear",
        source="results/run_summary.csv + trajectory_samples/*.csv",
    )
    evidence.add(
        gate="P",
        check="prerequisite_execution_order_and_evidence_identity",
        passed=bool(
            provenance["prerequisite_execution_order_pass"]
            and provenance["integrator_identity_pass"]
            and provenance["run_git_identity_pass"]
        ),
        observed={
            "execution_order_first_two": provenance[
                "execution_order_first_two"
            ],
            "integrator_identity": provenance[
                "integrator_identity_pass"
            ],
            "run_git_identity": provenance["run_git_identity_pass"],
            "master_config_sha256": provenance[
                "actual_master_preregistration_sha256"
            ],
        },
        threshold=(
            "integrator then zero-flow; one exact git identity; "
            "integrator config hash equals current preregistration"
        ),
        source=_relative_source(
            bundle.experiment_root
            / "configs"
            / "preregistered_primary_tgv.yml",
            bundle.project_root,
        ),
    )
    evidence.add(
        gate="P",
        check="configuration_logs_and_failure_evidence_retained",
        passed=bool(provenance["pass"]),
        observed=provenance,
        threshold="all hashes/logs and failed-run evidence present",
        source="results/run_summary.csv",
    )
    return evidence.rows


def _phase_stub_context(
    bundle: EvidenceBundle,
    *,
    phase: str,
    protocols: Sequence[str],
    expected_run_count: int,
) -> dict[str, Any]:
    selected = bundle.run_summary[
        bundle.run_summary["_protocol"].isin(protocols)
    ]
    observed_run_count = len(selected)
    execution_status = (
        "NOT_RUN" if observed_run_count == 0 else "PARTIAL"
    )
    failed = selected[~selected["_accepted"]]
    failure_run_ids = failed["_run_id"].astype(str).tolist()
    failure_details = [
        {
            "run_id": str(row["_run_id"]),
            "failure": _failure_text(row, bundle),
        }
        for _, row in failed.iterrows()
    ]
    prior_failed = bundle.run_summary[~bundle.run_summary["_accepted"]]
    prior_failure_run_ids = (
        prior_failed["_run_id"].astype(str).tolist()
    )
    reason = (
        f"{phase} phase retained {observed_run_count}/"
        f"{expected_run_count} expected runs"
        if observed_run_count
        else (
            f"{phase} phase blocked by a prior preregistered hard gate"
        )
    )
    if failure_run_ids:
        reason += "; failed_run_ids=" + ",".join(failure_run_ids)
    elif prior_failure_run_ids:
        reason += "; prior_failed_run_ids=" + ",".join(
            prior_failure_run_ids
        )
    return {
        "phase": phase,
        "record_type": "phase_execution",
        "execution_status": execution_status,
        "status": execution_status,
        "expected_run_count": expected_run_count,
        "observed_run_count": observed_run_count,
        "failure_run_ids": failure_run_ids,
        "failure_details": failure_details,
        "not_run_reason": reason,
    }


def _time_not_run(
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return [dict(context)], {
        "execution_status": context["execution_status"],
        "not_run_reason": context["not_run_reason"],
        "run_count": context["observed_run_count"],
        "all_four_trajectories_finite": False,
        "analytic_endpoint_ratios": {
            metric: None for metric in CONVERGENCE_METRICS
        },
        "analytic_ratio_limit": None,
        "analytic_trend_pass": False,
        "self_finest_to_coarsest_ratio": None,
        "self_ratio_limit": None,
        "self_trend_pass": False,
        "credible_trend_pass": False,
        "platform_detected": False,
        "common_time_count": 0,
    }


def _space_not_run(
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return [dict(context)], {
        "execution_status": context["execution_status"],
        "not_run_reason": context["not_run_reason"],
        "primary_all_finite": False,
        "primary_all_selected_slopes_positive": False,
        "primary_velocity_n32_n16_ratio": None,
        "primary_velocity_ratio_limit": None,
        "primary_velocity_ratio_pass": False,
        "primary_space_pass": False,
        "primary_nonworsening": False,
        "space_plateau_conditional": False,
        "support_family_comparison_complete": False,
    }


def _disorder_not_run(
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return [dict(context)], {
        "execution_status": context["execution_status"],
        "not_run_reason": context["not_run_reason"],
        "complete": False,
        "regular_pass": False,
        "jitter_05_pass": False,
        "jitter_10_pass": False,
        "jitter_10_max_velocity_relative_l2": None,
        "regular_velocity_relative_l2": None,
        "jitter_10_to_regular_velocity_ratio": None,
        "jitter_10_velocity_ratio_limit": None,
        "jitter_10_velocity_ratio_pass": False,
        "robustness_pass": False,
        "sampled_failure_evidence_complete": False,
        "unsampled_failure_run_ids": [],
        "conditional_jitter_robustness": False,
    }


def _mach_not_run(
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return [dict(context)], {
        "execution_status": context["execution_status"],
        "not_run_reason": context["not_run_reason"],
        "complete_and_quantified": False,
        "velocity_error_improves_as_mach_decreases": False,
        "density_fluctuation_improves_as_mach_decreases": False,
        "weak_compressibility_error_dominance_supported": False,
        "model_form_dominant_declared": False,
    }


def _conditional_qualifications(
    *,
    time: Mapping[str, Any],
    space: Mapping[str, Any],
    disorder: Mapping[str, Any],
    mach: Mapping[str, Any],
) -> dict[str, bool]:
    """Derive the three preregistered conditional branches from evidence."""

    space_plateau = bool(
        time.get("execution_status") == "COMPLETE"
        and time.get("all_four_trajectories_finite") is True
        and time.get("credible_trend_pass") is True
        and space.get("execution_status") == "COMPLETE"
        and space.get("support_family_comparison_complete") is True
        and space.get("primary_space_pass") is False
        and space.get("primary_nonworsening") is True
        and space.get("space_plateau_conditional") is True
    )
    jitter_robustness = bool(
        disorder.get("execution_status") == "COMPLETE"
        and disorder.get("conditional_jitter_robustness") is True
    )
    model_form_dominance = bool(
        mach.get("execution_status") == "COMPLETE"
        and mach.get("complete_and_quantified") is True
        and mach.get(
            "velocity_error_improves_as_mach_decreases"
        )
        is True
        and mach.get(
            "weak_compressibility_error_dominance_supported"
        )
        is True
    )
    return {
        "time_pass_space_plateau": space_plateau,
        "regular_and_jitter05_pass_jitter10_fails": (
            jitter_robustness
        ),
        "quantified_model_form_error_dominant": (
            model_form_dominance
        ),
    }


def _derive_v2_status(
    *,
    raw_hard_checks: Mapping[str, bool],
    conditional_checks: Mapping[str, bool],
    disorder_robustness_pass: bool,
) -> tuple[str, dict[str, bool]]:
    """Apply failure priority while allowing only registered exemptions."""

    effective_hard_checks = {
        key: bool(value) for key, value in raw_hard_checks.items()
    }
    effective_hard_checks["primary_space"] = bool(
        raw_hard_checks["primary_space"]
        or conditional_checks["time_pass_space_plateau"]
    )
    effective_hard_checks["disorder_outcome_qualified"] = bool(
        disorder_robustness_pass
        or conditional_checks[
            "regular_and_jitter05_pass_jitter10_fails"
        ]
    )
    if not all(effective_hard_checks.values()):
        return "V2_FAIL", effective_hard_checks
    if any(conditional_checks.values()):
        return "V2_CONDITIONAL", effective_hard_checks
    return "V2_PASS", effective_hard_checks


def evaluate_all(bundle: EvidenceBundle) -> EvaluationProducts:
    """Evaluate every table and choose one failure-prioritized V2 status."""

    integrator_rows, integrator_pass = evaluate_integrator(bundle)
    zero = evaluate_zero_flow(bundle)
    conservation = evaluate_dynamic_conservation(bundle)
    time_count = int(
        (bundle.run_summary["_protocol"] == "time_convergence").sum()
    )
    if time_count == 4:
        time_rows, time = evaluate_time_convergence(bundle)
    else:
        time_rows, time = _time_not_run(
            _phase_stub_context(
                bundle,
                phase="time",
                protocols=("time_convergence",),
                expected_run_count=4,
            )
        )

    summary_resolutions = _summary_numeric_values(
        bundle,
        "resolution",
        ("N",),
    )
    primary_space_count = int(
        (
            (bundle.run_summary["_protocol"] == "space_convergence")
            & np.isin(summary_resolutions, (16, 24, 32))
        ).sum()
    )
    constant_support_count = int(
        (
            (
                bundle.run_summary["_protocol"]
                == "support_family_comparison"
            )
            & (
                bundle.run_summary["_support_family"]
                == "constant_neighbor"
            )
            & np.isin(summary_resolutions, (16, 24, 32))
        ).sum()
    )
    if primary_space_count == 3 and constant_support_count == 3:
        space_rows, space = evaluate_space_convergence(bundle)
    else:
        space_rows, space = _space_not_run(
            _phase_stub_context(
                bundle,
                phase="space_and_support",
                protocols=(
                    "space_convergence",
                    "support_family_comparison",
                ),
                expected_run_count=6,
            )
        )
    autograd = evaluate_autograd(bundle)
    disorder_count = int(
        (
            bundle.run_summary["_protocol"]
            == "disorder_robustness"
        ).sum()
    )
    if disorder_count == 7:
        disorder_rows, disorder = evaluate_disorder(bundle)
    else:
        disorder_rows, disorder = _disorder_not_run(
            _phase_stub_context(
                bundle,
                phase="disorder",
                protocols=("disorder_robustness",),
                expected_run_count=7,
            )
        )
    mach_count = int(
        (bundle.run_summary["_protocol"] == "mach_sensitivity").sum()
    )
    if mach_count == 3:
        mach_rows, mach = evaluate_mach(bundle)
    else:
        mach_rows, mach = _mach_not_run(
            _phase_stub_context(
                bundle,
                phase="mach",
                protocols=("mach_sensitivity",),
                expected_run_count=3,
            )
        )
    smoke = _smoke_gate(bundle)
    resources = evaluate_resources_and_clustering(bundle)
    provenance = evaluate_provenance(bundle)

    raw_hard_checks = {
        "integrator": integrator_pass,
        "zero_flow": bool(zero["pass"]),
        "dynamic_conservation": bool(conservation["pass"]),
        "time_four_finite": bool(time["all_four_trajectories_finite"]),
        "time_credible_trend": bool(time["credible_trend_pass"]),
        "primary_space": bool(space["primary_space_pass"]),
        "support_family_complete": bool(
            space["support_family_comparison_complete"]
        ),
        "autograd": bool(autograd["pass"]),
        "smoke": bool(smoke["pass"]),
        "disorder_complete": bool(disorder["complete"]),
        "regular_disorder_control": bool(disorder["regular_pass"]),
        "jitter_05_disorder_control": bool(
            disorder["jitter_05_pass"]
        ),
        "mach_quantified": bool(mach["complete_and_quantified"]),
        "resources_and_clustering": bool(resources["pass"]),
        "provenance": bool(provenance["pass"]),
    }
    conditional_checks = _conditional_qualifications(
        time=time,
        space=space,
        disorder=disorder,
        mach=mach,
    )
    space["conditional_space_plateau_eligible"] = conditional_checks[
        "time_pass_space_plateau"
    ]
    disorder["conditional_jitter_robustness_eligible"] = (
        conditional_checks[
            "regular_and_jitter05_pass_jitter10_fails"
        ]
    )
    mach["conditional_model_form_eligible"] = conditional_checks[
        "quantified_model_form_error_dominant"
    ]
    status, hard_checks = _derive_v2_status(
        raw_hard_checks=raw_hard_checks,
        conditional_checks=conditional_checks,
        disorder_robustness_pass=bool(disorder["robustness_pass"]),
    )
    allowed = tuple(
        _nested(bundle.configuration, "v2_decision", "allowed_status")
    )
    if tuple(allowed) != ALLOWED_FINAL_STATUSES:
        raise EvidenceError(
            f"allowed status drift: {allowed} != {ALLOWED_FINAL_STATUSES}"
        )
    if status not in allowed:
        raise EvidenceError(f"derived disallowed V2 status {status}")

    gate_rows = _build_gate_evidence(
        bundle,
        integrator_rows=integrator_rows,
        integrator_pass=integrator_pass,
        zero=zero,
        conservation=conservation,
        time=time,
        space=space,
        autograd=autograd,
        disorder=disorder,
        mach=mach,
        smoke=smoke,
        resources=resources,
        provenance=provenance,
    )
    hard_execution_status = {
        "dynamic_conservation": conservation.get(
            "execution_status",
            "COMPLETE",
        ),
        "time_four_finite": time.get("execution_status", "COMPLETE"),
        "time_credible_trend": time.get(
            "execution_status",
            "COMPLETE",
        ),
        "primary_space": space.get("execution_status", "COMPLETE"),
        "support_family_complete": space.get(
            "execution_status",
            "COMPLETE",
        ),
        "smoke": smoke.get("execution_status", "COMPLETE"),
        "disorder_complete": disorder.get(
            "execution_status",
            "COMPLETE",
        ),
        "regular_disorder_control": disorder.get(
            "execution_status",
            "COMPLETE",
        ),
        "jitter_05_disorder_control": disorder.get(
            "execution_status",
            "COMPLETE",
        ),
        "mach_quantified": mach.get("execution_status", "COMPLETE"),
        "disorder_outcome_qualified": disorder.get(
            "execution_status",
            "COMPLETE",
        ),
    }
    hard_not_run_reason = {
        "dynamic_conservation": conservation.get("not_run_reason", ""),
        "time_four_finite": time.get("not_run_reason", ""),
        "time_credible_trend": time.get("not_run_reason", ""),
        "primary_space": space.get("not_run_reason", ""),
        "support_family_complete": space.get("not_run_reason", ""),
        "smoke": smoke.get("not_run_reason", ""),
        "disorder_complete": disorder.get("not_run_reason", ""),
        "regular_disorder_control": disorder.get(
            "not_run_reason",
            "",
        ),
        "jitter_05_disorder_control": disorder.get(
            "not_run_reason",
            "",
        ),
        "mach_quantified": mach.get("not_run_reason", ""),
        "disorder_outcome_qualified": disorder.get(
            "not_run_reason",
            "",
        ),
    }
    for name, passed in hard_checks.items():
        if not passed and not any(
            row["check"] == f"decision_hard_{name}"
            for row in gate_rows
        ):
            not_run = hard_execution_status.get(name) == "NOT_RUN"
            gate_rows.append(
                {
                    "gate": "V2",
                    "check": f"decision_hard_{name}",
                    "passed": False,
                    "observed": "NOT_RUN" if not_run else False,
                    "threshold": True,
                    "source": "derived from prior gate rows",
                    "severity": "NOT_RUN" if not_run else "HARD",
                    "detail": (
                        hard_not_run_reason.get(name, "")
                        if not_run
                        else "failure-priority decision input"
                    ),
                }
            )
    gate_rows.append(
        {
            "gate": "V2",
            "check": "unique_final_status",
            "passed": status == "V2_PASS",
            "observed": status,
            "threshold": "V2_PASS; conditional/failure rules explicit",
            "source": "preregistered_primary_tgv.yml",
            "severity": "STATUS",
            "detail": json.dumps(
                {
                    "raw_hard_checks": raw_hard_checks,
                    "effective_hard_checks": hard_checks,
                    "conditional_checks": conditional_checks,
                },
                sort_keys=True,
            ),
        }
    )
    return EvaluationProducts(
        integrator_rows=integrator_rows,
        time_rows=time_rows,
        space_rows=space_rows,
        disorder_rows=disorder_rows,
        mach_rows=mach_rows,
        gate_rows=gate_rows,
        status=status,
    )


def _csv_scalar(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return "" if not math.isfinite(number) else number
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return str(value)


def _field_order(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    order: list[str] = []
    for row in rows:
        for key in row:
            if key not in order:
                order.append(key)
    if not order:
        raise EvidenceError("cannot write an empty evidence table")
    return order


def _stage_rows_lf(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
) -> Path:
    fields = _field_order(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: _csv_scalar(row.get(key)) for key in fields}
            )
    return temporary


def write_products(
    products: EvaluationProducts,
    *,
    output_directory: Path,
) -> None:
    """Write the six LF CSVs and sole LF-terminated V2 status."""

    table_targets: list[
        tuple[Path, Sequence[Mapping[str, Any]]]
    ] = [
        (
            output_directory / "integrator_gate_evidence.csv",
            products.integrator_rows,
        ),
        (
            output_directory / "time_convergence_metrics.csv",
            products.time_rows,
        ),
        (
            output_directory / "space_convergence_metrics.csv",
            products.space_rows,
        ),
        (
            output_directory / "disorder_summary.csv",
            products.disorder_rows,
        ),
        (
            output_directory / "mach_summary.csv",
            products.mach_rows,
        ),
        (
            output_directory / "stage01d_gate_evidence.csv",
            products.gate_rows,
        ),
    ]
    status_path = output_directory / "stage01d_v2_status.txt"
    all_targets = [path for path, _ in table_targets] + [status_path]
    existing = [path for path in all_targets if path.exists()]
    temporary_paths = [
        path.with_name(path.name + ".tmp") for path in all_targets
    ]
    existing_temporary = [
        path for path in temporary_paths if path.exists()
    ]
    if existing or existing_temporary:
        raise EvidenceError(
            "refusing to overwrite evaluator evidence; existing targets="
            f"{[str(path) for path in existing]}, existing temporary files="
            f"{[str(path) for path in existing_temporary]}"
        )

    staged: list[tuple[Path, Path]] = []
    for path, rows in table_targets:
        staged.append((_stage_rows_lf(path, rows), path))
    output_directory.mkdir(parents=True, exist_ok=True)
    status_temporary = status_path.with_name(status_path.name + ".tmp")
    with status_temporary.open("x", encoding="utf-8", newline="") as stream:
        stream.write(products.status + "\n")
    staged.append((status_temporary, status_path))

    # Every payload is complete before any public evidence target appears.
    for temporary, target in staged:
        if target.exists():
            raise EvidenceError(
                f"refusing late overwrite of evaluator evidence: {target}"
            )
        temporary.replace(target)


def run(
    *,
    project_root: Path = PROJECT_ROOT,
    experiment_root: Path = EXPERIMENT_ROOT,
    output_directory: Path | None = None,
    write: bool = True,
) -> EvaluationProducts:
    bundle = load_evidence(
        project_root=project_root,
        experiment_root=experiment_root,
    )
    products = evaluate_all(bundle)
    if write:
        destination = (
            bundle.results_root
            if output_directory is None
            else output_directory.resolve()
        )
        write_products(products, output_directory=destination)
    return products


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate existing Stage 01D evidence; never run TGV.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
    )
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=EXPERIMENT_ROOT,
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="evaluate all evidence without writing derived outputs",
    )
    args = parser.parse_args()
    try:
        products = run(
            project_root=args.project_root,
            experiment_root=args.experiment_root,
            output_directory=args.output_directory,
            write=not args.validate_only,
        )
    except EvidenceError as error:
        print(f"EVIDENCE_ERROR: {error}", file=sys.stderr)
        return 2
    print(products.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
