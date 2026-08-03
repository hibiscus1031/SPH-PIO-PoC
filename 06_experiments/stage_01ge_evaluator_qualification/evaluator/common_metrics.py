"""Dependency-light metric primitives for evaluator-only use.

This module consumes ordinary Python mappings and sequences.  It never imports
or calls the SPH solver, integrators, source adapters, or training code.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


class MetricContractError(ValueError):
    """Raised when supplied evidence cannot satisfy the frozen metric schema."""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def flatten(values: Sequence[object]) -> list[float]:
    """Flatten a scalar or vector sequence while rejecting non-numeric data."""
    output: list[float] = []
    for value in values:
        if _is_number(value):
            output.append(float(value))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if not value:
                raise MetricContractError("empty vector is not a metric value")
            for component in value:
                if not _is_number(component):
                    raise MetricContractError("metric vectors must be numeric")
                output.append(float(component))
        else:
            raise MetricContractError("metric values must be scalar or vector sequences")
    return output


def all_finite(value: object) -> bool:
    if _is_number(value):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return all(all_finite(item) for item in value)
    return True


def normalized_weights(count: int, weights: Sequence[float] | None = None) -> list[float]:
    if count <= 0:
        raise MetricContractError("at least one particle is required")
    raw = [1.0] * count if weights is None else [float(value) for value in weights]
    if len(raw) != count or not all(math.isfinite(value) and value > 0.0 for value in raw):
        raise MetricContractError("weights must be finite, positive, and particle-aligned")
    total = math.fsum(raw)
    return [value / total for value in raw]


def _particle_squared_magnitudes(values: Sequence[object]) -> list[float]:
    squared: list[float] = []
    for value in values:
        components = [float(value)] if _is_number(value) else flatten([value])
        squared.append(math.fsum(component * component for component in components))
    return squared


def weighted_l2(values: Sequence[object], weights: Sequence[float] | None = None) -> float:
    norm_weights = normalized_weights(len(values), weights)
    squared = _particle_squared_magnitudes(values)
    return math.sqrt(math.fsum(weight * value for weight, value in zip(norm_weights, squared)))


def linf(values: Sequence[object]) -> float:
    squared = _particle_squared_magnitudes(values)
    return math.sqrt(max(squared))


def subtract(left: Sequence[object], right: Sequence[object]) -> list[object]:
    if len(left) != len(right):
        raise MetricContractError("metric arrays have different particle counts")
    differences: list[object] = []
    for lhs, rhs in zip(left, right):
        if _is_number(lhs) and _is_number(rhs):
            differences.append(float(lhs) - float(rhs))
            continue
        lhs_vector = flatten([lhs])
        rhs_vector = flatten([rhs])
        if len(lhs_vector) != len(rhs_vector):
            raise MetricContractError("metric vectors have different dimensions")
        differences.append([a - b for a, b in zip(lhs_vector, rhs_vector)])
    return differences


def error_norms(
    numerical: Sequence[object],
    reference: Sequence[object],
    weights: Sequence[float] | None = None,
) -> dict[str, float | None]:
    error = subtract(numerical, reference)
    absolute_l2 = weighted_l2(error, weights)
    denominator = weighted_l2(reference, weights)
    return {
        "l2": absolute_l2,
        "linf": linf(error),
        "relative_l2": None if denominator == 0.0 else absolute_l2 / denominator,
        "reference_l2": denominator,
    }


def periodic_position_error(
    numerical: Sequence[Sequence[float]],
    reference: Sequence[Sequence[float]],
    domain_length: float,
    weights: Sequence[float] | None = None,
) -> dict[str, float]:
    if not math.isfinite(domain_length) or domain_length <= 0.0:
        raise MetricContractError("domain length must be positive and finite")
    raw = subtract(numerical, reference)
    wrapped = [
        [component - domain_length * math.floor(component / domain_length + 0.5) for component in vector]
        for vector in raw
    ]
    return {"l2": weighted_l2(wrapped, weights), "linf": linf(wrapped)}


def least_squares_coefficient(
    signal: Sequence[float], basis: Sequence[float], weights: Sequence[float] | None = None
) -> float | None:
    if len(signal) != len(basis):
        raise MetricContractError("signal and basis lengths differ")
    norm_weights = normalized_weights(len(signal), weights)
    numerator = math.fsum(w * float(y) * float(x) for w, y, x in zip(norm_weights, signal, basis))
    denominator = math.fsum(w * float(x) ** 2 for w, x in zip(norm_weights, basis))
    return None if denominator == 0.0 else numerator / denominator


def linear_fit(x_values: Sequence[float], y_values: Sequence[float]) -> tuple[float, float]:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise MetricContractError("linear fit requires at least two aligned points")
    x_mean = math.fsum(float(value) for value in x_values) / len(x_values)
    y_mean = math.fsum(float(value) for value in y_values) / len(y_values)
    denominator = math.fsum((float(value) - x_mean) ** 2 for value in x_values)
    if denominator == 0.0:
        raise MetricContractError("linear-fit abscissae are degenerate")
    slope = math.fsum(
        (float(x) - x_mean) * (float(y) - y_mean) for x, y in zip(x_values, y_values)
    ) / denominator
    return slope, y_mean - slope * x_mean


def fitted_positive_decay_rate(times: Sequence[float], amplitudes: Sequence[float]) -> float:
    selected = [(float(t), abs(float(a))) for t, a in zip(times, amplitudes) if abs(float(a)) > 0.0]
    if len(selected) < 2:
        raise MetricContractError("decay fit requires two positive-amplitude samples")
    slope, _ = linear_fit([item[0] for item in selected], [math.log(item[1]) for item in selected])
    return -slope


def unwrap_phases(phases: Sequence[float]) -> list[float]:
    if not phases:
        raise MetricContractError("phase sequence is empty")
    result = [float(phases[0])]
    for phase in phases[1:]:
        candidate = float(phase)
        while candidate - result[-1] > math.pi:
            candidate -= 2.0 * math.pi
        while candidate - result[-1] <= -math.pi:
            candidate += 2.0 * math.pi
        result.append(candidate)
    return result


def wrapped_phase_error(value: float, reference: float) -> float:
    difference = float(value) - float(reference)
    return abs((difference + math.pi) % (2.0 * math.pi) - math.pi)


def harmonic_amplitude(
    times: Sequence[float], values: Sequence[float], angular_frequency: float
) -> float:
    if len(times) != len(values) or len(times) < 2:
        raise MetricContractError("harmonic amplitude requires aligned time samples")
    cosine = [math.cos(angular_frequency * float(time)) for time in times]
    sine = [math.sin(angular_frequency * float(time)) for time in times]
    cc = math.fsum(value * value for value in cosine)
    ss = math.fsum(value * value for value in sine)
    cs = math.fsum(a * b for a, b in zip(cosine, sine))
    yc = math.fsum(float(y) * x for y, x in zip(values, cosine))
    ys = math.fsum(float(y) * x for y, x in zip(values, sine))
    determinant = cc * ss - cs * cs
    if determinant <= 0.0:
        raise MetricContractError("temporal quadrature basis is singular")
    cosine_coefficient = (yc * ss - ys * cs) / determinant
    sine_coefficient = (ys * cc - yc * cs) / determinant
    return math.hypot(cosine_coefficient, sine_coefficient)


def concatenate_particle_series(samples: Iterable[Sequence[object]]) -> list[object]:
    output: list[object] = []
    for sample in samples:
        output.extend(sample)
    if not output:
        raise MetricContractError("spatiotemporal metric has no samples")
    return output


def relative_change(value: float, reference: float) -> float:
    value = float(value)
    reference = float(reference)
    if reference == 0.0:
        return 0.0 if value == 0.0 else math.inf
    return abs(value - reference) / abs(reference)


def strict_decrease(values: Sequence[float]) -> bool:
    return all(float(left) > float(right) for left, right in zip(values, values[1:]))
