"""Instrumented, fixed-physics Stage 01D-R rollout implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
import gc
import hashlib
import math
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Mapping

import numpy as np
import torch

from dynamic_solver.acceleration import (
    DynamicPhysicalParameters,
    ForceEvaluation,
    force_structure_audit,
)
from dynamic_solver.diagnostics import (
    collect_dynamic_diagnostics,
    kinetic_energy,
    process_peak_rss_bytes,
    tgv_exact_kinetic_energy,
    tgv_exact_modal_amplitude,
    tgv_modal_basis,
)
from dynamic_solver.periodic_rollout import (
    explicit_midpoint_dynamic_step,
    prepare_dynamic_state,
)
from dynamic_solver.state import DynamicSPHState
from dynamic_solver.taylor_green import (
    initialize_taylor_green_state,
    taylor_green_velocity,
)
from resource_diagnostics.object_retention import RetentionTracker
from resource_diagnostics.rss_sampler import MemorySampler
from resource_diagnostics.tensor_inventory import collect_tensor_inventory
from structure_preserving.kernels import (
    divergence_from_vector_gradient,
    quadratic_weighted_least_squares,
)
from structure_preserving.neighborhood import minimum_image


PROBE_SCHEMA_VERSION = "sph-pio-poc.stage01dr.rollout-probe.v1"


@dataclass
class ProbeArtifacts:
    """Small scalar evidence buffers populated even if a probe fails."""

    diagnostic_records: list[dict[str, Any]] = field(default_factory=list)
    numerical_records: list[dict[str, Any]] = field(default_factory=list)
    comparison_records: list[dict[str, Any]] = field(default_factory=list)
    retention_records: list[dict[str, Any]] = field(default_factory=list)
    archive_metadata: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    diagnostic_sink: Callable[[Mapping[str, Any]], None] | None = None
    numerical_sink: Callable[[Mapping[str, Any]], None] | None = None
    retention_sink: Callable[[Mapping[str, Any]], None] | None = None

    def add_diagnostic(self, record: dict[str, Any]) -> None:
        if self.diagnostic_sink is not None:
            self.diagnostic_sink(record)
        self.diagnostic_records.append(record)

    def add_numerical(self, record: dict[str, Any]) -> None:
        if self.numerical_sink is not None:
            self.numerical_sink(record)
        self.numerical_records.append(record)

    def add_retention(self, record: dict[str, Any]) -> None:
        if self.retention_sink is not None:
            self.retention_sink(record)
        self.retention_records.append(record)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _nonself_minimum_separation(evaluation: ForceEvaluation) -> float:
    neighborhood = evaluation.neighborhood
    mask = neighborhood.row != neighborhood.col
    if not bool(mask.any()):
        return math.inf
    return float(neighborhood.distance[mask].detach().min())


def _memory_steps(configuration: Mapping[str, Any]) -> set[int]:
    sampling = configuration["sampling"]
    interval = int(sampling["solver_step_interval"])
    steps = int(configuration["warmup"]["post_warmup_last_step"])
    selected = set(range(0, steps + 1, interval))
    selected.update(int(value) for value in sampling["mandatory_solver_steps"])
    return selected


def _inventory_requested(
    configuration: Mapping[str, Any],
    *,
    phase: str,
    step: int | None,
) -> bool:
    sampling = configuration["sampling"]
    return bool(
        phase in set(sampling["tensor_inventory_phases"])
        or (
            step is not None
            and int(step)
            in {int(value) for value in sampling["tensor_inventory_steps"]}
        )
    )


def sample_memory_checkpoint(
    sampler: MemorySampler,
    *,
    configuration: Mapping[str, Any],
    phase: str,
    step: int | None,
    edge_count: int | None,
    step_wall_seconds: float | None,
    tracker: RetentionTracker | None,
    force_inventory: bool = False,
    current_rss_limit_bytes: int | None = None,
    note: str = "",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Measure gate RSS before any sparse tensor/GC inventory."""

    include_pressure = bool(
        step is None
        or step in {0, 25, 26, 500}
        or (step is not None and step % 25 == 0)
    )
    pre = sampler.sample(
        phase=phase,
        step=step,
        edge_count=edge_count,
        step_wall_seconds=step_wall_seconds,
        include_system_pressure=include_pressure,
        note=(note + ";pre_tensor_inventory").strip(";"),
    )
    qualification = configuration["qualification"]
    rss_limit = int(
        qualification["current_rss_stop_bytes"]
        if current_rss_limit_bytes is None
        else current_rss_limit_bytes
    )
    if int(pre["current_rss_bytes"]) > rss_limit:
        raise MemoryError("Stage 01D-R current RSS safety stop")
    pressure = pre.get("system_memory_free_percent")
    if pressure is not None:
        if float(pressure) < float(
            qualification["system_memory_free_percentage_below"]
        ):
            sampler.low_system_memory_sample_streak += 1
        else:
            sampler.low_system_memory_sample_streak = 0
        if sampler.low_system_memory_sample_streak >= int(
            qualification["system_memory_pressure_consecutive_samples"]
        ):
            raise MemoryError("Stage 01D-R system memory pressure safety stop")
    requested = force_inventory or _inventory_requested(
        configuration,
        phase=phase,
        step=step,
    )
    if not requested:
        return pre, None
    started = time.perf_counter()
    inventory = collect_tensor_inventory()
    retention = None if tracker is None else tracker.snapshot(collect=False)
    post = sampler.sample(
        phase=phase,
        step=step,
        edge_count=edge_count,
        step_wall_seconds=step_wall_seconds,
        tensor_inventory=inventory,
        retention=retention,
        include_system_pressure=False,
        note=(
            note
            + f";post_tensor_inventory;inventory_seconds="
            f"{time.perf_counter() - started:.9f}"
        ).strip(";"),
    )
    return pre, post


