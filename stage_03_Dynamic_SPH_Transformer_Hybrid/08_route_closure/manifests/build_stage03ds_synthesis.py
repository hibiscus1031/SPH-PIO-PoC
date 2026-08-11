#!/usr/bin/env python3
"""Build Stage 03D-S ledgers, boundaries, publication assessment, and reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stage_03_Dynamic_SPH_Transformer_Hybrid"
ROOT = STAGE / "08_route_closure"
REPORTS = STAGE / "09_reports"
MANIFESTS = STAGE / "10_manifests"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_md(name: str, text: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / name).write_text(text.rstrip() + "\n")


for name in (
    "freeze", "status_ledger", "evidence_matrix", "gradient_boundary",
    "topology_boundary", "claim_boundary", "manuscript_assessment",
    "figure_plan", "future_hypotheses", "manifests",
):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

freeze_path = MANIFESTS / "stage03ds_input_freeze_manifest.json"
freeze = json.loads(freeze_path.read_text())
if freeze["status"] != "PASS":
    raise RuntimeError("Stage 03D-S input freeze is not PASS")

final_manifests = {
    stage: STAGE / f"10_manifests/stage03{suffix}_final_manifest.json"
    for stage, suffix in [("Stage 03A", "a"), ("Stage 03B", "b"), ("Stage 03C", "c"), ("Stage 03D", "d"), ("Stage 03D-R", "dr")]
}

ledger_specs = [
    {
        "stage": "Stage 03A",
        "status": "DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE",
        "purpose": "冻结动态控制方程、D0-D3 因果架构、RK2/history/graph 语义、reference hierarchy 与 V&V 路线。",
        "execution_count": 0,
        "execution_kind": "specification_only",
        "principal_pass_evidence": "45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。",
        "principal_blocker": "尚无动态实现、trajectory payload 或计算资格化。",
        "downstream_authorization": "Stage 03B only；implementation/training/rollout 均未授权。",
        "optimizer_steps": 0,
        "training_runs": 0,
        "performance_evaluations": 0,
        "interpretation_boundary": "规格完整不等于实现、可训练性或性能成立。",
    },
    {
        "stage": "Stage 03B",
        "status": "DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE",
        "purpose": "资格化 D-R1/D-R2/D-R3 动态参考、轨迹、边界分类和 provenance。",
        "execution_count": 1,
        "execution_kind": "reference_qualification_campaign",
        "principal_pass_evidence": "D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。",
        "principal_blocker": "acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。",
        "downstream_authorization": "Stage 03C implementation only；training/neural rollout 未授权。",
        "optimizer_steps": 0,
        "training_runs": 0,
        "performance_evaluations": 0,
        "interpretation_boundary": "参考资格化不等于模型、数据集或动态性能资格化。",
    },
    {
        "stage": "Stage 03C",
        "status": "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "purpose": "实现并验证独立 RK2、D0-D3 接口、history/graph、zero correction、结构性质、checkpoint 与 one-step autograd。",
        "execution_count": 1,
        "execution_kind": "implementation_qualification_campaign",
        "principal_pass_evidence": "D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。",
        "principal_blocker": "未执行 multistep AD/FD、训练或 rollout 性能评价。",
        "downstream_authorization": "Stage 03D multistep AD/FD + preregistered topology family only；training=false。",
        "optimizer_steps": 0,
        "training_runs": 0,
        "performance_evaluations": 0,
        "interpretation_boundary": "implementation verified 与 one-step plumbing verified 不证明完整多步梯度资格。",
    },
    {
        "stage": "Stage 03D",
        "status": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "purpose": "执行冻结的 360-probe 多步 AD/FD 合同，并独立资格化 TE1 拓扑事件分量。",
        "execution_count": 1,
        "execution_kind": "formal_multistep_gradient_and_topology_campaign",
        "principal_pass_evidence": "216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。",
        "principal_blocker": "144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。",
        "downstream_authorization": "Stage 03E authorization NONE；仅允许 Stage 03D-R 失败归因。",
        "optimizer_steps": 0,
        "training_runs": 0,
        "performance_evaluations": 0,
        "interpretation_boundary": "总体 NOT_QUALIFIED；topology component PASS 不得写成 Stage 03D 总体 PASS。",
    },
    {
        "stage": "Stage 03D-R",
        "status": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
        "purpose": "在不改合同的前提下归因 Stage 03D 的 144 个失败，并作动态路线决策。",
        "execution_count": 1,
        "execution_kind": "forensic_attribution_campaign",
        "principal_pass_evidence": "reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。",
        "principal_blocker": "19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。",
        "downstream_authorization": "NONE；Stage 03E=false；不得立即改合同或训练。",
        "optimizer_steps": 0,
        "training_runs": 0,
        "performance_evaluations": 0,
        "interpretation_boundary": "D-R 是归因诊断，不覆盖、不修复 Stage 03D 的 NOT_QUALIFIED。",
    },
]

ledger_rows = []
for order, spec in enumerate(ledger_specs, 1):
    artifact = final_manifests[spec["stage"]]
    ledger_rows.append({
        "order": order,
        **spec,
        "superseded": False,
        "artifact": str(artifact.relative_to(REPO)),
        "artifact_sha256": digest(artifact),
    })

ledger = {
    "schema_version": "sph-pio-poc.stage03ds.status-ledger.v1",
    "chronology": [row["stage"] for row in ledger_rows],
    "rows": ledger_rows,
    "non_override_rule": "Stage 03D-R does not override or repair the Stage 03D failure verdict.",
    "stage03e_authorization": False,
    "status": "PASS",
}
write_json(ROOT / "status_ledger/stage03ds_status_ledger.json", ledger)
write_json(MANIFESTS / "stage03ds_status_ledger.json", ledger)

def ev(eid: str, category: str, item: str, status: str, evidence: str, boundary: str, artifact: str) -> dict:
    return {"id": eid, "category": category, "item": item, "status": status, "evidence": evidence, "boundary": boundary, "artifact": artifact}


evidence_rows = [
    ev("A01", "A_SPECIFICATION", "governing equations", "PASS", "dx/dt, dρ/dt and dv/dt with additive conservative correction frozen.", "合同证据；无性能含义。", "01_governing_contract/hybrid_equations.md"),
    ev("A02", "A_SPECIFICATION", "causal Transformer contract", "PASS", "D3 H=4 causal scalar-history Transformer with reciprocal pair head frozen.", "候选架构，不证明必要或优越。", "02_temporal_architecture/temporal_transformer_contract.md"),
    ev("A03", "A_SPECIFICATION", "D0-D3 arm matrix", "PASS", "D0 baseline, D1 instantaneous MLP, D2 recurrent, D3 temporal Transformer roles frozen.", "未训练、未比较性能。", "02_temporal_architecture/baseline_arm_contract.md"),
    ev("A04", "A_SPECIFICATION", "RK2/history/graph semantics", "PASS", "Start/midpoint graph rebuild and one accepted-state history commit specified.", "语义合同与实现证据分层。", "03_time_integration/rk2_stage_semantics.md"),
    ev("A05", "A_SPECIFICATION", "reference hierarchy", "PASS", "D-R1 through D-R4 roles and disallowed uses frozen.", "D-R4 remains NOT_AVAILABLE.", "04_reference_and_trajectory/dynamic_reference_hierarchy.md"),
    ev("B01", "B_REFERENCE", "D-R1 analytic/MMS closure", "PASS", "Two D-R1 families passed analytic closure and produced six exact trajectories.", "MMS verifies equations/code, not physical validation.", "09_reports/stage03b_dr1_lagrangian_mms.md"),
    ev("B02", "B_REFERENCE", "D-R2 time-reference sensitivity", "PASS", "Six same-semidiscrete DOP853 cases passed.", "Isolates time error; not spatial truth.", "09_reports/stage03b_dr2_semidiscrete_reference.md"),
    ev("B03", "B_REFERENCE", "D-R3 source-free exact reference", "PASS", "Two oblique-shear families passed and yielded six exact trajectories.", "Independent validation only; forbidden for training/threshold selection.", "09_reports/stage03b_dr3_source_free_reference.md"),
    ev("B04", "B_REFERENCE", "acoustic boundary", "DIAGNOSTIC", "Classified DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL.", "Not an unrestricted exact D-R3 family.", "09_reports/stage03b_acoustic_and_vortex_boundary.md"),
    ev("B05", "B_REFERENCE", "periodic vortex boundary", "NOT_QUALIFIED", "Rejected as exact source-free reference due to momentum/EOS mismatch.", "May only support a separately sourced MMS role.", "09_reports/stage03b_acoustic_and_vortex_boundary.md"),
    ev("C01", "C_IMPLEMENTATION", "independent RK2", "PASS", "Independent RK2 comparison 48/48.", "Implementation verification only.", "05_dynamic_solver_implementation/stage03c/results/independent_rk2_results.json"),
    ev("C02", "C_IMPLEMENTATION", "zero correction", "PASS", "288/288 bitwise equivalence; no post-hoc tolerance.", "Does not prove nonzero correction accuracy.", "05_dynamic_solver_implementation/stage03c/results/zero_correction_results.json"),
    ev("C03", "C_IMPLEMENTATION", "conservation/equivariance", "PASS", "Reciprocal antisymmetry, conservation, O(2), permutation and periodic checks passed.", "Structural property, not learned performance.", "05_dynamic_solver_implementation/stage03c/results/structural_smoke_results.json"),
    ev("C04", "C_IMPLEMENTATION", "checkpoint/resume", "PASS", "Six configurations reproduced state, graph, history and RNG identity.", "No trained checkpoint exists.", "05_dynamic_solver_implementation/stage03c/results/checkpoint_resume_results.json"),
    ev("C05", "C_IMPLEMENTATION", "one-step autograd", "PASS", "6/6 one-step runs returned finite nonzero expected gradients.", "No finite difference and no multistep qualification in Stage 03C.", "05_dynamic_solver_implementation/stage03c/results/differentiability_smoke_results.json"),
    ev("C06", "C_IMPLEMENTATION", "resources", "PASS", "CPU float64 resource audit passed.", "Resource record is not a speed or cost comparison.", "05_dynamic_solver_implementation/stage03c/results/resource_audit_results.json"),
    ev("D01", "D_MULTISTEP_GRADIENT", "360 frozen probes", "NOT_QUALIFIED", "216 PASS and 144 failure rows; 2880 AD/FD comparisons.", "Complete gradient qualification failed.", "05_dynamic_solver_implementation/stage03dr/failure_matrix/stage03d_complete_360_row_matrix.json"),
    ev("D02", "D_MULTISTEP_GRADIENT", "stable epsilon windows", "DIAGNOSTIC", "216/360 probes had a stable adjacent window.", "Cannot report only the passing subset.", "05_dynamic_solver_implementation/stage03d/results/fixed_topology_adfd_results.json"),
    ev("D03", "D_MULTISTEP_GRADIENT", "reverse/JVP crosscheck", "PASS", "60/60 same-math-backend reverse/JVP comparisons passed.", "Supports AD implementation consistency, not complete AD/FD validity.", "05_dynamic_solver_implementation/stage03dr/ad_crosscheck/reverse_vs_jvp.json"),
    ev("D04", "D_MULTISTEP_GRADIENT", "extended finite difference", "DIAGNOSTIC", "2640 FD paths; 30/60 selected paths stable.", "Conditioning contribution remains path dependent.", "05_dynamic_solver_implementation/stage03dr/fd_conditioning/extended_fd_results.json"),
    ev("D05", "D_MULTISTEP_GRADIENT", "history influence", "UNRESOLVED", "1 HISTORY_FD_CONDITIONING_LIMITED and 5 HISTORY_SENSITIVITY_BELOW_FD_RESOLUTION.", "Strong rollout attenuation is observed; long-chain trainability is not established.", "05_dynamic_solver_implementation/stage03dr/history_path/reference_prehistory_trace.json"),
    ev("D06", "D_MULTISTEP_GRADIENT", "backend sensitivity", "DIAGNOSTIC", "Historical default backend disagreed with math JVP on 12/60, all in D3 selected probes.", "Conditional diagnostic; no backend switch or requalification authorized.", "09_reports/stage03dr_ad_crosscheck.md"),
    ev("D07", "D_MULTISTEP_GRADIENT", "failure attribution", "UNRESOLVED", "144 failures split across seven reasons, including 19 unresolved.", "Mixed contributors; no single complete root cause.", "05_dynamic_solver_implementation/stage03dr/attribution/failure_attribution.json"),
    ev("D08", "D_MULTISTEP_GRADIENT", "horizon scaling", "DIAGNOSTIC", "90/90 traces classified bounded or nonmonotone.", "No systematic vanishing/exploding detected, not proof of healthy training gradients.", "05_dynamic_solver_implementation/stage03dr/horizon_scaling/horizon_gradient_scaling.json"),
    ev("D09", "D_MULTISTEP_GRADIENT", "dynamic training", "NOT_EXECUTED", "optimizer steps=0; training runs=0; performance evaluations=0.", "Must not be called training failure.", "10_manifests/stage03dr_final_manifest.json"),
    ev("E01", "E_TOPOLOGY", "TE1 birth/death", "PASS", "One deterministic edge birth and one death recorded.", "Discrete edge existence is not differentiable.", "05_dynamic_solver_implementation/stage03d/topology_event_scan/te1_dense_scan_results.json"),
    ev("E02", "E_TOPOLOGY", "replay", "PASS", "6/6 topology-stage replays passed.", "Qualification is for TE1 semantics.", "05_dynamic_solver_implementation/stage03d/topology_stage_replay/replay_results.json"),
    ev("E03", "E_TOPOLOGY", "event-side gradients", "PASS", "12/12 fixed-side gradients passed.", "Gradients are within a fixed event side, not through cutoff membership.", "05_dynamic_solver_implementation/stage03d/event_side_gradients/event_side_gradient_results.json"),
    ev("E04", "E_TOPOLOGY", "piecewise-smooth boundary", "PASS", "Finite bounded force jumps and deterministic empty-graph behavior established.", "Topology map remains piecewise smooth with discrete events.", "05_dynamic_solver_implementation/stage03dr/topology_preservation/topology_component_status.json"),
]

matrix = {
    "schema_version": "sph-pio-poc.stage03ds.evidence-matrix.v1",
    "allowed_statuses": ["PASS", "DIAGNOSTIC", "NOT_QUALIFIED", "NOT_EXECUTED", "UNRESOLVED"],
    "rows": evidence_rows,
    "status_counts": {status: sum(r["status"] == status for r in evidence_rows) for status in ["PASS", "DIAGNOSTIC", "NOT_QUALIFIED", "NOT_EXECUTED", "UNRESOLVED"]},
    "overall_gradient_status": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
    "topology_component_status": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
    "stage03e_authorization": False,
}
write_json(ROOT / "evidence_matrix/stage03ds_dynamic_evidence_matrix.json", matrix)
write_json(MANIFESTS / "stage03ds_evidence_matrix.json", matrix)

gradient = {
    "schema_version": "sph-pio-poc.stage03ds.gradient-boundary.v1",
    "implementation_verified": True,
    "one_step_autograd_verified": True,
    "partial_multistep_evidence": True,
    "complete_multistep_gradient_qualification": False,
    "stage03d_status_preserved": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
    "stage03dr_status": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
    "stage03dr_overrides_stage03d": False,
    "counts": {"probes": 360, "pass": 216, "fail": 144, "comparisons": 2880, "history_pass": 0, "history_required": 6},
    "failure_reason_counts": {
        "AD_FD_DIRECTION_OR_SIGN_MISMATCH": 5,
        "DERIVATIVE_NEAR_STRUCTURAL_ZERO": 29,
        "FD_NONMONOTONE_NO_ADJACENT_WINDOW": 69,
        "FD_ROUNDOFF_DOMINATED": 3,
        "FD_TRUNCATION_DOMINATED": 3,
        "NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH": 16,
        "UNRESOLVED": 19,
    },
    "backend_crosscheck": {"same_math_reverse_jvp": "60/60_PASS", "historical_backend_vs_math_jvp": "48/60_MATCH", "interpretation": "D3 backend sensitivity diagnostic"},
    "history": {"conditioning_limited": 1, "below_fd_resolution": 5, "rollout_attenuation_ratio_range": [0.000154, 0.00491]},
    "horizon_scaling": {"bounded_or_nonmonotone": 90, "systematic_vanishing_or_exploding_detected": False},
    "training_authorized": False,
    "performance_tested": False,
}
write_json(ROOT / "gradient_boundary/stage03ds_gradient_boundary.json", gradient)

topology = {
    "schema_version": "sph-pio-poc.stage03ds.topology-boundary.v1",
    "component_status": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
    "gates": {"birth": "1/1_PASS", "death": "1/1_PASS", "replay": "6/6_PASS", "fixed_side_gradients": "12/12_PASS", "finite_force_jumps": True, "empty_graph_semantics": True},
    "allowed_claim": "deterministic edge birth/death and fixed-side piecewise-smooth gradient semantics are qualified for TE1",
    "prohibited_claims": ["cutoff edge existence is differentiable", "topology PASS makes Stage 03D overall PASS", "arbitrary topology-event families are qualified"],
}
write_json(ROOT / "topology_boundary/stage03ds_topology_component_boundary.json", topology)

supported = [
    ("dynamic RK2 hybrid solver implementation is verified", "动态 RK2 hybrid solver 的冻结实现合同已通过 Stage 03C。", "dynamic solver performance is verified"),
    ("zero-correction equivalence is bitwise established", "zero correction 在 288/288 检查中与 D0 bitwise 等价。", "nonzero learned correction is accurate"),
    ("reciprocal pair-force conservation persists through multiple stages", "冻结多步审计的 540/540 stage conservation checks 通过。", "long-time conservation and stability are proven"),
    ("deterministic edge birth/death semantics are qualified", "TE1 的 birth/death、replay 和 fixed-side gradients 已资格化。", "cutoff membership is differentiable"),
    ("gradients are valid on many fixed-topology paths", "360 个冻结 probes 中 216 个获得 stable AD/FD window。", "all multistep gradients are valid"),
    ("complete multistep gradient qualification was not achieved", "Stage 03D 保持 NOT_QUALIFIED，D-R 保持 MIXED_OR_UNRESOLVED。", "Stage 03D-R repaired the Stage 03D failure"),
]
conditional = [
    ("D3 gradients show backend sensitivity", "在冻结的 selected diagnostics 内，D3 的部分梯度显示 backend sensitivity。", "D3 is intrinsically non-differentiable"),
    ("temporal-history influence is strongly attenuated through rollout", "当前 reference-prehistory paths 显示 rollout 中 history influence 强烈衰减。", "temporal memory is useless"),
    ("finite-difference conditioning contributes to some failures", "extended FD 支持 conditioning 对部分 failure 的贡献。", "all failures are finite-difference artifacts"),
    ("no systematic vanishing/exploding gradient was detected", "冻结 horizon diagnostics 未检测到系统性 vanish/explode。", "gradient health is proven for training"),
]
unsupported = [
    ("dynamic Transformer is trainable", "动态训练尚未授权或执行。", "the dynamic Transformer is trainable"),
    ("solver-in-the-loop training is valid", "solver-in-the-loop 为 NOT AUTHORIZED / NOT EXECUTED。", "solver-in-the-loop training is valid"),
    ("rollout improves SPH", "未进行 rollout 性能评价。", "rollout improves SPH"),
    ("Transformer outperforms recurrent/instantaneous baselines", "D1/D2/D3 未训练、未比较。", "Transformer outperforms D1/D2"),
    ("cutoff edge existence is differentiable", "只能主张 event 两侧的 piecewise-smooth gradients。", "edge membership is differentiable"),
    ("Stage 01 V2 is restored", "Stage 01 仍为 V2_QUALIFICATION_FAIL。", "Stage 03 restores Stage 01 V2"),
    ("viscosity operator is confirmed", "viscosity operator form 仍为 NOT_CONFIRMED。", "viscosity operator is confirmed"),
    ("long-time stability is established", "未执行 long-time rollout/stability qualification。", "long-time stability is established"),
]

def claim_rows(items: list[tuple[str, str, str]]) -> list[dict]:
    return [{"claim": c, "allowed_wording": a, "prohibited_wording": p} for c, a, p in items]


claims = {
    "schema_version": "sph-pio-poc.stage03ds.claim-boundary.v1",
    "supported_claims": claim_rows(supported),
    "conditional_claims": claim_rows(conditional),
    "unsupported_claims": claim_rows(unsupported),
    "semantic_guards": {
        "training": "NOT AUTHORIZED / NOT EXECUTED; never training failed",
        "solver": "Stage 03D NOT_QUALIFIED; never whole Transformer solver failed",
        "topology": "component qualified; never Stage 03D overall qualified",
    },
}
write_json(ROOT / "claim_boundary/stage03ds_claim_boundary.json", claims)

assessment = {
    "schema_version": "sph-pio-poc.stage03ds.manuscript-readiness.v1",
    "working_title": "Verification-first development of a conservative dynamic neural-SPH solver: zero-correction equivalence, topology events, and limits of multistep gradient qualification",
    "recommended_direction": "Paper B with a tightly scoped Paper C diagnostic contribution",
    "paper_complete_now": False,
    "current_cmame_readiness": "NOT_READY_FOR_FULL_SOLVER_CLAIM; CONDITIONALLY_PLAUSIBLE_AFTER_METHOD_DEPTH_AND_INDEPENDENT_VALIDATION",
    "cmame_scope_source": "https://www.sciencedirect.com/journal/computer-methods-in-applied-mechanics-and-engineering",
    "cmame_scope_checked_on": "2026-08-05",
    "papers": [
        {"paper": "A", "direction": "完整动态 SPH-Transformer hybrid solver", "readiness": "NOT_READY", "assessment": "缺少训练、rollout 与独立性能验证；不能形成完整 solver-performance 论文。", "journal_fit": "当前不适合以完整求解器主张投稿 CMAME。"},
        {"paper": "B", "direction": "verification-first conservative dynamic neural-SPH coupling", "readiness": "MOST_DEFENSIBLE_BUT_INCOMPLETE", "assessment": "创新点可放在 verification-first 分层、bitwise zero correction、结构守恒、TE1 事件边界和透明负梯度证据；必须把 multistep limitation 置于主文。", "journal_fit": "主题与 CMAME 的 meshless、fluid mechanics、physically based ML 范围相符，但当前需增强方法普适性与独立验证后才更有竞争力。"},
        {"paper": "C", "direction": "limits of multistep differentiability verification in dynamic graph particle solvers", "readiness": "POTENTIAL_METHODS_NOTE", "assessment": "可围绕 backend sensitivity、FD conditioning、history attenuation、piecewise topology 与 negative-result value；需证明诊断框架超出单个 PoC。", "journal_fit": "若形成通用、可复现实验方法并覆盖多实现/问题族，才可能与高水平计算方法期刊匹配。"},
    ],
    "missing_core_evidence": ["冻结训练协议下的正式动态训练资格", "受控与自主 rollout 的独立性能/稳定性证据", "新且独立的 D-R4 或等价外部验证与跨问题泛化证据"],
    "main_text_results": ["V&V pipeline and contracts", "D0-D3 architecture and RK2/history/graph semantics", "Stage 03B reference qualification", "Stage 03C zero/structural/checkpoint/one-step evidence", "complete 360-probe outcomes including 144 failures", "TE1 topology component boundary", "D-R mixed/unresolved attribution", "claim boundary"],
    "supplementary_audits": ["complete hash ledger", "360-row matrix", "extended FD paths", "reverse/JVP tables", "history traces", "horizon scaling", "topology replay and event-side rows", "resource audits"],
    "internal_only": ["machine-specific RSS/timing except reproducibility context", "individual debug traces without preregistered interpretive role", "any unqualified post-hoc backend comparison beyond the frozen diagnostic"],
}
write_json(ROOT / "manuscript_assessment/stage03ds_manuscript_readiness.json", assessment)

figures = [
    (1, "Stage 03 V&V pipeline", "workflow", "Show A-D-R chronology and independent topology branch."),
    (2, "D0-D3 dynamic architecture", "architecture schematic", "No superiority encoding."),
    (3, "RK2 graph rebuild and history commit", "state-transition schematic", "Show start/midpoint rebuilds and one accepted commit."),
    (4, "D-R1/D-R2/D-R3 reference hierarchy", "evidence hierarchy", "Keep role and disallowed-use labels."),
    (5, "Zero-correction and structural qualification matrix", "status matrix", "Separate bitwise/structural from performance."),
    (6, "360-probe multistep AD/FD outcome matrix", "complete matrix", "Show all 216 PASS and 144 failures."),
    (7, "History-gradient attenuation and backend sensitivity", "diagnostic panels", "Use conditional language; no trainability claim."),
    (8, "TE1 birth/death and piecewise-smooth boundary", "event schematic", "Do not depict edge existence as differentiable."),
    (9, "Supported versus unsupported claim map", "claim map", "Include training/rollout NOT EXECUTED."),
]
tables = [
    "Stage 03 status ledger", "trajectory inventory", "implementation gates", "AD/FD failure taxonomy", "topology-event results", "final evidence matrix",
]
figure_plan = {
    "schema_version": "sph-pio-poc.stage03ds.figure-plan.v1",
    "figures": [{"figure": n, "title": t, "form": f, "integrity_rule": rule} for n, t, f, rule in figures],
    "tables": [{"table": i + 1, "title": title} for i, title in enumerate(tables)],
    "prohibitions": ["show only the 216 passing probes", "hide the 144 failures", "equate topology component PASS with Stage 03D overall PASS", "invent training or performance plots"],
}
write_json(ROOT / "figure_plan/stage03ds_figure_and_table_plan.json", figure_plan)

future = {
    "schema_version": "sph-pio-poc.stage03ds.future-hypotheses.v1",
    "execution_in_stage03ds": False,
    "stage03e_continuation": False,
    "hypotheses": [
        {"id": 1, "hypothesis": "不依赖长链 reverse-mode 的局部 one-step/短窗目标可获得可资格化训练信号。", "required_stage": "new Stage 04", "executed": False},
        {"id": 2, "hypothesis": "显式可微邻域近似或连续邻接权重可重定义拓扑可微边界。", "required_stage": "new Stage 04 with a new topology contract", "executed": False},
        {"id": 3, "hypothesis": "离散伴随、自定义 JVP 或统一 math-attention backend 可改善多步梯度资格。", "required_stage": "new Stage 04 with new implementation and AD/FD contracts", "executed": False},
        {"id": 4, "hypothesis": "非学习或解析型动态保守修正可在不依赖端到端训练时建立动态证据。", "required_stage": "new Stage 04", "executed": False},
    ],
}
write_json(ROOT / "future_hypotheses/stage03ds_future_hypotheses.json", future)

write_json(ROOT / "freeze/stage03ds_freeze_reference.json", {
    "canonical_manifest": str(freeze_path.relative_to(REPO)),
    "canonical_manifest_sha256": digest(freeze_path),
    "historical_file_count": freeze["historical_file_count"],
    "status": freeze["status"],
})
write_json(ROOT / "manifests/stage03ds_scope_contract.json", freeze["scope_contract"])

status_lines = "\n".join(
    f"| {r['stage']} | `{r['status']}` | {r['execution_count']} ({r['execution_kind']}) | {r['principal_pass_evidence']} | {r['principal_blocker']} | {r['downstream_authorization']} | {r['optimizer_steps']} / {r['training_runs']} / {r['performance_evaluations']} |"
    for r in ledger_rows
)
write_md("stage03ds_freeze_and_scope.md", f"""# Stage 03D-S — Freeze and scope

