"""Stable, scalar diagnostics for Stage 01D dynamic SPH experiments.

The public collection function deliberately returns only JSON/CSV-safe scalar
values.  It does not retain autograd graphs and it does not write files.  A
runner can therefore append every returned record to an evidence table without
having to reinterpret tensors after a failed experiment.

Norm conventions
----------------
Velocity L1 and Linf are the mean and maximum, respectively, of the per-particle
Euclidean error magnitude.  Relative L2 is the unweighted discrete Euclidean
norm of the velocity error divided by that of the exact velocity.  The TGV
modal amplitude is the mass-weighted least-squares projection onto the
dimensionless Taylor--Green basis.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import math
import resource
import sys
from typing import TypeAlias

import torch

from structure_preserving.conservative_pressure import (
    accumulate_pair_forces,
    conservative_pressure_pair_forces,
    pressure_conservation_metrics,
)
from structure_preserving.conservative_viscosity import (
    conservative_viscosity_pair_forces,
    viscosity_conservation_metrics,
)
from structure_preserving.neighborhood import (
    PeriodicNeighborhood,
    audit_periodic_neighborhood,
)


JSONScalar: TypeAlias = str | int | float | bool | None

DIAGNOSTIC_SCHEMA_VERSION = "sph-pio-poc.stage01d.dynamic-diagnostics.v1"

FLOAT64_PAIR_RELATIVE_TOLERANCE = 1.0e-12
FLOAT64_TOTAL_FORCE_RELATIVE_TOLERANCE = 1.0e-10
DEFAULT_VISCOUS_POWER_POSITIVE_ABSOLUTE_TOLERANCE = 1.0e-12
DEFAULT_RSS_LIMIT_BYTES = 8_000_000_000
DEFAULT_THERMAL_SLOWDOWN_LIMIT = 0.30


# This order is the canonical per-sample CSV column order.
DYNAMIC_DIAGNOSTIC_COLUMNS = (
    "schema_version",
    "run_id",
    "config_hash",
    "git_hash",
    "sample_index",
    "step",
    "time",
    "dt",
    "status",
    "particle_count",
    "dtype",
    "device",
    "state_all_finite",
    "nonfinite_position_count",
    "nonfinite_velocity_count",
    "nonfinite_density_count",
    "nonfinite_pressure_count",
    "nonfinite_sound_speed_count",
    "nonpositive_density_count",
    "nonpositive_sound_speed_count",
    "total_mass",
    "velocity_error_l1",
    "velocity_error_l2",
    "velocity_relative_l2",
    "velocity_error_linf",
    "modal_amplitude",
    "exact_modal_amplitude",
    "modal_amplitude_error",
    "modal_amplitude_relative_error",
    "kinetic_energy",
    "exact_kinetic_energy",
    "kinetic_energy_error",
    "kinetic_energy_relative_error",
    "density_mean",
    "density_std",
    "density_fluctuation_rms",
    "density_fluctuation_relative_rms",
    "density_fluctuation_linf",
    "density_fluctuation_relative_linf",
    "density_minimum",
    "density_maximum",
    "pressure_minimum",
    "pressure_maximum",
    "pressure_absolute_maximum",
    "maximum_speed",
    "maximum_mach",
    "momentum_x",
    "momentum_y",
    "momentum_norm",
    "momentum_drift_x",
    "momentum_drift_y",
    "momentum_drift_absolute",
    "momentum_drift_normalized",
    "angular_momentum",
    "angular_momentum_drift_absolute",
    "angular_momentum_drift_normalized",
    "velocity_divergence_l2",
    "minimum_separation",
    "neighbor_edge_count",
    "neighbor_unique_edge_count",
    "neighbor_duplicate_edge_count",
    "neighbor_self_edge_count",
    "neighbor_missing_self_edge_count",
    "neighbor_nonreciprocal_nonself_edge_count",
    "neighbor_out_of_bounds_edge_count",
    "neighbor_omitted_strict_support_edge_count",
    "neighbor_unexpected_edge_count",
    "neighbor_minimum_image_linf",
    "neighbor_expected_strict_edge_count",
    "neighbor_count_mean",
    "neighbor_count_std",
    "neighbor_count_median",
    "neighbor_count_min",
    "neighbor_count_max",
    "neighbor_nonself_count_mean",
    "pressure_pair_force_residual_linf",
    "pressure_relative_pair_force_residual",
    "pressure_total_internal_force",
    "pressure_relative_total_internal_force",
    "pressure_minimum_image_pair_torque_linf",
    "pressure_relative_pair_torque_linf",
    "pressure_relative_total_pair_torque",
    "pressure_force_scale",
    "viscosity_gamma_minimum",
    "viscosity_gamma_maximum",
    "viscosity_relative_gamma_symmetry_residual",
    "viscosity_pair_force_residual_linf",
    "viscosity_relative_pair_force_residual",
    "viscosity_total_internal_force",
    "viscosity_relative_total_internal_force",
    "viscosity_minimum_image_pair_torque_linf",
    "viscosity_force_scale",
    "total_internal_force_x",
    "total_internal_force_y",
    "total_internal_force",
    "relative_total_internal_force",
    "accumulated_viscous_power",
    "pair_direct_viscous_power",
    "viscous_power_identity_absolute_difference",
    "viscous_power_positive_absolute_tolerance",
    "viscous_power_roundoff_tolerance",
    "wall_clock_seconds",
    "step_time_count",
    "step_time_mean_seconds",
    "step_time_median_seconds",
    "step_time_p95_seconds",
    "step_time_early_mean_seconds",
    "step_time_late_mean_seconds",
    "step_time_late_to_early_ratio",
    "thermal_slowdown_fraction",
    "peak_rss_bytes",
    "peak_rss_gib",
)


# Canonical one-row-per-run table.  Aggregation policy belongs in the runner;
# this constant prevents ad-hoc column drift between pilot and resolution runs.
DYNAMIC_RUN_TABLE_COLUMNS = (
    "schema_version",
    "run_id",
    "config_hash",
    "git_hash",
    "protocol",
    "method_id",
    "device",
    "dtype",
    "resolution",
    "particle_count",
    "dt",
    "t_final",
    "sample_interval",
    "status",
    "failure_class",
    "failure_reason",
    "first_failure_step",
    "first_failure_time",
    "final_velocity_relative_l2",
    "maximum_velocity_relative_l2",
    "final_modal_amplitude_relative_error",
    "final_kinetic_energy_relative_error",
    "maximum_density_fluctuation_relative_rms",
    "maximum_mach",
    "maximum_momentum_drift_normalized",
    "maximum_angular_momentum_drift_normalized",
    "maximum_pressure_relative_pair_force_residual",
    "maximum_viscosity_relative_pair_force_residual",
    "maximum_relative_total_internal_force",
    "maximum_viscous_power",
    "minimum_separation",
    "minimum_neighbor_count",
    "maximum_neighbor_count",
    "maximum_duplicate_edge_count",
    "maximum_omitted_strict_support_edge_count",
    "maximum_nonreciprocal_nonself_edge_count",
    "wall_clock_seconds",
    "mean_step_seconds",
    "thermal_slowdown_fraction",
    "peak_rss_bytes",
    "sample_table_path",
    "stdout_log_path",
    "stderr_log_path",
    "failure_evidence_path",
)


GATE_COLUMNS = (
    "pair_relative_tolerance",
    "total_force_relative_tolerance",
    "viscous_power_positive_absolute_tolerance",
    "viscous_power_identity_tolerance",
    "rss_limit_bytes",
    "thermal_slowdown_limit",
    "finite_state_pass",
    "topology_pass",
    "pressure_pair_residual_pass",
    "viscosity_pair_residual_pass",
    "pressure_total_force_pass",
    "viscosity_total_force_pass",
    "combined_total_force_pass",
    "viscous_power_nonpositive_pass",
    "viscous_power_identity_pass",
    "physics_gates_complete",
    "physics_gates_pass",
    "rss_limit_pass",
    "thermal_limit_pass",
    "stop_requested",
)


def _tensor_float(value: torch.Tensor) -> float:
    return float(value.detach().cpu().reshape(()).item())


def _finite_or_none(value: float | int | torch.Tensor | None) -> float | None:
    if value is None:
        return None
    result = _tensor_float(value) if torch.is_tensor(value) else float(value)
    return result if math.isfinite(result) else None


def _relative_error(numerator: float, denominator: float) -> float | None:
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    if denominator > 0.0:
        return numerator / denominator
    return 0.0 if numerator == 0.0 else None


def _particle_values(
    value: float | torch.Tensor,
    count: int,
    reference: torch.Tensor,
    *,
    name: str,
    positive: bool,
) -> torch.Tensor:
    result = torch.as_tensor(
        value,
        dtype=reference.dtype,
        device=reference.device,
    )
    if result.numel() == 1:
        result = result.reshape(1).expand(count)
    elif result.shape != (count,):
        raise ValueError(f"{name} must be scalar or have shape [particles]")
    detached = result.detach()
    if bool((~torch.isfinite(detached)).any()):
        raise ValueError(f"{name} must be finite")
    if positive and bool((detached <= 0.0).any()):
        raise ValueError(f"{name} must be positive")
    return result


def _validate_vector_field(
    value: torch.Tensor,
    count: int,
    *,
    name: str,
) -> None:
    if value.shape != (count, 2):
        raise ValueError(f"{name} must have shape [particles, 2]")


def _nonfinite_count(value: torch.Tensor) -> int:
    return int((~torch.isfinite(value.detach())).sum().cpu().item())


def tgv_modal_basis(
    positions: torch.Tensor,
    *,
    wave_number: float = math.pi,
) -> torch.Tensor:
    """Return the dimensionless 2-D Taylor--Green velocity basis.

    The basis is ``[-sin(k*x) cos(k*y), cos(k*x) sin(k*y)]``.  For the
    Stage 01D domain ``[-1, 1)^2``, ``k = pi``.
    """

    if positions.ndim != 2 or positions.shape[1] != 2:
        raise ValueError("positions must have shape [particles, 2]")
    x = positions[:, 0]
    y = positions[:, 1]
    k = torch.as_tensor(
        wave_number,
        dtype=positions.dtype,
        device=positions.device,
    )
    return torch.stack(
        (
            -torch.sin(k * x) * torch.cos(k * y),
            torch.cos(k * x) * torch.sin(k * y),
        ),
        dim=-1,
    )


def tgv_exact_modal_amplitude(
    time: float,
    *,
    initial_velocity: float,
    kinematic_viscosity: float,
    wave_number: float = math.pi,
) -> float:
    """Return ``U0 exp(-2 nu k^2 t)`` for the 2-D TGV mode."""

    if time < 0.0:
        raise ValueError("time must be nonnegative")
    if kinematic_viscosity < 0.0:
        raise ValueError("kinematic_viscosity must be nonnegative")
    return float(
        initial_velocity
        * math.exp(-2.0 * kinematic_viscosity * wave_number**2 * time)
    )


def tgv_exact_kinetic_energy(
    time: float,
    *,
    initial_kinetic_energy: float,
    kinematic_viscosity: float,
    wave_number: float = math.pi,
) -> float:
    """Return ``E0 exp(-4 nu k^2 t)`` using the runner's discrete ``E0``."""

    if time < 0.0:
        raise ValueError("time must be nonnegative")
    if initial_kinetic_energy < 0.0:
        raise ValueError("initial_kinetic_energy must be nonnegative")
    if kinematic_viscosity < 0.0:
        raise ValueError("kinematic_viscosity must be nonnegative")
    return float(
        initial_kinetic_energy
        * math.exp(-4.0 * kinematic_viscosity * wave_number**2 * time)
    )


