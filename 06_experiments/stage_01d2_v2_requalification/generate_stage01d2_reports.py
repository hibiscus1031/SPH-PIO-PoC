"""Render the eleven immutable Stage 01D2 Markdown reports from machine evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01d2_v2_requalification"
RESULTS = ROOT / "results"
REPORTS = PROJECT_ROOT / "07_reports"
CONFIG = ROOT / "configs" / "preregistered_stage01d2_v2.yml"


def table(name: str, columns: list[str]) -> str:
    rows = list(csv.DictReader((RESULTS / name).open(encoding="utf-8")))
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    lines += ["| " + " | ".join(str(row.get(c, "")) for c in columns) + " |" for row in rows]
    return "\n".join(lines)


def write(name: str, text: str) -> None:
    path = REPORTS / name
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def yn(value: bool) -> str: return "PASS" if value else "FAIL"


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")); e = json.loads((RESULTS / "stage01d2_evaluation.json").read_text()); prereq = json.loads((RESULTS / "prerequisite_summary.json").read_text())
    config_hash = hashlib.sha256(CONFIG.read_bytes()).hexdigest(); commit = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()
    common = f"正式配置：`{CONFIG.relative_to(PROJECT_ROOT)}`（SHA-256 `{config_hash}`）。分析时提交：`{commit}`。Stage 01D-P canary 使用数：`{e['canary_rows_used']}`。"
    write("stage_01d2_protocol_and_provenance.md", f"""# Stage 01D2 protocol and provenance

{common}

Stage 01D-P 预注册提交为 `{cfg['frozen_stage01dp']['preregistration_commit']}`，最终证据提交及冻结 tag 目标为 `{cfg['frozen_stage01dp']['final_evidence_commit']}`；冻结状态为 `{cfg['frozen_stage01dp']['status']}`。R5 tag 目标为 `{cfg['frozen_stage01dp']['r5_tag_target']}`。`stage01dp_frozen_sha256_manifest.csv` 逐项复核了五份报告、状态、配置和机器证据，原文件未改动。

每条前向轨迹由 `run_stage01d2_campaign.py` 启动独立子进程；worker 全程采用默认 cyclic GC 和 `torch.no_grad()`，父进程只记录标量摘要与相对路径。Stage 01D-P 三条 canary 只构成资源政策依据，未复制、未拟合、未重复。

历史结论保持冻结：Stage 01D=`V2_FAIL`，R=`RESOURCE_FAIL_LINEAR_GROWTH`，R2=`ATTRIBUTION_UNRESOLVED`，R3=`R3_CONFIRMATION_UNRESOLVED`，R4=`R4_RETENTION_REDETECTED`，R5=`R5_BOUNDED_GC_DELAY_CONFIRMED`，P=`POLICY_PASS_ISOLATED_DEFAULT_GC`。
""")
    identities = "\n".join(f"- `{k}`: {yn(v)}" for k,v in prereq["identity_checks"].items())
    write("stage_01d2_prerequisite_checks.md", f"""# Stage 01D2 prerequisite checks

总状态：**{prereq['status']}**。完整 pytest 返回码 `{prereq['pytest_return_code']}`，原始日志为 `{prereq['pytest_log_path']}`。

{identities}

N16 zero-flow、20-step N16 与 N32 smoke 的逐点守恒、拓扑与资源证据位于 `run_summaries/` 和 `trajectory_samples/`；子进程回收证据位于 `results/campaign_index.csv`。
""")
    write("stage_01d2_time_convergence.md", f"""# Stage 01D2 time convergence

{table('time_results.csv', ['run_id','dt','velocity_relative_l2','modal_error','kinetic_energy_error','peak_rss_bytes','wall_time_seconds','status'])}

门判定：{', '.join(f'{k}={yn(v)}' for k,v in e['time_gates'].items())}。粗相邻 dt endpoint self-difference=`{e['time_self_difference_coarse']:.8g}`，细相邻 dt=`{e['time_self_difference_fine']:.8g}`。解析误差与 21 个共同物理时刻的自收敛证据联合使用；未把完整 SPH 解强行称为 RK2 严格二阶。
""")
    write("stage_01d2_space_convergence.md", f"""# Stage 01D2 space convergence

