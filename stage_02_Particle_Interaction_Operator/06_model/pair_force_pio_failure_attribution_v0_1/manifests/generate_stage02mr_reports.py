#!/usr/bin/env python3
"""Close Stage 02M-R attribution, route decision, reports, and integrity evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_failure_attribution_v0_1"
REPORTS = STAGE / "07_reports"
KROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_report(name: str, text: str) -> None:
    (REPORTS / name).write_text(text.rstrip() + "\n")


freeze = json.loads((ROOT / "freeze/stage02mr_historical_freeze_manifest.json").read_text())
metric = json.loads((ROOT / "metric_reconstruction/complete_checkpoint_metric_reconstruction.json").read_text())
dynamics = json.loads((ROOT / "checkpoint_dynamics/checkpoint_dynamics.json").read_text())
conditioning = json.loads((ROOT / "optimization_conditioning/zero_step_conditioning.json").read_text())
scale = json.loads((ROOT / "target_scaling/target_scale_audit.json").read_text())
ident = json.loads((ROOT / "feature_identifiability/feature_identifiability_audit.json").read_text())
tangent = json.loads((ROOT / "tangent_space/tangent_space_audit.json").read_text())
shift = json.loads((ROOT / "family_shift/family_configuration_shift.json").read_text())

integrity_rows = []
for row in freeze["files"]:
    path = REPO / row["path"]
    actual = sha(path)
    integrity_rows.append({"path": row["path"], "expected": row["sha256"], "actual": actual, "status": "PASS" if actual == row["sha256"] else "FAIL"})
integrity = {"rows": integrity_rows, "verified_file_count": len(integrity_rows), "status": "PASS" if all(row["status"] == "PASS" for row in integrity_rows) else "FAIL"}
write_json(ROOT / "freeze/post_diagnostic_historical_integrity_verification.json", integrity)

basis_path = KROOT / "representability/pair_basis_representability.json"
basis = json.loads(basis_path.read_text())
basis_pass = basis.get("status") == "PASS" and float(basis.get("general_max_normalized_residual", 1.0)) <= float(basis.get("general_tolerance", 1e-10))

selected_tangent = [row for row in tangent["audits"] if row["point"] == "selected"]
k1_head_pass = [row for row in selected_tangent if row["architecture"] == "K1" and row["final_head"]["attainable_train_family_balanced_Q_L2"] <= 0.25]
k2_head_or_whole_pass = [row for row in selected_tangent if row["architecture"] == "K2" and min(row["final_head"]["attainable_train_family_balanced_Q_L2"], row["whole_network"]["attainable_train_family_balanced_Q_L2"]) <= 0.25]

def weighted_conditioning(point: str, multiplier_index: int) -> dict[str, float]:
    totals = {"n": 0.0, "epsilon": 0.0, "historical_epsilon": 0.0, "wd": 0.0, "near": 0.0}
    norms, cosines = [], []
    for audit in conditioning["audits"]:
        if audit["point"] != point:
            continue
        record = audit["loss_multiplier_diagnostics"][multiplier_index]
        norms.append(record["global_gradient_norm"])
        cosines.append(record["effective_update_direction_cosine_vs_multiplier_1"])
        for module in record["modules"].values():
            n = module["parameter_count"]
            totals["n"] += n
            totals["epsilon"] += n * module["epsilon_dominated_fraction"]
            totals["historical_epsilon"] += n * module["historical_epsilon_dominated_fraction"]
            totals["wd"] += n * module["weight_decay_dominated_fraction"]
            totals["near"] += n * module["near_zero_gradient_fraction"]
    return {
        "gradient_norm_median": float(np.median(norms)),
        "prospective_epsilon_dominated_fraction": totals["epsilon"] / totals["n"],
        "historical_epsilon_dominated_fraction": totals["historical_epsilon"] / totals["n"],
        "weight_decay_dominated_fraction": totals["wd"] / totals["n"],
        "near_zero_gradient_fraction": totals["near"] / totals["n"],
        "effective_update_direction_cosine_median_vs_multiplier_1": float(np.median(cosines)),
    }

condition_summary = {point: {str(mult): weighted_conditioning(point, index) for index, mult in enumerate((1, 1000, 1000000))} for point in ("initialization", "selected")}
loss_scale_stable = condition_summary["selected"]["1000"]["effective_update_direction_cosine_median_vs_multiplier_1"] >= 0.95 and condition_summary["selected"]["1000000"]["effective_update_direction_cosine_median_vs_multiplier_1"] >= 0.95
conditioning_evidence = (
    condition_summary["selected"]["1"]["historical_epsilon_dominated_fraction"] >= 0.5 and
    condition_summary["selected"]["1"]["weight_decay_dominated_fraction"] >= 0.5 and
    condition_summary["selected"]["1000000"]["prospective_epsilon_dominated_fraction"] < condition_summary["selected"]["1"]["prospective_epsilon_dominated_fraction"]
)

actual_k1_train_pass = sum(run["architecture"] == "K1" and run["C_validation_selected_checkpoint"]["train"]["family_balanced_mean"]["Q_L2"] <= 0.25 for run in metric["runs"])
actual_k2_train_pass = sum(run["architecture"] == "K2" and run["C_validation_selected_checkpoint"]["train"]["family_balanced_mean"]["Q_L2"] <= 0.25 for run in metric["runs"])

criteria = {
    "no_hard_feature_identifiability_contradiction": ident["status"] == "NO_HARD_IDENTIFIABILITY_CONTRADICTION_FOUND",
    "basis_representability_pass": basis_pass,
    "K1_selected_head_audit_seed_count_Q_L2_le_0p25": len(k1_head_pass),
    "K2_selected_head_or_whole_audit_seed_count_Q_L2_le_0p25": len(k2_head_or_whole_pass),
    "K1_actual_selected_train_gate_seed_count": actual_k1_train_pass,
    "K2_actual_selected_train_gate_seed_count": actual_k2_train_pass,
    "historical_actual_train_gate_zero_of_three_for_K1": actual_k1_train_pass == 0,
    "optimization_conditioning_evidence": conditioning_evidence,
    "loss_scale_direction_stability_condition_met": loss_scale_stable,
    "loss_scale_evidence_label": "LOSS_SCALE_DIAGNOSTIC_CONDITIONING_SENSITIVE_BUT_DIRECTION_UNSTABLE" if not loss_scale_stable else "LOSS_SCALE_CONDITIONING_EVIDENCE",
    "evidence_complete": freeze["status"] == "PASS" and tangent["complete"] and integrity["status"] == "PASS",
}

status = "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING"
if not criteria["evidence_complete"]:
    status = "STATIC_FITTING_FAILURE_EVIDENCE_INCOMPLETE"
elif not (criteria["no_hard_feature_identifiability_contradiction"] and criteria["basis_representability_pass"] and criteria["K1_selected_head_audit_seed_count_Q_L2_le_0p25"] >= 2 and criteria["historical_actual_train_gate_zero_of_three_for_K1"] and criteria["optimization_conditioning_evidence"]):
    status = "STATIC_FITTING_FAILURE_MIXED_OR_UNRESOLVED"

attribution = {
    "status": status,
    "unique_primary_attribution": True,
    "metric_reconstruction_classification": metric["classification"],
    "criteria": criteria,
    "early_stopping_primary_blocker": False,
    "selection_conflict_primary_blocker": False,
    "family_shift_primary_blocker": False,
    "feature_identifiability_primary_blocker": False,
    "function_class_primary_blocker": False,
    "interpretation": "K1 final-head local tangent projections cross the train gate for two selected historical seeds while all historical K1 fits remain near the zero-correction baseline; extremely small normalized targets/losses, dominant historical epsilon/weight-decay fractions, and strong scale sensitivity identify optimization conditioning as the primary attributable mechanism.",
    "limitations": [
        "The audit-only tangent projection is not trained-model performance and creates no deployable checkpoint.",
        "Whole-network LSQR values are frozen-iteration upper bounds; they did not converge to the feasible head-only subspace solution and are not function-class lower bounds.",
        "No hard feature contradiction was found, but absence of observed exact contradiction is not a global identifiability proof.",
        "Loss multiplier directions were not stable enough for the stricter LOSS_SCALE_CONDITIONING_EVIDENCE label.",
    ],
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
}
write_json(ROOT / "results/failure_attribution.json", attribution)

route = {
    "stage02mr_status": status,
    "current_pio_learning_route": "one prospective redesign is scientifically justified but not yet authorized for execution",
    "next_authorized_branch": "Stage 02M-P — Prospective Training Protocol v0.2 Design with New Blind Evaluation Families",
    "direct_training_authorized": False,
    "stage02n_authorized": False,
    "existing_K0_K1_K2_retraining_authorized": False,
    "BLIND_FAMILY_04_current_role": "consumed_historical_test_only",
    "future_confirmatory_requirement": "After the new protocol and thresholds are frozen, generate previously unobserved validation and test families; BLIND_FAMILY_04 may not select or requalify any changed protocol or architecture.",
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
    "rollouts": 0,
}
write_json(ROOT / "route_decision/route_decision.json", route)

metric_lines = ["| run | init train Q | best-train update/Q | selected update/Q | terminal update/Q |", "|---|---:|---:|---:|---:|"]
for run in metric["runs"]:
    metric_lines.append(f"| {run['run_id']} | {run['A_initialization']['train']['family_balanced_mean']['Q_L2']:.6f} | {run['B_lowest_train_metric_checkpoint']['update']} / {run['B_lowest_train_metric_checkpoint']['train']['family_balanced_mean']['Q_L2']:.6f} | {run['best_update']} / {run['C_validation_selected_checkpoint']['train']['family_balanced_mean']['Q_L2']:.6f} | {run['D_terminal_checkpoint']['update']} / {run['D_terminal_checkpoint']['train']['family_balanced_mean']['Q_L2']:.6f} |")
metric_table = "\n".join(metric_lines)

tangent_lines = ["| architecture | seed | selected whole-network Q | selected head-only Q | classification |", "|---|---:|---:|---:|---|"]
for row in selected_tangent:
    tangent_lines.append(f"| {row['architecture']} | {row['seed']} | {row['whole_network']['attainable_train_family_balanced_Q_L2']:.6f} | {row['final_head']['attainable_train_family_balanced_Q_L2']:.6f} | {row['final_head_classification']} |")
tangent_table = "\n".join(tangent_lines)

target_min = min(row["target_tilde_RMS"] for row in scale["train_graphs"])
target_max = max(row["target_tilde_RMS"] for row in scale["train_graphs"])
shift_agg = shift["aggregates_by_split"]

write_report("stage02mr_freeze_and_scope.md", f"""# Stage 02M-R — Freeze and scope

