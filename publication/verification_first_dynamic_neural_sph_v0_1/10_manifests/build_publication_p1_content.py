#!/usr/bin/env python3
"""Build the evidence-locked P1 Chinese manuscript package and frozen-data figures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path



REPO = Path(__file__).resolve().parents[3]
PUB = Path(__file__).resolve().parents[1]
STAGE = REPO / "stage_03_Dynamic_SPH_Transformer_Hybrid"


def read_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text())


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


freeze = read_json("publication/verification_first_dynamic_neural_sph_v0_1/00_freeze/publication_input_freeze_manifest.json")
ledger = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_status_ledger.json")
evidence_matrix = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_evidence_matrix.json")
claims_boundary = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/claim_boundary/stage03ds_claim_boundary.json")
gradient = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/gradient_boundary/stage03ds_gradient_boundary.json")
topology = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/topology_boundary/stage03ds_topology_component_boundary.json")
readiness = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/manuscript_assessment/stage03ds_manuscript_readiness.json")
rk2 = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/independent_rk2_results.json")
zero = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/zero_correction_results.json")
structural = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/structural_smoke_results.json")
checkpoint = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/checkpoint_resume_results.json")
autograd = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/differentiability_smoke_results.json")
adfd = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/results/fixed_topology_adfd_results.json")
matrix360 = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/failure_matrix/stage03d_complete_360_row_matrix.json")
conservation = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/conservation_over_time/conservation_results.json")
history = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/history_gradients/reference_prehistory_results.json")
reverse_jvp = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/ad_crosscheck/reverse_vs_jvp.json")
extended_fd = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/fd_conditioning/extended_fd_results.json")
attribution = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/attribution/failure_attribution.json")
topology_scan = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_event_scan/te1_dense_scan_results.json")
replay = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_stage_replay/replay_results.json")
event_side = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/event_side_gradients/event_side_gradient_results.json")
topology_status = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/topology_preservation/topology_component_status.json")
reference = read_json("stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/qualification/stage03b_qualification_summary.json")

assert freeze["status"] == "PASS"
assert (rk2["passed"], rk2["required"]) == (48, 48)
assert (zero["passed"], zero["required"]) == (288, 288)
assert structural["passed"] == structural["required_stage_audits"] == 72
assert len(checkpoint["rows"]) == 6 and all(row["pass"] for row in checkpoint["rows"])
assert autograd["one_step_runs"] == 6 and autograd["pass"]
assert matrix360["summary"]["row_count"] == 360
assert matrix360["summary"]["pass_count"] == 216 and matrix360["summary"]["fail_count"] == 144
assert adfd["adfd_comparison_count"] == 2880
assert conservation["per_stage_pass_count"] == conservation["per_stage_count"] == 540
assert history["history_gradient_pass_count"] == 0
assert reverse_jvp["passed"] == reverse_jvp["required"] == 60
assert extended_fd["extended_stable_count"] == 30 and extended_fd["required"] == 60
assert extended_fd["extended_fd_path_count"] == 2640
assert sum(attribution["primary_reason_counts"].values()) == 144
assert len(replay["rows"]) == 6 and all(row["pass"] for row in replay["rows"])
assert len(event_side["rows"]) == 12 and all(row["pass"] for row in event_side["rows"])
assert topology_status["component_status"] == "TOPOLOGY_EVENT_COMPONENT_QUALIFIED"

ART = {
    "ledger": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_status_ledger.json",
    "matrix": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_evidence_matrix.json",
    "ref": "stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/qualification/stage03b_qualification_summary.json",
    "rk2": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/independent_rk2_results.json",
    "zero": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/zero_correction_results.json",
    "struct": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/structural_smoke_results.json",
    "checkpoint": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/checkpoint_resume_results.json",
    "autograd": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/differentiability_smoke_results.json",
    "adfd": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/results/fixed_topology_adfd_results.json",
    "matrix360": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/failure_matrix/stage03d_complete_360_row_matrix.json",
    "conservation": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/conservation_over_time/conservation_results.json",
    "history": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/history_gradients/reference_prehistory_results.json",
    "reverse": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/ad_crosscheck/reverse_vs_jvp.json",
    "extended": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/fd_conditioning/extended_fd_results.json",
    "attribution": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/attribution/failure_attribution.json",
    "scan": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_event_scan/te1_dense_scan_results.json",
    "replay": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_stage_replay/replay_results.json",
    "side": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/event_side_gradients/event_side_gradient_results.json",
    "jump": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/event_jump_audit/event_force_jump_results.json",
    "topology": "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/topology_preservation/topology_component_status.json",
    "readiness": "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/manuscript_assessment/stage03ds_manuscript_readiness.json",
}


def claim(cid: str, location: str, wording: str, artifact: str | list[str], status: str,
          allowed: str, prohibited: str, limitation: str, role: str) -> dict:
    return {
        "claim_id": cid,
        "manuscript_location": location,
        "exact_wording": wording,
        "evidence_artifact": [artifact] if isinstance(artifact, str) else artifact,
        "evidence_status": status,
        "allowed_wording": allowed,
        "prohibited_wording": prohibited,
        "limitation": limitation,
        "role": role,
    }


claim_rows = [
    claim("C01", "9.5", "Stage 01仍为V2_QUALIFICATION_FAIL，Stage 01H为FINITE_RESOLUTION_DOMINANT，黏性算子形式未被确认错误。", "07_reports/stage01h_final_report.md", "PASS_BOUNDARY", "保持历史边界。", "Stage 03恢复Stage 01 V2。", "不构成对Stage 01模型的修复。", "main"),
    claim("C02", "9.5", "Stage 02静态学习路线以STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE关闭。", "stage_02_Particle_Interaction_Operator/07_reports/stage02ms_final_report.md", "PASS_BOUNDARY", "静态路线已关闭。", "静态失败被动态模型修复。", "Stage 02权重与结果不作为Stage 03性能证据。", "main"),
    claim("C03", "3.1", "Stage 03建立规格、参考、实现、多步梯度与拓扑事件的分层资格链。", ART["ledger"], "PASS", "分层资格链已建立。", "完整求解器已资格化。", "各层级结论不可互相替代。", "main"),
    claim("C04", "4", "D-R1两族、D-R2六例与D-R3两族通过，形成18条canonical trajectories。", [ART["ref"], "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_trajectory_manifest.json"], "PASS", "参考轨迹资格化完成。", "这些轨迹证明模型性能。", "参考数据未用于训练。", "main"),
    claim("C05", "4.4–4.5", "声学参考仅为线性区间条件证据，周期涡旋被拒绝为无源精确D-R3。", ART["ref"], "PASS_BOUNDARY", "明确条件与拒绝边界。", "二者均为无限制精确参考。", "不外推到非线性声学或任意涡旋。", "main"),
    claim("C06", "2.4, 5", "D0–D3统一动态接口及冻结实现合同通过Stage 03C。", ART["ledger"], "PASS", "实现合同通过。", "D3性能或优越性已证实。", "实现验证不等于性能验证。", "main"),
    claim("C07", "6.1", "独立RK2实现48/48检查通过。", ART["rk2"], "PASS", "48/48通过。", "长期时间积分稳定性已证明。", "仅覆盖冻结实现检查。", "main"),
    claim("C08", "6.2", "零修正288/288与D0基线bitwise等价。", ART["zero"], "PASS", "bitwise等价。", "非零修正准确或必要。", "只证明退化极限。", "main"),
    claim("C09", "6.3–6.4", "结构smoke 72/72通过。", ART["struct"], "PASS", "冻结结构门通过。", "自主rollout长期守恒。", "结构性质不等于性能。", "main"),
    claim("C10", "5.5", "checkpoint/resume 6/6通过。", ART["checkpoint"], "PASS", "冻结状态与缓存可复现。", "存在训练checkpoint。", "检查对象不是训练模型。", "main"),
    claim("C11", "6.5", "one-step autograd 6/6通过。", ART["autograd"], "PASS", "一步梯度通路通过。", "完整多步可微性通过。", "未包含有限差分或多步资格。", "main"),
    claim("C12", "6.6", "Stage 03C资源审计为CPU float64，优化器步数和训练运行数均为0。", "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/resource_audit_results.json", "PASS_BOUNDARY", "报告执行边界。", "给出速度或成本优势。", "机器资源仅用于复现。", "main"),
    claim("C13", "7.1–7.3", "冻结360个probes产生2880次AD/FD比较，其中216个获得稳定窗口、144个失败。", [ART["adfd"], ART["matrix360"]], "NOT_QUALIFIED", "完整报告216/144。", "只报告216个通过项或声明全部通过。", "总体Stage 03D保持NOT_QUALIFIED。", "main"),
    claim("C14", "7.4", "144个失败按七类唯一主因归档，其中19项UNRESOLVED。", ART["attribution"], "UNRESOLVED", "公开完整分类及未决项。", "所有失败已有单一根因。", "归因是诊断，不是修复。", "main"),
    claim("C15", "7.7", "history资格门0/6通过。", ART["history"], "NOT_QUALIFIED", "history 0/6。", "时间记忆无用或训练失败。", "未执行训练。", "main"),
    claim("C16", "7.5", "同数学后端reverse/JVP 60/60通过。", ART["reverse"], "PASS_DIAGNOSTIC", "AD实现交叉一致。", "AD/FD总体通过。", "不替代FD外部校验。", "main"),
    claim("C17", "7.6", "extended FD覆盖2640条路径，60个选择路径中30个稳定。", ART["extended"], "DIAGNOSTIC", "conditioning贡献于部分失败。", "全部失败均为FD伪影。", "结果依赖路径。", "main"),
    claim("C18", "7.8", "历史默认后端与数学JVP在60个选择诊断中匹配48个，12个不匹配。", ART["reverse"], "DIAGNOSTIC", "冻结诊断显示backend sensitivity。", "D3内在不可微。", "未授权切换后重新资格化。", "main"),
    claim("C19", "7.9", "90条horizon traces均分类为bounded或nonmonotone，未观察到系统性vanish/explode。", "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/horizon_scaling/horizon_gradient_scaling.json", "DIAGNOSTIC", "未检测到系统性vanish/explode。", "训练梯度健康。", "不证明可训练性。", "supplement"),
    claim("C20", "6.3, 7.3", "冻结多阶段审计中540/540 stage conservation检查通过。", ART["conservation"], "PASS", "多阶段结构守恒通过。", "长期稳定性已建立。", "仅覆盖冻结horizon与配置。", "main"),
    claim("C21", "8.2", "TE1记录一次确定性edge birth和一次death。", ART["scan"], "PASS", "事件语义资格化。", "cutoff membership可微。", "边存在性为离散映射。", "main"),
    claim("C22", "8.3", "topology-stage replay 6/6通过。", ART["replay"], "PASS", "冻结重放确定。", "任意拓扑族均通过。", "仅TE1。", "main"),
    claim("C23", "8.4", "event-side fixed-topology gradients 12/12通过。", ART["side"], "PASS", "事件两侧梯度通过。", "跨事件导数存在。", "不穿越cutoff membership求导。", "main"),
    claim("C24", "8.5–8.6", "TE1两侧力跳有限有界，空图语义确定。", [ART["jump"], ART["replay"]], "PASS", "有限跳跃与空图语义通过。", "力在事件处连续。", "连续性不是资格要求。", "main"),
    claim("C25", "8.7", "TOPOLOGY_EVENT_COMPONENT_QUALIFIED是独立组件状态。", ART["topology"], "PASS", "拓扑组件独立通过。", "Stage 03D总体通过。", "不得覆盖梯度总体失败。", "main"),
    claim("C26", "Abstract, 7.9, 9", "Stage 03D保持DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED，Stage 03D-R保持DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED。", ART["ledger"], "NOT_QUALIFIED", "两个状态同时可见。", "D-R修复或覆盖D。", "路线暂停。", "main"),
    claim("C27", "Abstract, 9.3, 10", "未执行动态训练、自主rollout或性能评价，Stage 03E authorization=false。", ART["ledger"], "NOT_EXECUTED", "NOT_EXECUTED/NOT_TESTED。", "训练失败、性能不足或模型提升。", "未执行不等于失败。", "main"),
    claim("C28", "9.6", "当前完整求解器论文证据不完整，缺少训练资格、rollout性能/稳定性与独立D-R4等价验证。", ART["readiness"], "READINESS_BOUNDARY", "明确三类缺口。", "完整求解器已可投稿。", "P1只形成受限方法/验证稿。", "main"),
    claim("C29", "1.3, 9.4", "论文采用verification-first方法/验证主线并吸收多步可微性边界。", ART["readiness"], "MANUSCRIPT_POSITION", "Paper B + Paper C边界。", "successful Transformer solver。", "工作标题不是最终投稿题名。", "main"),
    claim("C30", "3.4, 9", "支持、条件与不支持主张必须分层，训练与性能主张不进入提交稿。", "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/claim_boundary/stage03ds_claim_boundary.json", "PASS_BOUNDARY", "使用冻结claim boundary。", "将条件诊断写成普遍结论。", "P2前保留REF-TODO。", "main"),
]

claim_map = {
    "schema_version": "sph-pio-poc.publication-p1.claim-to-evidence.v1",
    "workflow": "Publication Track P1",
    "unsupported_marker": "UNSUPPORTED_DRAFT_STATEMENT",
    "claim_count": len(claim_rows),
    "claims": claim_rows,
}
write_json(PUB / "01_claim_map/claim_to_evidence_matrix.json", claim_map)


RASTER_FIGURE_IMPLEMENTATION_DISABLED = r'''
# ---------- Frozen-data figure package ----------
FIG = PUB / "04_figures"
BLUE, NAVY, TEAL, GREEN, GOLD, RED, GRAY, LIGHT = "#2E74B5", "#17365D", "#26828E", "#3B7A57", "#B47D18", "#B33A3A", "#6B7280", "#EDF2F7"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titleweight": "bold", "figure.dpi": 150})


def save(fig, name: str) -> None:
    fig.savefig(FIG / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def boxes_figure(name: str, title: str, boxes: list[tuple[float, float, float, float, str, str]], arrows: list[tuple[tuple[float, float], tuple[float, float]]]):
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.set_xlim(0, 10.5); ax.set_ylim(0, 5.2); ax.axis("off")
    ax.set_title(title, fontsize=15, color=NAVY, pad=14)
    for x, y, w, h, label, color in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08", facecolor=color, edgecolor=NAVY, linewidth=1.1))
        ax.text(x+w/2, y+h/2, label, ha="center", va="center", fontsize=9.5, color=NAVY, wrap=True)
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=1.4, color=GRAY))
    save(fig, name)


boxes_figure("figure_01_pipeline.png", "Verification-first Stage 03 evidence chain", [
    (0.3, 2.1, 1.55, 1.0, "03A\nSpecification", LIGHT), (2.1, 2.1, 1.55, 1.0, "03B\nReferences", LIGHT),
    (3.9, 2.1, 1.55, 1.0, "03C\nImplementation\nVERIFIED", "#DDEFE4"), (5.7, 2.1, 1.55, 1.0, "03D\nAD/FD\nNOT QUALIFIED", "#F7DDDD"),
    (7.5, 2.1, 1.55, 1.0, "03D-R\nMixed / unresolved", "#F8EBCF"), (9.3, 2.1, 0.9, 1.0, "03D-S\nClose", LIGHT),
    (5.7, 0.45, 2.4, 0.85, "Independent TE1 topology component\nQUALIFIED", "#DDEFE4"),
    (7.8, 4.0, 2.0, 0.7, "Stage 03E = false", "#F7DDDD"),
], [((1.85,2.6),(2.1,2.6)),((3.65,2.6),(3.9,2.6)),((5.45,2.6),(5.7,2.6)),((7.25,2.6),(7.5,2.6)),((9.05,2.6),(9.3,2.6)),((6.5,2.1),(6.8,1.3)),((8.25,3.1),(8.7,4.0))])

boxes_figure("figure_02_architecture.png", "D0-D3 unified dynamic controls (no superiority encoding)", [
    (0.5, 3.4, 2.0, 0.9, "D0\nBaseline WCSPH\nno correction", LIGHT),
    (3.0, 3.4, 2.0, 0.9, "D1\nInstantaneous MLP\nreciprocal head", "#E5EDF7"),
    (5.5, 3.4, 2.0, 0.9, "D2\nRecurrent state\nreciprocal head", "#E5EDF7"),
    (8.0, 3.4, 2.0, 0.9, "D3\nCausal temporal attention\nreciprocal head", "#E5EDF7"),
    (1.7, 1.3, 7.1, 1.0, "Shared solver contract: explicit midpoint RK2 | graph rebuild per RHS | transactional history | additive antisymmetric pair force", "#DDEFE4"),
], [((1.5,3.4),(3.0,2.3)),((4.0,3.4),(4.5,2.3)),((6.5,3.4),(6.0,2.3)),((9.0,3.4),(7.5,2.3))])

boxes_figure("figure_03_rk2_history.png", "RK2 graph rebuild and transactional history commit", [
    (0.5, 3.3, 2.0, 0.9, "Committed Sⁿ, Hⁿ", LIGHT), (3.0, 3.3, 2.0, 0.9, "Start RHS k₁\nrebuild graph", "#E5EDF7"),
    (5.5, 3.3, 2.0, 0.9, "Midpoint state\nephemeral token", "#F8EBCF"), (8.0, 3.3, 2.0, 0.9, "Midpoint RHS k₂\nrebuild graph", "#E5EDF7"),
    (5.5, 1.2, 2.0, 0.9, "Accept checks", LIGHT), (8.0, 1.2, 2.0, 0.9, "Commit Sⁿ⁺¹, Hⁿ⁺¹\nonce only", "#DDEFE4"),
], [((2.5,3.75),(3.0,3.75)),((5.0,3.75),(5.5,3.75)),((7.5,3.75),(8.0,3.75)),((9.0,3.3),(6.5,2.1)),((7.5,1.65),(8.0,1.65))])

boxes_figure("figure_04_reference_hierarchy.png", "Dynamic reference hierarchy and use boundaries", [
    (0.7, 3.3, 2.4, 1.0, "D-R1\nLagrangian MMS\n2 families | verification", "#E5EDF7"),
    (4.05, 3.3, 2.4, 1.0, "D-R2\nSemidiscrete DOP853\n6 cases | time reference", "#E5EDF7"),
    (7.4, 3.3, 2.4, 1.0, "D-R3\nOblique shear\n2 families | source-free", "#DDEFE4"),
    (1.3, 1.0, 3.2, 0.9, "Acoustic: linear-regime conditional", "#F8EBCF"),
    (6.0, 1.0, 3.2, 0.9, "Periodic vortex: rejected as exact source-free", "#F7DDDD"),
], [((3.1,3.8),(4.05,3.8)),((6.45,3.8),(7.4,3.8))])

fig, ax = plt.subplots(figsize=(10.5, 4.8))
labels = ["Independent RK2", "Zero correction", "Structural smoke", "Checkpoint/resume", "One-step autograd", "Training", "Performance"]
passed = [48, 288, 72, 6, 6, 0, 0]
required = [48, 288, 72, 6, 6, 0, 0]
colors = [GREEN]*5 + [GRAY, GRAY]
ax.barh(labels[::-1], passed[::-1], color=colors[::-1])
for i, (p, req) in enumerate(zip(passed[::-1], required[::-1])):
    ax.text(max(p, 1)+3, i, f"{p}/{req}" if req else "NOT EXECUTED", va="center", fontsize=9)
ax.set_xscale("symlog", linthresh=1); ax.set_xlim(0, 450); ax.set_xlabel("Frozen check count (symlog)")
ax.set_title("Implementation and structural qualification matrix", color=NAVY)
ax.spines[["top","right"]].set_visible(False)
save(fig, "figure_05_qualification_matrix.png")

rows360 = matrix360["rows"]
outcomes = np.array([1 if row["historical_stable_window_verdict"] else 0 for row in rows360]).reshape(18, 20)
fig, ax = plt.subplots(figsize=(11.2, 6.0))
ax.imshow(outcomes, aspect="auto", interpolation="nearest", cmap=ListedColormap([RED, BLUE]), vmin=0, vmax=1)
ax.set_xlabel("Probe sequence within complete frozen 360-row matrix")
ax.set_ylabel("Rows 1-360 grouped 20 per line")
ax.set_title("Complete multistep AD/FD outcomes: 216 PASS, 144 failure", color=NAVY)
ax.set_xticks(np.arange(0,20,2)); ax.set_xticklabels(np.arange(1,21,2)); ax.set_yticks(np.arange(0,18,2)); ax.set_yticklabels([f"{i*20+1}-{(i+1)*20}" for i in range(0,18,2)])
ax.legend(handles=[Patch(color=BLUE,label="Stable window PASS (216)"),Patch(color=RED,label="Failure (144)")], loc="upper center", bbox_to_anchor=(0.5,-0.12), ncol=2, frameon=False)
save(fig, "figure_06_complete_360_matrix.png")

fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
axes[0].bar(["History gate", "Reverse/JVP", "Extended FD"], [0,60,30], color=[RED,GREEN,GOLD])
axes[0].set_ylim(0,65); axes[0].set_ylabel("Passed / stable selections")
axes[0].set_title("Frozen gradient diagnostics", color=NAVY)
for i, txt in enumerate(["0/6","60/60","30/60"]): axes[0].text(i, [0,60,30][i]+2, txt, ha="center")
axes[1].bar(["Match", "Mismatch"], [48,12], color=[GREEN,RED])
axes[1].set_ylim(0,65); axes[1].set_title("Historical backend vs math JVP (selected)", color=NAVY)
for i, v in enumerate([48,12]): axes[1].text(i,v+2,f"{v}/60",ha="center")
for ax in axes: ax.spines[["top","right"]].set_visible(False)
fig.suptitle("History attenuation and backend sensitivity are diagnostics, not trainability evidence", fontsize=13, fontweight="bold")
save(fig, "figure_07_history_backend.png")

fig, ax = plt.subplots(figsize=(10.8, 4.8))
s = np.linspace(0, 1, 1001)
active = ((s > topology_scan["analytic"]["birth"]) & (s < topology_scan["analytic"]["death"])).astype(int)
ax.step(s, active, where="post", color=BLUE, lw=2.5)
ax.axvline(0.25,color=GREEN,ls="--",label="birth s=0.25"); ax.axvline(0.75,color=RED,ls="--",label="death s=0.75")
ax.fill_between(s,0,active,step="post",alpha=.15,color=BLUE)
ax.text(.5,.72,"fixed-side gradients qualified\n(event-side 12/12)",ha="center",color=NAVY)
ax.text(.25,.12,"discrete graph change",ha="center",color=GREEN); ax.text(.75,.12,"discrete graph change",ha="center",color=RED)
ax.set_yticks([0,1]); ax.set_yticklabels(["edge absent","edge present"]); ax.set_xlabel("TE1 path parameter s")
ax.set_title("TE1 edge birth/death and piecewise-smooth boundary", color=NAVY); ax.legend(frameon=False)
ax.spines[["top","right"]].set_visible(False)
save(fig, "figure_08_topology_event.png")

fig, ax = plt.subplots(figsize=(9.0, 4.8))
counts = [len(claims_boundary["supported_claims"]),len(claims_boundary["conditional_claims"]),len(claims_boundary["unsupported_claims"])]
ax.bar(["Supported","Conditional","Unsupported"],counts,color=[GREEN,GOLD,RED])
for i,v in enumerate(counts): ax.text(i,v+.25,str(v),ha="center",fontsize=12,fontweight="bold")
ax.set_ylim(0,9); ax.set_ylabel("Frozen claim count"); ax.set_title("Supported / conditional / unsupported claim boundary", color=NAVY)
ax.text(2,0.8,"Includes training, rollout, superiority,\nlong-time stability and Stage 01 recovery",ha="center",color="white",fontsize=8)
ax.spines[["top","right"]].set_visible(False)
save(fig, "figure_09_claim_map.png")
'''


# ---------- Tables ----------
ledger_lines = ["| 阶段 | 唯一状态 | 主要通过证据 | 主要边界 |", "|---|---|---|---|"]
for row in ledger["rows"]:
    ledger_lines.append(f"| {row['stage']} | `{row['status']}` | {row['principal_pass_evidence']} | {row['principal_blocker']} |")
table1 = "\n".join(ledger_lines)

table2 = """| 层级 | 冻结对象 | 结果 | 证据角色与边界 |
|---|---|---|---|
| D-R1 | Lagrangian compression；coupled deformation | 两族PASS | 解析/MMS verification，不等于物理验证 |
| D-R2 | 同半离散DOP853 time reference | 6/6 PASS | 时间参考，不是空间真值 |
| D-R3 | oblique shear A/B | 两族PASS；6条exact trajectories | source-free independent validation |
| Acoustic | acoustic candidate | linear-regime conditional | 不外推为无限制精确D-R3 |
| Vortex | periodic vortex candidate | rejected as exact source-free | 不作为D-R3精确参考 |
| D-R4 | 外部V&V-qualified reference | NOT_AVAILABLE | 当前独立验证缺口 |"""

table3 = """| 资格门 | 结果 | 状态 | 允许解释 |
|---|---:|---|---|
| Independent RK2 | 48/48 | PASS | 冻结RK2实现一致 |
| Zero correction | 288/288 | PASS | 与D0 bitwise等价 |
| Structural smoke | 72/72 | PASS | 结构守恒/等变等冻结门通过 |
| Checkpoint/resume | 6/6 | PASS | state/graph/history/RNG可复现 |
| One-step autograd | 6/6 | PASS | 一步梯度通路有限非零 |
| Dynamic training / performance | 0 / 0 | NOT_EXECUTED | 不可写为训练失败或性能不足 |"""

reason_cn = {
    "AD_FD_DIRECTION_OR_SIGN_MISMATCH":"AD/FD方向或符号不一致",
    "DERIVATIVE_NEAR_STRUCTURAL_ZERO":"导数接近结构零",
    "FD_NONMONOTONE_NO_ADJACENT_WINDOW":"FD非单调且无相邻稳定窗",
    "FD_ROUNDOFF_DOMINATED":"FD舍入误差主导",
    "FD_TRUNCATION_DOMINATED":"FD截断误差主导",
    "NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH":"固定图数值非光滑",
    "UNRESOLVED":"未决",
}
tax_lines = ["| 主因 | 数量 | 解释边界 |", "|---|---:|---|"]
for key,count in attribution["primary_reason_counts"].items():
    tax_lines.append(f"| {reason_cn[key]} (`{key}`) | {count} | 归因诊断，不代表合同已修复 |")
table4 = "\n".join(tax_lines)

table5 = """| TE1证据 | 结果 | 状态 | 禁止外推 |
|---|---:|---|---|
| edge birth | 1/1 | PASS | 非任意拓扑族 |
| edge death | 1/1 | PASS | 非连续edge membership |
| stage replay | 6/6 | PASS | 仅冻结TE1语义 |
| fixed-side gradients | 12/12 | PASS | 不穿过cutoff事件求导 |
| force jump | finite and bounded | PASS | 不声称事件处连续 |
| empty graph | deterministic | PASS | 不构造合成非物理pair |"""

table6 = """| 主张类别 | 可写入正文 | 不可写入正文 | 主要证据状态 |
|---|---|---|---|
| 实现 | RK2 hybrid冻结实现通过 | solver performance verified | PASS |
| 退化极限 | zero correction 288/288 bitwise等价 | nonzero correction准确 | PASS |
| 守恒 | 540/540多阶段守恒检查通过 | 长时稳定性已证明 | PASS |
| 多步梯度 | 216/360稳定窗；144 failure | 全部梯度有效 | NOT_QUALIFIED |
| 失败归因 | mixed or unresolved；19未决 | 单一根因已解决 | UNRESOLVED |
| 拓扑 | TE1 birth/death与fixed-side通过 | cutoff membership可微 | COMPONENT PASS |
| 训练 | 未授权、未执行 | Transformer可训练 | NOT_EXECUTED |
| 性能 | 未测试 | rollout改进SPH或D3优于D1/D2 | NOT_TESTED |"""

write(PUB / "05_tables/table_package.md", f"""# Publication P1 — Table package

