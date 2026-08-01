"""Render the five deterministic Stage 01D-P reports from scalar evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_resource_policy.yml"
REPORT_ROOT = PROJECT_ROOT / "07_reports"
REPORTS = {
    "horizon": REPORT_ROOT / "stage_01dp_evidence_horizon_audit.md",
    "canary": REPORT_ROOT / "stage_01dp_operational_canary.md",
    "subprocess": REPORT_ROOT / "stage_01dp_subprocess_policy.md",
    "policy": REPORT_ROOT / "stage_01dp_resource_policy.md",
    "final": REPORT_ROOT / "stage_01dp_final_report.md",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    header = list(headers)
    output = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    output.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(output)


def _evidence_index() -> str:
    paths = (
        CONFIG_PATH,
        RESULTS_ROOT / "campaign_summary.json",
        RESULTS_ROOT / "evidence_identity.csv",
        RESULTS_ROOT / "evidence_horizon.csv",
        RESULTS_ROOT / "canary_summary.csv",
        RESULTS_ROOT / "subprocess_audit.csv",
        RESULTS_ROOT / "policy_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dp_status.txt",
    )
    return _table(
        ("path", "SHA-256", "bytes"),
        ((f"`{path.relative_to(PROJECT_ROOT).as_posix()}`", _sha256(path), path.stat().st_size) for path in paths),
    )


def render_reports() -> dict[Path, str]:
    horizon = _read_csv(RESULTS_ROOT / "evidence_horizon.csv")
    identities = _read_csv(RESULTS_ROOT / "evidence_identity.csv")
    canaries = _read_csv(RESULTS_ROOT / "canary_summary.csv")
    processes = _read_csv(RESULTS_ROOT / "subprocess_audit.csv")
    gates = _read_csv(RESULTS_ROOT / "policy_gate_evidence.csv")
    analysis = _read_json(RESULTS_ROOT / "analysis_summary.json")
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    status = (RESULTS_ROOT / "stage01dp_status.txt").read_text(encoding="utf-8").strip()
    horizon_table = _table(
        ("source", "t_final", "minimum dt", "steps", "repeats", "pass"),
        ((row["source"], row["final_time"], row["minimum_dt"], row["trajectory_steps"], row["repeat_count"], row["pass"]) for row in horizon),
    )
    identity_table = _table(
        ("evidence", "expected SHA-256", "observed SHA-256", "pass"),
        ((row["evidence"], row["expected_sha256"], row["observed_sha256"], row["identity_pass"]) for row in identities),
    )
    canary_table = _table(
        ("run", "steps", "finite", "GC", "no_grad", "topology", "pair residual max", "viscous power max", "current RSS", "peak RSS", "RSS Δquartile", "RSS relative", "time ratio", "system avail min", "pass"),
        (
            (
                row["run_id"], row["completed_steps"], row["finite"], row["default_gc"], row["no_grad"], row["topology_pass"],
                f"{max(float(row['max_pressure_pair_residual']), float(row['max_viscosity_pair_residual'])):.3g}",
                f"{float(row['max_viscous_power']):.3g}", row["current_rss_bytes"], row["peak_rss_bytes"],
                f"{float(row['rss_quartile_increase_bytes']):.0f}", f"{float(row['rss_relative_increase']):.4f}",
                f"{float(row['step_time_ratio']):.4f}", f"{float(row['minimum_system_available_fraction']):.4f}", row["policy_gate_pass"],
            )
            for row in canaries
        ),
    )
    process_table = _table(
        ("run", "return", "PID", "reclaimed", "child RSS absent", "parent RSS growth", "scalar only", "summary"),
        ((row["run_id"], row["return_code"], row["pid"], row["process_reclaimed"], row["child_rss_absent"], row["parent_rss_growth_from_baseline_bytes"], row["scalar_summary_only"], f"`{row['summary_path']}`") for row in processes),
    )
    gate_table = _table(
        ("gate", "name", "passed", "observed", "required"),
        ((row["gate"], row["name"], row["passed"], row["observed"], row["required"]) for row in gates),
    )
    eligibility = (
        "具备提交下一轮审计、申请设计新 Stage 01D2 的资格"
        if analysis["stage01d2_design_application_eligible"]
        else "不具备申请设计 Stage 01D2 的资格"
    )
    freeze = (
        "R5 最终证据提交为 `f4262b71d1f5fb4763535a34e8187c1b1e02bcaa`；"
        "annotated tag `stage-01dr5-bounded-gc-delay-confirmed` target 为 "
        f"`{analysis['r5_tag_target']}`；状态 `R5_BOUNDED_GC_DELAY_CONFIRMED` 保持不变。"
    )
    policy_text = """正式运行政策固定为：每条轨迹一个独立子进程；默认 cyclic GC 启用；