def _initialize_state(
    configuration: Mapping[str, Any],
    *,
    resolution: int,
) -> tuple[DynamicSPHState, DynamicPhysicalParameters, float, float]:
    physics = configuration["physics"]
    resolution_config = configuration["resolutions"][resolution]
    state = initialize_taylor_green_state(
        resolution,
        support_ratio=float(resolution_config["support_ratio"]),
        reference_density=float(physics["reference_density"]),
        velocity_amplitude=float(physics["velocity_amplitude"]),
        physical_viscosity=float(physics["physical_viscosity"]),
        sound_speed=float(physics["sound_speed"]),
        jitter_fraction=0.0,
        seed=int(physics["seed"]),
        domain_minimum=tuple(float(v) for v in physics["domain_minimum"]),
        domain_maximum=tuple(float(v) for v in physics["domain_maximum"]),
    )
    parameters = DynamicPhysicalParameters(
        reference_density=float(physics["reference_density"]),
        sound_speed=float(physics["sound_speed"]),
        physical_viscosity=float(physics["physical_viscosity"]),
    )
    extent = float(state.domain_extent[0].detach())
    dx = extent / resolution
    return state, parameters, dx, float(resolution_config["time_step"])


def _archive_snapshot(
    state: DynamicSPHState,
    evaluation: ForceEvaluation,
) -> dict[str, np.ndarray | float]:
    return {
        "time": float(state.time),
        "positions": state.positions.detach().cpu().contiguous().numpy().copy(),
        "velocities": state.velocities.detach().cpu().contiguous().numpy().copy(),
        "densities": evaluation.densities.detach().cpu().contiguous().numpy().copy(),
        "pressures": evaluation.pressures.detach().cpu().contiguous().numpy().copy(),
    }


def _write_archive_once(
    path: Path,
    *,
    steps: list[int],
    snapshots: list[dict[str, np.ndarray | float]],
) -> dict[str, Any]:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite archive: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    if temporary.exists():
        raise RuntimeError(f"stale temporary archive exists: {temporary.name}")
    arrays = {
        "steps": np.asarray(steps, dtype=np.int64),
        "times": np.asarray(
            [float(snapshot["time"]) for snapshot in snapshots],
            dtype=np.float64,
        ),
        "positions": np.stack([snapshot["positions"] for snapshot in snapshots]),
        "velocities": np.stack([snapshot["velocities"] for snapshot in snapshots]),
        "densities": np.stack([snapshot["densities"] for snapshot in snapshots]),
        "pressures": np.stack([snapshot["pressures"] for snapshot in snapshots]),
    }
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)
    project_root = Path(__file__).resolve().parents[2]
    resolved_path = path.resolve()
    recorded_path = (
        resolved_path.relative_to(project_root).as_posix()
        if resolved_path.is_relative_to(project_root)
        else f"<EXTERNAL_TEST_PATH>/{path.name}"
    )
    return {
        "archive_path": recorded_path,
        "archive_sha256": _sha256(path),
        "archive_bytes": path.stat().st_size,
        "archive_write_count": 1,
        "archive_checkpoint_count": len(steps),
        "archive_uncompressed_array_bytes": int(
            sum(array.nbytes for array in arrays.values())
        ),
        "archive_steps": list(steps),
    }


