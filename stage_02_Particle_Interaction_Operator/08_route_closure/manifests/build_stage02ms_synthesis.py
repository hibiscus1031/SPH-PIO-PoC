#!/usr/bin/env python3
"""Build Stage 02M-S machine ledgers and publication-boundary reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "08_route_closure"
REPORTS = STAGE / "07_reports"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def write_md(name: str, text: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / name).write_text(text.rstrip() + "\n")


for name in ("status_ledger", "evidence_matrix", "claim_boundary", "failure_taxonomy", "manuscript_assessment", "figure_plan", "future_branches", "manifests"):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

freeze_path = ROOT / "freeze/stage02ms_historical_freeze_manifest.json"
freeze = json.loads(freeze_path.read_text())
if freeze["status"] != "PASS":
    raise RuntimeError("Stage 02M-S historical freeze is not PASS")
source_map = freeze["stage_status_sources"]

stage_specs = [
    ("Stage 02A", "PIO_THEORY_QUALIFICATION_COMPLETE", "冻结 PIO 增量形式、reference hierarchy、守恒/对称与标签资格合同。", "Stage 01 最终边界与理论合同", 0, "protocol_only", 0, 0, "理论合同完整；未生成数据或模型。", "尚无可训练 target/dataset。", "Stage 02B 协议设计", "数学合同不等于模型有效性或性能。", "initial_contract"),
    ("Stage 02B", "DATASET_QUALIFICATION_COMPLETE", "定义 reference-to-target、schema、leakage/split 和 uncertainty 协议。", "Stage 02A 合同", 0, "protocol_only", 0, 0, "数据资格协议与 schema 完成。", "未生成数据，完成协议不授权生成或训练。", "Stage 02C audit-scale generation", "协议 PASS 不是数据资格 PASS。", "extends_02A_without_superseding"),
    ("Stage 02C", "DATASET_GENERATION_AUDIT_COMPLETE", "执行小规模 R2 数据生成与 provenance 审计。", "Stage 02B generation contract", 1, "audit_generation_campaign", 0, 0, "3 reference records、6 samples；4 diagnostic、2 topology rejected。", "eligible_for_future_training=0。", "Stage 02D target attribution audit", "R2 记录默认仅为诊断，不是训练标签。", "extends_02B_without_superseding"),
    ("Stage 02D", "TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE", "分解 space/time/reference/forcing/model-form/cross 误差并冻结升级门。", "Stage 02C six-sample corpus", 1, "six_sample_attribution_campaign", 0, 0, "6/6 完成分解；4 diagnostic、2 rejected。", "0 attribution PASS；resolution/disorder 混杂。", "Stage 02E controlled excitation only", "完成归因程序不等于目标已归因。", "extends_02C_without_superseding"),
    ("Stage 02E", "TARGET_CONSTRUCTION_COMPLETE", "构造八个非零候选并审查 temporal/reference contamination。", "Stage 02D failure-preserving design", 1, "eight_case_target_campaign", 0, 0, "8/8 非零且 reference audit 完整。", "空间 assembly 为零/roundoff，时间/reference derivative 主导；0 qualified。", "Stage 02F semidiscrete spatial route only", "非零 target 不自动是空间离散 target。", "new_target_hypothesis_without_overwriting_02D"),
    ("Stage 02F", "SPATIAL_TARGET_QUALIFICATION_COMPLETE", "定义 R2S same-state semidiscrete spatial target 并评估 resolution/support。", "Stage 02E preserved + R2S contract", 1, "five_candidate_spatial_campaign", 0, 0, "5 个非零 same-state spatial candidates；support 与 reference gates 完成。", "resolution smoothness 仍 diagnostic；0 qualified。", "Stage 02G attribution closure", "程序完成不代表六分量 attribution PASS。", "extends_02E_without_superseding"),
    ("Stage 02G", "SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE", "审查 R2S bias 并扩展预选 resolution path。", "Stage 02F candidates and frozen smoothness", 1, "refinement_and_bias_campaign", 0, 0, "R2S bias、refinement、4/6 attribution 完整。", "R2S bias relative to target 可测但未受控；仍 diagnostic。", "Stage 02H independent reference qualification", "诊断闭包不升级历史 candidate。", "closure_of_R2S_route_without_superseding"),
    ("Stage 02H", "REFERENCE_FIDELITY_QUALIFICATION_COMPLETE", "比较 Fourier、analytic、QWLS2、CWLS3 references。", "Stage 02G/H preregistered reference matrix", 1, "four_reference_candidate_campaign", 0, 0, "Fourier 与 analytic 在受控 periodic-vortex scope 内独立一致并 PASS。", "不授权 dataset；QWLS2/CWLS3 仍 diagnostic。", "Stage 02I target pool qualification", "reference PASS 仅限冻结空间算子与 case scope。", "independent_reference_branch"),
    ("Stage 02I", "QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY", "用独立 reference 构建七个归因目标并审查 conservation compatibility。", "Stage 02H accepted references", 1, "seven_target_campaign", 0, 0, "7/7 six-component attribution PASS；5 pair-compatible、2 node-residual-only。", "守恒兼容性不完整，Stage 02J 未授权。", "Stage 02I-R scope resolution", "目标归因 PASS 不等于 pair-force scope 全部可用。", "extends_02H_without_superseding"),
    ("Stage 02I-R", "CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY", "分解总力残差并选择 pair-only regular scope。", "Stage 02I seven-target pool", 1, "conservation_scope_audit", 0, 0, "五个 regular targets 确认 pair-only；jitter 保留诊断。", "未形成 versioned dataset/split/normalization。", "Stage 02J limited regular dataset construction", "scope resolution 不覆盖 Stage 02I NOT READY。", "resolution_stage_not_superseding_02I"),
    ("Stage 02J", "CONTROLLED_REGULAR_DATASET_NOT_READY", "物化五个 regular graph records 并审查 split feasibility。", "Stage 02I-R pair-only candidates", 1, "five_record_dataset_campaign", 0, 0, "5 records schema/canonical/QC 完整。", "单一 leakage component，无法合法切分；0 eligible。", "Stage 02J-R independent family attempt", "受控 corpus 不是 train-ready dataset。", "failed_dataset_version_v0_1_preserved"),
    ("Stage 02J-R", "MULTIFAMILY_CONTROLLED_DATASET_NOT_READY", "预注册三条新 lineage 并尝试多家族 target qualification。", "Stage 02J preserved records + frozen families", 1, "fifteen_candidate_multifamily_campaign", 0, 0, "15 candidates reference/conservation PASS，lineages 分离。", "regularity attribution 5/6 diagnostic，未物化；split/normalization blocked。", "Stage 02J-S versioned regularity contract", "未物化候选不能计为数据记录。", "failed_dataset_version_v0_2_preserved"),
    ("Stage 02J-S", "VERSIONED_MULTIFAMILY_DATASET_NOT_READY", "验证 graph-Sobolev regularity v0.2 与负控制。", "Stage 02J-R candidates + frozen v0.2 contract", 1, "development_regularity_campaign", 0, 0, "structured development paths PASS；80 invariance checks PASS。", "negative-control false-positive gate failed；held-out 未释放。", "Stage 02J-T single v0.3 candidate", "开发集规律不能替代 blind qualification。", "failed_regularity_version_v0_2_preserved"),
    ("Stage 02J-T", "REGULARITY_GATE_V03_NOT_QUALIFIED", "检验 magnitude-direction conjunction v0.3。", "Stage 02J-S preserved + single candidate preregistration", 1, "v0_3_regularity_campaign", 0, 0, "30 control combinations与 invariance 完成。", "CROSSMODE N12 magnitude gate failure；blind gate未开启。", "Stage 02J-V final necessity audit", "局部 PASS 不生成最终 v0.3 contract。", "failed_regularity_version_v0_3_preserved"),
    ("Stage 02J-V", "REGULARITY_HARD_GATE_ROUTE_TERMINATED", "执行最后的 necessity/Bonferroni regularity 候选并关闭硬门路线。", "Stage 02J-T preserved + v0.4 candidate", 1, "v0_4_regularity_campaign", 0, 0, "positive/hard-negative controls 与 real targets 完整。", "9/192 invariance rows失败；禁止 v0.5。", "Stage 02J-W alternate eligibility route with regularity diagnostic-only", "route terminated 不等于数据或架构失败。", "terminal_regularity_route_state"),
    ("Stage 02J-W", "BLIND_MULTIFAMILY_DATASET_READY", "在 regularity diagnostic-only 合同下构建 blind multifamily dataset。", "Stage 02J-V termination + frozen blind generator", 1, "twenty_record_blind_dataset_campaign", 0, 0, "20/20 reference/target/conservation/QC PASS；4 lineage components；10/5/5 split；train-only normalization。", "仅静态 pair-scope 数据；不含 solver/rollout evidence。", "Stage 02K architecture qualification", "READY 不覆盖 J/J-R/J-S/J-T 的历史失败。", "alternate_eligibility_contract_not_superseding_regularity_failures"),
    ("Stage 02K", "PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED", "资格化 K1 pair MLP 与 K2 reciprocal attention PIO 的结构合同。", "Stage 02J-W ready dataset and frozen normalization", 1, "architecture_hard_gate_campaign", 0, 0, "K1/K2 antisymmetry、momentum、O(2)、periodicity、differentiability、O(E d) PASS。", "未训练；结构正确性不证明 learnability。", "Stage 02L protocol preregistration only", "K0 diagnostic；attention necessity 未建立。", "architecture_contract_version_v0_1"),
    ("Stage 02L", "STATIC_FITTING_PROTOCOL_READY", "预注册 v0.1 九运行静态拟合、测试封存与门槛。", "Stage 02K qualified architectures + v1.0 dataset", 0, "preregistration_only", 0, 0, "协议、loss、optimizer、checkpoint、test seal 完整。", "尚无训练结果。", "Stage 02M formal static fitting", "READY 不是拟合成功。", "training_protocol_v0_1"),
    ("Stage 02M", "STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED", "执行 v0.1 K0/K1/K2 × 3 seeds 静态拟合与一次性测试。", "Stage 02L protocol hash and sealed test", 9, "formal_training_runs", 9, 8020, "9/9 runs、sealed test、postfit、resources 完整。", "K1/K2 未满足冻结 A-E，训练拟合失败。", "Stage 02M-R failure attribution only", "validation/test局部结果不覆盖 train-fit failure。", "failed_training_protocol_v0_1_preserved"),
    ("Stage 02M-R", "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING", "对 v0.1 失败做 post-hoc、无新训练的唯一归因。", "Stage 02M frozen histories/checkpoints", 1, "forensic_diagnostic_campaign", 0, 0, "loss scale、Adam epsilon/weight decay、梯度/更新尺度证据一致。", "归因是 diagnostic contribution，不证明改参必成功。", "Stage 02M-P one prospective v0.2 design", "不覆盖 M 的 NOT QUALIFIED。", "posthoc_attribution_not_verdict_replacement"),
    ("Stage 02M-P", "STATIC_FITTING_PROTOCOL_V02_READY", "冻结 a_sup、AdamW conditioning 修复、新 blind families 与唯一重试协议。", "Stage 02M-R authorization and zero-step diagnostics", 0, "preregistration_only", 0, 0, "v0.2 protocol、a_sup、9-run matrix、v1.1 collection、test seal READY。", "无训练；仅授权一次 02M-Q。", "Stage 02M-Q unique formal retry", "conditioning readiness 不是 learnability evidence。", "training_protocol_v0_2"),
    ("Stage 02M-Q", "STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED", "执行唯一 v0.2 九运行静态拟合重试并关闭路线。", "Stage 02M-P protocol hash and v1.1 sealed test", 9, "formal_training_runs", 9, 8440, "9/9 conditioning/terminal/closure/test/postfit/resource evidence完整；C/D/E gates PASS。", "K1 train gate 0/3、K2 train gate 1/3；均未达 B 的2/3。", "Stage 02M-S closure only; Stage 02N unauthorized", "静态失败不等于 rollout failure；rollout从未执行。", "failed_training_protocol_v0_2_terminal_route_state"),
]

ledger_rows = []
for order, spec in enumerate(stage_specs, 1):
    stage, status, purpose, input_freeze, execution_count, execution_unit, training_runs, optimizer_steps, evidence, blocker, authorization, boundary, relation = spec
    source = source_map[stage]
    ledger_rows.append({
        "order": order,
        "stage": stage,
        "unique_status": status,
        "purpose": purpose,
        "input_freeze": input_freeze,
        "execution_count": execution_count,
        "execution_unit": execution_unit,
        "optimizer_steps": optimizer_steps,
        "training_runs": training_runs,
        "principal_evidence": {"summary": evidence, "artifact": source["path"]},
        "principal_blocker": blocker,
        "downstream_authorization": authorization,
        "historical_hash": source["sha256"],
        "superseded": False,
        "version_relationship": relation,
        "scientific_interpretation_boundary": boundary,
    })
ledger = {
    "ledger_version": "stage02-complete-status-ledger-1.0.0",
    "chronology_rule": "later states extend or branch from earlier states and never overwrite historical failures",
    "stage_count": len(ledger_rows),
    "rows": ledger_rows,
    "terminal_route_state": {
        "Stage_02M_Q": "STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED",
        "static_pio_learning_route_terminated": True,
        "Stage02N_authorized": False,
        "training_protocol_v03_permitted": False,
        "rollout_authorized": False,
        "solver_in_the_loop_authorized": False,
    },
    "status": "PASS" if len(ledger_rows) == 22 and all(not row["superseded"] for row in ledger_rows) else "FAIL",
}
write_json(ROOT / "status_ledger/stage02_complete_status_ledger.json", ledger)

def ev(identifier: str, claim_class: str, claim: str, level: str, artifact: str, limitations: str, publishable: bool, confirmatory: bool, diagnostic: bool, negative: bool, prohibited: str) -> dict[str, object]:
    path = REPO / artifact
    return {"id": identifier, "claim_class": claim_class, "claim": claim, "evidence_level": level, "supporting_artifact": artifact, "supporting_artifact_sha256": sha(path), "limitations": limitations, "publishable": publishable, "confirmatory": confirmatory, "diagnostic": diagnostic, "negative_result": negative, "prohibited_extrapolation": prohibited}

evidence_rows = [
    ev("A1", "Numerics/reference", "MMS 与半离散时间 reference 验证链已建立。", "qualified_with_stage01_failure_boundary", "07_reports/stage_01f5b_final_report.md", "不覆盖独立 shear V2 failure。", True, True, False, False, "不得声称 V2 全面验证通过"),
    ev("A2", "Numerics/reference", "Fourier 与 analytic reference 在冻结 periodic-vortex scope 内独立一致。", "confirmatory_scope_limited", "stage_02_Particle_Interaction_Operator/07_reports/stage02h_final_report.md", "仅限冻结空间算子、周期涡旋与 case matrix。", True, True, False, False, "不得外推为任意流动真值"),
    ev("A3", "Numerics/reference", "七个 spatial targets 完成 six-component attribution。", "qualified_candidate_level", "stage_02_Particle_Interaction_Operator/07_reports/stage02i_final_report.md", "其中2个 jitter 不满足 pair-force global residual。", True, True, False, False, "不得将全部七个用于 pair-force training"),
    ev("A4", "Numerics/reference", "resolution consistency 在最终 blind families 的冻结路径通过。", "confirmatory_dataset_scope", "stage_02_Particle_Interaction_Operator/07_reports/stage02jw_target_qualification.md", "无连续收敛阶或任意高分辨率 truth 结论。", True, True, False, False, "不得声称高分辨率 SPH 就是真值"),
    ev("A5", "Numerics/reference", "support consistency 在最终 blind families 通过。", "confirmatory_dataset_scope", "stage_02_Particle_Interaction_Operator/07_reports/stage02jw_target_qualification.md", "仅覆盖预注册 H/dx 组合。", True, True, False, False, "不得外推至任意 kernel/support"),
    ev("A6", "Numerics/reference", "reference uncertainty、roundoff 与 deterministic evidence 已逐阶段保留。", "audited", "stage_02_Particle_Interaction_Operator/04_target_attribution/reference_sensitivity/reference_sensitivity_budget.json", "没有单一 universal uncertainty/GCI。", True, True, False, False, "不得把 uncertainty 当作已消除"),
    ev("B1", "Dataset", "四个 blind families 按冻结 seed/formula 单次生成。", "confirmatory", "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_final_manifest.json", "仅20个完整 graphs。", True, True, False, False, "不得称为大规模数据集"),
    ev("B2", "Dataset", "family lineage 独立且 leakage graph 为四个 components。", "confirmatory", "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/leakage/leakage_graph.json", "共同代码/EOS 是 infrastructure，不是样本独立性。", True, True, False, False, "不得把粒子数当统计样本数"),
    ev("B3", "Dataset", "prefrozen train/validation/test=10/5/5 split 无跨 split lineage。", "confirmatory", "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/splits/prefrozen_split_manifest.json", "每个 validation/test 仅一个 family。", True, True, False, False, "不得当作广泛分布泛化"),
    ev("B4", "Dataset", "输入 normalization 仅由10个 train graphs 拟合。", "confirmatory", "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/normalization/train_only_graph_balanced_statistics.json", "监督尺度 v0.2 是另一个 train-only统计。", True, True, False, False, "不得混用 validation/test 统计"),
    ev("B5", "Dataset", "20/20 records 在 Stage 02J-W eligibility contract 下 PASS。", "confirmatory_contract_specific", "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_dataset_manifest.json", "regularity effect 明确为 none/diagnostic。", True, True, False, False, "不得覆盖 J/J-R/J-S/J-T 历史失败"),
    ev("C1", "Architecture", "K1/K2 pair-force construction 硬编码 pair antisymmetry 与线性动量守恒。", "confirmatory_structural", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json", "不保证静态可学习性或动态稳定性。", True, True, False, False, "不得称为 solver 改进"),
    ev("C2", "Architecture", "K1/K2 permutation/edge reorder、translation/Galilean、O(2)、periodicity gates PASS。", "confirmatory_structural", "stage_02_Particle_Interaction_Operator/07_reports/stage02k_qualification_report.md", "只在冻结 metamorphic matrix 与 float64 tolerance 下。", True, True, False, False, "不得声称任意几何泛化"),
    ev("C3", "Architecture", "K1/K2 differentiability 与 edge-local O(E d) resource scaling PASS。", "confirmatory_structural", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/resource_audit/resource_results.json", "未测 solver-wide scaling。", True, True, False, False, "不得声称 solver 加速"),
    ev("C4", "Architecture", "directed-softmax negative control 暴露非互易 attention 的守恒失败。", "confirmatory_negative_control", "stage_02_Particle_Interaction_Operator/07_reports/stage02k_final_report.md", "并不证明 reciprocal attention 优于所有非-attention 模型。", True, True, False, True, "不得声称 Transformer 必要"),
    ev("D1", "Learning", "v0.1 九运行静态拟合未满足冻结资格门。", "confirmatory_negative_result", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_1/results/stage02m_qualification_summary.json", "仅静态同任务 protocol v0.1。", True, True, False, True, "不得改写为 rollout failure"),
    ev("D2", "Learning", "v0.1 failure 的主要可审计贡献被归因为 optimization conditioning。", "diagnostic_attribution", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_failure_attribution_v0_1/results/failure_attribution.json", "post-hoc attribution；不证明修复充分。", True, False, True, True, "不得声称唯一科学原因已证明"),
    ev("D3", "Learning", "v0.2 改善 conditioning，并使 K1/K2 validation/test transfer gates 3/3 PASS。", "descriptive_confirmatory", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json", "train-fit B gate仍失败；新旧 families 非 paired benchmark。", True, True, False, True, "不得把 transfer gate PASS 画成模型成功"),
    ev("D4", "Learning", "v0.2 K1 train gate 0/3，K2 train gate 1/3，均未达到2/3。", "confirmatory_negative_result", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_frozen_success_gate_evaluation.json", "只支持冻结静态协议的失败。", True, True, False, True, "不得宣称所有神经 correction 不可学习"),
    ev("D5", "Learning", "v0.2 test release合规且9个selected checkpoints各评一次。", "confirmatory_provenance", "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/test_evaluation/stage02mq_sealed_test_evaluation.json", "test通过不能覆盖 train-fit failure。", True, True, False, False, "不得重新评价或选择 checkpoint"),
    ev("D6", "Learning", "静态 PIO learning route 已终止。", "terminal_decision", "stage_02_Particle_Interaction_Operator/07_reports/stage02mq_final_report.md", "终止仅针对当前 static delta_a learning hypothesis 与两份协议。", True, True, False, True, "不得写成 rollout或solver-in-loop失败"),
]
evidence_matrix = {"matrix_version": "stage02-complete-evidence-matrix-1.0.0", "claim_count": len(evidence_rows), "rows": evidence_rows, "all_supporting_artifacts_present": all((REPO / row["supporting_artifact"]).is_file() for row in evidence_rows), "status": "PASS"}
write_json(ROOT / "evidence_matrix/stage02_complete_evidence_matrix.json", evidence_matrix)

failure_classes = [
    {"id": 1, "name": "numerical verification failure", "definition": "冻结数值/独立基准硬门未通过。", "instances": [{"stage": "Stage 01G", "state": "FAIL", "evidence": "V2_QUALIFICATION_FAIL; shear failed"}], "not_instances": ["Stage 02M-Q static learnability failure"]},
    {"id": 2, "name": "resource/infrastructure failure", "definition": "执行因资源或基础设施不能完成；受控恢复不改变科学状态。", "instances": [{"stage": "Stage 02C/02J-W", "state": "DIAGNOSTIC", "evidence": "retained controlled infrastructure retry"}], "not_instances": ["02M/02M-Q resources PASS"]},
    {"id": 3, "name": "reference-construction failure", "definition": "reference 与目标模型/状态/不确定性合同不满足。", "instances": [{"stage": "Stage 02E", "state": "NOT QUALIFIED", "evidence": "temporal/reference derivative dominated nonzero candidates"}], "not_instances": ["Stage 02H Fourier-analytic PASS"]},
    {"id": 4, "name": "attribution failure", "definition": "候选差异无法通过预注册分量归因。", "instances": [{"stage": "Stage 02D/02F/02G", "state": "DIAGNOSTIC", "evidence": "0 qualified then 4/6 diagnostic closure"}], "not_instances": ["Stage 02I seven 6/6 candidates"]},
    {"id": 5, "name": "conservation-scope failure", "definition": "target 不满足所选 pair-force global residual范围。", "instances": [{"stage": "Stage 02I", "state": "NOT QUALIFIED", "evidence": "2 jitter node-residual-only"}], "not_instances": ["five regular pair-only targets"]},
    {"id": 6, "name": "family/leakage failure", "definition": "lineage components不足以形成合法 split。", "instances": [{"stage": "Stage 02J/02J-R", "state": "NOT QUALIFIED", "evidence": "one realized leakage component; no eligible split"}], "not_instances": ["Stage 02J-W four components PASS"]},
    {"id": 7, "name": "regularity-contract failure", "definition": "预注册 regularity hard gate或其 invariance/controls失败。", "instances": [{"stage": "Stage 02J-S/J-T/J-V", "state": "NOT QUALIFIED", "evidence": "negative-control, magnitude, then invariance failures"}], "not_instances": ["regularity diagnostic-only registry in J-W"]},
    {"id": 8, "name": "optimization-conditioning failure", "definition": "loss/optimizer数值尺度导致有效更新不利。", "instances": [{"stage": "Stage 02M-R", "state": "DIAGNOSTIC", "evidence": "v0.1 failure attributed to conditioning contribution"}], "not_instances": ["proof that v0.2 must succeed"]},
    {"id": 9, "name": "static learnability failure", "definition": "完整预注册静态训练未满足资格门。", "instances": [{"stage": "Stage 02M", "state": "NOT QUALIFIED", "evidence": "v0.1 A-E failed"}, {"stage": "Stage 02M-Q", "state": "NOT QUALIFIED", "evidence": "K1 B=0/3; K2 B=1/3"}], "not_instances": ["universal impossibility of learned SPH corrections"]},
    {"id": 10, "name": "dynamic evidence absence", "definition": "动态证据从未授权或执行，不是失败结果。", "instances": [{"stage": "Stage 02M-Q", "state": "NOT AUTHORIZED / NOT EXECUTED", "evidence": "rollout=0; solver-in-loop=0"}], "not_instances": ["rollout failed", "solver unstable"]},
]
taxonomy = {"taxonomy_version": "stage02ms-failure-taxonomy-1.0.0", "status_semantics": {"FAIL": "执行了适用硬门且未通过", "NOT QUALIFIED": "完成资格程序但未满足完整资格条件", "NOT AUTHORIZED": "上游门未开放，禁止执行", "NOT EXECUTED": "没有产生该类实验或证据", "EVIDENCE INCOMPLETE": "必要 provenance/矩阵/闭包缺失", "DIAGNOSTIC": "仅用于解释或风险定位，不构成硬门 PASS"}, "classes": failure_classes, "rollout_semantic_guard": "NOT AUTHORIZED_AND_NOT_EXECUTED; never write rollout failed", "status": "PASS"}
write_json(ROOT / "failure_taxonomy/stage02_failure_taxonomy.json", taxonomy)

supported = [
    ("构建了 reference-qualified、lineage-disconnected 的 blind multifamily pair-scope dataset。", "在冻结 periodic-vortex、20-graph、pair-scope 下构建并资格化了 blind multifamily dataset。", "构建了适用于任意流动的大规模 truth dataset。"),
    ("pair-force architectures 强制离散线性动量守恒。", "K1/K2 的互易 pair-force 构造在冻结合同下满足反对称与全局线性动量。", "模型因此动态稳定或精确。"),
    ("K1/K2 满足冻结的 O(2)、periodicity、permutation 与 Galilean contracts。", "在预注册 metamorphic matrix 与 float64 tolerance 下结构门 PASS。", "可泛化到任意几何或任意分布。"),
    ("两个预注册静态拟合协议均未达到 train-fit qualification。", "v0.1 与 v0.2 均按原门槛判为 NOT QUALIFIED。", "所有 learned corrections 都不可学习。"),
    ("架构正确性不蕴含静态可学性。", "结构硬门 PASS 与两次静态训练资格失败同时成立。", "结构合同无价值。"),
    ("测试封存与一次性释放机制可审计。", "两轮 protocol 均保留选择闭包与 sealed-test provenance。", "test PASS 证明模型成功。"),
]
conditional = [
    ("optimization conditioning 对 v0.1 failure 有重要贡献。", "诊断显示 loss scale、epsilon 与 weight decay 共同限制有效更新；这是贡献性归因。", "优化条件是唯一根因。"),
    ("v0.2 改善 conditioning 与 transfer gates。", "相对 v0.1 可描述 conditioning 与 frozen gate pattern 改善。", "v0.2 在统计上显著优于 v0.1。"),
    ("当前 local feature-to-coefficient mapping 可能仍难以识别。", "结合 K1/K2 train-fit seed counts 作为待检验机制。", "已证明 feature identifiability 不可能。"),
]
unsupported = [
    ("learned correction improves SPH", "当前没有 solver/rollout性能证据。", "学习修正已提高 SPH 精度。"),
    ("learned model restores V2", "Stage 01 仍为 V2_QUALIFICATION_FAIL。", "模型恢复了 V2。"),
    ("attention is superior", "K2 无2/3 train-fit，且新旧协议非架构优越性试验。", "attention 优于 MLP。"),
    ("Transformer is necessary", "没有 necessity ablation；K2 是 reciprocal attention，不构成 Transformer 必要性。", "Transformer 是必要条件。"),
    ("rollout is stable", "rollout 未授权、未执行。", "rollout 稳定/失败。"),
    ("solver is accelerated", "无 solver-in-loop 或 wall-clock comparison。", "solver 被加速。"),
    ("arbitrary-flow generalization", "families与物理范围有限。", "泛化到任意流动。"),
    ("viscosity operator is confirmed", "Stage 01H 仍为 NOT_CONFIRMED。", "黏性算子形式已确认/否定。"),
    ("high-resolution SPH is truth", "reference hierarchy 明确反对按分辨率排序真值。", "最高分辨率即 truth。"),
]
claim_boundary = {"boundary_version": "stage02ms-claim-boundary-1.0.0", "supported_claims": [{"claim": c, "allowed_wording": a, "prohibited_wording": p} for c, a, p in supported], "conditional_claims": [{"claim": c, "allowed_wording": a, "prohibited_wording": p} for c, a, p in conditional], "unsupported_claims": [{"claim": c, "allowed_wording": a, "prohibited_wording": p} for c, a, p in unsupported], "status": "PASS"}
write_json(ROOT / "claim_boundary/stage02_claim_boundary.json", claim_boundary)

papers = [
    {"paper": "Paper A", "direction": "Transformer/Attention-corrected SPH solver", "novelty": "potentially high but unsubstantiated", "evidence_completeness": "low", "required_missing_evidence": ["qualified trained model", "prospective one-step correction benefit", "stable solver-in-loop rollouts", "accuracy/conservation/cost comparison across flows"], "strongest_supported_contribution": "reciprocal attention architecture satisfies structural contracts", "fatal_weakness": "no qualified static model and no solver-performance evidence", "suitable_claim_level": "architecture design and negative static result only", "manuscript_readiness": "NOT_READY", "current_CMAME_target_defensible": False},
    {"paper": "Paper B", "direction": "V&V-first qualification framework for conservative learned SPH corrections", "novelty": "high in end-to-end falsifiable qualification workflow", "evidence_completeness": "medium-high for methodology, low for external generality", "required_missing_evidence": ["replication on multiple mechanics regimes", "independent implementation or external benchmark", "comparison with simpler conservative baselines"], "strongest_supported_contribution": "hash-addressed staged qualification from reference hierarchy through sealed negative fitting", "fatal_weakness": "single problem family and no demonstration that framework changes a solver outcome", "suitable_claim_level": "methodology plus falsification case study", "manuscript_readiness": "DRAFTABLE_AFTER_SYNTHESIS", "current_CMAME_target_defensible": False},
    {"paper": "Paper C", "direction": "Negative-result study on architecture validity versus static learnability", "novelty": "moderate-high if framed as falsification and reproducibility", "evidence_completeness": "high for the two frozen static protocols", "required_missing_evidence": ["broader task replication", "non-neural/low-dimensional baseline", "mechanistic identifiability analysis"], "strongest_supported_contribution": "structural correctness and transfer gates coexist with preregistered train-fit failure", "fatal_weakness": "one dataset scope cannot establish general architecture-versus-learnability law", "suitable_claim_level": "carefully bounded negative-result paper", "manuscript_readiness": "DRAFTABLE", "current_CMAME_target_defensible": False},
]
assessment = {
    "assessment_version": "stage02ms-manuscript-readiness-1.0.0",
    "CMAME_scope_source": "https://www.sciencedirect.com/journal/computer-methods-in-applied-mechanics-and-engineering",
    "CMAME_scope_interpretation": "CMAME targets significant developments in computational methods for applied mechanics; machine learning is in scope, but the current evidence does not yet demonstrate a significant solver method outcome or broad mechanics validation.",
    "papers": papers,
    "recommended_primary_line": "Paper B + Paper C hybrid: V&V-first methodology demonstrated through a fully preserved falsified static-learning route",
    "working_title": "Verification- and qualification-first development of conservative learned correction operators for SPH: from reference construction to falsified static fitting",
    "complete_journal_paper_possible": True,
    "best_article_type": "methodology_and_negative_results",
    "current_CMAME_readiness": "NOT_YET_DEFENSIBLE",
    "three_critical_missing_evidence": ["跨多个力学流态/问题的独立 reference-qualified 复现", "非神经或低维 conservative correction baseline 与 identifiability 对照", "在全新 Stage 03 中预注册的 one-step/solver consequence evidence；不得回写 Stage 02"],
    "main_text": ["V&V-first pipeline", "reference hierarchy", "blind dataset and leakage control", "architecture hard gates", "two complete negative static protocols", "claim boundary and route termination"],
    "supplement": ["all per-case uncertainty tables", "complete hash ledger", "all conditioning parameter rows", "metamorphic matrices", "checkpoint identities"],
    "internal_audit_only": ["machine/environment minutiae", "full loader decode logs", "all checkpoint write timings", "temporary render QA images"],
    "status": "PASS",
}
write_json(ROOT / "manuscript_assessment/stage02_manuscript_readiness.json", assessment)

figures = [
    (1, "V&V-first PIO qualification pipeline", "流程图", ["status ledger"], "显示资格门、失败保留与停止规则；不显示 solver 成功箭头。"),
    (2, "Reference and target qualification hierarchy", "层级图", ["Stage 02A/H/I evidence"], "区分 R1/R2/R3/RX 和 candidate/qualified/pair-compatible。"),
    (3, "Stage decision/failure tree", "决策树", ["22-stage ledger"], "保留所有 NOT READY/NOT QUALIFIED 节点。"),
    (4, "Blind dataset family/split/leakage structure", "网络/分组图", ["J-W leakage graph", "10/5/5 split"], "family为统计单元；不得以粒子数扩充 n。"),
    (5, "K0/K1/K2 architecture and conservation contract", "结构示意", ["Stage 02K contract"], "K0标为 diagnostic，K1/K2标结构合格，不画性能排序。"),
    (6, "Static fitting v0.1 and v0.2 train/validation trajectories", "全 seed 轨迹", ["M/M-Q training histories"], "九条seed全部展示；v0.1/v0.2不同protocol/family不得作paired significance。"),
    (7, "Frozen gate outcomes across seeds", "门槛矩阵", ["M/M-Q frozen gates"], "同时展示A-E，突出B train-fit failure；validation/test PASS不着成功色。"),
    (8, "Supported/unsupported claim boundary", "边界图", ["claim boundary"], "明确 supported/conditional/unsupported，不用营销性箭头。"),
]
tables = ["Stage status ledger", "reference qualification", "dataset inventory", "architecture hard gates", "v0.1/v0.2 static fitting results", "final evidence/claim matrix"]
figure_plan = {"plan_version": "stage02ms-figure-table-plan-1.0.0", "figures": [{"figure": number, "title": title, "form": form, "data_sources": sources, "integrity_rule": rule, "status": "PLANNED_NOT_FABRICATED"} for number, title, form, sources, rule in figures], "tables": [{"table": i + 1, "title": title, "source": "machine manifests only", "status": "PLANNED"} for i, title in enumerate(tables)], "prohibitions": ["do not delete failed seeds", "do not show only best seed", "do not use particle count as sample size", "do not depict validation/test PASS as overall model success"], "status": "PASS"}
write_json(ROOT / "figure_plan/stage02_figure_and_table_plan.json", figure_plan)

branches = [
    {"branch": 1, "title": "停止学习修正，聚焦 V&V/qualification framework", "hypothesis": "可复核的失败边界本身构成方法学贡献", "required_stage": "new Stage 03A", "allowed_design": ["跨问题复现设计", "外部实现审计", "论文验证包"], "execution_in_stage02ms": False, "priority": 1},
    {"branch": 2, "title": "学习低维、可唯一识别的物理系数或 closure", "hypothesis": "低维 identifiable quantity 比完整 delta_a 更可学", "required_stage": "new Stage 03B", "allowed_design": ["新 target definition", "identifiability preregistration", "independent V&V"], "execution_in_stage02ms": False, "priority": 2},
    {"branch": 3, "title": "真实多状态 trajectory dataset", "hypothesis": "多状态轨迹可能提供当前静态局部映射缺失的信息", "required_stage": "new Stage 03C", "allowed_design": ["全新 trajectory families", "重新执行 independent reference/V&V", "新 split/leakage contract"], "execution_in_stage02ms": False, "priority": 4},
    {"branch": 4, "title": "非神经 conservative correction", "hypothesis": "解析/回归型低容量 closure 可提供可解释 baseline", "required_stage": "new Stage 03D", "allowed_design": ["解析基函数", "constrained regression", "same structural hard gates"], "execution_in_stage02ms": False, "priority": 3},
]
future = {"future_branch_version": "stage02ms-future-branches-1.0.0", "branches": branches, "stage02_direct_continuation": False, "v0_3_permitted": False, "status": "DESIGN_ONLY_COMPLETE"}
write_json(ROOT / "future_branches/stage03_branch_decision_design.json", future)

write_md("stage02ms_freeze_and_scope.md", f"""# Stage 02M-S — Freeze and scope

