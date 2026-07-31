"""Run preregistered Stage 01D trajectories with incremental evidence."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from typing import Any, Iterable

import numpy as np
import torch
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from dynamic_solver.acceleration import (  # noqa: E402
    DynamicPhysicalParameters,
)
from dynamic_solver.diagnostics import (  # noqa: E402
    DIAGNOSTIC_SCHEMA_VERSION,
    DYNAMIC_DIAGNOSTIC_COLUMNS,
    DYNAMIC_RUN_TABLE_COLUMNS,
    collect_dynamic_diagnostics,
    diagnostic_record_to_json,
    evaluate_dynamic_gates,
    kinetic_energy,
    ordered_diagnostic_row,
    process_peak_rss_bytes,
    tgv_exact_kinetic_energy,
    tgv_exact_modal_amplitude,
    tgv_modal_basis,
)
from dynamic_solver.periodic_rollout import (  # noqa: E402
    explicit_midpoint_dynamic_step,
    prepare_dynamic_state,
)
from dynamic_solver.taylor_green import (  # noqa: E402
    initialize_taylor_green_state,
    taylor_green_velocity,
)
from structure_preserving.kernels import (  # noqa: E402
    divergence_from_vector_gradient,
    quadratic_weighted_least_squares,
)
from structure_preserving.neighborhood import (  # noqa: E402
    build_periodic_neighborhood,
    minimum_image,
    periodic_cartesian_layout,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_primary_tgv.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
SAMPLE_ROOT = RESULTS_ROOT / "trajectory_samples"
STATE_ROOT = RESULTS_ROOT / "trajectory_states"
LOG_ROOT = EXPERIMENT_ROOT / "logs"
SUMMARY_PATH = RESULTS_ROOT / "run_summary.csv"
INDEX_PATH = RESULTS_ROOT / "trajectory_index.csv"

RESOURCE_FAILURE_CLASSES = frozenset(
    {
        "RSS_LIMIT",
        "RSS_LIMIT_ARCHIVE",
        "MEMORY_GROWTH",
        "SYSTEM_MEMORY_PRESSURE",
        "PROJECTED_RUNTIME",
        "THERMAL_SLOWDOWN",
    }
)
CONTINUABLE_SCIENTIFIC_FAILURE_CLASSES = frozenset(
    {
        "DYNAMIC_GATE",
        "NONFINITE_STATE",
        "INVALID_PHYSICAL_STATE",
        "NEIGHBOR_DEFECT",
        "PARTICLE_CLUSTERING",
    }
)


@dataclass(frozen=True)
class RunSpec:
    protocol: str
    resolution: int
    support_family: str
    support_ratio: float
    dt: float
    t_final: float
    sound_speed: float
    layout: str = "regular"
    jitter_fraction: float = 0.0
    seed: int = 0
    zero_flow: bool = False

    @property
    def steps(self) -> int:
        value = int(round(self.t_final / self.dt))
        if not math.isclose(
            value * self.dt,
            self.t_final,
            rel_tol=0.0,
            abs_tol=2.0e-14,
        ):
            raise ValueError("t_final must be an integer multiple of dt")
        return value

    @property
    def dx(self) -> float:
        return 2.0 / self.resolution

    @property
    def run_id(self) -> str:
        raw = (
            f"{self.protocol}_{self.support_family}_"
            f"n{self.resolution}_h{self.support_ratio:.2f}_"
            f"dt{self.dt:.8f}_tf{self.t_final:.3f}_cs{self.sound_speed:.1f}_"
            f"{self.layout}_s{self.seed}"
        )
        return re.sub(r"[^A-Za-z0-9_-]+", "p", raw)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _git_hash() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()


def _source_tree_changes() -> list[str]:
    output = subprocess.check_output(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=PROJECT_ROOT,
        text=True,
    )
    ignored_prefixes = (
        "06_experiments/stage_01d_fixed_physics_tgv/results/",
        "06_experiments/stage_01d_fixed_physics_tgv/logs/",
        "06_experiments/stage_01d_fixed_physics_tgv/figures/",
        "06_experiments/stage_01d_fixed_physics_tgv/time_convergence/",
        "06_experiments/stage_01d_fixed_physics_tgv/space_convergence/",
        "06_experiments/stage_01d_fixed_physics_tgv/support_family_comparison/",
        "06_experiments/stage_01d_fixed_physics_tgv/disorder_robustness/",
        "06_experiments/stage_01d_fixed_physics_tgv/mach_sensitivity/",
        "06_experiments/stage_01d_integrator_verification/results/",
    )
    changes: list[str] = []
    for line in output.splitlines():
        path = line[3:].split(" -> ")[-1]
        if not path.startswith(ignored_prefixes):
            changes.append(line)
    return changes


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def _load_configuration() -> dict[str, Any]:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("preregistered configuration must be a mapping")
    if value.get("status") != "PREREGISTERED_BEFORE_FIRST_STAGE_01D_TGV_RUN":
        raise ValueError("Stage 01D configuration status is not preregistered")
    return value


def _spec_payload(
    spec: RunSpec,
    *,
    master_hash: str,
    git_hash: str,
) -> dict[str, Any]:
    _, _, initial_layout_sha256 = periodic_cartesian_layout(
        spec.resolution,
        jitter_fraction=spec.jitter_fraction,
        seed=spec.seed,
        dtype=torch.float64,
    )
    sample_steps = list(_sample_steps(spec))
    artifact_paths = _resolved_paths(spec.run_id)
    return {
        "stage": "01D",
        "run_id": spec.run_id,
        "run_spec": asdict(spec),
        "steps": spec.steps,
        "particle_count": spec.resolution**2,
        "sample_steps": sample_steps,
        "sample_times": [step * spec.dt for step in sample_steps],
        "dx": spec.dx,
        "support": spec.support_ratio * spec.dx,
        "dtype": "float64",
        "device": "cpu",
        "physical_viscosity": 0.02,
        "mass_reference_density": 1.0,
        "eos_reference_density_mode": (
            "initial_uniform_kernel_sum_mean"
            if spec.zero_flow
            else "fixed"
        ),
        "eos_reference_density_fixed_value": (
            None if spec.zero_flow else 1.0
        ),
        "velocity_amplitude": 1.0,
        "domain": [[-1.0, -1.0], [1.0, 1.0]],
        "initial_layout_sha256": initial_layout_sha256,
        "one_trajectory_per_process": True,
        "peak_rss_measurement": "getrusage_RUSAGE_SELF",
        "artifact_paths": {
            key: _relative(path)
            for key, path in artifact_paths.items()
        },
        "master_preregistration_path": _relative(CONFIG_PATH),
        "master_preregistration_sha256": master_hash,
        "git_hash": git_hash,
        "method": "explicit_midpoint_rk2_stage01c_conservative_pairs",
    }


def _safe_token(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def _redact_private_paths(value: str) -> str:
    rendered = value.replace(str(PROJECT_ROOT), "<PROJECT_ROOT>")
    rendered = rendered.replace(str(Path.home()), "<HOME>")
    return re.sub(r"/Users/[^/\\s:]+", "<HOME>", rendered)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_json_once_or_verify(path: Path, value: Any) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != value:
            raise RuntimeError(
                f"existing immutable evidence differs: {_relative(path)}"
            )
        return
    _write_json(path, value)


def _current_rss_bytes() -> int:
    output = subprocess.check_output(
        ("ps", "-o", "rss=", "-p", str(os.getpid())),
        text=True,
    ).strip()
    return int(output) * 1024


def _system_memory_free_percent() -> float:
    output = subprocess.check_output(
        ("/usr/bin/memory_pressure", "-Q"),
        text=True,
        stderr=subprocess.STDOUT,
    )
    match = re.search(
        r"System-wide memory free percentage:\s*([0-9.]+)%",
        output,
    )
    if match is None:
        raise RuntimeError("cannot parse memory_pressure -Q output")
    return float(match.group(1))


def _memory_growth_flag(
    values: list[int],
    policy: dict[str, Any],
) -> bool:
    transitions = int(policy["consecutive_strict_increases"])
    required_values = transitions + 1
    if len(values) < required_values:
        return False
    selected = values[-required_values:]
    increasing = all(
        right > left for left, right in zip(selected, selected[1:])
    )
    absolute = selected[-1] - selected[0]
    fractional = absolute / max(selected[0], 1)
    return bool(
        increasing
        and absolute >= int(policy["minimum_absolute_increase_bytes"])
        and fractional >= float(policy["minimum_fractional_increase"])
    )


def _sustained_pressure_flag(
    values: list[float],
    policy: dict[str, Any],
) -> bool:
    count = int(policy["consecutive_samples"])
    if len(values) < count:
        return False
    threshold = float(policy["free_percentage_below"])
    return all(value < threshold for value in values[-count:])


def _sample_steps(spec: RunSpec) -> tuple[int, ...]:
    if spec.zero_flow:
        return tuple(range(spec.steps + 1))
    count = min(21, spec.steps + 1)
    values = np.linspace(0, spec.steps, count, dtype=np.int64)
    return tuple(int(value) for value in np.unique(values))


def _angular_momentum(
    positions: torch.Tensor,
    velocities: torch.Tensor,
    masses: torch.Tensor,
) -> torch.Tensor:
    return torch.sum(
        masses
        * (
            positions[:, 0] * velocities[:, 1]
            - positions[:, 1] * velocities[:, 0]
        )
    )


def _divergence_l2(
    velocity: torch.Tensor,
    masses: torch.Tensor,
    density: torch.Tensor,
    neighborhood: Any,
) -> float:
    volume = masses / density
    gradient, _, _ = quadratic_weighted_least_squares(
        neighborhood,
        velocity,
        volume,
    )
    divergence = divergence_from_vector_gradient(gradient)
    return float(torch.sqrt(torch.mean(divergence.square())))


def _resolved_paths(run_id: str) -> dict[str, Path]:
    return {
        "sample": SAMPLE_ROOT / f"{run_id}.csv",
        "state": STATE_ROOT / f"{run_id}.npz",
        "config": LOG_ROOT / f"{run_id}_config.json",
        "stdout": LOG_ROOT / f"{run_id}_stdout.log",
        "stderr": LOG_ROOT / f"{run_id}_stderr.log",
        "failure": LOG_ROOT / f"{run_id}_failure.txt",
    }


def _write_state_archive(
    path: Path,
    *,
    steps: list[int],
    times: list[float],
    positions: list[np.ndarray],
    velocities: list[np.ndarray],
    densities: list[np.ndarray],
    pressures: list[np.ndarray],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(
        temporary,
        steps=np.asarray(steps, dtype=np.int64),
        times=np.asarray(times, dtype=np.float64),
        positions=np.stack(positions),
        velocities=np.stack(velocities),
        densities=np.stack(densities),
        pressures=np.stack(pressures),
    )
    temporary.replace(path)


def _read_summary_rows() -> list[dict[str, str]]:
    if not SUMMARY_PATH.is_file():
        return []
    with SUMMARY_PATH.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_table(
    path: Path,
    rows: Iterable[dict[str, Any]],
    *,
    preferred: Iterable[str] = (),
) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"cannot write empty table: {path}")
    preferred_fields = list(preferred)
    extra = sorted(
        {
            key
            for row in values
            for key in row
            if key not in preferred_fields
        }
    )
    fields = preferred_fields + extra
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(values)
    temporary.replace(path)


def _upsert_summary(row: dict[str, Any]) -> None:
    rows = [
        existing
        for existing in _read_summary_rows()
        if existing.get("run_id") != row["run_id"]
    ]
    rows.append(row)
    rows.sort(key=lambda value: str(value["run_id"]))
    _write_table(
        SUMMARY_PATH,
        rows,
        preferred=DYNAMIC_RUN_TABLE_COLUMNS,
    )
    index_rows = [
        {
            "run_id": value["run_id"],
            "protocol": value["protocol"],
            "status": value["status"],
            "sample_table_path": value["sample_table_path"],
            "state_path": value["state_path"],
            "config_path": value["config_path"],
            "config_hash": value["config_hash"],
            "git_hash": value["git_hash"],
        }
        for value in rows
    ]
    _write_table(INDEX_PATH, index_rows)


def _numeric_max(
    rows: list[dict[str, Any]],
    key: str,
) -> float | None:
    values = [
        float(row[key])
        for row in rows
        if row.get(key) is not None
    ]
    return max(values) if values else None


def _numeric_min(
    rows: list[dict[str, Any]],
    key: str,
) -> float | None:
    values = [
        float(row[key])
        for row in rows
        if row.get(key) is not None
    ]
    return min(values) if values else None


def _build_summary(
    spec: RunSpec,
    *,
    config_hash: str,
    git_hash: str,
    paths: dict[str, Path],
    records: list[dict[str, Any]],
    status: str,
    failure_class: str,
    failure_reason: str,
    first_failure_step: int | None,
    first_failure_time: float | None,
    wall_seconds: float,
    step_times: list[float],
    current_rss: list[int],
    free_percent: list[float],
    memory_growth: bool,
    sustained_pressure: bool,
    checkpoint_available: bool,
    eos_reference_density: float | None,
    final_process_peak_rss_bytes: int | None,
) -> dict[str, Any]:
    final = records[-1] if records else {}
    thermal = final.get("thermal_slowdown_fraction")
    min_separation = _numeric_min(records, "minimum_separation")
    ratio = (
        None
        if min_separation is None
        else min_separation / spec.dx
    )
    row: dict[str, Any] = {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "run_id": spec.run_id,
        "config_hash": config_hash,
        "git_hash": git_hash,
        "protocol": spec.protocol,
        "method_id": "explicit_midpoint_rk2_stage01c_pairs",
        "device": "cpu",
        "dtype": "float64",
        "resolution": spec.resolution,
        "particle_count": spec.resolution**2,
        "dt": spec.dt,
        "t_final": spec.t_final,
        "sample_interval": (
            spec.t_final / max(len(_sample_steps(spec)) - 1, 1)
        ),
        "status": status,
        "failure_class": failure_class,
        "failure_reason": failure_reason,
        "first_failure_step": first_failure_step,
        "first_failure_time": first_failure_time,
        "final_velocity_relative_l2": final.get(
            "velocity_relative_l2"
        ),
        "maximum_velocity_relative_l2": _numeric_max(
            records,
            "velocity_relative_l2",
        ),
        "final_modal_amplitude_relative_error": final.get(
            "modal_amplitude_relative_error"
        ),
        "final_kinetic_energy_relative_error": final.get(
            "kinetic_energy_relative_error"
        ),
        "maximum_density_fluctuation_relative_rms": _numeric_max(
            records,
            "density_fluctuation_relative_rms",
        ),
        "maximum_mach": _numeric_max(records, "maximum_mach"),
        "maximum_momentum_drift_normalized": _numeric_max(
            records,
            "momentum_drift_normalized",
        ),
        "maximum_angular_momentum_drift_normalized": _numeric_max(
            records,
            "angular_momentum_drift_normalized",
        ),
        "maximum_pressure_relative_pair_force_residual": _numeric_max(
            records,
            "pressure_relative_pair_force_residual",
        ),
        "maximum_viscosity_relative_pair_force_residual": _numeric_max(
            records,
            "viscosity_relative_pair_force_residual",
        ),
        "maximum_relative_total_internal_force": _numeric_max(
            records,
            "relative_total_internal_force",
        ),
        "maximum_assembled_relative_internal_force": _numeric_max(
            records,
            "assembled_relative_internal_force",
        ),
        "maximum_assembly_force_consistency_relative_linf": _numeric_max(
            records,
            "assembly_force_consistency_relative_linf",
        ),
        "maximum_viscous_power": _numeric_max(
            records,
            "accumulated_viscous_power",
        ),
        "minimum_separation": min_separation,
        "minimum_neighbor_count": _numeric_min(
            records,
            "neighbor_count_min",
        ),
        "maximum_neighbor_count": _numeric_max(
            records,
            "neighbor_count_max",
        ),
        "maximum_duplicate_edge_count": _numeric_max(
            records,
            "neighbor_duplicate_edge_count",
        ),
        "maximum_omitted_strict_support_edge_count": _numeric_max(
            records,
            "neighbor_omitted_strict_support_edge_count",
        ),
        "maximum_nonreciprocal_nonself_edge_count": _numeric_max(
            records,
            "neighbor_nonreciprocal_nonself_edge_count",
        ),
        "wall_clock_seconds": wall_seconds,
        "mean_step_seconds": (
            sum(step_times) / len(step_times) if step_times else None
        ),
        "thermal_slowdown_fraction": thermal,
        "peak_rss_bytes": (
            max(
                [
                    int(row["peak_rss_bytes"])
                    for row in records
                    if row.get("peak_rss_bytes") is not None
                ]
                + (
                    [int(final_process_peak_rss_bytes)]
                    if final_process_peak_rss_bytes is not None
                    else []
                )
            )
            if records or final_process_peak_rss_bytes is not None
            else None
        ),
        "peak_rss_measurement": (
            "getrusage_RUSAGE_SELF_single_trajectory_process_through_archive"
        ),
        "sample_table_path": _relative(paths["sample"]),
        "state_path": _relative(paths["state"]),
        "config_path": _relative(paths["config"]),
        "stdout_log_path": _relative(paths["stdout"]),
        "stderr_log_path": _relative(paths["stderr"]),
        "failure_evidence_path": (
            _relative(paths["failure"]) if paths["failure"].is_file() else ""
        ),
        "support_family": spec.support_family,
        "support_ratio": spec.support_ratio,
        "layout": spec.layout,
        "jitter_fraction": spec.jitter_fraction,
        "seed": spec.seed,
        "sound_speed": spec.sound_speed,
        "physical_viscosity": 0.02,
        "mass_reference_density": 1.0,
        "eos_reference_density": eos_reference_density,
        "velocity_amplitude": 1.0,
        "dx": spec.dx,
        "edge_count": final.get("neighbor_edge_count"),
        "acoustic_cfl_max": (
            spec.dt
            * (
                spec.sound_speed
                + float(_numeric_max(records, "maximum_speed") or 0.0)
            )
            / spec.dx
        ),
        "minimum_separation_over_dx": ratio,
        "clustering_pass": (
            None if ratio is None else ratio >= 0.25
        ),
        "sustained_memory_pressure": sustained_pressure,
        "memory_growth_with_step": memory_growth,
        "checkpoint_available": checkpoint_available,
        "projected_over_two_hours_without_checkpoint": (
            failure_class == "PROJECTED_RUNTIME"
        ),
        "current_rss_initial_bytes": (
            current_rss[0] if current_rss else None
        ),
        "current_rss_final_bytes": (
            current_rss[-1] if current_rss else None
        ),
        "system_memory_free_minimum_percent": (
            min(free_percent) if free_percent else None
        ),
        "all_states_finite": bool(records)
        and all(bool(row.get("state_all_finite")) for row in records),
        "source_tree_dirty": False,
    }
    return row


def _run_one_impl(
    spec: RunSpec,
    *,
    configuration: dict[str, Any],
) -> bool:
    source_changes = _source_tree_changes()
    if source_changes:
        raise RuntimeError(
            "refusing formal trajectory with source-tree changes: "
            + "; ".join(source_changes)
        )
    master_hash = _sha256_bytes(CONFIG_PATH.read_bytes())
    git_hash = _git_hash()
    payload = _spec_payload(
        spec,
        master_hash=master_hash,
        git_hash=git_hash,
    )
    config_hash = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
    payload["resolved_config_sha256"] = config_hash
    paths = _resolved_paths(spec.run_id)
    existing_evidence = [
        _relative(path) for path in paths.values() if path.exists()
    ]
    if existing_evidence:
        raise RuntimeError(
            "refusing to overwrite existing trajectory evidence: "
            + ", ".join(existing_evidence)
        )
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(paths["config"], payload)
    paths["stdout"].write_text("", encoding="utf-8")
    paths["stderr"].write_text("", encoding="utf-8")
    start_wall = time.perf_counter()

    physics = configuration["primary_tgv"]
    resource_policy = configuration["resource_stopping"]
    memory_policy = resource_policy["memory_growth_policy"]
    pressure_policy = resource_policy["sustained_memory_pressure_policy"]
    pair_tolerance = float(
        configuration["dynamic_conservation_thresholds"][
            "maximum_relative_pair_force_residual"
        ]
    )
    total_tolerance = float(
        configuration["dynamic_conservation_thresholds"][
            "maximum_characteristic_normalized_internal_force_residual"
        ]
    )
    power_tolerance = float(
        configuration["dynamic_conservation_thresholds"][
            "viscous_power_positive_absolute_tolerance"
        ]
    )
    rss_limit = int(resource_policy["peak_rss_bytes"])
    thermal_limit = float(
        resource_policy["second_half_mean_step_time_increase_fraction"]
    )
    runtime_limit = float(
        resource_policy["projected_single_experiment_seconds_without_checkpoint"]
    )
    clustering_limit = float(
        configuration["particle_clustering_diagnostic"][
            "minimum_separation_over_dx"
        ]
    )

    state = initialize_taylor_green_state(
        spec.resolution,
        support_ratio=spec.support_ratio,
        reference_density=float(physics["rho0"]),
        velocity_amplitude=float(physics["U0"]),
        physical_viscosity=float(physics["physical_viscosity"]),
        sound_speed=spec.sound_speed,
        jitter_fraction=spec.jitter_fraction,
        seed=spec.seed,
    )
    if spec.zero_flow:
        state = state.with_updates(
            velocities=torch.zeros_like(state.velocities),
            pressures=torch.zeros_like(state.pressures),
        )
        eos_reference_density = float(state.densities.mean())
    else:
        eos_reference_density = float(physics["rho0"])
    parameters = DynamicPhysicalParameters(
        reference_density=eos_reference_density,
        sound_speed=spec.sound_speed,
        physical_viscosity=float(physics["physical_viscosity"]),
    )
    state, evaluation = prepare_dynamic_state(state, parameters)
    initial_positions = state.positions.detach().clone()
    initial_density = evaluation.densities.detach().clone()
    unwrapped_positions = state.positions.detach().clone()
    reference_momentum = torch.sum(
        state.masses[:, None] * state.velocities,
        dim=0,
    )
    reference_angular = _angular_momentum(
        unwrapped_positions,
        state.velocities,
        state.masses,
    )
    initial_energy = kinetic_energy(state.velocities, state.masses)
    selected_steps = set(_sample_steps(spec))
    records: list[dict[str, Any]] = []
    archive_steps: list[int] = []
    archive_times: list[float] = []
    archive_positions: list[np.ndarray] = []
    archive_velocities: list[np.ndarray] = []
    archive_densities: list[np.ndarray] = []
    archive_pressures: list[np.ndarray] = []
    step_times: list[float] = []
    current_rss: list[int] = []
    free_percent: list[float] = []
    memory_growth = False
    sustained_pressure = False
    checkpoint_available = False
    failure_class = ""
    failure_reason = ""
    first_failure_step: int | None = None
    first_failure_time: float | None = None
    sample_index = 0

    with paths["sample"].open(
        "w",
        newline="",
        encoding="utf-8",
    ) as sample_stream, paths["stdout"].open(
        "a",
        encoding="utf-8",
    ) as stdout_stream, paths["stderr"].open(
        "a",
        encoding="utf-8",
    ) as stderr_stream:
        writer = csv.DictWriter(
            sample_stream,
            fieldnames=DYNAMIC_DIAGNOSTIC_COLUMNS,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        try:
            for step_index in range(spec.steps + 1):
                if step_index in selected_steps:
                    rss = _current_rss_bytes()
                    free = _system_memory_free_percent()
                    current_rss.append(rss)
                    free_percent.append(free)
                    memory_growth = memory_growth or _memory_growth_flag(
                        current_rss,
                        memory_policy,
                    )
                    sustained_pressure = (
                        sustained_pressure
                        or _sustained_pressure_flag(
                            free_percent,
                            pressure_policy,
                        )
                    )
                    if spec.zero_flow:
                        exact_velocity = torch.zeros_like(state.velocities)
                        modal_basis = None
                        exact_amplitude = None
                        exact_energy = 0.0
                    else:
                        exact_velocity = taylor_green_velocity(
                            state.positions,
                            state.time,
                            velocity_amplitude=float(physics["U0"]),
                            physical_viscosity=float(
                                physics["physical_viscosity"]
                            ),
                        )
                        modal_basis = tgv_modal_basis(state.positions)
                        exact_amplitude = tgv_exact_modal_amplitude(
                            state.time,
                            initial_velocity=float(physics["U0"]),
                            kinematic_viscosity=float(
                                physics["physical_viscosity"]
                            ),
                        )
                        exact_energy = tgv_exact_kinetic_energy(
                            state.time,
                            initial_kinetic_energy=initial_energy,
                            kinematic_viscosity=float(
                                physics["physical_viscosity"]
                            ),
                        )
                    divergence_l2 = _divergence_l2(
                        state.velocities,
                        state.masses,
                        evaluation.densities,
                        evaluation.neighborhood,
                    )
                    record = collect_dynamic_diagnostics(
                        positions=state.positions,
                        velocity=state.velocities,
                        mass=state.masses,
                        density=evaluation.densities,
                        pressure=evaluation.pressures,
                        sound_speed=spec.sound_speed,
                        neighborhood=evaluation.neighborhood,
                        physical_viscosity=float(
                            physics["physical_viscosity"]
                        ),
                        assembled_acceleration=evaluation.acceleration,
                        time=state.time,
                        exact_velocity=exact_velocity,
                        modal_basis=modal_basis,
                        exact_modal_amplitude=exact_amplitude,
                        exact_kinetic_energy=exact_energy,
                        reference_density=eos_reference_density,
                        reference_momentum=reference_momentum,
                        reference_angular_momentum=reference_angular,
                        characteristic_velocity=float(physics["U0"]),
                        characteristic_length=float(physics["L"]),
                        angular_momentum_positions=unwrapped_positions,
                        velocity_divergence_l2=divergence_l2,
                        run_id=spec.run_id,
                        config_hash=config_hash,
                        git_hash=git_hash,
                        sample_index=sample_index,
                        step=step_index,
                        dt=spec.dt,
                        wall_clock_seconds=(
                            time.perf_counter() - start_wall
                        ),
                        step_times_seconds=step_times,
                        peak_rss_bytes=process_peak_rss_bytes(),
                        viscous_power_positive_absolute_tolerance=(
                            power_tolerance
                        ),
                    )
                    record["current_rss_bytes"] = rss
                    record["system_memory_free_percent"] = free
                    if spec.zero_flow:
                        record["position_drift_linf"] = float(
                            (
                                state.positions - initial_positions
                            ).abs().max()
                        )
                        record["velocity_linf"] = float(
                            state.velocities.abs().max()
                        )
                        record["relative_density_drift"] = float(
                            (
                                evaluation.densities - initial_density
                            ).abs().max()
                            / initial_density.abs().max()
                        )
                    writer.writerow(ordered_diagnostic_row(record))
                    sample_stream.flush()
                    records.append(record)
                    archive_steps.append(step_index)
                    archive_times.append(state.time)
                    archive_positions.append(
                        state.positions.detach().cpu().numpy().copy()
                    )
                    archive_velocities.append(
                        state.velocities.detach().cpu().numpy().copy()
                    )
                    archive_densities.append(
                        evaluation.densities.detach().cpu().numpy().copy()
                    )
                    archive_pressures.append(
                        evaluation.pressures.detach().cpu().numpy().copy()
                    )
                    stdout_stream.write(
                        diagnostic_record_to_json(record) + "\n"
                    )
                    stdout_stream.flush()
                    gates = evaluate_dynamic_gates(
                        record,
                        pair_relative_tolerance=pair_tolerance,
                        total_force_relative_tolerance=total_tolerance,
                        viscous_power_positive_absolute_tolerance=(
                            power_tolerance
                        ),
                        rss_limit_bytes=rss_limit,
                        thermal_slowdown_limit=thermal_limit,
                    )
                    zero_violation = ""
                    if spec.zero_flow:
                        zero_config = configuration["zero_flow"]
                        zero_checks = (
                            (
                                "position drift",
                                float(record["position_drift_linf"]),
                                float(
                                    zero_config[
                                        "position_drift_tolerance"
                                    ]
                                ),
                            ),
                            (
                                "velocity Linf",
                                float(record["velocity_linf"]),
                                float(
                                    zero_config[
                                        "velocity_linf_tolerance"
                                    ]
                                ),
                            ),
                            (
                                "relative density drift",
                                float(record["relative_density_drift"]),
                                float(
                                    zero_config[
                                        "relative_density_drift_tolerance"
                                    ]
                                ),
                            ),
                            (
                                "pressure Linf",
                                float(record["pressure_absolute_maximum"]),
                                float(
                                    zero_config[
                                        "pressure_linf_tolerance"
                                    ]
                                ),
                            ),
                        )
                        failed_zero = [
                            f"{name}={observed} > {limit}"
                            for name, observed, limit in zero_checks
                            if observed > limit
                        ]
                        zero_violation = "; ".join(failed_zero)
                    separation = record.get("minimum_separation")
                    clustered = (
                        separation is not None
                        and float(separation) / spec.dx < clustering_limit
                    )
                    physics_stop = any(
                        gates[name] is False
                        for name in (
                            "finite_state_pass",
                            "physical_state_pass",
                            "topology_pass",
                            "pressure_pair_residual_pass",
                            "viscosity_pair_residual_pass",
                            "pressure_total_force_pass",
                            "viscosity_total_force_pass",
                            "combined_total_force_pass",
                            "assembled_total_force_pass",
                            "assembly_consistency_pass",
                            "viscous_power_nonpositive_pass",
                            "viscous_power_identity_pass",
                        )
                    )
                    thermal_stop = (
                        step_index == spec.steps
                        and gates["thermal_limit_pass"] is False
                    )
                    if zero_violation:
                        failure_class = "ZERO_EQUILIBRIUM"
                        failure_reason = zero_violation
                    elif gates["rss_limit_pass"] is False:
                        failure_class = "RSS_LIMIT"
                        failure_reason = _canonical_json(gates)
                    elif memory_growth:
                        failure_class = "MEMORY_GROWTH"
                        failure_reason = "sustained current RSS growth"
                    elif sustained_pressure:
                        failure_class = "SYSTEM_MEMORY_PRESSURE"
                        failure_reason = "sustained low system memory"
                    elif thermal_stop:
                        failure_class = "THERMAL_SLOWDOWN"
                        failure_reason = _canonical_json(gates)
                    elif physics_stop:
                        if gates["finite_state_pass"] is False:
                            failure_class = "NONFINITE_STATE"
                        elif gates["physical_state_pass"] is False:
                            failure_class = "INVALID_PHYSICAL_STATE"
                        elif gates["topology_pass"] is False:
                            failure_class = "NEIGHBOR_DEFECT"
                        else:
                            failure_class = "DYNAMIC_GATE"
                        failure_reason = _canonical_json(gates)
                    elif clustered:
                        failure_class = "PARTICLE_CLUSTERING"
                        failure_reason = (
                            f"minimum separation/dx below {clustering_limit}"
                        )
                    if failure_class:
                        first_failure_step = step_index
                        first_failure_time = state.time
                        raise RuntimeError(failure_reason)
                    sample_index += 1

                if step_index == spec.steps:
                    break
                step_start = time.perf_counter()
                previous_position = state.positions
                with torch.no_grad():
                    result = explicit_midpoint_dynamic_step(
                        state,
                        dt=spec.dt,
                        parameters=parameters,
                        start_evaluation=evaluation,
                    )
                step_times.append(time.perf_counter() - step_start)
                displacement = minimum_image(
                    result.state.positions - previous_position,
                    state.domain_extent,
                )
                unwrapped_positions = unwrapped_positions + displacement
                state = result.state.with_updates(
                    time=(step_index + 1) * spec.dt,
                )
                evaluation = result.end_evaluation
                if (
                    len(step_times) >= 5
                    and (
                        time.perf_counter() - start_wall
                        + (
                            sum(step_times) / len(step_times)
                            * (spec.steps - step_index)
                        )
                    )
                    > runtime_limit
                    and not checkpoint_available
                ):
                    failure_class = "PROJECTED_RUNTIME"
                    failure_reason = (
                        f"projected runtime exceeds {runtime_limit} seconds "
                        "without checkpoint"
                    )
                    first_failure_step = step_index + 1
                    first_failure_time = state.time
                    raise RuntimeError(failure_reason)
        except Exception:
            if not failure_class:
                failure_class = "EXCEPTION"
                failure_reason = "trajectory raised an exception"
                first_failure_step = len(step_times)
                first_failure_time = state.time
            rendered = _redact_private_paths(traceback.format_exc())
            paths["failure"].write_text(rendered, encoding="utf-8")
            stderr_stream.write(rendered)
            stderr_stream.flush()

    if archive_steps:
        _write_state_archive(
            paths["state"],
            steps=archive_steps,
            times=archive_times,
            positions=archive_positions,
            velocities=archive_velocities,
            densities=archive_densities,
            pressures=archive_pressures,
        )
    final_process_peak_rss = process_peak_rss_bytes()
    if final_process_peak_rss > rss_limit:
        prior_failure_class = failure_class
        prior_failure_reason = failure_reason
        failure_class = "RSS_LIMIT_ARCHIVE"
        failure_reason = (
            f"process peak RSS through state archive "
            f"{final_process_peak_rss} exceeds {rss_limit} bytes"
        )
        if prior_failure_class:
            failure_reason += (
                f"; prior_failure_class={prior_failure_class}; "
                f"prior_failure_reason={prior_failure_reason}"
            )
        if first_failure_step is None:
            first_failure_step = spec.steps
            first_failure_time = state.time
        archive_failure = (
            "RSS_LIMIT_ARCHIVE\n"
            f"observed_peak_rss_bytes={final_process_peak_rss}\n"
            f"limit_bytes={rss_limit}\n"
        )
        with paths["failure"].open("a", encoding="utf-8") as stream:
            stream.write(archive_failure)
        with paths["stderr"].open("a", encoding="utf-8") as stream:
            stream.write(archive_failure)
    wall_seconds = time.perf_counter() - start_wall
    success = (
        not failure_class
        and archive_steps
        and archive_steps[-1] == spec.steps
    )
    summary = _build_summary(
        spec,
        config_hash=config_hash,
        git_hash=git_hash,
        paths=paths,
        records=records,
        status="PASS" if success else "FAIL",
        failure_class=failure_class,
        failure_reason=failure_reason,
        first_failure_step=first_failure_step,
        first_failure_time=first_failure_time,
        wall_seconds=wall_seconds,
        step_times=step_times,
        current_rss=current_rss,
        free_percent=free_percent,
        memory_growth=memory_growth,
        sustained_pressure=sustained_pressure,
        checkpoint_available=checkpoint_available,
        eos_reference_density=eos_reference_density,
        final_process_peak_rss_bytes=final_process_peak_rss,
    )
    _upsert_summary(summary)
    print(
        f"{spec.run_id}: {'PASS' if success else 'FAIL'} "
        f"steps={archive_steps[-1] if archive_steps else 0}/{spec.steps} "
        f"wall={wall_seconds:.3f}s"
    )
    return bool(success)


def run_one(
    spec: RunSpec,
    *,
    configuration: dict[str, Any],
) -> bool:
    """Run once and retain failures that occur after evidence allocation."""

    try:
        return _run_one_impl(spec, configuration=configuration)
    except Exception as error:
        paths = _resolved_paths(spec.run_id)
        message = str(error)
        if (
            not paths["config"].is_file()
            or message.startswith("refusing formal trajectory")
            or message.startswith("refusing to overwrite")
        ):
            raise

        rendered = _redact_private_paths(traceback.format_exc())
        if not paths["failure"].exists():
            paths["failure"].write_text(rendered, encoding="utf-8")
        with paths["stderr"].open("a", encoding="utf-8") as stream:
            stream.write(rendered)
        if not paths["sample"].exists():
            with paths["sample"].open(
                "w",
                newline="",
                encoding="utf-8",
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=DYNAMIC_DIAGNOSTIC_COLUMNS,
                    lineterminator="\n",
                )
                writer.writeheader()

        rows = _read_summary_rows()
        if not any(row.get("run_id") == spec.run_id for row in rows):
            master_hash = _sha256_bytes(CONFIG_PATH.read_bytes())
            git_hash = _git_hash()
            payload = _spec_payload(
                spec,
                master_hash=master_hash,
                git_hash=git_hash,
            )
            config_hash = _sha256_bytes(
                _canonical_json(payload).encode("utf-8")
            )
            reason = _redact_private_paths(
                f"{type(error).__name__}: {error}"
            )
            summary = _build_summary(
                spec,
                config_hash=config_hash,
                git_hash=git_hash,
                paths=paths,
                records=[],
                status="FAIL",
                failure_class="INITIALIZATION_OR_FINALIZATION_EXCEPTION",
                failure_reason=reason,
                first_failure_step=0,
                first_failure_time=0.0,
                wall_seconds=0.0,
                step_times=[],
                current_rss=[],
                free_percent=[],
                memory_growth=False,
                sustained_pressure=False,
                checkpoint_available=False,
                eos_reference_density=None,
                final_process_peak_rss_bytes=None,
            )
            _upsert_summary(summary)
        print(f"{spec.run_id}: FAIL before complete trajectory sampling")
        return False


def _specs_for_phase(
    phase: str,
    configuration: dict[str, Any],
) -> list[RunSpec]:
    primary = configuration["primary_tgv"]
    c_s = float(primary["sound_speed"])
    specs: list[RunSpec] = []
    if phase == "zero":
        zero = configuration["zero_flow"]
        specs.append(
            RunSpec(
                protocol="zero_flow",
                resolution=int(zero["resolution"]),
                support_family="constant_neighbor",
                support_ratio=float(zero["support_ratio"]),
                dt=float(zero["time_step"]),
                t_final=float(zero["time_step"]) * int(zero["steps"]),
                sound_speed=c_s,
                zero_flow=True,
            )
        )
    elif phase == "smoke":
        for name, values in configuration["smoke_tests"].items():
            resolution = int(values["resolution"])
            specs.append(
                RunSpec(
                    protocol=f"smoke_n{resolution}",
                    resolution=resolution,
                    support_family="increasing_neighbor",
                    support_ratio=float(values["support_ratio"]),
                    dt=float(values["time_step"]),
                    t_final=float(values["final_time"]),
                    sound_speed=c_s,
                )
            )
    elif phase == "time":
        values = configuration["time_convergence"]
        for dt in values["time_steps"]:
            specs.append(
                RunSpec(
                    protocol="time_convergence",
                    resolution=int(values["resolution"]),
                    support_family=str(values["support_family"]),
                    support_ratio=float(values["support_ratio"]),
                    dt=float(dt),
                    t_final=float(values["final_time"]),
                    sound_speed=c_s,
                )
            )
    elif phase in {"space", "n48"}:
        values = configuration["space_convergence"]
        selected = (
            [48]
            if phase == "n48"
            else [int(value) for value in values["primary_resolutions"]]
        )
        ratios = values["resolutions_and_support_ratios"]
        for resolution in selected:
            specs.append(
                RunSpec(
                    protocol="space_convergence",
                    resolution=resolution,
                    support_family=str(values["support_family"]),
                    support_ratio=float(
                        ratios.get(resolution, ratios.get(str(resolution)))
                    ),
                    dt=float(values["time_step"]),
                    t_final=float(values["final_time"]),
                    sound_speed=c_s,
                )
            )
    elif phase == "support":
        values = configuration["support_family_comparison"]
        # The increasing-neighbor N16/N24/N32 trajectories are byte-for-byte
        # the primary space specifications and are reused as that side of the
        # comparison.  Only the three constant-neighbor counterparts are new.
        families = (
            ("constant_neighbor", values["constant_neighbor_ratios"]),
        )
        for family, ratios in families:
            for resolution in values["resolutions"]:
                n = int(resolution)
                specs.append(
                    RunSpec(
                        protocol="support_family_comparison",
                        resolution=n,
                        support_family=family,
                        support_ratio=float(
                            ratios.get(n, ratios.get(str(n)))
                        ),
                        dt=float(values["time_step"]),
                        t_final=float(values["final_time"]),
                        sound_speed=c_s,
                    )
                )
    elif phase == "disorder":
        values = configuration["disorder_robustness"]
        for layout, seeds in values["layouts"].items():
            jitter = {
                "regular": 0.0,
                "jitter_05": 0.05,
                "jitter_10": 0.10,
            }[layout]
            for seed in seeds:
                specs.append(
                    RunSpec(
                        protocol="disorder_robustness",
                        resolution=int(values["resolution"]),
                        support_family="increasing_neighbor",
                        support_ratio=float(values["support_ratio"]),
                        dt=float(values["time_step"]),
                        t_final=float(values["final_time"]),
                        sound_speed=c_s,
                        layout=layout,
                        jitter_fraction=jitter,
                        seed=int(seed),
                    )
                )
    elif phase == "mach":
        values = configuration["mach_sensitivity"]
        for sound_speed in values["sound_speeds"]:
            specs.append(
                RunSpec(
                    protocol="mach_sensitivity",
                    resolution=int(values["resolution"]),
                    support_family="increasing_neighbor",
                    support_ratio=float(values["support_ratio"]),
                    dt=float(values["time_step"]),
                    t_final=float(values["final_time"]),
                    sound_speed=float(sound_speed),
                )
            )
    else:
        raise ValueError(f"unknown phase: {phase}")
    return specs


def _already_complete(spec: RunSpec, configuration: dict[str, Any]) -> bool:
    rows = _read_summary_rows()
    match = next(
        (row for row in rows if row.get("run_id") == spec.run_id),
        None,
    )
    if match is None or match.get("status") not in {"PASS", "ACCEPTED"}:
        return False
    current_git = _git_hash()
    if match.get("git_hash") != current_git:
        return False
    payload = _spec_payload(
        spec,
        master_hash=_sha256_bytes(CONFIG_PATH.read_bytes()),
        git_hash=current_git,
    )
    expected = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
    if match.get("config_hash") != expected:
        return False

    resolved: dict[str, Path] = {}
    for key in (
        "sample_table_path",
        "state_path",
        "config_path",
        "stdout_log_path",
        "stderr_log_path",
    ):
        raw = match.get(key, "")
        path = Path(raw)
        if not raw or path.is_absolute():
            return False
        candidate = (PROJECT_ROOT / path).resolve()
        try:
            candidate.relative_to(PROJECT_ROOT)
        except ValueError:
            return False
        if not candidate.is_file():
            return False
        resolved[key] = candidate

    try:
        stored = json.loads(
            resolved["config_path"].read_text(encoding="utf-8")
        )
        stored_hash = stored.pop("resolved_config_sha256")
        if stored != payload or stored_hash != expected:
            return False
        with resolved["sample_table_path"].open(
            newline="",
            encoding="utf-8",
        ) as stream:
            samples = list(csv.DictReader(stream))
        expected_steps = list(_sample_steps(spec))
        if len(samples) != len(expected_steps):
            return False
        if [int(row["step"]) for row in samples] != expected_steps:
            return False
        if any(
            row.get("run_id") != spec.run_id
            or row.get("config_hash") != expected
            or row.get("git_hash") != current_git
            for row in samples
        ):
            return False
        with np.load(resolved["state_path"], allow_pickle=False) as archive:
            archived_steps = archive["steps"].astype(np.int64).tolist()
        if archived_steps != expected_steps:
            return False
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False
    return True


def _failed_attempt_matches_current(spec: RunSpec) -> bool:
    rows = [
        row
        for row in _read_summary_rows()
        if row.get("run_id") == spec.run_id and row.get("status") == "FAIL"
    ]
    if len(rows) != 1:
        return False
    row = rows[0]
    current_git = _git_hash()
    payload = _spec_payload(
        spec,
        master_hash=_sha256_bytes(CONFIG_PATH.read_bytes()),
        git_hash=current_git,
    )
    expected = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
    if (
        row.get("git_hash") != current_git
        or row.get("config_hash") != expected
        or not row.get("failure_class")
    ):
        return False
    paths = _resolved_paths(spec.run_id)
    required = (
        paths["sample"],
        paths["config"],
        paths["stdout"],
        paths["stderr"],
        paths["failure"],
    )
    if not all(path.is_file() for path in required):
        return False
    try:
        stored = json.loads(paths["config"].read_text(encoding="utf-8"))
        stored_hash = stored.pop("resolved_config_sha256")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False
    return stored == payload and stored_hash == expected


def _require_attempted_specs(
    phase: str,
    configuration: dict[str, Any],
) -> list[dict[str, str]]:
    specs = _specs_for_phase(phase, configuration)
    incomplete = [
        spec.run_id
        for spec in specs
        if not (
            _already_complete(spec, configuration)
            or _failed_attempt_matches_current(spec)
        )
    ]
    if incomplete:
        raise RuntimeError(
            f"all current-config/current-commit {phase} attempts required: "
            + ", ".join(incomplete)
        )
    rows = _read_summary_rows()
    return [
        next(row for row in rows if row.get("run_id") == spec.run_id)
        for spec in specs
    ]


def _integrator_gate_passes(configuration: dict[str, Any]) -> bool:
    path = (
        PROJECT_ROOT
        / "06_experiments"
        / "stage_01d_integrator_verification"
        / "results"
        / "integrator_verification.csv"
    )
    if not path.is_file():
        return False
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 8:
        return False
    integrator = configuration["integrator"]
    expected_dts = sorted(
        (float(value) for value in integrator["time_steps"]),
        reverse=True,
    )
    expected_git = _git_hash()
    expected_config = _sha256_bytes(CONFIG_PATH.read_bytes())
    fitted_minimum = float(
        integrator["qualification"]["fitted_order_minimum"]
    )
    finest_minimum = float(
        integrator["qualification"][
            "finest_pair_observed_order_minimum"
        ]
    )
    if any(
        row.get("git_hash") != expected_git
        or row.get("config_sha256") != expected_config
        or row.get("method") != "explicit_midpoint_rk2"
        for row in rows
    ):
        return False
    observed_problems = {row.get("problem") for row in rows}
    if observed_problems != {
        "scalar_decay",
        "coupled_damped_oscillator",
    }:
        return False
    for problem in ("scalar_decay", "coupled_damped_oscillator"):
        selected = [
            row for row in rows if row.get("problem") == problem
        ]
        if len(selected) != 4:
            return False
        selected.sort(key=lambda row: float(row["dt"]), reverse=True)
        observed_dts = [float(row["dt"]) for row in selected]
        if observed_dts != expected_dts:
            return False
        if any(
            int(row["steps"]) != int(round(1.0 / dt))
            for row, dt in zip(selected, observed_dts)
        ):
            return False
        expected_exact = (
            (math.exp(-1.3),)
            if problem == "scalar_decay"
            else (
                math.exp(-0.2)
                * (math.cos(1.4) + math.sin(1.4) / 7.0),
                -(10.0 / 7.0) * math.exp(-0.2) * math.sin(1.4),
            )
        )
        recomputed_errors: list[float] = []
        for row in selected:
            numerical = [float(row["numerical_0"])]
            exact = [float(row["exact_0"])]
            if problem == "coupled_damped_oscillator":
                numerical.append(float(row["numerical_1"]))
                exact.append(float(row["exact_1"]))
            if not all(
                math.isclose(
                    value,
                    expected,
                    rel_tol=2.0e-14,
                    abs_tol=2.0e-14,
                )
                for value, expected in zip(exact, expected_exact)
            ):
                return False
            recomputed_errors.append(
                math.sqrt(
                    sum(
                        (value - reference) ** 2
                        for value, reference in zip(numerical, exact)
                    )
                )
            )
        errors = [float(row["error_L2"]) for row in selected]
        if not all(
            math.isclose(
                recorded,
                recomputed,
                rel_tol=2.0e-13,
                abs_tol=2.0e-15,
            )
            for recorded, recomputed in zip(errors, recomputed_errors)
        ):
            return False
        if not all(
            math.isfinite(value) and value > 0.0 for value in errors
        ):
            return False
        if not all(
            fine < coarse
            for coarse, fine in zip(errors, errors[1:])
        ):
            return False
        fitted_order = float(
            np.polyfit(
                np.log(np.asarray(observed_dts, dtype=np.float64)),
                np.log(np.asarray(errors, dtype=np.float64)),
                1,
            )[0]
        )
        finest_order = math.log(errors[-2] / errors[-1], 2.0)
        if not math.isfinite(fitted_order) or fitted_order < fitted_minimum:
            return False
        if not math.isfinite(finest_order) or finest_order < finest_minimum:
            return False
    return True


def _require_completed_specs(
    phase: str,
    configuration: dict[str, Any],
    *,
    selected: Iterable[RunSpec] | None = None,
) -> None:
    specs = (
        list(selected)
        if selected is not None
        else _specs_for_phase(phase, configuration)
    )
    incomplete = [
        spec.run_id
        for spec in specs
        if not _already_complete(spec, configuration)
    ]
    if incomplete:
        raise RuntimeError(
            f"current-config/current-commit {phase} evidence required: "
            + ", ".join(incomplete)
        )


def _require_phase_gate(
    phase: str,
    configuration: dict[str, Any],
    *,
    require_scientific_pass: bool,
    allow_space_plateau: bool = False,
) -> None:
    path = RESULTS_ROOT / f"{phase}_phase_gate.json"
    if not path.is_file():
        raise RuntimeError(f"missing immutable {phase} phase gate evidence")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected_specs = _specs_for_phase(phase, configuration)
    expected_ids = [spec.run_id for spec in expected_specs]
    provenance_pass = bool(
        value.get("stage") == "01D"
        and value.get("phase") == phase
        and value.get("git_hash") == _git_hash()
        and value.get("master_preregistration_sha256")
        == _sha256_bytes(CONFIG_PATH.read_bytes())
        and value.get("run_ids") == expected_ids
        and all(_already_complete(spec, configuration) for spec in expected_specs)
    )
    scientific_pass = (
        bool(
            value.get("phase_gate_pass")
            or (
                phase == "space"
                and allow_space_plateau
                and value.get("space_plateau_conditional")
                and value.get("downstream_allowed")
            )
        )
        if require_scientific_pass
        else True
    )
    if not provenance_pass or not scientific_pass:
        raise RuntimeError(
            f"{phase} phase-level convergence gate does not authorize "
            "this downstream phase"
        )


def _require_phase_prerequisites(
    phase: str,
    configuration: dict[str, Any],
) -> None:
    if not _integrator_gate_passes(configuration):
        raise RuntimeError(
            "independent scalar/coupled integrator gate must pass first"
        )
    if phase == "zero":
        return
    _require_completed_specs("zero", configuration)
    if phase == "smoke":
        return
    _require_completed_specs("smoke", configuration)
    if phase == "time":
        return
    _require_completed_specs("time", configuration)
    _require_phase_gate(
        "time",
        configuration,
        require_scientific_pass=phase not in {"space", "support"},
    )
    if phase == "space":
        return
    _require_completed_specs("space", configuration)
    _require_phase_gate(
        "space",
        configuration,
        require_scientific_pass=phase != "support",
        allow_space_plateau=phase != "support",
    )
    if phase == "support":
        return
    _require_completed_specs("support", configuration)
    if phase == "disorder":
        return
    regular_disorder = [
        spec
        for spec in _specs_for_phase("disorder", configuration)
        if spec.layout == "regular"
    ]
    _require_completed_specs(
        "regular disorder control",
        configuration,
        selected=regular_disorder,
    )
    if phase == "mach":
        summary_rows = _read_summary_rows()
        for spec in _specs_for_phase("disorder", configuration):
            failed = next(
                (
                    row
                    for row in summary_rows
                    if row.get("run_id") == spec.run_id
                    and row.get("status") == "FAIL"
                ),
                None,
            )
            if (
                failed is not None
                and _failed_attempt_matches_current(spec)
                and failed.get("failure_class")
                not in CONTINUABLE_SCIENTIFIC_FAILURE_CLASSES
            ):
                raise RuntimeError(
                    "non-scientific disorder campaign failure blocks Mach: "
                    f"{spec.run_id}"
                )
        return
    if phase == "n48":
        mach_rows = _require_attempted_specs("mach", configuration)
        if any(
            row.get("failure_class")
            and row.get("failure_class")
            not in CONTINUABLE_SCIENTIFIC_FAILURE_CLASSES
            for row in mach_rows
        ):
            raise RuntimeError(
                "non-scientific Mach campaign failure does not permit N48"
            )
        n32_spec = next(
            spec
            for spec in _specs_for_phase("space", configuration)
            if spec.resolution == 32
        )
        n32 = next(
            row
            for row in _read_summary_rows()
            if row.get("run_id") == n32_spec.run_id
        )
        policy = configuration["space_convergence"]["n48_policy"]
        if int(float(n32["peak_rss_bytes"])) >= int(
            policy["run_only_if_n32_peak_rss_below_bytes"]
        ):
            raise RuntimeError("N32 peak RSS does not permit N48")
        n48_spec = _specs_for_phase("n48", configuration)[0]
        n32_state = initialize_taylor_green_state(
            n32_spec.resolution,
            support_ratio=n32_spec.support_ratio,
            reference_density=1.0,
            velocity_amplitude=1.0,
            physical_viscosity=0.02,
            sound_speed=n32_spec.sound_speed,
        )
        n32_neighborhood = build_periodic_neighborhood(
            n32_state.positions,
            n32_state.supports,
        )
        n48_state = initialize_taylor_green_state(
            n48_spec.resolution,
            support_ratio=n48_spec.support_ratio,
            reference_density=1.0,
            velocity_amplitude=1.0,
            physical_viscosity=0.02,
            sound_speed=n48_spec.sound_speed,
        )
        n48_neighborhood = build_periodic_neighborhood(
            n48_state.positions,
            n48_state.supports,
        )
        n32_edges = int(n32_neighborhood.row.numel())
        n48_edges = int(n48_neighborhood.row.numel())
        edge_scale = n48_edges / n32_edges
        particle_scale = n48_spec.resolution**2 / n32_spec.resolution**2
        projection_safety_factor = float(
            policy["projection_safety_factor"]
        )
        cost_scale = (
            max(edge_scale, particle_scale) * projection_safety_factor
        )
        projected = float(n32["wall_clock_seconds"]) * cost_scale
        wall_limit = float(
            policy["run_only_if_projected_wall_seconds_below"]
        )
        eligibility = {
            "stage": "01D",
            "git_hash": _git_hash(),
            "master_preregistration_sha256": _sha256_bytes(
                CONFIG_PATH.read_bytes()
            ),
            "n32_run_id": n32_spec.run_id,
            "n32_peak_rss_bytes": int(float(n32["peak_rss_bytes"])),
            "n32_wall_clock_seconds": float(n32["wall_clock_seconds"]),
            "n32_mean_step_seconds": float(n32["mean_step_seconds"]),
            "n32_particle_count": n32_spec.resolution**2,
            "n32_initial_edge_count": n32_edges,
            "n48_particle_count": n48_spec.resolution**2,
            "n48_initial_edge_count": n48_edges,
            "edge_count_scale": edge_scale,
            "particle_count_scale": particle_scale,
            "projection_safety_factor": projection_safety_factor,
            "conservative_cost_scale": cost_scale,
            "projected_n48_wall_seconds": projected,
            "wall_seconds_limit": wall_limit,
            "peak_rss_qualification_pass": True,
            "projected_wall_qualification_pass": projected < wall_limit,
            "eligible": projected < wall_limit,
        }
        _write_json_once_or_verify(
            RESULTS_ROOT / "n48_eligibility.json",
            eligibility,
        )
        if projected >= wall_limit:
            raise RuntimeError("N32 timing projection does not permit N48")
        return
    raise RuntimeError(f"unhandled prerequisite phase: {phase}")


def _failure_class_for_run(run_id: str) -> str | None:
    matches = [
        row
        for row in _read_summary_rows()
        if row.get("run_id") == run_id and row.get("status") == "FAIL"
    ]
    return matches[0].get("failure_class") if len(matches) == 1 else None


def _run_phase_in_isolated_processes(
    *,
    phase: str,
    specs: list[RunSpec],
    configuration: dict[str, Any],
    resume: bool,
) -> int:
    """Give every trajectory an independent process-lifetime RSS counter."""

    all_success = True
    for spec in specs:
        if resume and _already_complete(spec, configuration):
            print(f"{spec.run_id}: SKIP matching completed evidence")
            continue
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--phase",
            phase,
            "--run-id",
            spec.run_id,
        ]
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
        )
        if completed.returncode == 0:
            continue
        all_success = False
        failure_class = _failure_class_for_run(spec.run_id)
        if (
            failure_class is None
            or phase not in {"disorder", "mach"}
            or failure_class in RESOURCE_FAILURE_CLASSES
            or failure_class
            not in CONTINUABLE_SCIENTIFIC_FAILURE_CLASSES
        ):
            return 1
    return 0 if all_success else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=(
            "zero",
            "smoke",
            "time",
            "space",
            "support",
            "disorder",
            "mach",
            "n48",
        ),
        required=True,
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    configuration = _load_configuration()
    _require_phase_prerequisites(args.phase, configuration)
    specs = _specs_for_phase(args.phase, configuration)
    if args.run_id is not None:
        specs = [spec for spec in specs if spec.run_id == args.run_id]
        if not specs:
            raise SystemExit(f"unknown run-id for phase: {args.run_id}")
    elif len(specs) > 1:
        return _run_phase_in_isolated_processes(
            phase=args.phase,
            specs=specs,
            configuration=configuration,
            resume=args.resume,
        )
    all_success = True
    for spec in specs:
        if args.resume and _already_complete(spec, configuration):
            print(f"{spec.run_id}: SKIP matching completed evidence")
            continue
        if not run_one(spec, configuration=configuration):
            all_success = False
            if args.phase != "disorder":
                return 1
    return 0 if all_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
