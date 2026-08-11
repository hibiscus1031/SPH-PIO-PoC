"""Stage 02M-Q controlled loader with one-way new-test release."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
QROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_2"
PROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
sys.path.insert(0, str(LROOT / "data_access"))
from sealed_loader import INPUT_ARRAY_PATHS, selective_decode  # noqa: E402

TARGET_PATH = "target.delta_a"


class AccessPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class InputRecord:
    case_id: str
    split_role: str
    arrays: dict[str, np.ndarray]


@dataclass(frozen=True)
class SupervisedRecord:
    case_id: str
    split_role: str
    family_id: str
    resolution_id: str
    support_id: str
    target: np.ndarray


class ControlledStage02MQLoader:
    def __init__(self, protocol_hash: str) -> None:
        expected = json.loads((PROOT / "freeze/protocol_v0_2_hash.json").read_text())["protocol_sha256"]
        if protocol_hash != expected:
            raise AccessPolicyError("PROTOCOL_HASH_MISMATCH")
        self.inventory = json.loads((PROOT / "canonical_records/canonical_inventory.json").read_text())
        self.rows = {row["case_id"]: row for row in self.inventory["rows"]}
        self.payloads = {}
        for case_id, row in self.rows.items():
            payload = (REPO / row["canonical_path"]).read_bytes()
            actual = "sha256:" + hashlib.sha256(payload).hexdigest()
            if actual != row["canonical_sha256"]:
                raise AccessPolicyError(f"RECORD_HASH_MISMATCH:{case_id}")
            self.payloads[case_id] = payload
        self.manifest = json.loads((PROOT / "manifests/v1_1_collection_manifest.json").read_text())
        self.base = self
        self.test_target_access = False
        self.test_release_hash: str | None = None
        self.decode_log: list[dict[str, Any]] = []
        self.evaluation_counts: dict[str, int] = {}

    def load_inputs(self, case_id: str) -> InputRecord:
        _metadata, arrays, _ = selective_decode(self.payloads[case_id], INPUT_ARRAY_PATHS, self.inventory["fixed_array_path_order"])
        self.decode_log.append({"case_id": case_id, "split_role": self.rows[case_id]["split_role"], "target_decoded": False})
        return InputRecord(case_id, self.rows[case_id]["split_role"], arrays)

    def load_target(self, case_id: str, purpose: str) -> SupervisedRecord:
        row = self.rows[case_id]
        role = row["split_role"]
        allowed = (role == "future_train" and purpose == "training") or (role == "future_validation" and purpose == "validation") or (role == "future_test" and purpose == "sealed_test" and self.test_target_access and self.test_release_hash)
        if not allowed:
            if role == "future_test":
                raise AccessPolicyError("V02_TEST_TARGET_SEALED")
            raise AccessPolicyError(f"TARGET_PURPOSE_DENIED:{role}:{purpose}")
        metadata, arrays, _ = selective_decode(self.payloads[case_id], {TARGET_PATH}, self.inventory["fixed_array_path_order"])
        identity = metadata["identity_and_provenance"]
        self.decode_log.append({"case_id": case_id, "split_role": role, "target_decoded": True, "purpose": purpose})
        return SupervisedRecord(case_id, role, row["family_id"], identity["resolution_id"], identity["support_id"], arrays[TARGET_PATH])

    def direct_array_path(self, case_id: str, path: str, purpose: str) -> np.ndarray:
        if path != TARGET_PATH:
            raise AccessPolicyError("DIRECT_PATH_NOT_AUTHORIZED")
        return self.load_target(case_id, purpose).target

    def wildcard_decode(self, case_id: str, selector: str, purpose: str) -> Any:
        if "*" in selector:
            raise AccessPolicyError("WILDCARD_TARGET_DECODE_DENIED")
        return self.direct_array_path(case_id, selector, purpose)

    def metric_evaluator_access(self, case_ids: list[str], purpose: str) -> list[SupervisedRecord]:
        if any(self.rows[case_id]["split_role"] == "future_test" for case_id in case_ids) and not self.test_target_access:
            raise AccessPolicyError("V02_TEST_METRIC_EVALUATOR_DENIED")
        return [self.load_target(case_id, purpose) for case_id in case_ids]

    def release_test(self, release_manifest_path: Path) -> None:
        if self.test_target_access:
            raise AccessPolicyError("TEST_ALREADY_RELEASED")
        manifest = json.loads(release_manifest_path.read_text())
        if manifest.get("one_time_evaluation_authorization") is not True or manifest.get("status") != "RELEASED":
            raise AccessPolicyError("INVALID_TEST_RELEASE_MANIFEST")
        self.test_release_hash = "sha256:" + hashlib.sha256(release_manifest_path.read_bytes()).hexdigest()
        self.test_target_access = True

    def mark_checkpoint_evaluated(self, checkpoint_hash: str) -> None:
        count = self.evaluation_counts.get(checkpoint_hash, 0) + 1
        if count > 1:
            raise AccessPolicyError("CHECKPOINT_TEST_EVALUATED_MORE_THAN_ONCE")
        self.evaluation_counts[checkpoint_hash] = count

    def audit(self) -> dict[str, Any]:
        return {
            "collection_id": self.manifest["dataset_collection"],
            "record_hash_pass_count": len(self.rows),
            "split_counts": {role: sum(row["split_role"] == role for row in self.rows.values()) for role in ("future_train", "future_validation", "future_test")},
            "target_decode_log": self.decode_log,
            "train_target_decode_count": sum(row.get("target_decoded") and row["split_role"] == "future_train" for row in self.decode_log),
            "validation_target_decode_count": sum(row.get("target_decoded") and row["split_role"] == "future_validation" for row in self.decode_log),
            "test_target_decode_count": sum(row.get("target_decoded") and row["split_role"] == "future_test" for row in self.decode_log),
            "test_target_access": self.test_target_access,
            "test_release_hash": self.test_release_hash,
            "test_checkpoint_evaluation_counts": self.evaluation_counts,
        }
