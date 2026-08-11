#!/usr/bin/env python3
"""Build the non-computational S1 evidence synthesis from frozen records."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "project_wide_synthesis"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def write_json(rel, data):
    p = OUT / rel; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(rel, text):
    p = OUT / rel; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")


def esc(x):
    return str(x).replace("|", "\\|").replace("\n", " ")


def md_table(headers, rows):
    s = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        s.append("| " + " | ".join(esc(v) for v in row) + " |")
    return "\n".join(s)


def sha(rel):
    h = hashlib.sha256(); p = ROOT / rel
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def tag_commit(tag):
    try:
        return subprocess.run(["git", "rev-list", "-n", "1", tag], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()
    except Exception:
        return "NO_TAG"


freeze = load("project_wide_synthesis/00_freeze/project_wide_input_freeze_manifest.json")
s2ledger = load("stage_02_Particle_Interaction_Operator/08_route_closure/status_ledger/stage02_complete_status_ledger.json")
s3ledger = load("stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/status_ledger/stage03ds_status_ledger.json")
s1d2 = load("06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json")
s1e = load("06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json")
s1f3 = load("06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json")
s1f3b = load("06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json")
s1f3c = load("06_experiments/stage_01f3c_ct2_adjudication/results/stage01f3c_evaluation.json")
s1f5b = load("06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json")
s1g = load("06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json")
s1h = load("06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json")
s2m = load("stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_1/results/stage02m_qualification_summary.json")
s2mq = load("stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json")
s2mr = load("stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_failure_attribution_v0_1/results/stage02mr_final_summary.json")
s3d = load("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json")
s3dr = load("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json")
p1 = load("publication/verification_first_dynamic_neural_sph_v0_1/10_manifests/publication_p1_final_manifest.json")
p2 = load("publication/verification_first_dynamic_neural_sph_v0_1/11_literature_verification/manifests/publication_p2_final_manifest.json")
novelty_p2 = load("publication/verification_first_dynamic_neural_sph_v0_1/11_literature_verification/novelty_matrix/novelty_positioning_matrix.json")


STATUS_ONTOLOGY = [
    ("PASS", "预注册的整体门全部满足；只适用于明确范围。"),
    ("FAIL", "已执行且至少一个决定性门失败。"),
    ("NOT_QUALIFIED", "已执行但不足以产生资格；可含通过的组成部分。"),
    ("EVIDENCE_INCOMPLETE", "结论所需证据缺失或不可用，不能判为失败。"),
    ("NOT_AUTHORIZED", "上游合同未授权该活动。"),
    ("NOT_EXECUTED", "活动没有执行；不得改写为 FAIL。"),
    ("DIAGNOSTIC", "仅用于归因或机制理解，不产生资格。"),
    ("CONDITIONAL", "在明确条件和边界内成立。"),
    ("TERMINATED", "路线按预注册停止规则关闭。"),
    ("PAUSED", "路线暂停，等待新假设或新授权。"),
    ("QUALIFIED_COMPONENT", "组成分量通过，但总体不因此通过。"),
]
ontology = {"schema": "s1.status-ontology.v1", "terms": [{"term": a, "definition": b} for a,b in STATUS_ONTOLOGY],
            "hard_rules": ["NOT_EXECUTED != FAIL", "QUALIFIED_COMPONENT != PASS", "DIAGNOSTIC != PASS", "later diagnosis cannot overwrite historical failure"]}
write_json("06_evidence_hierarchy/status_ontology.json", ontology)
write_md("06_evidence_hierarchy/status_ontology.md", "# 全项目状态本体\n\n[PROJECT_EVIDENCE] 本体用于跨阶段归一化，不替代各阶段 exact status。\n\n" + md_table(["术语","严格含义"], STATUS_ONTOLOGY) + "\n\n## 不可违反规则\n\n- `NOT_EXECUTED` 不等于 `FAIL`。\n- `QUALIFIED_COMPONENT` 不得提升为整体 `PASS`。\n- 后续诊断不得改写冻结的历史 verdict。")


levels = [
    ("L0", "specification", "achieved", "Stage 01–03 多阶段合同、阈值、停止规则与哈希冻结"),
    ("L1", "implementation", "achieved", "Stage 01 SPH 路径、Stage 02 K1/K2、Stage 03 D0–D3/RK2"),
    ("L2", "code verification", "achieved", "算子、守恒、zero-correction、one-step AD、图更新语义"),
    ("L3", "solution verification", "partial/failed", "MMS 实现与 plateau-aware 子路线通过；Stage 01 V2 最终 FAIL"),
    ("L4", "reference qualification", "achieved_with_scope", "Stage 02 Fourier/analytic；Stage 03 D-R1/D-R2/D-R3；D-R4 unavailable"),
    ("L5", "data qualification", "achieved_static_scope", "Stage 02J-W 20-record blind multifamily static pair dataset"),
    ("L6", "structural model qualification", "achieved", "K1/K2 antisymmetry与结构门；Stage 03实现资格"),
    ("L7", "training qualification", "failed_static/not_executed_dynamic", "static fitting v0.1/v0.2 未资格；动态训练未授权"),
    ("L8", "rollout validation", "not_executed", "autonomous rollout 未授权/未执行"),
    ("L9", "physical validation", "partial/unavailable", "独立 shear/acoustic 有边界；D-R4 不可用"),
    ("L10", "cost/utility", "not_executed", "没有完整性能、成本或效用比较"),
]
evidence_matrix = {"schema":"s1.evidence-hierarchy.v1", "levels":[{"level":a,"name":b,"state":c,"evidence":d} for a,b,c,d in levels],
                   "project_ceiling":"L6 achieved; L7 static failed and dynamic not executed; L8/L10 not executed; L9 partial"}
write_json("06_evidence_hierarchy/project_wide_evidence_matrix.json", evidence_matrix)
write_md("06_evidence_hierarchy/project_wide_evidence_matrix.md", "# 全项目证据等级矩阵\n\n[PROJECT_EVIDENCE] 证据上限不是单一最高数字，而是不同路线的分层状态。\n\n" + md_table(["等级","名称","状态","证据边界"], levels) + "\n\n[PROJECT_EVIDENCE] Stage 02/03 尚未达到正式动态训练资格、autonomous rollout、full solver performance 或 D-R4 physical validation。")


def trow(stage,status,question,hypothesis,evidence,outcome,blocker,next_auth,commit="UNTRACKED_ARTIFACT_HASH",resource="metadata/read-only",boundary="不得外推"):
    return {"stage_id":stage,"exact_final_status":status,"scientific_question":question,"hypothesis":hypothesis,
            "authorized_input":evidence,"implementation_execution":outcome,"primary_metric":"stage-specific frozen machine gates",
            "qualification_gate":"pre-registered or frozen hard gates","outcome":outcome,"blocker":blocker,"next_authorization":next_auth,
            "commit_or_hash":commit,"resource_use":resource,"claim_boundary":boundary}


timeline = []
timeline.append(trow("Stage 00","CONDITIONAL","Apple Silicon 环境能否承载2D PoC？","CPU/MPS可在保守粒子数下支持PoC。","07_reports/stage_00_summary.md","CPU/MPS操作检查通过；diffSPH仅安装/导入/邻域预检。","完整diffSPH求解器未在该阶段运行。","Stage 01最小执行路径",tag_commit("stage-00-complete"),"N<=1024 benchmark envelope","环境预检不是求解器验证"))
stage1_defs = [
 ("Stage 01","CONDITIONAL PASS (V0 only)","官方链能否执行并保留窄范围AD？","完整链可执行。","07_reports/stage_01_scope_reclassification.md","V0工程可执行；V1部分；V2未完成；V3未开始。","不可作fixed-physics truth。","Stage 01B V1", "stage-01-v0-pass"),
 ("Stage 01B","V1_FAIL","固定物理SPH算子是否满足V1？","原算子可通过一致性、守恒和多步AD门。","07_reports/stage_01b_final_vv_report.md","kernel/Laplacian/AD及结构门触发停止。","V2/TGV未授权。","Stage 01C修复", "stage-01b-v1-fail"),
 ("Stage 01C","C1_PASS_C2_PASS_C3_PASS_C4_PASS","结构保持算子能否修复V1缺陷？","项目侧邻域、pair作用和native AD可重资格。","06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt","四项静态重资格门通过。","不是动态V2。","Stage 01D", "stage-01c-operator-requalified"),
 ("Stage 01D","V2_FAIL","固定物理动态TGV能否通过V2？","修复算子可进入时间/空间/无序验证。","06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt","N32 smoke资源门失败；后续多门NOT_RUN。","资源增长机制未明。","Stage 01D-R诊断", "stage-01d-v2-fail-resource-gate"),
 ("Stage 01D-R","RESOURCE_FAIL_LINEAR_GROWTH","RSS增长是否越界？","post-warm-up多重复可区分缓存与retention。","06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt","资源重资格仍失败。","不能据此直接称memory leak。","Stage 01D-R2", "stage-01dr-resource-fail-live-bytes-gate"),
 ("Stage 01D-R2","ATTRIBUTION_UNRESOLVED","增长是否由storage/edge数解释？","组件归因可定位。","06_experiments/stage_01dr2_storage_attribution/results/stage01dr2_attribution_status.txt","storage归因未唯一解析。","cutoff topology与生命周期混杂。","Stage 01D-R3", "stage-01dr2-attribution-unresolved-cutoff-topology"),
 ("Stage 01D-R3","R3_CONFIRMATION_UNRESOLVED","冻结拓扑能否消除增长？","拓扑变化是主因。","06_experiments/stage_01dr3_topology_confirmation/results/stage01dr3_status.txt","证据仍未解析。","weakref语义待核。","Stage 01D-R4", "stage-01dr3-confirmation-unresolved-weakref-semantics"),
 ("Stage 01D-R4","R4_RETENTION_REDETECTED","weakref测试能否解释对象保留？","正确fixture将消除retention。","06_experiments/stage_01dr4_weakref_semantics/results/stage01dr4_status.txt","retention被重新检测。","GC时序未定位。","Stage 01D-R5", "stage-01dr4-retention-redetected-gc-delayed"),
 ("Stage 01D-R5","R5_BOUNDED_GC_DELAY_CONFIRMED","retention是否为有界GC延迟？","默认GC长窗呈有界上包络。","06_experiments/stage_01dr5_gc_cycle_localization/results/stage01dr5_status.txt","GC-disabled线性；default-GC 2000步有界。","不能把旧资源失败改写为假阳性。","Stage 01D-P", "stage-01dr5-bounded-gc-delay-confirmed"),
 ("Stage 01D-P","POLICY_PASS_ISOLATED_DEFAULT_GC","隔离子进程政策能否覆盖1600步最大计划轨迹？","default-GC/no_grad/trajectory-per-process可形成安全包络。","06_experiments/stage_01dp_resource_policy/results/stage01dp_status.txt","3/3 canary通过；政策资格化。","仅资源政策，不是V2数据。","Stage 01D2设计申请", "stage-01dp-isolated-default-gc-policy-pass"),
 ("Stage 01D2",s1d2["final_status"],"重新执行完整V2能否通过？","资源政策后时间、空间、jitter、Mach可整体资格化。","06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json","时间可解释，但空间非单调、jitter/资源门失败。","不能进入V3。","Stage 01E归因", "stage-01d2-v2-requalification-fail"),
 ("Stage 01E",s1e["unique_classification"],"V2误差由离散还是模型形式主导？","不可压TGV与WCSPH EOS存在对齐误差。","06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json","EOS初始化残差主导；两项渐近拟合不可识别。","不改变V2失败。","WCSPH-compatible MMS", "stage-01e-model-form-alignment-dominant"),
 ("Stage 01F","MMS_SPECIFICATION_PASS","能否设计WCSPH兼容制造解？","源项与解析闭合可避免TGV模型错配。","06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json","MMS规格通过。","规格不等于实现/收敛。","Stage 01F2", "stage-01f-mms-specification-pass"),
 ("Stage 01F2","MMS_IMPLEMENTATION_VERIFIED_PASS","MMS实现、源项与AD是否正确？","双路径实现可闭合。","06_experiments/stage_01f2_mms_implementation/results/stage01f2_evaluation_v2.json","实现验证通过。","未建立收敛资格。","Stage 01F3", "stage-01f2-mms-implementation-verified-pass"),
 ("Stage 01F3",s1f3["status"],"严格单调收敛门能否通过？","误差应严格单调并显示预期阶。","06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json","reference/topology identity硬门前停止或收敛门失败。","需reference资格化。","Stage 01F3-R", "stage-01f3-fail-semidscrete-topology-identity"),
 ("Stage 01F3-R","SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT","同半离散reference能否去除参考误差？","dense/sparse等价DOP853可作时间truth。","06_experiments/stage_01f3r_reference_qualification/results/stage01f3r_evaluation.json","reference资格化。","不修复原F3失败。","Stage 01F3B", "stage-01f3r-semidiscrete-reference-dense-equivalent"),
 ("Stage 01F3B",s1f3b["status"],"连续时间/空间隔离后严格门能否通过？","更好reference应恢复单调趋势。","06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json","仍为收敛资格失败；GCI不成立。","plateau/cancellation影响门设计。","Stage 01F3C", "stage-01f3b-fail-continuous-velocity-ct2"),
 ("Stage 01F3C",s1f3c["status"],"CT2失败是时间阶、平台还是抵消？","分解可唯一归因。","06_experiments/stage_01f3c_ct2_adjudication/results/stage01f3c_evaluation.json","时间阶接近2但抵消门失败，混合/未解析。","严格单点门不稳健。","Stage 01F4", "stage-01f3c-ct2-mixed-or-unresolved"),
 ("Stage 01F4","PLATEAU_AWARE_PROTOCOL_APPROVED","能否前瞻修正规则而不改写历史？","平台感知指标可分离趋势与精度地板。","06_experiments/stage_01f4_protocol_adjudication/results/stage01f4_evaluation.json","新协议批准；旧失败保持。","尚未执行。","Stage 01F5", "stage-01f4-plateau-aware-protocol-approved"),
 ("Stage 01F5","PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED","一次性重资格设计是否完整？","预冻结矩阵可避免结果后改门。","06_experiments/stage_01f5_requalification_design/results/stage01f5_evaluation.json","设计批准。","执行清单分支不全。","Stage 01F5-P", "stage-01f5-requalification-design-approved"),
 ("Stage 01F5-P","EXECUTION_MANIFEST_INCOMPLETE","N64分支依赖是否完整？","原清单覆盖全部触发。","06_experiments/stage_01f5p_branch_completeness/results/stage01f5p_evaluation.json","执行清单不完整。","空间horizon参数未绑定。","Stage 01F5-Q", "stage-01f5p-execution-manifest-incomplete"),
 ("Stage 01F5-Q","FORMAL_SPACE_EXECUTION_BUNDLE_READY","补充清单后可否执行？","只修复合同完整性即可。","06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_evaluation.json","正式执行bundle就绪。","尚未产生资格。","Stage 01F5B", "stage-01f5q-formal-space-execution-bundle-ready"),
 ("Stage 01F5B",s1f5b["unique_status"],"plateau-aware MMS能否通过？","新合同可正确识别平台但保留失败分支。","06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json","一次性重资格通过；基础设施retry单独保留。","不等于V2 physical validation。","Stage 01G独立验证", "stage-01f5b-plateau-aware-mms-requalification-pass"),
 ("Stage 01G design","INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED","独立shear/acoustic能否形成V2门？","双基准可提供独立物理检查。","06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json","设计通过但未执行。","需独立授权。","Stage 01G-P", "stage-01g-independent-validation-design-approved"),
 ("Stage 01G-P","INDEPENDENT_VALIDATION_EXECUTION_READY","执行前依赖是否齐备？","冻结身份和metric binding可就绪。","06_experiments/stage_01gp_preexecution_audit/results/stage01gp_evaluation.json","preexecution audit通过。","evaluator尚需资格化。","Stage 01G-E", "UNTRACKED_ARTIFACT_HASH"),
 ("Stage 01G-E","INDEPENDENT_VALIDATION_EVALUATOR_READY","评价器能否独立重算门？","依赖隔离与metric binding可资格化。","06_experiments/stage_01ge_evaluator_qualification/results/stage01ge_evaluation.json","evaluator就绪。","执行基础设施仍需授权。","Stage 01G V2 preflight", "UNTRACKED_ARTIFACT_HASH"),
 ("Stage 01G preflight V2","INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED","是否可以执行独立验证？","冻结bundle满足执行前置。","06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json","执行获授权；未生成V2状态。","需基础设施成功。","Stage 01G-R/execute", "UNTRACKED_ARTIFACT_HASH"),
 ("Stage 01G-R","EXECUTION_INFRA_READY_FOR_BENCHMARK","launch/config问题可否修复？","基础设施错误与科学失败可隔离。","06_experiments/stage_01gr_execution_infrastructure_repair/results/stage01gr_evaluation.json","修复后基础设施就绪。","科学门仍待执行。","Stage 01G execution", "UNTRACKED_ARTIFACT_HASH"),
 ("Stage 01G execution",s1g["unique_status"],"独立shear/acoustic是否恢复V2？","两族都应通过冻结门。","06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json","acoustic通过；shear N48门失败；V2失败。","SHEAR3衰减误差。","Stage 01H诊断", "UNTRACKED_ARTIFACT_HASH"),
 ("Stage 01H",s1h["unique_status"],"shear失败是算子形式还是有限分辨率？","误差分解可识别主导机制。","06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json","分类FINITE_RESOLUTION_DOMINANT；算子形式失败未确认。","支持尺度与分辨率共变。","Stage 02独立理论路线", "UNTRACKED_ARTIFACT_HASH"),
]
for stage,status,q,h,e,o,b,n,tag in stage1_defs:
    timeline.append(trow(stage,status,q,h,e,o,b,n,tag_commit(tag) if tag not in {"UNTRACKED_ARTIFACT_HASH"} else tag,"frozen recorded execution","只支持对应冻结范围"))

for row in s2ledger["rows"]:
    timeline.append(trow(row["stage"],row["unique_status"],row["purpose"],row["purpose"],row["principal_evidence"]["artifact"],row["principal_evidence"]["summary"],row["principal_blocker"],row["downstream_authorization"],row["historical_hash"],f"executions={row['execution_count']}; training={row['training_runs']}; optimizer_steps={row['optimizer_steps']}",row["scientific_interpretation_boundary"]))
for row in s3ledger["rows"]:
    timeline.append(trow(row["stage"],row["status"],row["purpose"],row["purpose"],row["artifact"],row["principal_pass_evidence"],row["principal_blocker"],row["downstream_authorization"],row["artifact_sha256"],f"executions={row['execution_count']}; training={row['training_runs']}; optimizer_steps={row['optimizer_steps']}",row["interpretation_boundary"]))
timeline += [
 trow("Stage 03D-S","STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE","如何关闭动态路线并固化边界？","负结果与合格拓扑分量应分层保存。","stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json","路线暂停；Stage03E=false。","多步梯度未资格。","Stage04需新合同；非自动继承",sha("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json"),"new probes/training=0","闭环报告不修复Stage03D"),
 trow("Publication P1",p1["status"],"现有证据能否形成verification-first稿件？","负结果主线可形成证据锁定草稿。","publication/verification_first_dynamic_neural_sph_v0_1/10_manifests/publication_p1_final_manifest.json",f"{p1['package_summary']['manuscript_character_count']}字；{p1['package_summary']['docx_page_count']}页；claim map完成。","仍需外部文献定位。","Publication P2",sha("publication/verification_first_dynamic_neural_sph_v0_1/10_manifests/publication_p1_final_manifest.json"),"no new computation","草稿不是发表接受"),
 trow("Publication P2",p2["terminal_status"],"主张与文献定位是否可核验？","系统检索可约束新颖性措辞。","publication/verification_first_dynamic_neural_sph_v0_1/11_literature_verification/manifests/publication_p2_final_manifest.json","文献核验与positioning完成。","项目后续Stage04仍未知。","S1 project-wide decision dossier",sha("publication/verification_first_dynamic_neural_sph_v0_1/11_literature_verification/manifests/publication_p2_final_manifest.json"),"literature-only","不将文献空缺写成绝对首次"),
]
timeline_payload={"schema":"s1.complete-stage-timeline.v1","chronology_rule":"dependency order; no later row overwrites earlier verdict","row_count":len(timeline),"rows":timeline}
write_json("02_stage_timeline/complete_stage_timeline.json",timeline_payload)
write_md("02_stage_timeline/complete_stage_timeline.md","# 全项目阶段时间线\n\n[PROJECT_EVIDENCE] 依赖顺序来自Git/tag、阶段账本和冻结manifests；exact status保持原字面。\n\n"+md_table(["阶段","exact final status","科学问题/结果","阻断与下一授权","证据"],[(r["stage_id"],r["exact_final_status"],r["outcome"],r["blocker"]+" → "+r["next_authorization"],r["authorized_input"]) for r in timeline]))


hyp_defs = [
 ("H01","高分辨率 SPH 可自动作为真值。","FALSIFIED","Stage01与Stage02显示离散、时间、quadrature与模型形式污染必须分离。","候选reference必须独立资格化。"),
 ("H02","WCSPH 与不可压 TGV 在当前设置中模型形式一致。","LIMITED/FALSIFIED_IN_SCOPE","Stage01E EOS初始化残差主导，比例由机器记录给出。","采用WCSPH-compatible MMS与source-free独立验证。"),
 ("H03","static pair-force correction 在合格架构下可学习。","NOT_QUALIFIED","Stage02M/M-Q中K1/K2 train-fit硬门未整体通过。","转向局部因果动态训练假设。"),
 ("H04","regularity 可作为dataset hard gate。","FALSIFIED","v0.1–v0.4出现false positive、cross-mode与invariance失败；路线终止。","regularity仅作diagnostic，dataset eligibility由reference/target/conservation/lineage决定。"),
 ("H05","attention优于MLP。","NOT_TESTED","K1/K2结构资格化不等于优越性；static fitting也未建立稳定优势。","未来只可在公平D0–D3合同和合格训练后比较。"),
 ("H06","optimization conditioning主导static fitting。","SUPPORTED_AS_DIAGNOSIS_NOT_GENERAL_LAW","Stage02M-R量化归因支持conditioning，但v0.2仍未资格。","需新任务对齐、尺度与blind families检验。"),
 ("H07","短时历史改善动态closure。","NOT_TESTED/GRADIENT_ATTENUATED","Stage03D history gradient 0/6；D-R观察到history influence强衰减。","Stage04需local-causal/task-aligned可证伪合同。"),
 ("H08","动态Transformer混合实现正确。","QUALIFIED_COMPONENT","Stage03C D0/zero-correction/checkpoint/one-step AD通过。","实现正确不等于多步可微或训练有效。"),
 ("H09","多步梯度可按360-probe合同资格化。","NOT_QUALIFIED","216 stable、144 failure；history 0/6；归因为mixed/unresolved。","需新任务对齐梯度合同，不能后改epsilon门。"),
 ("H10","动态训练资格已建立。","NOT_AUTHORIZED/NOT_EXECUTED","Stage03E=false；optimizer/training=0。","Stage04必须独立进口新证据。"),
 ("H11","Stage04 local-causal training能避开全局history梯度衰减并保持结构性质。","NOT_TESTED","仅为Stage04新假设，没有训练或rollout证据。","以task-aligned gradient→training→rollout→validation顺序检验。"),
]
hyp=[]
for i,w,s,e,n in hyp_defs:
    hyp.append({"id":i,"original_wording":w,"evidence":e,"status":s,"falsification_or_limitation":e,"successor_hypothesis":n,"prohibited_retrospective_reinterpretation":"不得用后续局部PASS覆盖该条历史状态。"})
write_json("03_hypothesis_register/complete_hypothesis_register.json",{"schema":"s1.hypothesis-register.v1","hypotheses":hyp})
write_md("03_hypothesis_register/complete_hypothesis_register.md","# 完整假设演化登记\n\n"+"\n\n".join(f"## {h['id']} {h['original_wording']}\n\n- 状态：`{h['status']}`\n- [PROJECT_EVIDENCE] 证据/限制：{h['evidence']}\n- [INFERENCE] 后继假设：{h['successor_hypothesis']}\n- 禁止回溯改写：{h['prohibited_retrospective_reinterpretation']}" for h in hyp))


def failure(fid,cat,stage,status,gate,num,direct,deeper,*rest):
    if len(rest) == 6:
        ruled = "见冻结的直接/深层因果审计；未将未执行事项作为排除证据。"
        unresolved,kind,repaired,effect,pub,lesson = rest
    elif len(rest) == 7:
        ruled,unresolved,kind,repaired,effect,pub,lesson = rest
    else:
        raise ValueError(f"unexpected failure fields for {fid}: {len(rest)}")
    return {"id":fid,"category":cat,"stage":stage,"exact_status":status,"failed_gate":gate,"numerical_evidence":num,"direct_cause":direct,"deeper_cause":deeper,"ruled_out_causes":ruled,"unresolved_causes":unresolved,"infrastructure_or_scientific":kind,"later_repaired":repaired,"historical_failure_immutable":True,"downstream_effect":effect,"publication_value":pub,"lesson":lesson}


c=s3d["counts"]
failures=[
 failure("F-A01","A 环境与依赖问题","Stage 00/01G-R","CONDITIONAL / EXECUTION_INFRA_READY_FOR_BENCHMARK","MPS hybrid与launch/config gates","CPU/MPS检查通过但compact neighbor为CPU桥接；一次launch/config失败被保留。","平台/依赖边界而非科学模型失败。","CUDA缺失不是已观察失败；修复后benchmark可运行。","完整MPS算子覆盖仍未知。","infrastructure",True,"要求CPU canonical与基础设施/科学失败分离。","工程可复现性","环境PASS必须带边界。"),
 failure("F-B01","B 数值实现错误","Stage 01B","V1_FAIL","neighbor/Laplacian/backward","重复边、hard-coded alpha、h_i=None backward。","上游接口和执行栈缺陷。","不能归因于全部SPH理论。","上游其他路径未穷尽。","mixed",True,"推动Stage01C项目侧唯一pair几何/native AD。","代码验证方法","最小复现先于模型归因。"),
 failure("F-C01","C 守恒/对称结构问题","Stage 01B","V1_FAIL","pairwise internal-force gates","variable-density viscosity与mixed-sign pressure不满足严格pair反对称。","离散作用结构不是事后数值噪声。","非单纯硬件/随机种子。","角动量/耗散仅部分诊断。","scientific",True,"推动对称非负pair作用及K1/K2硬结构。","结构保持贡献","硬保证必须编码进作用形式。"),
 failure("F-D01","D 资源和内存问题","Stage 01D–D-P","V2_FAIL → POLICY_PASS_ISOLATED_DEFAULT_GC","RSS growth gate","旧N32 smoke RSS增长；后续default-GC长窗有界。","retired对象受GC延迟、topology与fixture语义共同影响。","没有正式路径O(step·E) tensor历史；不能称简单memory leak。","具体循环链归因不唯一。","mixed",True,"旧V2失败保留，但建立隔离子进程资源政策。","资源资格化方法","资源门与科学门分离。"),
 failure("F-E01","E 模型形式不一致","Stage 01E",s1e["unique_classification"],"benchmark alignment","EOS/operator比与EOS/viscosity比来自机器分解。","不可压TGV压力与WCSPH EOS初始化不一致。","闭合误差很小，非分解代码错误。","两项空间渐近拟合不可识别。","scientific",False,"推动WCSPH-compatible MMS。","模型形式辨识","benchmark知名度不能替代方程一致性。"),
 failure("F-F01","F reference specification问题","Stage 01F3","MMS_CONVERGENCE_VERIFICATION_FAIL","semidiscrete identity","原reference与稀疏拓扑身份不足。","continuum truth、semidiscrete time truth与spatial truth角色混淆。","Stage01F2实现已通过。","严格门下部分误差平台。","scientific",True,"Stage01F3-R建立dense-equivalent same-semidiscrete DOP853。","reference治理","先资格化reference角色。"),
 failure("F-G01","G solution verification问题","Stage 01D2/01F3B/01G","V2_QUALIFICATION_FAIL","space/jitter/CT2/shear gates","空间非单调、plateau/cancellation及shear N48超阈值。","有限分辨率、支持尺度共变与门设计敏感性。","Stage01H排除时间步与确定性主因；operator-form failure未确认。","支持尺度独立性仍不足。","scientific",False,"形成plateau-aware protocol与finite-resolution边界。","V&V负结果","不以单个component PASS恢复总体V2。"),
 failure("F-H01","H target attribution问题","Stage 02D–I","QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY","six-component attribution","temporal/reference/quadrature污染，部分target只能node residual。","高分辨率SPH并非自动truth。","same-state与独立reference修复了部分污染。","jitter pair-only范围有限。","scientific",True,"推动R2S、Fourier/analytic与pair-only scope。","target资格链","target非零不等于可训练。"),
 failure("F-I01","I dataset lineage/leakage问题","Stage 02J","CONTROLLED_REGULAR_DATASET_NOT_READY","lineage split gate","5 records属于单一leakage component。","粒子/边/patch随机切分会泄漏。","canonical/schema/QC本身通过。","更广泛跨问题泛化未测试。","scientific",True,"Stage02J-W形成4 lineage、10/5/5 blind split。","数据治理","家族血缘先于随机切分。"),
 failure("F-J01","J regularity contract问题","Stage 02J-S/T/V","REGULARITY_HARD_GATE_ROUTE_TERMINATED","negative control/cross-mode/invariance","v0.2 false positive、v0.3 cross-mode、v0.4 9/192 invariance失败。","regularity统计量不足以作为必要且稳定的资格硬门。","不是dataset生成或架构失败。","可能仍有诊断价值。","scientific",False,"hard-gate路线终止；regularity降为diagnostic。","前瞻证伪","失败后不校阈值。"),
 failure("F-K01","K architecture representability问题","Stage 02K","PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED","representability/structure gates","K1/K2结构门通过。","此类别未观察架构硬失败，但representability不等于learnability。","结构错误被排除。","attention necessity未建立。","scientific",True,"允许进入协议，但不宣称Transformer优越。","结构/学习分离","合格组件不得提升为性能PASS。"),
 failure("F-L01","L optimization conditioning问题","Stage 02M-R",s2mr["status"],"tangent/conditioning diagnostics","K1 selected-head 2 seeds通过，K2 selected-head/whole 0。","优化conditioning与尺度影响训练门。","结构门通过；test seal无泄漏。","不能证明conditioning是所有任务的一般主因。","scientific",False,"促成v0.2监督尺度与新blind families。","失败归因","归因诊断不等于训练资格。"),
 failure("F-M01","M static learnability问题","Stage 02M/M-Q",s2mq["status"],"A–E frozen gates",f"v0.1={s2m['status']}; v0.2={s2mq['status']}; K1 train-pass={s2mq['K1']['B_train_fit_pass_seed_count']}; K2={s2mq['K2']['B_train_fit_pass_seed_count']}","train-fit硬门未满足，即使validation/test transfer与守恒通过。","不是架构实现错误；不是test泄漏。","局部因果动态任务是否更可学未知。","scientific",False,"static route终止；Stage02N未授权。","负结果论文","transfer PASS不能覆盖train FAIL。"),
 failure("F-N01","N dynamic implementation问题","Stage 03C","DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED","implementation gates","D0、zero correction、checkpoint、one-step AD通过。","未观察实现硬失败；多步问题属于后续资格层。","bitwise baseline与结构语义已排除。","跨后端完整动态训练未知。","scientific",True,"授权Stage03D而不授权训练。","动态实现合同","实现验证不是performance。"),
 failure("F-O01","O multistep differentiability问题","Stage 03D/03D-R",s3d["final_status"],"360-probe stable-window/history gates",f"required={c['required_probe_count']}; stable={c['stable_epsilon_window_count']}; failures={c['required_probe_count']-c['stable_epsilon_window_count']}; history={c['history_gradient_pass_count']}/6","固定拓扑AD/FD稳定窗及history门失败。","FD conditioning、非光滑、结构零与history attenuation混合。","reverse/JVP 60/60；per-stage conservation 540/540。","19项归因未解析；backend sensitivity存在。","scientific",False,"Stage03E未授权；路线暂停。","梯度验证负结果","多epsilon稳定窗比单epsilon更严格。"),
 failure("F-P01","P topology-event问题","Stage 03D","TOPOLOGY_EVENT_COMPONENT_QUALIFIED","TE1 replay/fixed-side gradient","birth/death、6/6 replay、12/12 fixed-side gradient通过。","拓扑分量是piecewise-smooth边界，不代表可微neighbor search。","event-side测试排除非确定性。","跨事件总导数不作资格主张。","scientific",True,"保留为QUALIFIED_COMPONENT。","拓扑验证","分量PASS与总体NOT_QUALIFIED并存。"),
 failure("F-Q01","Q evidence/provenance问题","Stage 01F5-P/P1/P2","EXECUTION_MANIFEST_INCOMPLETE → repaired","manifest/hash/claim gates","Stage01F5-P暴露N64依赖不全；P1/P2后续完成claim与文献审计。","复杂工作流中合同完整性本身是资格前置。","未发生静默历史改写。","Stage04私有验证区有不可读文件。","infrastructure",True,"引入freeze、sealed test、delta manifest与claim audit。","证据治理","缺证据必须是EVIDENCE_INCOMPLETE。"),
 failure("F-R01","R 未执行或未授权事项","Stage 02/03","NOT_AUTHORIZED / NOT_EXECUTED","authorization gates","dynamic training、autonomous rollout、solver-in-the-loop、full performance evaluation均为0。","上游static fit和multistep gradient未资格。","不是执行失败。","Stage04结果未知。","not_executed",False,"不得产生性能或优越性主张。","发表边界","未执行必须显式可见。"),
]
write_json("04_failure_register/complete_failure_register.json",{"schema":"s1.failure-register.v1","events":failures,"category_coverage":[chr(x) for x in range(ord('A'),ord('R')+1)]})

deep = f"""# 完整失败登记与十项深度分析

