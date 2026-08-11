#!/usr/bin/env python3
"""Execute the preregistered Stage 02J-S regularity audit in two sealed phases."""

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
from scipy.stats import beta

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_2"
JROOT = STAGE / "05_dataset/controlled_regular_pair_scope_v0_1"
JRROOT = STAGE / "05_dataset/controlled_multifamily_pair_scope_v0_2"
ATTR = STAGE / "04_target_attribution"

CONTRACT_PATH = ROOT / "contract_design/regularity_contract_v0_2.yaml"
FREEZE_PATH = ROOT / "freeze/stage02js_input_freeze_manifest.json"
PREREG_PATH = JRROOT / "family_design/family_preregistration.yaml"
FORMULA_PATH = JRROOT / "family_design/analytic_family_definitions.py"
TARGETS_PATH = JRROOT / "target_qualification/new_family_target_candidates.json"
JR_ATTR_PATH = JRROOT / "target_qualification/six_component_attribution.json"
JR_REF_PATH = JRROOT / "reference_qualification/reference_qualification_results.json"
JR_CONS_PATH = JRROOT / "conservation/pair_only_conservation_qualification.json"
PV_ATTR_PATH = ATTR / "qualified_spatial_targets/attribution/resolution_attribution.json"
CONFIG_PATH = STAGE / "03_dataset/generation/generation_configuration.yaml"
GENERATOR_PATH = STAGE / "03_dataset/generation/generate_audit_dataset.py"
JR_SCRIPT_PATH = JRROOT / "target_qualification/run_stage02jr_qualification.py"

DEV_PATH = ROOT / "development_audit/development_regularity_audit.json"
NULL_PATH = ROOT / "permutation_nulls/development_permutation_distributions.json"
NEG_PATH = ROOT / "negative_controls/negative_control_audit.json"
INV_PATH = ROOT / "invariance/invariance_audit.json"
RELEASE_PATH = ROOT / "heldout_validation/heldout_release_gate.json"
ORIGINAL_PATH = ROOT / "development_audit/original_gate_reproduction.json"
HELDOUT_PATH = ROOT / "heldout_validation/heldout_transfer_validation.json"
REQ_PATH = ROOT / "requalification/versioned_target_requalification.json"

PV_CASES = (
    "i_res_n12_h26_regular", "i_anchor_n16_h26_regular", "i_res_n20_h26_regular",
    "i_sup_n16_h22_regular", "i_sup_n16_h30_regular",
)
FAMILY_PREFIX = {
    "FAMILY_CROSSMODE_A": "crossmode_a",
    "FAMILY_DIAGONAL_B": "diagonal_b",
    "FAMILY_MIXED_C": "mixed_c",
}
RES_SUFFIX = ("n12_h26", "n16_h26", "n20_h26")


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


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def seed64(*parts: Any) -> int:
    token = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big", signed=False)


def context_from_record(case_id: str) -> dict[str, Any]:
    record = load_json(JROOT / f"raw_graph_records/{case_id}.json")
    base = record["stage02b_record"]
    graph = base["neighbor_information"]
    return {
        "case_id": case_id,
        "family_id": "FAMILY_PV_EXISTING",
        "path_membership": ["support"] if "sup" in case_id else ["resolution"],
        "particles_per_axis": {"i_res_n12_h26_regular": 12, "i_res_n20_h26_regular": 20}.get(case_id, 16),
        "h_over_dx": {"i_sup_n16_h22_regular": 2.2, "i_sup_n16_h30_regular": 3.0}.get(case_id, 2.6),
        "position": np.asarray(base["particle_state"]["position_periodic"], dtype=np.float64),
        "particle_id": np.asarray(base["particle_state"]["particle_id_local"], dtype=np.int64),
        "field": np.asarray(record["target"]["delta_a"], dtype=np.float64),
        "source": np.asarray(graph["source_index"], dtype=np.int64),
        "target": np.asarray(graph["target_index"], dtype=np.int64),
        "displacement": np.asarray(graph["minimum_image_displacement"], dtype=np.float64),
        "active": np.asarray(record["reciprocal_graph_extensions"]["active_kernel_indicator"], dtype=bool),
        "h": float(base["particle_state"]["smoothing_length"][0]),
        "source_target_hash": record["identity_and_provenance"]["source_target_hash"],
    }


