#!/usr/bin/env python3
"""Finalize Stage 02M-P gates, reports, route decision, and manifests."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
REPORTS = STAGE / "07_reports"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def report(name: str, text: str) -> None:
    (REPORTS / name).write_text(text.rstrip() + "\n")


freeze = json.loads((ROOT / "freeze/stage02mp_historical_freeze_manifest.json").read_text())
scale = json.loads((ROOT / "target_scale/train_only_supervision_scale.json").read_text())
protocol = json.loads((ROOT / "freeze/protocol_v0_2_hash.json").read_text())
formulas = json.loads((ROOT / "blind_family_generator/blind_family_formulas_v0_2.json").read_text())
physical = json.loads((ROOT / "reference_qualification/physical_preflight.json").read_text())
reference = json.loads((ROOT / "reference_qualification/reference_qualification.json").read_text())
target_core = json.loads((ROOT / "target_qualification/target_core_qualification.json").read_text())
paths_initial = json.loads((ROOT / "target_qualification/resolution_support_qualification.json").read_text())
paths = json.loads((ROOT / "target_qualification/resolution_support_qualification_infrastructure_corrected.json").read_text())
conservation = json.loads((ROOT / "conservation/pair_only_conservation.json").read_text())
family = json.loads((ROOT / "target_qualification/family_all_or_none_qualification_infrastructure_corrected.json").read_text())
correction = json.loads((ROOT / "qc/frozen_infrastructure_semantics_application.json").read_text())
collection = json.loads((ROOT / "manifests/v1_1_collection_manifest.json").read_text())
inventory = json.loads((ROOT / "canonical_records/canonical_inventory.json").read_text())
split = json.loads((ROOT / "split/prefrozen_split_manifest.json").read_text())
lineage = json.loads((ROOT / "split/family_lineage_registry.json").read_text())
normalization = json.loads((ROOT / "normalization/input_normalization_reuse_verification.json").read_text())
seal = json.loads((ROOT / "test_seal/test_seal_denial_audit.json").read_text())
conditioning = json.loads((ROOT / "conditioning_contract/zero_step_conditioning_preflight.json").read_text())
harness = json.loads((ROOT / "harness/zero_step_harness_preflight.json").read_text())
checkpoint = json.loads((ROOT / "checkpointing/zero_step_checkpoint_roundtrip_audit.json").read_text())
resource = json.loads((ROOT / "resource_forecast/resource_forecast.json").read_text())

historical_rows = []
for row in freeze["files"]:
    actual = sha(REPO / row["path"])
    historical_rows.append({"path": row["path"], "expected": row["sha256"], "actual": actual, "status": "PASS" if actual == row["sha256"] else "FAIL"})
historical_integrity = {
    "stage02mp_frozen_file_count": len(historical_rows),
    "stage02mp_frozen_files_status": "PASS" if all(row["status"] == "PASS" for row in historical_rows) else "FAIL",
    "stage02mr_285_file_status": freeze["stage02mr_285_file_verification"]["status"],
    "rows": historical_rows,
}
historical_integrity["status"] = "PASS" if historical_integrity["stage02mp_frozen_files_status"] == historical_integrity["stage02mr_285_file_status"] == "PASS" else "FAIL"
write_json(ROOT / "freeze/post_stage02mp_historical_integrity_verification.json", historical_integrity)

step_rows = []
for path in sorted(ROOT.rglob("*.py")):
    calls = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "step":
            calls.append(node.lineno)
    step_rows.append({"path": str(path.relative_to(REPO)), "step_call_lines": calls})
step_audit = {"files": step_rows, "step_call_count": sum(len(row["step_call_lines"]) for row in step_rows)}
step_audit["status"] = "PASS" if step_audit["step_call_count"] == 0 else "FAIL"
write_json(ROOT / "harness/forbidden_step_call_audit.json", step_audit)

protocol_hash_unchanged = sha(ROOT / "freeze/training_protocol_v0_2.yaml") == protocol["protocol_sha256"]
test_release_absent = not any(ROOT.rglob("test_release_manifest*"))
reference_max = max(row["pair_agreement"]["normalized_L2"] for fam in reference["families"] for row in fam["rows"])
force_max = max(row["normalized_total_target_force_residual"] for fam in conservation["families"] for row in fam["rows"])
pair_max = max(row["general_antisymmetric"]["normalized_projection_residual"] for fam in conservation["families"] for row in fam["rows"])
loss_values = [row["initial_scaled_loss"] for row in conditioning["rows"] if row["architecture"] in ("K1", "K2")]
epsilon_values = [row["parameter_weighted_epsilon_dominated_fraction"] for row in conditioning["rows"] if row["architecture"] in ("K1", "K2")]
gradient_errors = [row["full_batch_gradient_equivalence_relative_error"] for row in harness["rows"]]

gates = {
    "historical_freeze_PASS": historical_integrity["status"] == "PASS",
    "train_only_a_sup_complete": scale["train_graph_count"] == 10 and scale["historical_validation_target_decode_count"] == scale["historical_test_target_decode_count"] == 0,
    "protocol_hash_frozen_before_blind_formula": protocol["frozen_before_blind_formula_materialization"] and protocol["blind_formula_path_absent_at_hash_time"] and protocol_hash_unchanged,
    "two_blind_families_single_materialized": formulas["family_count"] == 2 and formulas["single_materialization"] and formulas["materialized_after_protocol_hash"] and not formulas["family_replacement_or_redraw_used"],
    "new_reference_target_conservation_PASS": physical["all_2_families_PASS"] and reference["all_10_PASS"] and target_core["all_10_PASS"] and paths["all_2_families_resolution_support_PASS"] and conservation["all_10_PASS"] and family["all_2_families_materialization_authorized"],
    "frozen_infrastructure_semantics_non_scientific": correction["source_target_unchanged"] and not correction["scientific_threshold_changed"] and not correction["family_seed_formula_or_role_changed"] and not correction["generator_physics_changed"] and not correction["result_dependent_selection_used"],
    "v1_1_collection_complete": collection["status"] == "BLIND_MULTIFAMILY_DATASET_V1_1_READY" and inventory["record_count"] == 20,
    "four_lineage_components": lineage["family_count"] == 4 and not lineage["cross_split_lineage"],
    "new_split_PASS": split["status"] == "PASS" and split["counts"] == {"future_train": 10, "future_validation": 5, "future_test": 5},
    "old_input_normalization_reused": normalization["status"] == "PASS" and not normalization["refit_performed"],
    "new_test_seal_PASS": seal["status"] == "PASS" and seal["test_target_decode_count"] == 0 and not seal["test_target_access"] and test_release_absent,
    "conditioning_9_of_9_PASS": conditioning["status"] == "PASS" and len(conditioning["rows"]) == 9,
    "checkpoint_harness_PASS": harness["status"] == "PASS" and checkpoint["status"] == "PASS" and checkpoint["all_counters_zero"],
    "forbidden_step_call_audit_PASS": step_audit["status"] == "PASS",
    "resource_forecast_PASS": resource["status"] == "PASS",
    "counters_zero": conditioning["new_optimizer_steps"] == conditioning["new_training_runs"] == conditioning["new_test_evaluations"] == 0,
}
status = "STATIC_FITTING_PROTOCOL_V02_READY" if all(gates.values()) else "STATIC_FITTING_PROTOCOL_V02_NOT_READY"

route = {
    "stage02mp_status": status,
    "Stage_02M_Q_authorized": status == "STATIC_FITTING_PROTOCOL_V02_READY",
    "authorized_scope": "Controlled Static Pair-Force Fitting v0.2 with New Sealed-Test Evaluation" if status == "STATIC_FITTING_PROTOCOL_V02_READY" else None,
    "direct_training_in_stage02mp_authorized": False,
    "stage02n_authorized": False,
    "rollout_authorized": False,
    "if_future_stage02mq_not_qualified": "terminate_static_PIO_learning_route_and_enter_method_summary_and_paper_boundary_evaluation",
    "historical_consumed_boundaries": {"BLIND_FAMILY_03": "consumed_historical_validation_only", "BLIND_FAMILY_04": "consumed_historical_test_only"},
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
}
write_json(ROOT / "route_termination/stage02mp_route_decision.json", route)

summary = {
    "status": status,
    "authorization_source": "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING",
    "protocol_sha256": protocol["protocol_sha256"],
    "supervision_scale": scale["a_sup"],
    "supervision_scale_hash": scale["result_hash"],
    "new_collection": collection["dataset_collection"],
    "record_count": inventory["record_count"],
    "lineage_component_count": lineage["family_count"],
    "conditioning_preflight": conditioning["status"],
    "harness": harness["status"],
    "resource_forecast": resource["status"],
    "test_seal": seal["status"],
    "Stage_02M_Q_authorized": route["Stage_02M_Q_authorized"],
    "gates": gates,
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
    "rollouts": 0,
    "historical_integrity": historical_integrity["status"],
}
write_json(ROOT / "results/stage02mp_final_summary.json", summary)

formula_table = "\n".join(["| family | role | root seed | formula hash |", "|---|---|---:|---|"] + [f"| {row['family_id']} | {row['role']} | {row['root_seed']} | `{row['formula_hash']}` |" for row in formulas["families"]])
conditioning_table = "\n".join(["| run | scaled loss | epsilon-dominated fraction | major modules |", "|---|---:|---:|---|"] + [f"| {row['run_id']} | {row['initial_scaled_loss']:.6f} | {row['parameter_weighted_epsilon_dominated_fraction']:.6f} | {'PASS' if row['major_module_gradient_gate_PASS'] else 'FAIL'} |" for row in conditioning["rows"]])

report("stage02mp_freeze_and_scope.md", f"""# Stage 02M-P — Freeze and scope