前向处于 `torch.no_grad()`；不在时间循环中调用 `gc.collect()`，也不关闭 cyclic GC；
父进程不接收 Tensor、neighborhood 或完整 state；只保留标量 diagnostics 与相对证据路径；
轨迹结束即退出子进程；AD 检查必须使用另一短程进程。"""
    interpretation = """R5 表明 GC-disabled 路径线性累积，而默认 GC 的 2000-step 上包络有界。
本政策把资源安全裁决放在最大单轨迹能否在明确 RSS、时间、数值、拓扑及进程回收边界内完成，
不要求 retired count 每步为零、后半程必有全量归零，也不要求 live tensor 原始斜率严格为零。"""

    horizon_report = f"""# Stage 01D-P Evidence-horizon Audit

## R5 冻结

{freeze}

## 只读 SHA-256 复核

{identity_table}

## 步数计算与证据覆盖

明确计算：`0.2 / 0.000125 = 1600 steps`。

{horizon_table}

R5 default-GC 证据长度为 2000 steps，大于计划最大单轨迹 1600 steps；旧 R5 状态未重新计算。
"""
    canary_report = f"""# Stage 01D-P Maximum-horizon Operational Canary

三次 canary 均使用 N32、dt=1.25e-4、1600 steps、t_final=0.2、H/dx=5、c_s=20、nu=0.02、
regular layout、float64 CPU、默认 GC、`torch.no_grad()`与正常动态邻域重建。

{canary_table}

这些结果只用于运行政策验证；没有计算或输出收敛率、误差阶或 GCI，也不属于未来正式 V2 数据。
"""
    subprocess_report = f"""# Stage 01D-P Subprocess Policy Audit

{policy_text}

父进程顺序启动三个 canary：

{process_table}

campaign 汇总：process reclaimed=`{campaign['all_processes_reclaimed']}`，child RSS absent=
`{campaign['all_child_rss_absent']}`，scalar-only return=`{campaign['all_parent_returns_scalar_only']}`，
maximum parent RSS growth=`{campaign['maximum_parent_rss_growth_bytes']}` bytes。
"""
    policy_report = f"""# Stage 01D-P Resource Policy

## 运行解释

{interpretation}

## 冻结政策

{policy_text}

## 裁决门

{gate_table}

唯一状态为 **`{status}`**；{eligibility}。该资格不等于已设计或运行 Stage 01D2。
"""
    final_report = f"""# Stage 01D-P 最终报告

## 1. R5 冻结

{freeze}

## 2. 2000-step R5 证据与 1600-step 最大计划轨迹

{horizon_table}

最大计划步数由 `0.2 / 0.000125 = 1600` 明确得到；R5 default-GC horizon 为 2000。

## 3. 有界 GC 延迟的运行解释

{interpretation}

## 4. 正式子进程政策

{policy_text}

## 5. 三个 maximum-horizon canary

{canary_table}

## 6. RSS、运行时间、数值安全和拓扑

上表逐次记录 current/peak RSS、首末四分位 RSS、step-time 比率、系统可用内存、finite state、
pair-force residual、黏性功与拓扑门；判据完全来自预注册配置。

## 7. 子进程退出与资源回收

{process_table}

## 8. Canary 的证据边界

**本 canary 不属于 V2 收敛数据。** 未计算收敛率、误差阶或 GCI，也不得并入未来正式 V2 数据。

## 9. 唯一政策状态

唯一状态为 **`{status}`**。

{gate_table}

## 10. Stage 01D2 设计申请资格

当前结论：**{eligibility}**。Stage 01D2 未设计、未建立、未运行。

## 11. 历史状态

Stage 01D=`V2_FAIL`；Stage 01D-R=`RESOURCE_FAIL_LINEAR_GROWTH`；
Stage 01D-R2=`ATTRIBUTION_UNRESOLVED`；Stage 01D-R3=`R3_CONFIRMATION_UNRESOLVED`；
Stage 01D-R4=`R4_RETENTION_REDETECTED`；Stage 01D-R5=`R5_BOUNDED_GC_DELAY_CONFIRMED`。
全部保持不变。

## 12. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未训练神经网络或生成学习标签。

## 证据索引

{_evidence_index()}
"""
    return {
        REPORTS["horizon"]: horizon_report,
        REPORTS["canary"]: canary_report,
        REPORTS["subprocess"]: subprocess_report,
        REPORTS["policy"]: policy_report,
        REPORTS["final"]: final_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_reports()
    if args.check:
        mismatches = [path.name for path, text in rendered.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        if mismatches:
            raise SystemExit("REPORT_MISMATCH " + ",".join(mismatches))
        print("CHECK_OK rendered=5 existing=5 matching=5")
        return 0
    for path, text in rendered.items():
        if path.exists():
            raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    print("rendered=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