[PROJECT_EVIDENCE] 本登记保留基础设施失败、科学失败、NOT_QUALIFIED 与 NOT_EXECUTED 的差异。

{md_table(['ID','类别','阶段','exact status','直接原因','后续影响'],[(f['id'],f['category'],f['stage'],f['exact_status'],f['direct_cause'],f['downstream_effect']) for f in failures])}

## 1. Stage 01B V1 failure

[PROJECT_EVIDENCE] kernel consistency 与 manufactured Laplacian 在10% jitter高分辨率反弹；variable-density viscosity与mixed-sign pressure不满足严格pair内部力结构；上游generic Laplacian三步backward在`h_i=None`失败。因此`V1_FAIL`是已执行硬门失败。Stage01C用唯一pair几何、10-seed ensemble、对称pair作用和native PyTorch AD修复C1–C4，但没有回写Stage01B。

## 2. Stage 01D资源增长

[PROJECT_EVIDENCE] 旧N32 smoke触发RSS增长门；D-R复核仍见post-warm-up增长，D-R2/R3未唯一归因，D-R4在正确weakref语义下重新检测retention，D-R5显示GC-disabled线性而default-GC 2000步上包络有界。D-P的1600步隔离子进程canary通过。[INFERENCE] 最稳妥结论是“有界GC延迟与生命周期效应”，不是简单memory leak；旧`V2_FAIL`不变。