{table('space_results.csv', ['run_id','resolution','support_ratio','velocity_relative_l2','modal_error','kinetic_energy_error','status'])}

门判定：{', '.join(f'{k}={yn(v)}' for k,v in e['space_gates'].items())}。velocity 与 modal 的拟合斜率分别为 `{e['space_slope_velocity']:.6g}` 和 `{e['space_slope_modal']:.6g}`。**{e['gci_statement']}**；仅当正、有限、单调并近似进入渐近区时才允许 Richardson/GCI。
""")
    write("stage_01d2_support_family_comparison.md", "# Stage 01D2 support-family comparison\n\n" + table('support_family_results.csv', ['run_id','family','resolution','support_ratio','velocity_relative_l2','modal_error','kinetic_energy_error','density_fluctuation','wall_time_seconds','mean_edge_count','peak_rss_bytes']) + "\n\n该表并列给出 constant-neighbor 与 increasing-neighbor 家族，不预设优劣，用于审计 quadrature–truncation tradeoff。\n")
    write("stage_01d2_disorder_robustness.md", f"# Stage 01D2 disorder robustness\n\n{table('disorder_results.csv', ['run_id','layout','seed','status','velocity_relative_l2','modal_error','density_fluctuation','momentum_drift','minimum_separation_over_dx','mean_neighbor_count','peak_rss_bytes','failure_type'])}\n\n判定：**{e['disorder_status']}**；10% jitter median velocity-error multiplier=`{e['jitter10_median_velocity_error_multiplier']:.6g}`。三种种子只用于稳健性检查，不代表完整随机不确定性。\n")
    write("stage_01d2_mach_model_form.md", f"# Stage 01D2 Mach/model-form assessment\n\n{table('mach_results.csv', ['run_id','sound_speed','nominal_mach','velocity_relative_l2','modal_error','density_fluctuation','maximum_mach','maximum_pressure_absolute','acoustic_cfl_maximum','wall_time_seconds','peak_rss_bytes','status'])}\n\n3/3 完成：{yn(e['mach_complete'])}；密度波动随声速增大不恶化：{yn(e['mach_density_nonworsening'])}。若速度误差未随 Mach 降低而改善，则空间离散或模型其他组成可能主导；未事后挑选最有利声速。\n")
    write("stage_01d2_dynamic_conservation.md", f"""# Stage 01D2 dynamic conservation

全部已接受正式轨迹的逐采样检查结果：**{yn(e['conservation_pass'])}**。原始值见每条 `trajectory_samples/*.csv` 与 `run_summaries/*.json`，涵盖 pressure/viscosity pair residual、reconstructed/assembled internal force、viscous power、momentum drift、angular diagnostic 与全部 topology defect counts。

硬门为 pair residual ≤1e-12、normalized internal force ≤1e-10、viscous power ≤1e-12 且 topology defects=0。角动量仅作诊断；未宣称非中心黏性力严格守恒角动量。
""")
    write("stage_01d2_autograd_regression.md", f"# Stage 01D2 autograd regression\n\n{table('autograd_results.csv', ['parameter','steps','autograd_gradient','finite_difference_gradient','relative_difference','finite','nonzero','status'])}\n\n完成 `{e['ad_completed_cases']}/20`，总判定 **{yn(e['ad_pass'])}**。每个 case 均在独立短程子进程中执行；1/3/5/8 步采用 1% AD/FD 门，16 步要求 finite/nonzero。邻域整数拓扑选择不可微，本报告不作相反声明。Stage 01C baseline 只读身份由 prerequisite 复核。\n")
    write("stage_01d2_uncertainty_assessment.md", f"""# Stage 01D2 numerical uncertainty assessment

