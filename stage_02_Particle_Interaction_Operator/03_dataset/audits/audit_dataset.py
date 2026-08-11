#!/usr/bin/env python3
"""Audit Stage 02C samples against the frozen Stage 02B contracts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

sys.dont_write_bytecode = True


REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator" / "03_dataset"
SCHEMA_PATH = DATASET_ROOT / "schema" / "pio_dataset_schema.json"
CONFIG_PATH = DATASET_ROOT / "generation" / "generation_configuration.yaml"
CASE_PATH = DATASET_ROOT / "cases" / "case_manifest.yaml"
GENERATOR_PATH = DATASET_ROOT / "generation" / "generate_audit_dataset.py"
SAMPLE_DIR = DATASET_ROOT / "samples"
REFERENCE_DIR = DATASET_ROOT / "references"
MANIFEST_DIR = DATASET_ROOT / "manifests"
AUDIT_DIR = DATASET_ROOT / "audits"


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
    spec = importlib.util.spec_from_file_location("stage02c_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load generator module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool) and math.isfinite(float(instance))
    if expected == "boolean":
        return isinstance(instance, bool)
    return True


def resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"Unsupported external ref: {ref}")
    node: Any = root
    for token in ref[2:].split("/"):
        node = node[token.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise ValueError(f"Ref does not resolve to schema object: {ref}")
    return node


def validate(instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        return validate(instance, resolve_ref(root, schema["$ref"]), root, path)
    if "oneOf" in schema:
        branches = [validate(instance, branch, root, path) for branch in schema["oneOf"]]
        if sum(not branch for branch in branches) != 1:
            errors.append(f"{path}: oneOf matched {sum(not branch for branch in branches)} branches")
        return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value not in enum")
    expected_type = schema.get("type")
    if expected_type and not type_matches(instance, expected_type):
        errors.append(f"{path}: expected type {expected_type}")
        return errors
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required key {key}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property {key}")
        if len(instance) < int(schema.get("minProperties", 0)):
            errors.append(f"{path}: fewer than minProperties")
    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            errors.append(f"{path}: more than maxItems")
        if schema.get("uniqueItems"):
            encoded = [canonical_bytes(value) for value in instance]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: duplicate array items")
        if "items" in schema:
            for index, value in enumerate(instance):
                errors.extend(validate(value, schema["items"], root, f"{path}[{index}]"))
    if isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            errors.append(f"{path}: shorter than minLength")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: pattern mismatch")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum")
    return errors


def semantic_audit(sample: dict[str, Any], config: dict[str, Any], generator: Any) -> list[str]:
    errors: list[str] = []
    particle = sample["particle_state"]
    n = particle["particle_count"]
    dim = particle["dimension"]
    scalar_fields = ("particle_id_local", "density", "pressure", "mass", "support", "smoothing_length")
    vector_fields = ("position_periodic", "position_unwrapped", "velocity")
    for field in scalar_fields:
        if field in particle and len(particle[field]) != n:
            errors.append(f"particle_state.{field}: length != particle_count")
    for field in vector_fields:
        if field in particle:
            if len(particle[field]) != n:
                errors.append(f"particle_state.{field}: length != particle_count")
            if any(len(vector) != dim for vector in particle[field]):
                errors.append(f"particle_state.{field}: vector length != dimension")
    neighbor = sample["neighbor_information"]
    edge_fields = ("source_index", "target_index", "reciprocal_pair_id", "minimum_image_displacement", "relative_velocity", "distance", "normalized_distance", "kernel_value", "kernel_radial_gradient")
    edge_count = len(neighbor["source_index"])
    for field in edge_fields:
        if field in neighbor and len(neighbor[field]) != edge_count:
            errors.append(f"neighbor_information.{field}: inconsistent edge length")
    if any(index >= n for index in neighbor["source_index"] + neighbor["target_index"]):
        errors.append("neighbor_information: particle index out of range")
    for field in ("a_SPH", "a_ref", "delta_a"):
        if len(sample[field]["values"]) != n:
            errors.append(f"{field}.values: length != particle_count")
        if any(len(vector) != dim for vector in sample[field]["values"]):
            errors.append(f"{field}.values: vector length != dimension")
    a_sph = np.asarray(sample["a_SPH"]["values"], dtype=np.float64)
    a_ref = np.asarray(sample["a_ref"]["values"], dtype=np.float64)
    delta = np.asarray(sample["delta_a"]["values"], dtype=np.float64)
    if not np.allclose(delta, a_ref - a_sph, atol=float(config["target"]["sign_check_atol"]), rtol=float(config["target"]["sign_check_rtol"])):
        errors.append("delta_a: a_ref_minus_a_sph semantic check failed")
    if sample["metadata"]["state_hash"] != content_hash(particle):
        errors.append("state_hash: content mismatch")
    neighbor_without_hash = dict(neighbor)
    recorded_graph_hash = neighbor_without_hash.pop("neighbor_graph_hash")
    if recorded_graph_hash != content_hash(neighbor_without_hash):
        errors.append("neighbor_graph_hash: content mismatch")
    if sample["a_SPH"]["configuration_hash"] != sample["metadata"]["configuration_hash"]:
        errors.append("configuration_hash: baseline/metadata mismatch")
    expected_verdict, expected_reasons = generator.derive_eligibility(sample)
    if sample["eligibility"]["verdict"] != expected_verdict:
        errors.append("eligibility.verdict: automatic recomputation mismatch")
    if sorted(sample["eligibility"]["reason_codes"]) != sorted(expected_reasons):
        errors.append("eligibility.reason_codes: automatic recomputation mismatch")
    if sample["a_ref"]["reference_class"] != "R2_semidiscrete_qualified":
        errors.append("reference policy: non-R2 record present")
    if "split_assignment" in sample["metadata"]:
        errors.append("split assignment is prohibited in Stage 02C")
    if sample["delta_a"]["sign_convention"] != "a_ref_minus_a_sph":
        errors.append("delta sign convention mismatch")
    return errors


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    case_manifest = yaml.safe_load(CASE_PATH.read_text(encoding="utf-8"))
    generator = load_generator()
    dataset_manifest_path = MANIFEST_DIR / "dataset_manifest.json"
    run_manifest_path = MANIFEST_DIR / "generation_run_manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    sample_paths = sorted(SAMPLE_DIR.glob("*.json"))
    reference_paths = sorted(REFERENCE_DIR.glob("*.json"))
    if not sample_paths:
        raise RuntimeError("No samples found")
    schema_rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    eligibility_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    manifest_by_path = {row["path"]: row for row in dataset_manifest["samples"]}
    expected_roles = {case["case_id"]: case["audit_role"] for case in case_manifest["cases"]}
    for path in sample_paths:
        sample = json.loads(path.read_text(encoding="utf-8"))
        structural_errors = validate(sample, schema, schema)
        semantic_errors = semantic_audit(sample, config, generator)
        sample_id = sample["sample_id"]
        case_id = sample_id.split("__t", 1)[0]
        role = expected_roles[case_id]
        verdict = sample["eligibility"]["verdict"]
        expected_for_role = "rejected" if role == "predefined_rejection_control" else "diagnostic"
        verdict_role_pass = verdict == expected_for_role
        relative = str(path.relative_to(REPO_ROOT))
        row = manifest_by_path.get(relative)
        file_hash_pass = row is not None and row["sha256"] == file_hash(path)
        provenance_complete = all(
            sample["provenance"].get(key)
            for key in (
                "baseline_source_id", "reference_source_id", "configuration_source_id",
                "software_environment_id", "resource_policy_id", "determinism_policy_id", "evidence_uris"
            )
        )
        schema_rows.append({"sample_id": sample_id, "errors": structural_errors, "status": "PASS" if not structural_errors else "FAIL"})
        semantic_rows.append({"sample_id": sample_id, "errors": semantic_errors, "status": "PASS" if not semantic_errors else "FAIL"})
        eligibility_rows.append({
            "sample_id": sample_id,
            "audit_role": role,
            "verdict": verdict,
            "expected_verdict": expected_for_role,
            "reason_codes": sample["eligibility"]["reason_codes"],
            "automatic_recomputation": "PASS" if not any("eligibility" in error for error in semantic_errors) else "FAIL",
            "role_expectation_status": "PASS" if verdict_role_pass else "FAIL",
        })
        provenance_rows.append({
            "sample_id": sample_id,
            "state_hash_status": "PASS" if not any("state_hash" in error for error in semantic_errors) else "FAIL",
            "graph_hash_status": "PASS" if not any("neighbor_graph_hash" in error for error in semantic_errors) else "FAIL",
            "file_hash_status": "PASS" if file_hash_pass else "FAIL",
            "provenance_fields_status": "PASS" if provenance_complete else "FAIL",
        })
    reference_rows = []
    reference_manifest_by_path = {row["path"]: row for row in dataset_manifest["references"]}
    for path in reference_paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        relative = str(path.relative_to(REPO_ROOT))
        manifest_row = reference_manifest_by_path.get(relative)
        status = (
            record.get("reference_class") == "R2_semidiscrete_qualified"
            and record.get("status") == "PASS"
            and record.get("solver_status", {}).get("primary", {}).get("success") is True
            and record.get("solver_status", {}).get("sensitivity", {}).get("success") is True
            and manifest_row is not None
            and manifest_row["sha256"] == file_hash(path)
        )
        reference_rows.append({"case_id": record.get("case_id"), "path": relative, "status": "PASS" if status else "FAIL"})
    all_schema = all(row["status"] == "PASS" for row in schema_rows)
    all_semantic = all(row["status"] == "PASS" for row in semantic_rows)
    all_eligibility = all(row["automatic_recomputation"] == "PASS" and row["role_expectation_status"] == "PASS" for row in eligibility_rows)
    all_provenance = all(all(value == "PASS" for key, value in row.items() if key.endswith("_status")) for row in provenance_rows)
    all_references = all(row["status"] == "PASS" for row in reference_rows) and len(reference_rows) == len(case_manifest["cases"])
    pipeline_pass = all(step["status"] == "PASS" and str(step["output_hash"]).startswith("sha256:") for step in run_manifest["pipeline_steps"])
    determinism_pass = run_manifest["determinism"]["status"] == "PASS" and run_manifest["determinism"]["canonical_in_memory_bytes_equal"] is True
    prohibited_pass = (
        dataset_manifest["split_assignment_created"] is False
        and dataset_manifest["normalization_statistics_created"] is False
        and dataset_manifest["training_artifacts_created"] is False
        and all(value is False for value in run_manifest["prohibited_outputs"].values())
    )
    schema_report = {
        "audit_version": "stage02c-schema-audit-1.0.0",
        "validator": "frozen_schema_recursive_subset_plus_semantic_contract",
        "sample_count": len(sample_paths),
        "structural_status": "PASS" if all_schema else "FAIL",
        "semantic_status": "PASS" if all_semantic else "FAIL",
        "structural_rows": schema_rows,
        "semantic_rows": semantic_rows,
    }
    eligibility_report = {
        "audit_version": "stage02c-eligibility-audit-1.0.0",
        "manual_override_permitted": False,
        "status": "PASS" if all_eligibility else "FAIL",
        "verdict_counts": dict(sorted({verdict: sum(row["verdict"] == verdict for row in eligibility_rows) for verdict in ("eligible_for_future_training", "diagnostic", "rejected")}.items())),
        "rows": eligibility_rows,
    }
    provenance_report = {
        "audit_version": "stage02c-provenance-audit-1.0.0",
        "status": "PASS" if all_provenance and all_references and pipeline_pass and determinism_pass else "FAIL",
        "sample_rows": provenance_rows,
        "reference_rows": reference_rows,
        "pipeline_hash_status": "PASS" if pipeline_pass else "FAIL",
        "determinism_status": "PASS" if determinism_pass else "FAIL",
    }
    sample_report = {
        "audit_version": "stage02c-sample-audit-1.0.0",
        "campaign_id": dataset_manifest["campaign_id"],
        "sample_count": len(sample_paths),
        "reference_record_count": len(reference_paths),
        "R2_only_status": "PASS" if all_references else "FAIL",
        "schema_status": "PASS" if all_schema and all_semantic else "FAIL",
        "eligibility_status": "PASS" if all_eligibility else "FAIL",
        "provenance_status": provenance_report["status"],
        "pipeline_status": "PASS" if pipeline_pass else "FAIL",
        "determinism_status": "PASS" if determinism_pass else "FAIL",
        "prohibited_output_status": "PASS" if prohibited_pass else "FAIL",
        "overall_status": "PASS" if all((all_schema, all_semantic, all_eligibility, all_provenance, all_references, pipeline_pass, determinism_pass, prohibited_pass)) else "FAIL",
        "historical_boundaries": run_manifest["historical_boundaries"],
    }
    outputs = {
        AUDIT_DIR / "schema_validation.json": schema_report,
        AUDIT_DIR / "eligibility_audit.json": eligibility_report,
        AUDIT_DIR / "provenance_audit.json": provenance_report,
        AUDIT_DIR / "sample_audit.json": sample_report,
    }
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError("No-overwrite contract; existing audits: " + ", ".join(existing))
    for path, value in outputs.items():
        write_json_no_overwrite(path, value)
    print(json.dumps({"status": sample_report["overall_status"], "sample_count": len(sample_paths), "verdict_counts": eligibility_report["verdict_counts"]}, sort_keys=True))
    return 0 if sample_report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