## 3. Stage 01D2 V2 failure

[PROJECT_EVIDENCE] 时间序列可解释，但空间误差非单调；jitter显著恶化并触发冻结资源/无序门，最终为`{s1d2['final_status']}`。这些门已执行，因此是FAIL；V3不能开始。

## 4. Stage 01E model-form mismatch

[PROJECT_EVIDENCE] 210个静态case闭合最大Linf为`{s1e['maximum_closure_linf']:.6e}`；EOS/operator比`{s1e['EOS_to_pressure_operator_ratio']:.6g}`，EOS/viscosity比`{s1e['EOS_to_viscosity_ratio']:.6g}`。不可压TGV解析压力与WCSPH EOS初值不相容，推动WCSPH-compatible MMS；该归因不恢复V2。

## 5. Stage 01F3/F3B/F3C convergence gates

[PROJECT_EVIDENCE] F3与F3B均保持`MMS_CONVERGENCE_VERIFICATION_FAIL`；F3-R只资格化same-semidiscrete dense-equivalent reference；F3C虽见近二阶时间行为，但cancellation/plateau门仍失败，状态`{s1f3c['status']}`。因此后续建立前瞻性plateau-aware协议，并保留旧失败。

## 6. Stage 01G V2 failure

[PROJECT_EVIDENCE] acoustic gates通过，但shear N48 decay-rate相对误差`0.0279495032685`超过`0.02`。Stage01H将其分类为`{s1h['classification']}`，时间步贡献极小、重复bitwise一致；由于H/dx与N共变，不能宣称viscosity operator-form failure。