- Phase type: noncomputational route closure.
- Frozen historical files: **{freeze['historical_file_count']}**, all read-only inputs.
- Freeze status: **PASS**.
- Preserved Stage 03C: `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED`.
- Preserved Stage 03D: `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`.
- Preserved Stage 03D-R: `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`.
- Preserved topology component: `TOPOLOGY_EVENT_COMPONENT_QUALIFIED`.
- Stage 03E authorization: **false**.
- New AD/FD contracts, epsilons, probes, backends, architectures, datasets and training protocols: **0**.
- Optimizer steps, training runs, rollout and performance evaluations: **0**.

Stage 03D-S synthesizes frozen evidence only. It does not alter any historical verdict or artifact.
""")

write_md("stage03ds_status_ledger.md", f"""# Stage 03D-S — Complete status ledger

| Stage | Unique status | Execution count | Principal PASS evidence | Principal blocker | Downstream authorization | Steps / runs / performance |
|---|---|---:|---|---|---|---:|
{status_lines}

## Non-override rule

Stage 03D-R is a diagnostic attribution stage. It does **not** override, repair, supersede or convert the Stage 03D failure verdict. All five rows have `superseded=false`.
""")

matrix_lines = "\n".join(f"| {r['id']} | {r['category']} | {r['item']} | **{r['status']}** | {r['evidence']} | {r['boundary']} |" for r in evidence_rows)
write_md("stage03ds_dynamic_evidence_matrix.md", f"""# Stage 03D-S — Dynamic evidence matrix