所有表格均由 `publication_input_freeze_manifest.json` 中的只读机器 artifact 生成；不得脱离其解释边界。

## Table 1. Stage 03 status ledger

{table1}

## Table 2. Dynamic reference trajectory inventory

{table2}

## Table 3. Implementation and structural gates

{table3}

## Table 4. AD/FD failure taxonomy

{table4}

## Table 5. Topology-event evidence

{table5}

## Table 6. Final claim/evidence matrix

{table6}
""")


figure_plan_rows = [
    (1,"Stage 03 verification-first pipeline","workflow","显示03A–03D-S时序及独立topology分支；Stage 03E=false。","P1_DETAILED_DESIGN"),
    (2,"D0–D3 dynamic architecture","architecture schematic","不编码优越性；显示共享RK2/history/reciprocal head合同。","P1_DETAILED_DESIGN"),
    (3,"RK2 graph rebuild and history commit","state-transition schematic","start/midpoint各重建图，accepted state仅commit一次。","P1_DETAILED_DESIGN"),
    (4,"D-R1/D-R2/D-R3 reference hierarchy","evidence hierarchy","保留MMS、time reference、source-free及拒绝边界。","P1_DETAILED_DESIGN"),
    (5,"Zero-correction and structural qualification matrix","status matrix","bitwise/structural与performance分离。","P1_DETAILED_DESIGN"),
    (6,"Complete 360-probe AD/FD outcome matrix","complete matrix","显示全部360 rows、216 PASS与144 failure。","P1_DETAILED_DESIGN"),
    (7,"History attenuation and backend sensitivity","diagnostic panels","条件性措辞；不声称可训练。","P1_DETAILED_DESIGN"),
    (8,"TE1 edge birth/death and piecewise-smooth boundary","event schematic","不把edge existence画成可微。","P1_DETAILED_DESIGN"),
    (9,"Supported/conditional/unsupported claim map","claim map","包含training/rollout NOT EXECUTED。","P1_DETAILED_DESIGN"),
]
fig_lines = ["| Figure | 标题 | 形式 | 完整性规则 | 文件 |", "|---:|---|---|---|---|"]
for row in figure_plan_rows: fig_lines.append("| " + " | ".join(map(str,row)) + " |")
write(PUB / "04_figures/figure_package_plan.md", "# Publication P1 — Figure package plan\n\nP1采用附件允许的详细设计路径；未指定Python/R投稿绘图后端，因此本轮不生成最终科研图。每幅图已锁定证据输入、面板结构和完整性规则。\n\n" + "\n".join(fig_lines) + "\n\n禁止图件：训练曲线、rollout误差曲线、speedup、模型准确率或只包含216个PASS的选择性图。")


title_keywords = """# Title and keywords — working version