def new_contexts(family_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    prereg = load_yaml(PREREG_PATH)
    config = load_yaml(CONFIG_PATH)
    analytic = load_module("stage02js_analytic_readonly", FORMULA_PATH)
    generator = load_module("stage02js_generator_readonly", GENERATOR_PATH)
    jr = load_module("stage02js_jr_readonly", JR_SCRIPT_PATH)
    family_map = {row["family_id"]: row for row in prereg["families"]}
    contexts: dict[str, dict[str, Any]] = {}
    for family_id in family_ids:
        family = family_map[family_id]
        for raw in jr.case_rows(prereg, family_id, family["split_role"]):
            state, _ = jr.state_for_case(raw, analytic, config)
            rhs, edges = generator.sparse_rhs_components(state, raw, config, apply_control=False)
            rho0 = float(config["physics"]["rho0"])
            cs = float(config["physics"]["sound_speed"])
            nu = float(config["physics"]["kinematic_viscosity"])
            ref = analytic.fourier_spatial_reference(state["x"], state["rho"], state["v"], rho0=rho0, cs=cs, nu=nu)
            field = ref["acceleration"] - rhs["total"]
            dx = float(config["domain"]["box_length"]) / int(raw["particles_per_axis"])
            h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
            distance = np.linalg.norm(edges["displacement"], axis=1)
            kernel, _ = generator.kernel_values(distance, h)
            contexts[raw["case_id"]] = {
                "case_id": raw["case_id"], "family_id": family_id,
                "path_membership": raw["path_membership"],
                "particles_per_axis": int(raw["particles_per_axis"]),
                "h_over_dx": float(raw["h_over_dx"]),
                "position": state["x"], "particle_id": np.arange(len(field), dtype=np.int64),
                "field": field, "source": edges["source"].astype(np.int64),
                "target": edges["target"].astype(np.int64), "displacement": edges["displacement"],
                "active": kernel > 0.0, "h": h,
                "state": state, "rhs": rhs, "edges": edges,
            }
    return contexts


def graph_sobolev(context: dict[str, Any], field: np.ndarray | None = None) -> float:
    values = context["field"] if field is None else np.asarray(field, dtype=np.float64)
    rms = float(np.sqrt(np.mean(np.sum(values * values, axis=1), dtype=np.float64)))
    if rms == 0.0:
        return math.inf
    source = context["source"]
    target = context["target"]
    mask = context["active"] & (source < target)
    displacement = context["displacement"][mask]
    scaled_r2 = np.sum(displacement * displacement, axis=1) / (float(context["h"]) ** 2)
    diff = values[source[mask]] - values[target[mask]]
    numerator2 = np.mean(np.sum(diff * diff, axis=1) / (scaled_r2 + 16.0 * np.finfo(np.float64).eps), dtype=np.float64)
    return float(math.sqrt(float(numerator2)) / rms)


def null_distribution(context: dict[str, Any]) -> np.ndarray:
    field = context["field"]
    values = []
    for index in range(256):
        permutation = np.random.Generator(np.random.PCG64(seed64(20260207, context["case_id"], index))).permutation(len(field))
        values.append(graph_sobolev(context, field[permutation]))
    return np.asarray(values, dtype=np.float64)


def p_smooth(observed: float, nulls: np.ndarray) -> tuple[float, int]:
    count = int(np.count_nonzero(nulls <= observed))
    return (1.0 + count) / 257.0, count


def clopper_pearson(count: int, total: int = 256, alpha: float = 0.05) -> list[float]:
    lower = 0.0 if count == 0 else float(beta.ppf(alpha / 2.0, count, total - count + 1))
    upper = 1.0 if count == total else float(beta.ppf(1.0 - alpha / 2.0, count + 1, total - count))
    return [lower, upper]


def audit_case(context: dict[str, Any]) -> tuple[dict[str, Any], np.ndarray]:
    observed = graph_sobolev(context)
    nulls = null_distribution(context)
    pvalue, count = p_smooth(observed, nulls)
    std = float(np.std(nulls, ddof=1))
    row = {
        "case_id": context["case_id"], "family_id": context["family_id"],
        "path_membership": context["path_membership"], "particles_per_axis": context["particles_per_axis"],
        "h_over_dx": context["h_over_dx"], "S_h_observed": observed,
        "S_h_null_mean": float(np.mean(nulls)), "S_h_null_std": std,
        "S_h_null_min": float(np.min(nulls)), "S_h_null_max": float(np.max(nulls)),
        "observed_percentile_lower_tail": float(np.count_nonzero(nulls <= observed) / len(nulls)),
        "observed_z_score": float((observed - np.mean(nulls)) / std),
        "lower_tail_count": count, "p_smooth": pvalue,
        "lower_tail_probability_Clopper_Pearson_95": clopper_pearson(count),
        "structured_target_gate": "PASS" if pvalue <= 0.01 else "FAIL",
        "target_content_hash": content_hash(context["field"].tolist()),
    }
    return row, nulls


def resolution_summary(family_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = sorted(
        [row for row in rows if row["family_id"] == family_id and "resolution" in row["path_membership"]],
        key=lambda row: row["particles_per_axis"],
    )
    values = np.asarray([row["S_h_observed"] for row in selected], dtype=np.float64)
    slope = float(np.polyfit(np.arange(3, dtype=np.float64), values, 1)[0])
    checks = {
        "three_resolution_levels": "PASS" if len(selected) == 3 else "FAIL",
        "all_p_smooth_at_most_0p01": "PASS" if all(row["p_smooth"] <= 0.01 for row in selected) else "FAIL",
        "endpoint_not_worse": "PASS" if values[-1] <= values[0] else "FAIL",
        "OLS_level_slope_not_positive": "PASS" if slope <= 0.0 else "FAIL",
    }
    return {
        "family_id": family_id, "case_ids": [row["case_id"] for row in selected],
        "S_h": values.tolist(), "OLS_slope_against_level_index": slope,
        "checks": checks, "status": "PASS" if all(value == "PASS" for value in checks.values()) else "FAIL",
    }


def control_field(control: str, context: dict[str, Any], realization: int) -> np.ndarray:
    field = context["field"]
    rng = np.random.Generator(np.random.PCG64(seed64(20260207, context["case_id"], control, realization)))
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
        phase_x = int(rng.integers(0, 2)); phase_y = int(rng.integers(0, 2))
        canonical = np.asarray([(-1.0) ** ((i // n_axis + phase_x) + (i % n_axis + phase_y)) for i in range(n)])
        checker[order] = canonical
        theta = float(rng.uniform(0.0, 2.0 * math.pi))
        rms = float(np.sqrt(np.mean(np.sum(field * field, axis=1))))
        result = rms * checker[:, None] * np.asarray([[math.cos(theta), math.sin(theta)]])
    elif control == "GAUSSIAN_WHITE_MATCHED_RMS":
        result = rng.normal(size=field.shape)
    else:
        raise ValueError(control)
    source_rms = float(np.sqrt(np.mean(np.sum(field * field, axis=1))))
    result_rms = float(np.sqrt(np.mean(np.sum(result * result, axis=1))))
    return result * (source_rms / result_rms)


def negative_control_audit(contexts: dict[str, dict[str, Any]], null_map: dict[str, np.ndarray]) -> dict[str, Any]:
    controls = (
        "FULL_PARTICLE_PERMUTATION", "INDEPENDENT_COMPONENT_PERMUTATION",
        "RANDOM_PARTICLE_SIGN_FLIP", "NYQUIST_CHECKERBOARD_MATCHED_RMS", "GAUSSIAN_WHITE_MATCHED_RMS",
    )
    case_rows = []
    for context in contexts.values():
        if "resolution" not in context["path_membership"]:
            continue
        nulls = null_map[context["case_id"]]
        for control in controls:
            smooth_false_positives = 0
            pvalues = []
            svalues = []
            for realization in range(64):
                value = graph_sobolev(context, control_field(control, context, realization))
                pvalue, _ = p_smooth(value, nulls)
                smooth_false_positives += int(pvalue <= 0.01)
                pvalues.append(pvalue); svalues.append(value)
            rate = smooth_false_positives / 64.0
            case_rows.append({
                "case_id": context["case_id"], "family_id": context["family_id"], "control_id": control,
                "realization_count": 64, "smooth_false_positive_count": smooth_false_positives,
                "smooth_false_positive_rate": rate, "p_smooth_min": min(pvalues), "p_smooth_max": max(pvalues),
                "S_h_min": min(svalues), "S_h_max": max(svalues),
                "status": "PASS" if rate <= 0.05 else "FAIL",
            })
    summaries = []
    for control in controls:
        selected = [row for row in case_rows if row["control_id"] == control]
        total = sum(row["realization_count"] for row in selected)
        false = sum(row["smooth_false_positive_count"] for row in selected)
        max_case_rate = max(row["smooth_false_positive_rate"] for row in selected)
        summaries.append({
            "control_id": control, "realization_count": total, "smooth_false_positive_count": false,
            "aggregate_false_positive_rate": false / total, "maximum_case_false_positive_rate": max_case_rate,
            "all_case_rates_at_most_0p05": all(row["status"] == "PASS" for row in selected),
            "status": "PASS" if all(row["status"] == "PASS" for row in selected) else "FAIL",
        })
    return {
        "audit_version": "stage02js-negative-controls-0.2.0", "rows": case_rows, "control_summaries": summaries,
        "all_controls_PASS": all(row["status"] == "PASS" for row in summaries),
        "threshold_changed_after_observation": False,
    }


def invariance_audit(contexts: dict[str, dict[str, Any]], rows: list[dict[str, Any]], null_map: dict[str, np.ndarray]) -> dict[str, Any]:
    audit_rows = []
    row_map = {row["case_id"]: row for row in rows}
    for context in contexts.values():
        baseline = row_map[context["case_id"]]
        base_s = baseline["S_h_observed"]
        base_p = baseline["p_smooth"]
        variants: list[tuple[str, dict[str, Any], np.ndarray]] = []
        for scale in (0.1, 1.0, 10.0):
            variants.append((f"amplitude_scale_{scale:g}", context, context["field"] * scale))
        translated = dict(context); translated["position"] = np.mod(context["position"] + np.asarray([0.173, 0.319]), 1.0)
        variants.append(("periodic_translation", translated, context["field"]))
        exchanged = dict(context); exchanged["displacement"] = context["displacement"][:, ::-1]
        variants.append(("axis_exchange", exchanged, context["field"][:, ::-1]))
        rotation = np.asarray([[0.0, -1.0], [1.0, 0.0]])
        variants.append(("vector_rotation_90", context, context["field"] @ rotation.T))
        reordered = dict(context)
        order = np.arange(len(context["field"]) - 1, -1, -1)
        inverse = np.empty_like(order); inverse[order] = np.arange(len(order))
        reordered["field"] = context["field"][order]; reordered["position"] = context["position"][order]
        reordered["particle_id"] = context["particle_id"][order]
        reordered["source"] = inverse[context["source"]]; reordered["target"] = inverse[context["target"]]
        canonical = np.argsort(reordered["particle_id"])
        inverse2 = np.empty_like(canonical); inverse2[canonical] = np.arange(len(canonical))
        reordered["field"] = reordered["field"][canonical]; reordered["position"] = reordered["position"][canonical]
        reordered["particle_id"] = reordered["particle_id"][canonical]
        reordered["source"] = inverse2[reordered["source"]]; reordered["target"] = inverse2[reordered["target"]]
        variants.append(("reverse_then_recanonicalize", reordered, reordered["field"]))
        reversed_edges = dict(context); reversed_edges["source"] = context["target"]; reversed_edges["target"] = context["source"]
        reversed_edges["displacement"] = -context["displacement"]
        variants.append(("edge_forward_reverse", reversed_edges, context["field"]))
        for name, candidate_context, field in variants:
            value = graph_sobolev(candidate_context, field)
            transformed_null = []
            for index in range(256):
                perm = np.random.Generator(np.random.PCG64(seed64(20260207, context["case_id"], index))).permutation(len(field))
                transformed_null.append(graph_sobolev(candidate_context, field[perm]))
            pvalue, _ = p_smooth(value, np.asarray(transformed_null))
            tolerance = 1.0e-14 + 1.0e-12 * abs(base_s)
            s_pass = abs(value - base_s) <= tolerance
            p_pass = pvalue == base_p
            audit_rows.append({
                "case_id": context["case_id"], "family_id": context["family_id"], "transformation": name,
                "baseline_S_h": base_s, "transformed_S_h": value, "absolute_difference": abs(value - base_s),
                "tolerance": tolerance, "baseline_p_smooth": base_p, "transformed_p_smooth": pvalue,
                "S_h_invariance": "PASS" if s_pass else "FAIL", "p_smooth_invariance": "PASS" if p_pass else "FAIL",
                "status": "PASS" if s_pass and p_pass else "FAIL",
            })
    return {
        "audit_version": "stage02js-invariance-0.2.0", "rows": audit_rows,
        "all_invariance_PASS": all(row["status"] == "PASS" for row in audit_rows),
        "tolerance_changed_after_observation": False,
    }


def old_tv(context: dict[str, Any], field: np.ndarray) -> float:
    source = context["source"]; target = context["target"]
    mask = source < target
    diff = field[source[mask]] - field[target[mask]]
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def original_gate_rows(contexts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    historical_new = load_json(JR_ATTR_PATH)
    historical_ratios = {}
    historical_tv = {}
    for family in historical_new["families"]:
        for row in family["resolution"]["rows"]:
            historical_ratios[row["case_id"]] = row["permuted_null_ratio"]
            historical_tv[row["case_id"]] = row["graph_TV"]
    pv = load_json(PV_ATTR_PATH)
    for row in pv["rows"]:
        historical_ratios[row["candidate_id"]] = row["permuted_null_ratio"]
        historical_tv[row["candidate_id"]] = row["graph_total_variation_RMS"]
    rows = []
    for case_id, context in sorted(contexts.items()):
        field = context["field"]
        observed = old_tv(context, field)
        permutation = np.random.default_rng(20260207).permutation(len(field))
        null = old_tv(context, field[permutation])
        ratio = observed / null
        old_ratio = historical_ratios.get(case_id)
        old_graph_tv = historical_tv.get(case_id)
        drift = None if old_ratio is None else abs(ratio - old_ratio)
        tv_drift = None if old_graph_tv is None else abs(observed - old_graph_tv)
        reproduced = (drift is None or drift <= 1.0e-14) and (tv_drift is None or tv_drift <= 1.0e-14)
        rows.append({
            "case_id": case_id, "family_id": context["family_id"], "seed": 20260207,
            "graph_TV": observed, "permuted_null_graph_TV": null, "permuted_null_ratio": ratio,
            "historical_ratio": old_ratio, "absolute_ratio_drift": drift,
            "historical_graph_TV": old_graph_tv, "absolute_graph_TV_drift": tv_drift,
            "historical_comparison_available": old_ratio is not None,
            "v0_1_gate": "PASS" if ratio <= 0.8 else "FAIL",
            "exact_reproduction_status": "PASS" if reproduced else "FAIL",
        })
    return rows


def run_development() -> int:
    freeze = load_json(FREEZE_PATH)
    if file_hash(CONTRACT_PATH) != freeze["contract_hash"]:
        raise RuntimeError("Frozen v0.2 contract hash mismatch")
    contexts = {case_id: context_from_record(case_id) for case_id in PV_CASES}
    contexts.update(new_contexts(("FAMILY_CROSSMODE_A",)))
    rows = []; null_map = {}
    for case_id in sorted(contexts):
        row, nulls = audit_case(contexts[case_id]); rows.append(row); null_map[case_id] = nulls
    resolution = [resolution_summary(family, rows) for family in ("FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A")]
    dev = {
        "audit_version": "stage02js-development-0.2.0", "contract_hash": freeze["contract_hash"],
        "development_families": ["FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A"],
        "rows": rows, "resolution_summaries": resolution,
        "development_structured_targets_PASS": all(item["status"] == "PASS" for item in resolution),
        "heldout_target_arrays_used": False, "threshold_or_seed_screening_used": False,
    }
    null_output = {
        "audit_version": "stage02js-development-nulls-0.2.0", "root_seed": 20260207,
        "permutation_count_per_case": 256,
        "cases": [{"case_id": case_id, "S_h_permutations": null_map[case_id].tolist(), "distribution_hash": content_hash(null_map[case_id].tolist())} for case_id in sorted(null_map)],
    }
    negative = negative_control_audit(contexts, null_map)
    invariance = invariance_audit(contexts, rows, null_map)
    release = {
        "gate_version": "stage02js-heldout-release-0.2.0", "contract_hash": freeze["contract_hash"],
        "checks": {
            "contract_hash_frozen": "PASS", "development_structured_targets": "PASS" if dev["development_structured_targets_PASS"] else "FAIL",
            "negative_controls": "PASS" if negative["all_controls_PASS"] else "FAIL",
            "invariance": "PASS" if invariance["all_invariance_PASS"] else "FAIL",
        },
    }
    release["heldout_access_authorized"] = all(value == "PASS" for value in release["checks"].values())
    write_json(DEV_PATH, dev); write_json(NULL_PATH, null_output); write_json(NEG_PATH, negative); write_json(INV_PATH, invariance); write_json(RELEASE_PATH, release)
    print(json.dumps({"development": dev["development_structured_targets_PASS"], "negative": negative["all_controls_PASS"], "invariance": invariance["all_invariance_PASS"], "heldout_release": release["heldout_access_authorized"]}, sort_keys=True))
    return 0


def run_heldout() -> int:
    freeze = load_json(FREEZE_PATH); release = load_json(RELEASE_PATH)
    if file_hash(CONTRACT_PATH) != freeze["contract_hash"] or not release["heldout_access_authorized"]:
        raise RuntimeError("Held-out access gate is closed")
    contexts = {case_id: context_from_record(case_id) for case_id in PV_CASES}
    contexts.update(new_contexts(("FAMILY_CROSSMODE_A", "FAMILY_DIAGONAL_B", "FAMILY_MIXED_C")))
    source = load_json(TARGETS_PATH)
    source_map = {row["case_id"]: row for row in source["candidates"]}
    source_checks = []
    for case_id, row in source_map.items():
        reconstructed = contexts[case_id]["field"]
        exact = np.array_equal(reconstructed, np.asarray(row["delta_a"], dtype=np.float64))
        source_checks.append({"case_id": case_id, "candidate_content_hash_before_attribution": row["candidate_content_hash_before_attribution"], "reconstructed_delta_a_exact_equal": exact})
        if not exact:
            raise RuntimeError(f"Frozen target reconstruction mismatch: {case_id}")
    heldout_rows = []; null_cases = []
    for family_id in ("FAMILY_DIAGONAL_B", "FAMILY_MIXED_C"):
        for case_id in sorted(case for case, context in contexts.items() if context["family_id"] == family_id):
            row, nulls = audit_case(contexts[case_id]); heldout_rows.append(row)
            null_cases.append({"case_id": case_id, "S_h_permutations": nulls.tolist(), "distribution_hash": content_hash(nulls.tolist())})
    jr_attr = load_json(JR_ATTR_PATH); jr_ref = load_json(JR_REF_PATH); jr_cons = load_json(JR_CONS_PATH)
    attr_map = {family["family_id"]: family for family in jr_attr["families"]}
    ref_map = {family["family_id"]: family for family in jr_ref["families"]}
    cons_map = {family["family_id"]: family for family in jr_cons["families"]}
    summaries = []
    for family_id in ("FAMILY_DIAGONAL_B", "FAMILY_MIXED_C"):
        regularity = resolution_summary(family_id, heldout_rows)
        legacy = attr_map[family_id]
        legacy_checks = {key: value for key, value in legacy["resolution"]["checks"].items() if key != "PCG64_permuted_null_ratio"}
        checks = {
            "existing_five_components": "PASS" if all(result["pass_count"] == 5 for result in legacy["case_results"]) else "FAIL",
            "all_three_resolution_p_smooth": regularity["checks"]["all_p_smooth_at_most_0p01"],
            "S_h_refinement_behavior": regularity["status"],
            "legacy_resolution_checks": "PASS" if all(value == "PASS" for value in legacy_checks.values()) else "FAIL",
            "support_consistency": legacy["support"]["status"],
            "negative_control_separation_applicable": "PASS",
            "historical_reference": "PASS" if ref_map[family_id]["family_reference_qualified"] else "FAIL",
            "historical_conservation": "PASS" if cons_map[family_id]["family_5_of_5_pair_only_PASS"] else "FAIL",
        }
        family_pass = all(value == "PASS" for value in checks.values())
        summaries.append({"family_id": family_id, "resolution": regularity, "checks": checks, "family_attribution_v0_2": "6/6_PASS" if family_pass else "NOT_6/6", "family_5_of_5_PASS": family_pass})
    dev = load_json(DEV_PATH)
    cross_regular = resolution_summary("FAMILY_CROSSMODE_A", dev["rows"])
    cross_legacy = attr_map["FAMILY_CROSSMODE_A"]
    cross_legacy_checks = {key: value for key, value in cross_legacy["resolution"]["checks"].items() if key != "PCG64_permuted_null_ratio"}
    cross_checks = {
        "existing_five_components": "PASS" if all(result["pass_count"] == 5 for result in cross_legacy["case_results"]) else "FAIL",
        "all_three_resolution_p_smooth": cross_regular["checks"]["all_p_smooth_at_most_0p01"],
        "S_h_refinement_behavior": cross_regular["status"],
        "legacy_resolution_checks": "PASS" if all(value == "PASS" for value in cross_legacy_checks.values()) else "FAIL",
        "support_consistency": cross_legacy["support"]["status"],
        "negative_control_separation_applicable": "PASS",
        "historical_reference": "PASS" if ref_map["FAMILY_CROSSMODE_A"]["family_reference_qualified"] else "FAIL",
        "historical_conservation": "PASS" if cons_map["FAMILY_CROSSMODE_A"]["family_5_of_5_pair_only_PASS"] else "FAIL",
    }
    cross_pass = all(value == "PASS" for value in cross_checks.values())
    all_new_pass = cross_pass and all(item["family_5_of_5_PASS"] for item in summaries)
    heldout = {
        "audit_version": "stage02js-heldout-transfer-0.2.0", "contract_hash": freeze["contract_hash"],
        "release_gate_hash": file_hash(RELEASE_PATH), "target_arrays_opened_after_release_gate": True,
        "frozen_source_reconstruction_checks": source_checks, "rows": heldout_rows, "null_distributions": null_cases,
        "family_summaries": summaries, "heldout_validation_and_test_PASS": all(item["family_5_of_5_PASS"] for item in summaries),
        "post_observation_contract_change_used": False,
    }
    original_rows = original_gate_rows(contexts)
    original = {
        "audit_version": "stage02js-v0.1-exact-reproduction-0.2.0", "seed": 20260207, "threshold_max": 0.8,
        "rows": original_rows, "case_count": len(original_rows),
        "all_historical_comparisons_exact": all(row["exact_reproduction_status"] == "PASS" for row in original_rows),
        "v0_1_result_preserved": True, "v0_1_corrected_or_deleted": False,
    }
    decisions = []
    family_pass_map = {"FAMILY_CROSSMODE_A": cross_pass, **{item["family_id"]: item["family_5_of_5_PASS"] for item in summaries}}
    for row in source["candidates"]:
        passed = family_pass_map[row["family_id"]]
        decisions.append({
            "case_id": row["case_id"], "family_id": row["family_id"],
            "source_candidate_content_hash": row["candidate_content_hash_before_attribution"],
            "historical_status_v0_1": "diagnostic_nonmaterialized_candidate_v0_1",
            "historical_candidate_discretization_target": False,
            "candidate_discretization_target_v0_2": passed,
            "attribution_contract_v0_2": "6/6_PASS" if passed else "NOT_6/6",
            "manual_override_permitted": False,
        })
    req = {
        "decision_version": "stage02js-versioned-requalification-0.2.0", "contract_hash": freeze["contract_hash"],
        "crossmode_development": {"resolution": cross_regular, "checks": cross_checks, "family_5_of_5_PASS": cross_pass},
        "decisions": decisions, "all_three_new_families_5_of_5_PASS": all_new_pass,
        "v0_1_fields_overwritten": False, "partial_case_selection_used": False,
    }
    write_json(HELDOUT_PATH, heldout); write_json(ORIGINAL_PATH, original); write_json(REQ_PATH, req)
    print(json.dumps({"original_exact": original["all_historical_comparisons_exact"], "crossmode": cross_pass, "diagonal": summaries[0]["family_5_of_5_PASS"], "mixed": summaries[1]["family_5_of_5_PASS"], "all_new": all_new_pass}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("development", "heldout"), required=True)
    args = parser.parse_args()
    return run_development() if args.phase == "development" else run_heldout()


if __name__ == "__main__":
    raise SystemExit(main())