| ID | Category | Item | Status | Frozen evidence | Interpretation boundary |
|---|---|---|---|---|---|
{matrix_lines}

The matrix deliberately keeps `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED` and `TOPOLOGY_EVENT_COMPONENT_QUALIFIED` as different levels of verdict.
""")

reason_lines = "\n".join(f"| `{k}` | {v} |" for k, v in gradient["failure_reason_counts"].items())
write_md("stage03ds_gradient_failure_boundary.md", f"""# Stage 03D-S — Gradient failure boundary

## Layered verdict

1. Implementation: **verified** (Stage 03C).
2. One-step autograd plumbing: **verified**, 6/6.
3. Multistep evidence: **partial**, 216/360 probes with stable windows.
4. Complete multistep gradient qualification: **failed**, 144/360 failures and history gate 0/6.
5. Failure attribution: **mixed or unresolved**, not a verdict replacement.
6. Dynamic training: **not authorized / not executed**.
7. Rollout performance: **not tested**.

| Primary failure reason | Count |
|---|---:|
{reason_lines}

Same-math reverse/JVP passed 60/60. Extended FD produced 30/60 stable selected paths across 2640 evaluations. History traces separated stable temporal-module paths from rollout attenuation: one path was FD-conditioning-limited and five fell below FD resolution. All 90 horizon diagnostics were bounded or nonmonotone, so systematic vanishing/exploding was not detected; this does not qualify trainability.
""")

write_md("stage03ds_topology_component_boundary.md", """# Stage 03D-S — Topology component boundary