## 7. Stage 02 target/reference failures

[PROJECT_EVIDENCE] Stage02D–I依次暴露temporal contamination、spatial attribution不足、quadrature/reference角色混淆与pair-only conservation scope；Stage02J-S/T/V前瞻证伪regularity hard gate。修正链是same-state target → independent Fourier/analytic reference → pair-only scope → lineage-based blind dataset；任何中间candidate都未被追认为旧PASS。

## 8. Stage 02 static fitting failure

[PROJECT_EVIDENCE] v0.1状态`{s2m['status']}`；v0.2状态`{s2mq['status']}`。v0.2 K1 train-fit通过seed数`{s2mq['K1']['B_train_fit_pass_seed_count']}`，K2为`{s2mq['K2']['B_train_fit_pass_seed_count']}`；validation/test各有3个seed通过且守恒保持，但冻结B门要求整体train fit，故不能把transfer PASS写成模型成功。M-R支持optimization conditioning归因，监督尺度`a_sup={s2mq['a_sup']}`后仍未资格，static route必须终止。

## 9. Stage 03D multistep gradient failure

[PROJECT_EVIDENCE] 机器清单记录`{c['required_probe_count']}` probes、`{c['stable_epsilon_window_count']}` stable windows、`{c['required_probe_count']-c['stable_epsilon_window_count']}` failures、history `{c['history_gradient_pass_count']}/6`、per-stage conservation `{c['per_stage_conservation_pass_count']}/{c['per_stage_conservation_count']}`。D-R的reverse/JVP 60/60与extended FD不能覆盖stable-window失败；backend sensitivity、conditioning/non-smooth/structural-zero与history attenuation共同导致`{s3dr['final_status']}`。

