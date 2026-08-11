"""Preregister Stage 06A before the first blind TRAIN-target decode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
import yaml

HERE = Path(__file__).resolve()
STAGE06 = HERE.parents[2]
ROOT = HERE.parents[3]
STAGE05 = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training"
STAGE05C = STAGE05 / "02_optimizer_gradient_qualification/stage05c"
STAGE05CR = STAGE05 / "02_optimizer_gradient_qualification/stage05cr"
STAGE05CQ = STAGE05 / "02_optimizer_gradient_qualification/stage05cq"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO

SEEDS = [20600601, 20600602, 20600603]
FUTURE_FORMAL_SEED_NAMESPACE = "stage06b_formal_seed_v1:not-any-of-20600601-20600603"
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
VARIANTS = ["VARIANT_LOW", "VARIANT_MAIN"]
ARMS = {"D1": D1InstantaneousPairMLP, "D2": D2CausalRecurrentPairPIO, "D3": D3CausalTemporalTransformerPIO}
LRS = [1e-5, 3e-5, 1e-4, 3e-4, 1e-3]
FD_SCALES = [.25, .5, 1., 2.]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tensor_bytes(value: torch.Tensor) -> bytes:
    array = value.detach().contiguous().cpu().numpy()
    return str(array.dtype).encode() + b"\0" + np.asarray(array.shape, dtype=np.int64).tobytes() + array.tobytes()


def parameter_hash(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, parameter in model.named_parameters():
        digest.update(name.encode()); digest.update(tensor_bytes(parameter))
    return "sha256:" + digest.hexdigest()


def collect_origins(value: Any, output: set[tuple[str, str, int]]) -> None:
    if isinstance(value, dict):
        rid = value.get("record_id")
        if isinstance(rid, str) and "_N8_O" in rid:
            parts = rid.split("_")
            output.add(("_".join(parts[:2]), "_".join(parts[2:4]), int(parts[-1][1:])))
        for child in value.values(): collect_origins(child, output)
    elif isinstance(value, list):
        for child in value: collect_origins(child, output)


def group_map() -> dict[str, list[dict[str, Any]]]:
    # Reuse the already qualified complete/unique tensor partition, but copy its
    # content into a new Stage 06 identity rather than importing weights.
    source = json.loads((STAGE05CQ / "parameter_groups/preregistered_parameter_groups.json").read_text())
    return source["groups"]


def main() -> None:
    stage05b = json.loads((STAGE05 / "09_manifests/stage05b_final_manifest.json").read_text())
    stage05c = json.loads((STAGE05 / "09_manifests/stage05c_final_manifest.json").read_text())
    stage05cr = json.loads((STAGE05CR / "manifests/stage05cr_final_manifest.json").read_text())
    stage05cq = json.loads((STAGE05 / "09_manifests/stage05cq_final_manifest.json").read_text())
    assert stage05b["status"] == "CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED"
    assert stage05c["terminal_status"] == "OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED"
    assert stage05cr["stage05cr_status"] == "DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE"
    assert not stage05cr["stage05cp_started"] and not stage05cr["stage05d_authorized"]
    assert stage05cq["terminal_status"] == "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED"
    assert not stage05cq["stage05d_authorized"]

    groups = group_map()
    group_path = STAGE06 / "01_update_map_qualification/optimizer_definition/parameter_groups.json"
    write_json(group_path, {"schema": "sph-pio-poc.stage06a.parameter-groups.v1", "groups": groups,
                            "unique_complete_coverage": True})

    models = []
    for arm, cls in ARMS.items():
        for seed in SEEDS:
            torch.manual_seed(seed)
            model = cls().to(dtype=torch.float64, device="cpu")
            schema = [{"name": name, "shape": list(parameter.shape), "count": parameter.numel()}
                      for name, parameter in model.named_parameters()]
            models.append({"arm": arm, "seed": seed, "complete_parameter_sha256": parameter_hash(model),
                           "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                           "parameter_schema_sha256": sha_bytes(canonical(schema)),
                           "backend": "CPU_FLOAT64_SDPBackend.MATH", "historical_weight_reads": 0})
            del model
    model_path = STAGE06 / "01_update_map_qualification/blind_models/preregistered_model_identities.json"
    write_json(model_path, {"schema": "sph-pio-poc.stage06a.models.v1", "seeds": SEEDS, "models": models,
                            "fresh_initialization": True, "historical_weight_reads": 0,
                            "future_formal_seed_namespace": FUTURE_FORMAL_SEED_NAMESPACE,
                            "qualification_weights_must_be_destroyed": True})

    old_c = json.loads((STAGE05C / "batch_selection/preregistered_batches.json").read_text())
    old_q = json.loads((STAGE05CQ / "blind_origin_selection/preregistered_blind_origins.json").read_text())
    excluded: dict[tuple[str, str], set[int]] = {(lineage, variant): set() for lineage in LINEAGES for variant in VARIANTS}
    for manifest, label in ((old_c, "stage05c"), (old_q, "stage05cq")):
        for row in manifest["selection"]:
            excluded[(row["lineage"], row["variant"])].update(row["origins"])
    r_origins: set[tuple[str, str, int]] = set()
    reconstruction = STAGE05CR / "failed_probe_reconstruction/original_failed_probe_reconstruction.json"
    if reconstruction.exists(): collect_origins(json.loads(reconstruction.read_text()), r_origins)
    for lineage, variant, origin in r_origins: excluded[(lineage, variant)].add(origin)

    selection = []
    for lineage in LINEAGES:
        for variant in VARIANTS:
            ranked = sorted((hashlib.sha256(("stage06a_blind_origin_v1" + lineage + variant + str(origin)).encode()).hexdigest(), origin)
                            for origin in range(32) if origin not in excluded[(lineage, variant)])
            if len(ranked) < 8:
                raise RuntimeError("EVIDENCE_INCOMPLETE: fewer than eight unused origins")
            chosen = ranked[:8]
            selection.append({"lineage": lineage, "variant": variant, "origins": [origin for _, origin in chosen],
                              "selection_keys": ["sha256:" + key for key, _ in chosen],
                              "excluded_historical_origins": sorted(excluded[(lineage, variant)]),
                              "available_unused_origin_count": len(ranked), "historical_overlap_count": 0})
    origin_path = STAGE06 / "01_update_map_qualification/blind_batches/preregistered_blind_origins.json"
    write_json(origin_path, {"schema": "sph-pio-poc.stage06a.blind-origins.v1", "salt": "stage06a_blind_origin_v1",
                             "selection": selection, "origins_per_variant": 8, "lineage_batch_size": 16,
                             "global_batch_size": 96, "historical_origin_overlap_count": 0,
                             "stage05cr_referenced_origins": sorted([list(row) for row in r_origins])})

    # Fixed hash coordinate/block diagnostic plan. This boundary cannot qualify
    # complete coordinate/block FD coverage.
    probe_contexts = []
    for arm, arm_groups in groups.items():
        for group in arm_groups:
            count = group["element_count"]
            for seed in SEEDS:
                for lineage in LINEAGES:
                    coordinates, used = [], set()
                    for slot in range(2):
                        key = hashlib.sha256(("stage06a_coordinate_v1" + arm + group["group"] + str(seed) + lineage + str(slot)).encode()).hexdigest()
                        index = int(key[:16], 16) % count
                        while index in used: index = (index + 1) % count
                        used.add(index); coordinates.append({"slot": slot, "group_flat_index": index, "key": "sha256:" + key})
                    blocks, starts = [], set(); size = min(32, count)
                    for slot in range(2):
                        key = hashlib.sha256(("stage06a_block_v1" + arm + group["group"] + str(seed) + lineage + str(slot)).encode()).hexdigest()
                        start = int(key[:16], 16) % count
                        while start in starts: start = (start + 1) % count
                        starts.add(start); indices = [(start + i) % count for i in range(size)]
                        raw = b""; counter = 0
                        while len(raw) * 8 < size:
                            raw += hashlib.sha256(bytes.fromhex(key) + counter.to_bytes(8, "big")).digest(); counter += 1
                        signs = (2 * np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:size].astype(int) - 1).tolist()
                        blocks.append({"slot": slot, "start": start, "indices": indices, "rademacher_signs": signs,
                                       "key": "sha256:" + key, "l2_normalization": f"sqrt({size})"})
                    probe_contexts.append({"arm": arm, "group": group["group"], "seed": seed, "lineage": lineage,
                                           "coordinates": coordinates, "blocks": blocks})
    probe_path = STAGE06 / "01_update_map_qualification/coordinate_fd_boundary/preregistered_diagnostic_plan.json"
    write_json(probe_path, {"schema": "sph-pio-poc.stage06a.coordinate-boundary.v1", "contexts": probe_contexts,
                            "coordinates_per_group_context": 2, "blocks_per_group_context": 2,
                            "diagnostic_only": True, "complete_coordinate_fd_qualification": False})

    contract = {
        "contract_id": "actual_optimizer_update_dynamics_contract_v0_1",
        "schema": "sph-pio-poc.stage06a.contract.v1",
        "stage_nature": {"user_authorized_new_hypothesis": True, "formal_training": False,
                         "preserve_stage05_failures": True, "qualification_weights_disposable": True},
        "backend": {"device": "CPU", "dtype": "float64", "sdpa": "SDPBackend.MATH"},
        "models": {"seeds": SEEDS, "manifest": str(model_path.relative_to(ROOT)), "historical_weight_reads": 0,
                   "future_formal_seed_namespace": FUTURE_FORMAL_SEED_NAMESPACE},
        "blind_batches": {"manifest": str(origin_path.relative_to(ROOT)), "salt": "stage06a_blind_origin_v1",
                          "lineage_batch": "2 variants x 8 origins", "global_batch": 96, "historical_overlap": 0},
        "optimizer": {"family": "AdamW", "betas": [.9, .999], "eps": 1e-12, "weight_decay": 0,
                      "amsgrad": False, "global_gradient_clip_L2": 1.0,
                      "state_starts_at_zero_per_independent_clone": True},
        "loss": {"identity": "balanced mean ||(a_eff_theta-a_cons_star)/s_a||^2",
                 "s_a": 3.45632855338432798e-1, "target_balancing_RK2_unchanged": True},
        "learning_rate_ladder": LRS,
        "learning_rate_policy": {"qualification_only": True, "formal_lr_selection": False,
                                 "fresh_clone_same_initial_parameters_same_batch_each_lr": True},
        "update_horizons": [1, 2, 4],
        "gradient_update_gates": {"finite_active_gradient": True, "finite_effective_update": True,
                                  "cosine_update_negative_gradient_min_exclusive": 0,
                                  "parameter_relative_update_max_exclusive": 1e-2,
                                  "all_parameter_groups_required": True, "deterministic_repeat": True},
        "one_step_gates": {"delta_loss": "< -100*u_L", "u_L": "max(repeat loss difference,128*eps_float64*max(1,abs(L_before)))",
                           "adjacent_lr_pass_count_min": 2, "density_positive": True,
                           "correction_force_residual_max": 1e-10, "topology_unchanged": True,
                           "parameter_relative_update_max_exclusive": 1e-2, "optimizer_state_finite": True},
        "micro_update_gates": {"loss_1_lt_loss_0": True, "loss_2_le_loss_1_plus_floor": True,
                               "loss_4_le_loss_2_plus_floor": True, "step4_relative_reduction_min": 1e-4,
                               "single_step_relative_increase_max": 1e-3, "parameter_relative_displacement_max": 5e-2,
                               "gradient_update_explosion_forbidden": True, "structure_safety_required": True},
        "aggregation": {"arm_lineage_seed": "two adjacent one-step LRs and at least one micro-update LR",
                        "arm_lineage": "at least 2/3 seeds", "arm": "6/6 lineages", "global": "3/3 seeds",
                        "overall": "D1,D2,D3 all pass"},
        "actual_update_fd": {"direction": "effective AdamW update vector at smallest algorithmic passing LR",
                             "scales": FD_SCALES, "central": True, "two_adjacent_sign_stable_required": True,
                             "reverse_fd_sign_consistency": True, "one_step_local_prediction_consistency": True},
        "coordinate_fd_boundary": {"manifest": str(probe_path.relative_to(ROOT)), "diagnostic_only": True,
                                   "per_group": "2 hash coordinates + 2 hash blocks",
                                   "fd_window_missing_allowed": True,
                                   "hard_failures": ["reverse/JVP contradiction", "sign contradiction", "mapping contradiction", "nondeterminism", "safety failure"],
                                   "complete_coverage_claim_forbidden": True},
        "structure_safety": {"force_residual_max": 1e-10, "positive_density": True,
                             "transforms": ["permutation", "edge_reorder", "translation", "Galilean", "SO(2)", "reflection", "periodic_shift"],
                             "accepted_commit": 1, "midpoint_commit": 0, "moments_finite": True},
        "access": {"TRAIN_only": LINEAGES, "validation": ["LCDF_02", "LCDF_09"], "sealed_test": ["LCDF_03", "LCDF_10"],
                   "validation_decode_count_required": 0, "sealed_decode_count_required": 0},
        "resources": {"peak_rss_delta_max_bytes": 1610612736, "no_monotonic_retained_autograd": True,
                      "dense_particle_N_by_N_forbidden": True, "finite_completion": True, "all_models_destroyed": True},
        "prohibitions": {"formal_training_runs": 0, "saved_training_checkpoints": 0, "validation_evaluations": 0,
                         "sealed_test_evaluations": 0, "optimizer_or_lr_selection_for_training": False,
                         "neural_rollout": False, "arm_ranking": False},
        "terminal_statuses": ["ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED",
                              "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_NOT_QUALIFIED",
                              "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_EVIDENCE_INCOMPLETE"],
    }
    contract_path = STAGE06 / "01_update_map_qualification/contracts/actual_optimizer_update_dynamics_contract_v0_1.yaml"
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding="utf-8")

    key_inputs = [
        STAGE05 / "09_manifests/stage05a_contract_manifest.json",
        STAGE05 / "09_manifests/stage05a_final_manifest.json",
        STAGE05 / "09_manifests/stage05b_target_manifest.json",
        STAGE05 / "09_manifests/stage05b_scale_manifest.json",
        STAGE05 / "09_manifests/stage05b_uncertainty_manifest.json",
        STAGE05 / "09_manifests/stage05c_final_manifest.json",
        STAGE05CR / "manifests/stage05cr_final_manifest.json",
        STAGE05 / "09_manifests/stage05cq_final_manifest.json",
        ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_lineage_manifest.json",
        ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json",
    ] + sorted(STAGE03C.rglob("*.py"))
    target_manifest = json.loads((STAGE05 / "09_manifests/stage05b_target_manifest.json").read_text())
    assert target_manifest["record_count"] == 384
    historical_roots = [ROOT / "stage_01_verification", ROOT / "stage_02_Particle_Interaction_Operator",
                        ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid", ROOT / "stage_04_Local_Causal_Dynamic_Training",
                        ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training"]
    historical = []
    unreadable_private = []
    for base in historical_roots:
        for path in sorted(p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            relative = str(path.relative_to(ROOT))
            try:
                historical.append({"path": relative, "sha256": sha_file(path), "size_bytes": path.stat().st_size})
            except PermissionError:
                # Private validation/sealed payloads must not be opened. Their
                # identities are frozen transitively by the readable Stage 04B
                # seal manifests above.
                unreadable_private.append({"path": relative, "payload_read": False,
                                           "permission_denied": True, "size_bytes": path.stat().st_size})
    input_freeze = {
        "schema": "sph-pio-poc.stage06a.input-freeze.v1",
        "contract_path": str(contract_path.relative_to(ROOT)), "contract_sha256": sha_file(contract_path),
        "frozen_before_first_blind_target_decode": True, "blind_target_decode_count_at_freeze": 0,
        "key_inputs": [{"path": str(path.relative_to(ROOT)), "sha256": sha_file(path), "size_bytes": path.stat().st_size} for path in key_inputs],
        "target_record_count": target_manifest["record_count"],
        "target_manifest_record_identities": [{"record_id": row["record_id"], "npz_sha256": row["npz_sha256"],
                                                "json_sha256": row["json_sha256"]} for row in target_manifest["records"]],
        "historical_artifact_count": len(historical) + len(unreadable_private), "historical_artifacts": historical,
        "unreadable_private_artifacts": unreadable_private,
        "historical_files_modified": 0,
    }
    freeze_path = STAGE06 / "01_update_map_qualification/freeze/stage06a_freeze_record.json"
    write_json(freeze_path, input_freeze)
    write_json(STAGE06 / "09_manifests/stage06a_input_freeze_manifest.json", input_freeze)
    contract_manifest = {"schema": "sph-pio-poc.stage06a.contract-manifest.v1",
                         "path": str(contract_path.relative_to(ROOT)), "sha256": sha_file(contract_path),
                         "frozen": True, "modification_after_freeze_forbidden": True}
    write_json(STAGE06 / "09_manifests/stage06a_contract_manifest.json", contract_manifest)
    write_json(STAGE06 / "09_manifests/stage06a_model_manifest.json", json.loads(model_path.read_text()))
    write_json(STAGE06 / "09_manifests/stage06a_batch_manifest.json", json.loads(origin_path.read_text()))
    write_json(STAGE06 / "09_manifests/stage06a_optimizer_manifest.json", {
        "schema": "sph-pio-poc.stage06a.optimizer.v1", "family": "AdamW", "betas": [.9, .999], "eps": 1e-12,
        "weight_decay": 0, "amsgrad": False, "gradient_clip_L2": 1.0, "learning_rate_ladder": LRS,
        "formal_optimizer_selected": False, "formal_learning_rate_selected": False})
    print(json.dumps({"contract_sha256": sha_file(contract_path), "models": len(models), "blind_cases": 96,
                      "probe_contexts": len(probe_contexts), "historical_origin_overlap": 0,
                      "historical_artifacts_frozen": len(historical)}))


if __name__ == "__main__":
    main()