Historical Stage 02M-Q state is preserved as **STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED**. The historical freeze covers **{freeze['historical_file_count']}** files, 22 Stage 02 statuses and nine selected checkpoint identities; all checks are **PASS**.

This stage is evidence consolidation only. `static_pio_learning_route_terminated=true`, `Stage02N_authorized=false`, `training_protocol_v03_permitted=false`, `rollout_authorized=false`, and `solver_in_the_loop_authorized=false`. New training runs, optimizer steps and test evaluations are all zero. Historical artifacts were used as read-only inputs and were not rewritten.
""")

ledger_lines = ["# Stage 02M-S — Complete Stage 02 status ledger", "", "Later states do not supersede earlier failures.", "", "| # | Stage | Unique status | Runs | Optimizer steps | Principal blocker |", "|---:|---|---|---:|---:|---|"]
for row in ledger_rows:
    ledger_lines.append(f"| {row['order']} | {row['stage']} | `{row['unique_status']}` | {row['training_runs']} | {row['optimizer_steps']} | {row['principal_blocker']} |")
ledger_lines.extend(["", "Terminal boundary: static learning route terminated; Stage 02N, v0.3, rollout and solver-in-the-loop are not authorized."])
write_md("stage02ms_stage02_status_ledger.md", "\n".join(ledger_lines))

matrix_lines = ["# Stage 02M-S — Evidence matrix", "", "| ID | Class | Evidence level | Claim | Limitation |", "|---|---|---|---|---|"]
for row in evidence_rows:
    matrix_lines.append(f"| {row['id']} | {row['claim_class']} | `{row['evidence_level']}` | {row['claim']} | {row['limitations']} |")
matrix_lines.extend(["", "Confirmatory, diagnostic and negative evidence remain separately labeled. No dynamic solver evidence exists."])
write_md("stage02ms_evidence_matrix.md", "\n".join(matrix_lines))

tax_lines = ["# Stage 02M-S — Failure taxonomy", "", "`FAIL` means an executed hard gate failed; `NOT QUALIFIED` means a completed qualification did not satisfy the full contract; `NOT AUTHORIZED` and `NOT EXECUTED` are not failures; `DIAGNOSTIC` is not PASS; `EVIDENCE INCOMPLETE` is a provenance/completeness state.", ""]
for row in failure_classes:
    tax_lines.extend([f"## {row['id']}. {row['name']}", "", row["definition"], "", f"Recorded instances: {row['instances']}", "", f"Explicit non-instances: {row['not_instances']}", ""])
tax_lines.append("Rollout is **NOT AUTHORIZED / NOT EXECUTED**, never 'rollout failed'.")
write_md("stage02ms_failure_taxonomy.md", "\n".join(tax_lines))

claim_lines = ["# Stage 02M-S — Formal claim boundary", "", "## SUPPORTED CLAIMS", ""]
for c, a, p in supported:
    claim_lines.extend([f"- Claim: {c}", f"  - Allowed: {a}", f"  - Prohibited: {p}", ""])
claim_lines.extend(["## CONDITIONAL CLAIMS", ""])
for c, a, p in conditional:
    claim_lines.extend([f"- Claim: {c}", f"  - Allowed: {a}", f"  - Prohibited: {p}", ""])
claim_lines.extend(["## UNSUPPORTED CLAIMS", ""])
for c, a, p in unsupported:
    claim_lines.extend([f"- Claim: {c}", f"  - Allowed: {a}", f"  - Prohibited: {p}", ""])
write_md("stage02ms_claim_boundary.md", "\n".join(claim_lines))

ready_lines = ["# Stage 02M-S — Manuscript readiness", "", "CMAME targets significant computational-method developments in applied mechanics and includes machine learning. Current evidence is scientifically coherent but does not yet show a qualified solver method or broad mechanics replication.", "", "| Direction | Evidence completeness | Readiness | Current CMAME defensible | Fatal weakness |", "|---|---|---|---|---|"]
for paper in papers:
    ready_lines.append(f"| {paper['paper']}: {paper['direction']} | {paper['evidence_completeness']} | `{paper['manuscript_readiness']}` | {paper['current_CMAME_target_defensible']} | {paper['fatal_weakness']} |")
ready_lines.extend(["", "Recommended line: **Paper B + Paper C hybrid**, a methodology/negative-results paper. Paper A is not ready because complete solver-performance evidence is absent.", "", "Current CMAME readiness: **NOT_YET_DEFENSIBLE**. Three critical missing evidence items are cross-regime replication, a simpler conservative baseline/identifiability comparison, and prospectively authorized Stage 03 one-step/solver-consequence evidence."])
write_md("stage02ms_manuscript_readiness.md", "\n".join(ready_lines))

write_md("stage02ms_manuscript_framework.md", f"""# Stage 02M-S — Recommended manuscript framework

