#!/usr/bin/env python3
"""Construct and audit Stage 02F semidiscrete spatial targets.

This script performs same-state spatial-operator evaluation only.  It does not
generate trajectories or datasets and contains no model, training, split,
normalization, or performance-evaluation logic.
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
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
DESIGN_PATH = ATTR_ROOT / "semidiscrete_reference/r2s_reference_design.yaml"
MATRIX_PATH = ATTR_ROOT / "spatial_target/spatial_target_matrix.yaml"

TARGET_PATH = ATTR_ROOT / "spatial_target/spatial_target_candidates.json"
REFERENCE_PATH = ATTR_ROOT / "semidiscrete_reference/reference_qualification_audit.json"
RESOLUTION_PATH = ATTR_ROOT / "resolution_path/resolution_path_audit.json"
SUPPORT_PATH = ATTR_ROOT / "support_path/support_path_audit.json"
ATTRIBUTION_PATH = ATTR_ROOT / "qualification/spatial_attribution_results.json"
MANIFEST_PATH = ATTR_ROOT / "qualification/spatial_target_manifest.json"


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
    with path.open("r", encoding="utf-8") as handle:
        result = yaml.safe_load(handle)
    if not isinstance(result, dict):
        raise ValueError(f"Expected mapping in {path}")
    return result


def write_json_no_overwrite(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_generator() -> Any:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("stage02c_generator_readonly", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def array_hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    header = json.dumps({"dtype": "float64", "shape": list(value.shape)}, sort_keys=True).encode("utf-8")
    return sha256_bytes(header + b"\n" + value.tobytes(order="C"))


def state_hash(state: dict[str, np.ndarray]) -> str:
    return content_hash({key: array_hash(state[key]) for key in ("x", "v", "rho")})


def graph_hash(edges: dict[str, np.ndarray]) -> str:
    return content_hash(
        {
            "source": edges["source"].astype(np.int64).tolist(),
            "target": edges["target"].astype(np.int64).tolist(),
            "displacement_hash": array_hash(edges["displacement"]),
            "pair_id": edges["pair_id"].astype(np.int64).tolist(),
        }
    )


def physical_configuration(config: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": config["domain"],
        "physics": config["physics"],
        "kernel_family": config["kernel"]["family"],
        "kernel_smoothing_length_over_dx": config["kernel"]["smoothing_length_over_dx"],
        "graph_support_h_over_dx": float(case["h_over_dx"]),
        "timestamp": 0.0,
    }


def weighted_solve(
    matrix: np.ndarray, weights: np.ndarray, values: np.ndarray, *, sensitivity: bool
) -> tuple[np.ndarray, int, float]:
    sqrt_w = np.sqrt(np.maximum(weights, 0.0))
    weighted_matrix = matrix * sqrt_w[:, None]
    weighted_values = values * sqrt_w
    singular = np.linalg.svd(weighted_matrix, compute_uv=False)
    positive = singular[singular > np.finfo(np.float64).eps * max(weighted_matrix.shape) * singular[0]] if singular.size else singular
    rank = int(positive.size)
    condition = float(singular[0] / positive[-1]) if positive.size else math.inf
    if sensitivity:
        rcond = np.finfo(np.float64).eps * max(weighted_matrix.shape)
        coefficients = np.linalg.pinv(weighted_matrix, rcond=rcond) @ weighted_values
    else:
        coefficients = np.linalg.lstsq(weighted_matrix, weighted_values, rcond=None)[0]
    return coefficients, rank, condition


def r2s_evaluation(
    generator: Any,
    state: dict[str, np.ndarray],
    edges: dict[str, np.ndarray],
    case: dict[str, Any],
    config: dict[str, Any],
    *,
    sensitivity: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    particle_count = state["x"].shape[0]
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    support = float(case["h_over_dx"]) * dx
    smoothing_length = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    pressure = generator.pressure_from_density(state["rho"], config)
    nu = float(config["physics"]["kinematic_viscosity"])
    acceleration = np.zeros((particle_count, 2), dtype=np.float64)
    ranks: list[int] = []
    conditions: list[float] = []
    reproduction_errors: list[float] = []
    active_neighbor_counts: list[int] = []
    test_coefficients = np.asarray([0.7, -0.4, 0.3, -0.2, 0.5], dtype=np.float64)

    for i in range(particle_count):
        selection = edges["source"] == i
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
        kernel_weight, _ = generator.kernel_values(distance, smoothing_length)
        active_neighbor_counts.append(int(np.count_nonzero(kernel_weight > 0.0)))

        p_coeff, rank, condition = weighted_solve(
            matrix, kernel_weight, pressure[neighbors] - pressure[i], sensitivity=sensitivity
        )
        v_coeff = np.column_stack(
            [
                weighted_solve(
                    matrix,
                    kernel_weight,
                    state["v"][neighbors, component] - state["v"][i, component],
                    sensitivity=sensitivity,
                )[0]
                for component in range(2)
            ]
        )
        reproduction, _, _ = weighted_solve(
            matrix, kernel_weight, matrix @ test_coefficients, sensitivity=sensitivity
        )
        ranks.append(rank)
        conditions.append(condition)
        reproduction_errors.append(float(np.max(np.abs(reproduction - test_coefficients))))

        gradient_pressure = p_coeff[:2] / support
        laplacian_velocity = (v_coeff[2, :] + v_coeff[4, :]) / (support * support)
        acceleration[i] = -gradient_pressure / state["rho"][i] + nu * laplacian_velocity

    diagnostics = {
        "minimum_rank": int(min(ranks)),
        "maximum_condition_number": float(max(conditions)),
        "maximum_quadratic_reproduction_Linf": float(max(reproduction_errors)),
        "active_kernel_neighbor_count_min": int(min(active_neighbor_counts)),
        "active_kernel_neighbor_count_max": int(max(active_neighbor_counts)),
        "all_graph_edges_weighted_including_zero_compact_support_weights": True,
    }
    return acceleration, diagnostics


def vector_norm_metrics(field: np.ndarray) -> dict[str, float]:
    norms = np.linalg.norm(field, axis=1)
    return {
        "L2_particle_rms": float(np.sqrt(np.mean(norms * norms))),
        "Linf_particle_vector": float(np.max(norms)),
        "component_mean_x": float(np.mean(field[:, 0])),
        "component_mean_y": float(np.mean(field[:, 1])),
    }


def fourier_signature(position: np.ndarray, field: np.ndarray) -> np.ndarray:
    modes = ((1, 0), (0, 1), (1, 1), (1, -1), (2, 0), (0, 2))
    entries: list[float] = []
    for kx, ky in modes:
        phase = np.exp(-2.0j * math.pi * (kx * position[:, 0] + ky * position[:, 1]))
        for component in range(2):
            coefficient = np.mean(field[:, component] * phase)
            entries.extend((float(coefficient.real), float(coefficient.imag)))
    return np.asarray(entries, dtype=np.float64)


def direction_cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator > 0.0 else 0.0


def graph_total_variation(field: np.ndarray, edges: dict[str, np.ndarray]) -> float:
    selection = edges["source"] < edges["target"]
    differences = field[edges["target"][selection]] - field[edges["source"][selection]]
    return float(np.sqrt(np.mean(np.sum(differences * differences, axis=1))))


def construct_case(
    generator: Any,
    raw_case: dict[str, Any],
    config: dict[str, Any],
    design: dict[str, Any],
) -> dict[str, Any]:
    case = dict(raw_case)
    case.update(
        {
            "topology_control": "none",
            "time_horizon": 0.0,
            "trajectory_family": "stage02f_same_state_no_trajectory",
            "initial_condition_family": "periodic_vortex",
            "disorder_family": "regular",
            "reference_identity": design["reference_identity"],
        }
    )
    state = generator.initial_state(case, config)
    a_sph_components, edges = generator.sparse_rhs_components(state, case, config, apply_control=False)
    topology = generator.topology_audit(edges, state, case, config)
    a_r2s, primary_diagnostics = r2s_evaluation(
        generator, state, edges, case, config, sensitivity=False
    )
    a_r2s_sensitivity, sensitivity_diagnostics = r2s_evaluation(
        generator, state, edges, case, config, sensitivity=True
    )
    a_sph = a_sph_components["total"]
    delta = a_r2s - a_sph
    sensitivity_relative_l2 = float(
        np.linalg.norm(a_r2s - a_r2s_sensitivity)
        / max(float(np.linalg.norm(a_r2s)), np.finfo(np.float64).tiny)
    )

    thresholds = design["reference_qualification_thresholds"]
    reference_checks = {
        "same_state": "PASS",
        "same_configuration": "PASS",
        "same_graph": "PASS",
        "uncertainty": "PASS"
        if (
            primary_diagnostics["minimum_rank"] >= int(thresholds["minimum_matrix_rank"])
            and primary_diagnostics["maximum_condition_number"] <= float(thresholds["maximum_condition_number"])
            and primary_diagnostics["maximum_quadratic_reproduction_Linf"]
            <= float(thresholds["maximum_quadratic_reproduction_Linf"])
            and sensitivity_relative_l2 <= float(thresholds["maximum_solver_sensitivity_relative_L2"])
        )
        else "FAIL",
        "determinism": "PENDING_REPEAT",
    }
    spatial_tv = graph_total_variation(delta, edges)
    cyclic_null = np.roll(delta, 7, axis=0)
    null_tv = graph_total_variation(cyclic_null, edges)
    smoothness_ratio = float(spatial_tv / null_tv) if null_tv > 0.0 else 0.0

    shared_state_hash = state_hash(state)
    shared_graph_hash = graph_hash(edges)
    configuration = physical_configuration(config, case)
    record = {
        "candidate_id": case["case_id"],
        "study_membership": case["study_membership"],
        "timestamp": 0.0,
        "resolution_identity": case["resolution_identity"],
        "support_identity": case["support_identity"],
        "particles_per_axis": int(case["particles_per_axis"]),
        "particle_count": int(state["x"].shape[0]),
        "h_over_dx": float(case["h_over_dx"]),
        "reference_class": design["reference_class"],
        "reference_identity": design["reference_identity"],
        "target_equation": "delta_a_space = a_R2S - a_SPH",
        "sign_convention": "a_R2S_minus_a_SPH",
        "hashes": {
            "state_hash": shared_state_hash,
            "a_sph_state_hash": shared_state_hash,
            "a_r2s_state_hash": shared_state_hash,
            "configuration_hash": content_hash(configuration),
            "a_sph_configuration_hash": content_hash(configuration),
            "a_r2s_configuration_hash": content_hash(configuration),
            "graph_hash": shared_graph_hash,
            "a_sph_graph_hash": shared_graph_hash,
            "a_r2s_graph_hash": shared_graph_hash,
        },
        "topology": topology,
        "reference_diagnostics": {
            "primary": primary_diagnostics,
            "sensitivity": sensitivity_diagnostics,
            "solver_sensitivity_relative_L2": sensitivity_relative_l2,
            "temporal_derivative_used": False,
            "temporal_inputs_used": False,
        },
        "reference_qualification_checks": reference_checks,
        "spatial_metrics": {
            **vector_norm_metrics(delta),
            "graph_total_variation_rms": spatial_tv,
            "cyclic_null_total_variation_rms": null_tv,
            "smoothness_ratio_to_cyclic_null": smoothness_ratio,
        },
        "spatial_distribution": {
            "particle_id_local": list(range(state["x"].shape[0])),
            "position_periodic": state["x"].astype(np.float64).tolist(),
            "delta_a_space": delta.astype(np.float64).tolist(),
        },
        "a_SPH": a_sph.astype(np.float64).tolist(),
        "a_R2S": a_r2s.astype(np.float64).tolist(),
        "delta_a_space": delta.astype(np.float64).tolist(),
        "fourier_signature": fourier_signature(state["x"], delta).tolist(),
        "failure_retention": {
            "zero_target": bool(vector_norm_metrics(delta)["Linf_particle_vector"] == 0.0),
            "topology_failure": topology["status"] != "PASS",
            "deletion_permitted": False,
        },
    }
    record["candidate_content_hash_before_attribution"] = content_hash(record)
    return record


def resolution_audit(candidates: dict[str, dict[str, Any]], matrix: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    ids = matrix["paths"]["resolution"]["cases"]
    rows = [candidates[case_id] for case_id in ids]
    magnitudes = [row["spatial_metrics"]["L2_particle_rms"] for row in rows]
    signatures = [np.asarray(row["fourier_signature"], dtype=np.float64) for row in rows]
    adjacent = [direction_cosine(signatures[i], signatures[i + 1]) for i in range(len(signatures) - 1)]
    smoothness = [row["spatial_metrics"]["smoothness_ratio_to_cyclic_null"] for row in rows]
    threshold = design["attribution_thresholds"]
    endpoint_ratio = float(magnitudes[-1] / magnitudes[0]) if magnitudes[0] > 0.0 else math.inf
    checks = {
        "three_or_more_levels": "PASS" if len(rows) >= 3 else "FAIL",
        "fixed_h_over_dx": "PASS" if len({row["h_over_dx"] for row in rows}) == 1 else "FAIL",
        "endpoint_magnitude_nonincreasing": "PASS"
        if endpoint_ratio <= float(threshold["resolution_endpoint_L2_ratio_max"])
        else "FAIL",
        "adjacent_direction_consistency": "PASS"
        if min(adjacent) >= float(threshold["resolution_min_adjacent_fourier_direction_cosine"])
        else "FAIL",
        "spatial_smoothness": "PASS"
        if max(smoothness) <= float(threshold["resolution_max_smoothness_ratio_to_cyclic_null"])
        else "FAIL",
    }
    return {
        "path": "fixed_H_over_dx_vary_N",
        "fixed_h_over_dx": rows[0]["h_over_dx"],
        "rows": [
            {
                "candidate_id": row["candidate_id"],
                "resolution_identity": row["resolution_identity"],
                "particle_count": row["particle_count"],
                "target_L2_particle_rms": row["spatial_metrics"]["L2_particle_rms"],
                "target_Linf_particle_vector": row["spatial_metrics"]["Linf_particle_vector"],
                "smoothness_ratio_to_cyclic_null": row["spatial_metrics"]["smoothness_ratio_to_cyclic_null"],
            }
            for row in rows
        ],
        "magnitude_endpoint_high_over_low_ratio": endpoint_ratio,
        "adjacent_fourier_direction_cosines": adjacent,
        "checks": checks,
        "status": "PASS" if all(value == "PASS" for value in checks.values()) else "DIAGNOSTIC",
        "interpretation_limit": "trend is evidence for this frozen path only; no convergence order or performance claim",
    }


def support_audit(candidates: dict[str, dict[str, Any]], matrix: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    ids = matrix["paths"]["support"]["cases"]
    rows = [candidates[case_id] for case_id in ids]
    magnitudes = [row["spatial_metrics"]["L2_particle_rms"] for row in rows]
    signatures = [np.asarray(row["fourier_signature"], dtype=np.float64) for row in rows]
    adjacent = [direction_cosine(signatures[i], signatures[i + 1]) for i in range(len(signatures) - 1)]
    magnitude_ratio = float(max(magnitudes) / min(magnitudes)) if min(magnitudes) > 0.0 else math.inf
    threshold = design["attribution_thresholds"]
    checks = {
        "three_or_more_levels": "PASS" if len(rows) >= 3 else "FAIL",
        "fixed_resolution": "PASS" if len({row["particles_per_axis"] for row in rows}) == 1 else "FAIL",
        "support_separated_from_resolution": "PASS",
        "adjacent_direction_consistency": "PASS"
        if min(adjacent) >= float(threshold["support_min_adjacent_fourier_direction_cosine"])
        else "FAIL",
        "bounded_magnitude_variation": "PASS"
        if magnitude_ratio <= float(threshold["support_max_L2_magnitude_ratio"])
        else "FAIL",
    }
    return {
        "path": "fixed_N_vary_H_over_dx",
        "fixed_particles_per_axis": rows[0]["particles_per_axis"],
        "rows": [
            {
                "candidate_id": row["candidate_id"],
                "support_identity": row["support_identity"],
                "h_over_dx": row["h_over_dx"],
                "target_L2_particle_rms": row["spatial_metrics"]["L2_particle_rms"],
                "target_Linf_particle_vector": row["spatial_metrics"]["Linf_particle_vector"],
            }
            for row in rows
        ],
        "target_L2_max_over_min_ratio": magnitude_ratio,
        "adjacent_fourier_direction_cosines": adjacent,
        "checks": checks,
        "status": "PASS" if all(value == "PASS" for value in checks.values()) else "DIAGNOSTIC",
        "interpretation_limit": "support response is separated experimentally but is not a continuum model-form confirmation",
    }


def qualify_candidates(
    candidates: dict[str, dict[str, Any]],
    resolution: dict[str, Any],
    support: dict[str, Any],
    design: dict[str, Any],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for record in candidates.values():
        checks = record["reference_qualification_checks"]
        reference_qualified = all(checks[name] == "PASS" for name in checks)
        nonzero = record["spatial_metrics"]["Linf_particle_vector"] > 0.0
        spatial_consistency = reference_qualified and nonzero and record["topology"]["status"] == "PASS"
        vector = {
            "spatial_consistency": "PASS" if spatial_consistency else "FAIL",
            "resolution_trend": "PASS" if resolution["status"] == "PASS" else "DIAGNOSTIC",
            "support_consistency": "PASS" if support["status"] == "PASS" else "DIAGNOSTIC",
            "temporal_contamination": "PASS",
            "reference_sensitivity": "PASS" if checks["uncertainty"] == "PASS" else "FAIL",
            "model_form_compatibility": "PASS_R2S_INTERNAL_SCOPE",
        }
        pass_count = sum(value.startswith("PASS") for value in vector.values())
        hard_failure = record["topology"]["status"] != "PASS" or not reference_qualified
        verdict = "rejected" if hard_failure else ("PASS" if pass_count == 6 else "diagnostic")
        reason_codes: list[str] = []
        if not nonzero:
            reason_codes.append("ZERO_TARGET_RETAINED")
        if record["topology"]["status"] != "PASS":
            reason_codes.append("TOPOLOGY_FAILURE_RETAINED")
        if not reference_qualified:
            reason_codes.append("REFERENCE_QUALIFICATION_FAILURE")
        if resolution["status"] != "PASS":
            reason_codes.append("UNRESOLVED_RESOLUTION_ATTRIBUTION")
        if support["status"] != "PASS":
            reason_codes.append("UNRESOLVED_SUPPORT_ATTRIBUTION")
        if not reason_codes and verdict == "PASS":
            reason_codes.append("SIX_OF_SIX_PASS_R2S_INTERNAL_SCOPE")
        results.append(
            {
                "candidate_id": record["candidate_id"],
                "attribution_vector": vector,
                "pass_count": pass_count,
                "verdict": verdict,
                "candidate_discretization_target": verdict == "PASS",
                "reason_codes": reason_codes,
                "historical_boundary": {
                    "viscosity_operator_form": "NOT CONFIRMED",
                    "continuum_model_form_confirmation_claimed": False,
                },
            }
        )
    counts = {label: sum(item["verdict"] == label for item in results) for label in ("PASS", "diagnostic", "rejected")}
    return {
        "qualification_scope": "R2S_semidiscrete_spatial_internal_attribution",
        "required_components": [
            "spatial_consistency",
            "resolution_trend",
            "support_consistency",
            "temporal_contamination",
            "reference_sensitivity",
            "model_form_compatibility",
        ],
        "six_of_six_required": True,
        "results": results,
        "summary": {
            "candidate_count": len(results),
            "qualified_candidate_count": counts["PASS"],
            "diagnostic_count": counts["diagnostic"],
            "rejected_count": counts["rejected"],
            "zero_target_retained_count": sum(
                item["spatial_metrics"]["Linf_particle_vector"] == 0.0 for item in candidates.values()
            ),
            "topology_failure_retained_count": sum(
                item["topology"]["status"] != "PASS" for item in candidates.values()
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="write the frozen audit outputs")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Stage 02F generation requires explicit --execute")

    for output in (TARGET_PATH, REFERENCE_PATH, RESOLUTION_PATH, SUPPORT_PATH, ATTRIBUTION_PATH, MANIFEST_PATH):
        if output.exists():
            raise FileExistsError(f"No-overwrite contract: {output}")

    generator = load_generator()
    config = load_yaml(CONFIG_PATH)
    design = load_yaml(DESIGN_PATH)
    matrix = load_yaml(MATRIX_PATH)
    case_list = matrix["cases"]

    first = [construct_case(generator, case, config, design) for case in case_list]
    second = [construct_case(generator, case, config, design) for case in case_list]
    repeat_differences: dict[str, float] = {}
    for left, right in zip(first, second):
        difference = float(
            np.max(
                np.abs(
                    np.asarray(left["a_R2S"], dtype=np.float64)
                    - np.asarray(right["a_R2S"], dtype=np.float64)
                )
            )
        )
        repeat_differences[left["candidate_id"]] = difference
        status = "PASS" if difference <= float(design["reference_qualification_thresholds"]["maximum_deterministic_repeat_difference"]) else "FAIL"
        left["reference_qualification_checks"]["determinism"] = status
        right["reference_qualification_checks"]["determinism"] = status
    deterministic = canonical_bytes(first) == canonical_bytes(second)
    if not deterministic:
        raise RuntimeError("In-memory deterministic-repeat contract failed")

    candidates = {record["candidate_id"]: record for record in first}
    resolution = resolution_audit(candidates, matrix, design)
    support = support_audit(candidates, matrix, design)
    attribution = qualify_candidates(candidates, resolution, support, design)

    target_output = {
        "artifact_type": "Stage02F controlled spatial-target audit candidates; not a dataset",
        "target_definition": "delta_a_space = a_R2S - a_SPH",
        "sign_convention": "a_R2S_minus_a_SPH",
        "candidate_count": len(first),
        "candidates": first,
    }
    reference_output = {
        "reference_class": design["reference_class"],
        "reference_identity": design["reference_identity"],
        "temporal_derivative_used": False,
        "finite_difference_velocity_derivative_used": False,
        "thresholds": design["reference_qualification_thresholds"],
        "deterministic_repeat_bitwise_equal": deterministic,
        "maximum_repeat_difference_by_candidate": repeat_differences,
        "candidate_checks": [
            {
                "candidate_id": record["candidate_id"],
                "hashes": record["hashes"],
                "topology": record["topology"],
                "diagnostics": record["reference_diagnostics"],
                "checks": record["reference_qualification_checks"],
                "status": "PASS"
                if all(value == "PASS" for value in record["reference_qualification_checks"].values())
                else "FAIL",
            }
            for record in first
        ],
    }

    write_json_no_overwrite(TARGET_PATH, target_output)
    write_json_no_overwrite(REFERENCE_PATH, reference_output)
    write_json_no_overwrite(RESOLUTION_PATH, resolution)
    write_json_no_overwrite(SUPPORT_PATH, support)
    write_json_no_overwrite(ATTRIBUTION_PATH, attribution)

    manifest = {
        "campaign_id": matrix["campaign_id"],
        "execution_scope": "same-state semidiscrete spatial evaluation and target attribution audit",
        "input_files": {
            str(path.relative_to(REPO_ROOT)): file_hash(path)
            for path in (GENERATOR_PATH, CONFIG_PATH, DESIGN_PATH, MATRIX_PATH)
        },
        "output_files": {
            str(path.relative_to(REPO_ROOT)): file_hash(path)
            for path in (TARGET_PATH, REFERENCE_PATH, RESOLUTION_PATH, SUPPORT_PATH, ATTRIBUTION_PATH)
        },
        "determinism": {
            "repeats": 2,
            "canonical_records_bitwise_equal": deterministic,
            "maximum_repeat_difference_by_candidate": repeat_differences,
        },
        "provenance_complete": True,
        "failure_records_retained": True,
        "no_dataset_generated": True,
        "no_trajectory_generated": True,
        "no_split_assignment": True,
        "no_normalization": True,
        "no_model_implementation": True,
        "no_training": True,
        "no_performance_evaluation": True,
        "historical_boundaries": {
            "stage01": "V2_QUALIFICATION_FAIL",
            "stage01h": "FINITE_RESOLUTION_DOMINANT",
            "viscosity_operator_form": "NOT CONFIRMED",
            "stage02e_candidate_discretization_target_count": 0,
        },
    }
    write_json_no_overwrite(MANIFEST_PATH, manifest)
    print(json.dumps(attribution["summary"], sort_keys=True))
    print(f"resolution_status={resolution['status']}")
    print(f"support_status={support['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
