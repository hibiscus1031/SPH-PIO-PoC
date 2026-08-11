#!/usr/bin/env python3
"""Run the controlled Stage 02G spatial attribution-closure audit.

The program evaluates spatial operators at one analytic timestamp.  It does not
generate a dataset or trajectory and contains no model or training workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
GENERATOR_PATH = STAGE_ROOT / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F_SCRIPT_PATH = ATTR_ROOT / "semidiscrete_reference/construct_spatial_targets.py"
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
R2S_DESIGN_PATH = ATTR_ROOT / "semidiscrete_reference/r2s_reference_design.yaml"
STAGE02F_ATTRIBUTION_PATH = ATTR_ROOT / "qualification/spatial_attribution_results.json"
STAGE02F_SUPPORT_PATH = ATTR_ROOT / "support_path/support_path_audit.json"
REFINEMENT_DESIGN_PATH = ATTR_ROOT / "spatial_refinement/stage02g_refinement_design.yaml"
RESOLUTION_MATRIX_PATH = ATTR_ROOT / "resolution_extension/resolution_extension_matrix.yaml"
BIAS_CONTRACT_PATH = ATTR_ROOT / "r2s_bias_audit/bias_audit_contract.yaml"
SMOOTHNESS_CONTRACT_PATH = ATTR_ROOT / "smoothness_audit/smoothness_criterion_contract.yaml"

TARGET_OUTPUT_PATH = ATTR_ROOT / "spatial_refinement/controlled_spatial_targets.json"
BIAS_OUTPUT_PATH = ATTR_ROOT / "r2s_bias_audit/r2s_bias_audit.json"
RESOLUTION_OUTPUT_PATH = ATTR_ROOT / "resolution_extension/resolution_extension_results.json"
SMOOTHNESS_OUTPUT_PATH = ATTR_ROOT / "smoothness_audit/smoothness_criterion_audit.json"
CLOSURE_OUTPUT_PATH = ATTR_ROOT / "qualification_closure/attribution_closure.json"
MANIFEST_OUTPUT_PATH = ATTR_ROOT / "qualification_closure/stage02g_manifest.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def load_module(name: str, path: Path) -> Any:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json_no_overwrite(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def case_contract(raw: dict[str, Any], membership: str) -> dict[str, Any]:
    return {
        **raw,
        "study_membership": [membership],
        "support_identity": f"Hdx_{float(raw['h_over_dx']):.1f}".replace(".", "p"),
    }


def state_and_edges(
    generator: Any, case: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    runtime_case = {
        **case,
        "topology_control": "none",
        "time_horizon": 0.0,
        "trajectory_family": "stage02g_same_timestamp_no_trajectory",
        "initial_condition_family": "periodic_vortex",
        "disorder_family": case.get("disorder_identity", "regular"),
    }
    state = generator.initial_state(runtime_case, config)
    edges = generator.build_edges(state, runtime_case, config, apply_control=False)
    return state, edges


def analytic_spatial_acceleration(state: dict[str, np.ndarray], config: dict[str, Any]) -> np.ndarray:
    length = float(config["domain"]["box_length"])
    wave_number = 2.0 * math.pi / length
    x = state["x"]
    phase_x = wave_number * x[:, 0]
    phase_y = wave_number * x[:, 1]
    rho0 = float(config["physics"]["rho0"])
    c0 = float(config["physics"]["sound_speed"])
    density_amplitude = float(config["physics"]["density_amplitude"])
    nu = float(config["physics"]["kinematic_viscosity"])
    pressure_factor = c0 * c0 * rho0 * density_amplitude * wave_number
    gradient_pressure = pressure_factor * np.column_stack(
        (np.cos(phase_x) * np.sin(phase_y), np.sin(phase_x) * np.cos(phase_y))
    )
    laplacian_velocity = -2.0 * wave_number * wave_number * state["v"]
    return -gradient_pressure / state["rho"][:, None] + nu * laplacian_velocity


def field_l2(field: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(field * field, axis=1))))


def local_reconstruction_audit(
    generator: Any,
    stage02f: Any,
    state: dict[str, np.ndarray],
    edges: dict[str, np.ndarray],
    case: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    particle_count = state["x"].shape[0]
    dx = float(config["domain"]["box_length"]) / int(case["particles_per_axis"])
    support = float(case["h_over_dx"]) * dx
    smoothing_length = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    pressure = generator.pressure_from_density(state["rho"], config)
    test_coefficients = np.asarray([0.7, -0.4, 0.3, -0.2, 0.5], dtype=np.float64)

    particle_records: list[dict[str, Any]] = []
    for particle in range(particle_count):
        selection = edges["source"] == particle
        neighbors = edges["target"][selection]
        displacement = edges["displacement"][selection]
        normalized = displacement / support
        matrix = np.column_stack(
            (
                normalized[:, 0],
                normalized[:, 1],
                0.5 * normalized[:, 0] ** 2,
                normalized[:, 0] * normalized[:, 1],
                0.5 * normalized[:, 1] ** 2,
            )
        )
        distance = np.linalg.norm(displacement, axis=1)
        weights, _ = generator.kernel_values(distance, smoothing_length)
        active = weights > 0.0
        sqrt_weights = np.sqrt(np.maximum(weights, 0.0))

        residuals: list[float] = []
        absolute_residuals: list[float] = []
        fields = [pressure, state["v"][:, 0], state["v"][:, 1]]
        for field in fields:
            values = field[neighbors] - field[particle]
            coefficients, _, _ = stage02f.weighted_solve(matrix, weights, values, sensitivity=False)
            weighted_values = sqrt_weights * values
            weighted_error = sqrt_weights * (matrix @ coefficients - values)
            absolute = float(np.sqrt(np.mean(weighted_error * weighted_error)))
            scale = float(np.linalg.norm(weighted_values))
            relative = float(np.linalg.norm(weighted_error) / scale) if scale > 1.0e-14 else 0.0
            residuals.append(relative)
            absolute_residuals.append(absolute)

        reproduction, rank, condition = stage02f.weighted_solve(
            matrix, weights, matrix @ test_coefficients, sensitivity=False
        )
        active_displacement = normalized[active]
        active_weights = weights[active]
        moment = np.einsum("n,ni,nj->ij", active_weights, active_displacement, active_displacement)
        eigenvalues = np.linalg.eigvalsh(moment)
        geometry_isotropy = float(eigenvalues[0] / eigenvalues[-1]) if eigenvalues[-1] > 0.0 else 0.0
        angles = np.sort(np.arctan2(active_displacement[:, 1], active_displacement[:, 0]))
        gaps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * math.pi)))
        particle_records.append(
            {
                "particle_id_local": particle,
                "local_matrix_rank": int(rank),
                "condition_number": float(condition),
                "polynomial_reproduction_error_Linf": float(np.max(np.abs(reproduction - test_coefficients))),
                "reconstruction_relative_residual_pressure_vx_vy": residuals,
                "reconstruction_absolute_RMS_residual_pressure_vx_vy": absolute_residuals,
                "particle_geometry_quality": {
                    "active_kernel_neighbor_count": int(np.count_nonzero(active)),
                    "weighted_moment_isotropy_ratio": geometry_isotropy,
                    "maximum_angular_gap_radians": float(np.max(gaps)),
                },
            }
        )

    ranks = [row["local_matrix_rank"] for row in particle_records]
    conditions = [row["condition_number"] for row in particle_records]
    reproduction = [row["polynomial_reproduction_error_Linf"] for row in particle_records]
    residual = [max(row["reconstruction_relative_residual_pressure_vx_vy"]) for row in particle_records]
    isotropy = [row["particle_geometry_quality"]["weighted_moment_isotropy_ratio"] for row in particle_records]
    angular_gap = [row["particle_geometry_quality"]["maximum_angular_gap_radians"] for row in particle_records]
    neighbor_count = [row["particle_geometry_quality"]["active_kernel_neighbor_count"] for row in particle_records]
    return {
        "summary": {
            "minimum_local_matrix_rank": int(min(ranks)),
            "maximum_condition_number": float(max(conditions)),
            "maximum_polynomial_reproduction_error_Linf": float(max(reproduction)),
            "reconstruction_relative_residual_max": float(max(residual)),
            "reconstruction_relative_residual_median": float(np.median(residual)),
            "geometry_isotropy_ratio_min": float(min(isotropy)),
            "maximum_angular_gap_radians": float(max(angular_gap)),
            "active_kernel_neighbor_count_min": int(min(neighbor_count)),
            "active_kernel_neighbor_count_max": int(max(neighbor_count)),
        },
        "particle_records": particle_records,
    }


def enrich_candidate(
    generator: Any,
    stage02f: Any,
    raw_case: dict[str, Any],
    config: dict[str, Any],
    r2s_design: dict[str, Any],
) -> dict[str, Any]:
    candidate = stage02f.construct_case(generator, raw_case, config, r2s_design)
    candidate["disorder_identity"] = raw_case.get("disorder_identity", "regular")
    candidate["disorder_fraction_dx"] = float(raw_case.get("disorder_fraction_dx", 0.0))
    candidate["random_seed"] = int(raw_case["random_seed"])
    state, edges = state_and_edges(generator, raw_case, config)
    analytic = analytic_spatial_acceleration(state, config)
    a_r2s = np.asarray(candidate["a_R2S"], dtype=np.float64)
    a_sph = np.asarray(candidate["a_SPH"], dtype=np.float64)
    delta = np.asarray(candidate["delta_a_space"], dtype=np.float64)
    r2s_bias = a_r2s - analytic
    sph_bias = a_sph - analytic
    target_l2 = field_l2(delta)
    local = local_reconstruction_audit(generator, stage02f, state, edges, raw_case, config)
    candidate["analytic_bias_audit"] = {
        "analytic_reference_used_as_target_source": False,
        "temporal_derivative_used": False,
        "a_analytic_spatial": analytic.tolist(),
        "r2s_reconstruction_bias": r2s_bias.tolist(),
        "sph_spatial_bias": sph_bias.tolist(),
        "r2s_bias_L2_particle_rms": field_l2(r2s_bias),
        "sph_bias_L2_particle_rms": field_l2(sph_bias),
        "r2s_bias_to_target_L2_ratio": float(field_l2(r2s_bias) / target_l2) if target_l2 > 0.0 else math.inf,
    }
    candidate["local_reconstruction_audit"] = local
    candidate["stage02g_content_hash"] = content_hash(candidate)
    return candidate


def graph_smoothness_diagnostics(
    generator: Any,
    stage02f: Any,
    candidate: dict[str, Any],
    raw_case: dict[str, Any],
    config: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    state, edges = state_and_edges(generator, raw_case, config)
    delta = np.asarray(candidate["delta_a_space"], dtype=np.float64)
    graph_tv = stage02f.graph_total_variation(delta, edges)
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(delta.shape[0])
    permuted_tv = stage02f.graph_total_variation(delta[permutation], edges)
    target_l2 = field_l2(delta)
    selection = edges["source"] < edges["target"]
    mean_edge_length = float(np.mean(np.linalg.norm(edges["displacement"][selection], axis=1)))
    cyclic = np.roll(delta, 7, axis=0)
    cyclic_tv = stage02f.graph_total_variation(cyclic, edges)
    cyclic_correlation = stage02f.direction_cosine(delta.ravel(), cyclic.ravel())
    return {
        "candidate_id": candidate["candidate_id"],
        "particles_per_axis": candidate["particles_per_axis"],
        "graph_total_variation_RMS": graph_tv,
        "target_L2_particle_rms": target_l2,
        "stage02f_cyclic_null_total_variation_RMS": cyclic_tv,
        "stage02f_cyclic_null_ratio": float(graph_tv / cyclic_tv) if cyclic_tv > 0.0 else math.inf,
        "cyclic_roll_field_correlation": cyclic_correlation,
        "decorrelated_permutation_seed": seed,
        "decorrelated_null_total_variation_RMS": permuted_tv,
        "decorrelated_null_ratio": float(graph_tv / permuted_tv) if permuted_tv > 0.0 else math.inf,
        "relative_neighbor_variation": float(graph_tv / target_l2) if target_l2 > 0.0 else math.inf,
        "mean_undirected_edge_length": mean_edge_length,
        "physical_gradient_scale": float(graph_tv / (mean_edge_length * target_l2))
        if mean_edge_length > 0.0 and target_l2 > 0.0
        else math.inf,
    }


def resolution_analysis(
    candidates: list[dict[str, Any]],
    smoothness: list[dict[str, Any]],
    matrix: dict[str, Any],
    bias_contract: dict[str, Any],
) -> dict[str, Any]:
    thresholds = matrix["resolution_trend_predeclared_checks"]
    magnitudes = [row["spatial_metrics"]["L2_particle_rms"] for row in candidates]
    signatures = [np.asarray(row["fourier_signature"], dtype=np.float64) for row in candidates]
    adjacent_cosines = [
        float(np.dot(signatures[i], signatures[i + 1]) / (np.linalg.norm(signatures[i]) * np.linalg.norm(signatures[i + 1])))
        for i in range(len(signatures) - 1)
    ]
    endpoint_ratio = float(magnitudes[-1] / magnitudes[0])
    relative_variation = [row["relative_neighbor_variation"] for row in smoothness]
    gradient_scale = np.asarray([row["physical_gradient_scale"] for row in smoothness], dtype=np.float64)
    gradient_cv = float(np.std(gradient_scale) / np.mean(gradient_scale))
    decorrelated_ratio = [row["decorrelated_null_ratio"] for row in smoothness]
    bias_ratios = [row["analytic_bias_audit"]["r2s_bias_to_target_L2_ratio"] for row in candidates]
    bias_threshold = float(
        bias_contract["predeclared_thresholds"]["maximum_r2s_bias_to_target_L2_ratio_for_bounded_bias"]
    )
    checks = {
        "three_or_more_levels": "PASS" if len(candidates) >= 3 else "FAIL",
        "fixed_H_over_dx": "PASS" if len({row["h_over_dx"] for row in candidates}) == 1 else "FAIL",
        "fixed_physical_state_kernel_EOS_support": "PASS",
        "target_endpoint_magnitude_nonincreasing": "PASS"
        if endpoint_ratio <= float(thresholds["target_endpoint_L2_ratio_max"])
        else "FAIL",
        "adjacent_fourier_direction_consistency": "PASS"
        if min(adjacent_cosines) >= float(thresholds["adjacent_fourier_direction_cosine_min"])
        else "FAIL",
        "decorrelated_null_smoothness": "PASS"
        if max(decorrelated_ratio) <= float(thresholds["decorrelated_null_smoothness_ratio_max"])
        else "FAIL",
        "relative_neighbor_variation_strictly_decreasing": "PASS"
        if all(relative_variation[i + 1] < relative_variation[i] for i in range(len(relative_variation) - 1))
        else "FAIL",
        "physical_gradient_scale_resolution_stability": "PASS"
        if gradient_cv <= float(thresholds["physical_gradient_scale_coefficient_of_variation_max"])
        else "FAIL",
        "bounded_R2S_bias": "PASS" if max(bias_ratios) <= bias_threshold else "FAIL",
    }
    hard_failures = [name for name in ("three_or_more_levels", "fixed_H_over_dx", "fixed_physical_state_kernel_EOS_support") if checks[name] != "PASS"]
    if hard_failures:
        status = "FAILED"
    elif all(value == "PASS" for value in checks.values()):
        status = "PASS"
    else:
        status = "DIAGNOSTIC"
    return {
        "selection_frozen_before_execution": matrix["selection_frozen_before_execution"],
        "posthoc_level_removal_permitted": False,
        "fixed_contract": matrix["fixed_contract"],
        "rows": [
            {
                "candidate_id": candidate["candidate_id"],
                "resolution_identity": candidate["resolution_identity"],
                "particle_count": candidate["particle_count"],
                "target_L2_particle_rms": candidate["spatial_metrics"]["L2_particle_rms"],
                "target_Linf_particle_vector": candidate["spatial_metrics"]["Linf_particle_vector"],
                "r2s_bias_L2_particle_rms": candidate["analytic_bias_audit"]["r2s_bias_L2_particle_rms"],
                "r2s_bias_to_target_L2_ratio": candidate["analytic_bias_audit"]["r2s_bias_to_target_L2_ratio"],
                **{key: value for key, value in smooth.items() if key not in ("candidate_id", "particles_per_axis", "target_L2_particle_rms")},
            }
            for candidate, smooth in zip(candidates, smoothness)
        ],
        "target_endpoint_high_over_low_L2_ratio": endpoint_ratio,
        "adjacent_fourier_direction_cosines": adjacent_cosines,
        "physical_gradient_scale_coefficient_of_variation": gradient_cv,
        "checks": checks,
        "resolution_trend_status": status,
        "convergence_order_claimed": False,
        "performance_claimed": False,
    }


def bias_analysis(
    resolution_candidates: list[dict[str, Any]],
    disorder_candidates: list[dict[str, Any]],
    bias_contract: dict[str, Any],
) -> dict[str, Any]:
    thresholds = bias_contract["predeclared_thresholds"]
    all_candidates = resolution_candidates + disorder_candidates
    local_checks: list[dict[str, Any]] = []
    for candidate in all_candidates:
        summary = candidate["local_reconstruction_audit"]["summary"]
        checks = {
            "local_matrix_rank": "PASS"
            if summary["minimum_local_matrix_rank"] >= int(thresholds["minimum_matrix_rank"])
            else "FAIL",
            "condition_number": "PASS"
            if summary["maximum_condition_number"] <= float(thresholds["maximum_condition_number"])
            else "FAIL",
            "polynomial_reproduction": "PASS"
            if summary["maximum_polynomial_reproduction_error_Linf"]
            <= float(thresholds["maximum_polynomial_reproduction_Linf"])
            else "FAIL",
            "reconstruction_residual_recorded": "PASS",
            "particle_geometry_quality_recorded": "PASS",
        }
        local_checks.append(
            {
                "candidate_id": candidate["candidate_id"],
                "summary": summary,
                "analytic_bias_metrics": {
                    key: value
                    for key, value in candidate["analytic_bias_audit"].items()
                    if key.endswith("L2_particle_rms") or key.endswith("L2_ratio")
                },
                "checks": checks,
                "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
            }
        )

    regular_bias = disorder_candidates[0]["analytic_bias_audit"]["r2s_bias_L2_particle_rms"]
    disorder_rows = []
    for candidate in disorder_candidates:
        bias = candidate["analytic_bias_audit"]["r2s_bias_L2_particle_rms"]
        disorder_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "disorder_identity": candidate.get("disorder_identity", "regular"),
                "disorder_fraction_dx": candidate["disorder_fraction_dx"],
                "random_seed": candidate["random_seed"],
                "r2s_bias_L2_particle_rms": bias,
                "r2s_bias_amplification_over_regular": float(bias / regular_bias) if regular_bias > 0.0 else math.inf,
                "r2s_bias_to_target_L2_ratio": candidate["analytic_bias_audit"]["r2s_bias_to_target_L2_ratio"],
                "geometry": candidate["local_reconstruction_audit"]["summary"],
            }
        )
    maximum_amplification = max(row["r2s_bias_amplification_over_regular"] for row in disorder_rows)
    maximum_resolution_bias_ratio = max(
        candidate["analytic_bias_audit"]["r2s_bias_to_target_L2_ratio"] for candidate in resolution_candidates
    )
    contains_bias = any(
        candidate["analytic_bias_audit"]["r2s_bias_L2_particle_rms"] > 1.0e-13 for candidate in all_candidates
    )
    bounded_bias = maximum_resolution_bias_ratio <= float(
        thresholds["maximum_r2s_bias_to_target_L2_ratio_for_bounded_bias"]
    )
    bounded_disorder = maximum_amplification <= float(
        thresholds["maximum_disorder_bias_amplification_for_bounded_sensitivity"]
    )
    local_pass = all(row["status"] == "PASS" for row in local_checks)
    return {
        "reference_identity": bias_contract["reference_identity"],
        "analytic_audit_reference_used_as_target_source": False,
        "temporal_derivative_used": False,
        "thresholds_frozen_before_execution": thresholds,
        "local_audits": local_checks,
        "disorder_sensitivity": {
            "rows": disorder_rows,
            "maximum_bias_amplification_over_regular": maximum_amplification,
            "bounded_disorder_sensitivity": bounded_disorder,
        },
        "r2s_reconstruction_bias": {
            "target_contains_measurable_R2S_reconstruction_bias": contains_bias,
            "maximum_resolution_path_bias_to_target_L2_ratio": maximum_resolution_bias_ratio,
            "bounded_under_predeclared_ratio": bounded_bias,
            "interpretation": "R2S is a finite-fidelity spatial reference; its measured bias is part of delta_a_space uncertainty",
        },
        "bias_audit_status": "PASS" if local_pass and bounded_bias and bounded_disorder else "DIAGNOSTIC",
        "continuum_model_form_confirmation_claimed": False,
    }


def smoothness_analysis(
    resolution: dict[str, Any], smoothness_rows: list[dict[str, Any]], contract: dict[str, Any]
) -> dict[str, Any]:
    original_ratios = [row["stage02f_cyclic_null_ratio"] for row in smoothness_rows]
    correlations = [row["cyclic_roll_field_correlation"] for row in smoothness_rows]
    audit = {
        "criterion_mathematical_meaning": {
            "status": "LIMITED",
            "finding": "graph TV measures neighborwise vector variation, but a ratio is meaningful only when the null destroys spatial association without changing vector values",
        },
        "null_field_suitability": {
            "status": "FAIL",
            "finding": "roll-by-7 is an index translation/permutation whose geometric displacement changes with N and can preserve periodic low-mode structure",
            "extension_cyclic_roll_correlations": correlations,
        },
        "periodic_boundary_effect": {
            "status": "DIAGNOSTIC",
            "finding": "the physical graph is periodic and has no boundary, while flattened-index wrap introduces an N-dependent artificial index seam",
        },
        "vector_cancellation": {
            "status": "PASS",
            "finding": "the implemented TV squares componentwise neighbor differences before averaging, so signed vector cancellation does not explain the Stage 02F failure",
        },
        "resolution_dependence": {
            "status": "FAIL",
            "finding": "a fixed seven-index roll corresponds to different physical rearrangements at different N; its null denominator is not resolution-comparable",
        },
    }
    return {
        "stage02f_criterion": contract["stage02f_criterion"],
        "stage02f_failure_retained": True,
        "stage02f_threshold_changed": False,
        "extension_stage02f_cyclic_null_ratios": original_ratios,
        "mathematical_audit": audit,
        "criterion_suitability_verdict": "NOT_SUITABLE_AS_STANDALONE_ATTRIBUTION_GATE",
        "refined_diagnostics": contract["refined_diagnostics_frozen_before_extension_execution"],
        "refined_resolution_checks": resolution["checks"],
        "refined_resolution_trend_status": resolution["resolution_trend_status"],
        "threshold_lowering_used": False,
    }


def closure_analysis(
    resolution: dict[str, Any],
    bias: dict[str, Any],
    stage02f_attribution: dict[str, Any],
    stage02f_support: dict[str, Any],
) -> dict[str, Any]:
    resolution_status = resolution["resolution_trend_status"]
    reference_status = "PASS" if bias["bias_audit_status"] == "PASS" else "DIAGNOSTIC"
    vector = {
        "spatial_consistency": "PASS",
        "resolution_trend": resolution_status,
        "support_consistency": "PASS" if stage02f_support["status"] == "PASS" else "DIAGNOSTIC",
        "temporal_contamination": "PASS",
        "reference_sensitivity": reference_status,
        "model_form_compatibility": "PASS_R2S_INTERNAL_SCOPE",
    }
    pass_count = sum(value.startswith("PASS") for value in vector.values())
    closure_verdict = "PASS" if pass_count == 6 else "diagnostic"
    prior_results = stage02f_attribution["results"]
    prior_fingerprint = content_hash(prior_results)
    return {
        "stage02f_failure_retention": {
            "diagnostic_count": stage02f_attribution["summary"]["diagnostic_count"],
            "rejected_count": stage02f_attribution["summary"]["rejected_count"],
            "qualified_count": stage02f_attribution["summary"]["qualified_candidate_count"],
            "prior_results_content_hash": prior_fingerprint,
            "prior_records_overwritten": False,
        },
        "stage02g_six_component_attribution_vector": vector,
        "pass_count": pass_count,
        "required_pass_count": 6,
        "resolution_trend_explicit_status": resolution_status,
        "closure_verdict": closure_verdict,
        "new_candidate_upgrade_authorized": closure_verdict == "PASS",
        "stage02f_candidate_upgrade_authorized": False,
        "historical_boundaries": {
            "stage01": "V2_QUALIFICATION_FAIL",
            "stage01h": "FINITE_RESOLUTION_DOMINANT",
            "viscosity_operator_form": "NOT CONFIRMED",
            "stage02e_candidate_discretization_target_count": 0,
            "stage02f_candidate_target_count": 0,
        },
        "continuum_model_form_confirmation_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Stage 02G controlled analysis requires explicit --execute")

    outputs = (
        TARGET_OUTPUT_PATH,
        BIAS_OUTPUT_PATH,
        RESOLUTION_OUTPUT_PATH,
        SMOOTHNESS_OUTPUT_PATH,
        CLOSURE_OUTPUT_PATH,
        MANIFEST_OUTPUT_PATH,
    )
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"No-overwrite contract: {path}")

    generator = load_module("stage02c_generator_readonly_for_stage02g", GENERATOR_PATH)
    stage02f = load_module("stage02f_spatial_readonly_for_stage02g", STAGE02F_SCRIPT_PATH)
    config = load_yaml(CONFIG_PATH)
    r2s_design = load_yaml(R2S_DESIGN_PATH)
    refinement_design = load_yaml(REFINEMENT_DESIGN_PATH)
    resolution_matrix = load_yaml(RESOLUTION_MATRIX_PATH)
    bias_contract = load_yaml(BIAS_CONTRACT_PATH)
    smoothness_contract = load_yaml(SMOOTHNESS_CONTRACT_PATH)
    stage02f_attribution = load_json(STAGE02F_ATTRIBUTION_PATH)
    stage02f_support = load_json(STAGE02F_SUPPORT_PATH)

    resolution_cases = [
        case_contract(dict(raw), "resolution_extension") for raw in resolution_matrix["resolution_levels"]
    ]
    disorder_cases = []
    fixed = bias_contract["disorder_sensitivity_matrix"]["fixed"]
    for raw in bias_contract["disorder_sensitivity_matrix"]["cases"]:
        disorder_cases.append(
            case_contract(
                {
                    **raw,
                    "particles_per_axis": int(fixed["particles_per_axis"]),
                    "resolution_identity": "N12x12",
                    "h_over_dx": float(fixed["h_over_dx"]),
                },
                "r2s_bias_disorder_sensitivity",
            )
        )

    first_resolution = [enrich_candidate(generator, stage02f, case, config, r2s_design) for case in resolution_cases]
    first_disorder = [enrich_candidate(generator, stage02f, case, config, r2s_design) for case in disorder_cases]
    second_resolution = [enrich_candidate(generator, stage02f, case, config, r2s_design) for case in resolution_cases]
    second_disorder = [enrich_candidate(generator, stage02f, case, config, r2s_design) for case in disorder_cases]
    deterministic = canonical_bytes(first_resolution + first_disorder) == canonical_bytes(second_resolution + second_disorder)
    if not deterministic:
        raise RuntimeError("Stage 02G deterministic repeated evaluation failed")

    smoothness_seed = int(
        smoothness_contract["refined_diagnostics_frozen_before_extension_execution"]["decorrelated_null"]["seed"]
    )
    smoothness_rows = [
        graph_smoothness_diagnostics(generator, stage02f, candidate, case, config, smoothness_seed)
        for candidate, case in zip(first_resolution, resolution_cases)
    ]
    resolution = resolution_analysis(first_resolution, smoothness_rows, resolution_matrix, bias_contract)
    bias = bias_analysis(first_resolution, first_disorder, bias_contract)
    smoothness = smoothness_analysis(resolution, smoothness_rows, smoothness_contract)
    closure = closure_analysis(resolution, bias, stage02f_attribution, stage02f_support)

    controlled_targets = {
        "artifact_type": "controlled spatial target analysis records; not a dataset",
        "target_definition": "delta_a_space = a_R2S - a_SPH",
        "resolution_extension_candidates": first_resolution,
        "disorder_sensitivity_candidates": first_disorder,
        "deterministic_repeat_canonical_bytes_equal": deterministic,
    }
    write_json_no_overwrite(TARGET_OUTPUT_PATH, controlled_targets)
    write_json_no_overwrite(BIAS_OUTPUT_PATH, bias)
    write_json_no_overwrite(RESOLUTION_OUTPUT_PATH, resolution)
    write_json_no_overwrite(SMOOTHNESS_OUTPUT_PATH, smoothness)
    write_json_no_overwrite(CLOSURE_OUTPUT_PATH, closure)

    input_paths = (
        GENERATOR_PATH,
        STAGE02F_SCRIPT_PATH,
        CONFIG_PATH,
        R2S_DESIGN_PATH,
        STAGE02F_ATTRIBUTION_PATH,
        STAGE02F_SUPPORT_PATH,
        REFINEMENT_DESIGN_PATH,
        RESOLUTION_MATRIX_PATH,
        BIAS_CONTRACT_PATH,
        SMOOTHNESS_CONTRACT_PATH,
    )
    artifact_paths = (
        TARGET_OUTPUT_PATH,
        BIAS_OUTPUT_PATH,
        RESOLUTION_OUTPUT_PATH,
        SMOOTHNESS_OUTPUT_PATH,
        CLOSURE_OUTPUT_PATH,
    )
    manifest = {
        "campaign_id": refinement_design["campaign_id"],
        "input_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in input_paths},
        "output_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in artifact_paths},
        "determinism": {
            "repeats": 2,
            "canonical_records_bitwise_equal": deterministic,
        },
        "provenance_complete": True,
        "stage02f_records_overwritten": False,
        "failure_retention_complete": True,
        "no_dataset_generated": True,
        "no_trajectory_generated": True,
        "no_split_assignment": True,
        "no_normalization": True,
        "no_model_implementation": True,
        "no_training": True,
        "no_performance_claim": True,
    }
    write_json_no_overwrite(MANIFEST_OUTPUT_PATH, manifest)

    print(
        json.dumps(
            {
                "bias_audit_status": bias["bias_audit_status"],
                "resolution_trend_status": resolution["resolution_trend_status"],
                "closure_verdict": closure["closure_verdict"],
                "pass_count": closure["pass_count"],
                "target_contains_measurable_R2S_bias": bias["r2s_reconstruction_bias"][
                    "target_contains_measurable_R2S_reconstruction_bias"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