def _minimal_numerical_record(
    *,
    run_id: str,
    step: int,
    state: DynamicSPHState,
    evaluation: ForceEvaluation,
    parameters: DynamicPhysicalParameters,
    reference_momentum: torch.Tensor,
    dx: float,
) -> dict[str, Any]:
    structure = force_structure_audit(state, evaluation, parameters)
    finite = all(
        bool(torch.isfinite(value.detach()).all())
        for value in (
            state.positions,
            state.velocities,
            evaluation.densities,
            evaluation.pressures,
            evaluation.acceleration,
        )
    )
    momentum = torch.sum(state.masses[:, None] * state.velocities, dim=0)
    drift = torch.linalg.vector_norm(momentum - reference_momentum)
    total_mass = state.masses.sum()
    minimum_separation = _nonself_minimum_separation(evaluation)
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "run_id": run_id,
        "step": int(step),
        "time": float(state.time),
        "state_all_finite": bool(finite),
        "pressure_relative_pair_force_residual": float(
            structure["pressure_relative_pair_force_residual"]
        ),
        "viscosity_relative_pair_force_residual": float(
            structure["viscosity_relative_pair_force_residual"]
        ),
        "relative_total_internal_force": float(
            structure["characteristic_normalized_total_internal_force"]
        ),
        "viscous_power": float(structure["viscous_power"]),
        "momentum_drift_normalized": float(drift / total_mass),
        "minimum_separation": minimum_separation,
        "minimum_separation_over_dx": minimum_separation / dx,
        "neighbor_duplicate_edge_count": int(
            structure["neighbor_duplicate_edge_count"]
        ),
        "neighbor_missing_self_edge_count": int(
            structure["neighbor_missing_self_edge_count"]
        ),
        "neighbor_nonreciprocal_nonself_edge_count": int(
            structure["neighbor_nonreciprocal_nonself_edge_count"]
        ),
        "neighbor_out_of_bounds_edge_count": int(
            structure["neighbor_out_of_bounds_edge_count"]
        ),
        "neighbor_omitted_strict_support_edge_count": int(
            structure["neighbor_omitted_strict_support_edge_count"]
        ),
        "neighbor_unexpected_edge_count": int(
            structure["neighbor_unexpected_edge_count"]
        ),
        "edge_count": int(evaluation.neighborhood.row.numel()),
    }


def _full_diagnostic_record(
    *,
    run_id: str,
    config_hash: str,
    git_hash: str,
    sample_index: int,
    step: int,
    state: DynamicSPHState,
    evaluation: ForceEvaluation,
    parameters: DynamicPhysicalParameters,
    reference_momentum: torch.Tensor,
    reference_angular_momentum: torch.Tensor,
    initial_energy: float,
    unwrapped_positions: torch.Tensor,
    dt: float,
    step_times: list[float],
    started_at: float,
) -> dict[str, Any]:
    exact_velocity = taylor_green_velocity(
        state.positions,
        state.time,
        velocity_amplitude=1.0,
        physical_viscosity=float(parameters.physical_viscosity),
    )
    exact_amplitude = tgv_exact_modal_amplitude(
        state.time,
        initial_velocity=1.0,
        kinematic_viscosity=float(parameters.physical_viscosity),
    )
    exact_energy = tgv_exact_kinetic_energy(
        state.time,
        initial_kinetic_energy=initial_energy,
        kinematic_viscosity=float(parameters.physical_viscosity),
    )
    divergence_l2 = _divergence_l2(
        state.velocities,
        state.masses,
        evaluation.densities,
        evaluation.neighborhood,
    )
    return collect_dynamic_diagnostics(
        positions=state.positions,
        velocity=state.velocities,
        mass=state.masses,
        density=evaluation.densities,
        pressure=evaluation.pressures,
        sound_speed=float(parameters.sound_speed),
        neighborhood=evaluation.neighborhood,
        physical_viscosity=float(parameters.physical_viscosity),
        assembled_acceleration=evaluation.acceleration,
        time=state.time,
        exact_velocity=exact_velocity,
        modal_basis=tgv_modal_basis(state.positions),
        exact_modal_amplitude=exact_amplitude,
        exact_kinetic_energy=exact_energy,
        reference_density=float(parameters.reference_density),
        reference_momentum=reference_momentum,
        reference_angular_momentum=reference_angular_momentum,
        characteristic_velocity=1.0,
        characteristic_length=2.0,
        angular_momentum_positions=unwrapped_positions,
        velocity_divergence_l2=divergence_l2,
        run_id=run_id,
        config_hash=config_hash,
        git_hash=git_hash,
        sample_index=sample_index,
        step=step,
        dt=dt,
        wall_clock_seconds=time.perf_counter() - started_at,
        step_times_seconds=step_times,
        peak_rss_bytes=process_peak_rss_bytes(),
        viscous_power_positive_absolute_tolerance=1.0e-12,
    )


