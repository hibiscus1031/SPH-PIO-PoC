"""Preregister Stage07B before any NEW_TRAIN_V2 trajectory decode."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

import numpy as np
import torch
import yaml


HERE = Path(__file__).resolve(); B = HERE.parents[1]; STAGE07 = HERE.parents[3]; ROOT = HERE.parents[4]
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO

SEEDS = [20700701, 20700702, 20700703]
ANCHORS = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
NEW = ["HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03", "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
LINEAGES = ANCHORS + NEW
VARIANTS = ["LOW", "MAIN"]
ARMS = {"D1": D1InstantaneousPairMLP, "D2": D2CausalRecurrentPairPIO, "D3": D3CausalTemporalTransformerPIO}


def canonical(value: Any) -> bytes: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
def sha_bytes(value: bytes) -> str: return "sha256:" + hashlib.sha256(value).hexdigest()
def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()
def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
def tensor_bytes(value: torch.Tensor) -> bytes:
    a = value.detach().contiguous().cpu().numpy(); return str(a.dtype).encode() + b"\0" + np.asarray(a.shape, dtype=np.int64).tobytes() + a.tobytes()
def parameter_hash(model: torch.nn.Module) -> str:
    h = hashlib.sha256()
    for name, parameter in model.named_parameters(): h.update(name.encode()); h.update(tensor_bytes(parameter))
    return "sha256:" + h.hexdigest()


def seal_audit() -> dict[str, Any]:
    stage07a_seal = json.loads((STAGE07 / "09_manifests/stage07a_validation_seal_manifest.json").read_text())
    rows = []
    for item in stage07a_seal["private_artifacts"]:
        path = ROOT / item["path"]
        rows.append({"path": item["path"], "exists": path.is_file(), "mode": oct(stat.S_IMODE(path.stat().st_mode)),
                     "expected_sha256": item["sha256"], "payload_read": False})
    return {"fresh_validation_private_artifact_count": len(rows), "rows": rows,
            "pass": len(rows) == 89 and all(r["exists"] and r["mode"] == "0o0" and not r["payload_read"] for r in rows)}


def main() -> None:
    stage07a = json.loads((STAGE07 / "09_manifests/stage07a_final_manifest.json").read_text())
    stage06c = json.loads((ROOT / "stage_06_Optimizer_Update_Dynamics_Training/09_manifests/stage06c_final_manifest.json").read_text())
    stage06cr = json.loads((ROOT / "stage_06_Optimizer_Update_Dynamics_Training/09_manifests/stage06cr_final_manifest.json").read_text())
    assert stage07a["final_status"] == "HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED"
    assert stage06c["status"] == "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED"
    assert stage06cr["status"] == "FORMAL_TRAINING_FAILURE_ATTRIBUTED"
    assert stage07a["next_stage"]["authorization"] == "LIMITED"
    role = json.loads((STAGE07 / "09_manifests/stage07a_role_manifest.json").read_text())
    assert role["train_v2"] == LINEAGES

    groups = json.loads((ROOT / "stage_06_Optimizer_Update_Dynamics_Training/01_update_map_qualification/optimizer_definition/parameter_groups.json").read_text())["groups"]
    group_path = B / "gradient_identity/parameter_groups.json"; write_json(group_path, {"groups": groups, "unique_complete_coverage": True})
    models = []
    for arm, cls in ARMS.items():
        for seed in SEEDS:
            torch.manual_seed(seed); model = cls().to(dtype=torch.float64, device="cpu")
            schema = [{"name": n, "shape": list(p.shape), "count": p.numel()} for n, p in model.named_parameters()]
            models.append({"arm": arm, "seed": seed, "complete_parameter_sha256": parameter_hash(model),
                           "parameter_count": sum(p.numel() for p in model.parameters()),
                           "parameter_schema_sha256": sha_bytes(canonical(schema)), "fresh_initialization": True,
                           "historical_weight_reads": 0, "future_stage07d_seed_reuse_forbidden": True})
            del model
    model_path = B / "model_seeds/preregistered_model_identities.json"; write_json(model_path, {"seeds": SEEDS, "models": models})

    selections = []
    for lineage in LINEAGES:
        for variant in VARIANTS:
            ranked = sorted((hashlib.sha256(("stage07b_lineage_update_context_v1" + lineage + variant + str(origin)).encode()).hexdigest(), origin) for origin in range(32))
            chosen = ranked[:8]
            selections.append({"lineage": lineage, "variant": variant, "origins": [o for _, o in chosen],
                               "selection_hashes": ["sha256:" + h for h, _ in chosen],
                               "global_origins": [o for _, o in chosen[:4]], "replacement_count": 0})
    origin_path = B / "update_contexts/preregistered_update_contexts.json"
    write_json(origin_path, {"salt": "stage07b_lineage_update_context_v1", "selection": selections,
                             "lineage_batch_size": 16, "global_batch_size": 112,
                             "lineage_contexts_per_arm": 42, "global_contexts_per_arm": 3, "formal_context_count": 135})

    probes = []
    for arm, arm_groups in groups.items():
        for group in arm_groups:
            count = group["element_count"]
            for seed in SEEDS:
                coordinates = []
                for slot in range(2):
                    key = hashlib.sha256(("stage07b_coordinate_v1" + arm + group["group"] + str(seed) + str(slot)).encode()).hexdigest()
                    coordinates.append({"slot": slot, "group_flat_index": int(key[:16], 16) % count, "key": "sha256:" + key})
                blocks = []; size = min(32, count)
                for slot in range(2):
                    key = hashlib.sha256(("stage07b_block_v1" + arm + group["group"] + str(seed) + str(slot)).encode()).hexdigest()
                    start = int(key[:16], 16) % count; indices = [(start + i) % count for i in range(size)]
                    raw = b""; counter = 0
                    while len(raw) * 8 < size:
                        raw += hashlib.sha256(bytes.fromhex(key) + counter.to_bytes(8, "big")).digest(); counter += 1
                    signs = (2 * np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:size].astype(int) - 1).tolist()
                    blocks.append({"slot": slot, "start": start, "indices": indices, "rademacher_signs": signs, "key": "sha256:" + key})
                probes.append({"arm": arm, "group": group["group"], "seed": seed, "context": "GLOBAL", "coordinates": coordinates, "blocks": blocks})
    probe_path = B / "coordinate_boundary/preregistered_diagnostic_plan.json"
    write_json(probe_path, {"contexts": probes, "coordinates_per_group_context": 2, "blocks_per_group_context": 2,
                            "diagnostic_only": True, "complete_coordinate_block_FD_qualified": False})

    contract = {
        "contract_id": "train_v2_defect_scale_optimizer_requalification_v0_1",
        "status": "FROZEN_BEFORE_NEW_TRAIN_V2_TRAJECTORY_DECODE",
        "authorization": "HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED",
        "historical_status": {"Stage06C": "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
                              "Stage06C_R": "FORMAL_TRAINING_FAILURE_ATTRIBUTED", "D3_primary": "TRAIN_LINEAGE_HETEROGENEITY_DOMINANT"},
        "train_v2": {"lineages": LINEAGES, "anchors": ANCHORS, "new_train": NEW, "variants": VARIANTS,
                     "origins_per_variant": 32, "formal_N8_target_count": 896},
        "d0_reference": {"identity": "complete_explicit_midpoint_RK2_D0", "dt": 2.0/20.0/256.0,
                         "class_functional_repeat": True, "route_L2_max": 1e-13, "route_Linf_max": 1e-12,
                         "graph_source_identity_exact": True},
        "defect": {"delta_v": "v_ref(n+1)-v_D0(n+1)", "a_def": "delta_v/dt", "formal_precursor": "a_def",
                   "a_cm": "sum_i(m_i*a_def_i)/sum_i(m_i)", "a_cons": "a_def-a_cm", "a_incompatible": "a_cm"},
        "conservative_gates": {"family_balanced_mean_incompatible_fraction_max": 5e-3, "p95_max": 1e-2,
                               "maximum_max": 5e-2, "each_lineage_mean_max": 1e-2, "zero_force_residual_max": 1e-12},
        "pair_basis": {"midpoint_graph": True, "radial_transverse": True, "frozen_F0": "sqrt(m_i*m_j)*cs^2/L",
                       "coefficient_bound": [-1, 1], "unbounded": {"mean": .02, "p95": .05, "max": .10, "lineage": .05},
                       "bounded": {"mean": .05, "p95": .10, "max": .20, "lineage": .10}, "LCDF_08_exception": False},
        "scale_v2": {"formula": "sqrt(mean_lineage mean_variant mean_origin mean_node mean_component a_cons^2)",
                     "balanced": ["lineage", "variant", "origin", "node", "component"], "clip": False,
                     "s_a_v1_historical": 3.45632855338432798e-1, "zero_correction_loss": 1.0, "absolute_error_max": 1e-12},
        "uncertainty": {"u_origin": "max(U1,U2,U3,U4,U5,u_roundoff_floor)", "s_a_v2_over_u_a_v2_min": 100,
                        "each_lineage_ratio_min": 20, "each_variant_ratio_min": 20,
                        "signal_bearing": "mass_norm(a_def)>=10*u_origin", "each_lineage_fraction_min": .90, "overall_fraction_min": .95},
        "distinguishability": {"all_origins_retained": True, "lineage_reweighting": False},
        "models": {"seeds": SEEDS, "identities": str(model_path.relative_to(ROOT)), "fresh_initialization": True,
                   "historical_weight_reads": 0, "future_Stage07D_must_use_different_seeds": True},
        "contexts": {"manifest": str(origin_path.relative_to(ROOT)), "lineage": "2 variants x 8 origins",
                     "global": "14 lineages x 2 variants x 4 origins", "total": 135},
        "optimizer": {"family": "AdamW", "betas": [.9, .999], "eps": 1e-12, "weight_decay": 0,
                      "amsgrad": False, "global_gradient_clip": 1.0, "formal_requalification_lr": 1e-5,
                      "forbidden_lrs": [3e-5, 1e-4, 3e-4, 1e-3], "zero_state_per_fresh_clone": True},
        "loss": {"identity": "balanced mean ||(a_eff_theta-a_cons)/s_a_v2||^2", "old_scale_qualification_forbidden": True},
        "gradient": {"full_and_repeat": True, "all_groups_activity_floor": "100x repeat/float64 floor", "deterministic": True},
        "one_step": {"delta_L": "<-100*u_L", "cos_update_negative_gradient": ">0", "relative_update": "<1e-2",
                     "density_positive": True, "force_residual_max": 1e-10, "deterministic": True, "all_groups": True},
        "actual_update_fd": {"scales": [.25, .5, 1., 2.], "central": True, "reverse_sign": True,
                             "two_adjacent_direction_stable": True, "observed_consistent": True, "topology_safety": True},
        "micro_update": {"horizons": [2, 4], "L1_lt_L0": True, "L2_le_L1_plus_floor": True, "L4_le_L2_plus_floor": True,
                         "relative_reduction_step4_min": 1e-4, "individual_relative_increase_max": 1e-3,
                         "relative_parameter_displacement_max": 5e-2},
        "aggregation": {"arm_lineage": "at_least_2_of_3_seeds", "arm": "14_of_14_lineages",
                        "global": "3_of_3_seeds", "overall": "D1_and_D2_and_D3"},
        "gradient_diagnostic": {"cosine_matrix": True, "posthoc_only": True, "hard_gate": False},
        "coordinate_boundary": {"plan": str(probe_path.relative_to(ROOT)), "diagnostic_only": True,
                                "FD_WINDOW_MISSING_allowed": True,
                                "hard_failures": ["SIGN_CONTRADICTION", "MAPPING_CONTRADICTION", "NONDETERMINISTIC", "SAFETY_FAIL"],
                                "complete_coordinate_qualification": False},
        "structure_safety": {"reciprocal_antisymmetry": True, "force_residual_max": 1e-10,
                             "transforms": ["permutation", "edge_reorder", "translation", "Galilean", "SO2", "reflection", "periodic_shift"],
                             "positive_density": True, "finite": True, "deterministic_graph": True, "accepted_commit": 1, "midpoint_commit": 0},
        "resolution_diagnostic": {"resolutions": [12, 16], "variant": "MAIN", "hash_origins_per_lineage": 4,
                                  "qualification_replacement": False, "scale_redefinition": False, "convergence_claim": False},
        "access": {"TRAIN_only": LINEAGES, "consumed_validation_payload_decode": 0, "fresh_validation_private_decode": 0,
                   "original_sealed_test_decode": 0, "fresh_private_artifact_count": 89},
        "resources": {"device": "CPU", "dtype": "float64", "D3_sdpa": "MATH", "peak_rss_delta_max": 1610612736,
                      "no_monotonic_autograd_retention": True, "no_dense_particle_N_by_N": True,
                      "finite_completion": True, "all_hashes_complete": True, "qualification_models_destroyed": True,
                      "training_checkpoints": 0},
        "prohibitions": {"higher_lr": True, "architecture_change": True, "feature_engineering": True, "loss_change": True,
                         "lineage_removal": True, "LCDF_08_removal": True, "reweighting": True, "curriculum": True,
                         "model_ranking": True, "training_runs": 0, "rollout": True},
        "terminal_statuses": ["TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED",
                              "TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_NOT_QUALIFIED",
                              "TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_EVIDENCE_INCOMPLETE"]}
    contract_path = B / "contracts/train_v2_defect_scale_optimizer_requalification_v0_1.yaml"
    contract_path.parent.mkdir(parents=True, exist_ok=True); contract_path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    key_inputs = [STAGE07 / "09_manifests/stage07a_final_manifest.json", STAGE07 / "09_manifests/stage07a_role_manifest.json",
                  STAGE07 / "09_manifests/stage07a_trajectory_manifest.json", STAGE07 / "09_manifests/stage07a_validation_seal_manifest.json",
                  ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_final_manifest.json",
                  ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json",
                  ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_scale_manifest.json",
                  ROOT / "stage_06_Optimizer_Update_Dynamics_Training/09_manifests/stage06c_final_manifest.json",
                  ROOT / "stage_06_Optimizer_Update_Dynamics_Training/09_manifests/stage06cr_final_manifest.json"]
    historical = [{"path": str(p.relative_to(ROOT)), "sha256": sha_file(p), "bytes": p.stat().st_size} for p in key_inputs]
    seal = seal_audit(); assert seal["pass"]
    freeze = {"schema": "sph-pio-poc.stage07b.input-freeze.v1", "contract_path": str(contract_path.relative_to(ROOT)),
              "contract_sha256": sha_file(contract_path), "frozen_before_new_train_trajectory_decode": True,
              "new_train_trajectory_decode_count_at_freeze": 0, "train_v2": LINEAGES, "target_count": 896,
              "model_manifest": {"path": str(model_path.relative_to(ROOT)), "sha256": sha_file(model_path)},
              "context_manifest": {"path": str(origin_path.relative_to(ROOT)), "sha256": sha_file(origin_path)},
              "group_manifest": {"path": str(group_path.relative_to(ROOT)), "sha256": sha_file(group_path)},
              "probe_plan": {"path": str(probe_path.relative_to(ROOT)), "sha256": sha_file(probe_path)},
              "historical_inputs": historical, "fresh_validation_start_audit": seal,
              "decode_counts": {"consumed_validation_state": 0, "consumed_validation_target": 0,
                                "fresh_validation_formula_private": 0, "fresh_validation_state": 0, "fresh_validation_source": 0,
                                "fresh_validation_target": 0, "fresh_validation_origin": 0,
                                "sealed_formula": 0, "sealed_state": 0, "sealed_source": 0, "sealed_target": 0, "sealed_origin": 0},
              "execution_counts": {"training_runs": 0, "rollouts": 0, "higher_lr_experiments": 0, "model_rankings": 0}}
    freeze_path = B / "freeze/stage07b_input_freeze_record.json"; write_json(freeze_path, freeze)
    write_json(STAGE07 / "09_manifests/stage07b_input_freeze_manifest.json", freeze)
    write_json(B / "access_control/start_access_audit.json", seal)
    print(json.dumps({"contract_sha256": freeze["contract_sha256"], "lineages": len(LINEAGES), "targets": 896,
                      "models": len(models), "contexts": 135, "fresh_private": len(seal["rows"]), "pass": True}, indent=2))


if __name__ == "__main__": main()
