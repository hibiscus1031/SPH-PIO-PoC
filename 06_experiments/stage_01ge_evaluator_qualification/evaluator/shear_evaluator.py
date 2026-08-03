"""Read-only evaluator for the frozen viscous transverse shear benchmark."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .common_metrics import (
    error_norms,
    fitted_positive_decay_rate,
    least_squares_coefficient,
    periodic_position_error,
    subtract,
    weighted_l2,
)
from .schema import SCHEMA_VERSION, MetricContractError, validate_dataset, validate_evaluator_output


def _weighted_vector_mean(vectors: list[list[float]], weights: list[float] | None) -> list[float]:
    raw = [1.0] * len(vectors) if weights is None else [float(value) for value in weights]
    total = math.fsum(raw)
    return [
        math.fsum(weight * float(vector[component]) for weight, vector in zip(raw, vectors)) / total
        for component in range(2)
    ]


def evaluate_shear(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate supplied trajectory/reference evidence without modifying either."""
    evidence = validate_dataset(dataset, "shear")
    metadata = evidence["metadata"]
    samples = evidence["samples"]
    weights = evidence.get("weights")
    domain_length = float(metadata["domain_length"])
    rho0 = float(metadata["rho0"])
    amplitude_scale = float(metadata["U_s"])
    wave_number = float(metadata["k_s"])
    exact_decay_rate = float(metadata["nu"]) * wave_number**2
    initial_reference_position = samples[0]["reference"]["position"]

    per_time: list[dict[str, Any]] = []
    numerical_amplitudes: list[float] = []
    reference_amplitudes: list[float] = []
    momenta: list[list[float]] = []

    for sample in samples:
        numerical = sample["numerical"]
        reference = sample["reference"]
        velocity = error_norms(numerical["velocity"], reference["velocity"], weights)
        position = periodic_position_error(
            numerical["position"], reference["position"], domain_length, weights
        )
        exact_displacement = subtract(reference["position"], initial_reference_position)
        displacement_scale = weighted_l2(exact_displacement, weights)
        position_relative_l2 = None if displacement_scale == 0.0 else position["l2"] / displacement_scale

        density_drift = [float(value) - rho0 for value in numerical["density"]]
        pressure = error_norms(numerical["pressure"], reference["pressure"], weights)
        transverse = [[0.0, float(value[1])] for value in numerical["velocity"]]
        transverse_leakage = weighted_l2(transverse, weights) / amplitude_scale
        basis = [math.sin(wave_number * float(position_value[1])) for position_value in reference["position"]]
        numerical_amplitude = least_squares_coefficient(
            [float(value[0]) for value in numerical["velocity"]], basis, weights
        )
        reference_amplitude = least_squares_coefficient(
            [float(value[0]) for value in reference["velocity"]], basis, weights
        )
        if numerical_amplitude is None or reference_amplitude is None:
            raise MetricContractError("shear modal basis is degenerate")
        numerical_amplitudes.append(numerical_amplitude)
        reference_amplitudes.append(reference_amplitude)
        momenta.append(_weighted_vector_mean(numerical["velocity"], weights))
        per_time.append(
            {
                "time": float(sample["time"]),
                "velocity_l2": velocity["l2"],
                "velocity_linf": velocity["linf"],
                "velocity_relative_l2": velocity["relative_l2"],
                "position_l2": position["l2"],
                "position_linf": position["linf"],
                "position_relative_l2": position_relative_l2,
                "density_drift_l2": weighted_l2(density_drift, weights),
                "density_drift_linf": max(abs(value) for value in density_drift),
                "pressure_l2": pressure["l2"],
                "pressure_linf": pressure["linf"],
                "transverse_leakage": transverse_leakage,
                "numerical_amplitude": numerical_amplitude,
                "reference_amplitude": reference_amplitude,
            }
        )

    times = [item["time"] for item in per_time]
    decay_rate = fitted_positive_decay_rate(times, numerical_amplitudes)
    reference_decay_rate = fitted_positive_decay_rate(times, reference_amplitudes)
    final = per_time[-1]
    if final["velocity_relative_l2"] is None or final["position_relative_l2"] is None:
        raise MetricContractError("final shear relative metrics require nonzero reference signals")
    momentum_initial = momenta[0]
    momentum_drift = max(
        math.hypot(value[0] - momentum_initial[0], value[1] - momentum_initial[1])
        for value in momenta
    )
    summary = {
        "all_finite": True,
        "velocity_relative_l2": final["velocity_relative_l2"],
        "velocity_linf": final["velocity_linf"],
        "position_relative_l2": final["position_relative_l2"],
        "position_linf": final["position_linf"],
        "decay_rate": decay_rate,
        "reference_decay_rate": reference_decay_rate,
        "decay_rate_relative_error": abs(decay_rate - exact_decay_rate) / exact_decay_rate,
        "amplitude_ratio": numerical_amplitudes[-1] / reference_amplitudes[-1],
        "density_drift_l2": max(item["density_drift_l2"] for item in per_time),
        "density_drift_linf": max(item["density_drift_linf"] for item in per_time),
        "pressure_l2": max(item["pressure_l2"] for item in per_time),
        "pressure_linf": max(item["pressure_linf"] for item in per_time),
        "transverse_leakage": max(item["transverse_leakage"] for item in per_time),
        "momentum_drift": momentum_drift,
        "viscous_power": evidence["diagnostics"].get("viscous_power"),
        "claim": metadata["claim"],
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "shear",
        "run_id": metadata["run_id"],
        "per_time": per_time,
        "summary": summary,
        "diagnostics": evidence["diagnostics"],
    }
    validate_evaluator_output(result, "shear")
    return result
