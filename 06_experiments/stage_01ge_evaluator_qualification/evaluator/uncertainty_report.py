"""Component-wise uncertainty assembly; deliberately no synthetic total GCI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .common_metrics import relative_change


def build_uncertainty_report(
    shear_runs: Mapping[str, Any], acoustic_runs: Mapping[str, Any]
) -> dict[str, Any]:
    components: dict[str, Any] = {
        "analytic_or_linear_reference": {
            "status": "REPORTED",
            "shear": "analytic continuum field and unwrapped trajectory",
            "acoustic": "independent linear theory; finite-amplitude departure separate",
        },
        "rk2_time_step": {
            "status": "REPORTED" if "g_shear_n32" in shear_runs and "g_shear_n32_dt_half" in shear_runs and "g_acoustic_e5e3_n32" in acoustic_runs and "g_acoustic_e5e3_n32_dt_half" in acoustic_runs else "MISSING",
        },
        "increasing_neighbor_spatial_envelope": {
            "status": "REPORTED" if all(name in shear_runs for name in ("g_shear_n24", "g_shear_n32", "g_shear_n48")) and all(name in acoustic_runs for name in ("g_acoustic_e5e3_n24", "g_acoustic_e5e3_n32", "g_acoustic_e5e3_n48")) else "MISSING",
        },
        "n48_n32_difference": {"status": "MISSING"},
        "float64_determinism": {
            "status": "REPORTED" if "g_shear_n48_rep2" in shear_runs and "g_acoustic_e5e3_n48_rep2" in acoustic_runs else "MISSING",
        },
        "acoustic_finite_amplitude_model_form": {
            "status": "REPORTED" if all(name in acoustic_runs for name in ("g_acoustic_e1e2_n48", "g_acoustic_e5e3_n48", "g_acoustic_e2p5e3_n48")) else "MISSING",
        },
        "kernel_density_eos_background": {"status": "MISSING"},
        "topology_and_resource": {"status": "MISSING"},
        "stage01f5b_gci_not_justified_limitation": {
            "status": "REPORTED",
            "statement": "GCI not justified; no single total GCI is generated",
        },
    }
    if components["rk2_time_step"]["status"] == "REPORTED":
        components["rk2_time_step"]["shear_velocity_relative_change"] = relative_change(
            shear_runs["g_shear_n32"]["summary"]["velocity_relative_l2"],
            shear_runs["g_shear_n32_dt_half"]["summary"]["velocity_relative_l2"],
        )
        components["rk2_time_step"]["acoustic_density_relative_change"] = relative_change(
            acoustic_runs["g_acoustic_e5e3_n32"]["summary"]["density_signal_normalized_l2"],
            acoustic_runs["g_acoustic_e5e3_n32_dt_half"]["summary"]["density_signal_normalized_l2"],
        )
    if "g_shear_n32" in shear_runs and "g_shear_n48" in shear_runs and "g_acoustic_e5e3_n32" in acoustic_runs and "g_acoustic_e5e3_n48" in acoustic_runs:
        components["n48_n32_difference"] = {
            "status": "REPORTED",
            "shear_velocity": abs(shear_runs["g_shear_n48"]["summary"]["velocity_relative_l2"] - shear_runs["g_shear_n32"]["summary"]["velocity_relative_l2"]),
            "acoustic_density": abs(acoustic_runs["g_acoustic_e5e3_n48"]["summary"]["density_signal_normalized_l2"] - acoustic_runs["g_acoustic_e5e3_n32"]["summary"]["density_signal_normalized_l2"]),
        }
    background_available = "g_shear_n48" in shear_runs and "g_acoustic_e5e3_n48" in acoustic_runs
    if background_available:
        components["kernel_density_eos_background"] = {
            "status": "REPORTED",
            "shear_density_drift_linf": shear_runs["g_shear_n48"]["summary"]["density_drift_linf"],
            "acoustic_density_bias": acoustic_runs["g_acoustic_e5e3_n48"]["summary"]["density_bias"],
            "acoustic_pressure_bias": acoustic_runs["g_acoustic_e5e3_n48"]["summary"]["pressure_bias"],
        }
    all_runs = list(shear_runs.values()) + list(acoustic_runs.values())
    if all_runs:
        components["topology_and_resource"] = {
            "status": "REPORTED",
            "run_count": len(all_runs),
            "diagnostics_present": all("diagnostics" in item for item in all_runs),
        }
    complete = all(component["status"] == "REPORTED" for component in components.values())
    return {
        "components": components,
        "complete": complete,
        "single_total_gci": None,
        "gci_statement": "GCI not justified",
    }
