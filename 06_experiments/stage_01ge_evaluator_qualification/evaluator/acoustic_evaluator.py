"""Read-only evaluator for the frozen linear-acoustic standing wave."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .common_metrics import (
    MetricContractError,
    error_norms,
    harmonic_amplitude,
    least_squares_coefficient,
    linear_fit,
    normalized_weights,
    unwrap_phases,
    weighted_l2,
    wrapped_phase_error,
)
from .schema import SCHEMA_VERSION, validate_dataset, validate_evaluator_output


def _coefficient(signal: list[float], basis: list[float], weights: list[float] | None) -> float:
    value = least_squares_coefficient(signal, basis, weights)
    if value is None:
        raise MetricContractError("acoustic modal basis is degenerate")
    return value


def _weighted_bias(values: list[float], reference: list[float], weights: list[float] | None) -> float:
    norm_weights = normalized_weights(len(values), weights)
    return math.fsum(
        weight * (float(value) - float(exact))
        for weight, value, exact in zip(norm_weights, values, reference)
    )


def _weighted_vector_mean(vectors: list[list[float]], weights: list[float] | None) -> list[float]:
    norm_weights = normalized_weights(len(vectors), weights)
    return [
        math.fsum(weight * float(vector[component]) for weight, vector in zip(norm_weights, vectors))
        for component in range(2)
    ]


def _global_signal_error(
    numerical_samples: list[list[Any]],
    reference_samples: list[list[Any]],
    weights: list[float] | None,
    reference_background: float | None = None,
) -> float:
    numerator_squared = 0.0
    denominator_squared = 0.0
    norm_weights = normalized_weights(len(numerical_samples[0]), weights)
    for numerical, reference in zip(numerical_samples, reference_samples):
        errors = error_norms(numerical, reference, weights)
        numerator_squared += float(errors["l2"]) ** 2
        if reference_background is None:
            signal = reference
        else:
            signal = [float(value) - reference_background for value in reference]
        denominator_squared += weighted_l2(signal, weights) ** 2
    del norm_weights  # weights are validated above and applied by the norm helpers.
    if denominator_squared == 0.0:
        raise MetricContractError("spatiotemporal reference signal is zero")
    return math.sqrt(numerator_squared / denominator_squared)


def evaluate_acoustic(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate supplied numerical/reference samples; never generate reference data."""
    evidence = validate_dataset(dataset, "acoustic")
    metadata = evidence["metadata"]
    samples = evidence["samples"]
    weights = evidence.get("weights")
    rho0 = float(metadata["rho0"])
    sound_speed = float(metadata["c_s"])
    wave_number = float(metadata["k_a"])
    angular_frequency = sound_speed * wave_number

    per_time: list[dict[str, Any]] = []
    density_coefficients: list[float] = []
    velocity_coefficients: list[float] = []
    reference_density_coefficients: list[float] = []
    reference_velocity_coefficients: list[float] = []
    density_biases: list[float] = []
    pressure_biases: list[float] = []
    transverse_numerical: list[list[Any]] = []
    velocity_reference_series: list[list[Any]] = []
    momenta: list[list[float]] = []

    for sample in samples:
        numerical = sample["numerical"]
        reference = sample["reference"]
        x_coordinates = [float(value[0]) for value in reference["position"]]
        density_basis = [math.cos(wave_number * value) for value in x_coordinates]
        velocity_basis = [math.sin(wave_number * value) for value in x_coordinates]
        density_second_basis = [math.cos(2.0 * wave_number * value) for value in x_coordinates]
        velocity_second_basis = [math.sin(2.0 * wave_number * value) for value in x_coordinates]
        numerical_density_signal = [float(value) - rho0 for value in numerical["density"]]
        reference_density_signal = [float(value) - rho0 for value in reference["density"]]
        numerical_velocity_x = [float(value[0]) for value in numerical["velocity"]]
        reference_velocity_x = [float(value[0]) for value in reference["velocity"]]
        numerical_density_coefficient = _coefficient(numerical_density_signal, density_basis, weights)
        numerical_velocity_coefficient = _coefficient(numerical_velocity_x, velocity_basis, weights)
        reference_density_coefficient = _coefficient(reference_density_signal, density_basis, weights)
        reference_velocity_coefficient = _coefficient(reference_velocity_x, velocity_basis, weights)
        density_second = _coefficient(numerical_density_signal, density_second_basis, weights)
        velocity_second = _coefficient(numerical_velocity_x, velocity_second_basis, weights)
        fundamental_magnitude = math.hypot(
            numerical_density_coefficient / rho0,
            numerical_velocity_coefficient / sound_speed,
        )
        second_magnitude = math.hypot(density_second / rho0, velocity_second / sound_speed)
        harmonic_ratio = None if fundamental_magnitude == 0.0 else second_magnitude / fundamental_magnitude
        density_error = error_norms(numerical["density"], reference["density"], weights)
        velocity_error = error_norms(numerical["velocity"], reference["velocity"], weights)
        pressure_error = error_norms(numerical["pressure"], reference["pressure"], weights)

        density_coefficients.append(numerical_density_coefficient)
        velocity_coefficients.append(numerical_velocity_coefficient)
        reference_density_coefficients.append(reference_density_coefficient)
        reference_velocity_coefficients.append(reference_velocity_coefficient)
        density_biases.append(_weighted_bias(numerical["density"], reference["density"], weights))
        pressure_biases.append(_weighted_bias(numerical["pressure"], reference["pressure"], weights))
        transverse_numerical.append([[0.0, float(value[1])] for value in numerical["velocity"]])
        velocity_reference_series.append(reference["velocity"])
        momenta.append(_weighted_vector_mean(numerical["velocity"], weights))
        per_time.append(
            {
                "time": float(sample["time"]),
                "density_l2": density_error["l2"],
                "density_linf": density_error["linf"],
                "velocity_l2": velocity_error["l2"],
                "velocity_linf": velocity_error["linf"],
                "pressure_l2": pressure_error["l2"],
                "pressure_linf": pressure_error["linf"],
                "density_fundamental": numerical_density_coefficient,
                "velocity_fundamental": numerical_velocity_coefficient,
                "density_second_harmonic": density_second,
                "velocity_second_harmonic": velocity_second,
                "second_harmonic_ratio": harmonic_ratio,
            }
        )

    times = [item["time"] for item in per_time]
    phases = unwrap_phases(
        [
            math.atan2(velocity / sound_speed, density / rho0)
            for density, velocity in zip(density_coefficients, velocity_coefficients)
        ]
    )
    reference_phases = unwrap_phases(
        [
            math.atan2(velocity / sound_speed, density / rho0)
            for density, velocity in zip(reference_density_coefficients, reference_velocity_coefficients)
        ]
    )
    phase_slope, _ = linear_fit(times, phases)
    reference_phase_slope, _ = linear_fit(times, reference_phases)
    phase_speed = phase_slope / wave_number
    reference_phase_speed = reference_phase_slope / wave_number
    density_amplitude = harmonic_amplitude(times, density_coefficients, angular_frequency) / rho0
    reference_density_amplitude = harmonic_amplitude(
        times, reference_density_coefficients, angular_frequency
    ) / rho0
    velocity_amplitude = harmonic_amplitude(times, velocity_coefficients, angular_frequency) / sound_speed
    reference_velocity_amplitude = harmonic_amplitude(
        times, reference_velocity_coefficients, angular_frequency
    ) / sound_speed
    density_signal_error = _global_signal_error(
        [sample["numerical"]["density"] for sample in samples],
        [sample["reference"]["density"] for sample in samples],
        weights,
        reference_background=rho0,
    )
    velocity_signal_error = _global_signal_error(
        [sample["numerical"]["velocity"] for sample in samples],
        [sample["reference"]["velocity"] for sample in samples],
        weights,
    )
    pressure_signal_error = _global_signal_error(
        [sample["numerical"]["pressure"] for sample in samples],
        [sample["reference"]["pressure"] for sample in samples],
        weights,
    )
    transverse_energy = math.fsum(weighted_l2(value, weights) ** 2 for value in transverse_numerical)
    reference_velocity_energy = math.fsum(
        weighted_l2(value, weights) ** 2 for value in velocity_reference_series
    )
    if reference_velocity_energy == 0.0:
        raise MetricContractError("acoustic transverse leakage has zero reference signal")
    harmonic_ratios = [
        item["second_harmonic_ratio"]
        for item in per_time
        if item["second_harmonic_ratio"] is not None
    ]
    if not harmonic_ratios:
        raise MetricContractError("acoustic harmonic ratio has no nonzero fundamental")
    initial_momentum = momenta[0]
    mean_momentum_drift = max(
        math.hypot(value[0] - initial_momentum[0], value[1] - initial_momentum[1])
        for value in momenta
    )
    summary = {
        "all_finite": True,
        "density_fundamental_amplitude": density_amplitude,
        "reference_density_fundamental_amplitude": reference_density_amplitude,
        "density_fundamental_amplitude_relative_error": abs(
            density_amplitude - reference_density_amplitude
        ) / reference_density_amplitude,
        "velocity_fundamental_amplitude": velocity_amplitude,
        "reference_velocity_fundamental_amplitude": reference_velocity_amplitude,
        "velocity_fundamental_amplitude_relative_error": abs(
            velocity_amplitude - reference_velocity_amplitude
        ) / reference_velocity_amplitude,
        "phase_speed": phase_speed,
        "reference_phase_speed": reference_phase_speed,
        "phase_speed_relative_error": abs(phase_speed - reference_phase_speed) / abs(reference_phase_speed),
        "one_period_phase_error": wrapped_phase_error(phases[-1], reference_phases[-1]) / (2.0 * math.pi),
        "density_signal_normalized_l2": density_signal_error,
        "velocity_signal_normalized_l2": velocity_signal_error,
        "pressure_signal_normalized_l2": pressure_signal_error,
        "pressure_linf": max(item["pressure_linf"] for item in per_time),
        "second_harmonic_ratio": max(harmonic_ratios),
        "transverse_leakage": math.sqrt(transverse_energy / reference_velocity_energy),
        "density_bias": max(abs(value) for value in density_biases),
        "pressure_bias": max(abs(value) for value in pressure_biases),
        "mean_momentum_drift": mean_momentum_drift,
        "claim": metadata["claim"],
        "epsilon": float(metadata["epsilon"]),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "acoustic",
        "run_id": metadata["run_id"],
        "per_time": per_time,
        "summary": summary,
        "diagnostics": evidence["diagnostics"],
    }
    validate_evaluator_output(result, "acoustic")
    return result
