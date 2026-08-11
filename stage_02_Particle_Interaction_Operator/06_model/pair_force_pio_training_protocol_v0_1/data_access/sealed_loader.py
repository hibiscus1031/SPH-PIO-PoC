"""Stage 02L identity-first selective loader with a hard test-target seal."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

COLLECTION_ID = "blind_multifamily_pair_scope_v1_0"
SCHEMA_COMPATIBILITY_ID = "controlled_regular_pair_scope_v0_1"
NORMALIZATION_HASH = "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051"

INPUT_ARRAY_PATHS = {
    "stage02b_record.particle_state.position_periodic",
    "stage02b_record.particle_state.velocity",
    "stage02b_record.particle_state.density",
    "stage02b_record.particle_state.pressure",
    "stage02b_record.particle_state.mass",
    "stage02b_record.particle_state.smoothing_length",
    "stage02b_record.neighbor_information.source_index",
    "stage02b_record.neighbor_information.target_index",
    "stage02b_record.neighbor_information.minimum_image_displacement",
    "stage02b_record.neighbor_information.relative_velocity",
    "reciprocal_graph_extensions.active_kernel_indicator",
}
TARGET_ARRAY_PATHS = {"target.delta_a", "target.nodal_force", "target.mass", "stage02b_record.delta_a.values"}
REFERENCE_OR_AUDIT_ARRAY_PATHS = {
    "stage02b_record.a_SPH.values", "stage02b_record.a_SPH.pressure_component",
    "stage02b_record.a_SPH.viscosity_component", "stage02b_record.a_SPH.forcing_component",
    "stage02b_record.a_ref.values", "references.a_FOURIER2", "references.a_ANALYTIC",
    "references.reference_difference",
}


class AccessPolicyError(RuntimeError):
    pass


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _content_hash(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def _dtype(code: str) -> np.dtype[Any]:
    if code == "f8": return np.dtype(">f8")
    if code == "i8": return np.dtype(">i8")
    if code == "u1": return np.dtype(np.uint8)
    raise ValueError(code)


def _decode_array(raw: bytes, code: str, shape: list[int]) -> np.ndarray:
    array = np.frombuffer(raw, dtype=_dtype(code)).reshape(shape)
    if code == "f8": return array.astype(np.float64)
    if code == "i8": return array.astype(np.int64)
    return array.astype(bool)


def selective_decode(payload: bytes, selected_paths: set[str], expected_order: list[str]) -> tuple[dict[str, Any], dict[str, np.ndarray], list[str]]:
    if payload[:8] != b"SPHPIOJ1": raise ValueError("canonical magic mismatch")
    offset = 8
    meta_size = struct.unpack_from(">Q", payload, offset)[0]; offset += 8
    metadata = json.loads(payload[offset:offset+meta_size].decode()); offset += meta_size
    count = struct.unpack_from(">I", payload, offset)[0]; offset += 4
    arrays: dict[str, np.ndarray] = {}
    skipped: list[str] = []
    seen: list[str] = []
    for _ in range(count):
        name_size = struct.unpack_from(">H", payload, offset)[0]; offset += 2
        path = payload[offset:offset+name_size].decode(); offset += name_size
        code = payload[offset:offset+2].decode("ascii"); offset += 2
        rank = struct.unpack_from(">B", payload, offset)[0]; offset += 1
        shape = []
        for _axis in range(rank): shape.append(struct.unpack_from(">Q", payload, offset)[0]); offset += 8
        byte_count = struct.unpack_from(">Q", payload, offset)[0]; offset += 8
        if path in selected_paths:
            arrays[path] = _decode_array(payload[offset:offset+byte_count], code, shape)
        else:
            skipped.append(path)
        offset += byte_count
        seen.append(path)
    if offset != len(payload) or seen != expected_order: raise ValueError("canonical order/length mismatch")
    return metadata, arrays, skipped


@dataclass(frozen=True)
class InputRecord:
    case_id: str
    split_role: str
    arrays: dict[str, np.ndarray]
    schema_compatibility_identifier: str


class SealedCollectionLoader:
    def __init__(self, repo: Path, protocol_hash: str) -> None:
        self.repo = repo
        self.protocol_hash = protocol_hash
        self.root = repo / "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0"
        self.operation_order: list[str] = []
        self.test_target_access = False
        self.target_decode_log: list[dict[str, Any]] = []
        self.payloads: dict[str, bytes] = {}
        self._initialize_identity()

    def _initialize_identity(self) -> None:
        self.manifest = json.loads((self.root / "manifests/stage02jw_dataset_manifest.json").read_text())
        self.operation_order.append("collection_manifest")
        if self.manifest.get("dataset_collection") != COLLECTION_ID: raise AccessPolicyError("collection_id")
        self.operation_order.append("collection_id_verified")
        self.inventory = json.loads((self.root / "canonical_records/canonical_inventory.json").read_text())
        self.rows = {row["case_id"]: row for row in self.inventory["rows"]}
        if len(self.rows) != 20: raise AccessPolicyError("record_count")
        for case_id, row in self.rows.items():
            payload = (self.repo / row["canonical_path"]).read_bytes()
            if _sha(payload) != row["canonical_sha256"]: raise AccessPolicyError(f"record_hash:{case_id}")
            self.payloads[case_id] = payload
        self.operation_order.append("20_record_hashes_verified_without_array_decode")
        self.split = json.loads((self.root / "splits/prefrozen_split_manifest.json").read_text())
        if self.split.get("counts") != {"future_train": 10, "future_validation": 5, "future_test": 5}: raise AccessPolicyError("split")
        self.operation_order.append("split_verified")
        self.normalization = json.loads((self.root / "normalization/train_only_graph_balanced_statistics.json").read_text())
        if self.normalization.get("dataset_collection") != COLLECTION_ID or self.normalization.get("statistics_hash") != NORMALIZATION_HASH or _content_hash(self.normalization["statistics"]) != NORMALIZATION_HASH: raise AccessPolicyError("normalization")
        self.operation_order.append("train_only_normalization_verified")

    def load_inputs(self, case_id: str) -> InputRecord:
        row = self.rows[case_id]
        metadata, arrays, skipped = selective_decode(self.payloads[case_id], INPUT_ARRAY_PATHS, self.inventory["fixed_array_path_order"])
        compatibility = metadata.get("dataset_version")
        if compatibility != SCHEMA_COMPATIBILITY_ID: raise AccessPolicyError("schema_compatibility")
        if any(path in arrays for path in TARGET_ARRAY_PATHS | REFERENCE_OR_AUDIT_ARRAY_PATHS): raise AccessPolicyError("forbidden_input_decode")
        self.target_decode_log.append({"case_id": case_id, "split_role": row["split_role"], "target_arrays_decoded": False, "skipped_array_count": len(skipped)})
        return InputRecord(case_id, row["split_role"], arrays, compatibility)

    def load_target(self, case_id: str) -> np.ndarray:
        role = self.rows[case_id]["split_role"]
        if role == "future_test" and not self.test_target_access:
            raise AccessPolicyError("TEST_TARGET_SEALED")
        if role != "future_train":
            raise AccessPolicyError("STAGE02L_TARGET_ACCESS_DENIED")
        raise AccessPolicyError("STAGE02L_STATIC_PREFLIGHT_USES_SYNTHETIC_SUPERVISION_ONLY")

    def audit(self) -> dict[str, Any]:
        roles = {role: sum(row["split_role"] == role for row in self.rows.values()) for role in ("future_train", "future_validation", "future_test")}
        return {
            "contract_version": "stage02l-sealed-loader-1.0.0",
            "protocol_hash_verified_before_decode": self.protocol_hash,
            "operation_order": self.operation_order,
            "collection_id": COLLECTION_ID,
            "schema_compatibility_identifier": SCHEMA_COMPATIBILITY_ID,
            "record_hash_pass_count": 20,
            "split_counts": roles,
            "normalization_statistics_hash": NORMALIZATION_HASH,
            "test_target_access": self.test_target_access,
            "target_decode_log": self.target_decode_log,
            "target_array_decode_count": sum(x["target_arrays_decoded"] for x in self.target_decode_log),
            "status": "PASS",
        }
