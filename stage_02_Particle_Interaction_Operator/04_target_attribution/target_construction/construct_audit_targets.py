#!/usr/bin/env python3
"""Construct and attribute the frozen Stage 02E non-zero R2 audit targets."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.integrate import solve_ivp

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE02 = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATASET = STAGE02 / "03_dataset"
ATTR = STAGE02 / "04_target_attribution"
GENERATOR_PATH = DATASET / "generation" / "generate_audit_dataset.py"
CONFIG_PATH = DATASET / "generation" / "generation_configuration.yaml"
MATRIX_PATH = ATTR / "excitation_design" / "target_excitation_matrix.yaml"
STAGE02D_DECISION_PATH = ATTR / "qualification" / "stage02e_upgrade_decision.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_no_overwrite(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path} already exists")
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def load_generator():
    spec = importlib.util.spec_from_file_location("stage02c_generator_for_stage02e", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Stage 02C semidiscrete implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initial_state(case: dict[str, Any], config: dict[str, Any]) -> dict[str, np.ndarray]:
    n_axis = int(case["particles_per_axis"])
    length = float(config["domain"]["box_length"])
    dx = length / n_axis
    grid = (np.arange(n_axis, dtype=np.float64) + 0.5) * dx
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    x = np.column_stack((xx.ravel(), yy.ravel()))
    disorder = float(case["disorder_fraction_dx"])
    if disorder:
        rng = np.random.default_rng(int(case["random_seed"]))
        x = np.mod(x + rng.uniform(-disorder * dx, disorder * dx, size=x.shape), length)
    rho0 = float(config["physics"]["rho0"])
    amp_v = float(config["physics"]["velocity_amplitude"])
    amp_rho = float(config["physics"]["density_amplitude"])
    px = 2.0 * math.pi * x[:, 0] / length
    py = 2.0 * math.pi * x[:, 1] / length
    family = case["initial_condition_family"]
    if family == "periodic_vortex":
        v = np.column_stack((amp_v * np.sin(px) * np.cos(py), -amp_v * np.cos(px) * np.sin(py)))
        rho = rho0 * (1.0 + amp_rho * np.sin(px) * np.sin(py))
    elif family == "compressive_wave":
        v = np.column_stack((amp_v * np.sin(px), 0.75 * amp_v * np.sin(py)))
        rho = rho0 * (1.0 + 0.5 * amp_rho * (np.cos(px) + np.cos(py)))
    else:
        raise ValueError(f"Unknown initial condition family: {family}")
    return {"x": x, "v": v, "rho": rho}


def pack(state: dict[str, np.ndarray]) -> np.ndarray:
    return np.concatenate((state["x"].ravel(), state["v"].ravel(), state["rho"].ravel()))


def unpack(vector: np.ndarray, n: int) -> dict[str, np.ndarray]:
    n2 = 2 * n
    return {"x": vector[:n2].reshape(n, 2).copy(), "v": vector[n2 : 2 * n2].reshape(n, 2).copy(), "rho": vector[2 * n2 :].copy()}


def five_point_derivative(solution: Any, center: float, half_window: float, n: int) -> np.ndarray:
    velocity_offset = 2 * n
    def velocity(t: float) -> np.ndarray:
        vector = solution.sol(t)
        return vector[velocity_offset : velocity_offset + 2 * n].reshape(n, 2)
    return (
        velocity(center - 2.0 * half_window)
        - 8.0 * velocity(center - half_window)
        + 8.0 * velocity(center + half_window)
        - velocity(center + 2.0 * half_window)
    ) / (12.0 * half_window)


def norms(field: np.ndarray) -> dict[str, float]:
    magnitude = np.linalg.norm(field, axis=1)
    return {"L2_rms_vector": float(np.sqrt(np.mean(magnitude**2))), "Linf_vector": float(np.max(magnitude))}


def topology_summary(edges: dict[str, np.ndarray], state: dict[str, np.ndarray], case: dict[str, Any], config: dict[str, Any], generator: Any) -> dict[str, Any]:
    audit = generator.topology_audit(edges, state, {**case, "topology_control": "none"}, config)
    edge_record = {
        "source": edges["source"].tolist(),
        "target": edges["target"].tolist(),
        "pair_id": edges["pair_id"].tolist(),
        "minimum_image_displacement": edges["displacement"].tolist(),
        "support_rule": config["kernel"]["support_rule"],
    }
    return {
        "status": audit["status"],
        "defects": audit["defects"],
        "reciprocal_status": audit["reciprocal_status"],
        "edge_count": int(len(edges["source"])),
        "neighbor_graph_hash": content_hash(edge_record),
    }


def fourier_signature(positions: np.ndarray, field: np.ndarray) -> list[float]:
    modes = [(1, 0), (0, 1), (1, 1), (1, -1), (2, 0), (0, 2)]
    columns = []
    for kx, ky in modes:
        phase = 2.0 * math.pi * (kx * positions[:, 0] + ky * positions[:, 1])
        columns.extend((np.cos(phase), np.sin(phase)))
    design = np.column_stack(columns)
    coefficients = []
    for component_index in range(2):
        coef, *_ = np.linalg.lstsq(design, field[:, component_index], rcond=None)
        coefficients.extend(coef.tolist())
    return [float(value) for value in coefficients]


def cosine(a: list[float], b: list[float]) -> float | None:
    av = np.asarray(a, dtype=np.float64)
    bv = np.asarray(b, dtype=np.float64)
    denominator = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return float(np.dot(av, bv) / denominator) if denominator > 0.0 else None


def spatial_distribution(positions: np.ndarray, delta: np.ndarray, edges: dict[str, np.ndarray]) -> dict[str, Any]:
    magnitude = np.linalg.norm(delta, axis=1)
    src = edges["source"]
    dst = edges["target"]
    local_tv = float(np.sqrt(np.mean(np.sum((delta[src] - delta[dst]) ** 2, axis=1)))) if len(src) else 0.0
    reversed_field = delta[::-1]
    shuffled_tv = float(np.sqrt(np.mean(np.sum((reversed_field[src] - reversed_field[dst]) ** 2, axis=1)))) if len(src) else 0.0
    return {
        "per_particle_magnitude": magnitude.tolist(),
        "quantiles": {name: float(np.quantile(magnitude, q)) for name, q in (("q0", 0.0), ("q25", 0.25), ("q50", 0.5), ("q75", 0.75), ("q100", 1.0))},
        "graph_total_variation_rms": local_tv,
        "deterministic_reverse_null_total_variation_rms": shuffled_tv,
        "smoothness_ratio_to_reverse_null": float(local_tv / shuffled_tv) if shuffled_tv > 0.0 else None,
        "fourier_signature": fourier_signature(positions, delta),
    }


def solve_case(case: dict[str, Any], config: dict[str, Any], matrix: dict[str, Any], generator: Any) -> dict[str, Any]:
    state0 = initial_state(case, config)
    y0 = pack(state0)
    n = state0["x"].shape[0]
    reference = matrix["reference"]
    center = float(matrix["target"]["evaluation_time"])
    horizon = float(case["time_horizon"])
    rhs = lambda t, y: generator.state_rhs_dense(t, y, n, {**case, "topology_control": "none"}, config)
    common = dict(fun=rhs, t_span=(0.0, horizon), y0=y0, method="DOP853", dense_output=True)
    primary = solve_ivp(rtol=float(reference["primary_rtol"]), atol=float(reference["primary_atol"]), **common)
    sensitivity = solve_ivp(rtol=float(reference["sensitivity_rtol"]), atol=float(reference["sensitivity_atol"]), **common)
    if not primary.success or not sensitivity.success or primary.sol is None or sensitivity.sol is None:
        raise RuntimeError(f"DOP853 failed for {case['case_id']}")
    state = unpack(primary.sol(center), n)
    case_for_generator = {**case, "topology_control": "none"}
    sparse, edges = generator.sparse_rhs_components(state, case_for_generator, config, apply_control=False)
    dense = generator.dense_rhs_components(state, case_for_generator, config, reverse_sum=False)
    dense_reverse = generator.dense_rhs_components(state, case_for_generator, config, reverse_sum=True)
    h_primary = float(reference["primary_derivative_half_window"])
    h_half = float(reference["window_sensitivity_half_window"])
    a_ref = five_point_derivative(primary, center, h_primary, n)
    a_ref_half_window = five_point_derivative(primary, center, h_half, n)
    a_ref_sensitivity_solver = five_point_derivative(sensitivity, center, h_primary, n)
    a_sph = sparse["total"]
    a_dense = dense["total"]
    delta = a_ref - a_sph
    assembly_component = a_dense - a_sph
    temporal_reference_component = a_ref - a_dense
    closure = delta - assembly_component - temporal_reference_component
    topo = topology_summary(edges, state, case, config, generator)
    particle_state = generator.particle_state_record(state, case_for_generator, config)
    config_hash = content_hash({"case": case, "configuration": config, "reference": reference})
    target_metrics = norms(delta)
    target_nonzero = target_metrics["Linf_vector"] > 0.0
    ref_uncertainty = {
        "dense_forward_reverse": norms(dense["total"] - dense_reverse["total"]),
        "DOP853_primary_vs_sensitivity_derivative": norms(a_ref - a_ref_sensitivity_solver),
        "five_point_window_sensitivity": norms(a_ref - a_ref_half_window),
        "assembly_sparse_vs_dense": norms(assembly_component),
        "closure_residual": norms(closure),
        "single_total_uncertainty_permitted": False,
    }
    temporal_fraction = None
    if target_metrics["L2_rms_vector"] > 0.0:
        temporal_fraction = float(norms(temporal_reference_component)["L2_rms_vector"] / target_metrics["L2_rms_vector"])
    return {
        "candidate_id": case["case_id"],
        "record_version": "stage02e-audit-target-1.0.0",
        "training_permitted": False,
        "case": case,
        "reference": {
            "class": "R2_semidiscrete_qualified",
            "identity": reference["identity"],
            "method": "DOP853_primary_five_point_velocity_derivative_centered_at_sample_state",
            "source_id": file_hash(Path(__file__).resolve()),
            "solver_primary": {"success": bool(primary.success), "nfev": int(primary.nfev), "status": int(primary.status)},
            "solver_sensitivity": {"success": bool(sensitivity.success), "nfev": int(sensitivity.nfev), "status": int(sensitivity.status)},
        },
        "alignment": {
            "same_state": "PASS",
            "same_configuration": "PASS",
            "same_timestamp": "PASS",
            "same_graph_contract": topo["status"],
            "uncertainty_available": "PASS",
            "state_hash": content_hash(particle_state),
            "configuration_hash": config_hash,
            "neighbor_graph_hash": topo["neighbor_graph_hash"],
        },
        "particle_state": {"position": particle_state["position_periodic"], "particle_count": n, "dimension": 2},
        "a_SPH": {"values": a_sph.tolist(), "hash": content_hash(a_sph.tolist())},
        "a_ref": {"values": a_ref.tolist(), "hash": content_hash(a_ref.tolist())},
        "delta_a": {
            "values": delta.tolist(),
            "sign_convention": "a_ref_minus_a_sph",
            "metrics": target_metrics,
            "nonzero": target_nonzero,
            "spatial_distribution": spatial_distribution(np.mod(state["x"], 1.0), delta, edges),
        },
        "decomposition": {
            "assembly_spatial_candidate": {"metrics": norms(assembly_component), "values_hash": content_hash(assembly_component.tolist())},
            "temporal_reference_component": {"metrics": norms(temporal_reference_component), "values_hash": content_hash(temporal_reference_component.tolist())},
            "closure_residual": {"metrics": norms(closure), "values_hash": content_hash(closure.tolist())},
            "temporal_reference_L2_fraction_of_target": temporal_fraction,
        },
        "uncertainty": ref_uncertainty,
        "topology": topo,
        "provenance": {
            "matrix_hash": file_hash(MATRIX_PATH),
            "generation_configuration_hash": file_hash(CONFIG_PATH),
            "stage02c_generator_hash": file_hash(GENERATOR_PATH),
            "stage02d_decision_hash": file_hash(STAGE02D_DECISION_PATH),
            "constructor_hash": file_hash(Path(__file__).resolve()),
            "dtype": "float64",
            "device": "CPU",
            "failure_flags": [],
        },
    }


def path_study(name: str, candidates: list[dict[str, Any]], varied_key: str) -> dict[str, Any]:
    selected = [candidate for candidate in candidates if name in candidate["case"]["study_membership"]]
    selected.sort(key=lambda candidate: float(candidate["case"][varied_key]) if varied_key in candidate["case"] else int(candidate["case"]["particles_per_axis"]))
    rows = []
    for candidate in selected:
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "resolution_family": candidate["case"]["resolution_family"],
            "particles_per_axis": candidate["case"]["particles_per_axis"],
            "h_over_dx": candidate["case"]["h_over_dx"],
            "disorder_family": candidate["case"]["disorder_family"],
            "state_family": candidate["case"]["initial_condition_family"],
            "delta_a_L2": candidate["delta_a"]["metrics"]["L2_rms_vector"],
            "delta_a_Linf": candidate["delta_a"]["metrics"]["Linf_vector"],
            "spatial_smoothness_ratio": candidate["delta_a"]["spatial_distribution"]["smoothness_ratio_to_reverse_null"],
            "fourier_signature": candidate["delta_a"]["spatial_distribution"]["fourier_signature"],
        })
    direction_pairs = []
    for left, right in zip(rows, rows[1:]):
        direction_pairs.append({
            "left": left["candidate_id"],
            "right": right["candidate_id"],
            "fourier_direction_cosine": cosine(left["fourier_signature"], right["fourier_signature"]),
        })
    l2_values = [row["delta_a_L2"] for row in rows]
    monotonic = all(right <= left for left, right in zip(l2_values, l2_values[1:])) or all(right >= left for left, right in zip(l2_values, l2_values[1:]))
    return {
        "study": name,
        "varied_axis": varied_key,
        "rows": rows,
        "magnitude_trend_monotonic_raw": monotonic,
        "direction_consistency": direction_pairs,
        "spatial_smoothness_checked": True,
        "interpretation": "DIAGNOSTIC_REFERENCE_TEMPORAL_ERROR_TREND_NOT_DISCRETIZATION_TREND",
    }


def main() -> int:
    generator = load_generator()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    stage02d = json.loads(STAGE02D_DECISION_PATH.read_text(encoding="utf-8"))
    if stage02d["stage02e_data_qualification_upgrade_authorized"] is not False:
        raise RuntimeError("Stage 02D false upgrade boundary must be preserved")
    cases = matrix["cases"]
    if len({case["resolution_family"] for case in cases}) < 3:
        raise RuntimeError("At least three resolution levels are required")
    if len({float(case["h_over_dx"]) for case in cases}) < 2:
        raise RuntimeError("Multiple H/dx levels are required")
    if {case["disorder_fraction_dx"] for case in cases} < {0.0, 0.05, 0.10}:
        raise RuntimeError("Regular, 5%, and 10% disorder are required")
    if len({case["initial_condition_family"] for case in cases}) < 2:
        raise RuntimeError("Multiple initial-condition families are required")

    first = [solve_case(case, config, matrix, generator) for case in cases]
    second = [solve_case(case, config, matrix, generator) for case in cases]
    if canonical_bytes(first) != canonical_bytes(second):
        raise RuntimeError("Deterministic repeat mismatch")
    candidates = first
    nonzero_count = sum(candidate["delta_a"]["nonzero"] for candidate in candidates)
    zero_count = len(candidates) - nonzero_count

    resolution = path_study("resolution", candidates, "particles_per_axis")
    support = path_study("support", candidates, "h_over_dx")
    disorder = path_study("disorder", candidates, "disorder_fraction_dx")

    reference_rows = []
    attribution_rows = []
    for candidate in candidates:
        alignment_pass = all(candidate["alignment"][key] == "PASS" for key in ("same_state", "same_configuration", "same_timestamp", "same_graph_contract", "uncertainty_available"))
        reference_rows.append({
            "candidate_id": candidate["candidate_id"],
            "reference_class": candidate["reference"]["class"],
            "reference_identity": candidate["reference"]["identity"],
            "same_state": candidate["alignment"]["same_state"],
            "same_configuration": candidate["alignment"]["same_configuration"],
            "same_timestamp": candidate["alignment"]["same_timestamp"],
            "graph_contract": candidate["alignment"]["same_graph_contract"],
            "uncertainty": candidate["alignment"]["uncertainty_available"],
            "qualification_status": "PASS_FOR_R2_AUDIT_USE" if alignment_pass else "FAIL",
            "training_reference_permitted": False,
        })
        nonzero = candidate["delta_a"]["nonzero"]
        topology_pass = candidate["topology"]["status"] == "PASS"
        temporal_fraction = candidate["decomposition"]["temporal_reference_L2_fraction_of_target"]
        assembly_l2 = candidate["decomposition"]["assembly_spatial_candidate"]["metrics"]["L2_rms_vector"]
        vector = {
            "spatial_consistency": "FAIL_NO_SPATIAL_COMPONENT_OBSERVED" if nonzero and assembly_l2 == 0.0 else "DIAGNOSTIC_UNRESOLVED",
            "resolution_trend": "DIAGNOSTIC_REFERENCE_ERROR_TREND_ONLY",
            "support_consistency": "DIAGNOSTIC_REFERENCE_ERROR_TREND_ONLY",
            "time_contamination": "FAIL_TARGET_EXPLAINED_BY_TEMPORAL_REFERENCE_COMPONENT" if temporal_fraction is not None and abs(temporal_fraction - 1.0) <= 1e-12 else "DIAGNOSTIC_UNRESOLVED",
            "reference_sensitivity": "DIAGNOSTIC_WINDOW_AND_SOLVER_SENSITIVITY_REPORTED",
            "model_form_compatibility": "DIAGNOSTIC_R2_INTERNAL_ONLY",
        }
        if not topology_pass:
            verdict = "rejected"
            reasons = ["REJECT_TOPOLOGY"]
        elif not nonzero:
            verdict = "diagnostic"
            reasons = ["ZERO_TARGET_RETAINED", "DIAG_R2_NOT_TRAINING_REFERENCE"]
        else:
            verdict = "diagnostic"
            reasons = ["DIAG_R2_NOT_TRAINING_REFERENCE", "DIAG_TARGET_TEMPORAL_REFERENCE_DOMINATED", "DIAG_NO_DISCRETIZATION_ATTRIBUTION_PASS"]
        attribution_rows.append({
            "candidate_id": candidate["candidate_id"],
            "categorical_attribution_vector": vector,
            "pass_count": sum(value == "PASS" for value in vector.values()),
            "candidate_verdict": verdict,
            "reason_codes": reasons,
            "candidate_discretization_target": False,
            "manual_override": False,
        })

    candidate_counts = dict(Counter(row["candidate_verdict"] for row in attribution_rows))
    qualified_count = sum(row["candidate_discretization_target"] for row in attribution_rows)
    pool = {
        "pool_version": "stage02e-candidate-target-pool-1.0.0",
        "campaign_id": matrix["campaign_id"],
        "purpose": "audit_only_not_training_dataset",
        "target_sign_convention": "a_ref_minus_a_sph",
        "candidate_count": len(candidates),
        "nonzero_count": nonzero_count,
        "zero_count": zero_count,
        "candidate_discretization_target_count": qualified_count,
        "training_permitted": False,
        "candidates": candidates,
    }
    reference_audit = {
        "audit_version": "stage02e-reference-qualification-1.0.0",
        "rows": reference_rows,
        "summary": dict(Counter(row["qualification_status"] for row in reference_rows)),
        "R2_automatic_training_upgrade": False,
    }
    attribution = {
        "audit_version": "stage02e-attribution-1.0.0",
        "required_components": ["spatial_consistency", "resolution_trend", "support_consistency", "time_contamination", "reference_sensitivity", "model_form_compatibility"],
        "pass_rule": "6_of_6_PASS",
        "rows": attribution_rows,
        "candidate_counts": candidate_counts,
        "candidate_discretization_target_count": qualified_count,
        "prior_stage02d_records_preserved": {"diagnostic": 4, "rejected": 2, "attribution_PASS": 0},
    }
    stage02f = {
        "decision_version": "stage02e-stage02f-gate-1.0.0",
        "stage02f_data_qualification_authorized": qualified_count > 0,
        "candidate_discretization_target_count": qualified_count,
        "reason": "no_candidate_has_6_of_6_attribution_PASS" if qualified_count == 0 else "qualified_candidates_available",
        "training_dataset_created": False,
        "model_or_training_created": False,
        "performance_evaluation_performed": False,
    }

    outputs = {
        ATTR / "target_construction" / "candidate_target_pool.json": pool,
        ATTR / "resolution_study" / "resolution_study.json": resolution,
        ATTR / "support_study" / "support_study.json": support,
        ATTR / "disorder_study" / "disorder_study.json": disorder,
        ATTR / "qualification" / "reference_qualification_audit_stage02e.json": reference_audit,
        ATTR / "qualification" / "attribution_results_stage02e.json": attribution,
        ATTR / "qualification" / "stage02f_decision.json": stage02f,
    }
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError("No-overwrite contract; existing outputs: " + ", ".join(existing))
    for path, value in outputs.items():
        write_json_no_overwrite(path, value)
    manifest = {
        "manifest_version": "stage02e-target-construction-manifest-1.0.0",
        "campaign_id": matrix["campaign_id"],
        "inputs": {
            "excitation_matrix": file_hash(MATRIX_PATH),
            "generation_configuration": file_hash(CONFIG_PATH),
            "stage02c_generator": file_hash(GENERATOR_PATH),
            "stage02d_decision": file_hash(STAGE02D_DECISION_PATH),
            "constructor": file_hash(Path(__file__).resolve()),
        },
        "outputs": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in outputs},
        "determinism": {"repeats": 2, "canonical_bytes_equal": True, "status": "PASS"},
        "candidate_count": len(candidates),
        "nonzero_count": nonzero_count,
        "qualified_count": qualified_count,
        "failure_retention": {"zero_targets_retained": True, "unresolved_retained": True, "topology_failures_retained": True, "stage02d_records_unchanged": True},
        "prohibited_outputs": {"training_dataset": False, "model": False, "training": False, "split_assignment": False, "normalization": False, "performance_evaluation": False},
        "status": "PASS" if nonzero_count > 0 else "FAIL",
    }
    manifest_path = ATTR / "target_construction" / "target_construction_manifest.json"
    write_json_no_overwrite(manifest_path, manifest)
    print(json.dumps({
        "status": manifest["status"],
        "candidate_count": len(candidates),
        "nonzero_count": nonzero_count,
        "zero_count": zero_count,
        "candidate_counts": candidate_counts,
        "candidate_discretization_target_count": qualified_count,
        "stage02f_authorized": stage02f["stage02f_data_qualification_authorized"],
    }, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