## 10. 未执行事项

[PROJECT_EVIDENCE] dynamic training、autonomous rollout、solver-in-the-loop与full performance evaluation均为`NOT_AUTHORIZED / NOT_EXECUTED`。它们不是失败，也没有可用的训练曲线、性能优势或成本结论。
"""
write_md("04_failure_register/complete_failure_register.md",deep)

tree={"root":"PROJECT_ROUTE","children":[
 {"node":"Stage01 V&V","children":[{"node":"V1 implementation/structure failures","effect":"Stage01C repair"},{"node":"V2/model-form/finite-resolution failures","effect":"MMS + independent validation boundaries"}]},
 {"node":"Stage02 static PIO","children":[{"node":"target/reference/data hard gates","effect":"qualified blind static dataset"},{"node":"regularity falsification","effect":"diagnostic-only"},{"node":"static fitting not qualified","effect":"route terminated"}]},
 {"node":"Stage03 dynamic hybrid","children":[{"node":"implementation qualified","effect":"Stage03D authorized"},{"node":"multistep gradients not qualified","effect":"Stage03E not authorized"},{"node":"topology component qualified","effect":"retained component evidence"}]},
 {"node":"Unexecuted","children":[{"node":"training/rollout/performance","status":"NOT_AUTHORIZED/NOT_EXECUTED"}]}]}
write_json("04_failure_register/failure_causal_tree.json",tree)
write_md("04_failure_register/failure_causal_tree.md","# 失败因果树\n\n```text\nPROJECT_ROUTE\n├─ Stage01 V&V\n│  ├─ V1实现/结构失败 → Stage01C修复\n│  └─ V2模型形式/有限分辨率 → MMS与独立验证边界\n├─ Stage02 static PIO\n│  ├─ target/reference/data门 → blind static dataset\n│  ├─ regularity硬门证伪 → diagnostic-only\n│  └─ static fitting未资格 → 路线终止\n├─ Stage03 dynamic hybrid\n│  ├─ implementation qualified\n│  ├─ multistep gradient NOT_QUALIFIED → Stage03E未授权\n│  └─ topology QUALIFIED_COMPONENT\n└─ training/rollout/performance → NOT_AUTHORIZED/NOT_EXECUTED\n```\n\n[INFERENCE] 树表达因果依赖，不把后续修复当作历史失败消失。")


innovation_titles=[
"不把高分辨率SPH自动称为真值","候选reference资格认定链","WCSPH-compatible MMS与双路径闭合审计","same-semidiscrete DOP853角色分离","plateau-aware temporal/spatial verification","source-free shear/acoustic验证边界","pair-force antisymmetry硬保证线动量守恒","family-lineage leakage graph与blind split","regularity hard-gate前瞻校准和证伪","static learnability与architecture correctness分离","optimization conditioning量化归因","bitwise zero-correction equivalence","RK2 start/midpoint graph rebuild与accepted-only history commit","D0/D1/D2/D3公平比较合同","D-R1/D-R2/D-R3/D-R4 reference hierarchy","360-probe multistep AD/FD stable-window qualification","reverse/JVP、extended FD、history attenuation、backend sensitivity联合诊断","deterministic cutoff birth/death与fixed-side gradient资格","topology component PASS与overall gradient NOT_QUALIFIED分层","全程保留失败并禁止结果后改门"]
cats=["A 科学认识","D reference治理","B 数值方法","C V&V方法","C V&V方法","A 科学认识","E 守恒神经架构","D 数据治理","C V&V方法","I 负结果治理","G 梯度验证","F 动态求解器","F 动态求解器","E 守恒神经架构","D reference治理","G 梯度验证","G 梯度验证","H 拓扑事件","H 拓扑事件","J 工程可复现性"]
p2_by={x['id']:x for x in novelty_p2}
innov=[]
for idx,title in enumerate(innovation_titles,1):
    ext = p2_by.get(f"N{idx-11}") if 12 <= idx <= 17 else None
    literature = ext["conclusion"] if ext else "POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION"
    evidence = timeline[min(len(timeline)-1, max(0, idx+8))]["authorized_input"]
    if idx in (12,13,16,17,18,19,20): evidence = "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json; publication P2 novelty matrix"
    innov.append({"id":f"I{idx:02d}","category":cats[idx-1],"exact_contribution":title,"supporting_artifacts":[evidence],"evidence_strength":"PROJECT_EVIDENCE_STRONG_INTERNAL" if idx not in (6,10,11) else "PROJECT_EVIDENCE_SCOPED","nearest_internal_predecessor":"preceding failed/limited stage in timeline","limitation":"仅限冻结SPH-PIO-PoC合同与case scope","potentially_publishable":True,"likely_generalizable":"requires cross-problem validation","literature_verification":literature,"prohibited_overclaim":"不得使用first/unprecedented/novel的绝对措辞；不得暗示训练或性能成功。"})
write_json("05_innovation_register/complete_innovation_register.json",{"schema":"s1.innovation-register.v1","innovations":innov})
write_json("05_innovation_register/innovation_evidence_map.json",{"schema":"s1.innovation-evidence-map.v1","map":[{"innovation_id":x['id'],"artifacts":x['supporting_artifacts'],"strength":x['evidence_strength'],"literature_status":x['literature_verification']} for x in innov]})
write_md("05_innovation_register/complete_innovation_register.md","# 全项目创新与突破登记\n\n[PROJECT_EVIDENCE] “创新”在本表首先指内部方法贡献；外部新颖性必须服从P2或标为待核验。\n\n"+md_table(["ID","类别","贡献","内部证据","外部新颖性","边界"],[(x['id'],x['category'],x['exact_contribution'],x['evidence_strength'],x['literature_verification'],x['limitation']) for x in innov]))


progress_rows=[
("Stage01B V1_FAIL","重复边/参数路径/backward与pair结构诊断","唯一pair几何、native AD、对称作用","Stage01C C1–C4 PASS","动态V2仍需检验"),
("Stage01D resource FAIL","RSS/weakref/topology/GC分层诊断","隔离子进程、default-GC、最大horizon canary","D-P政策PASS","旧V2失败与具体循环归因保留"),
("Stage01D2/01E","V2非单调与EOS模型形式分解","WCSPH-compatible MMS","F/F2规格与实现PASS","独立物理V2未恢复"),
("F3/F3B/F3C","reference、plateau、cancellation","same-semidiscrete reference与plateau-aware合同","F5B requalification PASS","只支持MMS合同"),
("Stage01G shear FAIL","finite-resolution/effective viscosity诊断","保留H/dx–N共变边界","acoustic component与diagnosis完整","operator-form failure未确认"),
("Stage02 target/data failures","污染、conservation、lineage、regularity诊断","独立reference、pair-only、blind lineage、regularity diagnostic-only","J-W dataset READY；K architecture qualified","static learnability失败"),
("Stage02M/M-Q","conditioning/supervision scale","v0.2前瞻合同","transfer/conservation证据更完整","train-fit仍未资格，路线终止"),
("Stage03D","stable-window/history/reverse/JVP/FD/backend联合诊断","分量与总体状态分层","topology component qualified","multistep gradient mixed/unresolved；训练未授权"),]
write_md("12_reports/how_failures_generated_methodological_progress.md","# 失败如何生成方法学进展\n\n[PROJECT_EVIDENCE] 失败不是可删除的无效工作：它们冻结了假设的证伪边界，并改变了后续合同。\n\n"+md_table(["Failure","Diagnosis","Contract correction","New evidence","Remaining boundary"],progress_rows)+"\n\n[INFERENCE] 代码缺陷主要集中在Stage01B接口/邻域/backward与Stage01G执行基础设施；科学假设证伪集中在模型形式、regularity hard gate、static learnability和multistep differentiability；评价门设计问题由F3系列暴露并以不回写旧结论的方式修正。")


claims=[
("C01","SUPPORTED","Stage03C实现已验证。","动态模型整体已验证并优于基线。","Stage03C","stage03c_final_manifest.json","仅实现/one-step范围","Paper1 main"),
("C02","SUPPORTED","zero correction对D0为288/288 bitwise等价。","训练后仍保证所有轨迹bitwise等价。","Stage03C","stage03c_final_manifest.json","只对冻结zero-correction测试","Paper1 main"),
("C03","SUPPORTED","K1/K2 pair antisymmetry硬保证线动量守恒。","所有物理守恒与耗散均已验证。","Stage02K/03C","stage02k_qualification_summary.json","角动量/耗散边界另列","Paper1 main"),
("C04","SUPPORTED","TE1 cutoff birth/death拓扑分量通过6/6 replay和12/12 fixed-side gradients。","neighbor search整体可微。","Stage03D","stage03d_final_manifest.json","piecewise fixed-side component","Paper1 main"),
("C05","CONDITIONAL","360 probes中216具有stable epsilon windows。","多步梯度已资格化。","Stage03D","stage03d_final_manifest.json","144失败、history 0/6","Paper1 main negative"),
("C06","SUPPORTED","static pair-force fitting v0.2未资格。","静态pair correction不可学习的一般定律。","Stage02M-Q","stage02mq_qualification_summary.json","仅冻结dataset/protocol/arms","Paper1 negative"),
("C07","SUPPORTED","多步AD/FD整体未资格。","梯度完全错误或完全不可用。","Stage03D-R","stage03dr_final_manifest.json","reverse/JVP与topology分量通过","Paper1 negative"),
("C08","NOT_TESTED","dynamic training未授权且未执行。","已训练动态Transformer。","Stage03","stage03ds_final_manifest.json","training_runs=0","Future Paper2"),
("C09","NOT_TESTED","autonomous rollout未执行。","rollout稳定或优于SPH。","Stage02/03","stage02ms/stage03ds manifests","rollouts=0","Future Paper2"),
("C10","UNSUPPORTED","Stage01最终仍为V2_QUALIFICATION_FAIL。","Stage01 V2已恢复。","Stage01G/H","stage01g_evaluation_reapplication_01.json","acoustic局部PASS不覆盖shear FAIL","Prohibited"),
("C11","UNSUPPORTED","K2结构资格化但attention superiority未建立。","Transformer优于MLP。","Stage02K/M-Q","stage02mq_qualification_summary.json","无合格公平性能比较","Prohibited"),
("C12","NOT_TESTED","full solver improvement/cost/utility未执行。","求解器更准确、更快或更便宜。","Project","evidence matrix L8–L10","无性能/成本证据","Future Paper2"),]
claim_data=[{"id":a,"classification":b,"allowed_wording":c,"prohibited_wording":d,"supporting_stage":e,"artifact":f,"limitation":g,"potential_manuscript_role":h} for a,b,c,d,e,f,g,h in claims]
write_json("07_claim_boundary/project_wide_claim_boundary.json",{"schema":"s1.claim-boundary.v1","claims":claim_data})
write_md("07_claim_boundary/project_wide_claim_boundary.md","# 全项目主张边界\n\n"+md_table(["ID","分类","允许措辞","禁止措辞","限制","稿件角色"],[(x['id'],x['classification'],x['allowed_wording'],x['prohibited_wording'],x['limitation'],x['potential_manuscript_role']) for x in claim_data]))


# Artifact inventory and publication asset inventories.
artifacts=[]
for i,x in enumerate(freeze["files"],1):
    artifacts.append({"artifact_id":f"A{i:05d}",**x,"inventory_status":"existing","claim_supported":bool(x["final_evidence_candidate"] or x["manifest_membership"]),"audit_note":"checkpoint bodies not loaded" if "checkpoint" in x["role"] else "read-only indexed"})
inv={"schema":"s1.complete-artifact-inventory.v1","source_freeze":"00_freeze/project_wide_input_freeze_manifest.json","artifact_count":len(artifacts),"artifacts":artifacts}
write_json("01_artifact_inventory/complete_artifact_inventory.json",inv)

def asset(rel,kind):
    p=rel["path"].lower(); existing=True
    internal=any(k in p for k in ("raw/","logs/","failure","checkpoint","internal_only","freeze/"))
    main=rel["final_evidence_candidate"] and not internal
    supp=not main and not internal
    return {"path":rel["path"],"sha256":rel["sha256"],"existing":existing,"derivable_from_existing_results":False,"requires_new_computation":False,"main_text_suitable":main,"supplement_suitable":supp,"internal_only":internal,"duplicated_across_potential_papers":kind in {"figure","table"} and ("stage02" in p or "stage03" in p),"claim_supported":bool(rel["manifest_membership"] or rel["final_evidence_candidate"])}
files=freeze["files"]
fig=[asset(x,"figure") for x in files if Path(x["path"]).suffix.lower() in {".png",".jpg",".jpeg",".svg",".tif",".tiff"}]
tab=[asset(x,"table") for x in files if Path(x["path"]).suffix.lower() in {".csv",".tsv",".xlsx"} or "table" in Path(x["path"]).name.lower()]
dat=[asset(x,"data") for x in files if x["machine_readable"] and Path(x["path"]).suffix.lower() not in {".py",".xlsx",".csv",".tsv"}]
code=[asset(x,"code") for x in files if Path(x["path"]).suffix.lower() in {".py",".sh",".zsh"}]
mans=[asset(x,"manuscript") for x in files if Path(x["path"]).suffix.lower() in {".docx",".md",".pdf",".bib",".ris",".enw"} and any(k in x["path"].lower() for k in ("publication","research_record","manuscript","report"))]
derivable_figs=["project-wide qualification pipeline","failure-to-method progress map","evidence-level heatmap","Stage04 decision tree"]
for name in derivable_figs: fig.append({"path":f"DERIVABLE::{name}","sha256":None,"existing":False,"derivable_from_existing_results":True,"requires_new_computation":False,"main_text_suitable":True,"supplement_suitable":False,"internal_only":False,"duplicated_across_potential_papers":False,"claim_supported":True})
for name,data in [("figure",fig),("table",tab),("data",dat),("code",code),("manuscript",mans)]:
    write_json(f"08_publication_assets/{name}_asset_inventory.json",{"schema":f"s1.{name}-assets.v1","count":len(data),"assets":data})


optionA=f"""# Option A：Stage 00–04 单篇整合论文

