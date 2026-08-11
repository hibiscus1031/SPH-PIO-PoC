#!/usr/bin/env python3
"""Compute the one frozen Stage 02M-P supervision scale from exactly 10 train targets."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
sys.path.insert(0, str(LROOT / "data_access"))
from sealed_loader import SealedCollectionLoader, selective_decode  # noqa: E402

PROTOCOL_AUTHORIZATION_HASH = "sha256:ab02a49a508c4ddcab5db037886abd329ab29d2eedfc8ffe5d818ad691668648"
TARGET_PATH = "target.delta_a"


def sha_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical(value: object) -> str:
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def kahan(values: list[float]) -> float:
    total = 0.0
    correction = 0.0
    for value in values:
        adjusted = value - correction
        updated = total + adjusted
        correction = (updated - total) - adjusted
        total = updated
    return total


freeze = json.loads((ROOT / "freeze/stage02mp_historical_freeze_manifest.json").read_text())
if freeze["status"] != "PASS":
    raise RuntimeError("historical freeze failed")
loader = SealedCollectionLoader(REPO, PROTOCOL_AUTHORIZATION_HASH)
case_ids = sorted(case for case, row in loader.rows.items() if row["split_role"] == "future_train")
if len(case_ids) != 10:
    raise RuntimeError("exactly 10 train graphs required")
rows = []
graph_energies = []
for case_id in case_ids:
    metadata, arrays, _ = selective_decode(loader.payloads[case_id], {TARGET_PATH}, loader.inventory["fixed_array_path_order"])
    target = np.asarray(arrays[TARGET_PATH], dtype=np.float64)
    node_squared_norms = [float(x * x + y * y) for x, y in target]
    graph_energy = kahan(node_squared_norms) / len(node_squared_norms)
    graph_energies.append(graph_energy)
    target_payload = np.asarray(target, dtype="<f8", order="C").tobytes()
    rows.append({
        "case_id": case_id,
        "family_id": loader.rows[case_id]["family_id"],
        "node_count": len(target),
        "target_array_hash": sha_bytes(target_payload),
        "graph_mean_squared_vector_norm": graph_energy,
        "graph_target_RMS_m_per_s2": math.sqrt(graph_energy),
    })
a_sup = math.sqrt(kahan(graph_energies) / 10.0)
core = {
    "calculation_version": "stage02mp-train-supervision-scale-1.0.0",
    "definition": "sqrt(mean_over_10_complete_train_graphs(mean_over_nodes(||delta_a||^2)))",
    "execution": "CPU_float64_deterministic_Kahan",
    "graph_weighting": "equal_complete_graph_weight_no_particle_count_weighting",
    "train_family_ids": sorted({row["family_id"] for row in rows}),
    "train_graph_count": len(rows),
    "target_hashes": [row["target_array_hash"] for row in rows],
    "rows": rows,
    "a_sup": a_sup,
    "units": "m s^-2",
    "use": "supervision_and_output_loss_scaling_only",
    "forbidden_uses": ["node_feature", "edge_feature", "validation_or_test_fitted_statistic", "family_identifier", "input_normalization"],
    "historical_validation_target_decode_count": 0,
    "historical_test_target_decode_count": 0,
}
core["calculation_code_hash"] = sha_bytes(Path(__file__).read_bytes())
core["result_hash"] = canonical(core)
output = ROOT / "target_scale/train_only_supervision_scale.json"
output.write_text(json.dumps(core, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(json.dumps({"a_sup": a_sup, "result_hash": core["result_hash"], "train_graphs": len(rows)}))