def _compact_full_record(record: Mapping[str, Any], *, dx: float) -> dict[str, Any]:
    minimum = float(record["minimum_separation"])
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "run_id": record["run_id"],
        "step": int(record["step"]),
        "time": float(record["time"]),
        "state_all_finite": bool(record["state_all_finite"]),
        "pressure_relative_pair_force_residual": float(
            record["pressure_relative_pair_force_residual"]
        ),
        "viscosity_relative_pair_force_residual": float(
            record["viscosity_relative_pair_force_residual"]
        ),
        "relative_total_internal_force": float(
            record["assembled_relative_internal_force"]
        ),
        "viscous_power": float(record["accumulated_viscous_power"]),
        "momentum_drift_normalized": float(
            record["momentum_drift_normalized"]
        ),
        "minimum_separation": minimum,
        "minimum_separation_over_dx": minimum / dx,
        "neighbor_duplicate_edge_count": int(
            record["neighbor_duplicate_edge_count"]
        ),
        "neighbor_missing_self_edge_count": int(
            record["neighbor_missing_self_edge_count"]
        ),
        "neighbor_nonreciprocal_nonself_edge_count": int(
            record["neighbor_nonreciprocal_nonself_edge_count"]
        ),
        "neighbor_out_of_bounds_edge_count": int(
            record["neighbor_out_of_bounds_edge_count"]
        ),
        "neighbor_omitted_strict_support_edge_count": int(
            record["neighbor_omitted_strict_support_edge_count"]
        ),
        "neighbor_unexpected_edge_count": int(
            record["neighbor_unexpected_edge_count"]
        ),
        "edge_count": int(record["neighbor_edge_count"]),
    }


def _validate_numerical_record(
    record: Mapping[str, Any],
    qualification: Mapping[str, Any],
) -> None:
    if not bool(record["state_all_finite"]):
        raise FloatingPointError("nonfinite state in Stage 01D-R probe")
    topology_keys = (
        "neighbor_duplicate_edge_count",
        "neighbor_missing_self_edge_count",
        "neighbor_nonreciprocal_nonself_edge_count",
        "neighbor_out_of_bounds_edge_count",
        "neighbor_omitted_strict_support_edge_count",
        "neighbor_unexpected_edge_count",
    )
    if any(int(record[key]) != 0 for key in topology_keys):
        raise RuntimeError("neighbor topology defect in Stage 01D-R probe")
    pair_limit = float(qualification["maximum_relative_pair_force_residual"])
    if max(
        float(record["pressure_relative_pair_force_residual"]),
        float(record["viscosity_relative_pair_force_residual"]),
    ) > pair_limit:
        raise RuntimeError("pair-force residual exceeds Stage 01D-R limit")
    if float(record["relative_total_internal_force"]) > float(
        qualification["maximum_characteristic_normalized_internal_force"]
    ):
        raise RuntimeError("internal-force residual exceeds Stage 01D-R limit")
    if float(record["viscous_power"]) > float(
        qualification["viscous_power_positive_absolute_tolerance"]
    ):
        raise RuntimeError("positive viscous power in Stage 01D-R probe")
    if float(record["minimum_separation_over_dx"]) < float(
        qualification["minimum_separation_over_dx"]
    ):
        raise RuntimeError("particle-separation gate failed")


def _record_retention(
    artifacts: ProbeArtifacts,
    tracker: RetentionTracker,
    *,
    step: int,
    phase: str = "solver_step",
) -> None:
    snapshot = tracker.snapshot(collect=True)
    artifacts.add_retention(
        {"step": int(step), "phase": str(phase), **snapshot}
    )


def run_qualifying_probe(
    *,
    configuration: Mapping[str, Any],
    run_id: str,
    variant: str,
    resolution: int,
    config_hash: str,
    git_hash: str,
    sampler: MemorySampler,
    artifacts: ProbeArtifacts,
    archive_path: Path | None,
) -> dict[str, Any]:
    """Run one A/B/C rollout with an outer forward-only no-grad guard."""

    if variant not in {"A", "B", "C"}:
        raise ValueError("qualifying variant must be A, B, or C")
    variant_config = configuration["variants"][variant]
    if not bool(variant_config["torch_no_grad"]):
        raise ValueError("qualifying variants must be preregistered no-grad")
    if variant == "C" and archive_path is None:
        raise ValueError("Variant C requires an archive path")
    if variant != "C" and archive_path is not None:
        raise ValueError("only Variant C may receive an archive path")

    with torch.no_grad():
        return _run_qualifying_probe_no_grad(
            configuration=configuration,
            run_id=run_id,
            variant=variant,
            resolution=resolution,
            config_hash=config_hash,
            git_hash=git_hash,
            sampler=sampler,
            artifacts=artifacts,
            archive_path=archive_path,
        )