## English working title

Verification-first development of a conservative dynamic neural–SPH solver: zero-correction equivalence, topology events, and limits of multistep gradient qualification

## 中文工作标题

守恒型动态神经–SPH求解器的验证优先开发：零修正等价、拓扑事件与多步梯度资格边界

## Keywords

smoothed particle hydrodynamics；physics-informed machine learning；verification and validation；conservative neural correction；multistep differentiability；topology event；negative evidence

题名为P1工作版本，不作为最终投稿题名；P2完成文献核验与期刊定位后再定稿。
"""
write(PUB / "03_manuscript_cn/title_and_keywords.md", title_keywords)

abstract = """# 结构化中文摘要

## 背景

动态神经–SPH耦合同时引入时间积分、动态图重建、历史状态提交和多步自动微分；如果这些层级未被分开资格认定，结构正确性、梯度有效性与模型性能容易被混为同一结论。[REF-TODO: verification of physics-informed machine learning；SPH verification and validation]

## 方法

本文采用verification-first路线，建立D0基线、D1瞬时MLP、D2循环模型和D3因果时间注意力模型的统一动态接口，并依次审计动态参考、独立RK2、zero correction、反对称reciprocal pair-force、多步AD/FD和确定性拓扑事件。全部结论受冻结claim boundary约束。

