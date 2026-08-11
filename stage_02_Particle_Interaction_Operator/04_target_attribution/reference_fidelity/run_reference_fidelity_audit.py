#!/usr/bin/env python3
"""Execute the Stage 02H controlled reference-fidelity audit.

All fields are evaluated at one frozen timestamp.  This module creates audit
evidence only; it does not generate a target dataset or implement training.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
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
STAGE02G_SCRIPT_PATH = ATTR_ROOT / "spatial_refinement/run_stage02g_refinement.py"
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
R2S_DESIGN_PATH = ATTR_ROOT / "semidiscrete_reference/r2s_reference_design.yaml"
STAGE02G_BIAS_PATH = ATTR_ROOT / "r2s_bias_audit/r2s_bias_audit.json"
STAGE02G_CLOSURE_PATH = ATTR_ROOT / "qualification_closure/attribution_closure.json"
MATRIX_PATH = ATTR_ROOT / "reference_fidelity/reference_candidate_matrix.yaml"
RULES_PATH = ATTR_ROOT / "acceptance/reference_acceptance_rules.yaml"

CANDIDATE_RESULTS_PATH = ATTR_ROOT / "reference_fidelity/reference_candidate_results.json"
CURRENT_R2S_PATH = ATTR_ROOT / "r2s_comparison/current_r2s_audit.json"
CROSS_REFERENCE_PATH = ATTR_ROOT / "r2s_comparison/cross_reference_audit.json"
BIAS_ANALYSIS_PATH = ATTR_ROOT / "bias_analysis/reference_bias_analysis.json"
ACCEPTANCE_RESULTS_PATH = ATTR_ROOT / "acceptance/reference_acceptance_results.json"
MANIFEST_PATH = ATTR_ROOT / "acceptance/stage02h_manifest.json"


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


def field_metrics(field: np.ndarray) -> dict[str, float]:
    vector_norm = np.linalg.norm(field, axis=1)
    return {
        "L2_particle_rms": float(np.sqrt(np.mean(vector_norm * vector_norm))),
        "Linf_particle_vector": float(np.max(vector_norm)),
    }


def field_cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.sum(left * right) / denominator) if denominator > 0.0 else 0.0


def runtime_case(raw: dict[str, Any]) -> dict[str, Any]:
    disorder_fraction = float(raw["disorder_fraction_dx"])
    return {
        **raw,
        "topology_control": "none",
        "time_horizon": 0.0,
        "trajectory_family": "stage02h_same_timestamp_no_trajectory",
        "initial_condition_family": "periodic_vortex",
        "disorder_family": raw.get("disorder_identity", "regular" if disorder_fraction == 0.0 else "frozen_jitter"),
    }


def analytic_spatial_acceleration(state: dict[str, np.ndarray], config: dict[str, Any]) -> np.ndarray:
    length = float(config["domain"]["box_length"])
    wave_number = 2.0 * math.pi / length
    phase_x = wave_number * state["x"][:, 0]
    phase_y = wave_number * state["x"][:, 1]
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


def solve_real_weighted(
    matrix: np.ndarray, weights: np.ndarray, values: np.ndarray, sensitivity: bool
) -> tuple[np.ndarray, int, float]:
    sqrt_weight = np.sqrt(np.maximum(weights, 0.0))
    weighted_matrix = matrix * sqrt_weight[:, None]
    weighted_values = values * sqrt_weight
    singular = np.linalg.svd(weighted_matrix, compute_uv=False)
    tolerance = np.finfo(np.float64).eps * max(weighted_matrix.shape) * singular[0]
    positive = singular[singular > tolerance]
    rank = int(positive.size)
    condition = float(singular[0] / positive[-1]) if positive.size else math.inf
    if sensitivity:
        coefficients = np.linalg.pinv(weighted_matrix, rcond=np.finfo(np.float64).eps * max(weighted_matrix.shape)) @ weighted_values
    else:
        coefficients = np.linalg.lstsq(weighted_matrix, weighted_values, rcond=None)[0]
    return coefficients, rank, condition


def cubic_wendland_reference(
    generator: Any,
    state: dict[str, np.ndarray],
    raw_case: dict[str, Any],
    config: dict[str, Any],
    sensitivity: bool,
) -> tuple[np.ndarray, dict[str, Any], str]:
    candidate_case = runtime_case({**raw_case, "h_over_dx": 4.1})
    edges = generator.build_edges(state, candidate_case, config, apply_control=False)
    particle_count = state["x"].shape[0]
    dx = float(config["domain"]["box_length"]) / int(raw_case["particles_per_axis"])
    support = 4.1 * dx
    pressure = generator.pressure_from_density(state["rho"], config)
    nu = float(config["physics"]["kinematic_viscosity"])
    acceleration = np.zeros((particle_count, 2), dtype=np.float64)
    ranks: list[int] = []
    conditions: list[float] = []
    reproduction_errors: list[float] = []
    relative_residuals: list[float] = []
    isotropy: list[float] = []
    angular_gaps: list[float] = []
    neighbor_counts: list[int] = []
    test_coefficients = np.asarray([0.7, -0.4, 0.3, -0.2, 0.5, 0.11, -0.13, 0.17, -0.19])

    for particle in range(particle_count):
        selection = edges["source"] == particle
        neighbors = edges["target"][selection]
        displacement = edges["displacement"][selection]
        xi = displacement / support
        x = xi[:, 0]
        y = xi[:, 1]
        matrix = np.column_stack(
            (x, y, 0.5 * x * x, x * y, 0.5 * y * y, x**3 / 6.0, x * x * y / 2.0, x * y * y / 2.0, y**3 / 6.0)
        )
        radius = np.linalg.norm(displacement, axis=1) / support
        weights = np.where(radius < 1.0, (1.0 - radius) ** 4 * (1.0 + 4.0 * radius), 0.0)
        p_coeff, rank, condition = solve_real_weighted(
            matrix, weights, pressure[neighbors] - pressure[particle], sensitivity
        )
        v_coefficients = np.column_stack(
            [
                solve_real_weighted(
                    matrix,
                    weights,
                    state["v"][neighbors, component] - state["v"][particle, component],
                    sensitivity,
                )[0]
                for component in range(2)
            ]
        )
        reproduction, _, _ = solve_real_weighted(matrix, weights, matrix @ test_coefficients, sensitivity)
        sqrt_weight = np.sqrt(weights)
        residual_per_field = []
        for field in (pressure, state["v"][:, 0], state["v"][:, 1]):
            values = field[neighbors] - field[particle]
            coefficients, _, _ = solve_real_weighted(matrix, weights, values, sensitivity)
            numerator = float(np.linalg.norm(sqrt_weight * (matrix @ coefficients - values)))
            denominator = float(np.linalg.norm(sqrt_weight * values))
            residual_per_field.append(numerator / denominator if denominator > 1.0e-14 else 0.0)
        moment = np.einsum("n,ni,nj->ij", weights, xi, xi)
        eigenvalues = np.linalg.eigvalsh(moment)
        angles = np.sort(np.arctan2(y, x))
        gaps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * math.pi)))
        ranks.append(rank)
        conditions.append(condition)
        reproduction_errors.append(float(np.max(np.abs(reproduction - test_coefficients))))
        relative_residuals.append(float(max(residual_per_field)))
        isotropy.append(float(eigenvalues[0] / eigenvalues[-1]))
        angular_gaps.append(float(np.max(gaps)))
        neighbor_counts.append(int(neighbors.size))
        gradient_pressure = p_coeff[:2] / support
        laplacian_velocity = (v_coefficients[2] + v_coefficients[4]) / (support * support)
        acceleration[particle] = -gradient_pressure / state["rho"][particle] + nu * laplacian_velocity

    diagnostics = {
        "minimum_matrix_rank": int(min(ranks)),
        "maximum_condition_number": float(max(conditions)),
        "maximum_polynomial_reproduction_Linf": float(max(reproduction_errors)),
        "maximum_reconstruction_relative_residual": float(max(relative_residuals)),
        "median_reconstruction_relative_residual": float(np.median(relative_residuals)),
        "geometry_isotropy_ratio_min": float(min(isotropy)),
        "maximum_angular_gap_radians": float(max(angular_gaps)),
        "neighbor_count_min": int(min(neighbor_counts)),
        "neighbor_count_max": int(max(neighbor_counts)),
    }
    return acceleration, diagnostics, stage02f_graph_hash(generator, edges)


def stage02f_graph_hash(generator: Any, edges: dict[str, np.ndarray]) -> str:
    del generator
    return content_hash(
        {
            "source": edges["source"].astype(np.int64).tolist(),
            "target": edges["target"].astype(np.int64).tolist(),
            "displacement": np.asarray(edges["displacement"], dtype=np.float64).tolist(),
        }
    )


def fourier_reference(
    state: dict[str, np.ndarray],
    config: dict[str, Any],
    sensitivity: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    length = float(config["domain"]["box_length"])
    modes = [(kx, ky) for kx in range(-2, 3) for ky in range(-2, 3)]
    mode_array = np.asarray(modes, dtype=np.float64)
    phase = (2.0j * math.pi / length) * (
        state["x"][:, 0, None] * mode_array[None, :, 0]
        + state["x"][:, 1, None] * mode_array[None, :, 1]
    )
    matrix = np.exp(phase)
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = np.finfo(np.float64).eps * max(matrix.shape) * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(singular[0] / singular[rank - 1])
    pressure = config["physics"]["sound_speed"] ** 2 * (state["rho"] - config["physics"]["rho0"])
    fields = (np.asarray(pressure), state["v"][:, 0], state["v"][:, 1])
    coefficients = []
    residuals = []
    for field in fields:
        if sensitivity:
            coefficient = np.linalg.pinv(matrix, rcond=np.finfo(np.float64).eps * max(matrix.shape)) @ field
        else:
            coefficient = np.linalg.lstsq(matrix, field, rcond=None)[0]
        coefficients.append(coefficient)
        residuals.append(float(np.linalg.norm((matrix @ coefficient).real - field) / max(np.linalg.norm(field), 1.0e-14)))
    p_coefficient, vx_coefficient, vy_coefficient = coefficients
    kx = (2.0 * math.pi / length) * mode_array[:, 0]
    ky = (2.0 * math.pi / length) * mode_array[:, 1]
    gradient_pressure = np.column_stack(
        ((matrix @ (1.0j * kx * p_coefficient)).real, (matrix @ (1.0j * ky * p_coefficient)).real)
    )
    laplacian_factor = -(kx * kx + ky * ky)
    laplacian_velocity = np.column_stack(
        ((matrix @ (laplacian_factor * vx_coefficient)).real, (matrix @ (laplacian_factor * vy_coefficient)).real)
    )
    nu = float(config["physics"]["kinematic_viscosity"])
    acceleration = -gradient_pressure / state["rho"][:, None] + nu * laplacian_velocity
    diagnostics = {
        "matrix_rank": rank,
        "condition_number": condition,
        "mode_count": len(modes),
        "maximum_field_reconstruction_relative_residual": float(max(residuals)),
        "modes": [list(mode) for mode in modes],
    }
    return acceleration, diagnostics


def incumbent_reference(
    generator: Any,
    stage02f: Any,
    stage02g: Any,
    state: dict[str, np.ndarray],
    edges: dict[str, np.ndarray],
    raw_case: dict[str, Any],
    config: dict[str, Any],
    sensitivity: bool,
) -> tuple[np.ndarray, dict[str, Any], str]:
    acceleration, primary = stage02f.r2s_evaluation(
        generator, state, edges, runtime_case(raw_case), config, sensitivity=sensitivity
    )
    local = stage02g.local_reconstruction_audit(
        generator, stage02f, state, edges, runtime_case(raw_case), config
    )["summary"]
    diagnostics = {
        "minimum_matrix_rank": primary["minimum_rank"],
        "maximum_condition_number": primary["maximum_condition_number"],
        "maximum_polynomial_reproduction_Linf": primary["maximum_quadratic_reproduction_Linf"],
        "maximum_reconstruction_relative_residual": local["reconstruction_relative_residual_max"],
        "median_reconstruction_relative_residual": local["reconstruction_relative_residual_median"],
        "geometry_isotropy_ratio_min": local["geometry_isotropy_ratio_min"],
        "maximum_angular_gap_radians": local["maximum_angular_gap_radians"],
        "neighbor_count_min": local["active_kernel_neighbor_count_min"],
        "neighbor_count_max": local["active_kernel_neighbor_count_max"],
    }
    return acceleration, diagnostics, stage02f.graph_hash(edges)


def evaluate_case(
    generator: Any,
    stage02f: Any,
    stage02g: Any,
    raw_case: dict[str, Any],
    candidate: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    case = runtime_case(raw_case)
    state = generator.initial_state(case, config)
    sph_components, baseline_edges = generator.sparse_rhs_components(state, case, config, apply_control=False)
    a_sph = sph_components["total"]
    analytic = analytic_spatial_acceleration(state, config)
    candidate_id = candidate["candidate_id"]
    candidate_graph_hash: str | None = None

    if candidate_id == "H_REF_QWLS2_INCUMBENT":
        primary, diagnostics, candidate_graph_hash = incumbent_reference(
            generator, stage02f, stage02g, state, baseline_edges, raw_case, config, False
        )
        sensitivity, _, _ = incumbent_reference(
            generator, stage02f, stage02g, state, baseline_edges, raw_case, config, True
        )
    elif candidate_id == "H_REF_CWLS3":
        primary, diagnostics, candidate_graph_hash = cubic_wendland_reference(
            generator, state, raw_case, config, False
        )
        sensitivity, _, _ = cubic_wendland_reference(generator, state, raw_case, config, True)
    elif candidate_id == "H_REF_FOURIER2":
        primary, diagnostics = fourier_reference(state, config, False)
        sensitivity, _ = fourier_reference(state, config, True)
    elif candidate_id == "H_REF_ANALYTIC":
        primary = analytic.copy()
        sensitivity = analytic.copy()
        diagnostics = {
            "closed_form": True,
            "reconstruction_residual": 0.0,
            "condition_number": 1.0,
            "scope": "periodic_vortex_family_only",
        }
    else:
        raise ValueError(f"Unknown candidate {candidate_id}")

    reference_target = primary - a_sph
    bias = primary - analytic
    solver_difference = primary - sensitivity
    target_metrics = field_metrics(reference_target)
    bias_metrics = field_metrics(bias)
    sensitivity_metrics = field_metrics(solver_difference)
    roundoff_floor = 1.0e-14
    uncertainty_l2 = bias_metrics["L2_particle_rms"] + sensitivity_metrics["L2_particle_rms"] + roundoff_floor
    target_l2 = target_metrics["L2_particle_rms"]
    target_linf = target_metrics["Linf_particle_vector"]
    return {
        "candidate_id": candidate_id,
        "implementation_identity": candidate["implementation_identity"],
        "independence_class": candidate["independence_class"],
        "case_id": raw_case["case_id"],
        "particles_per_axis": int(raw_case["particles_per_axis"]),
        "disorder_fraction_dx": float(raw_case["disorder_fraction_dx"]),
        "disorder_identity": raw_case.get("disorder_identity", "regular"),
        "random_seed": int(raw_case["random_seed"]),
        "state_hash": stage02f.state_hash(state),
        "baseline_state_hash": stage02f.state_hash(state),
        "candidate_state_hash": stage02f.state_hash(state),
        "physics_hash": content_hash({"domain": config["domain"], "physics": config["physics"], "timestamp": 0.0}),
        "baseline_graph_hash": stage02f.graph_hash(baseline_edges),
        "candidate_graph_hash": candidate_graph_hash,
        "same_state": "PASS",
        "same_physics": "PASS",
        "temporal_derivative_used": False,
        "a_reference": primary.tolist(),
        "a_SPH": a_sph.tolist(),
        "reference_target": reference_target.tolist(),
        "reference_target_metrics": target_metrics,
        "reference_bias": bias.tolist(),
        "bias_metrics": bias_metrics,
        "bias_to_reference_target_L2_ratio": float(bias_metrics["L2_particle_rms"] / target_l2)
        if target_l2 > 0.0
        else math.inf,
        "solver_sensitivity_metrics": sensitivity_metrics,
        "reference_uncertainty": {
            "method": "analytic_bias_L2_plus_primary_pseudoinverse_sensitivity_L2_plus_roundoff_floor",
            "L2_particle_rms_bound": uncertainty_l2,
            "to_reference_target_L2_ratio": float(uncertainty_l2 / target_l2) if target_l2 > 0.0 else math.inf,
            "GCI_status": "not_justified",
            "single_total_GCI_generated": False,
        },
        "diagnostics": diagnostics,
        "spatial_signature": stage02f.fourier_signature(state["x"], reference_target).tolist(),
        "target_Linf_for_normalization": target_linf,
    }


def cross_reference_analysis(
    records: list[dict[str, Any]], candidates: list[dict[str, Any]], rules: dict[str, Any]
) -> dict[str, Any]:
    thresholds = rules["numeric_thresholds"]
    by_key = {(row["candidate_id"], row["case_id"]): row for row in records}
    case_ids = sorted({row["case_id"] for row in records})
    candidate_map = {row["candidate_id"]: row for row in candidates}
    pairs = []
    for left_id, right_id in itertools.combinations(candidate_map, 2):
        case_rows = []
        for case_id in case_ids:
            left = by_key[(left_id, case_id)]
            right = by_key[(right_id, case_id)]
            left_a = np.asarray(left["a_reference"], dtype=np.float64)
            right_a = np.asarray(right["a_reference"], dtype=np.float64)
            difference = left_a - right_a
            difference_metrics = field_metrics(difference)
            left_target = np.asarray(left["reference_target"], dtype=np.float64)
            right_target = np.asarray(right["reference_target"], dtype=np.float64)
            max_target_l2 = max(
                left["reference_target_metrics"]["L2_particle_rms"],
                right["reference_target_metrics"]["L2_particle_rms"],
            )
            max_target_linf = max(
                left["reference_target_metrics"]["Linf_particle_vector"],
                right["reference_target_metrics"]["Linf_particle_vector"],
            )
            l2_ratio = float(difference_metrics["L2_particle_rms"] / max_target_l2)
            linf_ratio = float(difference_metrics["Linf_particle_vector"] / max_target_linf)
            target_cosine = field_cosine(left_target, right_target)
            checks = {
                "L2_agreement": "PASS"
                if l2_ratio <= float(thresholds["cross_reference_pair_L2_to_max_target_L2_ratio_max"])
                else "FAIL",
                "Linf_agreement": "PASS"
                if linf_ratio <= float(thresholds["cross_reference_pair_Linf_to_max_target_Linf_ratio_max"])
                else "FAIL",
                "spatial_pattern_agreement": "PASS"
                if target_cosine >= float(thresholds["cross_reference_target_pattern_cosine_min"])
                else "FAIL",
            }
            case_rows.append(
                {
                    "case_id": case_id,
                    "difference_L2_particle_rms": difference_metrics["L2_particle_rms"],
                    "difference_Linf_particle_vector": difference_metrics["Linf_particle_vector"],
                    "difference_L2_to_max_target_L2_ratio": l2_ratio,
                    "difference_Linf_to_max_target_Linf_ratio": linf_ratio,
                    "reference_target_pattern_cosine": target_cosine,
                    "difference_spatial_pattern": {
                        "particlewise_vector": difference.tolist(),
                        "fourier_signature_difference": (
                            np.asarray(left["spatial_signature"]) - np.asarray(right["spatial_signature"])
                        ).tolist(),
                    },
                    "checks": checks,
                    "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
                }
            )
        pair_status = "PASS" if all(row["status"] == "PASS" for row in case_rows) else "FAIL"
        pairs.append(
            {
                "left_candidate_id": left_id,
                "right_candidate_id": right_id,
                "independence_classes": [
                    candidate_map[left_id]["independence_class"],
                    candidate_map[right_id]["independence_class"],
                ],
                "independent_methods": candidate_map[left_id]["independence_class"]
                != candidate_map[right_id]["independence_class"],
                "cases": case_rows,
                "status": pair_status,
            }
        )
    return {
        "comparison_equation": "norm(a_ref1 - a_ref2)",
        "thresholds_frozen_before_execution": {
            key: value for key, value in thresholds.items() if key.startswith("cross_reference")
        },
        "candidate_pair_count": len(pairs),
        "pairs": pairs,
        "passing_independent_pairs": [
            [row["left_candidate_id"], row["right_candidate_id"]]
            for row in pairs
            if row["status"] == "PASS" and row["independent_methods"]
        ],
    }


def bias_analysis(records: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for candidate in candidates:
        candidate_records = [row for row in records if row["candidate_id"] == candidate["candidate_id"]]
        regular_n12 = next(row for row in candidate_records if row["case_id"] == "h_disorder_regular_n12")
        regular_bias = regular_n12["bias_metrics"]["L2_particle_rms"]
        disorder = []
        for row in candidate_records:
            if row["case_id"].startswith("h_disorder_"):
                bias_l2 = row["bias_metrics"]["L2_particle_rms"]
                disorder.append(
                    {
                        "case_id": row["case_id"],
                        "disorder_identity": row["disorder_identity"],
                        "bias_L2_particle_rms": bias_l2,
                        "bias_amplification_over_regular": float(bias_l2 / regular_bias)
                        if regular_bias > 1.0e-14
                        else (1.0 if bias_l2 <= 1.0e-14 else math.inf),
                        "condition_number": row["diagnostics"].get(
                            "maximum_condition_number", row["diagnostics"].get("condition_number")
                        ),
                        "reconstruction_residual": row["diagnostics"].get(
                            "maximum_reconstruction_relative_residual",
                            row["diagnostics"].get("maximum_field_reconstruction_relative_residual", 0.0),
                        ),
                    }
                )
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "method": candidate["method"],
                "maximum_bias_L2_particle_rms": max(row["bias_metrics"]["L2_particle_rms"] for row in candidate_records),
                "maximum_bias_to_reference_target_L2_ratio": max(
                    row["bias_to_reference_target_L2_ratio"] for row in candidate_records
                ),
                "maximum_reference_uncertainty_L2": max(
                    row["reference_uncertainty"]["L2_particle_rms_bound"] for row in candidate_records
                ),
                "maximum_uncertainty_to_reference_target_L2_ratio": max(
                    row["reference_uncertainty"]["to_reference_target_L2_ratio"] for row in candidate_records
                ),
                "resolution_rows": [
                    {
                        "case_id": row["case_id"],
                        "bias_L2_particle_rms": row["bias_metrics"]["L2_particle_rms"],
                        "bias_to_reference_target_L2_ratio": row["bias_to_reference_target_L2_ratio"],
                        "uncertainty_to_reference_target_L2_ratio": row["reference_uncertainty"][
                            "to_reference_target_L2_ratio"
                        ],
                    }
                    for row in candidate_records
                    if row["case_id"].startswith("h_regular_")
                ],
                "disorder_sensitivity": disorder,
            }
        )
    return {
        "bias_definition": "a_candidate_reference - analytic_spatial_acceleration",
        "reference_target_definition": "a_candidate_reference - a_SPH",
        "candidate_bias_rows": rows,
        "Stage02G_bias_failure_retained": True,
        "Stage02G_bias_artifact_hash": file_hash(STAGE02G_BIAS_PATH),
        "single_total_GCI_generated": False,
        "GCI_status": "not_justified",
    }


def acceptance_analysis(
    records: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    cross: dict[str, Any],
    rules: dict[str, Any],
    repeat: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    thresholds = rules["numeric_thresholds"]
    pair_lookup: dict[str, list[str]] = {row["candidate_id"]: [] for row in candidates}
    for pair in cross["pairs"]:
        if pair["status"] == "PASS" and pair["independent_methods"]:
            pair_lookup[pair["left_candidate_id"]].append(pair["right_candidate_id"])
            pair_lookup[pair["right_candidate_id"]].append(pair["left_candidate_id"])
    results = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        rows = [row for row in records if row["candidate_id"] == candidate_id]
        maximum_bias_ratio = max(row["bias_to_reference_target_L2_ratio"] for row in rows)
        maximum_uncertainty_ratio = max(
            row["reference_uncertainty"]["to_reference_target_L2_ratio"] for row in rows
        )
        agreeing_peers = pair_lookup[candidate_id]
        checks = {
            "same_state": "PASS" if all(row["same_state"] == "PASS" for row in rows) else "FAIL",
            "same_physics": "PASS" if all(row["same_physics"] == "PASS" for row in rows) else "FAIL",
            "deterministic": "PASS" if repeat[candidate_id]["canonical_records_equal"] else "FAIL",
            "low_reconstruction_bias": "PASS"
            if maximum_bias_ratio <= float(thresholds["bias_to_reference_target_L2_ratio_max"])
            else "FAIL",
            "cross_reference_agreement": "PASS"
            if len(agreeing_peers) >= int(thresholds["minimum_independent_agreeing_peer_count"])
            else "FAIL",
            "uncertainty_qualified": "PASS"
            if maximum_uncertainty_ratio <= float(thresholds["uncertainty_to_reference_target_L2_ratio_max"])
            else "FAIL",
        }
        accepted = all(value == "PASS" for value in checks.values())
        results.append(
            {
                "candidate_id": candidate_id,
                "checks": checks,
                "maximum_bias_to_reference_target_L2_ratio": maximum_bias_ratio,
                "maximum_uncertainty_to_reference_target_L2_ratio": maximum_uncertainty_ratio,
                "independent_agreeing_peers": agreeing_peers,
                "candidate_spatial_reference": accepted,
                "verdict": "accepted" if accepted else "diagnostic",
                "scope": "periodic_vortex_family_only"
                if candidate_id == "H_REF_ANALYTIC"
                else "stage02h_controlled_periodic_vortex_audit_scope",
            }
        )
    return {
        "rules_hash": file_hash(RULES_PATH),
        "thresholds_frozen_before_execution": True,
        "manual_override_used": False,
        "results": results,
        "summary": {
            "candidate_count": len(results),
            "accepted_count": sum(row["candidate_spatial_reference"] for row in results),
            "diagnostic_count": sum(not row["candidate_spatial_reference"] for row in results),
            "accepted_candidate_ids": [
                row["candidate_id"] for row in results if row["candidate_spatial_reference"]
            ],
        },
        "Stage02G_incumbent_bias_diagnostic_retained": True,
        "Stage02G_overwritten": False,
        "historical_boundaries": {
            "stage01": "V2_QUALIFICATION_FAIL",
            "stage01h": "FINITE_RESOLUTION_DOMINANT",
            "viscosity_operator_form": "NOT CONFIRMED",
            "stage02e_candidate_discretization_target_count": 0,
            "stage02f_qualified_candidate_count": 0,
        },
        "continuum_model_form_confirmation_claimed": False,
        "training_permission": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Stage 02H audit requires explicit --execute")
    outputs = (
        CANDIDATE_RESULTS_PATH,
        CURRENT_R2S_PATH,
        CROSS_REFERENCE_PATH,
        BIAS_ANALYSIS_PATH,
        ACCEPTANCE_RESULTS_PATH,
        MANIFEST_PATH,
    )
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"No-overwrite contract: {path}")

    generator = load_module("stage02c_generator_readonly_for_stage02h", GENERATOR_PATH)
    stage02f = load_module("stage02f_reference_readonly_for_stage02h", STAGE02F_SCRIPT_PATH)
    stage02g = load_module("stage02g_refinement_readonly_for_stage02h", STAGE02G_SCRIPT_PATH)
    config = load_yaml(CONFIG_PATH)
    matrix = load_yaml(MATRIX_PATH)
    rules = load_yaml(RULES_PATH)
    candidates = matrix["candidates"]
    cases = matrix["evaluation_suite"]["resolution_cases"] + matrix["evaluation_suite"]["disorder_cases"]

    first = [
        evaluate_case(generator, stage02f, stage02g, case, candidate, config)
        for candidate in candidates
        for case in cases
    ]
    second = [
        evaluate_case(generator, stage02f, stage02g, case, candidate, config)
        for candidate in candidates
        for case in cases
    ]
    repeat: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        left = [row for row in first if row["candidate_id"] == candidate_id]
        right = [row for row in second if row["candidate_id"] == candidate_id]
        maximum = max(
            float(
                np.max(
                    np.abs(
                        np.asarray(left_row["a_reference"], dtype=np.float64)
                        - np.asarray(right_row["a_reference"], dtype=np.float64)
                    )
                )
            )
            for left_row, right_row in zip(left, right)
        )
        repeat[candidate_id] = {
            "canonical_records_equal": canonical_bytes(left) == canonical_bytes(right),
            "maximum_repeat_Linf": maximum,
        }
    if not all(row["canonical_records_equal"] for row in repeat.values()):
        raise RuntimeError("Deterministic reference repeat failed")

    cross = cross_reference_analysis(first, candidates, rules)
    bias = bias_analysis(first, candidates)
    acceptance = acceptance_analysis(first, candidates, cross, rules, repeat)
    current_records = [row for row in first if row["candidate_id"] == "H_REF_QWLS2_INCUMBENT"]
    stage02g_bias = load_json(STAGE02G_BIAS_PATH)
    stage02g_closure = load_json(STAGE02G_CLOSURE_PATH)
    current_r2s = {
        "requested_identity_alias": matrix["requested_incumbent_alias"],
        "resolved_identity": matrix["resolved_incumbent_identity"],
        "Stage02G_bias_failure_retained": True,
        "Stage02G_bias_audit_status": stage02g_bias["bias_audit_status"],
        "Stage02G_maximum_bias_to_target_ratio": stage02g_bias["r2s_reconstruction_bias"][
            "maximum_resolution_path_bias_to_target_L2_ratio"
        ],
        "Stage02G_closure_verdict": stage02g_closure["closure_verdict"],
        "Stage02G_artifact_hashes": {
            str(STAGE02G_BIAS_PATH.relative_to(REPO_ROOT)): file_hash(STAGE02G_BIAS_PATH),
            str(STAGE02G_CLOSURE_PATH.relative_to(REPO_ROOT)): file_hash(STAGE02G_CLOSURE_PATH),
        },
        "recomputed_case_audits": [
            {
                "case_id": row["case_id"],
                "bias_metrics": row["bias_metrics"],
                "bias_to_reference_target_L2_ratio": row["bias_to_reference_target_L2_ratio"],
                "reference_uncertainty": row["reference_uncertainty"],
                "reconstruction_residual": row["diagnostics"]["maximum_reconstruction_relative_residual"],
                "geometry_isotropy_ratio_min": row["diagnostics"]["geometry_isotropy_ratio_min"],
                "condition_number": row["diagnostics"]["maximum_condition_number"],
            }
            for row in current_records
        ],
        "acceptance_verdict": next(
            row for row in acceptance["results"] if row["candidate_id"] == "H_REF_QWLS2_INCUMBENT"
        ),
    }

    candidate_output = {
        "artifact_type": "controlled same-timestamp reference evaluations; not a target dataset",
        "matrix_hash": file_hash(MATRIX_PATH),
        "candidate_count": len(candidates),
        "case_count": len(cases),
        "records": first,
        "deterministic_repeat": repeat,
    }
    write_json_no_overwrite(CANDIDATE_RESULTS_PATH, candidate_output)
    write_json_no_overwrite(CURRENT_R2S_PATH, current_r2s)
    write_json_no_overwrite(CROSS_REFERENCE_PATH, cross)
    write_json_no_overwrite(BIAS_ANALYSIS_PATH, bias)
    write_json_no_overwrite(ACCEPTANCE_RESULTS_PATH, acceptance)

    input_paths = (
        GENERATOR_PATH,
        STAGE02F_SCRIPT_PATH,
        STAGE02G_SCRIPT_PATH,
        CONFIG_PATH,
        R2S_DESIGN_PATH,
        STAGE02G_BIAS_PATH,
        STAGE02G_CLOSURE_PATH,
        MATRIX_PATH,
        RULES_PATH,
    )
    artifact_paths = (
        CANDIDATE_RESULTS_PATH,
        CURRENT_R2S_PATH,
        CROSS_REFERENCE_PATH,
        BIAS_ANALYSIS_PATH,
        ACCEPTANCE_RESULTS_PATH,
    )
    manifest = {
        "campaign_id": matrix["campaign_id"],
        "input_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in input_paths},
        "output_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in artifact_paths},
        "determinism": repeat,
        "provenance_complete": True,
        "failed_candidates_retained": True,
        "Stage02G_overwritten": False,
        "no_target_dataset_generated": True,
        "no_trajectory_generated": True,
        "no_split_assignment": True,
        "no_normalization": True,
        "no_model_implementation": True,
        "no_training": True,
        "no_performance_evaluation": True,
    }
    write_json_no_overwrite(MANIFEST_PATH, manifest)
    print(json.dumps(acceptance["summary"], sort_keys=True))
    print("passing_independent_pairs=" + json.dumps(cross["passing_independent_pairs"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
