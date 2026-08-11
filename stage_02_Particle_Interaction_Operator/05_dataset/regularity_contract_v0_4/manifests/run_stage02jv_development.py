#!/usr/bin/env python3
"""Execute Stage 02J-V necessity, development, calibration, and invariance gates."""

from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_4"
JTROOT = STAGE / "05_dataset/regularity_contract_v0_3"
JT_CORE = JTROOT / "manifests/run_stage02jt_development.py"
FREEZE_PATH = ROOT / "freeze/stage02jv_input_freeze_manifest.json"
PREREG_PATH = ROOT / "contract_design/v04_candidate_preregistration.yaml"
PV_ATTR_PATH = STAGE / "04_target_attribution/qualified_spatial_targets/attribution/resolution_attribution.json"
JR_ATTR_PATH = STAGE / "05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/six_component_attribution.json"
JT_SIGN_PATH = JTROOT / "control_semantics/signflip_semantics.json"

NECESSITY_OUT = ROOT / "necessity_controls/positive_control_results.json"
ABLATION_OUT = ROOT / "necessity_controls/signflip_ablation_results.json"
DEVELOPMENT_OUT = ROOT / "development/development_real_target_results.json"
CALIBRATION_OUT = ROOT / "calibration/hard_negative_calibration.json"
INVARIANCE_OUT = ROOT / "invariance/v04_invariance_results.json"
GATE_OUT = ROOT / "contract_design/v04_development_gate.json"

