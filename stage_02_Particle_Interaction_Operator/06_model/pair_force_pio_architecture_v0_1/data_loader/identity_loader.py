"""Identity-first Stage 02K loader for the frozen blind multifamily collection."""

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


def _sha_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _content_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return _sha_bytes(payload)


def _set_path(value: dict[str, Any], path: str, payload: Any) -> None:
    tokens = path.split(".")
    node = value
    for token in tokens[:-1]:
        node = node[token]
    node[tokens[-1]] = payload


def decode_canonical(payload: bytes, expected_paths: list[str]) -> dict[str, Any]:
    if payload[:8] != b"SPHPIOJ1":
        raise ValueError("canonical magic mismatch")
    offset = 8
    metadata_size = struct.unpack_from(">Q", payload, offset)[0]
    offset += 8
    record = json.loads(payload[offset : offset + metadata_size].decode("utf-8"))
    offset += metadata_size
    count = struct.unpack_from(">I", payload, offset)[0]
    offset += 4
    seen: list[str] = []
    for _ in range(count):
        name_size = struct.unpack_from(">H", payload, offset)[0]
        offset += 2
        path = payload[offset : offset + name_size].decode("utf-8")
        offset += name_size
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
        elif code == "i8":
            array = np.frombuffer(raw, dtype=">i8").astype(np.int64).reshape(shape)
        elif code == "u1":
            array = np.frombuffer(raw, dtype=np.uint8).astype(bool).reshape(shape)
        else:
            raise ValueError(f"unsupported canonical dtype: {code}")
        _set_path(record, path, array)
        seen.append(path)
    if offset != len(payload) or seen != expected_paths:
        raise ValueError("canonical field order or byte length mismatch")
    return record


@dataclass(frozen=True)
class LoadedCollection:
    collection_manifest: dict[str, Any]
    inventory: dict[str, Any]
    split_manifest: dict[str, Any]
    normalization: dict[str, Any]
    records: tuple[dict[str, Any], ...]
    audit: dict[str, Any]


class IdentityContractError(RuntimeError):
    pass


def load_collection(repo: Path) -> LoadedCollection:
    stage = repo / "stage_02_Particle_Interaction_Operator"
    root = stage / "05_dataset/blind_multifamily_pair_scope_v1_0"
    order: list[str] = []

    # 1. Collection manifest is deliberately the first dataset object read.
    manifest_path = root / "manifests/stage02jw_dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    order.append("collection_manifest")
    if manifest.get("dataset_collection") != COLLECTION_ID:
        raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: collection_id")
    order.append("collection_id_verified")

    # 2. Verify every frozen canonical payload before any decode.
    inventory = json.loads((root / "canonical_records/canonical_inventory.json").read_text())
    if inventory.get("record_count") != 20 or len(inventory.get("rows", [])) != 20:
        raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: record_count")
    payloads: list[tuple[dict[str, Any], bytes]] = []
    hash_rows = []
    for row in inventory["rows"]:
        path = repo / row["canonical_path"]
        payload = path.read_bytes()
        actual = _sha_bytes(payload)
        passed = actual == row["canonical_sha256"]
        hash_rows.append({"case_id": row["case_id"], "expected": row["canonical_sha256"], "actual": actual, "status": "PASS" if passed else "FAIL"})
        if not passed:
            raise IdentityContractError(f"DATA_LOADER_IDENTITY_CONTRACT_FAIL: hash:{row['case_id']}")
        payloads.append((row, payload))
    order.append("20_record_hashes_verified")

    # 3. Split identity is loaded and checked independently of record metadata.
    split = json.loads((root / "splits/prefrozen_split_manifest.json").read_text())
    expected_counts = {"future_train": 10, "future_validation": 5, "future_test": 5}
    if split.get("counts") != expected_counts or len(split.get("record_assignments", {})) != 20:
        raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: split")
    for row in inventory["rows"]:
        if split["record_assignments"].get(row["case_id"]) != row["split_role"]:
            raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: split_inventory_disagreement")
    order.append("split_manifest_verified")

    # 4. Load only the normalization explicitly bound to this collection/train split.
    normalization = json.loads((root / "normalization/train_only_graph_balanced_statistics.json").read_text())
    if normalization.get("dataset_collection") != COLLECTION_ID:
        raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: normalization_collection")
    if normalization.get("train_record_count") != 10:
        raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: normalization_train_count")
    if normalization.get("statistics_hash") != _content_hash(normalization.get("statistics")):
        raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: normalization_hash")
    order.append("train_only_normalization_verified")

    # 5. Canonical records are decoded only after all identity checks above.
    records = []
    for row, payload in payloads:
        record = decode_canonical(payload, inventory["fixed_array_path_order"])
        if record.get("dataset_version") != SCHEMA_COMPATIBILITY_ID:
            raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: schema_compatibility")
        if record.get("case_id") != row["case_id"]:
            raise IdentityContractError("DATA_LOADER_IDENTITY_CONTRACT_FAIL: case_identity")
        records.append(record)
    order.append("canonical_records_decoded")

    audit = {
        "contract_version": "stage02k-loader-identity-1.0.0",
        "collection_id": COLLECTION_ID,
        "schema_compatibility_identifier": SCHEMA_COMPATIBILITY_ID,
        "schema_identifier_used_for_collection_selection": False,
        "schema_identifier_used_for_split_selection": False,
        "schema_identifier_used_for_normalization_selection": False,
        "schema_identifier_used_for_lineage_identity": False,
        "operation_order": order,
        "record_hash_checks": hash_rows,
        "record_hash_pass_count": 20,
        "split_counts": expected_counts,
        "normalization_statistics_hash": normalization["statistics_hash"],
        "collection_identity": "PASS",
        "schema_compatibility_identity": "PASS",
        "status": "PASS",
    }
    return LoadedCollection(manifest, inventory, split, normalization, tuple(records), audit)