唯一授权来源为 Stage 02M-R `STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING`。Stage 02M verdict、Stage 02N=false 及 BLIND_FAMILY_03/04 consumed roles 保持不变。

历史冻结 {freeze['file_count']} 个直接输入，并复核 Stage 02M-R 的 285 个历史文件；阶段结束时历史完整性：**{historical_integrity['status']}**。本阶段只设计 protocol、物化新 blind data 并做 zero-step preflight，没有正式训练、checkpoint selection、model performance test 或 rollout。""")

report("stage02mp_failure_evidence_basis.md", """# Stage 02M-P — Failure-evidence basis

Stage 02M 的 164 个历史 checkpoint 均为 `NEVER_FIT_TRAIN`。Stage 02M-R 以 K1 两个 seed 的 head-only tangent 可达性，加上极小 loss、Adam epsilon 与 weight-decay dominance，将主失败源归因为 optimization conditioning。v0.2 只改变 supervision loss scale、Adam epsilon 与 weight decay；architecture、features、seed count、budget 和 success gates 不变，以隔离该机制。历史 validation/test metrics 未用于选择这些数值。""")

report("stage02mp_supervision_scale.md", f"""# Stage 02M-P — Train-only supervision scale

严格使用 10 个完整 train graphs、CPU float64、deterministic Kahan 和等图权计算：