def _run_qualifying_probe_no_grad(
    *,
    configuration: Mapping[str, Any],
    run_id: str,
    variant: str,
    resolution: int,
    config_hash: str,
    git_hash: str,
    sampler: MemorySampler,
    artifacts: ProbeArtifacts,
    archive_path: Path | None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    tracker = RetentionTracker()
    steps = int(configuration["resolutions"][resolution]["steps"])
    artifacts.summary.update(
        {
            "schema_version": PROBE_SCHEMA_VERSION,
            "run_id": run_id,
            "variant": variant,
            "resolution": int(resolution),
            "particle_count": int(resolution**2),
            "completed_steps": 0,
            "planned_steps": steps,
            "solver_completed": False,
            "last_completed_phase": "imports_complete",
            "torch_no_grad": True,
            "config_hash": config_hash,
            "git_hash": git_hash,
        }
    )
    state, parameters, dx, dt = _initialize_state(
        configuration,
        resolution=resolution,
    )
    artifacts.summary["last_completed_phase"] = "initial_state_complete"
    sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="initial_state_complete",
        step=0,
        edge_count=None,
        step_wall_seconds=None,
        tracker=tracker,
    )
    state, evaluation = prepare_dynamic_state(state, parameters)
    edge_count = int(evaluation.neighborhood.row.numel())
    artifacts.summary["last_completed_phase"] = "first_neighborhood_complete"
    sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="first_neighborhood_complete",
        step=0,
        edge_count=edge_count,
        step_wall_seconds=None,
        tracker=tracker,
    )

    reference_momentum = torch.sum(
        state.masses[:, None] * state.velocities,
        dim=0,
    )
    unwrapped_positions = state.positions.detach().clone()
    reference_angular = _angular_momentum(
        unwrapped_positions,
        state.velocities,
        state.masses,
    )
    initial_energy = kinetic_energy(state.velocities, state.masses)
    memory_steps = _memory_steps(configuration)
    diagnostic_steps = {
        int(value)
        for value in configuration["sampling"]["stage01d_diagnostic_steps"]
    }
    safety_steps = {
        int(value)
        for value in configuration["sampling"]["minimal_safety_audit_steps"]
    }
    archive_steps_selected = {
        int(value)
        for value in configuration["sampling"]["archive_checkpoint_steps"]
    }
    archive_steps: list[int] = []
    archive_snapshots: list[dict[str, np.ndarray | float]] = []
    step_times: list[float] = []
    qualification = configuration["qualification"]
    full_diagnostics = bool(
        configuration["variants"][variant]["stage01d_scalar_diagnostics"]
    )

    def audit(step: int) -> None:
        if full_diagnostics and step in diagnostic_steps:
            record = _full_diagnostic_record(
                run_id=run_id,
                config_hash=config_hash,
                git_hash=git_hash,
                sample_index=len(artifacts.diagnostic_records),
                step=step,
                state=state,
                evaluation=evaluation,
                parameters=parameters,
                reference_momentum=reference_momentum,
                reference_angular_momentum=reference_angular,
                initial_energy=initial_energy,
                unwrapped_positions=unwrapped_positions,
                dt=dt,
                step_times=step_times,
                started_at=started_at,
            )
            artifacts.add_diagnostic(record)
            compact = _compact_full_record(record, dx=dx)
            artifacts.add_numerical(compact)
            _validate_numerical_record(compact, qualification)
        elif not full_diagnostics and step in safety_steps:
            compact = _minimal_numerical_record(
                run_id=run_id,
                step=step,
                state=state,
                evaluation=evaluation,
                parameters=parameters,
                reference_momentum=reference_momentum,
                dx=dx,
            )
            artifacts.add_numerical(compact)
            _validate_numerical_record(compact, qualification)

    if variant == "C" and 0 in archive_steps_selected:
        archive_steps.append(0)
        archive_snapshots.append(_archive_snapshot(state, evaluation))
    audit(0)
    if 0 in memory_steps:
        sample_memory_checkpoint(
            sampler,
            configuration=configuration,
            phase="solver_step",
            step=0,
            edge_count=edge_count,
            step_wall_seconds=None,
            tracker=tracker,
        )
        if 0 in set(configuration["sampling"]["tensor_inventory_steps"]):
            _record_retention(artifacts, tracker, step=0)

    for step in range(1, steps + 1):
        old_state = state
        old_evaluation = evaluation
        previous_position = state.positions
        started_step = time.perf_counter()
        result = explicit_midpoint_dynamic_step(
            state,
            dt=dt,
            parameters=parameters,
            start_evaluation=evaluation,
        )
        step_wall = time.perf_counter() - started_step
        step_times.append(step_wall)
        tracker.watch("old_state", old_state)
        tracker.watch("old_evaluation", old_evaluation)
        tracker.watch("old_neighborhood", old_evaluation.neighborhood)
        tracker.watch("step_result", result)
        tracker.watch("midpoint_evaluation", result.midpoint_evaluation)
        tracker.watch(
            "midpoint_neighborhood",
            result.midpoint_evaluation.neighborhood,
        )
        tracker.watch(
            "midpoint_pressure_force",
            result.midpoint_evaluation.pressure_force,
        )
        tracker.watch(
            "midpoint_viscosity_force",
            result.midpoint_evaluation.viscosity_force,
        )
        displacement = minimum_image(
            result.state.positions - previous_position,
            state.domain_extent,
        )
        unwrapped_positions = unwrapped_positions + displacement
        state = result.state.with_updates(time=step * dt)
        evaluation = result.end_evaluation
        edge_count = int(evaluation.neighborhood.row.numel())
        del result, old_state, old_evaluation, previous_position, displacement
        tracker.clear_dead()
        artifacts.summary["completed_steps"] = step
        artifacts.summary["solver_completed"] = step == steps
        artifacts.summary["last_completed_phase"] = "accepted_solver_step"

        if variant == "C" and step in archive_steps_selected:
            archive_steps.append(step)
            archive_snapshots.append(_archive_snapshot(state, evaluation))
        audit(step)
        if step in memory_steps:
            phase = "warmup_complete" if step == 25 else "solver_step"
            pre, _ = sample_memory_checkpoint(
                sampler,
                configuration=configuration,
                phase=phase,
                step=step,
                edge_count=edge_count,
                step_wall_seconds=step_wall,
                tracker=tracker,
            )
            if step in set(configuration["sampling"]["tensor_inventory_steps"]):
                _record_retention(artifacts, tracker, step=step)

    pre_archive, _ = sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="before_archive",
        step=steps,
        edge_count=edge_count,
        step_wall_seconds=step_times[-1] if step_times else None,
        tracker=tracker,
        force_inventory=True,
        note=f"checkpoint_buffer_count={len(archive_snapshots)}",
    )
    artifacts.summary.update(
        {
            "last_completed_phase": "before_archive",
            "before_archive_current_rss_bytes": int(
                pre_archive["current_rss_bytes"]
            ),
            "archive_write_count": 0,
            "archive_checkpoint_count": len(archive_steps),
            "archive_steps": list(archive_steps),
        }
    )
    if variant == "C":
        assert archive_path is not None
        artifacts.archive_metadata.update(
            _write_archive_once(
                archive_path,
                steps=archive_steps,
                snapshots=archive_snapshots,
            )
        )
    else:
        artifacts.archive_metadata.update(
            {
                "archive_path": "",
                "archive_sha256": "",
                "archive_bytes": 0,
                "archive_write_count": 0,
                "archive_checkpoint_count": 0,
                "archive_uncompressed_array_bytes": 0,
                "archive_steps": [],
            }
        )
    artifacts.summary["last_completed_phase"] = "archive_write_complete"
    post_archive, _ = sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="after_archive",
        step=steps,
        edge_count=edge_count,
        step_wall_seconds=None,
        tracker=tracker,
        force_inventory=True,
        note="archive_written" if variant == "C" else "archive_disabled",
    )
    artifacts.summary["last_completed_phase"] = "after_archive"
    artifacts.archive_metadata.update(
        {
            "before_archive_current_rss_bytes": int(
                pre_archive["current_rss_bytes"]
            ),
            "after_archive_current_rss_bytes": int(
                post_archive["current_rss_bytes"]
            ),
            "archive_current_rss_delta_bytes": int(
                post_archive["current_rss_bytes"]
                - pre_archive["current_rss_bytes"]
            ),
            "peak_rss_through_archive_bytes": int(
                post_archive["peak_rss_bytes"]
            ),
        }
    )

    final_edge_count = edge_count
    final_time = float(state.time)
    max_momentum_drift = max(
        (
            float(row["momentum_drift_normalized"])
            for row in artifacts.numerical_records
        ),
        default=math.nan,
    )
    max_pair_residual = max(
        (
            max(
                float(row["pressure_relative_pair_force_residual"]),
                float(row["viscosity_relative_pair_force_residual"]),
            )
            for row in artifacts.numerical_records
        ),
        default=math.nan,
    )
    max_internal = max(
        (
            float(row["relative_total_internal_force"])
            for row in artifacts.numerical_records
        ),
        default=math.nan,
    )
    maximum_viscous_power = max(
        (float(row["viscous_power"]) for row in artifacts.numerical_records),
        default=math.nan,
    )
    minimum_separation_ratio = min(
        (
            float(row["minimum_separation_over_dx"])
            for row in artifacts.numerical_records
        ),
        default=math.nan,
    )
    archive_snapshots.clear()
    archive_steps.clear()
    del state, evaluation, parameters, reference_momentum
    del reference_angular, unwrapped_positions
    gc.collect()
    retention_final = tracker.snapshot(collect=False)
    artifacts.add_retention(
        {"step": steps, "phase": "after_solver_release", **retention_final}
    )
    sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="before_process_exit",
        step=steps,
        edge_count=final_edge_count,
        step_wall_seconds=None,
        tracker=tracker,
        force_inventory=True,
        note="solver_state_released",
    )
    summary = {
        "schema_version": PROBE_SCHEMA_VERSION,
        "run_id": run_id,
        "variant": variant,
        "resolution": int(resolution),
        "particle_count": int(resolution**2),
        "completed_steps": steps,
        "planned_steps": steps,
        "final_time": final_time,
        "status": "PASS",
        "torch_no_grad": True,
        "final_edge_count": final_edge_count,
        "mean_step_wall_seconds": float(np.mean(step_times)),
        "maximum_step_wall_seconds": float(np.max(step_times)),
        "numerical_record_count": len(artifacts.numerical_records),
        "diagnostic_record_count": len(artifacts.diagnostic_records),
        "maximum_momentum_drift_normalized": max_momentum_drift,
        "maximum_pair_force_residual": max_pair_residual,
        "maximum_relative_total_internal_force": max_internal,
        "maximum_viscous_power": maximum_viscous_power,
        "minimum_separation_over_dx": minimum_separation_ratio,
        "retention_final_alive_total": int(
            retention_final.get("alive_total", 0)
        ),
        "config_hash": config_hash,
        "git_hash": git_hash,
        **artifacts.archive_metadata,
    }
    artifacts.summary.update(summary)
    return summary


