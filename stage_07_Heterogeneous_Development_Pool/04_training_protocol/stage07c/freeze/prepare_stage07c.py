"""Freeze Stage07C protocol before any fresh-validation private payload decode."""

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
C = HERE.parents[1]
STAGE07 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE07B = STAGE07 / "02_defect_scale_requalification/stage07b"
STAGE06 = ROOT / "stage_06_Optimizer_Update_Dynamics_Training"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO


ARMS = ["D1", "D2", "D3"]
SEEDS = [20700711, 20700712, 20700713]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08",
            "HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03",
            "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
FRESH = ["HET_S1_01", "HET_S2_02", "HET_S3_03", "HET_S4_03"]
VARIANTS = ["LOW", "MAIN"]
MODELS = {"D1": D1InstantaneousPairMLP, "D2": D2CausalRecurrentPairPIO, "D3": D3CausalTemporalTransformerPIO}
S_A_V2 = 1.7254786448147168
SCALE_HASH = "sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b"
RESOURCE_GATE = 1610612736


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def tensor_bytes(value: torch.Tensor) -> bytes:
    array = value.detach().contiguous().cpu().numpy()
    return str(array.dtype).encode() + b"\0" + np.asarray(array.shape, dtype=np.int64).tobytes() + array.tobytes()


def parameter_hash(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, parameter in model.named_parameters():
        digest.update(name.encode()); digest.update(tensor_bytes(parameter))
    return "sha256:" + digest.hexdigest()


def schema_hash(model: torch.nn.Module) -> str:
    rows = [{"name": name, "shape": list(parameter.shape), "dtype": str(parameter.dtype)}
            for name, parameter in model.named_parameters()]
    return sha_bytes(canonical(rows))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def entry(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha_file(path), "bytes": path.stat().st_size}


def batch_schedule() -> dict[str, Any]:
    batches = [{"base_batch_id": f"B{index:02d}", "records": []} for index in range(8)]
    assignments = []
    for lineage in LINEAGES:
        for variant in VARIANTS:
            ranked = sorted((hashlib.sha256(("stage07c_train_batch_v1" + lineage + variant + str(origin)).encode()).hexdigest(), origin)
                            for origin in range(32))
            for batch_index in range(8):
                for key, origin in ranked[4 * batch_index:4 * (batch_index + 1)]:
                    record_id = f"{lineage}_{variant}_N8_O{origin:02d}"
                    row = {"record_id": record_id, "lineage": lineage, "variant": variant, "origin": origin,
                           "assignment_key": "sha256:" + key, "base_batch_id": f"B{batch_index:02d}"}
                    assignments.append(row); batches[batch_index]["records"].append({k: row[k] for k in row if k != "base_batch_id"})
    for batch in batches:
        batch["record_count"] = len(batch["records"])
        batch["lineage_counts"] = {lineage: sum(row["lineage"] == lineage for row in batch["records"]) for lineage in LINEAGES}
        batch["variant_counts"] = {variant: sum(row["variant"] == variant for row in batch["records"]) for variant in VARIANTS}
        batch["record_ids_sha256"] = sha_bytes(canonical([row["record_id"] for row in batch["records"]]))
    epoch_orders = []; update_schedule = []
    for arm in ARMS:
        for seed in SEEDS:
            run_id = f"{arm}_seed{seed}"
            run_orders = []
            for epoch in range(188):
                ranked = sorted((hashlib.sha256(("stage07c_batch_order_v1" + arm + str(seed) + str(epoch) + batch["base_batch_id"]).encode()).hexdigest(),
                                 batch["base_batch_id"]) for batch in batches)
                order = [batch_id for _key, batch_id in ranked]
                row = {"run_id": run_id, "epoch": epoch, "base_batch_order": order,
                       "order_keys": ["sha256:" + key for key, _batch in ranked]}
                epoch_orders.append(row); run_orders.append(row)
            update = 0
            for row in run_orders:
                for batch_id in row["base_batch_order"]:
                    if update == 1500: break
                    update += 1
                    update_schedule.append({"run_id": run_id, "update": update, "epoch": row["epoch"], "base_batch_id": batch_id})
                if update == 1500: break
            assert update == 1500
    ids = [row["record_id"] for row in assignments]
    passed = (len(ids) == 896 and len(set(ids)) == 896 and len(batches) == 8
              and all(batch["record_count"] == 112 for batch in batches)
              and all(all(count == 8 for count in batch["lineage_counts"].values()) for batch in batches)
              and all(all(count == 56 for count in batch["variant_counts"].values()) for batch in batches))
    return {"schema": "sph-pio-poc.stage07c.train-v2-batch-schedule.v1",
            "assignment_salt": "stage07c_train_batch_v1", "order_salt": "stage07c_batch_order_v1",
            "record_count": 896, "base_batch_count": 8, "records_per_batch": 112,
            "updates_per_epoch": 8, "max_updates": 1500, "base_batches": batches,
            "assignments": assignments, "epoch_orders": epoch_orders, "update_schedule": update_schedule,
            "random_shuffle": False, "augmentation": False, "curriculum": False,
            "loss_or_lineage_scheduling": False, "pass": passed}


def scheduler_schedule() -> dict[str, Any]:
    rows = []
    for update in range(1501):
        if update <= 40:
            factor = .1 + .9 * update / 40
            phase = "linear_warmup"
        else:
            progress = (update - 40) / (1500 - 40)
            factor = .1 + .9 * .5 * (1 + math.cos(math.pi * progress))
            phase = "cosine_decay"
        rows.append({"update": update, "factor": factor, "learning_rate": 1e-5 * factor, "phase": phase})
    return {"schema": "sph-pio-poc.stage07c.scheduler.v1", "rows": rows,
            "values_sha256": sha_bytes(canonical(rows)), "warmup_updates": 40,
            "terminal_learning_rate": 1e-6, "pass": rows[40]["learning_rate"] == 1e-5 and abs(rows[-1]["learning_rate"] - 1e-6) < 1e-20}


def model_identities() -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows = []; architectures = {}
    for arm in ARMS:
        for seed in SEEDS:
            torch.manual_seed(seed)
            model = MODELS[arm]().to(dtype=torch.float64, device="cpu")
            architecture = schema_hash(model); architectures.setdefault(arm, architecture)
            assert architectures[arm] == architecture
            rows.append({"run_id": f"{arm}_seed{seed}", "arm": arm, "formal_seed": seed,
                         "architecture_sha256": architecture, "initial_parameter_sha256": parameter_hash(model),
                         "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                         "backend": "CPU_FLOAT64_SDPBackend.MATH", "fresh_initialization": True,
                         "stage06c_weight_reads": 0, "stage07b_weight_reads": 0, "prior_optimizer_state_reads": 0})
            del model
    return rows, architectures


def history_freeze() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = [
        STAGE07 / "08_reports/stage07a_final_report.md",
        STAGE07 / "09_manifests/stage07a_role_manifest.json",
        STAGE07 / "09_manifests/stage07a_validation_seal_manifest.json",
        STAGE07 / "08_reports/stage07b_final_report.md",
        STAGE07B / "contracts/train_v2_defect_scale_optimizer_requalification_v0_1.yaml",
        STAGE07B / "manifests/target_record_manifest.json",
        STAGE07 / "09_manifests/stage07b_scale_manifest.json",
        STAGE07 / "09_manifests/stage07b_uncertainty_manifest.json",
        STAGE07 / "09_manifests/stage07b_update_manifest.json",
        STAGE07 / "09_manifests/stage07b_final_manifest.json",
        STAGE06 / "02_training_protocol/stage06b/contracts/formal_k1_defect_training_protocol_v0_1.yaml",
        STAGE06 / "09_manifests/stage06b_final_manifest.json",
        STAGE06 / "09_manifests/stage06c_final_manifest.json",
        STAGE06 / "09_manifests/stage06c_checkpoint_manifest.json",
        STAGE06 / "09_manifests/stage06c_selected_checkpoint_manifest.json",
        STAGE06 / "09_manifests/stage06cr_final_manifest.json",
        STAGE06 / "09_manifests/stage06cr_attribution_manifest.json",
        ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05a_final_manifest.json",
        ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_final_manifest.json",
        ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05c_final_manifest.json",
        ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05cq_final_manifest.json",
        ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/manifests/stage05cr_final_manifest.json",
        ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json",
    ]
    rows = [entry(path) for path in paths]
    checkpoint_manifest = json.loads((STAGE06 / "09_manifests/stage06c_checkpoint_manifest.json").read_text())
    checkpoint_rows = []
    for expected in checkpoint_manifest["checkpoints"]:
        path = ROOT / expected["path"]
        actual = sha_file(path)
        checkpoint_rows.append({**expected, "current_sha256": actual, "unchanged": actual == expected["sha256"] and path.stat().st_size == expected["bytes"]})
    selected_manifest = json.loads((STAGE06 / "09_manifests/stage06c_selected_checkpoint_manifest.json").read_text())
    selected_rows = []
    for expected in selected_manifest["checkpoints"]:
        path = ROOT / expected["path"]
        actual = sha_file(path)
        selected_rows.append({**expected, "current_sha256": actual, "unchanged": actual == expected["sha256"]})
    audit = {"stage06c_checkpoint_count": len(checkpoint_rows), "stage06c_checkpoint_unchanged": sum(row["unchanged"] for row in checkpoint_rows),
             "stage06c_selected_count": len(selected_rows), "stage06c_selected_unchanged": sum(row["unchanged"] for row in selected_rows),
             "checkpoints": checkpoint_rows, "selected_checkpoints": selected_rows,
             "pass": len(checkpoint_rows) == 590 and all(row["unchanged"] for row in checkpoint_rows)
                     and len(selected_rows) == 9 and all(row["unchanged"] for row in selected_rows)}
    return rows, audit


def main() -> None:
    directories = ["freeze", "contracts", "access_control", "model_seed_schedule", "train_v2_batch_schedule",
                   "optimizer_schedule", "success_gates", "checkpoint_policy", "fresh_validation_release",
                   "validation_target_construction", "validation_qualification", "zero_step_preflight", "memory_preflight",
                   "checkpoint_preflight", "sealed_test_preflight", "resource_forecast", "qualification", "manifests", "results"]
    for name in directories: (C / name).mkdir(parents=True, exist_ok=True)
    final07b = json.loads((STAGE07 / "09_manifests/stage07b_final_manifest.json").read_text())
    assert final07b["status"] == "TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED"
    assert final07b["all_gates_pass"] and final07b["stage07c_authorized"]
    assert final07b["train_v2_lineages"] == LINEAGES and final07b["target_record_count"] == 896
    scale_manifest = json.loads((STAGE07 / "09_manifests/stage07b_scale_manifest.json").read_text())
    assert scale_manifest["s_a_v2"] == S_A_V2 and scale_manifest["scale_v2_hash"] == SCALE_HASH

    history, checkpoint_audit = history_freeze()
    assert checkpoint_audit["pass"]
    write_json(C / "freeze/historical_checkpoint_audit.json", checkpoint_audit)
    batches = batch_schedule(); assert batches["pass"]
    batch_path = C / "train_v2_batch_schedule/formal_train_v2_batch_schedule.json"; write_json(batch_path, batches)
    scheduler = scheduler_schedule(); assert scheduler["pass"]
    scheduler_path = C / "optimizer_schedule/formal_scheduler_values.json"; write_json(scheduler_path, scheduler)
    model_rows, architectures = model_identities()

    seal = json.loads((STAGE07 / "09_manifests/stage07a_validation_seal_manifest.json").read_text())
    assert seal["payload_sealed"] and seal["fresh_validation_lineages"] == FRESH
    private = seal["private_artifacts"]
    start_rows = []
    for item in private:
        path = ROOT / item["path"]
        start_rows.append({"path": item["path"], "expected_sha256": item["sha256"], "bytes": item["bytes"],
                           "exists": path.exists(), "mode": oct(stat.S_IMODE(path.stat().st_mode)), "payload_read": False})
    start_pass = len(start_rows) == 89 and all(row["exists"] and row["mode"] == "0o0" and not row["payload_read"] for row in start_rows)
    write_json(C / "access_control/pre_protocol_access_audit.json", {"private_artifact_count": 89, "rows": start_rows, "pass": start_pass})
    assert start_pass
    def release_needed(path: str) -> bool:
        return ("/parameters/" in path or "/analytic_qualification/" in path or "/semidiscrete_audit/" in path
                or ("/trajectory_materialization/" in path and "_n8." in path)
                or ("/topology_qualification/" in path and "_n8_topology." in path))
    release_set = [item for item in private if release_needed(item["path"])]
    assert len(release_set) == 41
    release_plan = {"schema": "sph-pio-poc.stage07c.minimum-release.v1", "all_private_artifacts": 89,
                    "temporary_release_count": len(release_set), "temporary_mode": "0o400",
                    "retained_sealed_count": 89-len(release_set), "restore_mode": "0o0",
                    "release_only_after_protocol_hash_closed": True, "released_artifacts": release_set,
                    "first_decode_ledger_required": True, "payload_copy_outside_release_scope": False,
                    "pass": len(release_set) == 41}
    release_plan_path = C / "access_control/fresh_validation_access_contract.json"; write_json(release_plan_path, release_plan)

    checkpoint_policy = {
        "save": {"update_0_identity": True, "interval_updates": 20, "terminal": True, "selected": True},
        "selection_metric": "FRESH_VALIDATION_V2.global_balanced_Q_def_v2", "selection_rule": "minimum",
        "minimum_selectable_update": 320, "tie_break": "earlier_update", "train_metric_participates": False,
        "consumed_validation_participates": False, "LCDF_08_participates": False,
        "diagnostics_participate": False, "sealed_test_participates": False, "arm_comparison_participates": False,
        "payload": ["model", "optimizer", "scheduler", "RNG", "update", "protocol_hash", "run_id",
                    "architecture_hash", "parameter_hash", "batch_order_state", "TRAIN_metrics",
                    "fresh_validation_metrics", "scale_hash", "target_manifest_hash", "backend"]}
    success = {
        "A_numerical_safety": ["no NaN/Inf", "positive density", "finite coefficient/hidden", "deterministic evaluation"],
        "B_TRAIN_V2_global_Q_def_v2_max": .50,
        "C_FRESH_VALIDATION_V2_global_Q_def_v2_max": .90,
        "D_per_fresh_lineage_Q_def_v2_max": {lineage: 1.0 for lineage in FRESH},
        "E_structure": ["correction-force residual <=1e-10", "reciprocal antisymmetry", "permutation", "edge reorder",
                        "translation", "Galilean", "SO(2)", "reflection", "periodic shift", "history semantics"],
        "seed_pass": "A+B+C+D+E", "arm_pass": ">=2/3 seeds", "transformer_route": "D3 arm PASS",
        "D1_D2_runs_required": "3/3 complete", "D1_D2_arm_pass_required_for_sealed_test": False}
    diagnostic_policy = {"hard_gate": False, "checkpoint_selection": False,
                         "metrics": ["LCDF_08 Q_def_v2", "LCDF_08 raw defect RMSE", "eight new lineage Q_def_v2",
                                     "six-anchor mean", "eight-new mean", "within-stratum mean", "anchor-vs-new gap",
                                     "raw acceleration RMSE", "relative reduction versus lineage zero-correction raw baseline"],
                         "stage06c_D3_LCDF_08_history_retained": True,
                         "cross_stage_normalized_Q_only_comparison_forbidden": True}
    protocol = {
        "contract_id": "formal_train_v2_k1_retraining_protocol_v0_1",
        "schema": "sph-pio-poc.stage07c.protocol.v1",
        "authorization": {"source": "Stage07B", "status": final07b["status"], "stage07c_only": True,
                          "formal_training_authorized_in_stage07c": False},
        "historical_status_preservation": {"Stage06C": "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
                                            "Stage06C_R": "FORMAL_TRAINING_FAILURE_ATTRIBUTED",
                                            "D3_attribution": "TRAIN_LINEAGE_HETEROGENEITY_DOMINANT",
                                            "Stage07A_B_rewrite_forbidden": True},
        "backend": {"device": "CPU", "dtype": "float64", "D3_sdpa": "SDPBackend.MATH"},
        "formal_models": {"seeds": SEEDS, "run_count": 9, "architectures": architectures,
                          "runs": model_rows, "fresh_initialization": True, "historical_or_qualification_weight_reads": 0,
                          "future_preflight_weights_reuse_forbidden": True},
        "data_roles": {"TRAIN_V2": LINEAGES, "FRESH_VALIDATION_V2": FRESH,
                       "CONSUMED_VALIDATION_V1_DIAGNOSTIC_ONLY": ["LCDF_02", "LCDF_09"],
                       "ORIGINAL_SEALED_TEST": ["LCDF_03", "LCDF_10"]},
        "targets": {"TRAIN_V2_records": 896, "target": "Stage07B y_def_v2", "s_a_v2": S_A_V2,
                    "scale_hash": SCALE_HASH, "s_a_v1_use_forbidden": True,
                    "loss": "BAL_MEAN ||(a_eff_theta-a_cons)/s_a_v2||^2", "Q_def_v2": "sqrt(L_def_v2)",
                    "auxiliary_losses": False, "lineage_weights": False, "LCDF_08_special_penalty": False},
        "optimizer": {"family": "AdamW", "learning_rate": 1e-5, "betas": [.9, .999], "eps": 1e-12,
                      "weight_decay": 0, "amsgrad": False, "global_gradient_clip": 1.0,
                      "LR_search": False, "higher_LR": False, "arm_specific_LR": False},
        "training_batches": {"manifest": rel(batch_path), "manifest_sha256": sha_file(batch_path),
                             "base_batches": 8, "records_per_batch": 112, "updates_per_epoch": 8,
                             "assignment_salt": "stage07c_train_batch_v1", "order_salt": "stage07c_batch_order_v1",
                             "zero_overlap": True, "zero_omission": True, "lineage_variant_balanced": True},
        "budget": {"max_updates": 1500, "minimum_updates": 320, "validation_interval": 20,
                   "checkpoint_interval": 20, "budget_increase": False},
        "scheduler": {"warmup_updates": 40, "warmup_start_factor": .1, "warmup_end_factor": 1.0,
                      "post_warmup": "cosine", "terminal_learning_rate": 1e-6,
                      "values_manifest": rel(scheduler_path), "values_sha256": scheduler["values_sha256"]},
        "early_stopping": {"enabled_at_update": 320, "patience_updates": 300,
                           "minimum_global_fresh_validation_Q_improvement": 1e-5,
                           "arm_seed_lineage_specific_changes": False},
        "checkpoint_policy": checkpoint_policy, "success_gates": success,
        "heterogeneity_hypothesis_diagnostics": diagnostic_policy,
        "validation": {"open_only_after_protocol_hash_closed": True, "record_count": 256,
                       "construction": "complete RK2 D0-centered defect/conservative with TRAIN-only s_a_v2",
                       "scale_refit": False, "qualification": ["D0 class/functional/repeat", "graph/source identity", "finite",
                           "conservative zero-force", "provenance", "signal diagnostic", "pair-basis diagnostic", "seven transforms"],
                       "evaluation_chunks": {"rule": "four lineages separately then exact equal-lineage mean",
                                             "chunk_count": 4, "records_per_chunk": 64,
                                             "within_lineage": "equal variant then equal origin mean", "frozen_before_results": True},
                       "result_may_change_protocol": False},
        "access": {"contract": rel(release_plan_path), "contract_sha256": sha_file(release_plan_path),
                   "temporary_release_count": 41, "temporary_mode": "0o400", "restore_mode": "0o0",
                   "consumed_validation_private_reads": 0, "original_sealed_test_private_reads": 0},
        "resume_policy": {"infrastructure_resume_max": 2,
                          "requires_exact_checkpoint_RNG_optimizer_scheduler_protocol_batch_order_identity": True,
                          "scientific_retry": False, "failed_run_replacement": False,
                          "unrecoverable_status": "FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE"},
        "resource_limits": {"peak_RSS_delta_bytes": RESOURCE_GATE, "checkpoint_storage_bytes": 10 * 1024**3,
                            "validation_chunk_change_after_results": False, "budget_reduction_on_failure": False},
        "sealed_test_release": {"stage07c_decode": False, "required_stage07d_status": "FORMAL_TRAIN_V2_TRANSFORMER_RETRAINING_QUALIFIED",
                                "selected_checkpoint_hashes_closed": True, "explicit_stage07e_authorization": True},
        "stage07d_terminal_statuses": ["FORMAL_TRAIN_V2_TRANSFORMER_RETRAINING_QUALIFIED",
                                       "FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
                                       "FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE"],
        "prohibitions": {"formal_optimizer_steps": 0, "formal_parameter_updates": 0, "formal_training_runs": 0,
                         "saved_training_checkpoints": 0, "sealed_test_evaluations": 0, "rollouts": 0,
                         "model_ranking": False, "checkpoint_selection": False, "architecture_or_loss_change": False},
    }
    contract = C / "contracts/formal_train_v2_k1_retraining_protocol_v0_1.yaml"
    contract.write_text(yaml.safe_dump(protocol, sort_keys=False, allow_unicode=True), encoding="utf-8")
    protocol_hash = sha_file(contract)
    for row in model_rows:
        row["protocol_sha256"] = protocol_hash
        row["batch_manifest_sha256"] = sha_file(batch_path)
        row["target_manifest_sha256"] = sha_file(STAGE07B / "manifests/target_record_manifest.json")
        row["scale_hash"] = SCALE_HASH
        row["run_identity_sha256"] = sha_bytes(canonical({"run_id": row["run_id"], "architecture": row["architecture_sha256"],
                                                            "seed": row["formal_seed"], "backend": row["backend"], "protocol": protocol_hash}))
    model_manifest = {"schema": "sph-pio-poc.stage07c.formal-model-seeds.v1", "formal_seeds": SEEDS,
                      "run_count": 9, "runs": model_rows, "pass": len(model_rows) == 9}
    model_path = C / "model_seed_schedule/formal_model_seed_schedule.json"; write_json(model_path, model_manifest)
    write_json(C / "checkpoint_policy/frozen_checkpoint_selection_policy.json", checkpoint_policy)
    write_json(C / "success_gates/frozen_success_gates.json", success)
    protocol_manifest = {"schema": "sph-pio-poc.stage07c.protocol-manifest.v1", "protocol_path": rel(contract),
                         "protocol_sha256": protocol_hash, "frozen_before_fresh_validation_decode": True,
                         "fresh_validation_decode_count_at_freeze": 0, "success_gates_frozen_before_validation": True,
                         "batch_manifest": entry(batch_path), "scheduler_manifest": entry(scheduler_path),
                         "model_manifest": entry(model_path), "access_contract": entry(release_plan_path), "pass": True}
    write_json(C / "manifests/stage07c_protocol_manifest.json", protocol_manifest)
    freeze = {"schema": "sph-pio-poc.stage07c.input-freeze.v1", "authorization_status": final07b["status"],
              "protocol": {"path": rel(contract), "sha256": protocol_hash},
              "protocol_frozen_before_fresh_validation_decode": True, "fresh_validation_decode_count_at_freeze": 0,
              "historical_inputs": history, "historical_checkpoint_audit": entry(C / "freeze/historical_checkpoint_audit.json"),
              "historical_hashes_unchanged": checkpoint_audit["pass"], "train_v2": LINEAGES, "fresh_validation": FRESH,
              "private_artifact_count": 89, "minimum_release_count": 41,
              "decode_counts_at_freeze": {"fresh_formula_private": 0, "fresh_state": 0, "fresh_source": 0,
                  "fresh_target": 0, "fresh_origin": 0, "consumed_validation": 0,
                  "sealed_formula": 0, "sealed_state": 0, "sealed_source": 0, "sealed_target": 0, "sealed_origin": 0},
              "execution_counts_at_freeze": {"formal_optimizer_steps": 0, "formal_parameter_updates": 0,
                  "formal_training_runs": 0, "saved_training_checkpoints": 0, "sealed_test_evaluations": 0, "rollouts": 0},
              "artifacts": {"protocol": entry(contract), "batches": entry(batch_path), "scheduler": entry(scheduler_path),
                            "models": entry(model_path), "access_contract": entry(release_plan_path)}, "pass": True}
    write_json(C / "freeze/stage07c_input_freeze_record.json", freeze)
    write_json(STAGE07 / "09_manifests/stage07c_input_freeze_manifest.json", freeze)
    write_json(STAGE07 / "09_manifests/stage07c_protocol_manifest.json", protocol_manifest)
    print(json.dumps({"protocol_sha256": protocol_hash, "history": len(history), "checkpoints": 590,
                      "selected_checkpoints": 9, "batches": 8, "records": 896, "runs": 9,
                      "private_artifacts": 89, "minimum_release": 41, "fresh_decode_count": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