def velocity_error_metrics(
    velocity: torch.Tensor,
    exact_velocity: torch.Tensor,
) -> dict[str, float | None]:
    """Compute discrete vector L1, L2, relative L2, and Linf errors."""

    if velocity.shape != exact_velocity.shape:
        raise ValueError("velocity and exact_velocity must have identical shapes")
    if velocity.ndim != 2 or velocity.shape[1] != 2:
        raise ValueError("velocity fields must have shape [particles, 2]")
    error_magnitude = torch.linalg.vector_norm(
        velocity - exact_velocity,
        dim=-1,
    )
    error_l2 = torch.linalg.vector_norm(error_magnitude)
    exact_l2 = torch.linalg.vector_norm(exact_velocity)
    error_l2_value = _tensor_float(error_l2)
    exact_l2_value = _tensor_float(exact_l2)
    return {
        "velocity_error_l1": _tensor_float(error_magnitude.mean()),
        "velocity_error_l2": error_l2_value,
        "velocity_relative_l2": _relative_error(
            error_l2_value,
            exact_l2_value,
        ),
        "velocity_error_linf": _tensor_float(error_magnitude.max()),
    }


def mass_weighted_modal_amplitude(
    velocity: torch.Tensor,
    basis: torch.Tensor,
    mass: float | torch.Tensor,
) -> float:
    """Project a velocity field onto ``basis`` with particle-mass weights."""

    if velocity.shape != basis.shape:
        raise ValueError("velocity and basis must have identical shapes")
    if velocity.ndim != 2 or velocity.shape[1] != 2:
        raise ValueError("velocity and basis must have shape [particles, 2]")
    masses = _particle_values(
        mass,
        int(velocity.shape[0]),
        velocity,
        name="mass",
        positive=True,
    )
    numerator = torch.sum(
        masses * torch.sum(velocity * basis, dim=-1)
    )
    denominator = torch.sum(
        masses * torch.sum(basis.square(), dim=-1)
    )
    if _tensor_float(denominator) <= 0.0:
        raise ValueError("modal basis has zero mass-weighted norm")
    return _tensor_float(numerator / denominator)