`TOPOLOGY_EVENT_COMPONENT_QUALIFIED` is preserved independently from the Stage 03D overall verdict.

- TE1: one edge birth and one edge death.
- Replay: 6/6 PASS.
- Fixed-side event gradients: 12/12 PASS.
- Force jumps: finite and bounded under the frozen audit.
- Empty graph: deterministic semantics qualified.
- Differentiability: piecewise smooth on each fixed-topology side; cutoff edge membership itself is discrete and is **not** claimed differentiable.

This component result does not turn Stage 03D into an overall PASS and does not generalize automatically to arbitrary topology-event families.
""")

def claim_section(title: str, rows: list[dict]) -> str:
    lines = "\n".join(f"| {r['claim']} | {r['allowed_wording']} | {r['prohibited_wording']} |" for r in rows)
    return f"## {title}\n\n| Claim | Allowed wording | Prohibited wording |\n|---|---|---|\n{lines}"

write_md("stage03ds_claim_boundary.md", "# Stage 03D-S — Claim boundary\n\n" + "\n\n".join([
    claim_section("SUPPORTED CLAIMS", claims["supported_claims"]),
    claim_section("CONDITIONAL CLAIMS", claims["conditional_claims"]),
    claim_section("UNSUPPORTED CLAIMS", claims["unsupported_claims"]),
]) + "\n\nUnexecuted dynamic training must never be described as failed training. Stage 03D NOT_QUALIFIED must never be described as failure of the entire Transformer solver.\n")

paper_lines = "\n".join(f"| Paper {r['paper']} | {r['direction']} | {r['readiness']} | {r['assessment']} | {r['journal_fit']} |" for r in assessment["papers"])
write_md("stage03ds_manuscript_readiness.md", f"""# Stage 03D-S — Manuscript readiness