Working title: **{assessment['working_title']}**.

The current evidence can form a complete journal manuscript if framed as a V&V-first methodology demonstrated through a falsified static-learning route. It is better suited to a methodology/negative-results paper than a solver-performance paper. The main text should contain the qualification pipeline, reference hierarchy, blind lineage/split controls, structural architecture gates, both complete static protocols, and the terminal claim boundary. Detailed uncertainty tables, conditioning parameters, metamorphic matrices and hash identities belong in the supplement; loader logs and machine-level checkpoint I/O remain internal audit.

The manuscript must disclose Stage 01 `V2_QUALIFICATION_FAIL`, both static fitting failures, and absent rollout. It must not be premised on “Transformer successfully improves SPH.”
""")

fig_lines = ["# Stage 02M-S — Figure and table plan", "", "| Figure | Title | Form | Integrity rule |", "|---:|---|---|---|"]
for row in figure_plan["figures"]:
    fig_lines.append(f"| {row['figure']} | {row['title']} | {row['form']} | {row['integrity_rule']} |")
fig_lines.extend(["", "Tables: " + "; ".join(tables) + ".", "", "All failed seeds remain visible; particle count is never treated as sample count; validation/test PASS is not colored or captioned as overall model success."])
write_md("stage02ms_figure_and_table_plan.md", "\n".join(fig_lines))

branch_lines = ["# Stage 02M-S — Future research branches", "", "All branches are design-only and must begin as a new Stage 03; none is a Stage 02 repair.", ""]
for row in branches:
    branch_lines.extend([f"## Branch {row['branch']}: {row['title']}", "", f"Hypothesis: {row['hypothesis']}", "", f"Required stage: `{row['required_stage']}`. Allowed design scope: {', '.join(row['allowed_design'])}. Execution in Stage 02M-S: **no**.", ""])
write_md("stage02ms_future_research_branches.md", "\n".join(branch_lines))

print(json.dumps({"ledger": ledger["status"], "stages": len(ledger_rows), "evidence_claims": len(evidence_rows), "failure_classes": len(failure_classes), "papers": len(papers), "figures": len(figures), "branches": len(branches)}, sort_keys=True))