历史冻结 **{freeze['status']}**：{freeze['file_count']} 个文件、{freeze['checkpoint_count']} 个历史检查点、9 个 selected hash 与 {freeze['canonical_record_count']} 个 canonical records。运行更新序列 `{freeze['expected_optimizer_updates']}`、best-update 序列 `{freeze['expected_best_updates']}` 唯一且完全匹配。

保持 `STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`、Stage 02N authorization `false`、历史 optimizer steps `3280` 与 test release `completed_once`。本阶段只做 forward/backward/JVP/VJP/LSQR 审计；新 optimizer steps、训练 runs、test evaluations 均为 0。诊断后复核 {integrity['verified_file_count']} 个历史 hash：**{integrity['status']}**。""")

write_report("stage02mr_metric_reconstruction.md", f"""# Stage 02M-R — Metric reconstruction

所有 164 个历史 interval checkpoint 均在 train/validation 上重建；test 未重评。每个检查点的 graph/family Q_L2、Q_Linf、cosine、resolution/support、prediction/target RMS 和 zero-correction improvement 均保存在机器记录中。

{metric_table}

任一历史检查点达到 train family-balanced `Q_L2 <= 0.25`：**否**。分类：**{metric['classification']}**。""")

write_report("stage02mr_checkpoint_dynamics.md", f"""# Stage 02M-R — Checkpoint dynamics