def _grad_graph_node_count(tensor: torch.Tensor) -> int:
    root = tensor.grad_fn
    if root is None:
        return 0
    stack = [root]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        identity = id(node)
        if identity in seen:
            continue
        seen.add(identity)
        for child, _ in node.next_functions:
            if child is not None:
                stack.append(child)
    return len(seen)


def run_graph_sentinel(
    *,
    configuration: Mapping[str, Any],
    run_id: str,
    mode: str,
    config_hash: str,
    git_hash: str,
    sampler: MemorySampler,
    artifacts: ProbeArtifacts,
) -> dict[str, Any]:
    """Run the non-qualifying 20-step no-grad/grad-enabled sentinel."""

    if mode not in {"no_grad", "grad_enabled"}:
        raise ValueError("unknown graph sentinel mode")
    sentinel = configuration["variants"]["D"]
    resolution = int(sentinel["resolution"])
    sentinel_inventory_steps = {
        int(value)
        for value in configuration["sampling"]["sentinel_tensor_inventory_steps"]
    }
    sentinel_rss_limit = int(sentinel["current_rss_safety_stop_bytes"])
    artifacts.summary.update(
        {
            "schema_version": PROBE_SCHEMA_VERSION,
            "run_id": run_id,
            "variant": "D",
            "mode": mode,
            "resolution": resolution,
            "particle_count": resolution**2,
            "completed_steps": 0,
            "planned_steps": int(sentinel["steps"]),
            "solver_completed": False,
            "last_completed_phase": "imports_complete",
            "formal_resource_qualification": False,
            "config_hash": config_hash,
            "git_hash": git_hash,
        }
    )
    with torch.no_grad():
        state, parameters, _, _ = _initialize_state(
            configuration,
            resolution=resolution,
        )
        state = state.with_updates(
            positions=state.positions.detach().clone().requires_grad_(True),
            velocities=state.velocities.detach().clone().requires_grad_(True),
        )
    artifacts.summary["last_completed_phase"] = "initial_state_complete"
    sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="initial_state_complete",
        step=0,
        edge_count=None,
        step_wall_seconds=None,
        tracker=None,
        force_inventory=True,
        current_rss_limit_bytes=sentinel_rss_limit,
        note=f"sentinel_mode={mode}",
    )
    context = torch.no_grad() if mode == "no_grad" else torch.enable_grad()
    step_times: list[float] = []
    with context:
        state, evaluation = prepare_dynamic_state(state, parameters)
        artifacts.summary["last_completed_phase"] = "first_neighborhood_complete"
        sample_memory_checkpoint(
            sampler,
            configuration=configuration,
            phase="first_neighborhood_complete",
            step=0,
            edge_count=int(evaluation.neighborhood.row.numel()),
            step_wall_seconds=None,
            tracker=None,
            force_inventory=True,
            current_rss_limit_bytes=sentinel_rss_limit,
            note=f"sentinel_mode={mode}",
        )
        for step in range(1, int(sentinel["steps"]) + 1):
            started = time.perf_counter()
            result = explicit_midpoint_dynamic_step(
                state,
                dt=float(sentinel["time_step"]),
                parameters=parameters,
                start_evaluation=evaluation,
            )
            step_times.append(time.perf_counter() - started)
            state = result.state.with_updates(
                time=step * float(sentinel["time_step"])
            )
            evaluation = result.end_evaluation
            del result
            artifacts.summary["completed_steps"] = step
            artifacts.summary["solver_completed"] = step == int(sentinel["steps"])
            artifacts.summary["last_completed_phase"] = "accepted_solver_step"
            pre, _ = sample_memory_checkpoint(
                sampler,
                configuration=configuration,
                phase="solver_step",
                step=step,
                edge_count=int(evaluation.neighborhood.row.numel()),
                step_wall_seconds=step_times[-1],
                tracker=None,
                force_inventory=step in sentinel_inventory_steps,
                current_rss_limit_bytes=sentinel_rss_limit,
                note=f"sentinel_mode={mode}",
            )
    graph_nodes = max(
        _grad_graph_node_count(state.positions),
        _grad_graph_node_count(state.velocities),
    )
    summary = {
        "schema_version": PROBE_SCHEMA_VERSION,
        "run_id": run_id,
        "variant": "D",
        "mode": mode,
        "resolution": resolution,
        "particle_count": resolution**2,
        "completed_steps": int(sentinel["steps"]),
        "planned_steps": int(sentinel["steps"]),
        "status": "PASS",
        "torch_no_grad": mode == "no_grad",
        "final_positions_requires_grad": bool(state.positions.requires_grad),
        "final_velocities_requires_grad": bool(state.velocities.requires_grad),
        "final_positions_has_grad_fn": state.positions.grad_fn is not None,
        "final_velocities_has_grad_fn": state.velocities.grad_fn is not None,
        "reachable_grad_graph_node_count": int(graph_nodes),
        "mean_step_wall_seconds": float(np.mean(step_times)),
        "config_hash": config_hash,
        "git_hash": git_hash,
        "formal_resource_qualification": False,
    }
    artifacts.summary.update(summary)
    del state, evaluation, parameters
    gc.collect()
    sample_memory_checkpoint(
        sampler,
        configuration=configuration,
        phase="before_process_exit",
        step=int(sentinel["steps"]),
        edge_count=None,
        step_wall_seconds=None,
        tracker=None,
        force_inventory=True,
        current_rss_limit_bytes=sentinel_rss_limit,
        note=f"sentinel_mode={mode};solver_state_released",
    )
    return summary