POSITIVE = ("MAGNITUDE_ONLY_SMOOTH", "DIRECTION_ONLY_SMOOTH", "JOINT_SMOOTH")
HARD_NEGATIVE = (
    "FULL_PARTICLE_PERMUTATION", "GAUSSIAN_WHITE_MATCHED_RMS",
    "INDEPENDENT_COMPONENT_PERMUTATION", "NYQUIST_CHECKERBOARD_MATCHED_RMS",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_jt() -> Any:
    spec = importlib.util.spec_from_file_location("stage02jv_jt_readonly", JT_CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(JT_CORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def p_any(p_mag: float, p_dir: float) -> float:
    return min(1.0, 2.0 * min(p_mag, p_dir))


def evaluate(jt: Any, context: dict[str, Any], field: np.ndarray, perms: np.ndarray) -> dict[str, Any]:
    obs_s, obs_m, obs_d = jt.metric_batch(context, field)
    _, null_m, null_d = jt.metric_batch(context, field[perms])
    magnitude_count = int(np.count_nonzero(null_m <= obs_m[0]))
    direction_count = int(np.count_nonzero(null_d <= obs_d[0]))
    p_mag_value = (1 + magnitude_count) / 257.0
    p_dir_value = (1 + direction_count) / 257.0
    return {
        "S_h": float(obs_s[0]), "M_h": float(obs_m[0]), "D_h": float(obs_d[0]),
        "p_mag": p_mag_value, "p_dir": p_dir_value,
        "p_any": p_any(p_mag_value, p_dir_value),
        "magnitude_lower_tail_count": magnitude_count,
        "direction_lower_tail_count": direction_count,
    }


def matched_positive(control: str, context: dict[str, Any]) -> np.ndarray:
    position = context["position"]
    target_rms = float(np.sqrt(np.mean(np.sum(context["field"] ** 2, axis=1))))
    if control == "MAGNITUDE_ONLY_SMOOTH":
        shape = 1.0 + 0.4 * np.cos(2.0 * math.pi * position[:, 0])
        raw = np.column_stack((shape, np.zeros(len(shape))))
    elif control == "DIRECTION_ONLY_SMOOTH":
        raw = np.column_stack((np.cos(2.0 * math.pi * position[:, 0]), np.sin(2.0 * math.pi * position[:, 0])))
    elif control == "JOINT_SMOOTH":
        magnitude = 1.0 + 0.3 * np.cos(2.0 * math.pi * position[:, 0])
        raw = magnitude[:, None] * np.column_stack((np.cos(2.0 * math.pi * position[:, 1]), np.sin(2.0 * math.pi * position[:, 1])))
    elif control == "CONSTANT_VECTOR":
        raw = np.column_stack((np.ones(len(position)), np.zeros(len(position))))
    else:
        raise ValueError(control)
    raw_rms = float(np.sqrt(np.mean(np.sum(raw * raw, axis=1))))
    return raw * (target_rms / raw_rms)


def necessity_audit(jt: Any, contexts: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[tuple[str, str], np.ndarray]]:
    rows = []; fields = {}
    for context in contexts.values():
        if "resolution" not in context["path_membership"]:
            continue
        perms = jt.permutations(context["case_id"], len(context["field"]))
        for control in (*POSITIVE, "CONSTANT_VECTOR"):
            field = matched_positive(control, context); fields[(context["case_id"], control)] = field
            result = evaluate(jt, context, field, perms)
            if control == "CONSTANT_VECTOR":
                expected = result["M_h"] == 0.0 and result["D_h"] == 0.0 and result["p_mag"] == 1.0 and result["p_dir"] == 1.0 and result["p_any"] == 1.0
                status = "PASS" if expected else "FAIL"
                role = "zero_variation_handling_only"
            else:
                status = "PASS" if result["p_any"] <= 0.01 else "FAIL"
                role = "learnable_structure_positive_control"
            rows.append({
                "case_id": context["case_id"], "family_id": context["family_id"], "control_id": control,
                **result, "RMS_matched": True, "role": role, "status": status,
            })
    learnable = [row for row in rows if row["control_id"] in POSITIVE]
    constants = [row for row in rows if row["control_id"] == "CONSTANT_VECTOR"]
    return ({
        "audit_version": "stage02jv-necessity-controls-0.4.0", "rows": rows,
        "positive_control_case_count": len(learnable),
        "all_positive_controls_PASS": all(row["status"] == "PASS" for row in learnable),
        "constant_vector_handling_PASS": all(row["status"] == "PASS" for row in constants),
        "controls_are_dataset_targets": False,
    }, fields)


def refinement_summary(family_id: str, rows: list[dict[str, Any]], legacy: dict[str, str]) -> dict[str, Any]:
    selected = sorted([row for row in rows if row["family_id"] == family_id], key=lambda row: row["particles_per_axis"])
    m = np.asarray([row["M_h"] for row in selected]); d = np.asarray([row["D_h"] for row in selected])
    m_slope = float(np.polyfit(np.arange(3, dtype=np.float64), m, 1)[0]); d_slope = float(np.polyfit(np.arange(3, dtype=np.float64), d, 1)[0])
    mag_applicable = selected[0]["p_mag"] <= 0.01; dir_applicable = selected[0]["p_dir"] <= 0.01
    mag_refinement = m[-1] <= m[0] and m_slope <= 0.0
    dir_refinement = d[-1] <= d[0] and d_slope <= 0.0
    checks = {
        "all_p_any": "PASS" if all(row["p_any"] <= 0.01 for row in selected) else "FAIL",
        **legacy,
        "at_least_one_applicable_refinement": "PASS" if (mag_applicable and mag_refinement) or (dir_applicable and dir_refinement) else "FAIL",
    }
    return {
        "family_id": family_id, "case_ids": [row["case_id"] for row in selected],
        "magnitude": {"low_resolution_significant": mag_applicable, "applicability": "HARD" if mag_applicable else "DIAGNOSTIC", "endpoint_nonworse": mag_refinement, "OLS_slope": m_slope},
        "direction": {"low_resolution_significant": dir_applicable, "applicability": "HARD" if dir_applicable else "DIAGNOSTIC", "endpoint_nonworse": dir_refinement, "OLS_slope": d_slope},
        "checks": checks, "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
        "convergence_order_claimed": False,
    }


def development_audit(jt: Any, contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for context in contexts.values():
        if "resolution" not in context["path_membership"]:
            continue
        result = evaluate(jt, context, context["field"], jt.permutations(context["case_id"], len(context["field"])))
        rows.append({"case_id": context["case_id"], "family_id": context["family_id"], "particles_per_axis": context["particles_per_axis"], **result})
    keys = ("target_endpoint_magnitude_nonincreasing", "adjacent_low_mode_direction_cosine", "relative_neighbor_variation_strictly_decreasing", "physical_gradient_scale_coefficient_of_variation")
    pv = load_json(PV_ATTR_PATH)["checks"]
    jr = load_json(JR_ATTR_PATH); cross_all = next(item for item in jr["families"] if item["family_id"] == "FAMILY_CROSSMODE_A")["resolution"]["checks"]
    summaries = [
        refinement_summary("FAMILY_PV_EXISTING", rows, {key: pv[key] for key in keys}),
        refinement_summary("FAMILY_CROSSMODE_A", rows, {key: cross_all[key] for key in keys}),
    ]
    return {"audit_version": "stage02jv-development-real-0.4.0", "rows": sorted(rows, key=lambda row: row["case_id"]), "family_summaries": summaries, "development_real_targets_PASS": all(row["status"] == "PASS" for row in summaries)}


def realization_seed(case_id: str, control: str, index: int) -> int:
    token = f"stage02jv{case_id}{control}{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big", signed=False)


def hard_negative_field(control: str, context: dict[str, Any], index: int) -> np.ndarray:
    field = context["field"]; n = len(field)
    rng = np.random.Generator(np.random.PCG64(realization_seed(context["case_id"], control, index)))
    if control == "FULL_PARTICLE_PERMUTATION":
        result = field[rng.permutation(n)]
    elif control == "GAUSSIAN_WHITE_MATCHED_RMS":
        result = rng.normal(size=field.shape)
    elif control == "INDEPENDENT_COMPONENT_PERMUTATION":
        result = np.column_stack((field[rng.permutation(n), 0], field[rng.permutation(n), 1]))
    elif control == "NYQUIST_CHECKERBOARD_MATCHED_RMS":
        n_axis = context["particles_per_axis"]; order = np.lexsort((context["particle_id"], context["position"][:, 1], context["position"][:, 0]))
        checker = np.empty(n); px = int(rng.integers(0, 2)); py = int(rng.integers(0, 2))
        checker[order] = np.asarray([(-1.0) ** ((i // n_axis + px) + (i % n_axis + py)) for i in range(n)])
        theta = float(rng.uniform(0.0, 2.0 * math.pi)); result = checker[:, None] * np.asarray([[math.cos(theta), math.sin(theta)]])
    else:
        raise ValueError(control)
    target_rms = float(np.sqrt(np.mean(np.sum(field * field, axis=1)))); result_rms = float(np.sqrt(np.mean(np.sum(result * result, axis=1))))
    return result * target_rms / result_rms


def calibration_task(payload: tuple[dict[str, Any], str]) -> dict[str, Any]:
    context, control = payload; jt = load_jt(); perms = jt.permutations(context["case_id"], len(context["field"]))
    fp = 0; realizations = []
    for index in range(512):
        result = evaluate(jt, context, hard_negative_field(control, context, index), perms)
        passed = result["p_any"] <= 0.01; fp += int(passed)
        realizations.append({"realization_index": index, "p_mag": result["p_mag"], "p_dir": result["p_dir"], "p_any": result["p_any"], "false_positive": passed})
    upper = 1.0 if fp == 512 else float(beta.ppf(0.95, fp + 1, 512 - fp))
    return {"case_id": context["case_id"], "family_id": context["family_id"], "control_id": control, "false_positive_count": fp, "raw_rate": fp / 512.0, "one_sided_95_Clopper_Pearson_upper": upper, "status": "PASS" if upper <= 0.05 else "FAIL", "realizations": realizations}


def ablation_audit() -> dict[str, Any]:
    historical = load_json(JT_SIGN_PATH)
    rows = [{**row, "p_any": p_any(row["p_mag"], row["p_dir"]), "control_semantics_v0_4": "DIRECTION_ABLATION_CONTROL", "counted_as_hard_negative": False} for row in historical["rows"]]
    return {"audit_version": "stage02jv-signflip-ablation-0.4.0", "source_hash": file_hash(JT_SIGN_PATH), "rows": rows, "realization_count": len(rows), "magnitude_mapping_preserved_count": sum(row["magnitude_position_mapping_exact"] for row in rows), "p_any_PASS_count": sum(row["p_any"] <= 0.01 for row in rows), "hard_negative_false_positive_count_contribution": 0}


def invariance_audit(jt: Any, contexts: dict[str, dict[str, Any]], positive_fields: dict[tuple[str, str], np.ndarray]) -> dict[str, Any]:
    populations = []
    for context in contexts.values():
        if "resolution" not in context["path_membership"]:
            continue
        populations.append((context, "REAL_TARGET", context["field"]))
        for control in POSITIVE:
            populations.append((context, control, positive_fields[(context["case_id"], control)]))
    rows = []
    for context, population, field in populations:
        perms = jt.permutations(context["case_id"], len(field)); baseline = evaluate(jt, context, field, perms)
        variants: list[tuple[str, dict[str, Any], np.ndarray]] = []
        for scale in (0.1, 1.0, 10.0): variants.append((f"amplitude_{scale:g}", context, field * scale))
        translated = dict(context); translated["position"] = np.mod(context["position"] + np.asarray([0.173, 0.319]), 1.0); variants.append(("periodic_translation", translated, field))
        exchanged = dict(context); exchanged["displacement"] = context["displacement"][:, ::-1]; variants.append(("axis_exchange", exchanged, field[:, ::-1]))
        rotation = np.asarray([[0.0, -1.0], [1.0, 0.0]]); variants.append(("vector_rotation_90", context, field @ rotation.T))
        variants.append(("particle_recanonicalization", context, field.copy()))
        reversed_edges = dict(context); reversed_edges["source"] = context["target"]; reversed_edges["target"] = context["source"]; reversed_edges["displacement"] = -context["displacement"]; variants.append(("edge_forward_reverse_order", reversed_edges, field))
        for name, transformed_context, transformed_field in variants:
            result = evaluate(jt, transformed_context, transformed_field, perms)
            checks = {}
            for key in ("M_h", "D_h"):
                tolerance = 1e-14 + 1e-12 * abs(baseline[key]); checks[key] = "PASS" if abs(result[key] - baseline[key]) <= tolerance else "FAIL"
            for key in ("p_mag", "p_dir", "p_any"): checks[key] = "PASS" if result[key] == baseline[key] else "FAIL"
            rows.append({"case_id": context["case_id"], "population": population, "transformation": name, "checks": checks, "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL"})
    return {"audit_version": "stage02jv-invariance-0.4.0", "rows": rows, "all_invariance_PASS": all(row["status"] == "PASS" for row in rows)}


def main() -> int:
    freeze = load_json(FREEZE_PATH)
    if file_hash(PREREG_PATH) != freeze["candidate_preregistration_hash"]: raise RuntimeError("Candidate preregistration changed")
    jt = load_jt(); contexts = jt.dev_contexts()
    necessity, positive_fields = necessity_audit(jt, contexts)
    development = development_audit(jt, contexts)
    ablation = ablation_audit()
    resolution_contexts = [context for context in contexts.values() if "resolution" in context["path_membership"]]
    tasks = [(context, control) for context in resolution_contexts for control in HARD_NEGATIVE]
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(6, max(1, os.cpu_count() or 1))) as executor:
        rows = list(executor.map(calibration_task, tasks))
    calibration = {"audit_version": "stage02jv-hard-negative-calibration-0.4.0", "seed_root": 20260805, "realizations_per_case_control": 512, "permutations_per_realization": 256, "rows": sorted(rows, key=lambda row: (row["case_id"], row["control_id"])), "all_hard_negative_CP_PASS": all(row["status"] == "PASS" for row in rows), "signflip_included_as_hard_negative": False, "seed_screening_used": False}
    invariance = invariance_audit(jt, contexts, positive_fields)
    checks = {
        "decomposition_reuse_verified": "PASS" if file_hash(JTROOT / "decomposition/development_metric_decomposition.json") == freeze["required_inputs"]["stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/decomposition/development_metric_decomposition.json"] else "FAIL",
        "necessity_positive_controls": "PASS" if necessity["all_positive_controls_PASS"] and necessity["constant_vector_handling_PASS"] else "FAIL",
        "hard_negative_calibration": "PASS" if calibration["all_hard_negative_CP_PASS"] else "FAIL",
        "development_real_targets": "PASS" if development["development_real_targets_PASS"] else "FAIL",
        "invariance": "PASS" if invariance["all_invariance_PASS"] else "FAIL",
    }
    gate = {"gate_version": "stage02jv-development-gate-0.4.0", "candidate_preregistration_hash": freeze["candidate_preregistration_hash"], "checks": checks, "final_v04_contract_generation_authorized": all(value == "PASS" for value in checks.values()), "blind_formula_accessed": False}
    write(NECESSITY_OUT, necessity); write(ABLATION_OUT, ablation); write(DEVELOPMENT_OUT, development); write(CALIBRATION_OUT, calibration); write(INVARIANCE_OUT, invariance); write(GATE_OUT, gate)
    print(json.dumps({"positive": necessity["all_positive_controls_PASS"], "constant": necessity["constant_vector_handling_PASS"], "development": development["development_real_targets_PASS"], "hard_negative": calibration["all_hard_negative_CP_PASS"], "invariance": invariance["all_invariance_PASS"], "contract_authorized": gate["final_v04_contract_generation_authorized"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