`a_sup = {scale['a_sup']:.15f} m s^-2`

结果 hash `{scale['result_hash']}`，10 个 target-array hashes 和逐图能量均已保存。Historical validation/test target decode count 均为 0。a_sup 仅用于 output/supervision loss scaling，不作为输入特征、family ID 或 input normalization；旧 input-normalization hash仍为 `{normalization['statistics_hash']}`。""")

report("stage02mp_optimizer_conditioning_contract.md", """# Stage 02M-P — Optimizer conditioning contract

唯一 optimizer 为 AdamW：lr=1e-3、betas=(0.9,0.999)、epsilon=1e-12、weight_decay=0、global norm clip=1。相对 v0.1，仅把 epsilon 从 1e-8 改为 1e-12、weight decay 从 1e-6 改为 0，并用 train-only a_sup 替代 a0=400 的 loss scale。无 optimizer/epsilon/loss-scale/weight-decay grid，无 architecture-specific optimizer、restart 或 budget extension。""")

report("stage02mp_protocol_v02.md", f"""# Stage 02M-P — Protocol v0.2

Immutable protocol hash：`{protocol['protocol_sha256']}`。Hash 时 blind formula 文件不存在，且当前 YAML 复核不变：**{protocol_hash_unchanged}**。

K0/K1/K2 与 Stage 02K source/feature contract完全不变；新 seeds固定为 20261211/12/13。Maximum updates=1000、validation/checkpoint interval=20、min updates=300、patience=200、minimum improvement=1e-6，以及 Stage 02L success gates全部不变。协议顺序严格在 hash 后才物化 blind formulas。""")

report("stage02mp_blind_family_design.md", f"""# Stage 02M-P — Blind-family design

复用 Stage 02J-T/V generator source和mode/physics规则，无物理修改。两族均在 protocol hash 后按固定 root seed 单次物化，无重抽、替换或结果依赖 regeneration：

