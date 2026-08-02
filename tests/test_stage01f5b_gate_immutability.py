import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_gate_hashes_match_frozen_bundle():
    source = yaml.safe_load((ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml").read_text())
    bundle = json.loads((ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/manifests/stage01f5_execution_bundle_v3.json").read_text())
    blocks = {"T1_T5": source["time_gates"], "P1_P3": source["platform_gates"], "H1_H5": source["heldout"]["gates"], "S1_S4": source["spatial_matrix"]["gates"], "hard_safety": source["hard_safety_gates"]}
    for name, value in blocks.items():
        digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert digest == bundle["frozen_gate_hashes"][name]

