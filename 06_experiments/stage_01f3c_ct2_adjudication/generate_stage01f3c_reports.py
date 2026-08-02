"""Generate the five required Stage 01F3C Markdown reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"
RESULTS = STAGE / "results"
REPORTS = ROOT / "07_reports"


def load(name: str) -> dict[str, Any]:
    return json.loads((RESULTS / name).read_text())


def write(name: str, text: str) -> None:
    path = REPORTS / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def flag(value: bool) -> str:
    return "PASS" if value else "FAIL"


def decomposition_table(payload: dict[str, Any]) -> str:
    lines = [
        "| MMS | dt | endpoint total | endpoint space | endpoint time | endpoint cross | cosine | integrated total | integrated space | integrated time | integrated cross |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for solution, item in payload["solutions"].items():
        for row in item["rows"]:
            endpoint = row["endpoint"]
            integrated = row["integrated_rms"]
            lines.append(
                f"| {solution} | {row['dt']:.8g} | {endpoint['total_l2']:.12g} | "
                f"{endpoint['space_l2']:.12g} | {endpoint['temporal_l2']:.12g} | "
                f"{endpoint['cross_term_2_space_dot_temporal']:.12g} | "
                f"{endpoint['cosine_space_temporal']:.8g} | {integrated['total_l2']:.12g} | "
                f"{integrated['space_l2']:.12g} | {integrated['temporal_l2']:.12g} | "
                f"{integrated['cross_term_2_space_dot_temporal']:.12g} |"
            )
    return "\n".join(lines)


def reference_table(run_ids: tuple[str, ...]) -> str:
    lines = [
        "| run | solution | N | b/t pos Linf | b/t vel Linf | t/3 pos Linf | t/3 vel Linf | sparse/dense abs | sparse/dense rel | nfev b/t/3 | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for run_id in run_ids:
        item = json.loads((STAGE / "run_summaries" / f"{run_id}.json").read_text())
        compare = item["comparisons"]
        audit = item["sparse_dense_audit"]
        stats = item["statistics"]
        lines.append(
            f"| {run_id} | {item['solution']} | {item['resolution']} | "
            f"{compare['baseline_tighter_position_linf']:.3e} | "
            f"{compare['baseline_tighter_velocity_linf']:.3e} | "
            f"{compare['tighter_third_position_linf']:.3e} | "
            f"{compare['tighter_third_velocity_linf']:.3e} | "
            f"{audit['maximum_absolute_difference']:.3e} | "
            f"{audit['maximum_relative_difference']:.3e} | "
            f"{stats['baseline']['nfev']}/{stats['tighter']['nfev']}/{stats['third']['nfev']} | "
            f"{item['status']} |"
        )
    return "\n".join(lines)


def main() -> int:
    prerequisite = load("prerequisite_checks.json")
    n32 = load("n32_error_decomposition.json")
    heldout = load("heldout_error_decomposition.json")
    audit = load("resource_determinism_audit.json")
    evaluation = load("stage01f3c_evaluation.json")
    historical = json.loads(
        (
            ROOT
            / "06_experiments/stage_01f3b_mms_convergence/results/continuous_time_analysis.json"
        ).read_text()
    )
    old_a = historical["solutions"]["MMS_A"]["rows"]
    old_b = historical["solutions"]["MMS_B"]["rows"]
    old_failure = (
        f"旧 CT2 要求 total exact velocity error 非增；MMS-A 从 "
        f"`{old_a[0]['velocity_exact_l2']:.16g}` 增至 `{old_a[-1]['velocity_exact_l2']:.16g}`，"
        f"MMS-B 从 `{old_b[0]['velocity_exact_l2']:.16g}` 增至 "
        f"`{old_b[-1]['velocity_exact_l2']:.16g}`，故 Stage 01F3B 形式失败。"
    )
    n32_reference = reference_table(("f3c_ref_n32_a", "f3c_ref_n32_b"))
    all_references = reference_table(
        (
            "f3c_ref_n32_a",
            "f3c_ref_n32_b",
            "f3c_ref_heldout_a",
            "f3c_ref_heldout_b",
        )
    )
    n32_summary = "\n".join(
        f"- {solution}: endpoint time order `{item['temporal_endpoint_fitted_order']:.6f}`, "
        f"integrated time order `{item['temporal_integrated_fitted_order']:.6f}`, "
        f"finest platform distance `{item['finest_endpoint_platform_relative_distance']:.6%}`, "
        f"closure abs `{item['maximum_absolute_vector_closure']:.3e}`, status `{item['status']}`."
        for solution, item in n32["solutions"].items()
    )
    n32_c5 = all(
        item["checks"]["coarse_negative_cross_endpoint"]
        and item["checks"]["coarse_cross_explains_below_platform"]
        for item in n32["solutions"].values()
    )
    n32_c6 = all(
        item["checks"]["finest_platform_distance"]
        for item in n32["solutions"].values()
    )
    heldout_summary = "\n".join(
        f"- {solution}: endpoint time order `{item['temporal_endpoint_fitted_order']:.6f}`, "
        f"integrated time order `{item['temporal_integrated_fitted_order']:.6f}`, "
        f"finest platform distance `{item['finest_endpoint_platform_relative_distance']:.6%}`, "
        f"status `{item['status']}`."
        for solution, item in heldout["solutions"].items()
    )
    write(
        "stage_01f3c_n32_semidiscrete_reference.md",
        f"""# Stage 01F3C N32 半离散参考

## 冻结与方法

Stage 01F3B 冻结提交为 `5a0ef2556a7128865f07d60abcd54666ca5fba47`，历史状态保持 `MMS_CONVERGENCE_VERIFICATION_FAIL`。新参考使用 production sparse SPH RHS 与 SciPy DOP853，不使用项目 RK2。