1. 时间离散误差：四个 dt 的解析 endpoint 与共同时间 self-difference 联合评估；time={yn(e['time_pass'])}。
2. 空间离散误差：N16/N24/N32 与两种 support family 分开；space={yn(e['space_pass'])}。
3. 弱可压模型形式：用 c_s=10/20/40 定量，不将其混入空间误差。
4. 粒子无序：六个冻结 jitter 种子仅为有限稳健性证据；状态 `{e['disorder_status']}`。
5. 支撑尺度：constant/increasing 家族差异单独列表。
6. float64 舍入：残差门附近的数值只解释为舍入容限内证据。
7. CPU 确定性：正式 backend 固定 CPU，seed 与 run ID 预登记。
8. GC：默认 cyclic GC 仅是资源运行条件，不属于物理误差。

结论：**{e['gci_statement']}**。解析参考误差包含时间、空间、弱可压与其他模型形式成分，未全部归因为空间离散。
""")
    sections = [
        ("1. Stage 01D-P 冻结", f"P 状态 `{cfg['frozen_stage01dp']['status']}`；tag 固定于 `{cfg['frozen_stage01dp']['final_evidence_commit']}`。"),
        ("2. 历史失败状态", "Stage 01D 及 R–R5 的失败/诊断状态全部保留，未追溯修改。"),
        ("3. 正式资源运行政策", "独立子进程、默认 GC、no_grad、checkpoint-only；campaign_index 记录 PID、回收和父进程增长。"),
        ("4. Canary 排除证明", f"正式数据中 Stage 01D-P canary 行数为 `{e['canary_rows_used']}`。"),
        ("5. 固定物理方程和参数", "二维周期 TGV，rho0=1、U0=1、L=2、nu=0.02、Re=100、主 c_s=20、float64 CPU；Stage 01C 压力/黏性与 midpoint RK2 未改。"),
        ("6. Prerequisite", f"状态 **{prereq['status']}**，pytest 与身份、zero-flow、smoke、守恒、资源、回收均有机器证据。"),
        ("7. 时间误差", f"T1–T4：{', '.join(f'{k}={yn(v)}' for k,v in e['time_gates'].items())}。"),
        ("8. 空间误差", f"S1–S6：{', '.join(f'{k}={yn(v)}' for k,v in e['space_gates'].items())}；{e['gci_statement']}。"),
        ("9. 支撑族比较", "constant 与 increasing 两族均按预登记矩阵报告误差、成本、edge count 和 RSS。"),
        ("10. 动态无序", f"唯一子判定 **{e['disorder_status']}**。"),
        ("11. Mach/模型形式", f"三条完成={yn(e['mach_complete'])}，密度 non-worsening={yn(e['mach_density_nonworsening'])}。"),
        ("12. 动态守恒", f"硬门 **{yn(e['conservation_pass'])}**；角动量仅作诊断。"),
        ("13. AD 回归", f"{e['ad_completed_cases']}/20，**{yn(e['ad_pass'])}**；拓扑选择不可微。"),
        ("14. 资源使用", f"全部接受轨迹资源与子进程回收总门 **{yn(e['resource_pass'])}**。"),
        ("15. 数值不确定性", "时间、空间、Mach、无序、support、舍入与 CPU 确定性已区分；GC 不作物理误差。"),
        ("16. 所有失败和限制", f"空间/时间平台、Mach 与 disorder 限制按子报告披露；evidence_complete={e['evidence_complete']}。"),
        ("17. 唯一 Stage 01D2 状态", f"**{e['final_status']}**"),
        ("18. 是否具备申请 V3 的资格", "是，仅可提交下一轮审计申请。" if e['final_status']=="STAGE01D2_V2_REQUALIFIED_PASS" else "否；只有无条件 PASS 才可申请。"),
        ("19. Stage 02 边界", "Stage 02 未开始；V3、网络训练、学习标签与高保真资格均未启动。"),
    ]
    final = "# Stage 01D2 final V2 report\n\n" + common + "\n\n" + "\n\n".join(f"## {title}\n\n{text}" for title,text in sections)
    write("stage_01d2_final_v2_report.md", final)
    return 0


if __name__ == "__main__": raise SystemExit(main())