## 结果

独立RK2的48/48检查、zero correction的288/288 bitwise等价、结构smoke的72/72、checkpoint/resume的6/6与one-step autograd的6/6均通过；冻结多阶段测试中540/540守恒检查通过。完整360-probe多步AD/FD矩阵只有216个probe获得稳定窗口，144个失败，history门为0/6；因此Stage 03D保持`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。确定性TE1记录一次edge birth和一次death，6/6 replay与12/12 event-side gradients通过，但edge membership仍是离散事件。

## 结论

结果支持对动态实现、零修正退化、结构守恒和TE1事件两侧语义作分层资格认定，却不支持完整多步梯度、可训练性或性能主张。Stage 03D-R将144个失败限定为mixed or unresolved。本文未执行动态训练、自主rollout或性能验证；贡献在于公开验证链及其失败边界，而非证明Transformer改进SPH。
"""
write(PUB / "03_manuscript_cn/structured_abstract_cn.md", abstract)

outline = """# Evidence-locked manuscript architecture

## 论证主线

问题不是“Transformer是否提高SPH精度”，而是动态神经–SPH耦合中的守恒、时间推进、历史提交、动态图和多步梯度能否被拆分为可执行且不互相覆盖的资格合同。正文先建立公式和状态等级，再给出reference与implementation正证据，随后完整公开多步梯度负证据，最后把TE1作为独立组件处理。

## 研究问题

1. RQ1：如何把守恒、RK2、history commit与graph rebuild转化为可执行合同？
2. RQ2：zero correction、结构守恒与离散拓扑事件能否独立资格认定？
3. RQ3：固定拓扑多步rollout中的标准AD/FD资格门在哪些条件下不能形成完整证据？

## 论证顺序

Introduction → formulation → qualification framework → references → implementation → structural verification → complete multistep results → topology component → discussion/limitations → conclusions。

## 不可越界

Paper A不采用；Stage 03D NOT_QUALIFIED必须在摘要、结果和讨论可见；216/144同时报告；topology component PASS不等于整体gradient PASS；所有外部文献暂用`[REF-TODO: topic]`。
"""
write(PUB / "02_outline/manuscript_architecture.md", outline)

manuscript = f"""# 守恒型动态神经–SPH求解器的验证优先开发：零修正等价、拓扑事件与多步梯度资格边界

英文工作标题：Verification-first development of a conservative dynamic neural–SPH solver: zero-correction equivalence, topology events, and limits of multistep gradient qualification

P1中文稿 v0.1｜Evidence-locked manuscript draft｜非投稿定稿

## 摘要

动态神经–SPH耦合把时间积分、动态图重建、历史状态提交和多步自动微分置于同一计算链中；若缺少分层合同，架构正确、梯度有效与性能提升会被错误地合并为单一结论。本文采用verification-first路线，构建D0基线、D1瞬时MLP、D2循环模型与D3因果时间注意力模型的统一动态框架，并依次审计动态参考、独立RK2、zero correction、反对称reciprocal pair-force、多步AD/FD与确定性拓扑事件。独立RK2的48/48检查、zero correction的288/288 bitwise等价、结构smoke的72/72、checkpoint/resume的6/6与one-step autograd的6/6均通过；冻结多阶段测试中540/540守恒检查通过。完整360-probe矩阵中216个probe获得stable AD/FD window，144个失败，history门为0/6。因此，Stage 03D保持`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`；Stage 03D-R将失败归因为mixed or unresolved。确定性TE1记录一次edge birth与一次death，6/6 replay和12/12 event-side gradients通过，但cutoff edge membership仍为离散事件。本文没有执行动态训练、自主rollout或性能验证，因而不主张Transformer可训练、优于D1/D2或改进SPH。贡献在于建立可审计的资格链，并完整公开其正负证据边界。 <!-- CLAIM:C07,C08,C09,C10,C11,C13,C15,C20,C21,C22,C23,C26,C27 -->

## 关键词

光滑粒子流体动力学；物理机器学习；验证与确认；守恒型神经修正；多步可微性；拓扑事件；负证据

# 1. 引言

## 1.1 SPH与物理机器学习耦合的验证问题

光滑粒子流体动力学（SPH）以粒子邻域上的核近似离散连续介质方程，具有无网格与大变形适应性，但其误差同时受核、粒子分辨率、邻域、边界、黏性离散和时间推进影响。[REF-TODO: SPH foundations and verification] 当神经网络以加性修正进入动量方程时，新的误差源不仅来自函数逼近，还来自模型接口、成对力对称性、动态图构造、缓存状态和自动微分后端。[REF-TODO: conservative neural particle methods]

因此，“代码能够运行”不能替代实现验证，“一步梯度存在”不能替代多步梯度资格，“结构守恒”不能替代精度或稳定性证据。本文把这些命题拆成彼此独立的证据层级，并要求每个事实性结果句可追溯到冻结artifact。该做法的目标不是预设模型有效，而是允许验证流程在遇到负结果时停止，并保留仍然成立的局部结论。 <!-- CLAIM:C03,C30 -->

## 1.2 动态图、时间积分与可微性的证据缺口

动态图粒子求解器的计算图随粒子位置变化。显式midpoint/RK2在start和midpoint分别评估右端项；如果邻域只在整步开始重建，或midpoint临时history被错误提交，形式上相同的积分公式会对应不同的算法。另一方面，cutoff crossing引起edge birth/death，使edge membership成为离散映射；事件两侧可以讨论固定图分支内的梯度，跨事件的中心差分则混合了两套计算图。[REF-TODO: differentiable simulation with dynamic graphs]

这些问题使“可微”成为需要资格合同的经验命题。本文采用AD/FD stable-window规则，不以单个epsilon或最佳probe替代完整矩阵；同时采用reverse/JVP、extended FD、history路径和backend sensitivity作为归因诊断。所有诊断都保留原合同，不通过切换后端或事后放宽阈值重写结论。

## 1.3 verification-first研究思路

本文采用Paper B的verification-first conservative dynamic neural–SPH coupling主线，并吸收Paper C关于多步可微性边界的分析。主叙事由“先定义可执行合同，再分别判断PASS、NOT_QUALIFIED与NOT_EXECUTED”驱动，而不是由“Transformer改善SPH”的性能前提驱动。当前工作标题仅用于P1架构，不是最终投稿题名。 <!-- CLAIM:C29 -->

**图1设计。** Stage 03 verification-first资格链：按03A→03B→03C→03D→03D-R→03D-S排列，TE1 topology作为独立组件分支，Stage 03E=false；不得把topology component PASS连接为Stage 03D总体PASS。

## 1.4 研究问题与贡献

RQ1询问如何把守恒、时间推进、history commit与邻域重建转化为可执行验证合同；RQ2询问zero correction、结构守恒和离散拓扑事件能否独立资格认定；RQ3询问固定拓扑多步rollout中，标准AD/FD资格门在哪些条件下不能形成完整证据。本文不把“模型是否提高精度”作为已回答问题。

贡献包括：（1）建立reference–implementation–multistep gradient–topology的verification-first资格链；（2）实现D0–D3统一动态框架，并建立zero correction 288/288与D0 bitwise等价；（3）以反对称reciprocal pair-force在冻结多阶段测试中保持540/540离散线动量守恒；（4）建立TE1 deterministic topology-event audit；（5）公开全部360 probes，包含216 PASS、144 failure和mixed/unresolved归因。 <!-- CLAIM:C03,C06,C08,C13,C20,C21,C25,C26 -->

# 2. 控制方程与模型形式

## 2.1 WCSPH基线

冻结的半离散系统以粒子状态S={{x_i, v_i, ρ_i}}为基本变量。位置、密度和速度的演化写为：

$$ dx_i/dt = v_i $$

$$ dρ_i/dt = C_SPH,i(S) $$

$$ dv_i/dt = a_SPH,i(S) + a_θ,i(S_history, H_history, G_history) $$

压力采用冻结的弱可压EOS：

$$ p_i = c_s²(ρ_i - ρ₀) $$

本文不重新资格认定基线黏性算子，也不把Stage 03结果解释为Stage 01 V2恢复。基线方程、图和时间步选择仍由SPH求解器控制。

## 2.2 additive momentum correction

神经模块只产生加性加速度修正：

$$ a_θ,i = (1/m_i) Σ_{{j:{{i,j}}∈G}} f_θ,ij $$

这一接口把网络约束在动量修正层，不允许其直接预测粒子位置、替代EOS、改变邻域membership或覆盖baseline加速度。zero correction时，a_θ,i严格为零，从而定义可执行的baseline退化合同。

## 2.3 reciprocal antisymmetric pair-force

成对修正力写为：

$$ f_θ,ij = F⁰_ij [ α_ij r̂_ij + β_ij t_ij ] $$

其中α_ij=α_ji、β_ij=β_ji，且r̂_ji=-r̂_ij、t_ji=-t_ij，因此f_θ,ji=-f_θ,ij。该硬反对称构造在图上直接消去成对内力和；它建立结构守恒，不建立非零修正的准确性、必要性或性能优势。[REF-TODO: antisymmetric pair-force conservation]

## 2.4 D0–D3架构

D0为无修正baseline；D1使用瞬时局部token与MLP；D2引入循环hidden state；D3使用因果temporal attention处理accepted history。D1–D3共享tokenization、reciprocal head、RK2、graph rebuild与安全拒绝语义。D0–D3的作用是控制结构复杂度，不是经过训练的性能排序。冻结实现合同在Stage 03C通过，但不证明D3优于D1/D2。 <!-- CLAIM:C06 -->

**图2设计。** D0–D3统一动态架构：并列展示baseline、instantaneous MLP、recurrent state与causal temporal attention，共享RK2、graph rebuild、history semantics与reciprocal head；图形不编码模型优越性。

## 2.5 不允许的替代与软守恒方式

合同禁止网络改变edge membership、使用单向非reciprocal边、以损失惩罚替代硬反对称、在midpoint提交history、把wrapped position用于动力学推进，或将topology事件通过未登记的soft edge规避。本文不评价这些替代设计的普遍有效性，只说明它们不属于本次冻结证据。

# 3. 验证与资格框架

## 3.1 状态等级

资格链按时间顺序包含Stage 03A specification、Stage 03B reference qualification、Stage 03C implementation verification、Stage 03D multistep gradient/topology campaign、Stage 03D-R attribution和Stage 03D-S route closure。每一状态只回答本层问题，不继承为后续层的自动PASS。 <!-- CLAIM:C03 -->

**表1 Stage 03状态账本。**

{table1}

## 3.2 reference hierarchy

D-R1用于解析/MMS verification，D-R2用于同半离散时间参考，D-R3用于source-free exact/independent validation，D-R4要求外部V&V-qualified reference。层级越高，允许的确认性解释越强；但任何一层都不等于训练或性能数据。D-R4当前不可用，是投稿证据缺口而不是被低层级参考替代的空位。

## 3.3 FAIL、NOT_QUALIFIED与NOT_EXECUTED区别

FAIL表示执行了冻结门且不满足；NOT_QUALIFIED表示整体所需证据未满足，可能同时包含局部PASS；NOT_EXECUTED表示相关工作没有被授权或运行。Stage 03D属于NOT_QUALIFIED，因为144/360失败且history为0/6；动态训练属于NOT_EXECUTED，不能写为“训练失败”。

## 3.4 claim boundary

SUPPORTED claim可以直接由冻结证据支持；CONDITIONAL claim必须保留选择范围和限定词；UNSUPPORTED claim不得进入可提交稿。每条事实性结果句在P1源稿中以不可见CLAIM标记映射到`claim_to_evidence_matrix.json`，未映射语句在审计中标记`UNSUPPORTED_DRAFT_STATEMENT`。 <!-- CLAIM:C30 -->

# 4. 动态参考轨迹

## 4.1 D-R1 Lagrangian MMS

D-R1包含Lagrangian compression与coupled deformation两族，通过解析闭包与符号定义检查。其作用是验证控制方程、源项和Lagrangian状态演化的一致性；MMS不构成无源物理验证，也不允许作为模型性能数据。[REF-TODO: method of manufactured solutions]

## 4.2 D-R2 semidiscrete DOP853

D-R2对两族、N=8/12/16共六个case建立同半离散算子的高精度DOP853时间参考，6/6通过。该层隔离时间积分误差，但空间离散与核误差仍在两条轨迹中共享，因此DOP853不是连续方程真值。[REF-TODO: high-order time reference for semidiscrete systems]

## 4.3 D-R3 oblique shear

D-R3采用oblique shear A/B两族source-free exact reference，并在N=8/12/16形成六条精确轨迹。结合D-R1与D-R2，Stage 03B最终形成18条canonical trajectories；这些轨迹只用于资格化与后续冻结probe，不用于训练、normalization或阈值选择。 <!-- CLAIM:C04 -->

## 4.4 acoustic conditional boundary

声学候选仅被分类为`DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL`。因此正文只能将其视为线性区间的条件性参考，不能外推为任意振幅或长期声学传播的精确D-R3。 <!-- CLAIM:C05 -->

## 4.5 periodic-vortex rejection

periodic vortex被拒绝为exact source-free reference。拒绝结果被保留，因为reference qualification的价值包括排除角色不匹配的候选，而不是只展示通过家族。该候选不进入性能比较，也不被重新命名为外部独立验证。 <!-- CLAIM:C05 -->

**图4设计。** D-R1/D-R2/D-R3参考层级：分层显示MMS verification、semidiscrete time reference与source-free validation，并在侧栏标记acoustic conditional、periodic-vortex rejection与D-R4缺口。

**表2 动态参考轨迹清单。**

{table2}

# 5. 动态求解器实现

## 5.1 unwrapped/wrapped position

动力学状态保存unwrapped position以保持时间连续性；wrapped position仅用于周期邻域搜索与最小镜像表示。该分离避免粒子跨越周期边界时在积分状态中引入人为跳跃，同时使graph construction保持确定。

## 5.2 RK2 start/midpoint/accept

显式midpoint/RK2采用：

$$ k₁ = F(Sⁿ, historyⁿ) $$

$$ Sⁿ⁺¹ᐟ² = Sⁿ + (Δt/2) k₁ $$

$$ k₂ = F(Sⁿ⁺¹ᐟ², historyⁿ + ephemeral token) $$

$$ Sⁿ⁺¹ = Sⁿ + Δt k₂ $$

start与midpoint是独立RHS evaluation。accepted state必须通过finite与safety checks，拒绝步同时回滚state和history。

## 5.3 graph rebuild

每次RHS evaluation从对应state重建reciprocal graph，禁止固定整步topology。该语义保证midpoint的邻域由midpoint位置决定；同时，Stage 03D的fixed-topology AD/FD会显式筛选graph sequence identity，以免将edge change混入连续路径的梯度比较。

## 5.4 temporal history commit

start和midpoint只读committed snapshot；midpoint token为ephemeral，不得append、evict或覆盖accepted history。只有Sⁿ⁺¹被接受后，才在物理时刻tₙ₊₁原子提交一个token。该事务语义是D2/D3可复现与checkpoint一致性的必要条件。

**图3设计。** RK2 graph rebuild与history commit：Sⁿ→start RHS/rebuild→midpoint/ephemeral token→midpoint RHS/rebuild→accept checks→一次accepted commit；拒绝路径回滚state与cache。

## 5.5 checkpoint/resume

checkpoint记录state、graph、history、模型参数与RNG语义。冻结6种配置的resume结果为6/6通过，说明指定执行路径可复现；这里不存在训练checkpoint，不能把该结果解释为训练过程可恢复。 <!-- CLAIM:C10 -->

# 6. 结构验证

## 6.1 independent RK2 48/48

独立functional RK2与主实现的48/48冻结检查全部通过，覆盖指定状态、时间和graph语义。该结果支持实现一致性，但不覆盖长时间稳定性或自主rollout。 <!-- CLAIM:C07 -->

## 6.2 zero correction 288/288

zero correction在288/288检查中与D0 baseline bitwise相同，且没有使用事后容差。该结果是D1–D3接口的退化极限验证：当神经修正严格为零时，动态框架不改变baseline；它不证明非零修正准确。 <!-- CLAIM:C08 -->

## 6.3 pair-force conservation

反对称reciprocal pair-force使每条无序边的修正内力成对抵消。结构smoke包含72/72通过，多步campaign的540/540 stage conservation检查也通过。两者共同支持冻结实现中的离散线动量结构保持，但不支持长期稳定性或误差收敛主张。 <!-- CLAIM:C09,C20 -->

## 6.4 O(2)、Galilean与周期性

冻结structural smoke同时覆盖O(2)变换、粒子置换、Galilean与周期一致性。这里的PASS表示特定变换合同通过，不表示神经表示已经学习出一般物理规律。[REF-TODO: equivariant neural operators for particle systems]

## 6.5 one-step autograd

one-step autograd共6/6运行返回预期的有限非零梯度，证明基础计算图连接存在。Stage 03C没有运行finite difference或multistep AD/FD，因此该PASS不能用于推导完整多步可微性。 <!-- CLAIM:C11 -->

## 6.6 resource boundary

Stage 03C和Stage 03D的正式执行采用CPU float64以降低数值路径歧义；资源记录只服务复现，不构成速度、成本或加速比较。优化器对象、参数更新和训练运行均为0。 <!-- CLAIM:C12,C27 -->

**图5设计。** Zero-correction与结构资格矩阵：展示48/48、288/288、72/72、6/6、6/6，并以独立灰色栏标记training/performance为NOT EXECUTED，禁止把结构PASS解释为性能PASS。

**表3 实现与结构资格门。**

{table3}

# 7. 多步可微性资格

## 7.1 frozen 360-probe design

正式合同包含D1–D3、四个固定拓扑case、三个seed、K=1/2/4/8 horizon及参数、初值和history probe，合计360 rows。每个probe保存AD重复、四个冻结epsilon的FD值、graph sequence identity和stable-window verdict，形成2880次历史AD/FD比较。矩阵在结果前冻结，不允许根据结果增加epsilon或删probe。 <!-- CLAIM:C13 -->

## 7.2 AD/FD stable-window rule

资格门要求相邻epsilon形成稳定窗口，并同时满足方向、相对/绝对误差和确定性条件。单个epsilon的偶然接近不足以PASS；导数接近结构零时，需要结合绝对误差和尺度分类。该规则的目的是把roundoff、truncation与非光滑影响暴露出来，而不是优化通过率。[REF-TODO: finite-difference verification of algorithmic derivatives]

## 7.3 complete results：216/360

360个probe中216个获得stable window，144个未通过，总体通过率不被用作模型排名。按horizon，K=1/2/4/8分别为60/57/51/48个PASS；按arm，D1、D2、D3分别为65/96、75/120、76/144。完整结果意味着正负证据必须共同出现，Stage 03D据此保持NOT_QUALIFIED。冻结多阶段守恒同时为540/540通过，说明结构守恒可以在梯度资格失败时独立成立。 <!-- CLAIM:C13,C20,C26 -->

**图6设计。** 完整360-probe AD/FD outcome matrix：按arm/case/horizon/probe组织全部360格，216个PASS与144个failure同时显示；附七类failure taxonomy及19 unresolved，不允许筛选最佳子集。

## 7.4 failure taxonomy

144个失败按唯一主因分为：方向/符号不一致5、接近结构零29、FD非单调且无相邻窗69、roundoff主导3、truncation主导3、固定图数值非光滑16和UNRESOLVED 19。分类覆盖所有失败，但“唯一主因”是账本规则，不意味着每个失败只有一个物理贡献。19个未决row必须保留在主文和补充材料。 <!-- CLAIM:C14 -->

**表4 AD/FD失败分类。**

{table4}

## 7.5 reverse/JVP crosscheck

在统一数学attention后端上，reverse-mode与JVP的60/60选择比较通过。这支持两条AD实现路径的一致性，却不能替代FD或使360矩阵整体转为PASS。 <!-- CLAIM:C16 -->

## 7.6 extended FD

extended FD扩展至2640条路径；60个选择路径中30个显示扩展稳定性，另30个呈U形conditioning特征。该诊断支持“FD conditioning对部分失败有贡献”，但不支持“全部失败都是FD伪影”。 <!-- CLAIM:C17 -->

## 7.7 history attenuation

history资格门0/6通过；在reference-prehistory追踪中，一条路径被归为conditioning limited，五条低于FD resolution。该结果表示当前冻结路径中的history influence在rollout传播中强烈衰减，而不是证明temporal memory无用，更不是训练失败。 <!-- CLAIM:C15 -->

## 7.8 backend sensitivity

历史默认后端reverse与math JVP在60个选择诊断中匹配48个，12个不匹配，且不匹配集中在选定D3路径。正文只能写为“冻结选择诊断中存在backend sensitivity”；不能写为D3内在不可微，也不能在P1切换后端后重新资格化。 <!-- CLAIM:C18 -->

**图7设计。** History attenuation与backend sensitivity多面板：history 0/6、reverse/JVP 60/60、extended FD 30/60与historical-backend match 48/60；标题和图例均使用diagnostic限定。

## 7.9 mixed/unresolved attribution

90条horizon traces均被分类为bounded或nonmonotone，没有检测到系统性vanish/explode；该结果不证明训练梯度健康。综合AD crosscheck、extended FD、history attenuation、backend sensitivity与19个未决row，Stage 03D-R的唯一结论为`DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`。D-R是归因而非修复，不覆盖Stage 03D。 <!-- CLAIM:C19,C26 -->

# 8. 拓扑事件资格

## 8.1 TE1设计

TE1_TAGGED_PAIR_OSCILLATION使用两粒子确定性路径穿越cutoff Rc，在s=0.25附近发生birth、s=0.75附近发生death。4097点dense scan、三次bitwise重复及reciprocity/duplicate检查共同锁定事件语义。TE1是kinematic audit family，不代表任意动态图问题。[REF-TODO: nonsmooth events in particle neighbor graphs]

## 8.2 birth/death

dense scan记录恰好一次edge birth和一次death，顺序、bracket、margin、minimum-image及reciprocity门均通过。edge existence从0跳到1或从1跳到0，故该变量本身不是连续可微映射。 <!-- CLAIM:C21 -->

## 8.3 stage replay

D1、D2、D3在birth/death两侧的topology-stage replay共6/6通过，重复构造得到一致graph和pair语义。该结果仅资格认定冻结TE1实现。 <!-- CLAIM:C22 -->

## 8.4 fixed-side gradients

在事件前后各自固定edge membership，D1–D3的12/12 event-side gradient检查通过。允许的主张是事件两侧分支内piecewise-smooth；禁止的主张是跨cutoff membership存在普通导数。 <!-- CLAIM:C23 -->

## 8.5 force jump

事件两侧的修正力跳被登记为有限、有界、确定且满足成对守恒；连续性不是该离散事件的资格要求。跨事件中心差分随epsilon呈离散图变化特征，不能归因为网络梯度本身失败。 <!-- CLAIM:C24 -->

## 8.6 empty graph

edge absent侧保留canonical self records但不制造synthetic self pair；非self pair聚合为exact zero，token保持finite。D1–D3在两侧共6条empty-graph记录确定。 <!-- CLAIM:C24 -->

## 8.7 piecewise-smooth boundary

TE1组件状态为`TOPOLOGY_EVENT_COMPONENT_QUALIFIED`，因为birth/death、replay、fixed-side gradients、finite jumps和empty graph语义均满足；该组件PASS与Stage 03D整体NOT_QUALIFIED同时成立。 <!-- CLAIM:C25,C26 -->

**图8设计。** TE1 edge birth/death与piecewise-smooth boundary：显示s=0.25 birth、s=0.75 death、两侧固定拓扑梯度、有限力跳与空图语义；edge membership以阶跃呈现，不画成连续可微曲线。

**表5 拓扑事件证据。**

{table5}

# 9. 讨论

## 9.1 架构正确性与可训练性的区别

Stage 03C支持冻结动态实现、零修正退化、结构性质、checkpoint和一步梯度；Stage 03D则否定完整多步梯度资格。两者不矛盾：前者回答实现是否遵守合同，后者回答特定多步导数能否经AD/FD外部校验。没有执行训练意味着无法从任一结果推导Transformer可训练或不可训练。 <!-- CLAIM:C06,C08,C11,C26,C27 -->

## 9.2 fixed-topology gradient与discrete topology

fixed-topology梯度验证要求graph sequence identity，确保AD与FD比较同一分支；topology事件审计则承认edge membership离散，并分别检查两侧分支与事件跳。把两者合并会导致两类错误：要么把跨事件FD发散误写为网络梯度失败，要么把event-side PASS误写为edge existence可微。TE1的分离资格为动态图求解器提供可复用的验证模式，但其跨实现一般性仍需后续研究。[REF-TODO: piecewise differentiability and hybrid systems]

## 9.3 verification evidence与performance evidence

本文没有动态训练、自主rollout、长期稳定性、速度或误差对比。因而“implementation verified”不能写成“solver performance verified”，“540/540守恒”不能写成长时稳定，“216个stable windows”不能写成训练准备完成。未执行的性能工作属于NOT_TESTED，不是负性能结果。 <!-- CLAIM:C27,C30 -->

## 9.4 对dynamic neural particle solvers的含义

最直接的方法意义是：动态神经粒子求解器可以先资格认定结构与实现，再允许多步梯度门独立失败。透明报告144个失败与19个未决row，为选择训练目标、伴随方法或连续邻域假设提供边界，但这些均是未来新假设，不属于P1结果。当前最可辩护的论文定位是verification-first方法/验证稿，而非successful Transformer-corrected solver。 <!-- CLAIM:C14,C29 -->

## 9.5 与Stage 01/02边界

Stage 01保持`V2_QUALIFICATION_FAIL`，Stage 01H将shear偏差归为`FINITE_RESOLUTION_DOMINANT`，黏性算子形式仍为`NOT_CONFIRMED`。Stage 02静态路线以`STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE`关闭。Stage 03未恢复这些状态，也未复用Stage 02失败权重构造动态性能主张。 <!-- CLAIM:C01,C02 -->

## 9.6 limitations

第一，没有正式动态训练资格，不能讨论可训练性与优化稳定性；第二，没有受控或自主rollout性能/稳定性证据；第三，没有独立D-R4或等价外部验证；第四，当前为单一项目实现，跨SPH代码和问题族的一般性有限；第五，部分gradient failure仍为mixed/unresolved。上述限制使完整求解器论文证据不完整。 <!-- CLAIM:C14,C27,C28 -->

**图9设计。** Supported/conditional/unsupported claim map：列出6项支持、4项条件与8项不支持主张，明确training/rollout NOT EXECUTED、Stage 01未恢复及long-time stability未建立。

**表6 最终claim/evidence矩阵。**

{table6}

# 10. 结论

本文建立了守恒型动态神经–SPH耦合的verification-first资格链。D0–D3统一接口、独立RK2、zero correction、结构守恒、checkpoint与one-step autograd形成正实现证据；完整360-probe矩阵则使多步梯度总体保持NOT_QUALIFIED。TE1证明离散edge birth/death可与事件两侧fixed-topology gradients分开资格认定，但不能把edge membership写成可微。Stage 03D-R保留mixed/unresolved边界，Stage 03E未授权。 <!-- CLAIM:C03,C06,C07,C08,C09,C10,C11,C13,C21,C22,C23,C25,C26 -->

因此，本稿的贡献是验证架构及其证据边界，而不是证明训练成功、rollout改进或Transformer优越性。P1可以形成带严格claim limitation的方法/验证中文稿；完整求解器主张仍需训练资格、rollout性能/稳定性和独立验证三类新证据。 <!-- CLAIM:C27,C28,C29 -->

# Data availability

本文P1使用的全部数值结果均来自`publication_input_freeze_manifest.json`登记的项目内部机器artifact，并由hash锁定。360-row matrix、AD/FD comparisons、extended FD、history、horizon、TE1与manifest拟作为补充数据组织；公开仓库、持久标识和许可将在投稿前核验后填写。[REF-TODO: repository, DOI and data license]

# Code availability

本文涉及的Stage 01–03实现与审计代码当前保存在项目工作区。P1不修改历史代码，也不产生新的计算。投稿前需确定可公开代码范围、版本标签、环境文件与许可，并填写持久链接。[REF-TODO: code repository and software citation]

# Author contributions

[AUTHOR-TODO: 按CRediT taxonomy核验并填写作者贡献，不在P1虚构作者角色。]

# Conflict of interest

[AUTHOR-TODO: 投稿前由全体作者核验并填写竞争利益声明。]

# References

P1不生成未经检索核验的外部文献。正文中的`[REF-TODO: topic]`将在Publication Track P2中逐项检索、核验并替换为真实引用；历史项目文档不作为外部学术文献。
"""
write(PUB / "03_manuscript_cn/manuscript_cn_v0_1.md", manuscript)


supplement = """# Supplementary material structure

## Supplementary Note S1 — Contracts and frozen scope

Stage 03A–D-S合同索引、status ledger、claim boundary与freeze hashes。

## Supplementary Data S1 — Complete multistep matrix

完整360-row matrix；主文仍保留216/144、failure taxonomy、history 0/6与19 unresolved，不把失败全部移出主文。

## Supplementary Data S2 — Historical AD/FD comparisons

2880次历史AD/FD比较，包含四个冻结epsilon、AD重复、stable windows、graph identity与absolute/relative errors。

## Supplementary Data S3 — Extended FD and derivative scales

2640条extended FD paths、60条选择诊断、derivative decade distribution和U-shaped conditioning记录。

## Supplementary Data S4 — AD crosschecks and history

reverse/JVP 60/60、historical backend match 48/60、reference-prehistory trace与history 0/6。

## Supplementary Data S5 — Horizon scaling

90条horizon traces及bounded/nonmonotone分类；不得解释为训练梯度健康。

## Supplementary Data S6 — TE1 topology package

4097点dense scan、birth/death brackets、6/6 replay、12/12 fixed-side gradients、force jumps与empty-graph semantics。

## Supplementary Data S7 — Reproducibility and resources

checkpoint/resume hashes、resource audits、run manifests、input/output hashes与环境说明。

## Main-text retention rule

主文必须保留完整PASS/FAIL计数、七类failure taxonomy、history 0/6、19 unresolved、12/60 backend sensitivity和Stage 03D NOT_QUALIFIED。
"""
write(PUB / "06_supplement/supplementary_structure.md", supplement)

internal_only = """# Internal-only evidence register

下列材料只作内部证据，不直接进入一般方法主张：

- 机器特定RSS、timing与非比较性性能日志；
- 纯路径调试输出与临时trace；
- 未登记解释角色的post-hoc比较；
- 超出冻结选择集的backend内部细节；
- 不具备跨实现意义的单机diagnostic。

例外：正式登记的12/60 backend sensitivity必须至少在正文或补充材料保留，不得以“内部实现细节”为由完全隐藏。
"""
write(PUB / "07_internal_only/internal_only_register.md", internal_only)

reviewer = """# Anticipated reviewer questions — evidence-locked answers

## 1. 为什么没有训练？

Stage 03D的完整多步AD/FD门未资格化，history为0/6；冻结路线规定Stage 03E authorization=false。因此训练未获授权且未执行。本文研究问题是资格链及梯度边界，不是训练性能。

## 2. 为什么NOT_QUALIFIED仍值得发表？

NOT_QUALIFIED本身不是论文价值的充分条件；价值来自预注册式合同、完整360-row公开、正负证据分层、mixed/unresolved归因和可复用的topology-event审计。正文不把失败包装成成功。

## 3. MMS是否构成物理验证？

不构成。D-R1只用于方程、源项与实现verification；无源independent validation由D-R3 oblique shear承担，D-R4仍缺失。

## 4. DOP853是否是真值？

不是连续方程真值。D-R2是同半离散系统的高精度时间参考，用于隔离时间推进误差，空间离散误差仍共享。

## 5. 144个失败是否说明实现错误？

不能直接这样判断。Stage 03C实现门通过，reverse/JVP 60/60也支持同后端AD一致；144个失败包含FD conditioning、接近结构零、固定图数值非光滑、方向不一致及19未决。总体结论仍是NOT_QUALIFIED，而不是“实现无误”或“求解器全部失败”。

## 6. 为什么topology组件可以单独PASS？

TE1使用独立合同检查birth/death、replay、fixed-side gradients、force jumps和empty graph。组件证据可独立满足，而固定拓扑多步梯度门仍失败；状态层级不同。

## 7. cutoff membership为何不可微？

edge membership由距离与cutoff的离散比较确定，crossing时图集合发生跳变。事件两侧分支可piecewise smooth，但edge存在性本身不是普通连续变量。

## 8. 为什么不切换attention backend后重跑？

这会改变冻结实现/AD合同并构成新的资格campaign。P1只报告既有48/60 match与12/60 sensitivity；统一后端或custom JVP属于未来新Stage 04假设。

## 9. 是否存在选择性报告？

没有。主文与图6同时显示216 PASS和144 failure，failure taxonomy包含19 unresolved；补充材料规划完整360 rows、2880 comparisons和2640 extended paths。

## 10. 方法能否推广到其他SPH实现？

当前不能声称已推广。可迁移的是合同结构与审计逻辑；数值一般性仍受单项目实现限制，需跨代码/问题族验证。

## 11. 是否达到CMAME的方法创新深度？

主题与meshless、fluid mechanics和physically based ML方向相容，但当前证据不支持“CMAME ready”。需要证明verification framework的跨实现一般性，并补足独立验证；当前分类为`METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION`。

## 12. 缺少性能对比是否致命？

对完整求解器论文是核心缺口；对严格定位的方法/验证论文，不必伪造性能结论，但必须把范围限定在verification architecture与negative gradient evidence，并避免暗示solver improvement。
"""
write(PUB / "09_reports/anticipated_reviewer_questions.md", reviewer)

readiness_report = """# Publication readiness v0.1

## Classification

`METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION`

辅分类：`TOPICALLY_COMPATIBLE_BUT_EVIDENCE_INCOMPLETE`。

## 当前最强项

- verification-first framework；
- conservative dynamic coupling与hard antisymmetric pair-force；
- zero-correction 288/288 bitwise equivalence；
- TE1 deterministic topology qualification；
- 完整透明的216/144 negative gradient evidence。

## 当前弱项

- no dynamic training；
- no autonomous rollout；
- no independent D-R4；
- single project implementation；
- limited cross-problem generality。

## Paper方向

Paper A（完整动态Transformer-corrected solver）为`NOT_READY`。Paper B是P1主稿方向；Paper C的backend、FD conditioning、history attenuation和piecewise topology作为边界分析吸收。Stage 03D NOT_QUALIFIED必须在摘要、结果与讨论中可见。

## CMAME边界

冻结Stage 03D-S评估认为主题与CMAME覆盖的meshless methods、fluid mechanics和physically based machine learning范围相容；但当前不能写`CMAME ready`。若以CMAME或同等级计算方法期刊为目标，需要增加跨实现方法深度、独立D-R4等价验证，以及训练/rollout性能证据。

## 三项核心缺口

1. 冻结训练协议下的正式动态训练资格；
2. 受控与自主rollout性能及稳定性；
3. 独立D-R4等价验证和跨问题泛化。
"""
write(PUB / "09_reports/publication_readiness_v0_1.md", readiness_report)

print(json.dumps({
    "status": "CONTENT_PACKAGE_BUILT",
    "claim_count": len(claim_rows),
    "figure_count": len(figure_plan_rows),
    "table_count": 6,
    "manuscript_characters": len(manuscript),
    "evidence_matrix_rows": len(evidence_matrix["rows"]),
}, ensure_ascii=False))