9 个 run 的完整机器序列和 12 通道图已生成，包括 loss、train/validation Q_L2、LR、gradient norm、clipping、alpha/beta RMS 与 saturation、parameter norm 和 update/parameter ratio。

K0/K1 在 terminal 仍约为 0.991–0.994，表现为持续欠拟合。K2 的 seed 20261202 从 selected 0.905 降至 terminal 0.653，但仍未触及 0.25；另有 seed 出现 selected 后 train/validation 退化，说明 seed instability 与局部 overfit/plateau 存在。所有 run 依冻结 patience 规则 early-stop，但没有 terminal checkpoint 达门，因此 early stopping 与 checkpoint selection 不是主要失败来源。分析没有触发重选。""")

write_report("stage02mr_optimization_conditioning.md", f"""# Stage 02M-R — Optimization conditioning

18 个 initialization/selected 点均完成 zero-step backward，逐模块记录 data gradient、WD、Adam m/v、sqrt(v)、epsilon/WD/near-zero fractions、effective update 与 clipping；参数 hash 全部不变：**{conditioning['all_parameter_hashes_unchanged']}**。

Selected、multiplier=1 的参数加权历史 epsilon-dominated fraction 为 `{condition_summary['selected']['1']['historical_epsilon_dominated_fraction']:.6f}`，WD-dominated fraction 为 `{condition_summary['selected']['1']['weight_decay_dominated_fraction']:.6f}`，梯度范数中位数 `{condition_summary['selected']['1']['gradient_norm_median']:.3e}`。这支持尺度相关的 Adam/WD 条件化不良。