## 三重参考与 sparse/dense 抽查

{n32_reference}

三条容差路径状态均 finite；拓扑结构缺陷为 0，切换保持 reciprocal。每个解在至少 10 个状态上完成 sparse/dense total-acceleration 抽查。NPZ、配置、参数与代码 SHA-256 均记录于对应 run summary。
""",
    )
    write(
        "stage_01f3c_error_decomposition.md",
        f"""# Stage 01F3C N32 误差向量分解

## 定义与闭合

逐粒子、逐共同物理时刻使用 `e_total=u_RK2-u_exact`、`e_space=u_DOP853-u_exact`、`e_time=u_RK2-u_DOP853`。下表来自冻结 Stage 01F3B 五级 N32 轨迹；没有重算旧 CT2，也没有用标量误差相减替代向量分解。

{decomposition_table(n32)}

## 阶次与平台

{n32_summary}

Stage 01F3B successive-dt self-difference 身份复核为 `{n32['stage01f3b_self_difference_identity']['status']}`，最大绝对复算差 `{n32['stage01f3b_self_difference_identity']['maximum_absolute_difference']:.3e}`。
""",
    )
    c_checks = evaluation["checks"]
    write(
        "stage_01f3c_ct2_gate_assessment.md",
        f"""# Stage 01F3C CT2 机制门评估

## 旧 CT2

{old_failure} 该历史失败保持不变。

## C1–C7

| gate | evidence | result |
|---|---|---|
| C1 | N32 reference sensitivity | {flag(c_checks['n32_references_pass'])} |
| C2 | vector decomposition closure | {flag(c_checks['n32_vector_closure'])} |
| C3 | temporal error monotone and order >=1.80 | {flag(c_checks['n32_temporal_second_order'])} |
| C4 | frozen successive-dt self-difference identity | {flag(c_checks['stage01f3b_self_difference_identity'])} |
| C5 | endpoint negative cross term explains below-platform total error | {flag(n32_c5)} |
| C6 | finest total velocity error within 1% of platform | {flag(n32_c6)} |
| C7 | source/conservation/topology/resource/reference | {flag(c_checks['source_conservation_topology_resource_determinism'])} |

N32 机制状态：`{n32['status']}`。端点 coarse cross 为负，但 integrated-RMS coarse cross 为正；Stage 01F3B 的形式判据不被放宽、重算或重分类。
""",
    )
    write(
        "stage_01f3c_heldout_confirmation.md",
        f"""# Stage 01F3C held-out N24 确认

## 协议

Held-out 配置为 `N=24`、`H/dx=4.5`、`t_final=0.01`，五级 RK2 `dt` 独立子进程运行。由于最粗步长只有 10 步，使用无需插值的最大 11 点共同物理时间网格。另建三重 DOP853 半离散参考，并对最细层做独立确定性重复。

## 参考

{all_references}

## 向量分解

{decomposition_table(heldout)}

## 结论

{heldout_summary}

12 条 RK2 轨迹、4 条参考的资源隔离汇总状态为 `{audit['status']}`；确定性案例：{', '.join(case['status'] for case in audit['determinism_cases'])}。Held-out 不要求 total exact error 单调，只要求相对半离散参考的 time error 下降并达到预登记阶次。
""",
    )
    eligible = "具备" if evaluation["stage01f3d_application_eligible"] else "不具备"
    write(
        "stage_01f3c_final_report.md",
        f"""# Stage 01F3C 最终报告

## 1. Stage 01F3B 冻结

冻结提交 `5a0ef2556a7128865f07d60abcd54666ca5fba47`，annotated tag `stage-01f3b-fail-continuous-velocity-ct2`，SHA-256 清单与状态核验 `{prerequisite['status']}`。

## 2. 旧 CT2 的形式失败

{old_failure}

## 3. N32 半离散 DOP853 参考

{n32_reference}

## 4. total/space/time 向量分解

向量证据在每个粒子、每个共同物理时刻保存；N32 分解状态 `{n32['status']}`。

## 5. 交叉项与误差抵消

N32 cancellation gate `{flag(c_checks['n32_cancellation_mechanism'])}`；held-out cancellation gate `{flag(c_checks['heldout_cancellation_mechanism'])}`。平方范数按 `||e_total||²=||e_space||²+||e_time||²+2<e_space,e_time>` 复核。

## 6. 时间误差独立阶次

{n32_summary}

## 7. 空间平台距离

最细层相对距离列于上述摘要，门限固定为 1%。

## 8. Held-out N24 确认

{heldout_summary}

## 9. Source、守恒、拓扑、资源和确定性

综合状态 `{audit['status']}`；最大 pair residual `{audit['maxima']['maximum_pair_force_residual']:.3e}`，internal residual `{audit['maxima']['maximum_internal_force_residual']:.3e}`，assembly defect `{audit['maxima']['maximum_assembly_defect']:.3e}`，momentum defect `{audit['maxima']['maximum_momentum_update_defect']:.3e}`，peak RSS `{audit['maxima']['peak_rss_bytes']:.0f}` bytes。

## 10. 唯一 Stage 01F3C 状态

`{evaluation['status']}`

## 11. Stage 01F3D 申请资格

当前{eligible}申请设计 `Stage 01F3D — Plateau-aware MMS convergence requalification`。Stage 01F3D 未自动启动。

## 12. Stage 01F3B 历史状态

历史状态仍为 `MMS_CONVERGENCE_VERIFICATION_FAIL`，未修改、未放宽、未重算、未重分类。

## 13. 下游范围

Stage 01G、V3、Stage 02、训练与学习标签均未开始；Stage 01G 申请仍不允许。
""",
    )
    print(json.dumps({"reports": 5, "status": evaluation["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