def kinetic_energy(
    velocity: torch.Tensor,
    mass: float | torch.Tensor,
) -> float:
    """Return total discrete kinetic energy ``0.5 sum_i m_i |v_i|^2``."""

    if velocity.ndim != 2 or velocity.shape[1] != 2:
        raise ValueError("velocity must have shape [particles, 2]")
    masses = _particle_values(
        mass,
        int(velocity.shape[0]),
        velocity,
        name="mass",
        positive=True,
    )
    return _tensor_float(
        0.5 * torch.sum(masses * torch.sum(velocity.square(), dim=-1))
    )


def density_statistics(
    density: torch.Tensor,
    *,
    reference_density: float,
) -> dict[str, float]:
    """Return arithmetic density mean and fluctuations about ``rho0``."""

    if density.ndim != 1 or density.numel() == 0:
        raise ValueError("density must be a nonempty one-dimensional tensor")
    if reference_density <= 0.0 or not math.isfinite(reference_density):
        raise ValueError("reference_density must be finite and positive")
    fluctuation = density - reference_density
    rms = torch.sqrt(torch.mean(fluctuation.square()))
    linf = fluctuation.abs().max()
    return {
        "density_mean": _tensor_float(density.mean()),
        "density_std": _tensor_float(density.std(unbiased=False)),
        "density_fluctuation_rms": _tensor_float(rms),
        "density_fluctuation_relative_rms": _tensor_float(
            rms / reference_density
        ),
        "density_fluctuation_linf": _tensor_float(linf),
        "density_fluctuation_relative_linf": _tensor_float(
            linf / reference_density
        ),
        "density_minimum": _tensor_float(density.min()),
        "density_maximum": _tensor_float(density.max()),
    }


def timing_statistics(
    step_times_seconds: Sequence[float] | torch.Tensor | None,
) -> dict[str, JSONScalar]:
    """Summarize post-warm-up step timings and the late/early slowdown."""

    result: dict[str, JSONScalar] = {
        "step_time_count": 0,
        "step_time_mean_seconds": None,
        "step_time_median_seconds": None,
        "step_time_p95_seconds": None,
        "step_time_early_mean_seconds": None,
        "step_time_late_mean_seconds": None,
        "step_time_late_to_early_ratio": None,
        "thermal_slowdown_fraction": None,
    }
    if step_times_seconds is None:
        return result
    if torch.is_tensor(step_times_seconds):
        raw_times = step_times_seconds.detach().cpu().reshape(-1).tolist()
    else:
        raw_times = list(step_times_seconds)
    times = [float(value) for value in raw_times]
    if any((not math.isfinite(value) or value < 0.0) for value in times):
        raise ValueError("step times must be finite and nonnegative")
    count = len(times)
    result["step_time_count"] = count
    if count == 0:
        return result
    ordered = sorted(times)
    result["step_time_mean_seconds"] = sum(times) / count
    middle = count // 2
    if count % 2:
        median = ordered[middle]
    else:
        median = 0.5 * (ordered[middle - 1] + ordered[middle])
    result["step_time_median_seconds"] = median
    result["step_time_p95_seconds"] = ordered[
        max(0, math.ceil(0.95 * count) - 1)
    ]
    if count >= 2:
        split = count // 2
        early = times[:split]
        late = times[split:]
        early_mean = sum(early) / len(early)
        late_mean = sum(late) / len(late)
        result["step_time_early_mean_seconds"] = early_mean
        result["step_time_late_mean_seconds"] = late_mean
        if early_mean > 0.0:
            ratio = late_mean / early_mean
            result["step_time_late_to_early_ratio"] = ratio
            result["thermal_slowdown_fraction"] = ratio - 1.0
    return result


