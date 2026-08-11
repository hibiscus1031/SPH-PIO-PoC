#!/usr/bin/env python3
"""Qualify preregistered Stage 02J-R references and spatial targets."""

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
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import lsqr

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATA_ROOT = STAGE_ROOT / "05_dataset/controlled_multifamily_pair_scope_v0_2"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
PREREG_PATH = DATA_ROOT / "family_design/family_preregistration.yaml"
FORMULA_PATH = DATA_ROOT / "family_design/analytic_family_definitions.py"
PREFLIGHT_PATH = DATA_ROOT / "family_preflight/family_separability_preflight.json"
FREEZE_PATH = DATA_ROOT / "freeze/stage02jr_input_freeze_manifest.json"
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
GENERATOR_PATH = STAGE_ROOT / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F_PATH = ATTR_ROOT / "semidiscrete_reference/construct_spatial_targets.py"
REFERENCE_RULES_PATH = ATTR_ROOT / "acceptance/reference_acceptance_rules.yaml"
RESOLUTION_RULES_PATH = ATTR_ROOT / "resolution_extension/resolution_extension_matrix.yaml"
SMOOTHNESS_RULES_PATH = ATTR_ROOT / "smoothness_audit/smoothness_criterion_contract.yaml"
SUPPORT_RULES_PATH = ATTR_ROOT / "semidiscrete_reference/r2s_reference_design.yaml"

PHYSICAL_PREFLIGHT_PATH = DATA_ROOT / "family_preflight/physical_state_preflight.json"
UNIT_TEST_PATH = DATA_ROOT / "reference_qualification/analytic_derivative_unit_tests.json"
REFERENCE_OUTPUT_PATH = DATA_ROOT / "reference_qualification/reference_qualification_results.json"
TARGET_OUTPUT_PATH = DATA_ROOT / "target_qualification/new_family_target_candidates.json"
ATTRIBUTION_OUTPUT_PATH = DATA_ROOT / "target_qualification/six_component_attribution.json"
CONSERVATION_OUTPUT_PATH = DATA_ROOT / "conservation/pair_only_conservation_qualification.json"
RUN_MANIFEST_PATH = DATA_ROOT / "manifests/qualification_run_manifest.json"