[PUBLICATION_RECOMMENDATION] 只有Stage04E/F/G强通过、独立验证与refinement充分、D3相对D0/D1/D2存在稳定且等误差优势时才优先。

- 主线：V&V → reference → conservative architecture → dynamic implementation → training → rollout → independent validation → cost。
- 最强贡献：端到端verification-first资格链，同时保留static与gradient负结果。
- 所需Stage04：task-aligned gradients、训练资格、autonomous rollout、独立验证、refinement、cost全部形成机器证据。
- CMAME潜力：[INFERENCE] 高，但篇幅和叙事复杂度最高；需将完整失败矩阵移入补充材料，正文仍必须可见关键负结果。
- 风险：Stage04任何关键门不通过都会使“完整solver论文”主线断裂；不可用局部训练曲线掩盖Stage01/02/03失败。
"""
optionB="""# Option B：拆分两篇

## Paper 1：Stage 00–03 verification-first方法论文

- Research question：保守dynamic neural-SPH在训练前如何通过reference、结构、零修正、多步梯度和拓扑事件资格链？
- Contribution：失败保留的V&V链、static learnability负结果、360-probe梯度边界、拓扑分量资格。
- Figures/Tables：pipeline、timeline、failure tree、evidence hierarchy、AD/FD矩阵、topology；状态账本与claim boundary。
- Title candidates：*Verification-first qualification of conservative dynamic neural–SPH solvers*；*From reference qualification to multistep gradient limits in neural SPH*。
- Target level：[PUBLICATION_RECOMMENDATION] CMAME/Journal of Computational Physics层级需突出一般方法；若一般性不足则选择更专门的计算力学/数值方法期刊。
- Fatal weakness：单一项目/问题范围，且没有训练性能；必须把论文定位为资格方法与负结果，而非solver success。