| Direction | Focus | Readiness | Evidence assessment | Journal fit |
|---|---|---|---|---|
{paper_lines}

## Direct answers

1. A complete full-solver paper cannot yet be formed because training, rollout and independent performance evidence are absent.
2. The defensible route is a verification/methods paper (Paper B), potentially with Paper C's differentiability-limit diagnostics.
3. CMAME currently covers meshless methods, fluid mechanics and physically based machine learning, so the topic is in scope; the present evidence package is not yet ready for a full-solver CMAME claim and would need broader method depth and independent validation.
4. The three core missing evidence classes are: formal dynamic training qualification; controlled/autonomous rollout performance and stability; independent D-R4-equivalent validation and cross-problem generality.
5. Main text should retain the complete verification chain, all 360 outcomes including 144 failures, topology boundary and explicit claim map.
6. Supplementary material should contain full matrices, extended FD, reverse/JVP, history/horizon traces, topology replay and hash/resource audits.
7. Machine-specific debug traces and unqualified post-hoc comparisons remain internal only.

Official scope source checked 2026-08-05: {assessment['cmame_scope_source']}
""")

write_md("stage03ds_manuscript_framework.md", f"""# Stage 03D-S — Recommended manuscript framework

## Working title

{assessment['working_title']}

## Recommended argument

