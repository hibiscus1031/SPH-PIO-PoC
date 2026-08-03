"""Immutable Stage 01G gate bindings.

Thresholds are bound to the frozen Stage 01G config SHA-256.  Callers cannot
provide replacement thresholds or adaptive overrides.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .common_metrics import MetricContractError, relative_change, strict_decrease
from .provenance import FROZEN_STAGE01G_CONFIG_SHA256, FROZEN_STAGE01G_METRICS_SHA256


SHEAR_RUN_IDS = (
    "g_shear_n24",
    "g_shear_n32",
    "g_shear_n48",
    "g_shear_n32_dt_half",
    "g_shear_n48_rep2",
)
ACOUSTIC_RUN_IDS = (
    "g_acoustic_e5e3_n24",
    "g_acoustic_e5e3_n32",
    "g_acoustic_e5e3_n48",
    "g_acoustic_e5e3_n32_dt_half",
    "g_acoustic_e5e3_n48_rep2",
    "g_acoustic_e2p5e3_n48",
    "g_acoustic_e1e2_n48",
)

THRESHOLDS = {
    "SHEAR2": 0.02,
    "SHEAR3": 0.02,
    "SHEAR4": 0.01,
    "SHEAR5": 5.0e-3,
    "SHEAR6": 1.0e-3,
    "SHEAR8": 0.10,
    "ACOUSTIC2": 0.02,
    "ACOUSTIC3": 0.05,
    "ACOUSTIC4": 0.05,
    "ACOUSTIC5": 0.10,
    "ACOUSTIC6": 1.0e-3,
    "ACOUSTIC8": 0.10,
}
HARD_SAFETY_LIMITS = {
    "pair_force_residual": ("<=", 1.0e-12),
    "normalized_internal_force_residual": ("<=", 1.0e-10),
    "force_assembly_defect": ("<=", 1.0e-10),
    "momentum_update_defect": ("<=", 1.0e-10),
    "viscous_power_positive_tolerance": ("<=", 1.0e-12),
    "structural_topology_defects": ("<=", 0.0),
    "minimum_separation_over_dx": (">=", 0.25),
    "current_rss_bytes": ("<", 2_000_000_000.0),
    "peak_rss_bytes": ("<", 4_000_000_000.0),
    "rss_q4_minus_q1_bytes": ("<=", 250_000_000.0),
    "rss_q4_over_q1": ("<=", 1.50),
    "step_time_q4_over_q1": ("<=", 1.30),
    "source_call_count": ("<=", 0.0),
}


def metric_binding() -> dict[str, Any]:
    """Return the authoritative evaluator binding; no caller overrides exist."""
    return {
        "binding_version": "stage01ge-metric-binding-v1",
        "authoritative_sources": {
            "stage01g_config_sha256": FROZEN_STAGE01G_CONFIG_SHA256,
            "stage01g_metric_contract_sha256": FROZEN_STAGE01G_METRICS_SHA256,
        },
        "normalization": {
            "field_norms": "particle-volume weighted",
            "velocity_vector": "combined components before L2/Linf",
            "periodic_position": "component-wise minimum image, side length 2",
            "position_relative_l2": "periodic position L2 divided by exact displacement L2; t=0 excluded",
            "shear_amplitude": "weighted least-squares projection onto sin(k_s*y_reference)",
            "acoustic_fundamental": "weighted spatial projection plus fixed temporal quadrature",
            "acoustic_signal_l2": "spatiotemporal error L2 divided by independent reference signal L2",
            "transverse_acoustic": "spatiotemporal transverse L2 divided by reference velocity-signal L2",
            "epsilon_denominator": False,
            "adaptive_threshold": False,
        },
        "shear": {
            "SHEAR1": {"requires": ["all_finite", "hard_safety_PASS"]},
            "SHEAR2": {"metric": "N48.velocity_relative_l2", "op": "<=", "threshold": THRESHOLDS["SHEAR2"]},
            "SHEAR3": {"metric": "N48.decay_rate_relative_error", "op": "<=", "threshold": THRESHOLDS["SHEAR3"]},
            "SHEAR4": {"metric": "N48.position_relative_l2", "op": "<=", "threshold": THRESHOLDS["SHEAR4"]},
            "SHEAR5": {"metric": "N48.density_drift_linf", "op": "<=", "threshold": THRESHOLDS["SHEAR5"]},
            "SHEAR6": {"metric": "N48.transverse_leakage", "op": "<=", "threshold": THRESHOLDS["SHEAR6"]},
            "SHEAR7": {"strict_order": ["velocity_relative_l2", "position_relative_l2"], "resolutions": [24, 32, 48]},
            "SHEAR8": {"dt_change_metrics": ["velocity_relative_l2", "position_relative_l2", "decay_rate_relative_error"], "op": "<=", "threshold": THRESHOLDS["SHEAR8"]},
        },
        "acoustic": {
            "ACOUSTIC1": {"requires": ["all_finite", "hard_safety_PASS"]},
            "ACOUSTIC2": {"metric": "main_N48.phase_speed_relative_error", "op": "<=", "threshold": THRESHOLDS["ACOUSTIC2"]},
            "ACOUSTIC3": {"metric": "main_N48.density_fundamental_amplitude_relative_error", "op": "<=", "threshold": THRESHOLDS["ACOUSTIC3"]},
            "ACOUSTIC4": {"metric": "main_N48.velocity_fundamental_amplitude_relative_error", "op": "<=", "threshold": THRESHOLDS["ACOUSTIC4"]},
            "ACOUSTIC5": {"metrics": ["main_N48.density_signal_normalized_l2", "main_N48.velocity_signal_normalized_l2"], "op": "<=", "threshold": THRESHOLDS["ACOUSTIC5"]},
            "ACOUSTIC6": {"metric": "main_N48.transverse_leakage", "op": "<=", "threshold": THRESHOLDS["ACOUSTIC6"]},
            "ACOUSTIC7": {"strict_order": ["density_fundamental_amplitude_relative_error", "velocity_fundamental_amplitude_relative_error", "one_period_phase_error"], "resolutions": [24, 32, 48]},
            "ACOUSTIC8": {"dt_change_metrics": ["phase_speed_relative_error", "density_fundamental_amplitude_relative_error", "velocity_fundamental_amplitude_relative_error", "density_signal_normalized_l2", "velocity_signal_normalized_l2"], "op": "<=", "threshold": THRESHOLDS["ACOUSTIC8"]},
            "ACOUSTIC9": {"metric": "second_harmonic_ratio", "epsilon_order": [0.01, 0.005, 0.0025], "rule": "non-increasing as epsilon decreases"},
            "ACOUSTIC10": {"claim": "linear-acoustic-regime_validation"},
        },
        "hard_safety": {name: list(rule) for name, rule in HARD_SAFETY_LIMITS.items()},
    }


def _comparison(value: float, operator: str, threshold: float) -> bool:
    if not math.isfinite(float(value)):
        return False
    if operator == "<=":
        return float(value) <= threshold
    if operator == ">=":
        return float(value) >= threshold
    if operator == "<":
        return float(value) < threshold
    raise MetricContractError(f"unsupported frozen comparator: {operator}")


def evaluate_hard_safety(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    evidence = diagnostics.get("hard_safety", {})
    checks: dict[str, bool] = {}
    for name, (operator, threshold) in HARD_SAFETY_LIMITS.items():
        checks[name] = name in evidence and _comparison(evidence[name], operator, threshold)
    process = diagnostics.get("resource", {})
    checks["independent_child_process"] = process.get("independent_child_process") is True
    checks["cyclic_gc_default"] = process.get("cyclic_gc_default") is True
    checks["torch_no_grad"] = process.get("torch_no_grad") is True
    checks["no_in_loop_gc_collect"] = process.get("in_loop_gc_collect") is False
    checks["parent_scalar_only"] = process.get("parent_scalar_only") is True
    checks["child_fully_reclaimed"] = process.get("child_fully_reclaimed") is True
    return {"checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def _require_runs(run_results: Mapping[str, Any], required: tuple[str, ...]) -> None:
    missing = [run_id for run_id in required if run_id not in run_results]
    extra = [run_id for run_id in run_results if run_id not in required]
    if missing or extra:
        raise MetricContractError(f"run evidence mismatch; missing={missing}, extra={extra}")


def _gate(passed: bool, evidence: Any) -> dict[str, Any]:
    return {"status": "PASS" if passed else "FAIL", "evidence": evidence}


def evaluate_shear_gates(run_results: Mapping[str, Any]) -> dict[str, Any]:
    _require_runs(run_results, SHEAR_RUN_IDS)
    summaries = {name: run_results[name]["summary"] for name in SHEAR_RUN_IDS}
    hard = {name: evaluate_hard_safety(run_results[name]["diagnostics"]) for name in SHEAR_RUN_IDS}
    n24, n32, n48 = (summaries[name] for name in ("g_shear_n24", "g_shear_n32", "g_shear_n48"))
    half = summaries["g_shear_n32_dt_half"]
    dt_metrics = ("velocity_relative_l2", "position_relative_l2", "decay_rate_relative_error")
    dt_changes = {name: relative_change(n32[name], half[name]) for name in dt_metrics}
    ordering = {
        name: [n24[name], n32[name], n48[name]]
        for name in ("velocity_relative_l2", "position_relative_l2")
    }
    gates = {
        "SHEAR1": _gate(all(summary["all_finite"] for summary in summaries.values()) and all(item["status"] == "PASS" for item in hard.values()), hard),
        "SHEAR2": _gate(n48["velocity_relative_l2"] <= THRESHOLDS["SHEAR2"], n48["velocity_relative_l2"]),
        "SHEAR3": _gate(n48["decay_rate_relative_error"] <= THRESHOLDS["SHEAR3"], n48["decay_rate_relative_error"]),
        "SHEAR4": _gate(n48["position_relative_l2"] <= THRESHOLDS["SHEAR4"], n48["position_relative_l2"]),
        "SHEAR5": _gate(n48["density_drift_linf"] <= THRESHOLDS["SHEAR5"], n48["density_drift_linf"]),
        "SHEAR6": _gate(n48["transverse_leakage"] <= THRESHOLDS["SHEAR6"], n48["transverse_leakage"]),
        "SHEAR7": _gate(all(strict_decrease(values) for values in ordering.values()), ordering),
        "SHEAR8": _gate(all(value <= THRESHOLDS["SHEAR8"] for value in dt_changes.values()), dt_changes),
    }
    return {"gates": gates, "status": "PASS" if all(item["status"] == "PASS" for item in gates.values()) else "FAIL"}


def evaluate_acoustic_gates(run_results: Mapping[str, Any]) -> dict[str, Any]:
    _require_runs(run_results, ACOUSTIC_RUN_IDS)
    summaries = {name: run_results[name]["summary"] for name in ACOUSTIC_RUN_IDS}
    hard = {name: evaluate_hard_safety(run_results[name]["diagnostics"]) for name in ACOUSTIC_RUN_IDS}
    n24, n32, n48 = (
        summaries[name]
        for name in ("g_acoustic_e5e3_n24", "g_acoustic_e5e3_n32", "g_acoustic_e5e3_n48")
    )
    half = summaries["g_acoustic_e5e3_n32_dt_half"]
    ordering_metrics = (
        "density_fundamental_amplitude_relative_error",
        "velocity_fundamental_amplitude_relative_error",
        "one_period_phase_error",
    )
    ordering = {name: [n24[name], n32[name], n48[name]] for name in ordering_metrics}
    dt_metrics = (
        "phase_speed_relative_error",
        "density_fundamental_amplitude_relative_error",
        "velocity_fundamental_amplitude_relative_error",
        "density_signal_normalized_l2",
        "velocity_signal_normalized_l2",
    )
    dt_changes = {name: relative_change(n32[name], half[name]) for name in dt_metrics}
    harmonic_by_epsilon = [
        summaries[run_id]["second_harmonic_ratio"]
        for run_id in ("g_acoustic_e1e2_n48", "g_acoustic_e5e3_n48", "g_acoustic_e2p5e3_n48")
    ]
    gates = {
        "ACOUSTIC1": _gate(all(summary["all_finite"] for summary in summaries.values()) and all(item["status"] == "PASS" for item in hard.values()), hard),
        "ACOUSTIC2": _gate(n48["phase_speed_relative_error"] <= THRESHOLDS["ACOUSTIC2"], n48["phase_speed_relative_error"]),
        "ACOUSTIC3": _gate(n48["density_fundamental_amplitude_relative_error"] <= THRESHOLDS["ACOUSTIC3"], n48["density_fundamental_amplitude_relative_error"]),
        "ACOUSTIC4": _gate(n48["velocity_fundamental_amplitude_relative_error"] <= THRESHOLDS["ACOUSTIC4"], n48["velocity_fundamental_amplitude_relative_error"]),
        "ACOUSTIC5": _gate(max(n48["density_signal_normalized_l2"], n48["velocity_signal_normalized_l2"]) <= THRESHOLDS["ACOUSTIC5"], {"density": n48["density_signal_normalized_l2"], "velocity": n48["velocity_signal_normalized_l2"]}),
        "ACOUSTIC6": _gate(n48["transverse_leakage"] <= THRESHOLDS["ACOUSTIC6"], n48["transverse_leakage"]),
        "ACOUSTIC7": _gate(all(strict_decrease(values) for values in ordering.values()), ordering),
        "ACOUSTIC8": _gate(all(value <= THRESHOLDS["ACOUSTIC8"] for value in dt_changes.values()), dt_changes),
        "ACOUSTIC9": _gate(all(right <= left for left, right in zip(harmonic_by_epsilon, harmonic_by_epsilon[1:])), harmonic_by_epsilon),
        "ACOUSTIC10": _gate(all(summary["claim"] == "linear-acoustic-regime_validation" for summary in summaries.values()), [summary["claim"] for summary in summaries.values()]),
    }
    return {"gates": gates, "status": "PASS" if all(item["status"] == "PASS" for item in gates.values()) else "FAIL"}