def process_peak_rss_bytes() -> int:
    """Return this process's peak resident-set size in bytes.

    Darwin reports ``ru_maxrss`` in bytes; Linux and the BSD-derived Python
    documentation convention used there report KiB.  Stage 01D runs on macOS,
    while the Linux branch keeps unit tests and CI portable.
    """

    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def viscous_power_roundoff_tolerance(
    dtype: torch.dtype,
    *,
    power_scale: float,
) -> float:
    """Return an explicit small absolute-plus-relative roundoff allowance."""

    try:
        epsilon = torch.finfo(dtype).eps
    except TypeError as error:
        raise ValueError("viscous power requires a floating-point dtype") from error
    return float(64.0 * epsilon * (1.0 + abs(power_scale)))


def conservation_tolerances(dtype: torch.dtype) -> dict[str, float]:
    """Return preregistered relative conservation tolerances by dtype."""

    if dtype == torch.float64:
        return {
            "pair_relative_tolerance": FLOAT64_PAIR_RELATIVE_TOLERANCE,
            "total_force_relative_tolerance": (
                FLOAT64_TOTAL_FORCE_RELATIVE_TOLERANCE
            ),
        }
    if dtype == torch.float32:
        return {
            "pair_relative_tolerance": 5.0e-6,
            "total_force_relative_tolerance": 5.0e-6,
        }
    raise ValueError("Stage 01D supports only float32 and float64 diagnostics")


def _minimum_separation(
    neighborhood: PeriodicNeighborhood,
) -> float | None:
    nonself_distance = neighborhood.distance[neighborhood.nonself]
    if nonself_distance.numel() == 0:
        return None
    return _tensor_float(nonself_distance.min())


def _neighbor_fields(
    audit: Mapping[str, float | int],
) -> dict[str, JSONScalar]:
    mapping = {
        "edge_count": "neighbor_edge_count",
        "unique_edge_count": "neighbor_unique_edge_count",
        "duplicate_edge_count": "neighbor_duplicate_edge_count",
        "self_edge_count": "neighbor_self_edge_count",
        "missing_self_edge_count": "neighbor_missing_self_edge_count",
        "nonreciprocal_nonself_edge_count": (
            "neighbor_nonreciprocal_nonself_edge_count"
        ),
        "out_of_bounds_edge_count": "neighbor_out_of_bounds_edge_count",
        "omitted_strict_support_edge_count": (
            "neighbor_omitted_strict_support_edge_count"
        ),
        "unexpected_edge_count": "neighbor_unexpected_edge_count",
        "minimum_image_linf": "neighbor_minimum_image_linf",
        "expected_strict_edge_count": "neighbor_expected_strict_edge_count",
        "neighbor_count_mean": "neighbor_count_mean",
        "neighbor_count_std": "neighbor_count_std",
        "neighbor_count_median": "neighbor_count_median",
        "neighbor_count_min": "neighbor_count_min",
        "neighbor_count_max": "neighbor_count_max",
        "nonself_neighbor_count_mean": "neighbor_nonself_count_mean",
    }
    result: dict[str, JSONScalar] = {}
    for source, destination in mapping.items():
        value = audit.get(source)
        if isinstance(value, bool):
            result[destination] = value
        elif isinstance(value, int):
            result[destination] = value
        else:
            result[destination] = _finite_or_none(value)
    return result


def _blank_diagnostic_record() -> dict[str, JSONScalar]:
    return {column: None for column in DYNAMIC_DIAGNOSTIC_COLUMNS}