def run_frozen_state_regression(
    *,
    configuration: Mapping[str, Any],
    resolution: int,
) -> list[dict[str, Any]]:
    """Replay steps 0-4 and compare every frozen state field independently."""

    project_root = Path(__file__).resolve().parents[2]
    resolution_config = configuration["resolutions"][resolution]
    reference_path = project_root / str(
        resolution_config["frozen_reference_archive"]
    )
    comparison = configuration["qualification"]["first_four_state_comparison"]
    expected_steps = [int(value) for value in comparison["steps"]]
    fields = [str(value) for value in comparison["fields"]]
    required_keys = {"steps", "times", *fields}
    reference_sha256 = _sha256(reference_path)
    with np.load(reference_path, allow_pickle=False) as archive:
        if set(archive.files) != required_keys:
            raise RuntimeError("frozen reference archive key set changed")
        reference_steps = archive["steps"].astype(np.int64).tolist()
        if len(reference_steps) != len(set(reference_steps)):
            raise RuntimeError("frozen reference archive has duplicate steps")
        indices = [reference_steps.index(step) for step in expected_steps]
        expected_times = np.asarray(expected_steps, dtype=np.float64) * float(
            resolution_config["time_step"]
        )
        if not np.array_equal(archive["times"][indices], expected_times):
            raise RuntimeError("frozen reference archive times changed")
        references = {
            field: np.asarray(archive[field][indices]).copy()
            for field in fields
        }
    rows: list[dict[str, Any]] = []
    with torch.no_grad():
        state, parameters, _, dt = _initialize_state(
            configuration,
            resolution=resolution,
        )
        state, evaluation = prepare_dynamic_state(state, parameters)
        for sample_index, step in enumerate(expected_steps):
            if step > 0:
                result = explicit_midpoint_dynamic_step(
                    state,
                    dt=dt,
                    parameters=parameters,
                    start_evaluation=evaluation,
                )
                state = result.state.with_updates(time=step * dt)
                evaluation = result.end_evaluation
                del result
            current = {
                "positions": state.positions.detach().cpu().numpy(),
                "velocities": state.velocities.detach().cpu().numpy(),
                "densities": evaluation.densities.detach().cpu().numpy(),
                "pressures": evaluation.pressures.detach().cpu().numpy(),
            }
            for field in fields:
                observed = current[field]
                expected = references[field][sample_index]
                absolute = np.abs(observed - expected)
                scale = np.maximum(np.abs(expected), np.finfo(np.float64).tiny)
                rows.append(
                    {
                        "resolution": resolution,
                        "step": step,
                        "field": field,
                        "shape_exact": observed.shape == expected.shape,
                        "dtype_exact": observed.dtype == expected.dtype,
                        "bitwise_equal": bool(np.array_equal(observed, expected)),
                        "maximum_absolute_difference": float(absolute.max()),
                        "maximum_relative_difference": float(
                            (absolute / scale).max()
                        ),
                        "within_preregistered_tolerance": bool(
                            np.allclose(
                                observed,
                                expected,
                                rtol=float(comparison["relative_tolerance"]),
                                atol=float(comparison["absolute_tolerance"]),
                            )
                        ),
                        "reference_path": str(
                            Path(resolution_config["frozen_reference_archive"])
                        ),
                        "reference_sha256": reference_sha256,
                    }
                )
    return rows
