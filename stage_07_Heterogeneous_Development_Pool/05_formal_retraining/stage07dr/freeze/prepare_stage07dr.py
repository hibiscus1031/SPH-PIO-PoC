"""Freeze Stage07D-R post-hoc attribution inputs and diagnostic rules.

This stage is read-only with respect to every historical model/data artifact.  It
creates only Stage07D-R evidence, reports, and manifests.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
DR = HERE.parents[1]
S7 = HERE.parents[3]
ROOT = HERE.parents[4]
REPORTS = S7 / "08_reports"
MANIFESTS = S7 / "09_manifests"
D = DR.parent / "stage07d"
C = S7 / "04_training_protocol/stage07c"
B = S7 / "02_defect_scale_requalification/stage07b"
S6 = ROOT / "stage_06_Optimizer_Update_Dynamics_Training"
PROTOCOL = "sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb"
RUN_IDS = [f"{a}_seed{s}" for a in ("D1", "D2", "D3") for s in (20700711, 20700712, 20700713)]
DIRS = ["freeze", "checkpoint_scan", "train_fit_attribution", "fresh_validation_attribution",
        "het_s2_02_support_analysis", "descriptor_geometry", "target_geometry", "gradient_geometry",
        "tangent_reducibility", "history_value", "optimization_dynamics", "stage06_stage07_comparison",
        "hypothesis_outcome", "route_decision", "resources", "manifests", "results"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def identity(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size}


def main() -> None:
    for name in DIRS:
        (DR / name).mkdir(parents=True, exist_ok=True)
    final_d = load(MANIFESTS / "stage07d_final_manifest.json")
    checkpoints = load(MANIFESTS / "stage07d_checkpoint_manifest.json")
    selected = load(MANIFESTS / "stage07d_selected_checkpoint_manifest.json")
    runs = load(MANIFESTS / "stage07d_run_inventory_manifest.json")
    train_cache = load(C / "train_v2_batch_schedule/train_case_cache_manifest.json")
    val_cache = load(C / "validation_target_construction/validation_case_cache_manifest.json")
    sealed = load(C / "sealed_test_preflight/original_sealed_test_denial.json")

    fixed_direct_paths = [
        MANIFESTS / "stage07d_final_manifest.json", REPORTS / "stage07d_final_report.md",
        MANIFESTS / "stage07d_checkpoint_manifest.json", MANIFESTS / "stage07d_selected_checkpoint_manifest.json",
        MANIFESTS / "stage07d_run_inventory_manifest.json", MANIFESTS / "stage07b_train_v2_manifest.json",
        C / "manifests/stage07c_protocol_manifest.json", C / "manifests/validation_target_manifest.json",
        S7 / "01_pool_generation/heterogeneity_strata/formula_identity_library.json",
        S7 / "01_pool_generation/results/heterogeneity_descriptor_audit.json",
        B / "pair_basis_representability/pair_basis_summary.json",
        B / "conservative_decomposition/conservative_compatibility.json",
        S6 / "09_manifests/stage06cr_final_manifest.json",
        S6 / "08_reports/stage06cr_final_report.md",
    ]
    direct = [identity(path) for path in fixed_direct_paths]
    history = [identity(D / kind / f"{run_id}.jsonl") for kind in ("training_histories", "validation_histories") for run_id in RUN_IDS]
    checkpoint_failures = [row["path"] for row in checkpoints["checkpoints"]
                           if sha(ROOT / row["path"]) != row["sha256"]]
    selected_failures = [row["path"] for row in selected["checkpoints"]
                         if sha(ROOT / row["path"]) != row["sha256"]]
    train_failures = [row["record_id"] for row in train_cache["cases"] if sha(ROOT / row["path"]) != row["sha256"]]
    val_failures = [row["record_id"] for row in val_cache["cases"] if sha(ROOT / row["path"]) != row["sha256"]]

    # All thresholds are frozen before reading Stage07D-R diagnostic results.
    rules = {
        "selection_tension": {"train_advantage_Q_at_least": 0.02, "validation_penalty_Q_at_least": 0.02},
        "lineage_labels": {"persistent_hard_arm_mean_Q_above": 1.0,
                           "architecture_sensitive_arm_mean_range_above": 0.20,
                           "seed_sensitive_CV_above": 0.10},
        "descriptor_support": {
            "standardization": "TRAIN-only median and 1.4826*MAD; IQR/1.349 then 1.0 fallback",
            "distance_reference": "TRAIN leave-one-out nearest-neighbour distances",
            "in_support_max": "LOO_NN_p95", "edge_max": "1.5*LOO_NN_p95",
            "outside_if_envelope_exceedance_count_at_least": 2,
            "affine_residual_normalization": "distance divided by TRAIN robust radius",
        },
        "target_support": {"PCA_variance_fraction": 0.95, "minimum_components": 2,
                           "in_support_reconstruction_residual_max": "TRAIN_p95",
                           "edge_multiplier": 1.5},
        "tangent": {"subset": "LOW+MAIN origins 0,8,16,24 for HET_S2_01/02/03",
                    "pair_head_direction_count": 64, "full_network_direction_count": 128,
                    "high_fraction_at_least": 0.50, "low_fraction_below": 0.20,
                    "method": "deterministic Rademacher directional JVP range projection"},
        "gradient": {"cases": "all 64 origins per lineage", "conflict_mean_cosine_below": -0.05,
                     "conflict_negative_fraction_at_least": 0.50, "aligned_mean_cosine_at_least": 0.20},
        "optimizer": {"flat_abs_slope_at_most": 1e-5, "progress_slope_below": -1e-5},
        "branch_B": {"material_relative_reduction_gain_at_least": 0.02,
                     "fresh_transfer_requires_global_and_all_lineage_gates": True},
        "attribution_precedence": ["PAIR_BASIS_EXCLUSION", "SUPPORT_AND_TARGET_GEOMETRY", "GRADIENT_CONFLICT",
                                   "TANGENT_AND_OPTIMIZATION", "TEMPORAL_INFORMATION", "MIXED"],
    }
    checks = {
        "stage07d_failure_preserved": final_d["status"] == "FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED",
        "stage07e_false": not final_d["Stage07E_authorized"],
        "protocol_exact": final_d["protocol_sha256"] == PROTOCOL,
        "optimizer_histories_12860": sum(1 for p in (D / "training_histories").glob("*.jsonl") for line in p.open() if line.strip()) == 12860,
        "checkpoint_652": checkpoints["checkpoint_count"] == 652 and not checkpoint_failures,
        "selected_9": selected["selected_count"] == 9 and not selected_failures,
        "run_identities_9": len(runs["runs"]) == 9 and [x["run_id"] for x in runs["runs"]] == RUN_IDS,
        "train_v2_896": train_cache["case_count"] == 896 and not train_failures,
        "validation_v2_256": val_cache["case_count"] == 256 and not val_failures,
        "original_sealed_zero": sealed["pass"] and all(v == 0 for v in sealed["decode_counts"].values()),
        "stage07d_sealed_zero": final_d["sealed_test_evaluations"] == 0 and all(v == 0 for v in final_d["sealed_decode_counts"].values()),
    }
    record = {
        "schema": "sph-pio-poc.stage07dr.input-freeze.v1", "protocol_sha256": PROTOCOL,
        "historical_stage07d_status": final_d["status"], "Stage07E_authorized": False,
        "FRESH_VALIDATION_V2_role_transition": "CONSUMED_VALIDATION_V2_DIAGNOSTIC_ONLY",
        "validation_lineages": ["HET_S1_01", "HET_S2_02", "HET_S3_03", "HET_S4_03"],
        "frozen_direct_inputs": direct, "frozen_history_files": history,
        "checkpoint_manifest_sha256": sha(MANIFESTS / "stage07d_checkpoint_manifest.json"),
        "selected_manifest_sha256": sha(MANIFESTS / "stage07d_selected_checkpoint_manifest.json"),
        "checkpoint_failures": checkpoint_failures, "selected_failures": selected_failures,
        "train_case_failures": train_failures, "validation_case_failures": val_failures,
        "diagnostic_rules_frozen_before_result_read": rules, "checks": checks,
        "new_optimizer_steps": 0, "new_parameter_updates": 0, "new_training_runs": 0,
        "new_checkpoints": 0, "sealed_test_evaluations": 0, "rollouts": 0,
        "pass": all(checks.values()),
    }
    write(DR / "freeze/stage07dr_input_freeze_record.json", record)
    write(DR / "manifests/stage07dr_input_freeze_manifest.json", record)
    write(MANIFESTS / "stage07dr_input_freeze_manifest.json", record)
    (REPORTS / "stage07dr_freeze_and_scope.md").write_text(
        "# Stage07D-R Freeze and Scope\n\nStage07D remains `FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`; "
        "Stage07E remains false. FRESH_VALIDATION_V2 is permanently transitioned to "
        "`CONSUMED_VALIDATION_V2_DIAGNOSTIC_ONLY`. The 12,860 histories, 652 checkpoint hashes, nine selected hashes, "
        "896 TRAIN_V2 and 256 consumed-validation identities are frozen. Diagnostic algorithms and thresholds were fixed "
        f"before result reading. Freeze PASS: **{record['pass']}**. New training/update/checkpoint/rollout and original "
        "SEALED_TEST decode/evaluation counts are all zero.\n", encoding="utf-8")
    print(json.dumps({"event": "stage07dr_freeze", "pass": record["pass"], "checks": checks}, sort_keys=True))
    if not record["pass"]:
        raise SystemExit("TRAIN_V2_RETRAINING_FAILURE_EVIDENCE_INCOMPLETE")


if __name__ == "__main__":
    main()