def collect_dynamic_diagnostics(
    *,
    positions: torch.Tensor,
    velocity: torch.Tensor,
    mass: float | torch.Tensor,
    density: float | torch.Tensor,
    pressure: float | torch.Tensor,
    sound_speed: float | torch.Tensor,
    neighborhood: PeriodicNeighborhood,
    physical_viscosity: float | torch.Tensor,
    time: float,
    exact_velocity: torch.Tensor | None = None,
    modal_basis: torch.Tensor | None = None,
    exact_modal_amplitude: float | None = None,
    exact_kinetic_energy: float | None = None,
    reference_density: float = 1.0,
    reference_momentum: torch.Tensor | None = None,
    reference_angular_momentum: float | torch.Tensor | None = None,
    characteristic_velocity: float = 1.0,
    characteristic_length: float = 2.0,
    angular_momentum_positions: torch.Tensor | None = None,
    angular_momentum_origin: Sequence[float] | torch.Tensor | None = None,
    neighborhood_audit: Mapping[str, float | int] | None = None,
    velocity_divergence_l2: float | None = None,
    run_id: str = "",
    config_hash: str = "",
    git_hash: str = "",
    sample_index: int = 0,
    step: int = 0,
    dt: float | None = None,
    wall_clock_seconds: float | None = None,
    step_times_seconds: Sequence[float] | torch.Tensor | None = None,
    peak_rss_bytes: int | None = None,
    viscous_power_positive_absolute_tolerance: float = (
        DEFAULT_VISCOUS_POWER_POSITIVE_ABSOLUTE_TOLERANCE
    ),
) -> dict[str, JSONScalar]:
    """Collect one complete, fixed-schema dynamic diagnostic sample.

    ``angular_momentum_positions`` should be an unwrapped trajectory position
    when the integrator exposes one.  Falling back to wrapped positions is
    deterministic but can introduce coordinate-jump artifacts at periodic
    boundaries.

    ``kinetic_energy`` uses the total discrete convention
    ``0.5 * sum(m_i * |v_i|^2)``.  Consequently, ``exact_kinetic_energy`` must
    use the same convention; a domain-mean specific TGV reference must first
    be multiplied by total mass.

    A non-finite core state returns a fixed-schema ``NONFINITE_STATE`` record
    with unaffected topology/runtime evidence populated.  Structural shape
    errors and operator exceptions are intentionally raised so the runner can
    retain their complete traceback.
    """

    if positions.ndim != 2 or positions.shape[1] != 2:
        raise ValueError("positions must have shape [particles, 2]")
    count = int(positions.shape[0])
    if count <= 0:
        raise ValueError("at least one particle is required")
    _validate_vector_field(velocity, count, name="velocity")
    if neighborhood.particle_count != count:
        raise ValueError("neighborhood particle count does not match state")
    if not math.isfinite(float(time)) or float(time) < 0.0:
        raise ValueError("time must be finite and nonnegative")
    if dt is not None and (not math.isfinite(float(dt)) or float(dt) < 0.0):
        raise ValueError("dt must be finite and nonnegative")
    if characteristic_velocity <= 0.0 or not math.isfinite(
        characteristic_velocity
    ):
        raise ValueError("characteristic_velocity must be finite and positive")
    if characteristic_length <= 0.0 or not math.isfinite(characteristic_length):
        raise ValueError("characteristic_length must be finite and positive")
    if (
        not math.isfinite(viscous_power_positive_absolute_tolerance)
        or viscous_power_positive_absolute_tolerance < 0.0
    ):
        raise ValueError(
            "viscous_power_positive_absolute_tolerance must be finite "
            "and nonnegative"
        )

    densities = torch.as_tensor(
        density,
        dtype=positions.dtype,
        device=positions.device,
    )
    pressures = torch.as_tensor(
        pressure,
        dtype=positions.dtype,
        device=positions.device,
    )
    sound_speeds = torch.as_tensor(
        sound_speed,
        dtype=positions.dtype,
        device=positions.device,
    )
    for name, value in (
        ("density", densities),
        ("pressure", pressures),
        ("sound_speed", sound_speeds),
    ):
        if value.numel() == 1:
            value = value.reshape(1).expand(count)
        elif value.shape != (count,):
            raise ValueError(
                f"{name} must be scalar or have shape [particles]"
            )
        if name == "density":
            densities = value
        elif name == "pressure":
            pressures = value
        else:
            sound_speeds = value

    record = _blank_diagnostic_record()
    record.update(
        {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "run_id": str(run_id),
            "config_hash": str(config_hash),
            "git_hash": str(git_hash),
            "sample_index": int(sample_index),
            "step": int(step),
            "time": float(time),
            "dt": None if dt is None else float(dt),
            "status": "OK",
            "particle_count": count,
            "dtype": str(positions.dtype).removeprefix("torch."),
            "device": str(positions.device),
            "nonfinite_position_count": _nonfinite_count(positions),
            "nonfinite_velocity_count": _nonfinite_count(velocity),
            "nonfinite_density_count": _nonfinite_count(densities),
            "nonfinite_pressure_count": _nonfinite_count(pressures),
            "nonfinite_sound_speed_count": _nonfinite_count(sound_speeds),
            "nonpositive_density_count": int(
                (densities.detach() <= 0.0).sum().cpu().item()
            ),
            "nonpositive_sound_speed_count": int(
                (sound_speeds.detach() <= 0.0).sum().cpu().item()
            ),
            "velocity_divergence_l2": _finite_or_none(
                velocity_divergence_l2
            ),
            "wall_clock_seconds": _finite_or_none(wall_clock_seconds),
            "viscous_power_positive_absolute_tolerance": (
                float(viscous_power_positive_absolute_tolerance)
            ),
        }
    )
    record["state_all_finite"] = not any(
        int(record[key] or 0) > 0
        for key in (
            "nonfinite_position_count",
            "nonfinite_velocity_count",
            "nonfinite_density_count",
            "nonfinite_pressure_count",
            "nonfinite_sound_speed_count",
        )
    )

    audit = (
        audit_periodic_neighborhood(positions, neighborhood)
        if neighborhood_audit is None
        and int(record["nonfinite_position_count"] or 0) == 0
        else neighborhood_audit
    )
    if audit is not None:
        record.update(_neighbor_fields(audit))
    record["minimum_separation"] = _minimum_separation(neighborhood)
    record.update(timing_statistics(step_times_seconds))
    resolved_peak_rss = (
        process_peak_rss_bytes()
        if peak_rss_bytes is None
        else int(peak_rss_bytes)
    )
    if resolved_peak_rss < 0:
        raise ValueError("peak_rss_bytes must be nonnegative")
    record["peak_rss_bytes"] = resolved_peak_rss
    record["peak_rss_gib"] = resolved_peak_rss / 1024**3

    if not bool(record["state_all_finite"]):
        record["status"] = "NONFINITE_STATE"
        validate_serializable_record(record, required_columns=True)
        return record
    if int(record["nonpositive_density_count"] or 0) > 0 or int(
        record["nonpositive_sound_speed_count"] or 0
    ) > 0:
        record["status"] = "INVALID_PHYSICAL_STATE"
        validate_serializable_record(record, required_columns=True)
        return record

    with torch.no_grad():
        masses = _particle_values(
            mass,
            count,
            positions,
            name="mass",
            positive=True,
        )
        total_mass = masses.sum()
        record["total_mass"] = _tensor_float(total_mass)

        if exact_velocity is not None:
            _validate_vector_field(
                exact_velocity,
                count,
                name="exact_velocity",
            )
            record.update(velocity_error_metrics(velocity, exact_velocity))

        if modal_basis is not None:
            _validate_vector_field(modal_basis, count, name="modal_basis")
            modal_amplitude = mass_weighted_modal_amplitude(
                velocity,
                modal_basis,
                masses,
            )
            record["modal_amplitude"] = modal_amplitude
            exact_amplitude = _finite_or_none(exact_modal_amplitude)
            record["exact_modal_amplitude"] = exact_amplitude
            if exact_amplitude is not None:
                amplitude_error = abs(modal_amplitude - exact_amplitude)
                record["modal_amplitude_error"] = amplitude_error
                record["modal_amplitude_relative_error"] = _relative_error(
                    amplitude_error,
                    abs(exact_amplitude),
                )
        elif exact_modal_amplitude is not None:
            raise ValueError(
                "exact_modal_amplitude requires a modal_basis"
            )

        energy = kinetic_energy(velocity, masses)
        record["kinetic_energy"] = energy
        exact_energy = _finite_or_none(exact_kinetic_energy)
        record["exact_kinetic_energy"] = exact_energy
        if exact_energy is not None:
            energy_error = abs(energy - exact_energy)
            record["kinetic_energy_error"] = energy_error
            record["kinetic_energy_relative_error"] = _relative_error(
                energy_error,
                abs(exact_energy),
            )

        record.update(
            density_statistics(
                densities,
                reference_density=reference_density,
            )
        )
        record["pressure_minimum"] = _tensor_float(pressures.min())
        record["pressure_maximum"] = _tensor_float(pressures.max())
        record["pressure_absolute_maximum"] = _tensor_float(
            pressures.abs().max()
        )

        speeds = torch.linalg.vector_norm(velocity, dim=-1)
        record["maximum_speed"] = _tensor_float(speeds.max())
        record["maximum_mach"] = _tensor_float(
            (speeds / sound_speeds).max()
        )

        momentum = torch.sum(masses[:, None] * velocity, dim=0)
        record["momentum_x"] = _tensor_float(momentum[0])
        record["momentum_y"] = _tensor_float(momentum[1])
        record["momentum_norm"] = _tensor_float(
            torch.linalg.vector_norm(momentum)
        )
        if reference_momentum is not None:
            reference_momentum_tensor = torch.as_tensor(
                reference_momentum,
                dtype=positions.dtype,
                device=positions.device,
            )
            if reference_momentum_tensor.shape != (2,):
                raise ValueError("reference_momentum must have shape [2]")
            momentum_drift = momentum - reference_momentum_tensor
            drift_norm = torch.linalg.vector_norm(momentum_drift)
            record["momentum_drift_x"] = _tensor_float(momentum_drift[0])
            record["momentum_drift_y"] = _tensor_float(momentum_drift[1])
            record["momentum_drift_absolute"] = _tensor_float(drift_norm)
            record["momentum_drift_normalized"] = _tensor_float(
                drift_norm / (total_mass * characteristic_velocity)
            )

        angular_positions = (
            positions
            if angular_momentum_positions is None
            else angular_momentum_positions
        )
        _validate_vector_field(
            angular_positions,
            count,
            name="angular_momentum_positions",
        )
        if angular_momentum_origin is None:
            origin = 0.5 * (
                neighborhood.domain_min + neighborhood.domain_max
            )
        else:
            origin = torch.as_tensor(
                angular_momentum_origin,
                dtype=positions.dtype,
                device=positions.device,
            )
            if origin.shape != (2,):
                raise ValueError("angular_momentum_origin must have shape [2]")
        relative_position = angular_positions - origin
        angular_momentum = torch.sum(
            masses
            * (
                relative_position[:, 0] * velocity[:, 1]
                - relative_position[:, 1] * velocity[:, 0]
            )
        )
        record["angular_momentum"] = _tensor_float(angular_momentum)
        if reference_angular_momentum is not None:
            angular_reference = torch.as_tensor(
                reference_angular_momentum,
                dtype=positions.dtype,
                device=positions.device,
            ).reshape(())
            angular_drift = (angular_momentum - angular_reference).abs()
            record["angular_momentum_drift_absolute"] = _tensor_float(
                angular_drift
            )
            record["angular_momentum_drift_normalized"] = _tensor_float(
                angular_drift
                / (
                    total_mass
                    * characteristic_length
                    * characteristic_velocity
                )
            )

        pressure_metrics = pressure_conservation_metrics(
            neighborhood,
            mass=masses,
            density=densities,
            pressure=pressures,
        )
        viscosity_metrics = viscosity_conservation_metrics(
            neighborhood,
            mass=masses,
            density=densities,
            velocity=velocity,
            physical_viscosity=physical_viscosity,
        )
        pressure_mapping = {
            "pair_force_residual_linf": (
                "pressure_pair_force_residual_linf"
            ),
            "relative_pair_force_residual": (
                "pressure_relative_pair_force_residual"
            ),
            "total_internal_force": "pressure_total_internal_force",
            "relative_total_internal_force": (
                "pressure_relative_total_internal_force"
            ),
            "minimum_image_pair_torque_linf": (
                "pressure_minimum_image_pair_torque_linf"
            ),
            "relative_pair_torque_linf": (
                "pressure_relative_pair_torque_linf"
            ),
            "relative_total_pair_torque": (
                "pressure_relative_total_pair_torque"
            ),
            "force_scale": "pressure_force_scale",
        }
        viscosity_mapping = {
            "gamma_minimum": "viscosity_gamma_minimum",
            "gamma_maximum": "viscosity_gamma_maximum",
            "relative_gamma_symmetry_residual": (
                "viscosity_relative_gamma_symmetry_residual"
            ),
            "pair_force_residual_linf": (
                "viscosity_pair_force_residual_linf"
            ),
            "relative_pair_force_residual": (
                "viscosity_relative_pair_force_residual"
            ),
            "total_internal_force": "viscosity_total_internal_force",
            "relative_total_internal_force": (
                "viscosity_relative_total_internal_force"
            ),
            "minimum_image_pair_torque_linf": (
                "viscosity_minimum_image_pair_torque_linf"
            ),
            "accumulated_viscous_power": "accumulated_viscous_power",
            "pair_direct_viscous_power": "pair_direct_viscous_power",
            "power_identity_absolute_difference": (
                "viscous_power_identity_absolute_difference"
            ),
        }
        for source, destination in pressure_mapping.items():
            record[destination] = _finite_or_none(pressure_metrics[source])
        for source, destination in viscosity_mapping.items():
            record[destination] = _finite_or_none(viscosity_metrics[source])

        pressure_i, pressure_j, pressure_pair_force = (
            conservative_pressure_pair_forces(
                neighborhood,
                mass=masses,
                density=densities,
                pressure=pressures,
            )
        )
        viscosity_i, viscosity_j, viscosity_pair_force, _ = (
            conservative_viscosity_pair_forces(
                neighborhood,
                mass=masses,
                density=densities,
                velocity=velocity,
                physical_viscosity=physical_viscosity,
            )
        )
        pressure_particle_force = accumulate_pair_forces(
            count,
            pressure_i,
            pressure_j,
            pressure_pair_force,
        )
        viscosity_particle_force = accumulate_pair_forces(
            count,
            viscosity_i,
            viscosity_j,
            viscosity_pair_force,
        )
        total_internal_force_vector = (
            pressure_particle_force + viscosity_particle_force
        ).sum(dim=0)
        total_internal_force = torch.linalg.vector_norm(
            total_internal_force_vector
        )
        combined_force_scale = 2.0 * (
            torch.linalg.vector_norm(pressure_pair_force, dim=-1).sum()
            + torch.linalg.vector_norm(viscosity_pair_force, dim=-1).sum()
        )
        tiny = torch.finfo(positions.dtype).tiny
        viscosity_force_scale = 2.0 * torch.linalg.vector_norm(
            viscosity_pair_force,
            dim=-1,
        ).sum()
        record["viscosity_force_scale"] = _tensor_float(
            viscosity_force_scale
        )
        record["total_internal_force_x"] = _tensor_float(
            total_internal_force_vector[0]
        )
        record["total_internal_force_y"] = _tensor_float(
            total_internal_force_vector[1]
        )
        record["total_internal_force"] = _tensor_float(total_internal_force)
        record["relative_total_internal_force"] = _tensor_float(
            total_internal_force / (combined_force_scale + tiny)
        )
        direct_power = float(record["pair_direct_viscous_power"] or 0.0)
        record["viscous_power_roundoff_tolerance"] = (
            viscous_power_roundoff_tolerance(
                positions.dtype,
                power_scale=direct_power,
            )
        )

    validate_serializable_record(record, required_columns=True)
    return record


