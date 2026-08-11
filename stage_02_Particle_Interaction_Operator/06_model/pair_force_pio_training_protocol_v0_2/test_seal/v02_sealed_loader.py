"""Protocol-v0.2 collection loader with an unreleased new-test target seal."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
sys.path.insert(0, str(LROOT / "data_access"))
from sealed_loader import INPUT_ARRAY_PATHS, selective_decode  # noqa: E402

TARGET_PATH = "target.delta_a"


class V02AccessPolicyError(RuntimeError):
    pass


class V02SealedLoader:
    def __init__(self, protocol_sha256: str) -> None:
        protocol = json.loads((ROOT / "freeze/protocol_v0_2_hash.json").read_text())
        if protocol_sha256 != protocol["protocol_sha256"]:
            raise V02AccessPolicyError("PROTOCOL_HASH_MISMATCH")
        self.inventory = json.loads((ROOT / "canonical_records/canonical_inventory.json").read_text())
        self.rows = {row["case_id"]: row for row in self.inventory["rows"]}
        self.payloads: dict[str, bytes] = {}
        for case_id, row in self.rows.items():
            payload = (REPO / row["canonical_path"]).read_bytes()
            actual = "sha256:" + hashlib.sha256(payload).hexdigest()
            if actual != row["canonical_sha256"]:
                raise V02AccessPolicyError(f"RECORD_HASH_MISMATCH:{case_id}")
            self.payloads[case_id] = payload
        self.test_target_access = False
        self.decode_log: list[dict[str, Any]] = []

    def load_inputs(self, case_id: str) -> dict[str, Any]:
        metadata, arrays, _ = selective_decode(self.payloads[case_id], INPUT_ARRAY_PATHS, self.inventory["fixed_array_path_order"])
        self.decode_log.append({"case_id": case_id, "role": self.rows[case_id]["split_role"], "target_decoded": False})
        return {"metadata": metadata, "arrays": arrays}

    def load_target(self, case_id: str, purpose: str) -> Any:
        role = self.rows[case_id]["split_role"]
        if role == "future_test":
            raise V02AccessPolicyError("V02_TEST_TARGET_SEALED")
        if role != "future_train" or purpose != "training":
            raise V02AccessPolicyError(f"TARGET_PURPOSE_DENIED:{role}:{purpose}")
        _metadata, arrays, _ = selective_decode(self.payloads[case_id], {TARGET_PATH}, self.inventory["fixed_array_path_order"])
        self.decode_log.append({"case_id": case_id, "role": role, "target_decoded": True})
        return arrays[TARGET_PATH]

    def direct_array_path(self, case_id: str, path: str, purpose: str) -> Any:
        if path != TARGET_PATH:
            raise V02AccessPolicyError("DIRECT_PATH_NOT_AUTHORIZED")
        return self.load_target(case_id, purpose)

    def wildcard_decode(self, case_id: str, selector: str, purpose: str) -> Any:
        if "*" in selector:
            raise V02AccessPolicyError("WILDCARD_TARGET_DECODE_DENIED")
        return self.direct_array_path(case_id, selector, purpose)

    def metric_evaluator_access(self, case_ids: list[str], purpose: str) -> list[Any]:
        if any(self.rows[case_id]["split_role"] == "future_test" for case_id in case_ids):
            raise V02AccessPolicyError("V02_TEST_METRIC_EVALUATOR_DENIED")
        return [self.load_target(case_id, purpose) for case_id in case_ids]

    def audit(self) -> dict[str, Any]:
        return {
            "record_count": len(self.rows),
            "test_target_access": self.test_target_access,
            "train_target_decode_count": sum(row["target_decoded"] and row["role"] == "future_train" for row in self.decode_log),
            "validation_target_decode_count": sum(row["target_decoded"] and row["role"] == "future_validation" for row in self.decode_log),
            "test_target_decode_count": sum(row["target_decoded"] and row["role"] == "future_test" for row in self.decode_log),
            "decode_log": self.decode_log,
        }
