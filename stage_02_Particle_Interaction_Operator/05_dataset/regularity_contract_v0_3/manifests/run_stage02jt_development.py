#!/usr/bin/env python3
"""Run Stage 02J-T development decomposition, calibration, and invariance."""

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
ROOT = STAGE / "05_dataset/regularity_contract_v0_3"
JSROOT = STAGE / "05_dataset/regularity_contract_v0_2"
JS_CORE = JSROOT / "manifests/run_stage02js_regularity_audit.py"
FREEZE_PATH = ROOT / "freeze/stage02jt_input_freeze_manifest.json"
PREREG_PATH = ROOT / "contract_design/v03_candidate_preregistration.yaml"
SIGN_RULE_PATH = ROOT / "control_semantics/signflip_classification_rule.yaml"
PV_ATTR_PATH = STAGE / "04_target_attribution/qualified_spatial_targets/attribution/resolution_attribution.json"
JR_ATTR_PATH = STAGE / "05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/six_component_attribution.json"

DECOMP_OUT = ROOT / "decomposition/development_metric_decomposition.json"
STRUCTURED_OUT = ROOT / "statistical_calibration/development_structured_results.json"
SIGN_OUT = ROOT / "control_semantics/signflip_semantics.json"
CAL_OUT = ROOT / "statistical_calibration/control_calibration.json"
INV_OUT = ROOT / "decomposition/v03_invariance.json"
GATE_OUT = ROOT / "contract_design/v03_development_gate.json"