{formula_table}

每族恰有 N12/H2.6、N16/H2.6、N20/H2.6、N16/H2.2、N16/H3.0 五个完整图。""")

report("stage02mp_blind_reference_qualification.md", f"""# Stage 02M-P — Blind reference qualification

两族 10/10 cases 的 density positivity、Mach bound、closed-form derivative unit checks、Fourier/analytic acceptance、uncertainty与 deterministic repeat 均通过。最大 normalized Fourier/analytic L2 difference `{reference_max:.3e}`。这属于 reference/target 资格审计，不是 validation/test model performance evaluation。""")

report("stage02mp_blind_target_and_conservation.md", f"""# Stage 02M-P — Blind target and conservation

10/10 target identity、non-regularity resolution consistency、support consistency、temporal isolation与 frozen spatial-operator scope通过。最大 normalized total target-force residual `{force_max:.3e}`，最大 antisymmetric pair representability residual `{pair_max:.3e}`，均不超过 1e-10。

首轮脚本复现了已知 empty-set retention predicate错误；按既有冻结 Stage 02J-W 语义作 infrastructure correction 后通过。原失败证据保留，target hash不变，且未改科学阈值、公式、seed、role或generator physics。Regularity保持 diagnostic_only。""")

report("stage02mp_record_materialization.md", f"""# Stage 02M-P — Record materialization

新 collection `{collection['dataset_collection']}` 共 20 records：10 个 BLIND_FAMILY_01/02 train canonical records逐字节复用，5 个新 validation和5个新 sealed test records单次物化。Schema compatibility保持 `controlled_regular_pair_scope_v0_1`；20/20 schema、semantic、deterministic serialization与roundtrip QC通过。旧 v1.0 collection未覆盖。""")

report("stage02mp_split_and_test_seal.md", f"""# Stage 02M-P — Split and test seal

恰有 4 个 lineage components：train BLIND_FAMILY_01/02、validation V02_BLIND_VALIDATION_01、test V02_BLIND_TEST_01。Split 10/5/5，cross-split lineage=0；未采用 particle/edge/patch 或 resolution/support伪独立 split。

新 test seal 的 loader/direct-path/wildcard/metric-evaluator denial全部通过；test_target_access=false，test target decode=0，且未生成 test_release_manifest。BLIND_FAMILY_03/04 不进入新 collection，继续分别是 consumed historical validation/test only。""")

report("stage02mp_static_conditioning_preflight.md", f"""# Stage 02M-P — Static conditioning preflight

{conditioning_table}

9/9 finite forward/backward通过。K1/K2 的 scaled loss范围 `{min(loss_values):.6f}`–`{max(loss_values):.6f}`，epsilon-dominated fraction范围 `{min(epsilon_values):.6f}`–`{max(epsilon_values):.6f}`，均满足预冻结门；weight-decay-dominated fraction=0，所有主要模块 finite nonzero gradient fraction≥0.10。参数 hash未变，optimizer/scheduler step为0。""")

report("stage02mp_resource_forecast.md", f"""# Stage 02M-P — Resource forecast

Zero-step full-batch forward/backward 平均 `{resource['zero_step_mean_seconds']:.4f}` s，预测 9-run wall `{resource['forecast_nine_run_wall_seconds']:.1f}` s、peak RSS `{resource['forecast_peak_RSS_bytes']/1024**3:.3f}` GiB、checkpoint storage `{resource['forecast_checkpoint_storage_bytes']/1024**3:.3f}` GiB。1.5 GiB/10 GiB硬门通过；edge-local O(E d)，无 O(N²) allocation或切图规避，finite completion forecast PASS。""")

report("stage02mp_success_criteria.md", f"""# Stage 02M-P — Success criteria

训练门保持 train Q_L2≤0.25；validation family mean≤0.90且每图≤1.10；test family mean≤0.90且每图≤1.10；均采用 2/3 seed rule。未依据 Stage 02M 放宽。

Stage 02M-P readiness gates：{json.dumps(gates, sort_keys=True)}。最终：**{status}**。只有该状态才有限授权 Stage 02M-Q；Stage 02M-P 本身不授权 optimizer steps。""")

report("stage02mp_final_report.md", f"""# Stage 02M-P — Final report

## Final status

**{status}**

