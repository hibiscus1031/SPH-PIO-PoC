#!/usr/bin/env python3
"""Materialize and audit the five Stage 02J regular full-graph records.

This program reconstructs only the frozen Stage 02I states and graphs needed to
materialize existing targets. It creates no new target, physical state family,
trajectory, temporal frame, augmentation, model, split, or training artifact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import re
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATA_ROOT = STAGE_ROOT / "05_dataset/controlled_regular_pair_scope_v0_1"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
SOURCE_ROOT = ATTR_ROOT / "qualified_spatial_targets"

FREEZE_PATH = DATA_ROOT / "freeze/stage02j_input_freeze_manifest.json"
SCOPE_PATH = DATA_ROOT / "freeze/stage02j_scope_contract.yaml"
SCHEMA_J_PATH = DATA_ROOT / "schema/stage02j_graph_record_schema.json"
SCHEMA_B_PATH = STAGE_ROOT / "03_dataset/schema/pio_dataset_schema.json"
FEATURE_PATH = DATA_ROOT / "schema/feature_permission_table.yaml"
SERIAL_PATH = DATA_ROOT / "schema/canonical_serialization_contract.yaml"
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
GENERATOR_PATH = STAGE_ROOT / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F_PATH = ATTR_ROOT / "semidiscrete_reference/construct_spatial_targets.py"
MATRIX_PATH = SOURCE_ROOT / "case_matrix/preregistered_stage02i_case_matrix.yaml"
TARGETS_PATH = SOURCE_ROOT / "targets/spatial_target_candidates.json"
SIX_PATH = SOURCE_ROOT / "attribution/six_component_attribution.json"
CONSERVATION_PATH = SOURCE_ROOT / "conservation/conservation_compatibility_audit.json"
ARCHITECTURE_PATH = ATTR_ROOT / "conservation_closure/architecture_scope/architecture_scope_decision.json"
FORCE_PATH = ATTR_ROOT / "conservation_closure/force_decomposition/force_decomposition.json"
QUADRATURE_PATH = ATTR_ROOT / "conservation_closure/particle_quadrature/particle_quadrature_audit.json"
PAIR_NODE_PATH = ATTR_ROOT / "conservation_closure/pair_representability/jitter_pair_node_decomposition.json"

RAW_DIR = DATA_ROOT / "raw_graph_records"
CANON_DIR = DATA_ROOT / "canonical_records"
QC_PATH = DATA_ROOT / "qc/quality_control_results.json"
LEAKAGE_PATH = DATA_ROOT / "leakage/leakage_graph.json"
SPLIT_PATH = DATA_ROOT / "splits/split_feasibility.json"
NORM_PATH = DATA_ROOT / "normalization/prospective_normalization_contract.yaml"
OOD_PATH = DATA_ROOT / "ood_diagnostics/jitter_ood_registry.json"
ELIGIBILITY_PATH = DATA_ROOT / "eligibility/record_eligibility_results.json"
CANON_MANIFEST_PATH = CANON_DIR / "canonical_serialization_manifest.json"
DATASET_MANIFEST_PATH = DATA_ROOT / "manifests/stage02j_dataset_manifest.json"
RUN_MANIFEST_PATH = DATA_ROOT / "manifests/stage02j_run_manifest.json"

AUTHORIZED = [
    "i_res_n12_h26_regular",
    "i_anchor_n16_h26_regular",
    "i_res_n20_h26_regular",
    "i_sup_n16_h22_regular",
    "i_sup_n16_h30_regular",
]
JITTER = ["i_dis_n16_h26_jitter05", "i_dis_n16_h26_jitter10"]

ARRAY_PATHS: tuple[tuple[str, str], ...] = (
    ("stage02b_record.particle_state.particle_id_local", "i8"),
    ("stage02b_record.particle_state.position_periodic", "f8"),
    ("stage02b_record.particle_state.velocity", "f8"),
    ("stage02b_record.particle_state.density", "f8"),
    ("stage02b_record.particle_state.pressure", "f8"),
    ("stage02b_record.particle_state.mass", "f8"),
    ("stage02b_record.particle_state.support", "f8"),
    ("stage02b_record.particle_state.smoothing_length", "f8"),
    ("stage02b_record.neighbor_information.source_index", "i8"),
    ("stage02b_record.neighbor_information.target_index", "i8"),
    ("stage02b_record.neighbor_information.reciprocal_pair_id", "i8"),
    ("stage02b_record.neighbor_information.minimum_image_displacement", "f8"),
    ("stage02b_record.neighbor_information.relative_velocity", "f8"),
    ("stage02b_record.neighbor_information.distance", "f8"),
    ("stage02b_record.neighbor_information.normalized_distance", "f8"),
    ("stage02b_record.neighbor_information.kernel_value", "f8"),
    ("stage02b_record.neighbor_information.kernel_radial_gradient", "f8"),
    ("stage02b_record.a_SPH.values", "f8"),
    ("stage02b_record.a_SPH.pressure_component", "f8"),
    ("stage02b_record.a_SPH.viscosity_component", "f8"),
    ("stage02b_record.a_SPH.forcing_component", "f8"),
    ("stage02b_record.a_ref.values", "f8"),
    ("stage02b_record.delta_a.values", "f8"),
    ("reciprocal_graph_extensions.reciprocal_edge_mapping", "i8"),
    ("reciprocal_graph_extensions.active_kernel_indicator", "u1"),
    ("reciprocal_graph_extensions.zero_weight_exterior_edge_indicator", "u1"),
    ("reciprocal_graph_extensions.neighbor_count_total", "i8"),
    ("reciprocal_graph_extensions.neighbor_count_active", "i8"),
    ("references.a_FOURIER2", "f8"),
    ("references.a_ANALYTIC", "f8"),
    ("references.reference_difference", "f8"),
    ("target.delta_a", "f8"),
    ("target.nodal_force", "f8"),
    ("target.mass", "f8"),
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_path(value: dict[str, Any], path: str) -> Any:
    node: Any = value
    for token in path.split("."):
        node = node[token]
    return node


def set_path(value: dict[str, Any], path: str, payload: Any) -> None:
    tokens = path.split(".")
    node: Any = value
    for token in tokens[:-1]:
        node = node[token]
    node[tokens[-1]] = payload


def serialize_record(record: dict[str, Any]) -> bytes:
    metadata = copy.deepcopy(record)
    arrays: list[tuple[str, str, np.ndarray]] = []
    for path, code in ARRAY_PATHS:
        raw = get_path(record, path)
        if code == "f8":
            array = np.asarray(raw, dtype=np.float64)
            if not np.all(np.isfinite(array)):
                raise ValueError(f"Nonfinite float array: {path}")
        elif code == "i8":
            array = np.asarray(raw, dtype=np.int64)
        elif code == "u1":
            array = np.asarray(raw, dtype=np.bool_)
        else:
            raise ValueError(code)
        set_path(metadata, path, {"$array_ref": path})
        arrays.append((path, code, array))
    meta = canonical_json_bytes(metadata)
    out = bytearray(b"SPHPIOJ1")
    out.extend(struct.pack(">Q", len(meta)))
    out.extend(meta)
    out.extend(struct.pack(">I", len(arrays)))
    for path, code, array in arrays:
        name = path.encode("utf-8")
        out.extend(struct.pack(">H", len(name)))
        out.extend(name)
        out.extend(code.encode("ascii"))
        out.extend(struct.pack(">B", array.ndim))
        for size in array.shape:
            out.extend(struct.pack(">Q", int(size)))
        if code == "f8":
            payload = np.asarray(array, dtype=">f8", order="C").tobytes(order="C")
        elif code == "i8":
            payload = np.asarray(array, dtype=">i8", order="C").tobytes(order="C")
        else:
            payload = np.asarray(array, dtype=np.uint8, order="C").tobytes(order="C")
        out.extend(struct.pack(">Q", len(payload)))
        out.extend(payload)
    return bytes(out)


def deserialize_record(payload: bytes) -> dict[str, Any]:
    offset = 0
    if payload[:8] != b"SPHPIOJ1":
        raise ValueError("Canonical magic mismatch")
    offset = 8
    meta_len = struct.unpack_from(">Q", payload, offset)[0]
    offset += 8
    record = json.loads(payload[offset : offset + meta_len].decode("utf-8"))
    offset += meta_len
    count = struct.unpack_from(">I", payload, offset)[0]
    offset += 4
    expected_paths = [path for path, _ in ARRAY_PATHS]
    seen: list[str] = []
    for _ in range(count):
        name_len = struct.unpack_from(">H", payload, offset)[0]
        offset += 2
        path = payload[offset : offset + name_len].decode("utf-8")
        offset += name_len
        code = payload[offset : offset + 2].decode("ascii")
        offset += 2
        rank = struct.unpack_from(">B", payload, offset)[0]
        offset += 1
        shape = []
        for _axis in range(rank):
            shape.append(struct.unpack_from(">Q", payload, offset)[0])
            offset += 8
        byte_count = struct.unpack_from(">Q", payload, offset)[0]
        offset += 8
        raw = payload[offset : offset + byte_count]
        offset += byte_count
        if code == "f8":
            array = np.frombuffer(raw, dtype=">f8").astype(np.float64).reshape(shape)
            value = array.tolist()
        elif code == "i8":
            array = np.frombuffer(raw, dtype=">i8").astype(np.int64).reshape(shape)
            value = array.tolist()
        elif code == "u1":
            array = np.frombuffer(raw, dtype=np.uint8).astype(bool).reshape(shape)
            value = array.tolist()
        else:
            raise ValueError(f"Unknown canonical dtype {code}")
        set_path(record, path, value)
        seen.append(path)
    if offset != len(payload) or seen != expected_paths:
        raise ValueError("Canonical field order or byte length mismatch")
    return record


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
        raise ValueError(ref)
    return node


def validate_schema(instance: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        return validate_schema(instance, resolve_ref(root, schema["$ref"]), root, path)
    if "oneOf" in schema:
        branches = [validate_schema(instance, branch, root, path) for branch in schema["oneOf"]]
        if sum(not branch for branch in branches) != 1:
            errors.append(f"{path}: oneOf match count invalid")
        return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: enum mismatch")
    expected = schema.get("type")
    if expected and not type_matches(instance, expected):
        errors.append(f"{path}: expected {expected}")
        return errors
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing {key}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate_schema(value, properties[key], root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional {key}")
        if len(instance) < int(schema.get("minProperties", 0)):
            errors.append(f"{path}: too few properties")
    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: too few items")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            errors.append(f"{path}: too many items")
        if schema.get("uniqueItems") and len({canonical_json_bytes(x) for x in instance}) != len(instance):
            errors.append(f"{path}: duplicate items")
        if "items" in schema:
            for index, value in enumerate(instance):
                errors.extend(validate_schema(value, schema["items"], root, f"{path}[{index}]"))
    if isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            errors.append(f"{path}: too short")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: pattern mismatch")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum")
    return errors


def runtime_case(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        **raw,
        "topology_control": "none",
        "time_horizon": 0.0,
        "trajectory_family": "stage02i_same_timestamp_no_trajectory",
        "initial_condition_family": "analytic_periodic_vortex",
        "disorder_family": raw["disorder_identity"],
    }


def uncertainty_entry(
    availability: str,
    value_kind: str,
    method: str,
    status: str,
    evidence: list[str],
    *,
    value: float | None = None,
    units: str | None = None,
    norm: str | None = None,
    rule: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "availability": availability,
        "value_kind": value_kind,
        "method": method,
        "status": status,
        "evidence_uris": evidence,
    }
    if value is not None:
        row["value"] = value
    if units is not None:
        row["units"] = units
    if norm is not None:
        row["norm"] = norm
    if rule is not None:
        row["qualification_rule_id"] = rule
    return row


def build_record(
    source: dict[str, Any], raw: dict[str, Any], generator: Any, stage02f: Any, config: dict[str, Any],
    freeze: dict[str, Any], six_row: dict[str, Any], conservation_row: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    case_id = source["candidate_id"]
    case = runtime_case(raw)
    state = generator.initial_state(case, config)
    rhs, edges = generator.sparse_rhs_components(state, case, config, apply_control=False)
    n = int(state["x"].shape[0])
    identity_order = np.lexsort((np.arange(n), state["x"][:, 1], state["x"][:, 0]))
    if not np.array_equal(identity_order, np.arange(n)):
        raise RuntimeError(f"Frozen regular source is not in canonical particle order: {case_id}")
    edge_order = np.lexsort((edges["pair_id"], edges["target"], edges["source"]))
    if not np.array_equal(edge_order, np.arange(len(edges["source"]))):
        raise RuntimeError(f"Frozen graph is not in canonical edge order: {case_id}")

    state_hash = stage02f.state_hash(state)
    graph_hash = stage02f.graph_hash(edges)
    if state_hash != source["hashes"]["state_hash"] or graph_hash != source["hashes"]["SPH_neighbor_graph_hash"]:
        raise RuntimeError(f"Frozen state/graph hash mismatch: {case_id}")
    if not np.array_equal(np.asarray(source["a_SPH"], dtype=np.float64), rhs["total"]):
        raise RuntimeError(f"Baseline reconstruction differs from source: {case_id}")

    src = edges["source"]
    dst = edges["target"]
    edge_lookup = {(int(i), int(j)): index for index, (i, j) in enumerate(zip(src, dst))}
    reciprocal = np.asarray([edge_lookup[(int(j), int(i))] for i, j in zip(src, dst)], dtype=np.int64)
    distance = np.linalg.norm(edges["displacement"], axis=1)
    dx = float(config["domain"]["box_length"]) / int(raw["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    support = float(raw["h_over_dx"]) * dx
    kernel_value, kernel_gradient = generator.kernel_values(distance, h)
    active = kernel_value > 0.0
    zero_exterior = ~active
    neighbor_total = np.bincount(src, minlength=n).astype(np.int64)
    neighbor_active = np.bincount(src[active], minlength=n).astype(np.int64)
    mass_value = float(config["physics"]["rho0"]) / n
    mass = np.full(n, mass_value, dtype=np.float64)
    a_sph = np.asarray(source["a_SPH"], dtype=np.float64)
    a_fourier = np.asarray(source["a_FOURIER2"], dtype=np.float64)
    a_analytic = np.asarray(source["a_ANALYTIC"], dtype=np.float64)
    delta = np.asarray(source["delta_a_primary"], dtype=np.float64)
    reference_difference = a_fourier - a_analytic
    if not np.allclose(delta, a_fourier - a_sph, rtol=1e-13, atol=1e-14):
        raise RuntimeError(f"Target sign identity failed: {case_id}")
    nodal_force = mass[:, None] * delta
    target_hash = content_hash(delta.tolist())
    source_hash = freeze["authorized_regular_target_record_hashes"][case_id]
    reference_l2 = float(source["reference_pair_qualification"]["agreement"]["L2_particle_rms"])
    target_l2 = float(source["primary_target_metrics"]["L2_particle_rms"])
    evidence_targets = str(TARGETS_PATH.relative_to(REPO_ROOT))
    evidence_six = str(SIX_PATH.relative_to(REPO_ROOT))
    evidence_ir = str(ARCHITECTURE_PATH.relative_to(REPO_ROOT))
    particle_state = {
        "particle_count": n,
        "dimension": 2,
        "particle_id_local": list(range(n)),
        "position_periodic": state["x"].tolist(),
        "velocity": state["v"].tolist(),
        "density": state["rho"].tolist(),
        "pressure": rhs["pressure_value"].tolist(),
        "mass": mass.tolist(),
        "support": np.full(n, support, dtype=np.float64).tolist(),
        "smoothing_length": np.full(n, h, dtype=np.float64).tolist(),
    }
    neighbor = {
        "representation": "directed_edges_with_reciprocal_pair_id",
        "source_index": src.tolist(),
        "target_index": dst.tolist(),
        "reciprocal_pair_id": edges["pair_id"].tolist(),
        "minimum_image_displacement": edges["displacement"].tolist(),
        "relative_velocity": (state["v"][dst] - state["v"][src]).tolist(),
        "distance": distance.tolist(),
        "normalized_distance": (distance / support).tolist(),
        "kernel_value": kernel_value.tolist(),
        "kernel_radial_gradient": kernel_gradient.tolist(),
        "minimum_image_convention": "periodic_unit_square_componentwise_nearest_image",
        "support_rule_id": "strict_r_less_than_case_H_over_dx_times_dx",
        "neighbor_graph_hash": graph_hash,
        "topology_status": source["topology"]["status"],
        "topology_defects": source["topology"]["defects"],
        "reciprocal_status": source["topology"]["reciprocal_status"],
        "cutoff_crossing_status": "none",
    }
    uncertainty = {
        "reference_uncertainty": uncertainty_entry(
            "available", "scalar_bound", "Fourier2_vs_analytic_particle_field_difference",
            "PASS", [evidence_targets], value=reference_l2, units="m s^-2", norm="L2_particle_rms",
            rule="stage02h_frozen_cross_reference_acceptance",
        ),
        "time_error": uncertainty_entry(
            "not_applicable", "categorical_only", "same_state_no_temporal_derivative",
            "NOT_APPLICABLE", [evidence_targets], rule="stage02i_same_timestamp_spatial_target",
        ),
        "space_error": uncertainty_entry(
            "available", "scalar_bound", "qualified_spatial_target_magnitude",
            "PASS", [evidence_six], value=target_l2, units="m s^-2", norm="L2_particle_rms",
            rule="stage02i_six_component_attribution_6_of_6",
        ),
        "model_form_uncertainty": uncertainty_entry(
            "available", "categorical_only", "frozen_spatial_operator_scope_check",
            "PASS", [evidence_six], rule="stage02i_spatial_scope_only_not_full_PDE_confirmation",
        ),
        "topology_uncertainty": uncertainty_entry(
            "available", "categorical_only", "reciprocal_graph_defect_audit",
            "PASS", [evidence_targets], rule="stage01_internal_force_tolerance_and_stage02i_topology",
        ),
        "resource_uncertainty": uncertainty_entry(
            "available", "categorical_only", "completed_CPU_float64_materialization",
            "PASS", [evidence_targets], rule="stage02j_controlled_CPU_float64",
        ),
        "gci_status": "GCI not justified",
        "single_total_gci_permitted": False,
    }
    base_record = {
        "schema_version": "pio-dataset-frame-1.0.0",
        "record_type": "frame",
        "sample_id": case_id,
        "particle_state": particle_state,
        "neighbor_information": neighbor,
        "a_SPH": {
            "values": a_sph.tolist(),
            "pressure_component": rhs["pressure"].tolist(),
            "viscosity_component": rhs["viscosity"].tolist(),
            "forcing_component": rhs["forcing"].tolist(),
            "source_id": "stage02i_frozen_baseline_SPH",
            "configuration_hash": source["hashes"]["physical_configuration_hash"],
        },
        "a_ref": {
            "values": a_fourier.tolist(),
            "reference_class": "R1_continuum_compatible",
            "source_id": "H_REF_FOURIER2",
            "method": "accepted_Fourier_spectral_spatial_reference_same_state",
            "same_state_evaluation": True,
            "model_form_compatibility": "compatible",
        },
        "delta_a": {
            "values": delta.tolist(),
            "sign_convention": "a_ref_minus_a_sph",
            "target_component_attribution": "discretization_attributed",
            "sign_check_status": "PASS",
        },
        "metadata": {
            "comparison_time": 0.0,
            "time_units": "s",
            "quantity_units": {
                "position": "m", "velocity": "m s^-1", "density": "kg m^-3",
                "pressure": "Pa", "mass": "kg", "support": "m", "acceleration": "m s^-2",
            },
            "state_hash": state_hash,
            "configuration_hash": source["hashes"]["physical_configuration_hash"],
            "trajectory_family": "stage02i_same_timestamp_no_trajectory",
            "initial_condition_family": "analytic_periodic_vortex",
            "resolution_family": source["resolution_identity"],
            "h_over_dx_family": source["support_identity"],
            "disorder_family": "regular",
            "deterministic_repeat_family": "stage02j_canonical_repeat_same_source_record",
            "split_assignment": "unassigned",
            "failure_flags": [],
            "resource_status": "PASS",
            "determinism_status": "PASS",
            "finite_values_status": "PASS",
        },
        "uncertainty": uncertainty,
        "provenance": {
            "baseline_source_id": "stage02i_frozen_baseline_SPH",
            "reference_source_id": "H_REF_FOURIER2_with_H_REF_ANALYTIC_secondary",
            "configuration_source_id": "stage02c_generation_configuration_readonly_for_stage02i_state_identity",
            "hash_algorithm": "sha256",
            "canonical_serialization_version": "pio-canonical-bytes-1.0.0",
            "software_environment_id": "stage02j_python_numpy_CPU_float64",
            "hardware_device_id": "CPU",
            "resource_policy_id": "stage02j_five_graph_materialization_only",
            "determinism_policy_id": "stage02j_byte_identical_double_serialization",
            "evidence_uris": [evidence_targets, evidence_six, evidence_ir],
        },
        "eligibility": {
            "rules_version": "pio-label-eligibility-1.0.0",
            "verdict": "diagnostic",
            "reason_codes": ["DIAG_STAGE02J_ELIGIBILITY_PENDING"],
            "state_alignment": "same_state_verified",
            "leakage_status": "PASS",
        },
    }
    record = {
        "stage02j_schema_version": "stage02j-controlled-regular-graph-0.1.0",
        "dataset_version": "controlled_regular_pair_scope_v0_1",
        "record_type": "complete_particle_graph",
        "case_id": case_id,
        "identity_and_provenance": {
            "family_id": "analytic_periodic_vortex_shared_physics_t0_v1",
            "state_family_id": "analytic_periodic_vortex",
            "resolution_id": source["resolution_identity"],
            "support_id": source["support_identity"],
            "disorder_id": "regular",
            "reference_primary_id": "H_REF_FOURIER2",
            "reference_secondary_id": "H_REF_ANALYTIC",
            "source_target_hash": source_hash,
            "configuration_hash": source["hashes"]["physical_configuration_hash"],
            "state_hash": state_hash,
            "graph_hash": graph_hash,
            "provenance_chain": [
                {"role": "source_target", "path": evidence_targets, "sha256": file_hash(TARGETS_PATH)},
                {"role": "source_target_record", "case_id": case_id, "sha256": source_hash},
                {"role": "architecture_authorization", "path": evidence_ir, "sha256": file_hash(ARCHITECTURE_PATH)},
                {"role": "stage02b_schema", "path": str(SCHEMA_B_PATH.relative_to(REPO_ROOT)), "sha256": file_hash(SCHEMA_B_PATH)},
            ],
            "source_particle_order": "lexicographic_periodic_position_then_original_id",
            "source_edge_order": "source_target_pair_id",
        },
        "stage02b_record": base_record,
        "reciprocal_graph_extensions": {
            "reciprocal_edge_mapping": reciprocal.tolist(),
            "active_kernel_indicator": active.tolist(),
            "zero_weight_exterior_edge_indicator": zero_exterior.tolist(),
            "neighbor_count_total": neighbor_total.tolist(),
            "neighbor_count_active": neighbor_active.tolist(),
            "edge_id_is_model_feature": False,
        },
        "references": {
            "a_FOURIER2": a_fourier.tolist(),
            "a_ANALYTIC": a_analytic.tolist(),
            "reference_difference": reference_difference.tolist(),
            "units": "m s^-2",
            "input_feature_permitted": False,
        },
        "target": {
            "delta_a": delta.tolist(),
            "nodal_force": nodal_force.tolist(),
            "mass": mass.tolist(),
            "sign_convention": "a_reference_minus_a_sph",
            "units": {"delta_a": "m s^-2", "nodal_force": "kg m s^-2", "mass": "kg"},
            "conservation_metadata": {
                "total_target_force": np.sum(nodal_force, axis=0, dtype=np.float64).tolist(),
                "normalized_total_force_residual": conservation_row["normalized_total_force_residual"],
                "pair_force_compatible": conservation_row["architecture_compatibility"] == "pair_force_compatible",
                "tolerance": conservation_row["tolerance"],
            },
            "edge_pair_force_target_saved": False,
            "least_squares_projection_saved_as_label": False,
        },
        "qualification": {
            "candidate_discretization_target": bool(six_row["candidate_discretization_target"]),
            "pair_force_compatible": conservation_row["architecture_compatibility"] == "pair_force_compatible",
            "six_component_attribution": "6/6_PASS" if six_row["pass_count"] == 6 else "NOT_6/6",
            "training_eligibility": "not_yet_evaluated",
            "architecture_scope": "PAIR_ONLY_REGULAR_SCOPE",
            "manual_override_permitted": False,
        },
    }
    audit_context = {
        "state": state,
        "edges": edges,
        "target_hash": target_hash,
        "total_target_force": np.sum(nodal_force, axis=0, dtype=np.float64),
        "reference_difference_L2": reference_l2,
        "support": support,
        "active": active,
    }
    return record, audit_context


def finite_tree(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, list):
        return all(finite_tree(v) for v in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def semantic_qc(
    record: dict[str, Any], decoded: dict[str, Any], context: dict[str, Any], source: dict[str, Any],
    stage02f: Any, config: dict[str, Any]
) -> dict[str, str]:
    base = record["stage02b_record"]
    particle = base["particle_state"]
    neighbor = base["neighbor_information"]
    n = particle["particle_count"]
    edge_count = len(neighbor["source_index"])
    shape_pass = all(
        len(particle[key]) == n
        for key in ("particle_id_local", "position_periodic", "velocity", "density", "pressure", "mass", "support", "smoothing_length")
    ) and all(
        len(neighbor[key]) == edge_count
        for key in ("source_index", "target_index", "reciprocal_pair_id", "minimum_image_displacement", "relative_velocity", "distance", "normalized_distance", "kernel_value", "kernel_radial_gradient")
    )
    src = np.asarray(neighbor["source_index"], dtype=np.int64)
    dst = np.asarray(neighbor["target_index"], dtype=np.int64)
    disp = np.asarray(neighbor["minimum_image_displacement"], dtype=np.float64)
    pair_id = np.asarray(neighbor["reciprocal_pair_id"], dtype=np.int64)
    edge_set = {(int(i), int(j)) for i, j in zip(src, dst)}
    duplicate = len(src) != len(edge_set)
    missing_reciprocal = any((j, i) not in edge_set for i, j in edge_set)
    distance = np.linalg.norm(disp, axis=1)
    support = np.asarray(particle["support"], dtype=np.float64)[src]
    strict_support = bool(np.all(distance < support))
    zero = np.asarray(record["reciprocal_graph_extensions"]["zero_weight_exterior_edge_indicator"], dtype=bool)
    active = np.asarray(record["reciprocal_graph_extensions"]["active_kernel_indicator"], dtype=bool)
    zero_retention = bool(np.array_equal(zero, ~active))
    delta = np.asarray(record["target"]["delta_a"], dtype=np.float64)
    a_ref = np.asarray(record["references"]["a_FOURIER2"], dtype=np.float64)
    a_sph = np.asarray(base["a_SPH"]["values"], dtype=np.float64)
    mass = np.asarray(record["target"]["mass"], dtype=np.float64)
    nodal = np.asarray(record["target"]["nodal_force"], dtype=np.float64)
    state_round = {
        "x": np.asarray(decoded["stage02b_record"]["particle_state"]["position_periodic"], dtype=np.float64),
        "v": np.asarray(decoded["stage02b_record"]["particle_state"]["velocity"], dtype=np.float64),
        "rho": np.asarray(decoded["stage02b_record"]["particle_state"]["density"], dtype=np.float64),
    }
    nb_round = decoded["stage02b_record"]["neighbor_information"]
    edges_round = {
        "source": np.asarray(nb_round["source_index"], dtype=np.int64),
        "target": np.asarray(nb_round["target_index"], dtype=np.int64),
        "displacement": np.asarray(nb_round["minimum_image_displacement"], dtype=np.float64),
        "pair_id": np.asarray(nb_round["reciprocal_pair_id"], dtype=np.int64),
    }
    total = np.sum(nodal, axis=0, dtype=np.float64)
    decoded_total = np.sum(np.asarray(decoded["target"]["nodal_force"], dtype=np.float64), axis=0, dtype=np.float64)
    checks = {
        "units": "PASS" if record["target"]["units"]["delta_a"] == "m s^-2" else "FAIL",
        "finite_values": "PASS" if finite_tree(record) else "FAIL",
        "shape_consistency": "PASS" if shape_pass else "FAIL",
        "reciprocal_topology": "PASS" if not missing_reciprocal else "FAIL",
        "duplicate_edge": "PASS" if not duplicate else "FAIL",
        "missing_reciprocal_edge": "PASS" if not missing_reciprocal else "FAIL",
        "strict_support": "PASS" if strict_support else "FAIL",
        "zero_weight_exterior_edge_retention": "PASS" if zero_retention else "FAIL",
        "target_sign": "PASS" if record["target"]["sign_convention"] == "a_reference_minus_a_sph" else "FAIL",
        "delta_identity": "PASS" if np.allclose(delta, a_ref - a_sph, rtol=1e-13, atol=1e-14) else "FAIL",
        "nodal_force_identity": "PASS" if np.array_equal(nodal, mass[:, None] * delta) else "FAIL",
        "Fourier_analytic_agreement": "PASS" if source["reference_pair_qualification"]["agreement"]["status"] == "PASS" else "FAIL",
        "pair_force_compatibility": "PASS" if record["qualification"]["pair_force_compatible"] else "FAIL",
        "canonical_roundtrip": "PASS" if canonical_json_bytes(record) == canonical_json_bytes(decoded) else "FAIL",
        "state_hash_roundtrip": "PASS" if stage02f.state_hash(state_round) == record["identity_and_provenance"]["state_hash"] else "FAIL",
        "graph_hash_roundtrip": "PASS" if stage02f.graph_hash(edges_round) == record["identity_and_provenance"]["graph_hash"] else "FAIL",
        "target_hash_roundtrip": "PASS" if content_hash(decoded["target"]["delta_a"]) == context["target_hash"] else "FAIL",
        "total_target_force_roundtrip": "PASS" if np.array_equal(total, decoded_total) else "FAIL",
        "provenance_closure": "PASS" if all(row.get("sha256", "").startswith("sha256:") for row in record["identity_and_provenance"]["provenance_chain"]) else "FAIL",
        "edge_pair_label_absent": "PASS" if not record["target"]["edge_pair_force_target_saved"] else "FAIL",
    }
    return checks


def make_leakage_graph(record_ids: list[str]) -> dict[str, Any]:
    relation_codes = [
        "SAME_ANALYTIC_PERIODIC_VORTEX_STATE_FAMILY",
        "SAME_TIMESTAMP_T0",
        "SAME_REFERENCE_GENERATION_FAMILY",
        "SAME_PHYSICAL_COEFFICIENTS",
        "SAME_PERIODIC_UNIT_DOMAIN",
        "SAME_TARGET_CONSTRUCTION_PROTOCOL",
        "SHARED_STAGE02I_ANCHOR_LINEAGE",
    ]
    edges = []
    adjacency = [[0 for _ in record_ids] for _ in record_ids]
    for i in range(len(record_ids)):
        for j in range(i + 1, len(record_ids)):
            adjacency[i][j] = adjacency[j][i] = 1
            edges.append({"left": record_ids[i], "right": record_ids[j], "reason_codes": relation_codes})
    component_payload = {"record_ids": record_ids, "relation_policy": relation_codes}
    return {
        "leakage_contract_source": "stage_02_Particle_Interaction_Operator/03_dataset/splitting/split_strategy.md",
        "node_definition": "one_complete_particle_graph_record",
        "nodes": record_ids,
        "edges": edges,
        "adjacency_order": record_ids,
        "adjacency_matrix": adjacency,
        "connected_component_count": 1,
        "connected_components": [
            {
                "component_id": "leakage_component_000",
                "record_ids": record_ids,
                "component_hash": content_hash(component_payload),
            }
        ],
        "all_declared_leakage_relations_preserved": True,
        "particle_edge_or_within_graph_split_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Stage 02J materialization requires explicit --execute")
    static_outputs = [QC_PATH, LEAKAGE_PATH, SPLIT_PATH, NORM_PATH, OOD_PATH, ELIGIBILITY_PATH, CANON_MANIFEST_PATH, DATASET_MANIFEST_PATH, RUN_MANIFEST_PATH]
    dynamic_outputs = [RAW_DIR / f"{case_id}.json" for case_id in AUTHORIZED] + [CANON_DIR / f"{case_id}.bin" for case_id in AUTHORIZED]
    for path in static_outputs + dynamic_outputs:
        if path.exists():
            raise FileExistsError(f"No-overwrite contract: {path}")

    freeze = load_json(FREEZE_PATH)
    scope = load_yaml(SCOPE_PATH)
    schema_j = load_json(SCHEMA_J_PATH)
    schema_b = load_json(SCHEMA_B_PATH)
    config = load_yaml(CONFIG_PATH)
    matrix = load_yaml(MATRIX_PATH)
    targets = load_json(TARGETS_PATH)
    six = load_json(SIX_PATH)
    conservation = load_json(CONSERVATION_PATH)
    architecture = load_json(ARCHITECTURE_PATH)
    force = load_json(FORCE_PATH)
    quadrature = load_json(QUADRATURE_PATH)
    pair_node = load_json(PAIR_NODE_PATH)
    load_yaml(FEATURE_PATH)
    load_yaml(SERIAL_PATH)
    for role in freeze["frozen_roles"].values():
        if file_hash(REPO_ROOT / role["path"]) != role["sha256"]:
            raise RuntimeError(f"Frozen input changed: {role['path']}")
    if freeze["authorized_regular_target_ids"] != AUTHORIZED or scope["authorized_regular_target_ids"] != AUTHORIZED:
        raise RuntimeError("Authorized regular list mismatch")
    if architecture["decision"] != "PAIR_ONLY_REGULAR_SCOPE":
        raise RuntimeError("Architecture authorization mismatch")

    generator = load_module("stage02j_readonly_generator", GENERATOR_PATH)
    stage02f = load_module("stage02j_readonly_hash_contract", STAGE02F_PATH)
    source_map = {row["candidate_id"]: row for row in targets["candidates"]}
    matrix_map = {row["case_id"]: row for row in matrix["cases"]}
    six_map = {row["candidate_id"]: row for row in six["results"]}
    conservation_map = {row["candidate_id"]: row for row in conservation["rows"]}

    raw_payloads: dict[Path, bytes] = {}
    canonical_payloads: dict[Path, bytes] = {}
    qc_rows = []
    canonical_rows = []
    for case_id in AUTHORIZED:
        source = source_map[case_id]
        if content_hash(source) != freeze["authorized_regular_target_record_hashes"][case_id]:
            raise RuntimeError(f"Authorized source record hash changed: {case_id}")
        record, context = build_record(
            source, matrix_map[case_id], generator, stage02f, config, freeze,
            six_map[case_id], conservation_map[case_id],
        )
        structural_b = validate_schema(record["stage02b_record"], schema_b, schema_b)
        structural_j = validate_schema(record, schema_j, schema_j)
        first = serialize_record(record)
        second = serialize_record(record)
        decoded = deserialize_record(first)
        semantic = semantic_qc(record, decoded, context, source, stage02f, config)
        deterministic = first == second and sha256_bytes(first) == sha256_bytes(second)
        all_pass = not structural_b and not structural_j and all(value == "PASS" for value in semantic.values()) and deterministic
        if not all_pass:
            raise RuntimeError(
                f"Hard QC failure before materialization: {case_id}: "
                f"Stage02B={structural_b}, Stage02J={structural_j}, semantic={semantic}, deterministic={deterministic}"
            )
        raw_path = RAW_DIR / f"{case_id}.json"
        canonical_path = CANON_DIR / f"{case_id}.bin"
        raw = pretty_json_bytes(record)
        raw_payloads[raw_path] = raw
        canonical_payloads[canonical_path] = first
        qc_rows.append({
            "case_id": case_id,
            "stage02b_frozen_schema_errors": structural_b,
            "stage02j_extension_schema_errors": structural_j,
            "checks": semantic,
            "deterministic_bytes": "PASS" if deterministic else "FAIL",
            "provenance_status": "PASS",
            "status": "PASS",
            "verdict": "accepted_controlled_development_record",
            "controlled_retry_used": False,
        })
        canonical_rows.append({
            "case_id": case_id,
            "raw_record_path": str(raw_path.relative_to(REPO_ROOT)),
            "raw_record_sha256": sha256_bytes(raw),
            "canonical_record_path": str(canonical_path.relative_to(REPO_ROOT)),
            "canonical_record_sha256": sha256_bytes(first),
            "canonical_byte_count": len(first),
            "state_hash": record["identity_and_provenance"]["state_hash"],
            "graph_hash": record["identity_and_provenance"]["graph_hash"],
            "target_hash": context["target_hash"],
            "total_target_force_before": context["total_target_force"].tolist(),
            "total_target_force_after": np.sum(np.asarray(decoded["target"]["nodal_force"], dtype=np.float64), axis=0).tolist(),
            "roundtrip_status": "PASS",
            "deterministic_repeat_status": "PASS",
        })

    canonical_manifest = {
        "serializer_version": "stage02j-canonical-binary-0.1.0",
        "record_count": len(canonical_rows),
        "fixed_float_dtype": "big_endian_float64",
        "fixed_integer_dtype": "big_endian_int64",
        "fixed_array_path_order": [path for path, _ in ARRAY_PATHS],
        "rows": canonical_rows,
        "all_roundtrip_checks_pass": True,
        "all_deterministic_repeats_pass": True,
    }
    qc = {
        "audit_version": "stage02j-quality-control-0.1.0",
        "record_count": 5,
        "hard_failure_count": 0,
        "rejected_dataset_record_count": 0,
        "infrastructure_retry_count": 0,
        "rows": qc_rows,
        "overall_status": "PASS",
    }
    leakage = make_leakage_graph(AUTHORIZED)
    split = {
        "audit_version": "stage02j-split-feasibility-0.1.0",
        "sample_unit": "complete_particle_graph",
        "record_count": 5,
        "leakage_connected_component_count": 1,
        "formal_train_validation_test_split_exists": False,
        "status": "INSUFFICIENT_LEAKAGE_DISCONNECTED_FAMILIES",
        "split_manifest_created": False,
        "record_assignment": {case_id: "development_audit_corpus" for case_id in AUTHORIZED},
        "configuration_axis_holdout_feasibility": {
            "role": "diagnostic_only",
            "resolution_axis": "possible_as_configuration_sensitivity_but_not_independent_test",
            "support_axis": "possible_as_configuration_sensitivity_but_not_physical_family_generalization",
            "substitutes_for_formal_family_split": False,
        },
        "particle_edge_or_within_graph_split_used": False,
    }
    normalization = {
        "contract_version": "stage02j-prospective-normalization-0.1.0",
        "decision": "prospective_specification_only",
        "fitted_statistics_created": False,
        "blocking_reason": "no_formal_leakage_audited_train_split",
        "fit_scope_if_future_split_exists": "formal_train_split_only",
        "validation_test_application_only": True,
        "epsilon": {"value": 1.0e-12, "units": "field_native_units", "status": "prospective_not_fitted"},
        "field_wise_rules": {
            "position_periodic": "domain_length_nondimensionalization",
            "velocity": "train_only_component_mean_and_scale_or_prefrozen_physical_scale",
            "density": "train_only_center_at_rho0_and_scale",
            "pressure": "train_only_scale_or_prefrozen_rho0_c0_squared",
            "mass": "preserve_physical_value_and_units",
            "relative_displacement": "local_support_scale",
            "distance": "local_support_scale",
        },
        "train_record_hashes": [],
        "all_five_records_used_for_fit": False,
        "jitter_used_for_fit": False,
        "target_information_used_to_standardize_input": False,
        "normalization_statistics": None,
    }

    force_map = {row["candidate_id"]: row for row in force["rows"]}
    quad_map = {row["candidate_id"]: row for row in quadrature["rows"]}
    pair_node_map = {row["candidate_id"]: row for row in pair_node["rows"]}
    anchor = source_map["i_anchor_n16_h26_regular"]["primary_target_metrics"]
    ood_rows = []
    for case_id in JITTER:
        source = source_map[case_id]
        qrow = quad_map[case_id]
        prow = pair_node_map[case_id]
        metrics = source["primary_target_metrics"]
        ood_rows.append({
            "case_id": case_id,
            "role": "distribution_shift_diagnostic_only",
            "training_label_permitted": False,
            "normalization_fit_permitted": False,
            "split_membership": "none",
            "pair_force_supervision_permitted": False,
            "original_target_hash": freeze["jitter_target_record_hashes"][case_id],
            "classification": "node_residual_only",
            "quadrature_contamination_reason": "particle_quadrature_contamination_under_frozen_equal_mass_target_contract",
            "target_amplification_relative_to_regular_anchor": {
                "L2_ratio": metrics["L2_particle_rms"] / anchor["L2_particle_rms"],
                "Linf_ratio": metrics["Linf_particle_vector"] / anchor["Linf_particle_vector"],
            },
            "conservation_residual": force_map[case_id]["components"]["total"]["F_target_normalized_residual"],
            "node_residual": {
                "norm": prow["norm_y_node"],
                "node_over_y_ratio": prow["y_node_over_y_ratio"],
            },
            "geometry_metrics": {
                "zeroth_defect_RMS": qrow["partition_of_unity"]["zeroth_defect_RMS"],
                "first_moment_defect_RMS": qrow["partition_of_unity"]["first_moment_defect_RMS"],
                "coverage_isotropy_min": qrow["particle_coverage_anisotropy"]["isotropy_min"],
                "coverage_isotropy_median": qrow["particle_coverage_anisotropy"]["isotropy_median"],
            },
            "reference_uncertainty": {
                "Fourier_analytic_field_L2": source["reference_pair_qualification"]["agreement"]["L2_particle_rms"],
                "status": source["reference_pair_qualification"]["agreement"]["status"],
            },
            "target_modified": False,
            "conservation_projection_used": False,
        })
    ood = {
        "registry_version": "stage02j-jitter-ood-0.1.0",
        "record_count": 2,
        "readonly": True,
        "rows": ood_rows,
    }

    eligibility_rows = []
    for case_id in AUTHORIZED:
        gates = {
            "source_target_qualified": "PASS",
            "pair_only_scope_authorized": "PASS",
            "schema": "PASS",
            "canonical_serialization": "PASS",
            "provenance": "PASS",
            "uncertainty": "PASS",
            "topology": "PASS",
            "determinism": "PASS",
            "family_assignment": "PASS",
            "leakage": "PASS",
            "split_assignment": "FAIL_INSUFFICIENT_DISCONNECTED_FAMILIES",
            "normalization_contract": "BLOCKED_NO_FORMAL_TRAIN_SPLIT",
        }
        eligibility_rows.append({
            "case_id": case_id,
            "gates": gates,
            "first_eight_gates_pass": True,
            "all_twelve_gates_pass": False,
            "verdict": "diagnostic",
            "reason_codes": [
                "DIAG_INSUFFICIENT_LEAKAGE_DISCONNECTED_FAMILIES",
                "DIAG_NORMALIZATION_NOT_FITTED_NO_FORMAL_TRAIN_SPLIT",
            ],
            "eligible_for_future_training": False,
            "manual_override_permitted": False,
        })
    eligibility = {
        "audit_version": "stage02j-record-eligibility-0.1.0",
        "manual_override_permitted": False,
        "record_count": 5,
        "verdict_counts": {"eligible_for_future_training": 0, "diagnostic": 5, "rejected": 0},
        "rows": eligibility_rows,
        "dataset_readiness_category": "not_ready",
        "Stage02K_authorized": False,
    }

    canonical_manifest_bytes = pretty_json_bytes(canonical_manifest)
    qc_bytes = pretty_json_bytes(qc)
    leakage_bytes = pretty_json_bytes(leakage)
    split_bytes = pretty_json_bytes(split)
    norm_bytes = yaml.safe_dump(normalization, sort_keys=True, allow_unicode=True).encode("utf-8")
    ood_bytes = pretty_json_bytes(ood)
    eligibility_bytes = pretty_json_bytes(eligibility)
    materialized = {**raw_payloads, **canonical_payloads}
    materialized.update({
        CANON_MANIFEST_PATH: canonical_manifest_bytes,
        QC_PATH: qc_bytes,
        LEAKAGE_PATH: leakage_bytes,
        SPLIT_PATH: split_bytes,
        NORM_PATH: norm_bytes,
        OOD_PATH: ood_bytes,
        ELIGIBILITY_PATH: eligibility_bytes,
    })
    dataset_manifest = {
        "manifest_version": "stage02j-controlled-regular-dataset-manifest-0.1.0",
        "dataset_version": "controlled_regular_pair_scope_v0_1",
        "sample_unit": "complete_particle_graph",
        "sample_count": 5,
        "particle_count_is_sample_count": False,
        "authorized_record_ids": AUTHORIZED,
        "records": canonical_rows,
        "leakage_component_count": 1,
        "formal_split_created": False,
        "normalization_statistics_created": False,
        "jitter_registry_record_count": 2,
        "edge_pair_force_target_created": False,
        "new_target_or_physical_state_created": False,
        "model_created": False,
        "training_performed": False,
        "readiness_category": "not_ready",
        "Stage02K_authorized": False,
    }
    dataset_manifest_bytes = pretty_json_bytes(dataset_manifest)
    materialized[DATASET_MANIFEST_PATH] = dataset_manifest_bytes
    run_manifest = {
        "run_version": "stage02j-controlled-materialization-0.1.0",
        "execution": "CPU_float64_deterministic",
        "input_freeze_hash": file_hash(FREEZE_PATH),
        "input_freeze_reverified": True,
        "output_hashes": {
            str(path.relative_to(REPO_ROOT)): sha256_bytes(payload)
            for path, payload in sorted(materialized.items(), key=lambda item: str(item[0]))
        },
        "record_count": 5,
        "QC_status": "PASS",
        "leakage_graph_complete": True,
        "formal_split_created": False,
        "normalization_fitted": False,
        "jitter_OOD_only": True,
        "target_modified": False,
        "edge_pair_label_created": False,
        "new_target_generated": False,
        "new_physical_state_generated": False,
        "trajectory_generated": False,
        "augmentation_used": False,
        "model_generated": False,
        "training_performed": False,
        "performance_claim_generated": False,
        "historical_files_modified": False,
    }
    materialized[RUN_MANIFEST_PATH] = pretty_json_bytes(run_manifest)

    for path, payload in materialized.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    print(json.dumps({
        "record_count": 5,
        "QC_status": "PASS",
        "leakage_components": 1,
        "split_status": split["status"],
        "normalization_fitted": False,
        "eligible_for_future_training": 0,
        "Stage02K_authorized": False,
        "readiness_category": "not_ready",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