The paper should not begin from “Transformer improves SPH.” It should present a verification-first route in which conservative architecture, zero-correction identity, RK2/history/graph semantics and topology events can be positively qualified, while complete multistep gradient qualification remains falsified under the frozen contract.

## Main-text sequence

1. Problem and verification-first hypothesis.
2. Conservative dynamic neural-SPH formulation and D0-D3 controls.
3. Dynamic reference hierarchy and qualified trajectories.
4. Independent implementation verification and bitwise zero correction.
5. Structural conservation/equivariance, checkpoint and one-step AD.
6. Complete 360-probe multistep AD/FD results, including all failures.
7. TE1 topology-event qualification as an independent component.
8. D-R attribution: backend sensitivity, FD conditioning, history attenuation and unresolved cases.
9. Claim boundary, limitations and future hypotheses.

## Publication boundary

Paper A is not ready. Paper B is the strongest current framing but remains incomplete for a high-impact full computational-method claim. Paper C can become valuable if the diagnostic methodology is shown to generalize beyond this single PoC. Stage 03D NOT_QUALIFIED must remain visible in the abstract, results and discussion.
""")

fig_lines = "\n".join(f"| Figure {r['figure']} | {r['title']} | {r['form']} | {r['integrity_rule']} |" for r in figure_plan["figures"])
table_lines = "\n".join(f"| Table {r['table']} | {r['title']} |" for r in figure_plan["tables"])
write_md("stage03ds_figure_and_table_plan.md", f"""# Stage 03D-S — Figure and table plan

