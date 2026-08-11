#!/usr/bin/env python3
"""Build and hash immutable protocol v0.2 before blind-formula materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


formula_path = ROOT / "blind_family_generator/blind_family_formulas_v0_2.json"
if formula_path.exists():
    raise RuntimeError("protocol cannot be rebuilt after blind formula materialization")
freeze = json.loads((ROOT / "freeze/stage02mp_historical_freeze_manifest.json").read_text())
scale = json.loads((ROOT / "target_scale/train_only_supervision_scale.json").read_text())
if freeze["status"] != "PASS" or scale["train_graph_count"] != 10:
    raise RuntimeError("freeze or supervision scale incomplete")

sources = {
    "historical_freeze": ROOT / "freeze/stage02mp_historical_freeze_manifest.json",
    "supervision_scale": ROOT / "target_scale/train_only_supervision_scale.json",
    "loss": ROOT / "conditioning_contract/loss_v0_2.py",
    "optimizer": ROOT / "conditioning_contract/optimizer_conditioning_contract.json",
    "model_arms": ROOT / "model_arms/model_arms_v0_2.json",
    "run_matrix": ROOT / "run_matrix/run_matrix_v0_2.json",
    "checkpoint_and_stopping": ROOT / "checkpointing/checkpoint_and_stopping_contract.json",
    "success_gates": ROOT / "success_gates/success_gates_v0_2.json",
    "blind_generator_config": ROOT / "blind_family_generator/blind_generator_config_v0_2.yaml",
    "input_normalization": ROOT / "normalization/input_normalization_reuse_contract.json",
    "test_seal": ROOT / "test_seal/test_seal_preregistration.json",
    "route_termination": ROOT / "route_termination/route_termination_contract.json",
}
protocol = {
    "protocol_version": "pair-force-pio-training-protocol-v0.2.0",
    "authorization": "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING",
    "design_only_stage": "02M-P",
    "freeze_order": [
        "historical_input_freeze",
        "decode_exactly_10_train_targets",
        "compute_and_freeze_a_sup",
        "freeze_loss",
        "freeze_optimizer_and_schedule",
        "freeze_architecture_arms",
        "freeze_new_seeds",
        "freeze_budget_and_early_stopping",
        "freeze_success_gates",
        "freeze_blind_generator_source_config_seeds_roles",
        "generate_training_protocol_v0_2_yaml",
        "generate_immutable_protocol_sha256",
        "only_then_materialize_blind_formulas",
    ],
    "a_sup": scale["a_sup"],
    "a_sup_units": scale["units"],
    "supervision_scale_hash": scale["result_hash"],
    "loss": "equal_complete_graph_mean_of_node_vector_MSE_after_division_by_a_sup",
    "static_metrics": "Stage02L_Q_L2_Q_Linf_cosine_unchanged",
    "optimizer": {"name": "AdamW", "learning_rate": 1e-3, "betas": [0.9, 0.999], "epsilon": 1e-12, "weight_decay": 0.0, "global_norm_clip": 1.0},
    "schedule": {"warmup_updates": 50, "decay": "cosine", "minimum_learning_rate": 1e-5, "maximum_updates": 1000},
    "architectures": ["K0", "K1", "K2"],
    "seeds": [20261211, 20261212, 20261213],
    "prospective_run_count": 9,
    "validation_interval": 20,
    "minimum_updates_before_stopping": 300,
    "patience_updates": 200,
    "minimum_validation_improvement": 1e-6,
    "checkpoint_interval": 20,
    "checkpoint_selection": "lowest_validation_graph_mean_Q_L2_then_earlier_update",
    "success_gates": {"train_Q_L2_max": 0.25, "validation_family_mean_max": 0.90, "validation_every_graph_max": 1.10, "test_family_mean_max": 0.90, "test_every_graph_max": 1.10, "seed_rule": "2_of_3"},
    "new_blind_families": [
        {"family_id": "V02_BLIND_VALIDATION_01", "root_seed": 2026080501, "role": "future_validation", "graph_count": 5},
        {"family_id": "V02_BLIND_TEST_01", "root_seed": 2026080502, "role": "future_test", "graph_count": 5},
    ],
    "collection": "blind_multifamily_pair_scope_v1_1_protocol_v02",
    "train_families": ["BLIND_FAMILY_01", "BLIND_FAMILY_02"],
    "excluded_consumed_families": ["BLIND_FAMILY_03", "BLIND_FAMILY_04"],
    "input_normalization_hash": "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051",
    "test_target_access": False,
    "test_release_manifest_in_stage02mp": False,
    "counters": {"new_optimizer_steps": 0, "new_training_runs": 0, "new_test_evaluations": 0},
    "source_hashes": {name: sha(path) for name, path in sources.items()},
    "blind_formulas_materialized_at_protocol_freeze": False,
}
yaml_path = ROOT / "freeze/training_protocol_v0_2.yaml"
yaml_path.write_text(yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True))
record = {
    "freeze_version": "stage02mp-protocol-hash-1.0.0",
    "protocol_path": str(yaml_path.relative_to(REPO)),
    "protocol_sha256": sha(yaml_path),
    "frozen_before_blind_formula_materialization": True,
    "blind_formula_path_absent_at_hash_time": not formula_path.exists(),
    "supervision_scale_hash": scale["result_hash"],
    "status": "PASS",
}
(ROOT / "freeze/protocol_v0_2_hash.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps(record, sort_keys=True))