def _optional_le(value: JSONScalar, limit: float) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("gate metric must be a numeric scalar or None")
    return float(value) <= limit


def evaluate_dynamic_gates(
    record: Mapping[str, JSONScalar],
    *,
    pair_relative_tolerance: float | None = None,
    total_force_relative_tolerance: float | None = None,
    viscous_power_positive_absolute_tolerance: float | None = None,
    viscous_power_identity_tolerance: float | None = None,
    rss_limit_bytes: int = DEFAULT_RSS_LIMIT_BYTES,
    thermal_slowdown_limit: float = DEFAULT_THERMAL_SLOWDOWN_LIMIT,
) -> dict[str, JSONScalar]:
    """Evaluate conservation, topology, RSS, and thermal stop conditions."""

    dtype_name = str(record.get("dtype", ""))
    if pair_relative_tolerance is None or total_force_relative_tolerance is None:
        if dtype_name == "float64":
            defaults = conservation_tolerances(torch.float64)
        elif dtype_name == "float32":
            defaults = conservation_tolerances(torch.float32)
        else:
            raise ValueError("record dtype must be float32 or float64")
        if pair_relative_tolerance is None:
            pair_relative_tolerance = defaults["pair_relative_tolerance"]
        if total_force_relative_tolerance is None:
            total_force_relative_tolerance = defaults[
                "total_force_relative_tolerance"
            ]
    if pair_relative_tolerance < 0.0:
        raise ValueError("pair_relative_tolerance must be nonnegative")
    if total_force_relative_tolerance < 0.0:
        raise ValueError("total_force_relative_tolerance must be nonnegative")
    if rss_limit_bytes <= 0:
        raise ValueError("rss_limit_bytes must be positive")
    if thermal_slowdown_limit < 0.0:
        raise ValueError("thermal_slowdown_limit must be nonnegative")

    if viscous_power_positive_absolute_tolerance is None:
        stored_positive_tolerance = record.get(
            "viscous_power_positive_absolute_tolerance"
        )
        viscous_power_positive_absolute_tolerance = (
            DEFAULT_VISCOUS_POWER_POSITIVE_ABSOLUTE_TOLERANCE
            if stored_positive_tolerance is None
            else float(stored_positive_tolerance)
        )
    if (
        not math.isfinite(viscous_power_positive_absolute_tolerance)
        or viscous_power_positive_absolute_tolerance < 0.0
    ):
        raise ValueError(
            "viscous_power_positive_absolute_tolerance must be finite "
            "and nonnegative"
        )
    if viscous_power_identity_tolerance is None:
        stored_identity_tolerance = record.get(
            "viscous_power_roundoff_tolerance"
        )
        viscous_power_identity_tolerance = (
            None
            if stored_identity_tolerance is None
            else float(stored_identity_tolerance)
        )
    if viscous_power_identity_tolerance is not None and (
        not math.isfinite(viscous_power_identity_tolerance)
        or viscous_power_identity_tolerance < 0.0
    ):
        raise ValueError(
            "viscous_power_identity_tolerance must be finite and nonnegative"
        )
    identity_tolerance = (
        None
        if viscous_power_identity_tolerance is None
        else float(viscous_power_identity_tolerance)
    )
    accumulated_power = record.get("accumulated_viscous_power")
    direct_power = record.get("pair_direct_viscous_power")
    identity_difference = record.get(
        "viscous_power_identity_absolute_difference"
    )
    power_nonpositive_pass = (
        None
        if accumulated_power is None
        or direct_power is None
        else (
            float(accumulated_power)
            <= viscous_power_positive_absolute_tolerance
            and float(direct_power)
            <= viscous_power_positive_absolute_tolerance
        )
    )
    power_identity_pass = (
        None
        if identity_tolerance is None or identity_difference is None
        else float(identity_difference) <= identity_tolerance
    )

    topology_counts = (
        record.get("neighbor_duplicate_edge_count"),
        record.get("neighbor_missing_self_edge_count"),
        record.get("neighbor_nonreciprocal_nonself_edge_count"),
        record.get("neighbor_out_of_bounds_edge_count"),
        record.get("neighbor_omitted_strict_support_edge_count"),
        record.get("neighbor_unexpected_edge_count"),
    )
    topology_pass = (
        None
        if any(value is None for value in topology_counts)
        else all(int(value) == 0 for value in topology_counts)
    )
    gates: dict[str, JSONScalar] = {
        "pair_relative_tolerance": pair_relative_tolerance,
        "total_force_relative_tolerance": total_force_relative_tolerance,
        "viscous_power_positive_absolute_tolerance": (
            viscous_power_positive_absolute_tolerance
        ),
        "viscous_power_identity_tolerance": identity_tolerance,
        "rss_limit_bytes": int(rss_limit_bytes),
        "thermal_slowdown_limit": thermal_slowdown_limit,
        "finite_state_pass": (
            bool(record["state_all_finite"])
            if record.get("state_all_finite") is not None
            else None
        ),
        "topology_pass": topology_pass,
        "pressure_pair_residual_pass": _optional_le(
            record.get("pressure_relative_pair_force_residual"),
            pair_relative_tolerance,
        ),
        "viscosity_pair_residual_pass": _optional_le(
            record.get("viscosity_relative_pair_force_residual"),
            pair_relative_tolerance,
        ),
        "pressure_total_force_pass": _optional_le(
            record.get("pressure_relative_total_internal_force"),
            total_force_relative_tolerance,
        ),
        "viscosity_total_force_pass": _optional_le(
            record.get("viscosity_relative_total_internal_force"),
            total_force_relative_tolerance,
        ),
        "combined_total_force_pass": _optional_le(
            record.get("relative_total_internal_force"),
            total_force_relative_tolerance,
        ),
        "viscous_power_nonpositive_pass": power_nonpositive_pass,
        "viscous_power_identity_pass": power_identity_pass,
        "physics_gates_complete": None,
        "physics_gates_pass": None,
        "rss_limit_pass": _optional_le(
            record.get("peak_rss_bytes"),
            float(rss_limit_bytes),
        ),
        "thermal_limit_pass": _optional_le(
            record.get("thermal_slowdown_fraction"),
            thermal_slowdown_limit,
        ),
        "stop_requested": None,
    }
    physics_gate_names = (
        "finite_state_pass",
        "topology_pass",
        "pressure_pair_residual_pass",
        "viscosity_pair_residual_pass",
        "pressure_total_force_pass",
        "viscosity_total_force_pass",
        "combined_total_force_pass",
        "viscous_power_nonpositive_pass",
        "viscous_power_identity_pass",
    )
    physics_values = [gates[name] for name in physics_gate_names]
    gates["physics_gates_complete"] = all(
        value is not None for value in physics_values
    )
    gates["physics_gates_pass"] = (
        all(value is True for value in physics_values)
        if bool(gates["physics_gates_complete"])
        else None
    )
    stop_values = (
        *physics_values,
        gates["rss_limit_pass"],
        gates["thermal_limit_pass"],
    )
    gates["stop_requested"] = any(value is False for value in stop_values)
    validate_serializable_record(gates)
    return gates


