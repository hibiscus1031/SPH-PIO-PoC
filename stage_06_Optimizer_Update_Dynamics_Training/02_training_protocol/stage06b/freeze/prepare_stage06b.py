"""Freeze the complete Stage 06B protocol before VALIDATION payload decode."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import stat
import sys
from typing import Any

import numpy as np
import torch
import yaml

HERE = Path(__file__).resolve()
STAGE06B = HERE.parents[1]
STAGE06 = HERE.parents[3]
ROOT = HERE.parents[4]
Q06A = STAGE06 / "01_update_map_qualification"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO

ARMS = ["D1", "D2", "D3"]
QUALIFICATION_SEEDS = [20600601, 20600602, 20600603]
FORMAL_SEEDS = [20600611, 20600612, 20600613]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
VARIANTS = ["VARIANT_LOW", "VARIANT_MAIN"]
LRS = [1e-5, 3e-5, 1e-4, 3e-4, 1e-3]
MODELS = {"D1": D1InstantaneousPairMLP, "D2": D2CausalRecurrentPairPIO, "D3": D3CausalTemporalTransformerPIO}


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


def load_contexts() -> dict[str, dict[int, dict[str, dict[str, Any]]]]:
    result = {}
    for arm in ARMS:
        result[arm] = {}
        for seed in QUALIFICATION_SEEDS:
            result[arm][seed] = {}
            for context in [*LINEAGES, "GLOBAL"]:
                path = Q06A / f"results/{arm.lower()}/{arm}_{seed}_{context}.json"
                result[arm][seed][context] = json.loads(path.read_text())
    return result


def lr_matrix(contexts: dict[str, dict[int, dict[str, dict[str, Any]]]]) -> dict[str, Any]:
    matrix = []
    for lr in LRS:
        rows = []
        for arm in ARMS:
            for seed in QUALIFICATION_SEEDS:
                for context in [*LINEAGES, "GLOBAL"]:
                    result = contexts[arm][seed][context]
                    one = next(row for row in result["one_step_learning_rates"] if row["learning_rate"] == lr)
                    micro = next((row for row in result["micro_updates"] if row["learning_rate"] == lr), None)
                    actual = result["actual_update_FD"]
                    actual_at_candidate = actual is not None and actual["learning_rate"] == lr and actual["pass"]
                    structure = (one["topology_unchanged"] and one["safety_before"] and one["safety_after"]
                                 and one["density_positive"] and one["correction_force_residual_max"] <= 1e-10)
                    if context != "GLOBAL":
                        structure = structure and actual["structure_audit"] is not None and actual["structure_audit"]["pass"]
                    passed = one["pass"] and actual_at_candidate and micro is not None and micro["pass"] and structure
                    rows.append({"arm": arm, "qualification_seed": seed, "context": context,
                                 "one_step_pass": one["pass"], "actual_update_FD_pass_at_candidate_LR": actual_at_candidate,
                                 "actual_update_FD_evidence_LR": actual["learning_rate"] if actual else None,
                                 "micro_update_path_pass": micro is not None and micro["pass"],
                                 "structure_safety_pass": structure, "pass": bool(passed)})
        matrix.append({"learning_rate": lr, "contexts": rows, "pass_count": sum(row["pass"] for row in rows),
                       "required_context_count": 63, "fully_qualified": all(row["pass"] for row in rows)})
    common = [row["learning_rate"] for row in matrix if row["fully_qualified"]]
    selected = max(common) if common else None
    return {"schema": "sph-pio-poc.stage06b.formal-lr-selection.v1", "candidate_learning_rates": LRS,
            "definition": "candidate passes only with one-step, candidate-LR actual-update FD, candidate-LR micro-update, and structure/safety PASS in all 63 TRAIN-only contexts",
            "matrix": matrix, "common_fully_qualified_LR_set": common, "selected_formal_learning_rate": selected,
            "selection_rule": "maximum(common_fully_qualified_LR_set)", "validation_reads": 0,
            "per_arm_learning_rate_forbidden": True, "manual_selection": False,
            "pass": selected is not None}


def batch_schedule() -> dict[str, Any]:
    base = [{"base_batch_id": f"B{index:02d}", "records": []} for index in range(8)]
    assignment = []
    for lineage in LINEAGES:
        for variant in VARIANTS:
            ranked = sorted((hashlib.sha256(("stage06b_train_batch_v1" + lineage + variant + str(origin)).encode()).hexdigest(), origin)
                            for origin in range(32))
            for batch_index in range(8):
                group = ranked[4*batch_index:4*(batch_index+1)]
                for key, origin in group:
                    record_id = f"{lineage}_{variant}_N8_O{origin:02d}"
                    row = {"record_id": record_id, "lineage": lineage, "variant": variant, "origin": origin,
                           "assignment_key": "sha256:" + key}
                    base[batch_index]["records"].append(row); assignment.append({**row, "base_batch_id": f"B{batch_index:02d}"})
    for batch in base:
        batch["record_count"] = len(batch["records"])
        batch["lineage_counts"] = {lineage: sum(row["lineage"] == lineage for row in batch["records"]) for lineage in LINEAGES}
        batch["variant_counts"] = {variant: sum(row["variant"] == variant for row in batch["records"]) for variant in VARIANTS}
        batch["record_ids_sha256"] = sha_bytes(canonical([row["record_id"] for row in batch["records"]]))
    orders = []; updates = []
    update = 0
    for arm in ARMS:
        for seed in FORMAL_SEEDS:
            run_id = f"{arm}_seed{seed}"
            for epoch in range(188):
                rows = sorted((hashlib.sha256(("stage06b_batch_order_v1" + arm + str(seed) + str(epoch) + batch["base_batch_id"]).encode()).hexdigest(),
                               batch["base_batch_id"]) for batch in base)
                order = [batch_id for _, batch_id in rows]
                orders.append({"run_id": run_id, "epoch": epoch, "base_batch_order": order,
                               "order_keys": ["sha256:" + key for key, _ in rows]})
    # A separate update map makes the 1500-update truncation explicit.
    for arm in ARMS:
        for seed in FORMAL_SEEDS:
            run_id = f"{arm}_seed{seed}"; run_update = 0
            run_orders = [row for row in orders if row["run_id"] == run_id]
            for row in run_orders:
                for batch_id in row["base_batch_order"]:
                    if run_update >= 1500: break
                    run_update += 1
                    updates.append({"run_id": run_id, "update": run_update, "epoch": row["epoch"], "base_batch_id": batch_id})
                if run_update >= 1500: break
            assert run_update == 1500
    ids = [row["record_id"] for row in assignment]
    complete = (len(ids) == 384 and len(set(ids)) == 384 and all(batch["record_count"] == 48 for batch in base)
                and all(all(value == 8 for value in batch["lineage_counts"].values()) for batch in base)
                and all(all(value == 24 for value in batch["variant_counts"].values()) for batch in base))
    return {"schema": "sph-pio-poc.stage06b.train-batch-schedule.v1", "salt": "stage06b_train_batch_v1",
            "order_salt": "stage06b_batch_order_v1", "record_count": len(ids), "base_batch_count": 8,
            "updates_per_epoch": 8, "max_updates": 1500, "epochs_required": 187.5,
            "base_batches": base, "assignments": assignment, "epoch_orders": orders,
            "update_schedule": updates, "random_augmentation": False, "pass": complete}


def scheduler_values(selected_lr: float) -> list[dict[str, Any]]:
    rows = []
    for update in range(1501):
        if update <= 40:
            factor = .1 + .9 * update / 40
            phase = "linear_warmup"
        else:
            progress = (update - 40) / (1500 - 40)
            factor = .1 + .9 * .5 * (1 + math.cos(math.pi * progress))
            phase = "cosine_decay"
        value = selected_lr * factor
        rows.append({"update": update, "learning_rate": value, "factor": factor, "phase": phase,
                     "subqualification_decay_only": value < min(LRS)})
    return rows


def model_identities() -> tuple[list[dict[str, Any]], dict[str, str]]:
    stage06a_models = json.loads((Q06A / "blind_models/preregistered_model_identities.json").read_text())["models"]
    architecture = {}
    for arm in ARMS:
        hashes = {row["parameter_schema_sha256"] for row in stage06a_models if row["arm"] == arm}
        assert len(hashes) == 1; architecture[arm] = next(iter(hashes))
    rows = []
    for arm in ARMS:
        for seed in FORMAL_SEEDS:
            torch.manual_seed(seed); model = MODELS[arm]().to(dtype=torch.float64, device="cpu")
            rows.append({"run_id": f"{arm}_seed{seed}", "arm": arm, "formal_seed": seed,
                         "architecture_sha256": architecture[arm], "initial_parameter_sha256": parameter_hash(model),
                         "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                         "backend": "CPU_FLOAT64_SDPBackend.MATH", "historical_weight_reads": 0,
                         "qualification_weight_reads": 0})
            del model
    return rows, architecture


def main() -> None:
    final06a = json.loads((STAGE06 / "09_manifests/stage06a_final_manifest.json").read_text())
    assert final06a["terminal_status"] == "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED"
    assert final06a["stage06b_authorized"] and final06a["contract_unchanged"]
    contexts = load_contexts(); selection = lr_matrix(contexts)
    write_json(STAGE06B / "lr_selection/formal_lr_selection_matrix.json", selection)
    if not selection["pass"]:
        raise SystemExit("FORMAL_TRAINING_PROTOCOL_NOT_READY: common LR set empty")
    formal_lr = selection["selected_formal_learning_rate"]
    batches = batch_schedule(); assert batches["pass"]
    batch_path = STAGE06B / "train_batch_schedule/formal_train_batch_schedule.json"; write_json(batch_path, batches)
    model_rows, architecture = model_identities()
    scheduler = scheduler_values(formal_lr)
    scheduler_path = STAGE06B / "optimizer_schedule/formal_scheduler_values.json"
    write_json(scheduler_path, {"schema": "sph-pio-poc.stage06b.scheduler-values.v1", "rows": scheduler,
                                "values_sha256": sha_bytes(canonical(scheduler)), "minimum": min(row["learning_rate"] for row in scheduler),
                                "maximum": max(row["learning_rate"] for row in scheduler),
                                "subqualification_decay_only": True})
    checkpoint_policy = {
        "save": {"update_0_identity": True, "interval_updates": 20, "terminal": True, "selected": True},
        "selection_metric": "validation.global_balanced_Q_def", "selection_rule": "minimum",
        "tie_break": "earlier_update", "minimum_selectable_update": 320,
        "pre_320_results_recorded_but_not_selectable": True, "sealed_test_participates": False,
        "payload": ["model", "optimizer", "scheduler", "RNG", "update", "protocol_hash", "run_identity"],
    }
    success_gates = {
        "A_numerical_safety": ["no NaN/Inf", "positive density", "finite hidden/coefficient", "deterministic evaluation"],
        "B_train_global_Q_def_max": .50, "C_validation_global_Q_def_max": .90,
        "D_validation_lineage_Q_def_max": {"LCDF_02": 1., "LCDF_09": 1.},
        "E_structure": ["correction force residual <=1e-10", "permutation", "edge reorder", "translation", "Galilean", "SO(2)", "reflection", "periodic shift", "history semantics"],
        "seed_pass": "A+B+C+D+E", "arm_pass": "at least 2/3 seeds", "transformer_route": "D3 arm PASS",
        "D1_D2_completion_required": True, "D1_D2_pass_required_for_sealed_test": False,
    }
    protocol = {
        "contract_id": "formal_k1_defect_training_protocol_v0_1", "schema": "sph-pio-poc.stage06b.protocol.v1",
        "authorization": {"source": "Stage06A", "status": "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED",
                          "stage06b_only": True, "formal_training_authorized_in_stage06b": False},
        "backend": {"device": "CPU", "dtype": "float64", "sdpa": "SDPBackend.MATH"},
        "data_roles": {"TRAIN": LINEAGES, "VALIDATION": ["LCDF_02", "LCDF_09"], "SEALED_TEST": ["LCDF_03", "LCDF_10"],
                       "split_atom": "complete formula lineage component", "random_subsplit_forbidden": True},
        "formal_models": {"seeds": FORMAL_SEEDS, "qualification_seeds_excluded": QUALIFICATION_SEEDS,
                          "run_ids": [row["run_id"] for row in model_rows], "architecture_hashes": architecture,
                          "fresh_initialization": True, "historical_or_qualification_weight_reads": 0},
        "optimizer": {"family": "AdamW", "betas": [.9, .999], "eps": 1e-12, "weight_decay": 0,
                      "amsgrad": False, "global_gradient_clip": 1.0, "arm_specific_family": False},
        "formal_learning_rate": {"candidates": LRS, "selection_matrix": str((STAGE06B / "lr_selection/formal_lr_selection_matrix.json").relative_to(ROOT)),
                                 "algorithm": "maximum(common_fully_qualified_LR_set)", "selected": formal_lr,
                                 "validation_used": False},
        "training_batches": {"manifest": str(batch_path.relative_to(ROOT)), "all_384_origins": True,
                             "base_batches": 8, "origins_per_batch": 48, "updates_per_epoch": 8,
                             "assignment_salt": "stage06b_train_batch_v1", "order_salt": "stage06b_batch_order_v1",
                             "random_augmentation": False},
        "budget": {"max_updates": 1500, "minimum_updates": 320, "epochs": 187.5,
                   "validation_interval": 20, "checkpoint_interval": 20},
        "scheduler": {"warmup_updates": 40, "warmup_start_factor": .1, "warmup_end_factor": 1.,
                      "post_warmup": "cosine", "terminal_factor": .1, "terminal_update": 1500,
                      "values_manifest": str(scheduler_path.relative_to(ROOT)),
                      "subqualification_decay_only": True,
                      "subqualification_note": "warmup and cosine tail below 1e-5 are schedule-only and create no gradient-qualification claim"},
        "loss": {"identity": "balanced mean ||(a_eff_theta-a_cons_star)/s_a||^2",
                 "s_a": 3.45632855338432798e-1, "target": "a_cons_star", "complete_RK2": True,
                 "D0_centered_accepted_velocity_defect": True, "no_auxiliary_penalty": True, "target_in_token": False},
        "metrics": {"Q_def": "sqrt(L_def)", "zero_correction_baseline": 1.,
                    "train": ["global balanced", "per lineage", "per variant", "maximum origin"],
                    "validation": ["global balanced", "LCDF_02", "LCDF_09", "per variant", "maximum origin", "zero baseline identity"],
                    "diagnostic_only": ["accepted velocity", "position", "density", "coefficient RMS/saturation", "correction force residual"]},
        "validation": {"open_only_after_protocol_hash": True, "record_count": 128,
                       "construction": "Stage05B D0/reference/defect/conservative schema with frozen TRAIN s_a",
                       "cadence_updates": list(range(20, 1501, 20)), "hyperparameter_feedback": False,
                       "hard_origin_deletion": False},
        "early_stopping": {"enabled_at_update": 320, "patience_updates": 300,
                           "minimum_Q_def_improvement": 1e-5, "terminal_label": "EARLY_STOPPED",
                           "budget_extension_forbidden": True},
        "checkpoint_policy": checkpoint_policy, "success_gates": success_gates,
        "retry_policy": {"scientific_retry": False, "failed_run_replacement": False, "budget_increase": False,
                         "infrastructure_resume_max": 2, "resume_requires_exact_checkpoint_RNG_optimizer_scheduler_protocol_identity": True,
                         "unrecoverable_interruption_status": "FORMAL_K1_TRAINING_EVIDENCE_INCOMPLETE"},
        "resource_limits": {"peak_RSS_bytes": 1610612736, "checkpoint_storage_bytes": 10 * 1024**3,
                            "budget_reduction_on_forecast_failure": False},
        "sealed_test_release": {"stage06b_decode": False, "required_prior_status": "FORMAL_K1_TRANSFORMER_TRAINING_QUALIFIED",
                                "selected_checkpoints_frozen": True, "explicit_stage06d_authorization": True,
                                "one_time_evaluation": True},
        "stage06c_terminal_statuses": ["FORMAL_K1_TRANSFORMER_TRAINING_QUALIFIED",
                                       "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
                                       "FORMAL_K1_TRAINING_EVIDENCE_INCOMPLETE"],
        "prohibitions": {"formal_optimizer_steps": 0, "formal_parameter_updates": 0, "formal_training_runs": 0,
                         "sealed_test_evaluations": 0, "rollouts": 0, "performance_evaluations": 0,
                         "validation_derived_changes": False, "model_ranking": False},
    }
    contract_path = STAGE06B / "contracts/formal_k1_defect_training_protocol_v0_1.yaml"
    contract_path.write_text(yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True), encoding="utf-8")
    protocol_hash = sha_file(contract_path)
    for row in model_rows:
        row.update({"protocol_sha256": protocol_hash, "formal_learning_rate": formal_lr,
                    "batch_manifest_sha256": sha_file(batch_path), "target_manifest_sha256": sha_file(ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json"),
                    "scale_sha256": sha_file(ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_scale_manifest.json"),
                    "optimizer_config": protocol["optimizer"],
                    "run_identity_sha256": sha_bytes(canonical({"run_id": row["run_id"], "architecture": row["architecture_sha256"],
                                                                 "seed": row["formal_seed"], "backend": row["backend"],
                                                                 "protocol": protocol_hash}))})
    model_manifest = {"schema": "sph-pio-poc.stage06b.formal-model-seeds.v1", "formal_seeds": FORMAL_SEEDS,
                      "run_count": len(model_rows), "runs": model_rows, "pass": len(model_rows) == 9}
    write_json(STAGE06B / "model_seed_schedule/formal_model_seed_schedule.json", model_manifest)
    protocol_manifest = {"schema": "sph-pio-poc.stage06b.protocol-manifest.v1", "protocol_path": str(contract_path.relative_to(ROOT)),
                         "protocol_sha256": protocol_hash, "frozen_before_validation_decode": True,
                         "validation_decode_count_at_freeze": 0, "immutable": True, "selected_formal_learning_rate": formal_lr}
    write_json(STAGE06B / "manifests/stage06b_protocol_manifest.json", protocol_manifest)
    write_json(STAGE06B / "checkpoint_policy/checkpoint_policy.json", checkpoint_policy)
    write_json(STAGE06B / "success_gates/formal_success_gates.json", success_gates)

    # Verify the exact Stage 01-05 and Stage 06A snapshots without opening any
    # validation/sealed payload that was unreadable at Stage 06A freeze.
    freeze06a = json.loads((Q06A / "freeze/stage06a_freeze_record.json").read_text())
    changed = []
    for row in freeze06a["historical_artifacts"]:
        path = ROOT / row["path"]
        if not path.exists() or sha_file(path) != row["sha256"]: changed.append(row["path"])
    final06a_path = STAGE06 / "09_manifests/stage06a_final_manifest.json"
    for row in final06a["artifacts"]:
        path = ROOT / row["path"]
        if not path.exists() or sha_file(path) != row["sha256"]: changed.append(row["path"])
    private = []
    for row in freeze06a.get("unreadable_private_artifacts", []):
        path = ROOT / row["path"]
        private.append({"path": row["path"], "size_bytes": path.stat().st_size,
                        "posix_mode": stat.S_IMODE(path.stat().st_mode), "payload_read": False})
    input_freeze = {"schema": "sph-pio-poc.stage06b.input-freeze.v1", "authorization_status": final06a["terminal_status"],
                    "stage06a_final_manifest_sha256": sha_file(final06a_path), "protocol_sha256": protocol_hash,
                    "protocol_frozen_before_validation_decode": True, "validation_decode_count_at_freeze": 0,
                    "stage01_05_artifact_count": len(freeze06a["historical_artifacts"]),
                    "stage06a_artifact_count": len(final06a["artifacts"]) + 1,
                    "historical_files_changed": changed, "unreadable_private_artifacts": private,
                    "stage05c_failure_hashes": final06a["stage05c_failure_hashes_preserved"],
                    "stage05cq_failure_hashes": final06a["stage05cq_failure_hashes_preserved"],
                    "historical_statuses": {"Stage05C": "OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED",
                                            "Stage05C-R": "DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE",
                                            "Stage05C-Q": "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED",
                                            "coordinate_block_coverage": "NOT_QUALIFIED",
                                            "Stage06A": "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED"},
                    "pass": not changed}
    write_json(STAGE06B / "freeze/stage06b_freeze_record.json", input_freeze)

    top = STAGE06 / "09_manifests"
    write_json(top / "stage06b_input_freeze_manifest.json", input_freeze)
    write_json(top / "stage06b_protocol_manifest.json", protocol_manifest)
    write_json(top / "stage06b_batch_manifest.json", batches)
    write_json(top / "stage06b_model_seed_manifest.json", model_manifest)
    write_json(top / "stage06b_checkpoint_policy_manifest.json", {"schema": "sph-pio-poc.stage06b.checkpoint-policy-manifest.v1",
                                                                   "protocol_sha256": protocol_hash, **checkpoint_policy})
    print(json.dumps({"protocol_sha256": protocol_hash, "selected_formal_learning_rate": formal_lr,
                      "common_set": selection["common_fully_qualified_LR_set"], "runs": len(model_rows),
                      "train_records": batches["record_count"], "historical_changes": len(changed),
                      "validation_decode_count": 0}))


if __name__ == "__main__": main()
