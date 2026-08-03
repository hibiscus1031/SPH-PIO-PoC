"""Input/output schema validation without solver dependencies."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from .common_metrics import MetricContractError, all_finite
from .provenance import FROZEN_STAGE01G_CONFIG_SHA256


SCHEMA_VERSION = "stage01ge-evaluator-v1"
FIELD_NAMES = ("position", "velocity", "density", "pressure")
COMMON_METADATA = (
    "run_id",
    "benchmark",
    "N",
    "H_over_dx",
    "dt",
    "t_final",
    "domain_length",
    "rho0",
    "c_s",
    "config_sha256",
)
SHEAR_METADATA = ("nu", "U_s", "k_s", "claim")
ACOUSTIC_METADATA = ("nu", "epsilon", "k_a", "claim")


def _require(mapping: Mapping[str, Any], names: Sequence[str], context: str) -> None:
    missing = [name for name in names if name not in mapping]
    if missing:
        raise MetricContractError(f"{context} missing required fields: {missing}")


def _particle_count(field: Mapping[str, Any], context: str) -> int:
    _require(field, FIELD_NAMES, context)
    counts = []
    for name in FIELD_NAMES:
        values = field[name]
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise MetricContractError(f"{context}.{name} must be a sequence")
        counts.append(len(values))
    if len(set(counts)) != 1 or counts[0] <= 0:
        raise MetricContractError(f"{context} fields must share a positive particle count")
    for vector in field["position"]:
        if not isinstance(vector, Sequence) or len(vector) != 2:
            raise MetricContractError(f"{context}.position must contain 2D vectors")
    for vector in field["velocity"]:
        if not isinstance(vector, Sequence) or len(vector) != 2:
            raise MetricContractError(f"{context}.velocity must contain 2D vectors")
    if not all_finite(field):
        raise MetricContractError(f"{context} contains non-finite evidence")
    return counts[0]


def validate_dataset(dataset: Mapping[str, Any], benchmark: str) -> dict[str, Any]:
    """Validate and deep-copy evidence so evaluator code cannot mutate inputs."""
    if not isinstance(dataset, Mapping):
        raise MetricContractError("dataset must be a mapping")
    _require(dataset, ("metadata", "samples", "diagnostics"), "dataset")
    metadata = dataset["metadata"]
    if not isinstance(metadata, Mapping):
        raise MetricContractError("metadata must be a mapping")
    _require(metadata, COMMON_METADATA, "metadata")
    expected = SHEAR_METADATA if benchmark == "shear" else ACOUSTIC_METADATA
    _require(metadata, expected, "metadata")
    if metadata["benchmark"] != benchmark:
        raise MetricContractError("metadata benchmark does not match evaluator")
    if metadata["config_sha256"] != FROZEN_STAGE01G_CONFIG_SHA256:
        raise MetricContractError("metadata is not bound to the frozen Stage 01G config")
    if metadata["N"] <= 0 or metadata["dt"] <= 0.0 or metadata["domain_length"] <= 0.0:
        raise MetricContractError("N, dt, and domain length must be positive")

    samples = dataset["samples"]
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)) or len(samples) < 2:
        raise MetricContractError("samples must contain at least two common-time states")
    previous_time = None
    particle_count = None
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping):
            raise MetricContractError("each sample must be a mapping")
        _require(sample, ("time", "numerical", "reference"), f"sample[{index}]")
        time = float(sample["time"])
        if previous_time is not None and time <= previous_time:
            raise MetricContractError("sample times must be strictly increasing")
        previous_time = time
        numerical_count = _particle_count(sample["numerical"], f"sample[{index}].numerical")
        reference_count = _particle_count(sample["reference"], f"sample[{index}].reference")
        if numerical_count != reference_count:
            raise MetricContractError("numerical and reference particle counts differ")
        if particle_count is None:
            particle_count = numerical_count
        elif particle_count != numerical_count:
            raise MetricContractError("particle count changes between common-time samples")

    weights = dataset.get("weights")
    if weights is not None and len(weights) != particle_count:
        raise MetricContractError("weights are not particle-aligned")
    diagnostics = dataset["diagnostics"]
    _require(diagnostics, ("hard_safety", "topology", "resource", "determinism"), "diagnostics")
    if benchmark == "shear":
        _require(diagnostics, ("viscous_power",), "diagnostics")
        viscous_power = diagnostics["viscous_power"]
        if isinstance(viscous_power, bool) or not isinstance(viscous_power, (int, float)) or not math.isfinite(float(viscous_power)):
            raise MetricContractError("diagnostics.viscous_power must be a finite scalar")
    if not all_finite({"metadata": metadata, "samples": samples, "diagnostics": diagnostics}):
        raise MetricContractError("dataset contains non-finite evidence")
    return deepcopy(dict(dataset))


def validate_evaluator_output(result: Mapping[str, Any], benchmark: str) -> None:
    _require(result, ("schema_version", "benchmark", "run_id", "per_time", "summary", "diagnostics"), "result")
    if result["schema_version"] != SCHEMA_VERSION or result["benchmark"] != benchmark:
        raise MetricContractError("output schema version or benchmark is invalid")
    if not isinstance(result["per_time"], Sequence) or not result["per_time"]:
        raise MetricContractError("output per_time evidence is empty")
    if not all_finite(result):
        raise MetricContractError("output contains non-finite evidence")