def validate_serializable_record(
    record: Mapping[str, JSONScalar],
    *,
    required_columns: bool = False,
) -> None:
    """Reject tensors, nested values, non-finite floats, and schema drift."""

    if required_columns:
        missing = set(DYNAMIC_DIAGNOSTIC_COLUMNS) - set(record)
        extra = set(record) - set(DYNAMIC_DIAGNOSTIC_COLUMNS)
        if missing or extra:
            raise ValueError(
                f"diagnostic schema mismatch: missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
    for key, value in record.items():
        if not isinstance(key, str):
            raise TypeError("diagnostic record keys must be strings")
        if value is None or isinstance(value, (str, bool, int)):
            continue
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(f"non-finite diagnostic scalar: {key}")
            continue
        raise TypeError(
            f"diagnostic value {key!r} must be a JSON scalar, "
            f"not {type(value).__name__}"
        )


def ordered_diagnostic_row(
    record: Mapping[str, JSONScalar],
) -> dict[str, JSONScalar]:
    """Return one canonical-order row suitable for ``csv.DictWriter``."""

    validate_serializable_record(record, required_columns=True)
    return {column: record[column] for column in DYNAMIC_DIAGNOSTIC_COLUMNS}


def diagnostic_record_to_json(
    record: Mapping[str, JSONScalar],
    *,
    indent: int | None = None,
) -> str:
    """Serialize a diagnostic or gate record with strict finite-number JSON."""

    validate_serializable_record(record)
    return json.dumps(
        dict(record),
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
    )