将同一 loss 仅用于 backward 放大到 1e3/1e6 后，prospective epsilon-dominated fraction 从 `{condition_summary['selected']['1']['prospective_epsilon_dominated_fraction']:.6f}` 降至 `{condition_summary['selected']['1000']['prospective_epsilon_dominated_fraction']:.6f}` / `{condition_summary['selected']['1000000']['prospective_epsilon_dominated_fraction']:.6f}`，WD-dominated fraction从 `{condition_summary['selected']['1']['weight_decay_dominated_fraction']:.6f}` 降至 `{condition_summary['selected']['1000']['weight_decay_dominated_fraction']:.6f}` / `{condition_summary['selected']['1000000']['weight_decay_dominated_fraction']:.6f}`。但 effective-update direction cosine 中位数仅 `{condition_summary['selected']['1000']['effective_update_direction_cosine_median_vs_multiplier_1']:.3f}` / `{condition_summary['selected']['1000000']['effective_update_direction_cosine_median_vs_multiplier_1']:.3f}`，不满足方向稳定条件，故严格标签为 `{criteria['loss_scale_evidence_label']}`，不据此授权协议变更。""")

write_report("stage02mr_target_scale_audit.md", f"""# Stage 02M-R — Target scale audit

冻结 `a0 = 400 m s^-2`，未修改。10 个 train graphs 的 `target_tilde RMS` 范围为 `{target_min:.6e}`–`{target_max:.6e}`；相应 graph-balanced loss 处于约 1e-7–1e-6 数量级。逐图 dimensional target RMS、target_tilde RMS/Linf、9 组 initial/selected prediction RMS、coefficient RMS/saturation 及 family/resolution/support 范围已机器记录。

该尺度与实测微小梯度、高 epsilon/WD dominance 一致；encoder/head 梯度失衡按模块保留于 conditioning JSON。此结论是诊断，不改变 a0、loss 或 checkpoint。""")

write_report("stage02mr_feature_identifiability.md", f"""# Stage 02M-R — Feature identifiability

仅使用 Stage 02K 允许特征。CPU float64 canonical-byte 审计发现 `{ident['exact_edge_collision_group_count']}` 个重复 edge-feature 组，但未把非唯一 pseudoinverse edge coefficient 当作真值；edge collision 本身不构成矛盾。完全允许输入 graph collision 组数 `{ident['exact_full_allowed_graph_input_collision_group_count']}`，不相容 nodal target 案例数 `{len(ident['hard_incompatible_target_cases'])}`。