1. Stage 02M failure preserved：`STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`。
2. Stage 02M-R attribution preserved：`STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING`。
3. Train-only supervision scale：`a_sup={scale['a_sup']:.15f} m s^-2`，10 graphs、Kahan、等图权。
4. Output scale与input normalization严格分离；旧 hash `{normalization['statistics_hash']}` 原样复用。
5. v0.2 loss：10 个 complete train graphs 的 scaled node-vector MSE等图平均。
6. Adam epsilon/weight decay：1e-12 / 0；无 grid。
7. Architecture/features：Stage 02K K0/K1/K2完全不变，KNEG不训练。
8. New run seeds：20261211、20261212、20261213，共9 prospective runs。
9. Budget/success gates：保持 Stage 02L 原值，无放宽或延期。
10. Protocol freeze：hash `{protocol['protocol_sha256']}`，公式在 hash 后生成。
11. New blind validation formula：V02_BLIND_VALIDATION_01 / 2026080501 / `{formulas['families'][0]['formula_hash']}`。
12. New blind test formula：V02_BLIND_TEST_01 / 2026080502 / `{formulas['families'][1]['formula_hash']}`。
13. Reference/target/conservation：10/10 PASS；最大 force/pair residual `{force_max:.3e}` / `{pair_max:.3e}`。
14. v1.1 collection：`{collection['dataset_collection']}`，20 records完整。
15. Lineage/split：4 components，10 train / 5 validation / 5 test，无 cross-split lineage。
16. Input normalization：旧统计 hash复用，train record hashes一致，未 refit。
17. New test seal：4项 denial PASS；access=false；未生成 release manifest。
18. Zero-step conditioning：9/9 PASS；K1/K2 loss `[0.1,10]`、epsilon≤0.25、WD=0、主要模块梯度门通过。
19. Checkpoint/harness：9/9 zero-step roundtrip、RNG、next-forward、counter=0、resume dry run、gradient/reorder均 PASS；最大 gradient-equivalence error `{max(gradient_errors):.3e}`。
20. Resource forecast：PASS；RSS/storage/O(N²)/finite completion全部过门。
21. Stage 02M-Q authorization：**{route['Stage_02M_Q_authorized']}**，仅限 Controlled Static Pair-Force Fitting v0.2 with New Sealed-Test Evaluation。
22. `new_optimizer_steps = 0`。
23. `new_training_runs = 0`。
24. `new_test_evaluations = 0`。
25. `rollouts = 0`；无 solver-in-the-loop。
26. Consumed historical boundary：BLIND_FAMILY_03/04仅作 historical validation/test，不进入v1.1。
27. Historical hashes unchanged：Stage 02M-R 285-file复核及本阶段直接冻结输入均 **{historical_integrity['status']}**。

Stage 02M-P没有正式训练、checkpoint selection、validation/test performance evaluation或Stage 01 recovery claim。若未来 Stage 02M-Q 仍不 qualified，当前 static PIO learning route终止并进入方法总结与论文边界评估。""")

report_names = [
    "stage02mp_freeze_and_scope.md", "stage02mp_failure_evidence_basis.md", "stage02mp_supervision_scale.md",
    "stage02mp_optimizer_conditioning_contract.md", "stage02mp_protocol_v02.md", "stage02mp_blind_family_design.md",
    "stage02mp_blind_reference_qualification.md", "stage02mp_blind_target_and_conservation.md", "stage02mp_record_materialization.md",
    "stage02mp_split_and_test_seal.md", "stage02mp_static_conditioning_preflight.md", "stage02mp_resource_forecast.md",
    "stage02mp_success_criteria.md", "stage02mp_final_report.md",
]
artifacts = sorted(path for path in ROOT.rglob("*") if path.is_file() and path.name != "stage02mp_run_manifest.json") + [REPORTS / name for name in report_names]
write_json(ROOT / "manifests/stage02mp_run_manifest.json", {
    "manifest_version": "stage02mp-run-1.0.0",
    "status": status,
    "protocol_sha256": protocol["protocol_sha256"],
    "artifact_count": len(artifacts),
    "artifacts": [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "bytes": path.stat().st_size} for path in artifacts],
    "new_optimizer_steps": 0,
    "new_training_runs": 0,
    "new_test_evaluations": 0,
    "historical_integrity": historical_integrity["status"],
})
print(json.dumps(summary, sort_keys=True))
