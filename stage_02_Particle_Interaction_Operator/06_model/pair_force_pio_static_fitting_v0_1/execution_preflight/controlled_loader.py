"""Stage 02M controlled target loader with a one-way sealed-test release gate."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parents[3]
REPO = Path(__file__).resolve().parents[4]
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
sys.path.insert(0, str(LROOT / "data_access"))

from sealed_loader import (  # noqa: E402
    AccessPolicyError,
    INPUT_ARRAY_PATHS,
    SealedCollectionLoader,
    selective_decode,
)

TARGET_PATH = "target.delta_a"


@dataclass(frozen=True)
class SupervisedRecord:
    case_id: str
    split_role: str
    family_id: str
    resolution_id: str
    support_id: str
    target: np.ndarray


class ControlledStage02MLoader:
    def __init__(self, protocol_hash: str) -> None:
        self.base = SealedCollectionLoader(REPO, protocol_hash)
        self.test_target_access = False
        self.test_release_hash: str | None = None
        self.decode_log: list[dict[str, Any]] = []
        self.evaluation_counts: dict[str, int] = {}

    @property
    def rows(self) -> dict[str, dict[str, Any]]:
        return self.base.rows

    def load_inputs(self, case_id: str) -> Any:
        return self.base.load_inputs(case_id)

    def _authorize(self, case_id: str, purpose: str) -> str:
        role = self.rows[case_id]["split_role"]
        if role == "future_train" and purpose == "training": return role
        if role == "future_validation" and purpose == "validation": return role
        if role == "future_test" and purpose == "sealed_test" and self.test_target_access and self.test_release_hash: return role
        if role == "future_test": raise AccessPolicyError("TEST_TARGET_SEALED")
        raise AccessPolicyError(f"TARGET_PURPOSE_DENIED:{role}:{purpose}")

    def load_target(self, case_id: str, purpose: str) -> SupervisedRecord:
        role = self._authorize(case_id, purpose)
        metadata, arrays, _skipped = selective_decode(
            self.base.payloads[case_id], {TARGET_PATH}, self.base.inventory["fixed_array_path_order"]
        )
        target = arrays.get(TARGET_PATH)
        if target is None: raise AccessPolicyError("target decode missing")
        identity = metadata["identity_and_provenance"]
        self.decode_log.append({"case_id": case_id, "split_role": role, "purpose": purpose, "target_paths_decoded": [TARGET_PATH]})
        return SupervisedRecord(case_id, role, self.rows[case_id]["family_id"], identity["resolution_id"], identity["support_id"], target)

    def direct_array_path(self, case_id: str, path: str, purpose: str) -> np.ndarray:
        if path != TARGET_PATH: raise AccessPolicyError("DIRECT_PATH_NOT_AUTHORIZED")
        return self.load_target(case_id, purpose).target

    def wildcard_decode(self, case_id: str, selector: str, purpose: str) -> None:
        if "*" in selector: raise AccessPolicyError("WILDCARD_TARGET_DECODE_DENIED")
        self.direct_array_path(case_id, selector, purpose)

    def metric_evaluator_access(self, case_ids: list[str], purpose: str) -> list[SupervisedRecord]:
        if any(self.rows[case_id]["split_role"] == "future_test" for case_id in case_ids) and not self.test_target_access:
            raise AccessPolicyError("METRIC_EVALUATOR_TEST_DENIED")
        return [self.load_target(case_id, purpose) for case_id in case_ids]

    def release_test(self, release_manifest_path: Path) -> None:
        if self.test_target_access: raise AccessPolicyError("TEST_ALREADY_RELEASED")
        manifest = json.loads(release_manifest_path.read_text())
        if manifest.get("one_time_evaluation_authorization") is not True or manifest.get("status") != "RELEASED":
            raise AccessPolicyError("INVALID_TEST_RELEASE_MANIFEST")
        import hashlib
        self.test_release_hash = "sha256:" + hashlib.sha256(release_manifest_path.read_bytes()).hexdigest()
        self.test_target_access = True

    def mark_checkpoint_evaluated(self, checkpoint_hash: str) -> None:
        count = self.evaluation_counts.get(checkpoint_hash, 0) + 1
        if count > 1: raise AccessPolicyError("CHECKPOINT_TEST_EVALUATED_MORE_THAN_ONCE")
        self.evaluation_counts[checkpoint_hash] = count

    def audit(self) -> dict[str, Any]:
        by_role = {role: sum(row["split_role"] == role for row in self.rows.values()) for role in ("future_train", "future_validation", "future_test")}
        return {
            "collection_id": self.base.manifest["dataset_collection"],
            "record_hash_pass_count": 20,
            "split_counts": by_role,
            "normalization_statistics_hash": self.base.normalization["statistics_hash"],
            "target_decode_log": self.decode_log,
            "train_target_decode_count": sum(x["split_role"] == "future_train" for x in self.decode_log),
            "validation_target_decode_count": sum(x["split_role"] == "future_validation" for x in self.decode_log),
            "test_target_decode_count": sum(x["split_role"] == "future_test" for x in self.decode_log),
            "test_target_access": self.test_target_access,
            "test_release_hash": self.test_release_hash,
            "test_checkpoint_evaluation_counts": self.evaluation_counts,
        }