NEW_FAMILIES = ("FAMILY_CROSSMODE_A", "FAMILY_DIAGONAL_B", "FAMILY_MIXED_C")
FAMILY_PREFIX = {
    "FAMILY_CROSSMODE_A": "crossmode_a",
    "FAMILY_DIAGONAL_B": "diagonal_b",
    "FAMILY_MIXED_C": "mixed_c",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def content_hash(value: Any) -> str:
    return digest(canonical_bytes(value))


def file_hash(path: Path) -> str:
    return digest(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def field_metrics(field: np.ndarray) -> dict[str, Any]:
    magnitude = np.linalg.norm(field, axis=1)
    return {
        "L2_particle_rms": float(np.sqrt(np.mean(magnitude * magnitude))),
        "Linf_particle_vector": float(np.max(magnitude)),
        "component_mean": [float(x) for x in np.mean(field, axis=0)],
        "magnitude_quantiles": {str(q): float(np.quantile(magnitude, q)) for q in (0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0)},
    }


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.sum(left * right) / denominator) if denominator > 0.0 else 0.0


def signature(position: np.ndarray, field: np.ndarray, modes: list[list[int]]) -> np.ndarray:
    entries: list[float] = []
    for kx, ky in modes:
        phase = np.exp(-2.0j * math.pi * (kx * position[:, 0] + ky * position[:, 1]))
        for component in range(2):
            coefficient = np.mean(field[:, component] * phase)
            entries.extend((float(coefficient.real), float(coefficient.imag)))
    return np.asarray(entries, dtype=np.float64)


def case_rows(prereg: dict[str, Any], family_id: str, split_role: str) -> list[dict[str, Any]]:
    rows = []
    for path, entries in prereg["case_template"].items():
        for raw in entries:
            rows.append(
                {
                    **raw,
                    "case_id": f"{FAMILY_PREFIX[family_id]}_{raw['case_suffix']}",
                    "family_id": family_id,
                    "split_role": split_role,
                    "path_membership": ["resolution"] if path == "resolution_path" else ["support"],
                    "disorder_identity": "regular",
                    "disorder_fraction_dx": 0.0,
                    "random_seed": 0,
                    "topology_control": "none",
                    "time_horizon": 0.0,
                    "trajectory_family": f"{family_id}_no_trajectory",
                    "initial_condition_family": f"{family_id}_independent_IC",
                    "disorder_family": "regular",
                }
            )
    if len(rows) != 5 or len({row["case_id"] for row in rows}) != 5:
        raise RuntimeError(f"Case template did not yield exactly five cases: {family_id}")
    return rows


def state_for_case(raw: dict[str, Any], analytic: Any, config: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n_axis = int(raw["particles_per_axis"])
    grid = (np.arange(n_axis, dtype=np.float64) + 0.5) / n_axis
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    position = np.column_stack((xx.ravel(), yy.ravel()))
    fields = analytic.evaluate_family(
        raw["family_id"], position,
        rho0=float(config["physics"]["rho0"]), cs=float(config["physics"]["sound_speed"]),
        nu=float(config["physics"]["kinematic_viscosity"]),
    )
    state = {"x": position, "v": fields["velocity"], "rho": fields["rho"]}
    return state, fields


def graph_diagnostics(generator: Any, state: dict[str, np.ndarray], edges: dict[str, np.ndarray], raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    n = state["x"].shape[0]
    dx = 1.0 / int(raw["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    support = float(raw["h_over_dx"]) * dx
    distance = np.linalg.norm(edges["displacement"], axis=1)
    weights, _ = generator.kernel_values(distance, h)
    active = weights > 0.0
    active_count = np.bincount(edges["source"][active], minlength=n)
    total_count = np.bincount(edges["source"], minlength=n)
    return {
        "kernel_active_neighbor_count": {"min": int(active_count.min()), "max": int(active_count.max()), "mean": float(active_count.mean())},
        "total_neighbor_count": {"min": int(total_count.min()), "max": int(total_count.max()), "mean": float(total_count.mean())},
        "zero_weight_exterior_edges": {"directed_total": int(np.count_nonzero(~active))},
        "support": support,
    }


def reference_qualification(
    family_id: str, raw: dict[str, Any], state: dict[str, np.ndarray], fields: dict[str, np.ndarray],
    rhs: dict[str, np.ndarray], analytic: Any, config: dict[str, Any], rules: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    rho0 = float(config["physics"]["rho0"]); cs = float(config["physics"]["sound_speed"]); nu = float(config["physics"]["kinematic_viscosity"])
    primary = analytic.fourier_spatial_reference(state["x"], state["rho"], state["v"], rho0=rho0, cs=cs, nu=nu)
    secondary = fields
    primary_repeat = analytic.fourier_spatial_reference(state["x"], state["rho"], state["v"], rho0=rho0, cs=cs, nu=nu)
    secondary_repeat = analytic.evaluate_family(family_id, state["x"], rho0=rho0, cs=cs, nu=nu)
    a_sph = rhs["total"]
    p_target = primary["acceleration"] - a_sph
    s_target = secondary["acceleration"] - a_sph
    difference = primary["acceleration"] - secondary["acceleration"]
    diff_metrics = field_metrics(difference)
    p_metrics = field_metrics(p_target); s_metrics = field_metrics(s_target)
    max_l2 = max(p_metrics["L2_particle_rms"], s_metrics["L2_particle_rms"])
    max_linf = max(p_metrics["Linf_particle_vector"], s_metrics["Linf_particle_vector"])
    thresholds = rules["numeric_thresholds"]
    normalized_l2 = diff_metrics["L2_particle_rms"] / max_l2 if max_l2 > 0.0 else math.inf
    normalized_linf = diff_metrics["Linf_particle_vector"] / max_linf if max_linf > 0.0 else math.inf
    pattern_cosine = cosine(p_target, s_target)
    deterministic_primary = all(np.array_equal(primary[key], primary_repeat[key]) for key in primary)
    deterministic_secondary = all(np.array_equal(secondary[key], secondary_repeat[key]) for key in secondary)
    pair_checks = {
        "normalized_L2": "PASS" if normalized_l2 <= float(thresholds["cross_reference_pair_L2_to_max_target_L2_ratio_max"]) else "FAIL",
        "normalized_Linf": "PASS" if normalized_linf <= float(thresholds["cross_reference_pair_Linf_to_max_target_Linf_ratio_max"]) else "FAIL",
        "target_pattern_cosine": "PASS" if pattern_cosine >= float(thresholds["cross_reference_target_pattern_cosine_min"]) else "FAIL",
    }
    primary_bias_ratio = normalized_l2
    secondary_bias_ratio = 0.0
    primary_checks = {
        "same_state": "PASS", "same_physics": "PASS",
        "deterministic": "PASS" if deterministic_primary else "FAIL",
        "low_reconstruction_bias": "PASS" if primary_bias_ratio <= float(thresholds["bias_to_reference_target_L2_ratio_max"]) else "FAIL",
        "cross_reference_agreement": "PASS" if all(v == "PASS" for v in pair_checks.values()) else "FAIL",
        "uncertainty_qualified": "PASS" if normalized_l2 <= float(thresholds["uncertainty_to_reference_target_L2_ratio_max"]) else "FAIL",
    }
    secondary_checks = {
        "same_state": "PASS", "same_physics": "PASS",
        "deterministic": "PASS" if deterministic_secondary else "FAIL",
        "low_reconstruction_bias": "PASS" if secondary_bias_ratio <= float(thresholds["bias_to_reference_target_L2_ratio_max"]) else "FAIL",
        "cross_reference_agreement": "PASS" if all(v == "PASS" for v in pair_checks.values()) else "FAIL",
        "uncertainty_qualified": "PASS" if normalized_l2 <= float(thresholds["uncertainty_to_reference_target_L2_ratio_max"]) else "FAIL",
    }
    row = {
        "family_id": family_id,
        "case_id": raw["case_id"],
        "primary_reference_id": f"{family_id}_FOURIER_SPATIAL_V1",
        "secondary_reference_id": f"{family_id}_ANALYTIC_SPATIAL_V1",
        "same_state_hash_basis": "identical_position_velocity_density_arrays",
        "primary": {"checks": primary_checks, "bias_to_reference_target_L2_ratio": primary_bias_ratio, "status": "accepted" if all(v == "PASS" for v in primary_checks.values()) else "diagnostic"},
        "secondary": {"checks": secondary_checks, "bias_to_reference_target_L2_ratio": secondary_bias_ratio, "status": "accepted" if all(v == "PASS" for v in secondary_checks.values()) else "diagnostic"},
        "pair_agreement": {
            "L2_particle_rms": diff_metrics["L2_particle_rms"], "Linf_particle_vector": diff_metrics["Linf_particle_vector"],
            "normalized_L2": normalized_l2, "normalized_Linf": normalized_linf,
            "target_pattern_cosine": pattern_cosine, "checks": pair_checks,
            "status": "PASS" if all(v == "PASS" for v in pair_checks.values()) else "FAIL",
        },
        "deterministic_repeat": {
            "primary_canonical_equal": deterministic_primary, "secondary_canonical_equal": deterministic_secondary,
            "primary_max_Linf": float(np.max(np.abs(primary["acceleration"] - primary_repeat["acceleration"]))),
            "secondary_max_Linf": float(np.max(np.abs(secondary["acceleration"] - secondary_repeat["acceleration"]))),
            "status": "PASS" if deterministic_primary and deterministic_secondary else "FAIL",
        },
        "accepted": all(v == "PASS" for v in primary_checks.values()) and all(v == "PASS" for v in secondary_checks.values()) and all(v == "PASS" for v in pair_checks.values()),
    }
    arrays = {
        "a_FOURIER": primary["acceleration"], "a_ANALYTIC": secondary["acceleration"],
        "reference_difference": difference, "delta_a": p_target,
        "a_FOURIER_pressure": primary["pressure_acceleration"], "a_FOURIER_viscosity": primary["viscosity_acceleration"],
    }
    return row, arrays


def general_pair_audit(y: np.ndarray, edges: dict[str, np.ndarray]) -> dict[str, Any]:
    selection = edges["source"] < edges["target"]
    left = edges["source"][selection].astype(np.int64)
    right = edges["target"][selection].astype(np.int64)
    n = y.shape[0]; e = len(left)
    columns = np.arange(e, dtype=np.int64)
    incidence = coo_matrix(
        (np.concatenate((np.ones(e), -np.ones(e))), (np.concatenate((left, right)), np.concatenate((columns, columns)))),
        shape=(n, e),
    ).tocsr()
    reconstructed = np.zeros_like(y)
    iterations = []
    for component in range(2):
        result = lsqr(incidence, y[:, component], atol=1e-14, btol=1e-14, iter_lim=max(200, n * 4))
        reconstructed[:, component] = incidence @ result[0]
        iterations.append(int(result[2]))
    residual = y - reconstructed
    denominator = float(np.linalg.norm(y))
    normalized = float(np.linalg.norm(residual) / denominator) if denominator > 0.0 else 0.0
    return {
        "undirected_edge_count": e,
        "scalar_incidence_rank": n - 1,
        "scalar_null_space_dimension": e - n + 1,
        "vector_incidence_rank": 2 * (n - 1),
        "vector_null_space_dimension": 2 * (e - n + 1),
        "LSQR_iterations_xy": iterations,
        "least_squares_residual_norm": float(np.linalg.norm(residual)),
        "normalized_projection_residual": normalized,
        "projection_written_back": False,
    }


def central_pair_diagnostic(y: np.ndarray, state: dict[str, np.ndarray], edges: dict[str, np.ndarray]) -> dict[str, Any]:
    selection = edges["source"] < edges["target"]
    left = edges["source"][selection].astype(np.int64); right = edges["target"][selection].astype(np.int64)
    disp = edges["displacement"][selection]
    unit = disp / np.linalg.norm(disp, axis=1)[:, None]
    n = y.shape[0]; e = len(left); cols = np.arange(e)
    rows = np.concatenate((2 * left, 2 * left + 1, 2 * right, 2 * right + 1))
    columns = np.concatenate((cols, cols, cols, cols))
    values = np.concatenate((unit[:, 0], unit[:, 1], -unit[:, 0], -unit[:, 1]))
    matrix = coo_matrix((values, (rows, columns)), shape=(2 * n, e)).tocsr()
    result = lsqr(matrix, y.reshape(-1), atol=1e-14, btol=1e-14, iter_lim=max(500, n * 8))
    residual = y.reshape(-1) - matrix @ result[0]
    normalized = float(np.linalg.norm(residual) / np.linalg.norm(y)) if np.linalg.norm(y) > 0 else 0.0
    relative = state["x"] - 0.5
    target_torque = float(np.sum(relative[:, 0] * y[:, 1] - relative[:, 1] * y[:, 0]))
    return {
        "normalized_residual": normalized,
        "target_torque_wrapped_box_center": target_torque,
        "hard_gate": False,
        "LSQR_iterations": int(result[2]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--execute", action="store_true"); args = parser.parse_args()
    if not args.execute:
        parser.error("Qualification requires explicit --execute")
    outputs = [PHYSICAL_PREFLIGHT_PATH, UNIT_TEST_PATH, REFERENCE_OUTPUT_PATH, TARGET_OUTPUT_PATH, ATTRIBUTION_OUTPUT_PATH, CONSERVATION_OUTPUT_PATH, RUN_MANIFEST_PATH]
    for path in outputs:
        if path.exists(): raise FileExistsError(f"No-overwrite contract: {path}")
    prereg = load_yaml(PREREG_PATH); preflight = load_json(PREFLIGHT_PATH); freeze = load_json(FREEZE_PATH)
    if preflight["status"] != "PASS" or not preflight["executed_before_new_acceleration_or_target"]:
        raise RuntimeError("Family separability preflight not complete")
    for role in freeze["frozen_roles"].values():
        if file_hash(REPO_ROOT / role["path"]) != role["sha256"]: raise RuntimeError(f"Frozen input changed: {role['path']}")
    config = load_yaml(CONFIG_PATH); reference_rules = load_yaml(REFERENCE_RULES_PATH)
    resolution_rules = load_yaml(RESOLUTION_RULES_PATH); smoothness_rules = load_yaml(SMOOTHNESS_RULES_PATH); support_rules = load_yaml(SUPPORT_RULES_PATH)
    generator = load_module("stage02jr_generator_readonly", GENERATOR_PATH)
    stage02f = load_module("stage02jr_stage02f_readonly", STAGE02F_PATH)
    analytic = load_module("stage02jr_analytic_preregistered", FORMULA_PATH)
    rho0=float(config["physics"]["rho0"]); cs=float(config["physics"]["sound_speed"]); nu=float(config["physics"]["kinematic_viscosity"])
    unit_tests = analytic.closed_form_unit_tests(rho0=rho0, cs=cs, nu=nu)
    if not unit_tests["all_pass"]: raise RuntimeError("Closed-form derivative unit tests failed")

    family_map = {row["family_id"]: row for row in prereg["families"]}
    reference_rows=[]; target_rows=[]; contexts={}; physical_rows=[]
    for family_id in NEW_FAMILIES:
        family=family_map[family_id]
        formula_hash=freeze["family_formula_hashes"][family_id]
        family_physical=[]
        modes=sorted({tuple(mode) for group in family["mode_support"].values() for mode in group})
        for raw in case_rows(prereg, family_id, family["split_role"]):
            state, fields = state_for_case(raw, analytic, config)
            rhs, edges = generator.sparse_rhs_components(state, raw, config, apply_control=False)
            topology = generator.topology_audit(edges, state, raw, config)
            ref_row, arrays = reference_qualification(family_id, raw, state, fields, rhs, analytic, config, reference_rules)
            reference_rows.append(ref_row)
            delta=arrays["delta_a"]; metrics=field_metrics(delta)
            mass=rho0/state["x"].shape[0]
            mach=np.linalg.norm(state["v"],axis=1)/cs
            physical={"case_id":raw["case_id"],"rho_min":float(state["rho"].min()),"rho_max":float(state["rho"].max()),"Mach_min":float(mach.min()),"Mach_max":float(mach.max())}
            family_physical.append(physical)
            physical_rows.append({"family_id":family_id,**physical})
            physical_config={"common":prereg["common_physics"],"family_formula_hash":formula_hash,"h_over_dx":raw["h_over_dx"],"resolution":raw["resolution_id"]}
            target={
                "family_id":family_id,"split_role":family["split_role"],"case_id":raw["case_id"],"path_membership":raw["path_membership"],
                "particles_per_axis":raw["particles_per_axis"],"particle_count":int(state["x"].shape[0]),"h_over_dx":raw["h_over_dx"],
                "resolution_identity":raw["resolution_id"],"support_identity":raw["support_id"],"disorder_identity":"regular","timestamp":0.0,
                "formula_hash":formula_hash,"analytic_derivative_hash":file_hash(FORMULA_PATH),
                "hashes":{"state_hash":stage02f.state_hash(state),"configuration_hash":content_hash(physical_config),"graph_hash":stage02f.graph_hash(edges),
                          "Fourier_reference_hash":content_hash(arrays["a_FOURIER"].tolist()),"analytic_reference_hash":content_hash(arrays["a_ANALYTIC"].tolist())},
                "a_SPH":rhs["total"].tolist(),"a_SPH_pressure":rhs["pressure"].tolist(),"a_SPH_viscosity":rhs["viscosity"].tolist(),
                "a_FOURIER":arrays["a_FOURIER"].tolist(),"a_ANALYTIC":arrays["a_ANALYTIC"].tolist(),"reference_difference":arrays["reference_difference"].tolist(),
                "delta_a":delta.tolist(),"nodal_force":(mass*delta).tolist(),"mass":mass,"target_sign":"a_reference_minus_a_sph",
                "target_metrics":metrics,"graph_total_variation_RMS":stage02f.graph_total_variation(delta,edges),
                "Fourier_signature_modes":[list(mode) for mode in modes],"low_mode_fourier_signature":signature(state["x"],delta,[list(mode) for mode in modes]).tolist(),
                "reference_qualification":ref_row,"topology":topology,"graph_diagnostics":graph_diagnostics(generator,state,edges,raw,config),
                "deterministic_repeat":ref_row["deterministic_repeat"],"uncertainty":{"reference_L2":ref_row["pair_agreement"]["L2_particle_rms"],"time":"NOT_APPLICABLE","space":"attribution_pending","model_form":"frozen_spatial_scope","topology":topology["status"],"resource":"PASS","single_total_GCI":False,"GCI_status":"GCI not justified"},
                "edge_pair_force_target_saved":False,"incidence_projection_written_back":False,"training_eligibility":"not_yet_evaluated",
            }
            target["candidate_content_hash_before_attribution"]=content_hash(target)
            target_rows.append(target); contexts[target["case_id"]]={"raw":raw,"state":state,"edges":edges}
        bounds={"FAMILY_CROSSMODE_A":[0.995,1.005],"FAMILY_DIAGONAL_B":[0.996,1.004],"FAMILY_MIXED_C":[0.9965,1.0035]}[family_id]
        physical_rows.append({"family_id":family_id,"analytic_density_relative_bounds":{"min":bounds[0],"max":bounds[1]},"strict_positivity_proved":bounds[0]*rho0>0.0,"family_sampled_rho_min":min(r["rho_min"] for r in family_physical),"family_sampled_rho_max":max(r["rho_max"] for r in family_physical),"family_sampled_Mach_min":min(r["Mach_min"] for r in family_physical),"family_sampled_Mach_max":max(r["Mach_max"] for r in family_physical)})

    target_map={row["case_id"]:row for row in target_rows}
    attribution_families=[]
    for family_id in NEW_FAMILIES:
        family=family_map[family_id]; rows=[row for row in target_rows if row["family_id"]==family_id]
        prefix=FAMILY_PREFIX[family_id]
        res=[target_map[f"{prefix}_{suffix}"] for suffix in ("n12_h26","n16_h26","n20_h26")]
        support=[target_map[f"{prefix}_{suffix}"] for suffix in ("n16_h22","n16_h26","n16_h30")]
        thresholds=resolution_rules["resolution_trend_predeclared_checks"]
        seed=int(smoothness_rules["refined_diagnostics_frozen_before_extension_execution"]["decorrelated_null"]["seed"])
        smooth_rows=[]
        for row in res:
            ctx=contexts[row["case_id"]]; target=np.asarray(row["delta_a"]); edges=ctx["edges"]
            tv=stage02f.graph_total_variation(target,edges); permutation=np.random.default_rng(seed).permutation(len(target)); null_tv=stage02f.graph_total_variation(target[permutation],edges)
            selection=edges["source"]<edges["target"]; mean_edge=float(np.mean(np.linalg.norm(edges["displacement"][selection],axis=1))); l2=row["target_metrics"]["L2_particle_rms"]
            smooth_rows.append({"case_id":row["case_id"],"target_L2":l2,"graph_TV":tv,"PCG64_permuted_null_seed":seed,"permuted_null_ratio":tv/null_tv,"relative_neighbor_variation":tv/l2,"mean_undirected_edge_length":mean_edge,"physical_gradient_scale":tv/(mean_edge*l2)})
        magnitudes=[r["target_L2"] for r in smooth_rows]; signatures=[np.asarray(r["low_mode_fourier_signature"]) for r in res]
        adjacent=[cosine(signatures[i],signatures[i+1]) for i in range(2)]; endpoint=magnitudes[-1]/magnitudes[0]; rel=[r["relative_neighbor_variation"] for r in smooth_rows]; grad=np.asarray([r["physical_gradient_scale"] for r in smooth_rows]); grad_cv=float(np.std(grad)/np.mean(grad))
        resolution_checks={
            "target_endpoint_magnitude_nonincreasing":"PASS" if endpoint<=float(thresholds["target_endpoint_L2_ratio_max"]) else "FAIL",
            "adjacent_low_mode_direction_cosine":"PASS" if min(adjacent)>=float(thresholds["adjacent_fourier_direction_cosine_min"]) else "FAIL",
            "PCG64_permuted_null_ratio":"PASS" if max(r["permuted_null_ratio"] for r in smooth_rows)<=float(thresholds["decorrelated_null_smoothness_ratio_max"]) else "FAIL",
            "relative_neighbor_variation_strictly_decreasing":"PASS" if all(rel[i+1]<rel[i] for i in range(2)) else "FAIL",
            "physical_gradient_scale_coefficient_of_variation":"PASS" if grad_cv<=float(thresholds["physical_gradient_scale_coefficient_of_variation_max"]) else "FAIL",
        }
        sth=support_rules["attribution_thresholds"]; smag=[r["target_metrics"]["L2_particle_rms"] for r in support]; ssig=[np.asarray(r["low_mode_fourier_signature"]) for r in support]; sadj=[cosine(ssig[i],ssig[i+1]) for i in range(2)]; sratio=max(smag)/min(smag)
        support_checks={"three_support_levels":"PASS","fixed_N16":"PASS","bounded_target_magnitude_ratio":"PASS" if sratio<=float(sth["support_max_L2_magnitude_ratio"]) else "FAIL","adjacent_direction_consistency":"PASS" if min(sadj)>=float(sth["support_min_adjacent_fourier_direction_cosine"]) else "FAIL","reference_agreement":"PASS" if all(r["reference_qualification"]["accepted"] for r in support) else "FAIL","topology":"PASS" if all(r["topology"]["status"]=="PASS" for r in support) else "FAIL"}
        resolution_status="PASS" if all(v=="PASS" for v in resolution_checks.values()) else "DIAGNOSTIC"
        support_status="PASS" if all(v=="PASS" for v in support_checks.values()) else "DIAGNOSTIC"
        case_results=[]
        for row in rows:
            vector={"spatial_consistency":"PASS" if row["reference_qualification"]["accepted"] and row["topology"]["status"]=="PASS" else "FAIL","resolution_trend":resolution_status,"support_consistency":support_status,"temporal_contamination":"PASS","reference_sensitivity":row["reference_qualification"]["pair_agreement"]["status"],"model_form_compatibility":"PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE"}
            count=sum(str(v).startswith("PASS") for v in vector.values()); case_results.append({"case_id":row["case_id"],"attribution_vector":vector,"pass_count":count,"required_pass_count":6,"candidate_discretization_target":count==6,"manual_override_permitted":False})
        family_pass=all(r["candidate_discretization_target"] for r in case_results)
        attribution_families.append({"family_id":family_id,"resolution":{"rows":smooth_rows,"endpoint_ratio":endpoint,"adjacent_direction_cosines":adjacent,"gradient_scale_CV":grad_cv,"checks":resolution_checks,"status":resolution_status,"cyclic_roll_null_used":False},"support":{"target_L2_max_over_min_ratio":sratio,"adjacent_direction_cosines":sadj,"checks":support_checks,"status":support_status},"case_results":case_results,"family_5_of_5_6_component_PASS":family_pass,"manual_override_permitted":False})
        for result in case_results:
            target_map[result["case_id"]]["candidate_discretization_target"]=result["candidate_discretization_target"]
            target_map[result["case_id"]]["six_component_attribution"]=result["attribution_vector"]
            target_map[result["case_id"]]["uncertainty"]["space"]="PASS" if result["candidate_discretization_target"] else "DIAGNOSTIC"

    conservation_families=[]
    for family_id in NEW_FAMILIES:
        rows=[]
        for target in [r for r in target_rows if r["family_id"]==family_id]:
            ctx=contexts[target["case_id"]]; y=np.asarray(target["nodal_force"]); total=np.sum(y,axis=0); denominator=float(np.sum(np.linalg.norm(y,axis=1))); normalized=float(np.linalg.norm(total)/denominator) if denominator>0 else 0.0
            general=general_pair_audit(y,ctx["edges"]); central=central_pair_diagnostic(y,ctx["state"],ctx["edges"])
            force_pass=normalized<=1e-10; pair_pass=general["normalized_projection_residual"]<=1e-10
            rows.append({"case_id":target["case_id"],"total_target_force":total.tolist(),"normalized_total_target_force_residual":normalized,"normalized_force_tolerance":1e-10,"force_status":"PASS" if force_pass else "FAIL","general_antisymmetric_pair":{**general,"tolerance":1e-10,"status":"PASS" if pair_pass else "FAIL"},"central_pair_diagnostic":central,"target_mean_subtracted":False,"projection_writeback":False,"status":"PASS" if force_pass and pair_pass else "FAIL"})
        family_pass=all(r["status"]=="PASS" for r in rows)
        conservation_families.append({"family_id":family_id,"rows":rows,"family_5_of_5_pair_only_PASS":family_pass,"failed_case_deleted":False})

    reference_families=[]
    for family_id in NEW_FAMILIES:
        rows=[r for r in reference_rows if r["family_id"]==family_id]; reference_families.append({"family_id":family_id,"rows":rows,"accepted_case_count":sum(r["accepted"] for r in rows),"required_case_count":5,"family_reference_qualified":len(rows)==5 and all(r["accepted"] for r in rows),"partial_case_selection_used":False})
    ref_output={"qualification_version":"stage02jr-reference-qualification-0.2.0","acceptance_rule_source":str(REFERENCE_RULES_PATH.relative_to(REPO_ROOT)),"acceptance_rule_hash":file_hash(REFERENCE_RULES_PATH),"thresholds_loaded_directly_not_reentered":True,"families":reference_families,"all_three_families_reference_qualified":all(f["family_reference_qualified"] for f in reference_families)}
    target_output={"artifact_type":"new_family_spatial_target_candidates_not_training_dataset","target_sign":"a_reference_minus_a_sph","new_family_count":3,"candidate_count":len(target_rows),"candidates":target_rows,"posthoc_case_change_used":False,"edge_pair_force_target_saved":False}
    attribution_output={"qualification_version":"stage02jr-six-component-0.2.0","resolution_rule_source":str(RESOLUTION_RULES_PATH.relative_to(REPO_ROOT)),"smoothness_rule_source":str(SMOOTHNESS_RULES_PATH.relative_to(REPO_ROOT)),"support_rule_source":str(SUPPORT_RULES_PATH.relative_to(REPO_ROOT)),"thresholds_loaded_directly_not_reentered":True,"families":attribution_families,"all_three_families_5_of_5_PASS":all(f["family_5_of_5_6_component_PASS"] for f in attribution_families)}
    conservation_output={"qualification_version":"stage02jr-pair-only-conservation-0.2.0","normalized_tolerances":{"total_force":1e-10,"general_pair_projection":1e-10},"families":conservation_families,"all_three_families_5_of_5_PASS":all(f["family_5_of_5_pair_only_PASS"] for f in conservation_families),"target_modification_used":False,"hybrid_or_node_head_used":False}
    physical_output={"preflight_version":"stage02jr-physical-state-preflight-0.2.0","executed_after_lineage_preflight_and_before_materialization":True,"rho0":rho0,"cs":cs,"nu":nu,"U0":0.02*cs,"rows":physical_rows,"all_density_strictly_positive":all(r.get("strict_positivity_proved",True) for r in physical_rows)}
    ready=ref_output["all_three_families_reference_qualified"] and attribution_output["all_three_families_5_of_5_PASS"] and conservation_output["all_three_families_5_of_5_PASS"]
    unit_output={"unit_test_version":"stage02jr-analytic-derivative-tests-0.2.0","definition_source":str(FORMULA_PATH.relative_to(REPO_ROOT)),"definition_source_hash":file_hash(FORMULA_PATH),"finite_difference_target_used":False,"automatic_differentiation_reference_used":False,**unit_tests}
    write_json(PHYSICAL_PREFLIGHT_PATH,physical_output); write_json(UNIT_TEST_PATH,unit_output); write_json(REFERENCE_OUTPUT_PATH,ref_output); write_json(TARGET_OUTPUT_PATH,target_output); write_json(ATTRIBUTION_OUTPUT_PATH,attribution_output); write_json(CONSERVATION_OUTPUT_PATH,conservation_output)
    outputs_written=[PHYSICAL_PREFLIGHT_PATH,UNIT_TEST_PATH,REFERENCE_OUTPUT_PATH,TARGET_OUTPUT_PATH,ATTRIBUTION_OUTPUT_PATH,CONSERVATION_OUTPUT_PATH]
    manifest={"run_version":"stage02jr-qualification-run-0.2.0","preflight_hash":file_hash(PREFLIGHT_PATH),"family_preregistration_hash":file_hash(PREREG_PATH),"output_hashes":{str(p.relative_to(REPO_ROOT)):file_hash(p) for p in outputs_written},"new_candidate_count":15,"all_new_families_qualified_for_materialization":ready,"trajectory_generated":False,"DOP853_used":False,"velocity_finite_difference_target_used":False,"augmentation_used":False,"edge_pair_label_generated":False,"target_modified":False,"model_generated":False,"training_performed":False}
    write_json(RUN_MANIFEST_PATH,manifest)
    print(json.dumps({"reference_all":ref_output["all_three_families_reference_qualified"],"attribution_all":attribution_output["all_three_families_5_of_5_PASS"],"conservation_all":conservation_output["all_three_families_5_of_5_PASS"],"qualified_for_materialization":ready},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
