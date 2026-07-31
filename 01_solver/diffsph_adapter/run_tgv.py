#!/usr/bin/env python3
"""Run and record a headless official-diffSPH Taylor–Green validation case."""

from __future__ import annotations

import argparse
import copy
import csv
import dataclasses
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback
from typing import Any

import numpy as np
import torch
import yaml

from .tgv import (
    DIFFSPH_COMMIT,
    TGVConfig,
    advance_one_step,
    audit_system_device,
    build_context,
    synchronize,
    taylor_green_velocity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRICS_ROOT = PROJECT_ROOT / "05_metrics"
if str(METRICS_ROOT) not in sys.path:
    sys.path.insert(0, str(METRICS_ROOT))

from conservation import momentum_metrics, state_is_finite  # noqa: E402
from density import density_statistics  # noqa: E402
from energy import kinetic_energy_metrics, total_kinetic_energy  # noqa: E402
from runtime import RuntimeTracker, device_memory_bytes  # noqa: E402
from velocity_error import velocity_metrics  # noqa: E402


def _scalar(value: torch.Tensor | float | int | bool | None) -> Any:
    if value is None:
        return None
    if torch.is_tensor(value):
        if value.numel() != 1:
            raise ValueError(f"Expected scalar tensor, got shape {tuple(value.shape)}")
        return value.detach().cpu().item()
    return value


def _git_hash() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _package_versions() -> dict[str, str]:
    names = [
        "torch",
        "numpy",
        "scipy",
        "diffSPH",
        "torchCompactRadius",
        "h5py",
        "PyYAML",
    ]
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
    return versions


def _installed_python_tree_hash(package_name: str) -> str:
    """Hash installed Python sources without recording installation paths."""

    package = importlib.import_module(package_name)
    root = Path(package.__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _memory(device: torch.device) -> dict[str, int | None]:
    counters = dict(device_memory_bytes(device))
    # On macOS ru_maxrss is bytes.  It is a process high-water mark, not a
    # comparable current-allocation counter.
    counters["process_max_rss_bytes"] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return counters


def _state_hash(context: Any) -> str:
    digest = hashlib.sha256()
    state = context.system.systemState
    for tensor in (state.positions, state.velocities, state.densities):
        array = tensor.detach().cpu().contiguous().numpy()
        digest.update(array.tobytes())
    return digest.hexdigest()


def _metric_row(
    context: Any,
    *,
    step: int,
    step_seconds: float,
    initial_energy: torch.Tensor,
) -> dict[str, Any]:
    state = context.system.systemState
    time_value = _scalar(context.system.t)
    reference_velocity = taylor_green_velocity(
        state.positions,
        time_value,
        amplitude=context.spec.velocity_amplitude,
        viscosity=context.reference_kinematic_viscosity,
        wave_number=context.spec.wave_number,
    )
    velocity = velocity_metrics(state.velocities, reference_velocity)
    momentum = momentum_metrics(
        state.velocities,
        context.initial_velocities,
        mass=state.masses,
        reference_mass=state.masses,
    )
    # This matches the official example's energy definition.  For rho=rho0,
    # the effective mass reduces to the immutable SPH particle mass.
    effective_mass = state.masses * state.densities / context.spec.initial_density
    energy = kinetic_energy_metrics(
        state.velocities,
        reference_velocity,
        mass=effective_mass,
        reference_mass=state.masses,
    )
    energy_from_initial = total_kinetic_energy(state.velocities, effective_mass)
    density = density_statistics(state.densities, context.spec.initial_density)
    finite = state_is_finite(state.positions, state.velocities, state.densities)
    memory = _memory(context.device)
    total_momentum = momentum["total_momentum"]
    return {
        "backend": context.spec.backend,
        "dtype": context.spec.dtype,
        "resolution": context.spec.resolution,
        "particle_count": context.spec.particle_count,
        "run_id": context.spec.run_id,
        "seed": context.spec.seed,
        "step": step,
        "time": time_value,
        "dt": context.spec.target_dt,
        "velocity_relative_l2": _scalar(velocity["velocity_relative_l2"]),
        "velocity_rmse": _scalar(velocity["velocity_rmse"]),
        "total_kinetic_energy": _scalar(energy["total_kinetic_energy"]),
        "kinetic_energy_relative_error": _scalar(
            energy["kinetic_energy_relative_error"]
        ),
        "kinetic_energy_relative_initial": _scalar(
            (energy_from_initial - initial_energy).abs()
            / initial_energy.abs().clamp_min(torch.finfo(state.velocities.dtype).eps)
        ),
        "momentum_x": _scalar(total_momentum[0]),
        "momentum_y": _scalar(total_momentum[1]),
        "relative_momentum_drift": _scalar(momentum["relative_momentum_drift"]),
        "mean_density": _scalar(density["mean_density"]),
        "min_density": _scalar(density["min_density"]),
        "max_density": _scalar(density["max_density"]),
        "relative_density_fluctuation": _scalar(
            density["relative_density_fluctuation"]
        ),
        "max_particle_speed": _scalar(velocity["max_particle_speed"]),
        "has_nan_or_inf": not bool(_scalar(finite)),
        "step_time_seconds": step_seconds,
        **memory,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _save_trajectory(path: Path, snapshots: list[dict[str, Any]]) -> None:
    arrays: dict[str, Any] = {
        "steps": np.asarray([snapshot["step"] for snapshot in snapshots], dtype=np.int64),
        "times": np.asarray([snapshot["time"] for snapshot in snapshots], dtype=np.float64),
        "positions": np.stack([snapshot["positions"] for snapshot in snapshots]),
        "velocities": np.stack([snapshot["velocities"] for snapshot in snapshots]),
        "densities": np.stack([snapshot["densities"] for snapshot in snapshots]),
    }
    np.savez_compressed(path, **arrays)


def _snapshot(context: Any, step: int) -> dict[str, Any]:
    state = context.system.systemState
    return {
        "step": step,
        "time": _scalar(context.system.t),
        "positions": state.positions.detach().cpu().numpy(),
        "velocities": state.velocities.detach().cpu().numpy(),
        "densities": state.densities.detach().cpu().numpy(),
    }


def run(
    spec: TGVConfig,
    output_directory: Path,
    *,
    sustain_seconds: float | None = None,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = f"{spec.backend}_n{spec.resolution}_{spec.run_id}"
    numerical_path = output_directory / f"{stem}_numerical.csv"
    runtime_path = output_directory / f"{stem}_runtime.csv"
    trajectory_path = output_directory / f"{stem}_trajectory.npz"
    config_path = output_directory / f"{stem}_config.json"

    if spec.backend == "mps" and os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") == "1":
        raise RuntimeError("MPS fallback is enabled; refusing validation run")
    if sustain_seconds is not None and not 0 < sustain_seconds <= 900:
        raise ValueError("sustain_seconds must be in (0, 900]")

    metadata = spec.as_dict()
    metadata.update(
        {
            "project_git_hash": _git_hash(),
            "package_versions": _package_versions(),
            "diffsph_installed_python_tree_sha256": _installed_python_tree_hash(
                "diffSPH"
            ),
            "torchcompactradius_installed_python_tree_sha256": (
                _installed_python_tree_hash("torchCompactRadius")
            ),
            "python": sys.version.split()[0],
            "pytorch_mps_fallback_env": os.environ.get(
                "PYTORCH_ENABLE_MPS_FALLBACK", "unset"
            ),
            "device_fallback_disclosure": (
                "torchCompactRadius compact neighbor search transfers MPS "
                "positions to CPU and indices back to MPS"
                if spec.backend == "mps"
                else "none"
            ),
        }
    )
    startup_begin = time.perf_counter()
    context = build_context(spec)
    synchronize(context.device)
    startup_seconds = time.perf_counter() - startup_begin
    metadata.update(
        {
            "sound_speed": context.sound_speed,
            "smoothing_length": context.smoothing_length,
            "initial_state_sha256": _state_hash(context),
            "initial_state_policy": (
                "CPU canonical shuffled state copied tensor-for-tensor to MPS"
            ),
            "reference_kinematic_viscosity": (
                context.reference_kinematic_viscosity
            ),
            "reference_reynolds_number_U_L_over_nu": (
                context.reference_reynolds_number
            ),
            "viscosity_limitation": (
                "reachable diffSPH velocityDiffusion code hard-codes "
                "alpha=0.01; effective nu is the official notebook's "
                "post-hoc estimate and varies with resolution"
            ),
        }
    )
    config_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    # Warm a deep-copied official system; do not contaminate t=0 or metrics.
    warm_context = copy.deepcopy(context)
    warm_begin = time.perf_counter()
    for _ in range(spec.warmup_steps):
        current, updates = advance_one_step(warm_context)
        audit = audit_system_device(
            warm_context,
            extras={"current": current, "updates": updates},
        )
        if audit["mismatches"]:
            raise RuntimeError(f"Warm-up device mismatch: {audit['mismatches']}")
    synchronize(context.device)
    warmup_seconds = time.perf_counter() - warm_begin
    del warm_context

    state = context.system.systemState
    initial_effective_mass = (
        state.masses * state.densities / spec.initial_density
    )
    initial_energy = total_kinetic_energy(
        state.velocities,
        initial_effective_mass,
    ).detach()
    numerical_rows: list[dict[str, Any]] = [
        _metric_row(context, step=0, step_seconds=0.0, initial_energy=initial_energy)
    ]
    snapshots = [_snapshot(context, 0)]
    runtime_segments: list[dict[str, Any]] = []
    tracker = RuntimeTracker(context.device)
    first_nonfinite_step: int | None = None
    max_tensor_count = 0
    run_begin = time.perf_counter()
    segment_begin = run_begin
    segment_durations: list[float] = []
    step = 0
    target_steps = spec.total_steps

    try:
        while True:
            if sustain_seconds is None:
                if step >= target_steps:
                    break
            elif step > 0 and (time.perf_counter() - run_begin) >= sustain_seconds:
                break

            step += 1
            tracker.start()
            current, updates = advance_one_step(context)
            step_seconds = tracker.stop()
            segment_durations.append(step_seconds)
            audit = audit_system_device(
                context,
                extras={"current": current, "updates": updates},
            )
            max_tensor_count = max(max_tensor_count, int(audit["tensor_count"]))
            if audit["mismatches"]:
                raise RuntimeError(
                    f"Device mismatch at step {step}: {audit['mismatches']}"
                )

            state = context.system.systemState
            finite = bool(
                _scalar(
                    state_is_finite(
                        state.positions,
                        state.velocities,
                        state.densities,
                    )
                )
            )
            if not finite:
                first_nonfinite_step = step

            should_record = (
                step % spec.metric_interval == 0
                or (sustain_seconds is None and step == target_steps)
                or first_nonfinite_step is not None
            )
            if should_record:
                numerical_rows.append(
                    _metric_row(
                        context,
                        step=step,
                        step_seconds=step_seconds,
                        initial_energy=initial_energy,
                    )
                )
                snapshots.append(_snapshot(context, step))

            now = time.perf_counter()
            if sustain_seconds is not None and now - segment_begin >= 30.0:
                memory = _memory(context.device)
                segment_record = {
                    "backend": spec.backend,
                    "resolution": spec.resolution,
                    "particle_count": spec.particle_count,
                    "run_id": spec.run_id,
                    "record_type": "segment",
                    "segment_end_seconds": now - run_begin,
                    "segment_steps": len(segment_durations),
                    "mean_step_seconds": float(np.mean(segment_durations)),
                    "min_step_seconds": float(np.min(segment_durations)),
                    "max_step_seconds": float(np.max(segment_durations)),
                    **memory,
                }
                runtime_segments.append(segment_record)
                print(
                    json.dumps(
                        {"status": "RUNNING", **segment_record},
                        sort_keys=True,
                    ),
                    flush=True,
                )
                segment_begin = now
                segment_durations.clear()

            if first_nonfinite_step is not None:
                raise FloatingPointError(
                    f"NaN/Inf first observed at step {first_nonfinite_step}"
                )
    except Exception:
        _write_csv(numerical_path, numerical_rows)
        if snapshots:
            _save_trajectory(trajectory_path, snapshots)
        traceback.print_exc()
        raise

    synchronize(context.device)
    total_wall_seconds = time.perf_counter() - run_begin
    if segment_durations:
        memory = _memory(context.device)
        runtime_segments.append(
            {
                "backend": spec.backend,
                "resolution": spec.resolution,
                "particle_count": spec.particle_count,
                "run_id": spec.run_id,
                "record_type": "segment",
                "segment_end_seconds": total_wall_seconds,
                "segment_steps": len(segment_durations),
                "mean_step_seconds": float(np.mean(segment_durations)),
                "min_step_seconds": float(np.min(segment_durations)),
                "max_step_seconds": float(np.max(segment_durations)),
                **memory,
            }
        )

    summary = tracker.summary()
    final_memory = _memory(context.device)
    runtime_rows = [
        {
            "backend": spec.backend,
            "dtype": spec.dtype,
            "resolution": spec.resolution,
            "particle_count": spec.particle_count,
            "run_id": spec.run_id,
            "seed": spec.seed,
            "record_type": "summary",
            "startup_seconds": startup_seconds,
            "warmup_steps": spec.warmup_steps,
            "warmup_seconds": warmup_seconds,
            "measured_steps": summary.count,
            "total_step_seconds": summary.total_seconds,
            "mean_step_seconds": summary.mean_seconds,
            "min_step_seconds": summary.min_seconds,
            "max_step_seconds": summary.max_seconds,
            "std_step_seconds": summary.std_seconds,
            "total_wall_seconds": total_wall_seconds,
            "first_nonfinite_step": first_nonfinite_step,
            "device_fallback": spec.backend == "mps",
            "device_fallback_type": (
                "torchCompactRadius_compact_neighbor_search_cpu_bridge"
                if spec.backend == "mps"
                else "none"
            ),
            "pytorch_mps_fallback": False,
            "unsupported_operator": False,
            "max_audited_tensor_count": max_tensor_count,
            "initial_state_sha256": metadata["initial_state_sha256"],
            "final_state_sha256": _state_hash(context),
            "sustain_target_seconds": sustain_seconds,
            **final_memory,
        },
        *runtime_segments,
    ]
    _write_csv(numerical_path, numerical_rows)
    _write_csv(runtime_path, runtime_rows)
    _save_trajectory(trajectory_path, snapshots)
    print(
        json.dumps(
            {
                "status": "PASS",
                "numerical_csv": str(numerical_path.relative_to(PROJECT_ROOT)),
                "runtime_csv": str(runtime_path.relative_to(PROJECT_ROOT)),
                "trajectory": str(trajectory_path.relative_to(PROJECT_ROOT)),
                "steps": summary.count,
                "wall_seconds": total_wall_seconds,
                "final_state_sha256": runtime_rows[0]["final_state_sha256"],
            },
            sort_keys=True,
        )
    )
    return numerical_path, runtime_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=PROJECT_ROOT / "06_experiments/stage_01_tgv/raw",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--sustain-seconds", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    values = yaml.safe_load(args.config.read_text())
    spec = TGVConfig.from_mapping(values)
    if args.run_id:
        spec = dataclasses.replace(spec, run_id=args.run_id)
    run(
        spec,
        args.output_directory.resolve(),
        sustain_seconds=args.sustain_seconds,
    )


if __name__ == "__main__":
    main()