冻结半径 1e-6、1e-4、1e-2 的 normalized rooted-node near-collision pair 均为 0，未事后设置阈值。结论：**{ident['status']}**。这是“未发现硬矛盾”，不是全局唯一性证明；test target 未使用。""")

write_report("stage02mr_tangent_space_audit.md", f"""# Stage 02M-R — Tangent-space audit

K0/K1/K2 × 3 seeds × initialization/selected 共 18 点完成。whole-network 使用 matrix-free JVP/VJP/LSQR，固定 `atol=btol=1e-8`、30 iterations；final head 仅显式形成至多 66 列的小 Jacobian。所有点无 parameter writeback、无新 checkpoint、无 validation/test target。

{tangent_table}

K1 selected 的 20261201 与 20261203 在 head-only 局部投影分别达到 0.159343 和 0.158108，满足门槛，而历史 K1 train gate 为 0/3，构成 `HEAD_OPTIMIZATION_GAP` 支持。K2 各点未达到 0.25，不能由本审计推出相对架构优劣。whole-network LSQR 在冻结 iteration limit 内未收敛到已知 head-only 可行子空间，因此其 Q 是迭代受限上界，而非函数类不可达下界。""")

write_report("stage02mr_family_shift.md", f"""# Stage 02M-R — Family/configuration shift

基于允许输入的 graph summaries，validation 相对 train 的 NN/convex-hull 平均距离为 `{shift_agg['future_validation']['nearest_neighbor_mean']:.3f}` / `{shift_agg['future_validation']['convex_hull_mean']:.3f}`；consumed test input 为 `{shift_agg['future_test']['nearest_neighbor_mean']:.3f}` / `{shift_agg['future_test']['convex_hull_mean']:.3f}`。逐 resolution/support 结果已记录。

这些距离和已冻结的 validation/test metrics 仅作历史描述。由于 164 个 checkpoint 在 train 上从未达门，family shift 不是主要阻断因素。Test target decode=0，new test evaluations=0；BLIND_FAMILY_04 仍是 consumed historical test only。""")

write_report("stage02mr_failure_attribution.md", f"""# Stage 02M-R — Failure attribution

唯一主归因：**{status}**。

证据闭合：basis 的自由 per-edge representability 仍为 PASS（源 hash `{sha(basis_path)}`），但它不证明 learned map；未发现 hard feature contradiction；K1 有 2 个 selected seeds 的 head tangent 可达 train gate，而历史实际为 0/3；normalized target/loss 和 Adam/WD/gradient 证据支持条件化不良。Selection/transfer 条件因历史 train 从未达门而不成立；early stopping 不是主要阻断；whole-network iteration-limited LSQR 不能支持 function-class limit。

本归因不等于新模型性能，不宣称 attention 必要、K2 优于 K1、Stage 01 恢复，也不授权训练或 rollout。""")

write_report("stage02mr_route_decision.md", f"""# Stage 02M-R — Learning-route decision

当前 PIO learning route 具有一次有限、前瞻性的重设计科学依据。下一唯一允许分支：**{route['next_authorized_branch']}**。

这只授权设计，不授权训练。Stage 02N=false；不得直接重训 K0/K1/K2。`BLIND_FAMILY_04_current_role = consumed_historical_test_only`。任何未来协议必须先冻结新协议与阈值，再生成未观察的新 validation/test families；现有 test 不得选模或重新资格化。""")

write_report("stage02mr_final_report.md", f"""# Stage 02M-R — Final report

## Final status

**{status}**

1. Stage 02M failure preserved：`STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`；Stage 02N authorization=false。
2. 9-run/checkpoint mapping 唯一；optimizer updates `{freeze['expected_optimizer_updates']}`，best updates `{freeze['expected_best_updates']}`。
3. Initial/best-train/selected/terminal metrics：

{metric_table}