| Figure | Title | Form | Integrity rule |
|---|---|---|---|
{fig_lines}

| Table | Title |
|---|---|
{table_lines}

Figures must not show only the 216 PASS probes, hide 144 failures, convert topology component PASS into Stage 03D PASS, or invent training/performance evidence.
""")

hyp_lines = "\n".join(f"| H{r['id']} | {r['hypothesis']} | {r['required_stage']} | {r['executed']} |" for r in future["hypotheses"])
write_md("stage03ds_future_hypotheses.md", f"""# Stage 03D-S — Future hypotheses (design only)

| ID | New hypothesis | Required route | Executed in Stage 03D-S |
|---|---|---|---|
{hyp_lines}

No branch is a direct Stage 03E continuation. Each requires a new Stage 04 hypothesis and a new contract before any computation.
""")

write_md("stage03ds_final_report.md", f"""# Stage 03D-S — Final report

1. Stage 03D failure is preserved: `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`.
2. Stage 03D-R attribution is preserved: `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`; it does not override Stage 03D.
3. Topology component is preserved: `TOPOLOGY_EVENT_COMPONENT_QUALIFIED`.
4. The chronological Stage 03A/B/C/D/D-R ledger contains five unique, non-superseded states.
5. Dynamic reference evidence includes qualified D-R1, D-R2 and oblique-shear D-R3; acoustic is conditional, periodic vortex is not qualified as exact source-free, and D-R4 is unavailable.
6. Implementation evidence includes independent RK2, 288/288 bitwise zero correction, structural conservation/equivariance, 6/6 checkpoint/resume and 6/6 one-step autograd.
7. Multistep evidence contains 360 probes, 216 stable windows, 144 failures and 2880 comparisons.
8. Negative evidence is retained in full: history 0/6, seven failure classes, 19 unresolved rows, backend sensitivity and FD/history limitations.
9. Supported claims are restricted to verified implementation/structure/topology and incomplete gradient qualification.
10. Unsupported claims include trainability, solver-in-the-loop validity, rollout improvement, D3 superiority, differentiable cutoff membership, Stage 01 recovery, confirmed viscosity operator and long-time stability.
11. Paper A is not ready; Paper B is the preferred verification-first direction; Paper C is a possible generalizable differentiability-limit methods paper.
12. Recommended framing: “{assessment['working_title']}”.
13. CMAME topical scope is compatible, but current full-solver readiness is insufficient; stronger general method depth and independent validation are needed.
14. Missing evidence: formal dynamic training qualification, rollout performance/stability and independent D-R4-equivalent validation.
15. Stage 03 Research Record path: `stage_03_Dynamic_SPH_Transformer_Hybrid/documents/Stage_03_Research_Record.docx`.
16. Figure/table package plans 9 figures and 6 tables; no fictitious training or performance plot.
17. Four future Stage 04 hypotheses are design-only and unexecuted.
18. Stage 03E authorization = **false**.
19. New optimizer steps = 0; new training runs = 0.
20. New rollout and rollout-performance evaluations = 0.
21. Historical input freeze contains {freeze['historical_file_count']} files; final re-verification is required after DOCX/render completion.

Provisional closure state: `STAGE03_ROUTE_CLOSURE_EVIDENCE_INCOMPLETE` until the Research Record render audit and final manifest pass.
""")

print(json.dumps({
    "ledger_rows": len(ledger_rows),
    "evidence_rows": len(evidence_rows),
    "supported": len(supported),
    "conditional": len(conditional),
    "unsupported": len(unsupported),
    "figures": len(figures),
    "tables": len(tables),
    "future_hypotheses": len(future["hypotheses"]),
}, ensure_ascii=False))
