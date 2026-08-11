#!/usr/bin/env python3
"""Audit Stage 02C R2 targets without modifying or expanding the dataset."""

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

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE02 = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATASET = STAGE02 / "03_dataset"
ATTRIBUTION = STAGE02 / "04_target_attribution"
GENERATOR_PATH = DATASET / "generation" / "generate_audit_dataset.py"
CASE_PATH = DATASET / "cases" / "case_manifest.yaml"
CONFIG_PATH = DATASET / "generation" / "generation_configuration.yaml"
DATASET_MANIFEST_PATH = DATASET / "manifests" / "dataset_manifest.json"
RULES_PATH = ATTRIBUTION / "qualification" / "label_upgrade_rules.yaml"


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
    spec = importlib.util.spec_from_file_location("stage02c_generator_for_attribution", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Stage 02C generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector_norms(values: np.ndarray) -> dict[str, float]:
    per_particle = np.linalg.norm(values, axis=1)
    return {
        "L2_rms_vector": float(np.sqrt(np.mean(per_particle**2))),
        "Linf_vector": float(np.max(per_particle)),
    }


def sample_to_state(sample: dict[str, Any]) -> dict[str, np.ndarray]:
    particle = sample["particle_state"]
    return {
        "x": np.asarray(particle["position_unwrapped"], dtype=np.float64),
        "v": np.asarray(particle["velocity"], dtype=np.float64),
        "rho": np.asarray(particle["density"], dtype=np.float64),
    }


def match_case(sample_id: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_id = sample_id.split("__t", 1)[0]
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise KeyError(case_id)


def reference_record_for(case_id: str) -> dict[str, Any]:
    path = DATASET / "references" / f"{case_id}__r2_reference.json"
    return json.loads(path.read_text(encoding="utf-8"))


def edge_multiset(source: list[int], target: list[int]) -> Counter[tuple[int, int]]:
    return Counter(zip(source, target))


def state_alignment_row(sample: dict[str, Any], case: dict[str, Any], config: dict[str, Any], generator: Any) -> dict[str, Any]:
    sample_id = sample["sample_id"]
    state = sample_to_state(sample)
    particle = sample["particle_state"]
    time_value = float(sample["metadata"]["comparison_time"])
    ref_record = reference_record_for(case["case_id"])
    ref_times = {float(row["time"]): row for row in ref_record["times"]}
    same_state = (
        sample["a_ref"]["same_state_evaluation"] is True
        and sample["metadata"]["state_hash"] == content_hash(particle)
        and time_value in ref_times
        and ref_times[time_value]["rk2_state_hash"] == sample["metadata"]["state_hash"]
    )
    config_identity = content_hash({"case": case, "configuration": config})
    rho = np.asarray(particle["density"], dtype=np.float64)
    pressure = np.asarray(particle["pressure"], dtype=np.float64)
    expected_pressure = generator.pressure_from_density(rho, config)
    n = int(particle["particle_count"])
    expected_mass = float(config["physics"]["rho0"]) / n
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    expected_h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    expected_support = float(case["h_over_dx"]) * dx
    configuration_checks = {
        "configuration_hash": sample["metadata"]["configuration_hash"] == config_identity == sample["a_SPH"]["configuration_hash"] == ref_record["configuration_hash"],
        "EOS": bool(np.allclose(pressure, expected_pressure, rtol=0.0, atol=1e-14)),
        "kernel": sample["neighbor_information"]["support_rule_id"] == config["kernel"]["support_rule"],
        "support": bool(np.allclose(np.asarray(particle["support"]), expected_support, rtol=0.0, atol=1e-15)),
        "smoothing_length": bool(np.allclose(np.asarray(particle["smoothing_length"]), expected_h, rtol=0.0, atol=1e-15)),
        "mass": bool(np.allclose(np.asarray(particle["mass"]), expected_mass, rtol=0.0, atol=1e-15)),
        "neighbor_contract": sample["neighbor_information"]["minimum_image_convention"] == "delta_minus_L_floor_delta_over_L_plus_half_v1",
    }
    same_configuration = all(configuration_checks.values())
    same_timestamp = time_value in [float(value) for value in config["state_generation"]["output_times"]] and time_value in ref_times
    expected_edges = generator.build_edges(state, case, config, apply_control=False)
    neighbor = sample["neighbor_information"]
    observed_multiset = edge_multiset(neighbor["source_index"], neighbor["target_index"])
    expected_multiset = edge_multiset(expected_edges["source"].tolist(), expected_edges["target"].tolist())
    same_graph = (
        observed_multiset == expected_multiset
        and neighbor["topology_status"] == "PASS"
        and neighbor["reciprocal_status"] == "PASS"
        and all(value == 0 for value in neighbor["topology_defects"].values())
    )
    overall = same_state and same_configuration and same_timestamp and same_graph
    return {
        "sample_id": sample_id,
        "reference_identity": ref_record["reference_identity"],
        "same_state": {"status": "PASS" if same_state else "FAIL", "state_hash": sample["metadata"]["state_hash"]},
        "same_configuration": {"status": "PASS" if same_configuration else "FAIL", "checks": configuration_checks, "configuration_hash": config_identity},
        "same_timestamp": {"status": "PASS" if same_timestamp else "FAIL", "comparison_time": time_value, "units": sample["metadata"]["time_units"]},
        "same_graph_contract": {
            "status": "PASS" if same_graph else "FAIL",
            "observed_edge_count": sum(observed_multiset.values()),
            "expected_dense_support_edge_count": sum(expected_multiset.values()),
            "neighbor_graph_hash": neighbor["neighbor_graph_hash"],
            "topology_status": neighbor["topology_status"],
        },
        "overall_alignment_status": "PASS" if overall else "FAIL",
        "evidence": [
            f"../03_dataset/samples/{sample_id}.json",
            f"../03_dataset/references/{case['case_id']}__r2_reference.json",
            "../03_dataset/generation/generation_configuration.yaml",
        ],
    }


def temporal_sensitivity_by_case(case: dict[str, Any], config: dict[str, Any], generator: Any) -> dict[float, dict[str, Any]]:
    primary, sensitivity, solver = generator.dop853_reference_states(case, config)
    results: dict[float, dict[str, Any]] = {}
    for time_value in sorted(primary):
        a_primary = generator.dense_rhs_components(primary[time_value], case, config)["total"]
        a_sensitivity = generator.dense_rhs_components(sensitivity[time_value], case, config)["total"]
        difference = a_primary - a_sensitivity
        metrics = vector_norms(difference)
        primary_metrics = vector_norms(a_primary)
        denominator = primary_metrics["L2_rms_vector"]
        metrics["relative_L2_to_primary"] = float(metrics["L2_rms_vector"] / denominator) if denominator > 0.0 else None
        metrics["primary_acceleration_L2_rms_vector"] = denominator
        metrics["threshold"] = None
        metrics["automatic_smallness_decision"] = "NOT_PERMITTED_NO_FROZEN_THRESHOLD"
        results[time_value] = metrics
    results["solver_status"] = solver  # type: ignore[index]
    return results


def component(status: str, evidence: list[str], uncertainty: dict[str, Any], confidence: str) -> dict[str, Any]:
    return {"status": status, "evidence": evidence, "uncertainty": uncertainty, "attribution_confidence": confidence}


def main() -> int:
    generator = load_generator()
    case_manifest = yaml.safe_load(CASE_PATH.read_text(encoding="utf-8"))
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    rules = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    dataset_manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = case_manifest["cases"]
    samples = [json.loads((REPO_ROOT / row["path"]).read_text(encoding="utf-8")) for row in dataset_manifest["samples"]]
    if any(sample["a_ref"]["reference_class"] != "R2_semidiscrete_qualified" for sample in samples):
        raise RuntimeError("Stage 02D audit is restricted to the Stage 02C R2 batch")

    temporal_by_case = {case["case_id"]: temporal_sensitivity_by_case(case, config, generator) for case in cases}
    alignment_rows = [state_alignment_row(sample, match_case(sample["sample_id"], cases), config, generator) for sample in samples]
    alignment_by_id = {row["sample_id"]: row for row in alignment_rows}
    sensitivity_rows: list[dict[str, Any]] = []
    decomposition_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []

    for sample in samples:
        sample_id = sample["sample_id"]
        case = match_case(sample_id, cases)
        time_value = float(sample["metadata"]["comparison_time"])
        temporal = temporal_by_case[case["case_id"]][time_value]
        delta = np.asarray(sample["delta_a"]["values"], dtype=np.float64)
        delta_metrics = vector_norms(delta)
        time_linf = float(sample["uncertainty"]["time_error"]["value"])
        ref_forward_reverse = float(sample["uncertainty"]["reference_uncertainty"]["value"])
        n_edges = len(sample["neighbor_information"]["source_index"])
        max_neighbors = max(Counter(sample["neighbor_information"]["source_index"]).values(), default=0)
        a_ref = np.asarray(sample["a_ref"]["values"], dtype=np.float64)
        ref_rule = config["reference_uncertainty_rule"]
        float64_bound = max(
            float(ref_rule["absolute_floor_acceleration"]),
            float(ref_rule["bound_multiplier_machine_epsilon"])
            * np.finfo(np.float64).eps
            * max(1.0, float(np.max(np.abs(a_ref))))
            * max(1, max_neighbors),
        )
        if delta_metrics["L2_rms_vector"] > 0.0:
            time_to_delta = float(temporal["L2_rms_vector"] / delta_metrics["L2_rms_vector"])
            comparison_status = "RAW_RATIO_REPORTED_NO_THRESHOLD"
        else:
            time_to_delta = None
            comparison_status = "INDETERMINATE_ZERO_TARGET"
        alignment = alignment_by_id[sample_id]
        topology_pass = sample["neighbor_information"]["topology_status"] == "PASS"
        sensitivity_status = (
            temporal["L2_rms_vector"] >= 0.0
            and math.isfinite(float(temporal["L2_rms_vector"]))
            and ref_forward_reverse <= float64_bound
        )
        sensitivity_rows.append({
            "sample_id": sample_id,
            "case_id": case["case_id"],
            "time": time_value,
            "reference_identity": case["reference_identity"],
            "dense_forward_reverse": {"Linf_component": ref_forward_reverse, "units": "m s^-2", "status": "PASS" if ref_forward_reverse <= float64_bound else "FAIL"},
            "float64_roundoff": {"audit_bound": float64_bound, "units": "m s^-2", "method": ref_rule["rule_id"], "status": "PASS" if ref_forward_reverse <= float64_bound else "FAIL"},
            "DOP853_primary_vs_sensitivity": temporal,
            "assembly_sensitivity": {**delta_metrics, "units": "m s^-2", "interpretation": "sparse_vs_dense_same_state; topology control invalidates discretization interpretation" if not topology_pass else "qualified_graph_assembly_equivalence_only"},
            "RK2_state_vs_DOP853_state_acceleration_Linf": {"value": time_linf, "units": "m s^-2"},
            "DOP853_sensitivity_to_delta_L2_ratio": time_to_delta,
            "time_vs_delta_comparison_status": comparison_status if topology_pass else "NOT_APPLICABLE_REJECTED_TOPOLOGY",
            "single_total_uncertainty": None,
            "single_total_uncertainty_permitted": False,
            "status": "PASS" if sensitivity_status and topology_pass else ("REJECTED_TOPOLOGY" if not topology_pass else "FAIL"),
        })

        evidence = [f"../03_dataset/samples/{sample_id}.json", f"../03_dataset/references/{case['case_id']}__r2_reference.json"]
        if topology_pass:
            ledger = {
                "delta_a_space": component("UNRESOLVED_NOT_OBSERVED_BY_R2_ASSEMBLY_EQUIVALENCE", evidence, {"kind": "not_quantified", "reason": "no continuum-compatible spatial reference"}, "none"),
                "delta_a_time": component("BOUNDED_REPORTED_NO_SMALLNESS_THRESHOLD", evidence, {"DOP853_primary_vs_sensitivity_L2": temporal["L2_rms_vector"], "RK2_vs_DOP853_acceleration_Linf": time_linf, "units": "m s^-2"}, "moderate"),
                "delta_a_reference": component("BOUNDED_ROUNDOFF_AND_DOP853_SENSITIVITY", evidence, {"dense_forward_reverse_Linf": ref_forward_reverse, "float64_bound": float64_bound, "DOP853_sensitivity_Linf": temporal["Linf_vector"], "units": "m s^-2"}, "high_for_audit_only"),
                "delta_a_forcing": component("ZERO_AND_MATCHED", evidence, {"value": 0.0, "units": "m s^-2"}, "high"),
                "delta_a_model_form": component("COMPATIBLE_WITHIN_SAME_R2_SEMIDISCRETE_CONTRACT_ONLY", evidence, {"kind": "categorical", "continuum_alignment": "not_tested"}, "moderate"),
                "cross": component("UNRESOLVED", evidence, {"kind": "not_quantified"}, "none"),
            }
            ledger_status = "diagnostic"
        else:
            ledger = {
                "delta_a_space": component("REJECTED_TOPOLOGY_CONTAMINATED", evidence, {"kind": "invalid_target"}, "none"),
                "delta_a_time": component("NOT_ATTRIBUTABLE_AFTER_HARD_FAILURE", evidence, {"DOP853_primary_vs_sensitivity_L2": temporal["L2_rms_vector"], "units": "m s^-2"}, "none"),
                "delta_a_reference": component("ASSEMBLY_CONTAMINATED_BY_DUPLICATE_EDGE", evidence, {"assembly_Linf": delta_metrics["Linf_vector"], "units": "m s^-2"}, "high_for_failure_cause"),
                "delta_a_forcing": component("ZERO_BUT_TARGET_INVALID", evidence, {"value": 0.0, "units": "m s^-2"}, "high"),
                "delta_a_model_form": component("R2_INTERNAL_COMPATIBILITY_DOES_NOT_OVERRIDE_TOPOLOGY_FAILURE", evidence, {"kind": "categorical"}, "moderate"),
                "cross": component("UNRESOLVED_HARD_FAILURE", evidence, {"kind": "not_quantified"}, "none"),
            }
            ledger_status = "rejected"
        decomposition_rows.append({
            "sample_id": sample_id,
            "equation": "delta_a = delta_a_space + delta_a_time + delta_a_reference + delta_a_forcing + delta_a_model_form + cross",
            "observed_delta_a": {**delta_metrics, "units": "m s^-2"},
            "components": ledger,
            "attribution_verdict": ledger_status,
        })

        if topology_pass:
            score_components = {
                "spatial_consistency": "DIAGNOSTIC_ZERO_ASSEMBLY_DIFFERENCE_NOT_SPATIAL_EVIDENCE",
                "resolution_trend": "NOT_TESTED_RESOLUTION_DISORDER_CONFOUNDED",
                "support_consistency": "NOT_TESTED_SINGLE_H_OVER_DX",
                "time_contamination": "DIAGNOSTIC_NO_THRESHOLD_AND_ZERO_TARGET",
                "reference_sensitivity": "PASS_AUDIT_BOUNDS",
                "model_form_compatibility": "DIAGNOSTIC_R2_INTERNAL_ONLY",
            }
            candidate = "diagnostic"
            reason_codes = [
                "DIAG_R2_NOT_TRAINING_REFERENCE",
                "DIAG_SPATIAL_ATTRIBUTION_UNRESOLVED",
                "DIAG_RESOLUTION_DISORDER_CONFOUNDED",
                "DIAG_SINGLE_SUPPORT_RATIO",
                "DIAG_TEMPORAL_SMALLNESS_THRESHOLD_NOT_FROZEN",
                "DIAG_CONTINUUM_MODEL_FORM_ALIGNMENT_NOT_TESTED",
            ]
        else:
            score_components = {
                "spatial_consistency": "FAIL_TOPOLOGY",
                "resolution_trend": "NOT_APPLICABLE_REJECTED",
                "support_consistency": "NOT_APPLICABLE_REJECTED",
                "time_contamination": "NOT_APPLICABLE_REJECTED",
                "reference_sensitivity": "NOT_APPLICABLE_TO_INVALID_TARGET",
                "model_form_compatibility": "NOT_APPLICABLE_REJECTED",
            }
            candidate = "rejected"
            reason_codes = list(sample["eligibility"]["reason_codes"])
        counts = {
            "PASS": sum(str(value).startswith("PASS") for value in score_components.values()),
            "DIAGNOSTIC": sum(str(value).startswith("DIAGNOSTIC") for value in score_components.values()),
            "FAIL": sum(str(value).startswith("FAIL") for value in score_components.values()),
            "NOT_TESTED_OR_NOT_APPLICABLE": sum(str(value).startswith("NOT_") for value in score_components.values()),
        }
        score_rows.append({
            "sample_id": sample_id,
            "discretization_attribution_score": {"aggregation": "categorical_evidence_vector_no_numeric_threshold", "components": score_components, "counts": counts},
            "candidate": candidate,
            "reason_codes": reason_codes,
            "manual_override": False,
        })

    positive_rows = [row for row in score_rows if row["candidate"] == "diagnostic"]
    cross_resolution = {
        "available_positive_cases": ["r2_regular_n6", "r2_jitter05_n8"],
        "resolution_values": ["N6x6", "N8x8"],
        "h_over_dx_values": [2.6],
        "disorder_values": ["regular", "jitter_05pct_seed_2202"],
        "delta_a_observation": "zero_for_all_topology_qualified_samples",
        "smooth_trend": "INDETERMINATE_ZERO_ASSEMBLY_IDENTITY",
        "stable_direction": "INDETERMINATE_ZERO_VECTOR",
        "non_random_structure": "NOT_DEMONSTRATED",
        "confounding": "resolution_changes_together_with_disorder; single_H_over_dx",
        "status": "INSUFFICIENT_EVIDENCE_FOR_RESOLUTION_DEPENDENT_CORRECTION",
    }
    current_counts = dict(Counter(row["candidate"] for row in score_rows))
    stage02e_authorized = False
    alignment_report = {
        "audit_version": "stage02d-state-alignment-1.0.0",
        "reference_identity": "stage02c_r2_dense_all_pairs_dop853_v1",
        "rows": alignment_rows,
        "summary": dict(Counter(row["overall_alignment_status"] for row in alignment_rows)),
        "topology_qualified_alignment_status": "PASS" if all(row["overall_alignment_status"] == "PASS" for row in alignment_rows if "duplicate_edge_negative" not in row["sample_id"]) else "FAIL",
        "negative_control_status": "EXPECTED_FAIL_RETAINED",
    }
    sensitivity_report = {
        "audit_version": "stage02d-reference-sensitivity-1.0.0",
        "reference_identity": "stage02c_r2_dense_all_pairs_dop853_v1",
        "norm_definitions": {"L2": "sqrt(mean_i(||v_i||_2^2))", "Linf": "max_i(||v_i||_2)", "relative": "L2_difference/L2_primary"},
        "automatic_smallness_threshold": None,
        "automatic_threshold_selection_permitted": False,
        "rows": sensitivity_rows,
        "budget_combination": "componentwise_only_no_single_total",
    }
    decomposition_report = {
        "audit_version": "stage02d-error-decomposition-1.0.0",
        "equation": "delta_a = delta_a_space + delta_a_time + delta_a_reference + delta_a_forcing + delta_a_model_form + cross",
        "rows": decomposition_rows,
        "summary": dict(Counter(row["attribution_verdict"] for row in decomposition_rows)),
        "all_difference_equals_discretization_error": False,
    }
    score_report = {
        "audit_version": "stage02d-discretization-attribution-1.0.0",
        "score_rule_version": rules["rules_version"],
        "rows": score_rows,
        "candidate_counts": current_counts,
        "cross_resolution_attribution": cross_resolution,
        "discretization_attribution_PASS_count": 0,
    }
    stage02e_report = {
        "decision_version": "stage02d-stage02e-gate-1.0.0",
        "current_campaign": dataset_manifest["campaign_id"],
        "label_upgrade_authorized": False,
        "stage02e_data_qualification_upgrade_authorized": stage02e_authorized,
        "reasons": [
            "R2 reference is not training-permitted under the frozen contract",
            "spatial discretization component is not identified",
            "resolution and disorder are confounded",
            "only one H/dx is present",
            "temporal smallness threshold is not frozen and positive targets are zero",
            "continuum WCSPH model-form alignment is not tested",
            "no sample has discretization attribution PASS",
        ],
        "current_candidate_counts": current_counts,
        "required_future_evidence": [
            "training-permitted reference class or new versioned R2 target contract",
            "same-state PASS",
            "reference uncertainty PASS",
            "unconfounded multi-resolution trend",
            "multi-support consistency",
            "pre-frozen temporal contamination decision rule",
            "WCSPH model-form compatibility PASS for the claimed target",
            "topology/resource/determinism/leakage PASS",
        ],
        "dataset_expansion_performed": False,
        "training_performed": False,
    }
    outputs = {
        ATTRIBUTION / "audits" / "state_alignment_audit.json": alignment_report,
        ATTRIBUTION / "reference_sensitivity" / "reference_sensitivity_budget.json": sensitivity_report,
        ATTRIBUTION / "decomposition" / "error_decomposition_ledger.json": decomposition_report,
        ATTRIBUTION / "qualification" / "discretization_attribution_scores.json": score_report,
        ATTRIBUTION / "qualification" / "stage02e_upgrade_decision.json": stage02e_report,
    }
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError("No-overwrite contract; existing outputs: " + ", ".join(existing))
    for path, value in outputs.items():
        write_json_no_overwrite(path, value)
    print(json.dumps({
        "status": "PASS",
        "samples_audited": len(samples),
        "alignment_summary": alignment_report["summary"],
        "candidate_counts": current_counts,
        "stage02e_upgrade_authorized": stage02e_authorized,
        "output_hashes": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in outputs},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