## Paper 2：Stage 04 dynamic training and performance

- Research question：local-causal dynamic training是否在合格梯度、rollout、独立验证和成本门下优于D0/D1/D2？
- Contribution：只能来自Stage04新证据；Stage00–03仅作共享背景。
- Required additions：合格训练、autonomous rollout、refinement、independent validation、cost与失败证据。
- Fatal weakness：若只有短窗fit或单case improvement，不足以形成完整性能论文。
"""
optionC="""# Option C：Stage 04 未成功时的verification-only fallback

[PUBLICATION_RECOMMENDATION] 以verification-first、gradient qualification limits、topology-event qualification与negative-result methodology为主线。其独立价值来自“训练前资格链揭示哪些组成分量成立、哪些整体门失败”，不依赖Stage04成功。

不会破坏独立价值的Stage04结果包括：task-aligned gradient仍未资格、训练未资格、rollout失败、改进仅局限单case、独立验证/refinement不足。它们应作为后续证据或限制，不得回写Stage00–03。
"""
write_md("09_publication_options/publication_option_A_single_integrated_paper.md",optionA)
write_md("09_publication_options/publication_option_B_two_paper_split.md",optionB)
write_md("09_publication_options/publication_option_C_verification_only_fallback.md",optionC)
option_matrix={"schema":"s1.publication-options.v1","options":[
{"option":"A","when":"Stage04 E/F/G strong PASS + independent validation/refinement/cost","strength":"complete end-to-end narrative","risk":"highest dependency and length","recommendation":"conditional"},
{"option":"B","when":"Stage00–03 methods generalizable and Stage04 has distinct performance question","strength":"clear contribution separation","risk":"overlap/self-plagiarism","recommendation":"preferred default after a successful but distinct Stage04"},
{"option":"C","when":"Stage04 gradients/training/rollout not qualified","strength":"independent verification and negative-result value","risk":"must avoid solver-success framing","recommendation":"preferred fallback"}]}
write_json("09_publication_options/publication_option_comparison_matrix.json",option_matrix)


overlap_items=[
("equations","SHARED_BACKGROUND_ONLY","PAPER_2_PRIMARY","基础方程可简述并交叉引用；不重复完整推导"),
("reference","PAPER_1_PRIMARY","SHARED_BACKGROUND_ONLY","Paper2仅引入训练所需摘要"),
("architecture","PAPER_1_PRIMARY","SHARED_BACKGROUND_ONLY","结构合同一次作为主贡献"),
("zero correction","PAPER_1_PRIMARY","SUPPLEMENT_ONLY","Paper2不得再次作为主创新"),
("AD/FD","PAPER_1_PRIMARY","SHARED_BACKGROUND_ONLY","Stage04新task-aligned梯度可属Paper2"),
("topology","PAPER_1_PRIMARY","SUPPLEMENT_ONLY","相同TE1结果不可重复"),
("dataset","SUPPLEMENT_ONLY","PAPER_2_PRIMARY","Paper1讲资格原则，Paper2讲Stage04训练数据"),
("training","CANNOT_REPEAT","PAPER_2_PRIMARY","Paper1明确NOT_EXECUTED"),
("rollout","CANNOT_REPEAT","PAPER_2_PRIMARY","Paper1不得有性能结论"),
("validation","SHARED_BACKGROUND_ONLY","PAPER_2_PRIMARY","Stage01独立验证只作边界；Stage04新验证为Paper2"),
("figures","DUPLICATION_RISK","DUPLICATION_RISK","同一图不在两篇重复；只允许重新绘制共享背景小图"),
("tables","DUPLICATION_RISK","DUPLICATION_RISK","状态表与性能表分属不同论文"),
("conclusions","PAPER_1_PRIMARY","PAPER_2_PRIMARY","Paper1结论是资格边界；Paper2结论是性能与效用")]
overlap={"schema":"s1.cross-paper-overlap.v1","labels":["PAPER_1_PRIMARY","PAPER_2_PRIMARY","SHARED_BACKGROUND_ONLY","SUPPLEMENT_ONLY","DUPLICATION_RISK","CANNOT_REPEAT"],"rows":[{"item":a,"paper1":b,"paper2":c,"rule":d} for a,b,c,d in overlap_items]}
write_json("09_publication_options/cross_paper_overlap_matrix.json",overlap)
write_md("09_publication_options/anti_salami_publication_rules.md","# 反切香肠与重复发表规则\n\n1. 同一冻结结果只能在一篇论文中作为主贡献；另一篇仅作带引用的背景。\n2. Stage03C zero-correction、Stage03D 360-probe与TE1图表归Paper1；Stage04训练/rollout/refinement/cost归Paper2。\n3. 禁止同一图表换色或裁剪后重复；共享方程只保留最小背景并交叉引用。\n4. Paper1结论是资格边界和负结果方法；Paper2结论必须由Stage04新证据产生。\n5. 两稿同步披露相关稿件、共享数据/代码与前序结果。\n6. 若Paper2没有独立问题、独立结果和独立图表包，则合并而非拆分。")


scenarios=[
(1,"Stage04C task-aligned gradient仍未资格化","C","high","task-aligned gradient machine gates","独立投稿Stage00–03 verification paper","低：边界清楚","specialist/high-impact methods conditional"),
(2,"Stage04C通过但Stage04E训练未资格化","C or B(Paper1 first)","high","gradient PASS + training FAIL evidence","Stage00–03为主；Stage04作限制/技术报告","中","methods journal"),
(3,"Stage04E训练通过但Stage04F autonomous rollout未通过","B","medium","training gates + failed rollout","Paper2仅能是短窗学习论文；不宜完整CMAME主线","中高","specialist ML/physics methods"),
(4,"Stage04E/F通过但独立验证或refinement不足","B, Paper1 first","high","rollout PASS; validation/refinement incomplete","延后性能论文","中","Paper1 methods; Paper2 pending"),
(5,"Stage04E/F/G强通过且D3稳定独立等误差优于D0/D1/D2","A evaluate first","medium","training+rollout+validation+refinement+cost","评估完整CMAME整合稿","高：篇幅/叙事","CMAME/JCP potential"),
(6,"Stage04成功且Stage00–03框架跨模型/跨问题一般","B","medium","cross-model/cross-problem evidence","仍可拆分方法与性能，但严控重叠","中","two high-level papers possible"),]
decision={"schema":"s1.post-stage04-decision-tree.v1","scenarios":[{"scenario":a,"condition":b,"recommended_option":c,"confidence":d,"required_evidence":e,"merge_split_rationale":f,"publication_risk":g,"expected_journal_tier":h} for a,b,c,d,e,f,g,h in scenarios]}
write_json("10_merge_split_decision/post_stage04_merge_split_decision_tree.json",decision)
write_md("10_merge_split_decision/post_stage04_merge_split_decision_tree.md","# Stage 04后合并/拆分决策树\n\n"+md_table(["Scenario","条件","建议","信心","所需证据","理由","风险/期刊"],scenarios))


schema={"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Stage04EvidenceImport","type":"object","required":["schema_version","stage04_final_statuses","training_gates","model_results","rollout","validation","refinement","cost","failure_evidence","hashes"],"properties":{
"schema_version":{"const":"s1.stage04-import.v1"},"stage04_final_statuses":{"type":"array"},"training_gates":{"type":"array"},"model_results":{"type":"array"},"rollout":{"type":"object"},"validation":{"type":"object"},"refinement":{"type":"object"},"cost":{"type":"object"},"failure_evidence":{"type":"array"},"hashes":{"type":"array"},"historical_stage00_03_rewrite":{"const":False}}}
write_json("11_stage04_update_interface/stage04_evidence_import_schema.json",schema)
write_md("11_stage04_update_interface/stage04_decision_update_template.md","# Stage04决策增量更新模板\n\n- 导入日期：\n- Stage04 exact final statuses：\n- Task-aligned gradient：\n- Training gates：\n- Model arms D0/D1/D2/D3：\n- Autonomous rollout：\n- Independent validation：\n- Refinement：\n- Cost/utility：\n- Failure evidence：\n- Hash verification：\n- 匹配Scenario：\n- [PUBLICATION_RECOMMENDATION] 更新建议：\n\n约束：只导入Stage04 delta，不重新扫描或改写Stage00–03。")
write_json("11_stage04_update_interface/stage04_delta_manifest_template.json",{"schema_version":"s1.stage04-delta.v1","created_utc":"<ISO-8601>","base_s1_manifest_sha256":"<sha256>","stage04_artifacts":[],"historical_stage00_03_rewrite":False,"hash_verification":"PENDING","decision_scenario":"PENDING"})


sections=[
("1. 项目起源与核心科学问题","[PROJECT_EVIDENCE] 项目起点是把SPH物理求解与可学习粒子相互作用/动态历史结合，但很快把核心问题改写为：在任何训练与性能主张之前，reference、离散、结构、数据、梯度和拓扑证据是否分别合格。"),
("2. 原始SPH–Transformer设想","[PROJECT_EVIDENCE] 原设想包含静态pair correction和动态Transformer历史closure。[INFERENCE] 项目后续最重要的修正，是不再把架构存在等同于可学习、可微、可rollout或优于基线。"),
("3. V&V方法论修正","[PROJECT_EVIDENCE] 项目建立L0–L10证据层、预注册硬门、失败保留、sealed test、hash freeze与组成分量/总体状态分层。"),
("4. Stage00环境资格","[PROJECT_EVIDENCE] CPU/MPS请求操作通过；MPS邻域为CPU桥接的hybrid路径；full diffSPH execution在Stage00仍不可判断。"),
("5. Stage01数值验证完整过程","[PROJECT_EVIDENCE] 时间线覆盖V0执行、V1算子、资源诊断、V2重资格、模型形式归因、WCSPH MMS、plateau-aware重资格与独立shear/acoustic验证。最终Stage01仍为V2_QUALIFICATION_FAIL。"),
("6. Stage01全部失败与修复","[PROJECT_EVIDENCE] V1实现/结构缺陷由Stage01C修复；资源增长由D-R至D-P形成有界GC政策；TGV模型形式错配推动MMS；严格收敛门推动plateau-aware协议；shear失败被限定为finite-resolution dominant。所有旧FAIL保持。"),
("7. Stage01最终边界","[PROJECT_EVIDENCE] acoustic component PASS与MMS requalification PASS不能覆盖独立shear门；Stage01 V2未恢复，viscosity operator-form failure未确认。"),
("8. Stage02 PIO理论","[PROJECT_EVIDENCE] Stage02A冻结增量pair-force、reference hierarchy、守恒/对称与标签资格合同；理论完整不等于数据或模型性能。"),
("9. target/reference/dataset路线","[PROJECT_EVIDENCE] D–I逐步分离temporal/spatial/reference/quadrature与conservation；J暴露单lineage泄漏；J-W最终形成20-record、4-lineage、10/5/5 split的blind static dataset。"),
("10. Stage02 static training及失败",f"[PROJECT_EVIDENCE] v0.1为{s2m['status']}，v0.2为{s2mq['status']}。K1/K2 validation/test transfer与守恒局部通过，但train-fit硬门不满足；static route终止。"),
("11. Stage02主要创新与边界","[PROJECT_EVIDENCE] 贡献在reference/target资格链、pair antisymmetry、lineage split、regularity前瞻证伪、结构正确性与learnability分离、conditioning归因。边界是没有rollout/solver consequence。"),
("12. Stage03动态新假设","[PROJECT_EVIDENCE] D0–D3引入因果历史、动态图和zero-correction合同；短历史改善closure仍未测试。"),
("13. dynamic reference hierarchy","[PROJECT_EVIDENCE] D-R1/D-R2/D-R3在各自范围资格化；acoustic仅linear-regime conditional，periodic vortex不是exact source-free，D-R4 physical validation不可用。"),
("14. D0–D3实现","[PROJECT_EVIDENCE] Stage03C验证独立RK2、D0–D3接口、start/midpoint graph rebuild、accepted-only history commit、checkpoint与one-step autograd。"),
("15. zero correction与守恒","[PROJECT_EVIDENCE] zero correction 288/288 bitwise；pair-force结构和stage conservation在冻结门内通过。不得外推到训练后性能。"),
("16. multistep AD/FD",f"[PROJECT_EVIDENCE] {c['required_probe_count']} probes中{c['stable_epsilon_window_count']} stable、{c['required_probe_count']-c['stable_epsilon_window_count']}失败；history {c['history_gradient_pass_count']}/6；总体NOT_QUALIFIED。"),
("17. topology event","[PROJECT_EVIDENCE] cutoff birth/death、6/6 deterministic replay、12/12 fixed-side gradient通过；这是QUALIFIED_COMPONENT，不是可微neighbor search总体声明。"),
("18. Stage03失败归因","[PROJECT_EVIDENCE] reverse/JVP、extended FD、horizon与backend联合诊断支持mixed/unresolved；19项仍未解析，history influence强衰减。"),
("19. Stage03暂停原因","[PROJECT_EVIDENCE] Stage03E authorization=false；多步梯度硬门失败，训练、rollout、性能均未执行，因此路线PAUSED而非训练失败。"),
("20. 项目所有创新登记","[PROJECT_EVIDENCE] 20项内部贡献见innovation register。[LITERATURE_VERIFICATION_REQUIRED] 未在P2直接覆盖者统一标为POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION。"),
("21. 项目所有未解决问题","[PROJECT_EVIDENCE] 包括Stage01支持尺度独立性、static learnability的一般性、history attenuation机制、19项gradient归因、D-R4、动态训练/rollout/refinement/cost。"),
("22. 可发表证据","[PUBLICATION_RECOMMENDATION] 主文适合资格链、关键失败、reference角色、zero-correction、结构守恒、360-probe总体结果、topology分量与claim boundary。"),
("23. 只能放补充材料的证据","[PUBLICATION_RECOMMENDATION] 全量seed/checkpoint/hash、完整probe矩阵、每case reference/QC、资源重复与全部状态账本放补充材料，并在正文保留汇总与失败可见性。"),
("24. 只能内部保存的证据","[PUBLICATION_RECOMMENDATION] 临时launch日志、私有验证访问控制、冗长debug traces和不进入资格的内部seals只保留审计；不得用作主张。"),
("25. 单篇整合方案","[PUBLICATION_RECOMMENDATION] 仅Scenario5优先评估Option A；需要Stage04完整强证据和可控篇幅。"),
("26. 两篇拆分方案","[PUBLICATION_RECOMMENDATION] 默认以Paper1承载Stage00–03资格方法，Paper2仅承载Stage04新训练/性能；执行overlap matrix与anti-salami规则。"),
("27. Stage04后决策树","[PROJECT_EVIDENCE] 六场景以task-aligned gradient、training、rollout、validation/refinement和一般性逐级分叉；Stage04 delta不改写历史。"),
("28. 最终研究边界","[PROJECT_EVIDENCE] 已支持实现、结构、zero-correction、reference与topology组成分量；不支持Stage01 V2恢复、static fit资格、多步梯度资格、dynamic training、rollout、solver improvement、Transformer superiority或cost utility。"),
("29. artifact/hash index",f"[PROJECT_EVIDENCE] 冻结输入{freeze['selection']['included_file_count']}项、{freeze['selection']['included_total_bytes']} bytes；Git HEAD `{freeze['git']['head']}`。完整路径/哈希/大小/mtime/角色/manifest membership见`00_freeze/project_wide_input_freeze_manifest.json`与`01_artifact_inventory/complete_artifact_inventory.json`。"),
]
syn="# SPH-PIO-PoC 全项目研究综合\n\n**工作流：Cross-Stage Synthesis S1**  \n**性质：只读、非计算性证据审计**  \n**扫描截止：2026-08-05**\n\n## 执行摘要\n\n[PROJECT_EVIDENCE] 项目形成了从环境、SPH V&V、reference/target/data、保守架构、动态实现到多步梯度和拓扑事件的完整证据链。它没有形成动态训练或rollout成功证据。最稳健的现时发表主线是verification-first方法与负结果；Stage04以后再按决策树选择合并或拆分。\n\n"+"\n\n".join(f"## {h}\n\n{b}" for h,b in sections)
syn += "\n\n## 附录A：全阶段状态摘要\n\n"+md_table(["阶段","exact status","边界"],[(r['stage_id'],r['exact_final_status'],r['claim_boundary']) for r in timeline])
syn += "\n\n## 附录B：核心失败摘要\n\n"+md_table(["ID","阶段","状态","教训"],[(f['id'],f['stage'],f['exact_status'],f['lesson']) for f in failures])
write_md("12_reports/project_wide_research_synthesis.md",syn)

dossier="# 全项目发表决策案卷\n\n## 当前证据判定\n\n[PROJECT_EVIDENCE] Stage00–03可以支撑verification-first方法/负结果论文；不能支撑训练、rollout、solver improvement或Transformer superiority论文。\n\n## 推荐顺序\n\n1. [PUBLICATION_RECOMMENDATION] 现在优先准备Option C/Paper1主线。\n2. Stage04完成后只导入delta并匹配六场景。\n3. 仅当Scenario5证据完整时优先评估单篇CMAME整合；否则保持两篇或verification-only。\n\n## 决策护栏\n\n- Stage01 V2失败、Stage02 static route termination、Stage03 multistep gradient NOT_QUALIFIED必须在摘要/正文可见。\n- topology component PASS不得覆盖overall gradient failure。\n- 所有外部新颖性措辞服从P2；其余标记LITERATURE_VERIFICATION_REQUIRED。\n- overlap matrix是拆稿前置硬门。\n\n## 选项矩阵\n\n"+md_table(["Option","触发条件","价值","风险","建议"],[(x['option'],x['when'],x['strength'],x['risk'],x['recommendation']) for x in option_matrix['options']])
write_md("12_reports/project_wide_publication_decision_dossier.md",dossier)

print(json.dumps({"timeline_rows":len(timeline),"artifacts":len(artifacts),"failures":len(failures),"innovations":len(innov),"claims":len(claim_data)},ensure_ascii=False))