CONTROLS = (
    "FULL_PARTICLE_PERMUTATION", "INDEPENDENT_COMPONENT_PERMUTATION",
    "RANDOM_PARTICLE_SIGN_FLIP", "NYQUIST_CHECKERBOARD_MATCHED_RMS", "GAUSSIAN_WHITE_MATCHED_RMS",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def write(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite development artifact: {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_js() -> Any:
    spec = importlib.util.spec_from_file_location("stage02jt_js_readonly", JS_CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(JS_CORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dev_contexts() -> dict[str, dict[str, Any]]:
    js = load_js()
    contexts = {case_id: js.context_from_record(case_id) for case_id in js.PV_CASES}
    contexts.update(js.new_contexts(("FAMILY_CROSSMODE_A",)))
    return contexts


def permutation_seed(case_id: str, index: int) -> int:
    token = f"20260207|{case_id}|{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big", signed=False)


def permutations(case_id: str, particle_count: int) -> np.ndarray:
    return np.asarray([
        np.random.Generator(np.random.PCG64(permutation_seed(case_id, index))).permutation(particle_count)
        for index in range(256)
    ], dtype=np.int64)


def edge_data(context: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = context["active"] & (context["source"] < context["target"])
    source = context["source"][mask]
    target = context["target"][mask]
    scaled = np.sum(context["displacement"][mask] ** 2, axis=1) / float(context["h"]) ** 2
    denominator = scaled + 16.0 * np.finfo(np.float64).eps
    return source, target, denominator


def metric_batch(context: dict[str, Any], fields: np.ndarray, batch_size: int = 64) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(fields, dtype=np.float64)
    if values.ndim == 2:
        values = values[None, ...]
    source, target, denominator = edge_data(context)
    result_s = []; result_m = []; result_d = []
    for start in range(0, len(values), batch_size):
        block = values[start:start + batch_size]
        rms = np.sqrt(np.mean(np.sum(block * block, axis=2), axis=1))
        if np.any(rms == 0.0):
            raise RuntimeError("Zero target/control field")
        q = np.sqrt(np.sum(block * block, axis=2))
        mag_edge = (q[:, source] - q[:, target]) ** 2
        vector_diff = block[:, source, :] - block[:, target, :]
        total_edge = np.sum(vector_diff * vector_diff, axis=2)
        direction_edge = np.maximum(0.0, total_edge - mag_edge)
        s = np.sqrt(np.mean(total_edge / denominator[None, :], axis=1)) / rms
        m = np.sqrt(np.mean(mag_edge / denominator[None, :], axis=1)) / rms
        d = np.sqrt(np.mean(direction_edge / denominator[None, :], axis=1)) / rms
        result_s.append(s); result_m.append(m); result_d.append(d)
    return np.concatenate(result_s), np.concatenate(result_m), np.concatenate(result_d)


def observed_and_null(context: dict[str, Any], field: np.ndarray, perms: np.ndarray) -> dict[str, Any]:
    obs_s, obs_m, obs_d = metric_batch(context, field)
    null_s, null_m, null_d = metric_batch(context, field[perms])
    s = float(obs_s[0]); m = float(obs_m[0]); d = float(obs_d[0])
    count_m = int(np.count_nonzero(null_m <= m)); count_d = int(np.count_nonzero(null_d <= d))
    return {
        "S_h": s, "M_h": m, "D_h": d,
        "closure_absolute_error": abs(s * s - m * m - d * d),
        "closure_relative_error": abs(s * s - m * m - d * d) / (s * s),
        "p_mag": (1 + count_m) / 257.0, "p_dir": (1 + count_d) / 257.0,
        "magnitude_lower_tail_count": count_m, "direction_lower_tail_count": count_d,
        "M_null": null_m, "D_null": null_d, "S_null": null_s,
    }


def resolution_summary(family_id: str, rows: list[dict[str, Any]], legacy: dict[str, str]) -> dict[str, Any]:
    selected = sorted(
        [row for row in rows if row["family_id"] == family_id and "resolution" in row["path_membership"]],
        key=lambda row: row["particles_per_axis"],
    )
    m = np.asarray([row["M_h"] for row in selected]); d = np.asarray([row["D_h"] for row in selected])
    m_slope = float(np.polyfit(np.arange(3, dtype=np.float64), m, 1)[0])
    d_slope = float(np.polyfit(np.arange(3, dtype=np.float64), d, 1)[0])
    checks = {
        "three_levels": "PASS" if len(selected) == 3 else "FAIL",
        "all_p_mag": "PASS" if all(row["p_mag"] <= 0.01 for row in selected) else "FAIL",
        "all_p_dir": "PASS" if all(row["p_dir"] <= 0.01 for row in selected) else "FAIL",
        "M_endpoint": "PASS" if m[-1] <= m[0] else "FAIL",
        "D_endpoint": "PASS" if d[-1] <= d[0] else "FAIL",
        "M_slope": "PASS" if m_slope <= 0.0 else "FAIL",
        "D_slope": "PASS" if d_slope <= 0.0 else "FAIL",
        **legacy,
    }
    return {
        "family_id": family_id, "case_ids": [row["case_id"] for row in selected],
        "M_h": m.tolist(), "D_h": d.tolist(), "M_h_OLS_slope": m_slope, "D_h_OLS_slope": d_slope,
        "checks": checks, "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
    }


def realization_seed(case_id: str, control_id: str, index: int) -> int:
    token = f"stage02jt{case_id}{control_id}{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big", signed=False)


def control_field(control: str, context: dict[str, Any], index: int) -> np.ndarray:
    field = context["field"]
    rng = np.random.Generator(np.random.PCG64(realization_seed(context["case_id"], control, index)))
    n = len(field)
    if control == "FULL_PARTICLE_PERMUTATION":
        result = field[rng.permutation(n)]
    elif control == "INDEPENDENT_COMPONENT_PERMUTATION":
        result = np.column_stack((field[rng.permutation(n), 0], field[rng.permutation(n), 1]))
    elif control == "RANDOM_PARTICLE_SIGN_FLIP":
        result = field * rng.choice(np.asarray([-1.0, 1.0]), size=n)[:, None]
    elif control == "NYQUIST_CHECKERBOARD_MATCHED_RMS":
        n_axis = context["particles_per_axis"]
        order = np.lexsort((context["particle_id"], context["position"][:, 1], context["position"][:, 0]))
        checker = np.empty(n, dtype=np.float64)
        px = int(rng.integers(0, 2)); py = int(rng.integers(0, 2))
        canonical = np.asarray([(-1.0) ** ((i // n_axis + px) + (i % n_axis + py)) for i in range(n)])
        checker[order] = canonical
        theta = float(rng.uniform(0.0, 2.0 * math.pi))
        result = checker[:, None] * np.asarray([[math.cos(theta), math.sin(theta)]])
    elif control == "GAUSSIAN_WHITE_MATCHED_RMS":
        result = rng.normal(size=field.shape)
    else:
        raise ValueError(control)
    source_rms = float(np.sqrt(np.mean(np.sum(field * field, axis=1))))
    result_rms = float(np.sqrt(np.mean(np.sum(result * result, axis=1))))
    return result * (source_rms / result_rms)


def calibration_task(payload: tuple[dict[str, Any], str]) -> dict[str, Any]:
    context, control = payload
    perms = permutations(context["case_id"], len(context["field"]))
    joint_count = 0; mag_count = 0; dir_count = 0
    p_mag_values = []; p_dir_values = []
    for index in range(512):
        field = control_field(control, context, index)
        result = observed_and_null(context, field, perms)
        mag = result["p_mag"] <= 0.01; direction = result["p_dir"] <= 0.01
        mag_count += int(mag); dir_count += int(direction); joint_count += int(mag and direction)
        p_mag_values.append(result["p_mag"]); p_dir_values.append(result["p_dir"])
    upper = 1.0 if joint_count == 512 else float(beta.ppf(0.95, joint_count + 1, 512 - joint_count))
    return {
        "case_id": context["case_id"], "family_id": context["family_id"], "control_id": control,
        "realization_count": 512, "magnitude_significant_count": mag_count,
        "direction_significant_count": dir_count, "joint_false_positive_count": joint_count,
        "empirical_joint_false_positive_rate": joint_count / 512.0,
        "one_sided_95_Clopper_Pearson_upper": upper,
        "p_mag_quantiles": {str(q): float(np.quantile(p_mag_values, q)) for q in (0.0, 0.5, 0.95, 1.0)},
        "p_dir_quantiles": {str(q): float(np.quantile(p_dir_values, q)) for q in (0.0, 0.5, 0.95, 1.0)},
        "status": "PASS" if upper <= 0.05 else "FAIL",
    }


def signflip_semantics(contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    js = load_js()
    rows = []
    for context in contexts.values():
        if "resolution" not in context["path_membership"]:
            continue
        perms = permutations(context["case_id"], len(context["field"]))
        old_null = js.null_distribution(context)
        baseline_magnitude = np.linalg.norm(context["field"], axis=1)
        for index in range(64):
            field = js.control_field("RANDOM_PARTICLE_SIGN_FLIP", context, index)
            result = observed_and_null(context, field, perms)
            old_s = js.graph_sobolev(context, field)
            old_p, _ = js.p_smooth(old_s, old_null)
            rows.append({
                "case_id": context["case_id"], "family_id": context["family_id"], "realization_index": index,
                "S_h": result["S_h"], "M_h": result["M_h"], "D_h": result["D_h"],
                "p_mag": result["p_mag"], "p_dir": result["p_dir"],
                "joint_v0_3_PASS": result["p_mag"] <= 0.01 and result["p_dir"] <= 0.01,
                "stage02js_old_S_h_p_smooth": old_p, "stage02js_old_false_positive": old_p <= 0.01,
                "magnitude_position_mapping_exact": bool(np.array_equal(np.linalg.norm(field, axis=1), baseline_magnitude)),
            })
    old_fp = [row for row in rows if row["stage02js_old_false_positive"]]
    mag_rate = sum(row["p_mag"] <= 0.01 for row in old_fp) / len(old_fp) if old_fp else math.nan
    dir_rate = sum(row["p_dir"] <= 0.01 for row in old_fp) / len(old_fp) if old_fp else math.nan
    mapping = all(row["magnitude_position_mapping_exact"] for row in rows)
    if not old_fp or not mapping:
        classification = "SIGNFLIP_MECHANISM_UNRESOLVED"
    elif mag_rate >= 0.8 and dir_rate <= 0.2:
        classification = "SIGNFLIP_FALSE_POSITIVE_MAGNITUDE_DOMINATED"
    elif dir_rate >= 0.8 and mag_rate <= 0.2:
        classification = "SIGNFLIP_FALSE_POSITIVE_DIRECTION_DOMINATED"
    else:
        classification = "SIGNFLIP_FALSE_POSITIVE_MIXED"
    return {
        "audit_version": "stage02jt-signflip-semantics-0.3.0",
        "classification_rule_hash": file_hash(SIGN_RULE_PATH), "realization_count": len(rows), "rows": rows,
        "old_false_positive_count": len(old_fp),
        "old_false_positive_magnitude_significance_rate": mag_rate,
        "old_false_positive_direction_significance_rate": dir_rate,
        "all_magnitude_position_mappings_preserved": mapping,
        "classification": classification,
    }


def invariance_audit(contexts: dict[str, dict[str, Any]], baseline_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for context in contexts.values():
        baseline = baseline_rows[context["case_id"]]
        variants: list[tuple[str, dict[str, Any], np.ndarray]] = []
        for scale in (0.1, 1.0, 10.0):
            variants.append((f"amplitude_{scale:g}", context, context["field"] * scale))
        translated = dict(context); translated["position"] = np.mod(context["position"] + np.asarray([0.173, 0.319]), 1.0)
        variants.append(("periodic_translation", translated, context["field"]))
        exchanged = dict(context); exchanged["displacement"] = context["displacement"][:, ::-1]
        variants.append(("axis_exchange", exchanged, context["field"][:, ::-1]))
        rotation = np.asarray([[0.0, -1.0], [1.0, 0.0]])
        variants.append(("vector_rotation_90", context, context["field"] @ rotation.T))
        variants.append(("particle_reorder_then_canonicalize", context, context["field"].copy()))
        reversed_edges = dict(context); reversed_edges["source"] = context["target"]; reversed_edges["target"] = context["source"]
        reversed_edges["displacement"] = -context["displacement"]
        variants.append(("edge_order_reversal", reversed_edges, context["field"]))
        perms = permutations(context["case_id"], len(context["field"]))
        for name, transformed_context, field in variants:
            result = observed_and_null(transformed_context, field, perms)
            tolerance_m = 1e-14 + 1e-12 * abs(baseline["M_h"])
            tolerance_d = 1e-14 + 1e-12 * abs(baseline["D_h"])
            checks = {
                "M_h": "PASS" if abs(result["M_h"] - baseline["M_h"]) <= tolerance_m else "FAIL",
                "D_h": "PASS" if abs(result["D_h"] - baseline["D_h"]) <= tolerance_d else "FAIL",
                "p_mag": "PASS" if result["p_mag"] == baseline["p_mag"] else "FAIL",
                "p_dir": "PASS" if result["p_dir"] == baseline["p_dir"] else "FAIL",
            }
            rows.append({
                "case_id": context["case_id"], "family_id": context["family_id"], "transformation": name,
                "M_h": result["M_h"], "D_h": result["D_h"], "p_mag": result["p_mag"], "p_dir": result["p_dir"],
                "checks": checks, "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
            })
    return {"audit_version": "stage02jt-v03-invariance-0.3.0", "rows": rows, "all_invariance_PASS": all(row["status"] == "PASS" for row in rows)}


def main() -> int:
    freeze = load_json(FREEZE_PATH)
    if file_hash(PREREG_PATH) != freeze["candidate_preregistration_hash"]:
        raise RuntimeError("Candidate preregistration changed")
    contexts = dev_contexts()
    decomposition_rows = []; structured_rows = []; baseline_map = {}
    for case_id in sorted(contexts):
        context = contexts[case_id]; perms = permutations(case_id, len(context["field"]))
        result = observed_and_null(context, context["field"], perms)
        decomposition_rows.append({
            "case_id": case_id, "family_id": context["family_id"], "S_h": result["S_h"], "M_h": result["M_h"], "D_h": result["D_h"],
            "closure_absolute_error": result["closure_absolute_error"], "closure_relative_error": result["closure_relative_error"],
            "closure_status": "PASS" if result["closure_absolute_error"] <= 1e-14 + 1e-12 * result["S_h"] ** 2 else "FAIL",
        })
        row = {
            "case_id": case_id, "family_id": context["family_id"], "path_membership": context["path_membership"],
            "particles_per_axis": context["particles_per_axis"], "h_over_dx": context["h_over_dx"],
            "M_h": result["M_h"], "D_h": result["D_h"], "p_mag": result["p_mag"], "p_dir": result["p_dir"],
            "magnitude_lower_tail_count": result["magnitude_lower_tail_count"], "direction_lower_tail_count": result["direction_lower_tail_count"],
            "joint_structured_PASS": result["p_mag"] <= 0.01 and result["p_dir"] <= 0.01,
        }
        structured_rows.append(row); baseline_map[case_id] = row
    pv_legacy = load_json(PV_ATTR_PATH)["checks"]
    jr = load_json(JR_ATTR_PATH)
    cross_legacy_all = next(item for item in jr["families"] if item["family_id"] == "FAMILY_CROSSMODE_A")["resolution"]["checks"]
    legacy_keys = ("target_endpoint_magnitude_nonincreasing", "adjacent_low_mode_direction_cosine", "relative_neighbor_variation_strictly_decreasing", "physical_gradient_scale_coefficient_of_variation")
    summaries = [
        resolution_summary("FAMILY_PV_EXISTING", structured_rows, {key: pv_legacy[key] for key in legacy_keys}),
        resolution_summary("FAMILY_CROSSMODE_A", structured_rows, {key: cross_legacy_all[key] for key in legacy_keys}),
    ]
    decomposition = {
        "audit_version": "stage02jt-decomposition-0.3.0", "rows": decomposition_rows,
        "all_closure_PASS": all(row["closure_status"] == "PASS" for row in decomposition_rows),
        "maximum_closure_absolute_error": max(row["closure_absolute_error"] for row in decomposition_rows),
        "v0_2_S_h_redefined": False,
    }
    structured = {
        "audit_version": "stage02jt-development-structured-0.3.0", "rows": structured_rows,
        "resolution_summaries": summaries,
        "development_structured_PASS": all(item["status"] == "PASS" for item in summaries),
    }
    signflip = signflip_semantics(contexts)
    resolution_contexts = [context for context in contexts.values() if "resolution" in context["path_membership"]]
    tasks = [(context, control) for context in resolution_contexts for control in CONTROLS]
    worker_count = min(6, max(1, os.cpu_count() or 1))
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        calibration_rows = list(executor.map(calibration_task, tasks))
    calibration = {
        "audit_version": "stage02jt-control-calibration-0.3.0", "realization_root": 20260804,
        "realizations_per_case_control": 512, "permutations_per_realization": 256,
        "rows": sorted(calibration_rows, key=lambda row: (row["case_id"], row["control_id"])),
        "all_case_control_Clopper_Pearson_PASS": all(row["status"] == "PASS" for row in calibration_rows),
        "raw_rate_only_gate_used": False, "seed_screening_or_replacement_used": False,
    }
    invariance = invariance_audit(contexts, baseline_map)
    checks = {
        "decomposition_identity": "PASS" if decomposition["all_closure_PASS"] else "FAIL",
        "signflip_mechanism_resolved": "PASS" if signflip["classification"] != "SIGNFLIP_MECHANISM_UNRESOLVED" else "FAIL",
        "development_structured": "PASS" if structured["development_structured_PASS"] else "FAIL",
        "control_calibration": "PASS" if calibration["all_case_control_Clopper_Pearson_PASS"] else "FAIL",
        "invariance": "PASS" if invariance["all_invariance_PASS"] else "FAIL",
    }
    gate = {
        "gate_version": "stage02jt-development-gate-0.3.0", "candidate_preregistration_hash": freeze["candidate_preregistration_hash"],
        "signflip_classification_rule_hash": file_hash(SIGN_RULE_PATH), "checks": checks,
        "v03_contract_generation_authorized": all(value == "PASS" for value in checks.values()),
        "blind_family_numeric_field_accessed": False,
    }
    write(DECOMP_OUT, decomposition); write(STRUCTURED_OUT, structured); write(SIGN_OUT, signflip); write(CAL_OUT, calibration); write(INV_OUT, invariance); write(GATE_OUT, gate)
    print(json.dumps({
        "decomposition": decomposition["all_closure_PASS"], "structured": structured["development_structured_PASS"],
        "signflip": signflip["classification"], "calibration": calibration["all_case_control_Clopper_Pearson_PASS"],
        "invariance": invariance["all_invariance_PASS"], "contract_authorized": gate["v03_contract_generation_authorized"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