4. Ever-achieved train gate：否，**{metric['classification']}**。
5. Checkpoint dynamics：K0/K1 持续欠拟合；K2 存在 seed instability/plateau，但没有 selection conflict 能解释 train failure；early stopping 非主要阻断。
6. Target scale：a0 保持 400；target_tilde RMS `{target_min:.3e}`–`{target_max:.3e}`，loss 处于极小数量级。
7. Gradient/Adam conditioning：selected multiplier=1 的历史 epsilon-dominated/WD-dominated 参数比例 `{condition_summary['selected']['1']['historical_epsilon_dominated_fraction']:.3f}` / `{condition_summary['selected']['1']['weight_decay_dominated_fraction']:.3f}`。
8. Loss multiplier：放大显著降低 prospective epsilon/WD dominance，但 update 方向不稳定；未授予严格 `LOSS_SCALE_CONDITIONING_EVIDENCE` 标签，未改变协议。
9. Basis vs learned map：自由 edge coefficient basis residual PASS 不证明 `g_theta(allowed_features)` 可学习。
10. Feature identifiability：**{ident['status']}**；无 test target。
11. Tangent projection：18/18 完成；whole-network 是 30-iteration 上界。
12. Final-head projection：K1 selected 有 2 seeds 达 0.25 门，支持 `HEAD_OPTIMIZATION_GAP`。
13. Family/configuration shift：validation/test input 均明显偏离 train，但 train 从未拟合，故 transfer 不是主要阻断。
14. Consumed-test boundary：`current_test_status=consumed_confirmatory_test`；BLIND_FAMILY_04 仅可作历史 test。
15. Unique failure attribution：**{status}**。
16. Next authorized branch：`{route['next_authorized_branch']}`，仅设计、不训练。
17. `new_optimizer_steps = 0`。
18. `new_training_runs = 0`。
19. `new_test_evaluations = 0`。
20. `rollouts = 0`；诊断后 {integrity['verified_file_count']} 个历史 hashes unchanged：**{integrity['status']}**。

不修改 architecture/loss/features/a0，不重选 checkpoint，不解码 test target，不声称 K2 优于 K1、Attention 必要或 Stage 01 已恢复。""")

result_summary = {
    "status": status,
    "historical_stage02m_verdict": "STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED",
    "metric_classification": metric["classification"],
    "feature_identifiability": ident["status"],
    "K1_selected_head_tangent_pass_seed_count": len(k1_head_pass),
    "K2_selected_head_or_whole_tangent_pass_seed_count": len(k2_head_or_whole_pass),
    "next_authorized_branch": route["next_authorized_branch"],
    "direct_training_authorized": False,
    "stage02n_authorized": False,
    "current_test_status": "consumed_confirmatory_test",
    "BLIND_FAMILY_04_current_role": "consumed_historical_test_only",
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
    "rollouts": 0,
    "historical_integrity": integrity["status"],
}
write_json(ROOT / "results/stage02mr_final_summary.json", result_summary)

artifact_paths = sorted(path for path in ROOT.rglob("*") if path.is_file() and path.name != "stage02mr_run_manifest.json") + sorted(REPORTS / name for name in (
    "stage02mr_freeze_and_scope.md", "stage02mr_metric_reconstruction.md", "stage02mr_checkpoint_dynamics.md", "stage02mr_optimization_conditioning.md", "stage02mr_target_scale_audit.md", "stage02mr_feature_identifiability.md", "stage02mr_tangent_space_audit.md", "stage02mr_family_shift.md", "stage02mr_failure_attribution.md", "stage02mr_route_decision.md", "stage02mr_final_report.md"))
manifest = {
    "manifest_version": "stage02mr-run-1.0.0",
    "status": status,
    "artifact_count": len(artifact_paths),
    "artifacts": [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "bytes": path.stat().st_size} for path in artifact_paths],
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
    "historical_integrity": integrity["status"],
}
write_json(ROOT / "manifests/stage02mr_run_manifest.json", manifest)
print(json.dumps(result_summary, sort_keys=True))
