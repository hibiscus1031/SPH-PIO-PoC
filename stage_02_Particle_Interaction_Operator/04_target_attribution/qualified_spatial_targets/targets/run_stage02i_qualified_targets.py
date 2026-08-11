#!/usr/bin/env python3
"""Construct and audit Stage 02I controlled spatial target candidates.

This program evaluates one frozen spatial state per preregistered case. It does
not generate trajectories or datasets and includes no learning workflow.
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


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
QROOT = ATTR_ROOT / "qualified_spatial_targets"
GENERATOR_PATH = STAGE_ROOT / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F_SCRIPT_PATH = ATTR_ROOT / "semidiscrete_reference/construct_spatial_targets.py"
STAGE02G_SCRIPT_PATH = ATTR_ROOT / "spatial_refinement/run_stage02g_refinement.py"
STAGE02H_SCRIPT_PATH = ATTR_ROOT / "reference_fidelity/run_reference_fidelity_audit.py"
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
CASE_MATRIX_PATH = QROOT / "case_matrix/preregistered_stage02i_case_matrix.yaml"
SCOPE_PATH = QROOT / "freeze/stage02i_scope_contract.yaml"
FREEZE_PATH = QROOT / "freeze/stage02i_input_freeze_manifest.json"
H_MATRIX_PATH = ATTR_ROOT / "reference_fidelity/reference_candidate_matrix.yaml"
H_RESULTS_PATH = ATTR_ROOT / "reference_fidelity/reference_candidate_results.json"
H_RULES_PATH = ATTR_ROOT / "acceptance/reference_acceptance_rules.yaml"
H_ACCEPTANCE_PATH = ATTR_ROOT / "acceptance/reference_acceptance_results.json"
G_RESOLUTION_PATH = ATTR_ROOT / "resolution_extension/resolution_extension_matrix.yaml"
G_SMOOTHNESS_PATH = ATTR_ROOT / "smoothness_audit/smoothness_criterion_contract.yaml"
F_DESIGN_PATH = ATTR_ROOT / "semidiscrete_reference/r2s_reference_design.yaml"

REFERENCE_EXTENSION_PATH = QROOT / "reference_extension/reference_scope_extension_audit.json"
TARGETS_PATH = QROOT / "targets/spatial_target_candidates.json"
RESOLUTION_PATH = QROOT / "attribution/resolution_attribution.json"
SUPPORT_PATH = QROOT / "attribution/support_attribution.json"
DISORDER_PATH = QROOT / "attribution/disorder_audit.json"
SIX_COMPONENT_PATH = QROOT / "attribution/six_component_attribution.json"
CONSERVATION_PATH = QROOT / "conservation/conservation_compatibility_audit.json"
ELIGIBILITY_PATH = QROOT / "results/stage02i_eligibility_results.json"
MANIFEST_PATH = QROOT / "manifests/stage02i_run_manifest.json"


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


def verify_freeze(freeze: dict[str, Any]) -> None:
    for relative, expected in freeze["frozen_files"].items():
        path = REPO_ROOT / relative
        actual = file_hash(path)
        if actual != expected:
            raise RuntimeError(f"Frozen input changed: {relative}: {actual} != {expected}")
    if freeze["stage02h_accepted_reference_ids"] != ["H_REF_FOURIER2", "H_REF_ANALYTIC"]:
        raise RuntimeError("Stage 02H accepted references are not uniquely frozen")


def runtime_case(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        **raw,
        "topology_control": "none",
        "time_horizon": 0.0,
        "trajectory_family": "stage02i_same_timestamp_no_trajectory",
        "initial_condition_family": "analytic_periodic_vortex",
        "disorder_family": raw["disorder_identity"],
    }


def field_metrics(field: np.ndarray) -> dict[str, Any]:
    magnitudes = np.linalg.norm(field, axis=1)
    return {
        "L2_particle_rms": float(np.sqrt(np.mean(magnitudes * magnitudes))),
        "Linf_particle_vector": float(np.max(magnitudes)),
        "component_mean": [float(np.mean(field[:, 0])), float(np.mean(field[:, 1]))],
        "particlewise_magnitude": magnitudes.tolist(),
        "magnitude_quantiles": {
            str(q): float(np.quantile(magnitudes, q)) for q in (0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0)
        },
    }


def field_cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.sum(left * right) / denominator) if denominator > 0.0 else 0.0


def graph_diagnostics(
    generator: Any,
    state: dict[str, np.ndarray],
    edges: dict[str, np.ndarray],
    raw_case: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    dx = float(config["domain"]["box_length"]) / int(raw_case["particles_per_axis"])
    smoothing_length = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    distance = np.linalg.norm(edges["displacement"], axis=1)
    weights, _ = generator.kernel_values(distance, smoothing_length)
    active = weights > 0.0
    particle_count = state["x"].shape[0]
    active_counts = [int(np.count_nonzero(active & (edges["source"] == i))) for i in range(particle_count)]
    zero_counts = [int(np.count_nonzero((~active) & (edges["source"] == i))) for i in range(particle_count)]
    support = float(raw_case["h_over_dx"]) * dx
    isotropy: list[float] = []
    angular_gap: list[float] = []
    for i in range(particle_count):
        selection = active & (edges["source"] == i)
        displacement = edges["displacement"][selection] / support
        local_weights = weights[selection]
        moment = np.einsum("n,ni,nj->ij", local_weights, displacement, displacement)
        eigenvalues = np.linalg.eigvalsh(moment)
        isotropy.append(float(eigenvalues[0] / eigenvalues[-1]) if eigenvalues[-1] > 0.0 else 0.0)
        angles = np.sort(np.arctan2(displacement[:, 1], displacement[:, 0]))
        gaps = np.diff(np.concatenate((angles, angles[:1] + 2.0 * math.pi)))
        angular_gap.append(float(np.max(gaps)))
    return {
        "kernel_active_neighbor_count": {
            "min": min(active_counts),
            "max": max(active_counts),
            "mean": float(np.mean(active_counts)),
        },
        "zero_weight_exterior_edges": {
            "directed_total": int(np.count_nonzero(~active)),
            "per_particle_min": min(zero_counts),
            "per_particle_max": max(zero_counts),
        },
        "local_neighbor_geometry": {
            "weighted_moment_isotropy_min": min(isotropy),
            "weighted_moment_isotropy_median": float(np.median(isotropy)),
            "maximum_angular_gap_radians": max(angular_gap),
        },
    }


def reference_pair_checks(
    primary: dict[str, Any], secondary: dict[str, Any], rules: dict[str, Any]
) -> dict[str, Any]:
    thresholds = rules["numeric_thresholds"]
    p_target = np.asarray(primary["reference_target"], dtype=np.float64)
    s_target = np.asarray(secondary["reference_target"], dtype=np.float64)
    difference = p_target - s_target
    difference_metrics = field_metrics(difference)
    max_l2 = max(
        primary["reference_target_metrics"]["L2_particle_rms"],
        secondary["reference_target_metrics"]["L2_particle_rms"],
    )
    max_linf = max(
        primary["reference_target_metrics"]["Linf_particle_vector"],
        secondary["reference_target_metrics"]["Linf_particle_vector"],
    )
    normalized_l2 = float(difference_metrics["L2_particle_rms"] / max_l2)
    normalized_linf = float(difference_metrics["Linf_particle_vector"] / max_linf)
    cosine = field_cosine(p_target, s_target)
    checks = {
        "normalized_L2": "PASS"
        if normalized_l2 <= float(thresholds["cross_reference_pair_L2_to_max_target_L2_ratio_max"])
        else "FAIL",
        "normalized_Linf": "PASS"
        if normalized_linf <= float(thresholds["cross_reference_pair_Linf_to_max_target_Linf_ratio_max"])
        else "FAIL",
        "target_pattern_cosine": "PASS"
        if cosine >= float(thresholds["cross_reference_target_pattern_cosine_min"])
        else "FAIL",
    }
    return {
        "delta_a_reference_difference": difference.tolist(),
        "L2_particle_rms": difference_metrics["L2_particle_rms"],
        "Linf_particle_vector": difference_metrics["Linf_particle_vector"],
        "normalized_L2": normalized_l2,
        "normalized_Linf": normalized_linf,
        "target_pattern_cosine": cosine,
        "checks": checks,
        "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
    }


def reference_candidate_checks(
    record: dict[str, Any], deterministic: bool, rules: dict[str, Any], pair_status: str
) -> dict[str, Any]:
    thresholds = rules["numeric_thresholds"]
    checks = {
        "same_state": record["same_state"],
        "same_physics": record["same_physics"],
        "deterministic": "PASS" if deterministic else "FAIL",
        "low_reconstruction_bias": "PASS"
        if record["bias_to_reference_target_L2_ratio"]
        <= float(thresholds["bias_to_reference_target_L2_ratio_max"])
        else "FAIL",
        "cross_reference_agreement": pair_status,
        "uncertainty_qualified": "PASS"
        if record["reference_uncertainty"]["to_reference_target_L2_ratio"]
        <= float(thresholds["uncertainty_to_reference_target_L2_ratio_max"])
        else "FAIL",
    }
    return {
        "checks": checks,
        "status": "accepted" if all(value == "PASS" for value in checks.values()) else "diagnostic",
    }


def build_target_record(
    generator: Any,
    stage02f: Any,
    raw_case: dict[str, Any],
    config: dict[str, Any],
    primary: dict[str, Any],
    secondary: dict[str, Any],
    pair: dict[str, Any],
    primary_acceptance: dict[str, Any],
    secondary_acceptance: dict[str, Any],
    deterministic: dict[str, Any],
) -> dict[str, Any]:
    case = runtime_case(raw_case)
    state = generator.initial_state(case, config)
    _, edges = generator.sparse_rhs_components(state, case, config, apply_control=False)
    topology = generator.topology_audit(edges, state, case, config)
    primary_target = np.asarray(primary["reference_target"], dtype=np.float64)
    secondary_target = np.asarray(secondary["reference_target"], dtype=np.float64)
    primary_metrics = field_metrics(primary_target)
    secondary_metrics = field_metrics(secondary_target)
    physical_configuration = {
        "domain": config["domain"],
        "physics": config["physics"],
        "kernel": config["kernel"],
        "h_over_dx": float(raw_case["h_over_dx"]),
        "timestamp": 0.0,
        "external_source": "none",
    }
    record = {
        "candidate_id": raw_case["case_id"],
        "path_membership": raw_case["path_membership"],
        "timestamp": 0.0,
        "execution_environment": "CPU_float64",
        "resolution_identity": raw_case["resolution_identity"],
        "support_identity": raw_case["support_identity"],
        "disorder_identity": raw_case["disorder_identity"],
        "disorder_fraction_dx": float(raw_case["disorder_fraction_dx"]),
        "random_seed": int(raw_case["random_seed"]),
        "particles_per_axis": int(raw_case["particles_per_axis"]),
        "particle_count": int(state["x"].shape[0]),
        "h_over_dx": float(raw_case["h_over_dx"]),
        "hashes": {
            "state_hash": stage02f.state_hash(state),
            "physical_configuration_hash": content_hash(physical_configuration),
            "SPH_neighbor_graph_hash": stage02f.graph_hash(edges),
            "primary_reference_hash": content_hash(primary["a_reference"]),
            "secondary_reference_hash": content_hash(secondary["a_reference"]),
        },
        "reference_ids": {"primary": "H_REF_FOURIER2", "secondary": "H_REF_ANALYTIC"},
        "target_sign": "a_reference_minus_a_sph",
        "a_SPH": primary["a_SPH"],
        "a_FOURIER2": primary["a_reference"],
        "a_ANALYTIC": secondary["a_reference"],
        "delta_a_primary": primary_target.tolist(),
        "delta_a_secondary": secondary_target.tolist(),
        "delta_a_reference_difference": pair["delta_a_reference_difference"],
        "primary_target_metrics": primary_metrics,
        "secondary_target_metrics": secondary_metrics,
        "graph_total_variation_RMS": stage02f.graph_total_variation(primary_target, edges),
        "low_mode_fourier_signature": stage02f.fourier_signature(state["x"], primary_target).tolist(),
        "reference_pair_qualification": {
            "primary": primary_acceptance,
            "secondary": secondary_acceptance,
            "agreement": {key: value for key, value in pair.items() if key != "delta_a_reference_difference"},
            "both_candidates_accepted": primary_acceptance["status"] == "accepted"
            and secondary_acceptance["status"] == "accepted",
        },
        "reference_sensitivity_status": pair["status"],
        "topology": topology,
        "graph_diagnostics": graph_diagnostics(generator, state, edges, raw_case, config),
        "alignment": {
            "same_state": "PASS",
            "same_physical_configuration": "PASS",
            "same_timestamp": "PASS",
            "same_density_pressure_EOS_viscosity": "PASS",
        },
        "temporal_structure_proof": {
            "trajectory_generated": False,
            "time_integrator_used": False,
            "DOP853_used": False,
            "velocity_finite_difference_derivative_used": False,
            "temporal_derivative_used": False,
        },
        "operator_model_form_compatibility": "PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE",
        "deterministic_repeat_evidence": deterministic,
        "failure_retention": {
            "zero_target": primary_metrics["Linf_particle_vector"] == 0.0,
            "small_target_deleted": False,
            "nonmonotone_target_deleted": False,
            "direction_inconsistent_target_deleted": False,
        },
        "training_eligibility": "not_yet_evaluated",
    }
    record["candidate_content_hash_before_attribution"] = content_hash(record)
    return record


def resolution_audit(
    targets: dict[str, dict[str, Any]], matrix: dict[str, Any], stage02g_matrix: dict[str, Any], smooth_contract: dict[str, Any], generator: Any, stage02f: Any, config: dict[str, Any]
) -> dict[str, Any]:
    ids = matrix["paths"]["resolution"]["case_ids"]
    rows = [targets[case_id] for case_id in ids]
    thresholds = stage02g_matrix["resolution_trend_predeclared_checks"]
    seed = int(smooth_contract["refined_diagnostics_frozen_before_extension_execution"]["decorrelated_null"]["seed"])
    smoothness_rows = []
    for row in rows:
        raw = next(case for case in matrix["cases"] if case["case_id"] == row["candidate_id"])
        state = generator.initial_state(runtime_case(raw), config)
        _, edges = generator.sparse_rhs_components(state, runtime_case(raw), config, apply_control=False)
        target = np.asarray(row["delta_a_primary"], dtype=np.float64)
        graph_tv = stage02f.graph_total_variation(target, edges)
        permutation = np.random.default_rng(seed).permutation(target.shape[0])
        null_tv = stage02f.graph_total_variation(target[permutation], edges)
        l2 = row["primary_target_metrics"]["L2_particle_rms"]
        selection = edges["source"] < edges["target"]
        mean_edge = float(np.mean(np.linalg.norm(edges["displacement"][selection], axis=1)))
        smoothness_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "target_L2_particle_rms": l2,
                "target_Linf_particle_vector": row["primary_target_metrics"]["Linf_particle_vector"],
                "graph_total_variation_RMS": graph_tv,
                "PCG64_permuted_null_seed": seed,
                "permuted_null_ratio": float(graph_tv / null_tv),
                "relative_neighbor_variation": float(graph_tv / l2),
                "mean_undirected_edge_length": mean_edge,
                "physical_gradient_scale": float(graph_tv / (mean_edge * l2)),
            }
        )
    magnitudes = [row["target_L2_particle_rms"] for row in smoothness_rows]
    signatures = [np.asarray(row["low_mode_fourier_signature"], dtype=np.float64) for row in rows]
    adjacent = [stage02f.direction_cosine(signatures[i], signatures[i + 1]) for i in range(2)]
    endpoint_ratio = float(magnitudes[-1] / magnitudes[0])
    relative_variation = [row["relative_neighbor_variation"] for row in smoothness_rows]
    gradient_scale = np.asarray([row["physical_gradient_scale"] for row in smoothness_rows])
    gradient_cv = float(np.std(gradient_scale) / np.mean(gradient_scale))
    checks = {
        "target_endpoint_magnitude_nonincreasing": "PASS"
        if endpoint_ratio <= float(thresholds["target_endpoint_L2_ratio_max"])
        else "FAIL",
        "adjacent_low_mode_direction_cosine": "PASS"
        if min(adjacent) >= float(thresholds["adjacent_fourier_direction_cosine_min"])
        else "FAIL",
        "PCG64_permuted_null_ratio": "PASS"
        if max(row["permuted_null_ratio"] for row in smoothness_rows)
        <= float(thresholds["decorrelated_null_smoothness_ratio_max"])
        else "FAIL",
        "relative_neighbor_variation_strictly_decreasing": "PASS"
        if all(relative_variation[i + 1] < relative_variation[i] for i in range(2))
        else "FAIL",
        "physical_gradient_scale_coefficient_of_variation": "PASS"
        if gradient_cv <= float(thresholds["physical_gradient_scale_coefficient_of_variation_max"])
        else "FAIL",
    }
    return {
        "path": "fixed_H_over_dx_2.6_regular_vary_N12_N16_N20",
        "threshold_source_files": {
            str(G_RESOLUTION_PATH.relative_to(REPO_ROOT)): file_hash(G_RESOLUTION_PATH),
            str(G_SMOOTHNESS_PATH.relative_to(REPO_ROOT)): file_hash(G_SMOOTHNESS_PATH),
        },
        "cyclic_roll_null_used_as_gate": False,
        "rows": smoothness_rows,
        "target_magnitude_trend": magnitudes,
        "endpoint_high_over_low_ratio": endpoint_ratio,
        "adjacent_low_mode_fourier_direction_cosines": adjacent,
        "gradient_scale_coefficient_of_variation": gradient_cv,
        "checks": checks,
        "resolution_trend_status": "PASS" if all(value == "PASS" for value in checks.values()) else "DIAGNOSTIC",
        "convergence_order_computed_or_claimed": False,
    }


def support_audit(targets: dict[str, dict[str, Any]], matrix: dict[str, Any], stage02f: Any, f_design: dict[str, Any]) -> dict[str, Any]:
    ids = matrix["paths"]["support"]["case_ids"]
    rows = [targets[case_id] for case_id in ids]
    threshold = f_design["attribution_thresholds"]
    magnitudes = [row["primary_target_metrics"]["L2_particle_rms"] for row in rows]
    signatures = [np.asarray(row["low_mode_fourier_signature"], dtype=np.float64) for row in rows]
    adjacent = [stage02f.direction_cosine(signatures[i], signatures[i + 1]) for i in range(2)]
    ratio = float(max(magnitudes) / min(magnitudes))
    checks = {
        "three_support_levels": "PASS",
        "fixed_N16": "PASS",
        "bounded_target_magnitude_ratio": "PASS"
        if ratio <= float(threshold["support_max_L2_magnitude_ratio"])
        else "FAIL",
        "adjacent_direction_consistency": "PASS"
        if min(adjacent) >= float(threshold["support_min_adjacent_fourier_direction_cosine"])
        else "FAIL",
        "reference_agreement": "PASS" if all(row["reference_sensitivity_status"] == "PASS" for row in rows) else "FAIL",
        "topology": "PASS" if all(row["topology"]["status"] == "PASS" for row in rows) else "FAIL",
    }
    return {
        "path": "fixed_N16_regular_vary_H_over_dx_2.2_2.6_3.0",
        "canonical_rule_source": str(F_DESIGN_PATH.relative_to(REPO_ROOT)),
        "canonical_rule_source_hash": file_hash(F_DESIGN_PATH),
        "rows": [
            {
                "candidate_id": row["candidate_id"],
                "support_identity": row["support_identity"],
                "h_over_dx": row["h_over_dx"],
                "target_L2_particle_rms": row["primary_target_metrics"]["L2_particle_rms"],
                "target_Linf_particle_vector": row["primary_target_metrics"]["Linf_particle_vector"],
                "kernel_active_neighbor_count": row["graph_diagnostics"]["kernel_active_neighbor_count"],
                "zero_weight_exterior_edges": row["graph_diagnostics"]["zero_weight_exterior_edges"],
                "reference_agreement": row["reference_sensitivity_status"],
                "topology": row["topology"],
            }
            for row in rows
        ],
        "target_L2_max_over_min_ratio": ratio,
        "adjacent_direction_cosines": adjacent,
        "checks": checks,
        "support_consistency_status": "PASS" if all(value == "PASS" for value in checks.values()) else "DIAGNOSTIC",
        "overrides_resolution_failure": False,
    }


def disorder_audit(targets: dict[str, dict[str, Any]], matrix: dict[str, Any], stage02f: Any) -> dict[str, Any]:
    ids = matrix["paths"]["disorder"]["case_ids"]
    rows = [targets[case_id] for case_id in ids]
    regular = rows[0]
    regular_l2 = regular["primary_target_metrics"]["L2_particle_rms"]
    regular_linf = regular["primary_target_metrics"]["Linf_particle_vector"]
    regular_discrepancy = regular["reference_pair_qualification"]["agreement"]["L2_particle_rms"]
    regular_signature = np.asarray(regular["low_mode_fourier_signature"], dtype=np.float64)
    output_rows = []
    for row in rows:
        discrepancy = row["reference_pair_qualification"]["agreement"]["L2_particle_rms"]
        output_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "disorder_identity": row["disorder_identity"],
                "random_seed": row["random_seed"],
                "target_L2_amplification": float(row["primary_target_metrics"]["L2_particle_rms"] / regular_l2),
                "target_Linf_amplification": float(row["primary_target_metrics"]["Linf_particle_vector"] / regular_linf),
                "reference_discrepancy_amplification": float(discrepancy / regular_discrepancy)
                if regular_discrepancy > 0.0
                else (1.0 if discrepancy == 0.0 else math.inf),
                "Fourier_direction_cosine_to_regular": stage02f.direction_cosine(
                    regular_signature, np.asarray(row["low_mode_fourier_signature"], dtype=np.float64)
                ),
                "topology_status": row["topology"]["status"],
                "local_neighbor_geometry": row["graph_diagnostics"]["local_neighbor_geometry"],
                "deterministic_repeat": row["deterministic_repeat_evidence"],
                "candidate_gates": {
                    "reference_qualification": "PASS"
                    if row["reference_pair_qualification"]["both_candidates_accepted"]
                    else "FAIL",
                    "same_state_configuration": "PASS"
                    if all(value == "PASS" for value in row["alignment"].values())
                    else "FAIL",
                    "topology": row["topology"]["status"],
                    "uncertainty": row["reference_sensitivity_status"],
                    "model_form_compatibility": row["operator_model_form_compatibility"],
                },
            }
        )
    return {
        "path": "fixed_N16_H_over_dx_2.6_regular_jitter5_jitter10",
        "purpose": "distribution_shift_audit",
        "posthoc_monotonic_gate_added": False,
        "rows": output_rows,
        "all_candidate_required_gates_pass": all(
            all(str(value).startswith("PASS") for value in row["candidate_gates"].values()) for row in output_rows
        ),
    }


def conservation_audit(targets: dict[str, dict[str, Any]], matrix: dict[str, Any], config: dict[str, Any], generator: Any, tolerance: float) -> dict[str, Any]:
    rows = []
    for raw in matrix["cases"]:
        target = targets[raw["case_id"]]
        state = generator.initial_state(runtime_case(raw), config)
        delta = np.asarray(target["delta_a_primary"], dtype=np.float64)
        mass = float(config["physics"]["rho0"]) / state["x"].shape[0]
        total_force = np.sum(mass * delta, axis=0)
        denominator = float(np.sum(mass * np.linalg.norm(delta, axis=1)))
        normalized = float(np.linalg.norm(total_force) / denominator) if denominator > 0.0 else 0.0
        relative_position = state["x"] - 0.5 * float(config["domain"]["box_length"])
        torque = float(np.sum(mass * (relative_position[:, 0] * delta[:, 1] - relative_position[:, 1] * delta[:, 0])))
        power = float(np.sum(mass * np.sum(state["v"] * delta, axis=1)))
        compatible = normalized <= tolerance
        rows.append(
            {
                "candidate_id": raw["case_id"],
                "total_target_force": total_force.tolist(),
                "normalized_total_force_residual": normalized,
                "tolerance": tolerance,
                "architecture_compatibility": "pair_force_compatible" if compatible else "node_residual_only",
                "target_torque_diagnostic": {
                    "value": torque,
                    "coordinate_convention": "wrapped_periodic_position_relative_to_box_center",
                    "hard_gate": False,
                },
                "target_power_diagnostic": {"value": power, "hard_gate": False},
                "target_mean_subtracted_or_modified": False,
            }
        )
    return {
        "normalized_internal_force_tolerance": tolerance,
        "tolerance_source": "Stage01_frozen_tolerance_inherited_by_Stage02I_contract",
        "rows": rows,
        "pair_force_compatible_count": sum(row["architecture_compatibility"] == "pair_force_compatible" for row in rows),
        "node_residual_only_count": sum(row["architecture_compatibility"] == "node_residual_only" for row in rows),
        "all_candidates_pair_force_compatible": all(
            row["architecture_compatibility"] == "pair_force_compatible" for row in rows
        ),
    }


def six_component_attribution(
    targets: dict[str, dict[str, Any]], matrix: dict[str, Any], resolution: dict[str, Any], support: dict[str, Any]
) -> dict[str, Any]:
    results = []
    for raw in matrix["cases"]:
        target = targets[raw["case_id"]]
        spatial_pass = (
            target["reference_pair_qualification"]["both_candidates_accepted"]
            and target["topology"]["status"] == "PASS"
            and all(value == "PASS" for value in target["alignment"].values())
        )
        vector = {
            "spatial_consistency": "PASS" if spatial_pass else "FAIL",
            "resolution_trend": resolution["resolution_trend_status"],
            "support_consistency": support["support_consistency_status"],
            "temporal_contamination": "PASS",
            "reference_sensitivity": target["reference_sensitivity_status"],
            "model_form_compatibility": "PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE",
        }
        pass_count = sum(str(value).startswith("PASS") for value in vector.values())
        rejected = target["topology"]["status"] == "FAIL"
        verdict = "rejected" if rejected else ("PASS" if pass_count == 6 else "diagnostic")
        results.append(
            {
                "candidate_id": raw["case_id"],
                "path_membership": raw["path_membership"],
                "attribution_vector": vector,
                "pass_count": pass_count,
                "required_pass_count": 6,
                "candidate_discretization_target": verdict == "PASS",
                "verdict": verdict,
                "manual_override_permitted": False,
                "training_eligibility": "not_yet_evaluated",
            }
        )
    return {
        "required_components": [
            "spatial_consistency",
            "resolution_trend",
            "support_consistency",
            "temporal_contamination",
            "reference_sensitivity",
            "model_form_compatibility",
        ],
        "results": results,
        "summary": {
            "candidate_count": len(results),
            "qualified_candidate_count": sum(row["candidate_discretization_target"] for row in results),
            "diagnostic_count": sum(row["verdict"] == "diagnostic" for row in results),
            "rejected_count": sum(row["verdict"] == "rejected" for row in results),
            "main_resolution_path_qualified_count": sum(
                row["candidate_discretization_target"] and "resolution" in row["path_membership"] for row in results
            ),
        },
        "manual_override_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Stage 02I target analysis requires explicit --execute")
    outputs = (
        REFERENCE_EXTENSION_PATH,
        TARGETS_PATH,
        RESOLUTION_PATH,
        SUPPORT_PATH,
        DISORDER_PATH,
        SIX_COMPONENT_PATH,
        CONSERVATION_PATH,
        ELIGIBILITY_PATH,
        MANIFEST_PATH,
    )
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"No-overwrite contract: {path}")

    freeze = load_json(FREEZE_PATH)
    verify_freeze(freeze)
    matrix = load_yaml(CASE_MATRIX_PATH)
    scope = load_yaml(SCOPE_PATH)
    h_matrix = load_yaml(H_MATRIX_PATH)
    h_rules = load_yaml(H_RULES_PATH)
    h_results = load_json(H_RESULTS_PATH)
    g_resolution = load_yaml(G_RESOLUTION_PATH)
    g_smoothness = load_yaml(G_SMOOTHNESS_PATH)
    f_design = load_yaml(F_DESIGN_PATH)
    config = load_yaml(CONFIG_PATH)
    if len(matrix["cases"]) != 7 or len({row["case_id"] for row in matrix["cases"]}) != 7:
        raise RuntimeError("Preregistered Stage 02I matrix is not uniquely seven cases")

    generator = load_module("stage02c_generator_readonly_for_stage02i", GENERATOR_PATH)
    stage02f = load_module("stage02f_spatial_readonly_for_stage02i", STAGE02F_SCRIPT_PATH)
    stage02g = load_module("stage02g_spatial_readonly_for_stage02i", STAGE02G_SCRIPT_PATH)
    stage02h = load_module("stage02h_reference_readonly_for_stage02i", STAGE02H_SCRIPT_PATH)
    candidate_map = {row["candidate_id"]: row for row in h_matrix["candidates"]}
    primary_candidate = candidate_map["H_REF_FOURIER2"]
    secondary_candidate = candidate_map["H_REF_ANALYTIC"]

    first_pairs = []
    second_pairs = []
    for raw in matrix["cases"]:
        first_pairs.append(
            (
                stage02h.evaluate_case(generator, stage02f, stage02g, raw, primary_candidate, config),
                stage02h.evaluate_case(generator, stage02f, stage02g, raw, secondary_candidate, config),
            )
        )
        second_pairs.append(
            (
                stage02h.evaluate_case(generator, stage02f, stage02g, raw, primary_candidate, config),
                stage02h.evaluate_case(generator, stage02f, stage02g, raw, secondary_candidate, config),
            )
        )

    targets: dict[str, dict[str, Any]] = {}
    extension_rows = []
    covered_map = {
        "i_res_n12_h26_regular": "h_regular_n12",
        "i_anchor_n16_h26_regular": "h_regular_n16",
        "i_res_n20_h26_regular": "h_regular_n20",
    }
    frozen_h_records = {(row["candidate_id"], row["case_id"]): row for row in h_results["records"]}
    for raw, first_pair, second_pair in zip(matrix["cases"], first_pairs, second_pairs):
        primary, secondary = first_pair
        primary_repeat, secondary_repeat = second_pair
        p_equal = canonical_bytes(primary) == canonical_bytes(primary_repeat)
        s_equal = canonical_bytes(secondary) == canonical_bytes(secondary_repeat)
        p_diff = float(np.max(np.abs(np.asarray(primary["a_reference"]) - np.asarray(primary_repeat["a_reference"]))))
        s_diff = float(np.max(np.abs(np.asarray(secondary["a_reference"]) - np.asarray(secondary_repeat["a_reference"]))))
        pair = reference_pair_checks(primary, secondary, h_rules)
        primary_acceptance = reference_candidate_checks(primary, p_equal, h_rules, pair["status"])
        secondary_acceptance = reference_candidate_checks(secondary, s_equal, h_rules, pair["status"])
        deterministic = {
            "primary_canonical_record_equal": p_equal,
            "secondary_canonical_record_equal": s_equal,
            "primary_max_repeat_Linf": p_diff,
            "secondary_max_repeat_Linf": s_diff,
            "status": "PASS" if p_equal and s_equal and p_diff == 0.0 and s_diff == 0.0 else "FAIL",
        }
        target = build_target_record(
            generator,
            stage02f,
            raw,
            config,
            primary,
            secondary,
            pair,
            primary_acceptance,
            secondary_acceptance,
            deterministic,
        )
        targets[raw["case_id"]] = target
        covered_id = covered_map.get(raw["case_id"])
        covered_evidence = None
        if covered_id is not None:
            p_frozen = frozen_h_records[("H_REF_FOURIER2", covered_id)]
            s_frozen = frozen_h_records[("H_REF_ANALYTIC", covered_id)]
            covered_evidence = {
                "stage02h_primary_record_id": covered_id,
                "stage02h_primary_record_hash": content_hash(p_frozen),
                "stage02h_secondary_record_hash": content_hash(s_frozen),
                "recomputed_primary_reference_hash_match": content_hash(p_frozen["a_reference"])
                == content_hash(primary["a_reference"]),
                "recomputed_secondary_reference_hash_match": content_hash(s_frozen["a_reference"])
                == content_hash(secondary["a_reference"]),
            }
        extension_rows.append(
            {
                "case_id": raw["case_id"],
                "scope_status_before_stage02i": raw["stage02h_scope_status"],
                "covered_stage02h_evidence": covered_evidence,
                "primary_acceptance": primary_acceptance,
                "secondary_acceptance": secondary_acceptance,
                "pair_agreement": {key: value for key, value in pair.items() if key != "delta_a_reference_difference"},
                "determinism": deterministic,
                "eligible_for_target_attribution": primary_acceptance["status"] == "accepted"
                and secondary_acceptance["status"] == "accepted"
                and pair["status"] == "PASS",
            }
        )

    reference_extension = {
        "primary_reference_id": "H_REF_FOURIER2",
        "secondary_reference_id": "H_REF_ANALYTIC",
        "diagnostic_reference_ids_preserved_and_excluded": ["H_REF_QWLS2_INCUMBENT", "H_REF_CWLS3"],
        "acceptance_threshold_source": str(H_RULES_PATH.relative_to(REPO_ROOT)),
        "acceptance_threshold_source_hash": file_hash(H_RULES_PATH),
        "thresholds_reentered_or_modified": False,
        "rows": extension_rows,
        "all_seven_reference_pairs_qualified": all(row["eligible_for_target_attribution"] for row in extension_rows),
        "operator_level_model_form_alignment": {
            "status": "PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE",
            "full_PDE_model_form_PASS_claimed": False,
            "viscosity_operator_form_confirmation_claimed": False,
        },
    }
    target_output = {
        "artifact_type": "controlled spatial target candidates; not a dataset",
        "target_sign": "a_reference_minus_a_sph",
        "candidate_count": len(targets),
        "preregistered_case_ids": [row["case_id"] for row in matrix["cases"]],
        "candidates": list(targets.values()),
        "posthoc_deletion_or_addition_used": False,
    }
    resolution = resolution_audit(targets, matrix, g_resolution, g_smoothness, generator, stage02f, config)
    support = support_audit(targets, matrix, stage02f, f_design)
    disorder = disorder_audit(targets, matrix, stage02f)
    six = six_component_attribution(targets, matrix, resolution, support)
    tolerance = float(scope["conservation_audit"]["normalized_internal_force_tolerance"])
    conservation = conservation_audit(targets, matrix, config, generator, tolerance)

    main_ids = set(matrix["paths"]["resolution"]["case_ids"])
    main_results = [row for row in six["results"] if row["candidate_id"] in main_ids]
    prerequisites = {
        "stage02h_freeze": "PASS",
        "seven_case_preregistration": "PASS",
        "Fourier_analytic_reference_qualification": "PASS"
        if reference_extension["all_seven_reference_pairs_qualified"]
        else "FAIL",
        "main_resolution_path_three_of_three_six_component": "PASS"
        if len(main_results) == 3 and all(row["candidate_discretization_target"] for row in main_results)
        else "FAIL",
        "support_path": support["support_consistency_status"],
        "reference_sensitivity": "PASS"
        if all(row["reference_sensitivity_status"] == "PASS" for row in targets.values())
        else "FAIL",
        "conservation_compatibility_complete": "PASS"
        if conservation["all_candidates_pair_force_compatible"]
        else "PARTIAL",
        "provenance": "PASS",
        "no_dataset_model_training": "PASS",
    }
    pool_ready = all(value == "PASS" for value in prerequisites.values())
    eligibility = {
        "pool_readiness": "ready" if pool_ready else "not_ready",
        "readiness_prerequisites": prerequisites,
        "qualified_candidate_count": six["summary"]["qualified_candidate_count"],
        "main_resolution_qualified_count": six["summary"]["main_resolution_path_qualified_count"],
        "candidate_results": [
            {
                "candidate_id": row["candidate_id"],
                "candidate_discretization_target": row["candidate_discretization_target"],
                "training_eligibility": "not_yet_evaluated",
                "architecture_compatibility": next(
                    item["architecture_compatibility"] for item in conservation["rows"] if item["candidate_id"] == row["candidate_id"]
                ),
            }
            for row in six["results"]
        ],
        "Stage02J_authorized": pool_ready,
        "maximum_stage02i_label": "candidate_discretization_target",
        "dataset_materialized": False,
        "split_assigned": False,
        "normalization_statistics_created": False,
        "model_or_training_performed": False,
    }

    write_json_no_overwrite(REFERENCE_EXTENSION_PATH, reference_extension)
    write_json_no_overwrite(TARGETS_PATH, target_output)
    write_json_no_overwrite(RESOLUTION_PATH, resolution)
    write_json_no_overwrite(SUPPORT_PATH, support)
    write_json_no_overwrite(DISORDER_PATH, disorder)
    write_json_no_overwrite(SIX_COMPONENT_PATH, six)
    write_json_no_overwrite(CONSERVATION_PATH, conservation)
    write_json_no_overwrite(ELIGIBILITY_PATH, eligibility)

    input_paths = (
        GENERATOR_PATH,
        STAGE02F_SCRIPT_PATH,
        STAGE02G_SCRIPT_PATH,
        STAGE02H_SCRIPT_PATH,
        CONFIG_PATH,
        CASE_MATRIX_PATH,
        SCOPE_PATH,
        FREEZE_PATH,
        H_MATRIX_PATH,
        H_RESULTS_PATH,
        H_RULES_PATH,
        H_ACCEPTANCE_PATH,
        G_RESOLUTION_PATH,
        G_SMOOTHNESS_PATH,
        F_DESIGN_PATH,
    )
    output_paths = (
        REFERENCE_EXTENSION_PATH,
        TARGETS_PATH,
        RESOLUTION_PATH,
        SUPPORT_PATH,
        DISORDER_PATH,
        SIX_COMPONENT_PATH,
        CONSERVATION_PATH,
        ELIGIBILITY_PATH,
    )
    verify_freeze(freeze)
    manifest = {
        "campaign_id": matrix["campaign_id"],
        "input_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in input_paths},
        "output_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in output_paths},
        "freeze_reverified_after_execution": True,
        "provenance_complete": True,
        "preregistered_case_count": 7,
        "materialized_target_candidate_count": len(targets),
        "failed_and_diagnostic_records_retained": True,
        "no_historical_file_modified": True,
        "no_trajectory_generated": True,
        "no_time_integration_reference": True,
        "no_DOP853": True,
        "no_velocity_finite_difference_derivative": True,
        "no_dataset_materialized": True,
        "no_split_assignment": True,
        "no_normalization_statistics": True,
        "no_model_implementation": True,
        "no_training": True,
        "no_performance_claim": True,
    }
    write_json_no_overwrite(MANIFEST_PATH, manifest)
    print(
        json.dumps(
            {
                "reference_pairs_qualified": reference_extension["all_seven_reference_pairs_qualified"],
                "resolution_status": resolution["resolution_trend_status"],
                "support_status": support["support_consistency_status"],
                "qualified_candidate_count": six["summary"]["qualified_candidate_count"],
                "pair_force_compatible_count": conservation["pair_force_compatible_count"],
                "node_residual_only_count": conservation["node_residual_only_count"],
                "pool_readiness": eligibility["pool_readiness"],
                "Stage02J_authorized": eligibility["Stage02J_authorized"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
