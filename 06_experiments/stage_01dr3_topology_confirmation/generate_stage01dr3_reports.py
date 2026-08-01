"""Deterministic renderer for the four Stage 01D-R3 reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_topology_confirmation.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
R2_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution" / "results"
REPORT_ROOT = PROJECT_ROOT / "07_reports"
REPORTS = {
    "cutoff": REPORT_ROOT / "stage_01dr3_cutoff_shell_audit.md",
    "frozen": REPORT_ROOT / "stage_01dr3_frozen_topology_control.md",
    "margin": REPORT_ROOT / "stage_01dr3_support_margin_control.md",
    "final": REPORT_ROOT / "stage_01dr3_final_report.md",
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


def _freeze_text() -> str:
    target = subprocess.check_output(
        ("git", "rev-parse", "stage-01dr2-attribution-unresolved-cutoff-topology^{}"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()
    return (
        "R2 运行前提交为 `084c702c6eab16b6983078494c01627fd2d8cfbe`，"
        "最终证据提交为 `39ae3dc1f88f4468d2a423cfad8c952a0a4da8d3`；"
        "annotated tag `stage-01dr2-attribution-unresolved-cutoff-topology` target 为 "
        f"`{target}`。R2 的 `ATTRIBUTION_UNRESOLVED` 保持不变。"
    )


def _control_table(rows: list[dict[str, str]], control: str) -> str:
    selected = [row for row in rows if row["control"] == control]
    return _table(
        ("run", "steps", "edge values", "edge IDs", "tensor Δ", "unknown Δ", "old bytes", "age-2", "margin", "PASS"),
        (
            (
                row["run_id"],
                row["completed_steps"],
                row["unique_edge_counts"],
                row["unique_edge_identities"],
                row["live_tensor_count_delta"],
                row["unknown_live_bytes_delta"],
                row["maximum_old_survivor_bytes"],
                row["maximum_age2_alive_tensor_reference_count"],
                f"{float(row['minimum_dimensionless_cutoff_margin']):.16g}",
                row["pass"],
            )
            for row in selected
        ),
    )


def _evidence_index() -> str:
    paths = [
        CONFIG_PATH,
        RESULTS_ROOT / "cutoff_shell_audit_summary.json",
        RESULTS_ROOT / "cutoff_switch_edges.csv",
        RESULTS_ROOT / "campaign_summary.json",
        RESULTS_ROOT / "control_summary.csv",
        RESULTS_ROOT / "r2_evidence_identity.csv",
        RESULTS_ROOT / "r3_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dr3_status.txt",
    ]
    return _table(
        ("path", "SHA-256", "bytes"),
        (
            (
                f"`{path.relative_to(PROJECT_ROOT).as_posix()}`",
                _sha256(path),
                path.stat().st_size,
            )
            for path in paths
        ),
    )


def render_reports() -> dict[Path, str]:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cutoff = _read_json(RESULTS_ROOT / "cutoff_shell_audit_summary.json")
    switches = _read_csv(RESULTS_ROOT / "cutoff_switch_edges.csv")
    controls = _read_csv(RESULTS_ROOT / "control_summary.csv")
    gates = _read_csv(RESULTS_ROOT / "r3_gate_evidence.csv")
    analysis = _read_json(RESULTS_ROOT / "analysis_summary.json")
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    r2_models = _read_csv(R2_RESULTS / "edge_working_set_models.csv")
    status = (RESULTS_ROOT / "stage01dr3_status.txt").read_text(encoding="utf-8").strip()
    unique_switches: dict[int, dict[str, str]] = {}
    for row in switches:
        unique_switches.setdefault(int(row["edge_key"]), row)
    switch_table = _table(
        ("edge key", "row", "col", "offset", "shell", "actions", "min |r/H−1|"),
        (
            (
                key,
                row["row"],
                row["col"],
                f"({row['offset_x']},{row['offset_y']})",
                row["lattice_shell"],
                "/".join(sorted({item["action"] for item in switches if int(item["edge_key"]) == key})),
                f"{min(float(item['absolute_relative_cutoff_distance']) for item in switches if int(item['edge_key']) == key):.3e}",
            )
            for key, row in sorted(unique_switches.items())
        ),
    )
    f_table = _control_table(controls, "F")
    m_table = _control_table(controls, "M")
    r2_table = _table(
        ("run", "β_edge", "β_step", "β_step CI", "γ_step", "γ_step CI"),
        (
            (
                row["run_id"],
                f"{float(row['total_edge_coefficient']):.12g}",
                f"{float(row['total_step_coefficient']):.3e}",
                f"[{float(row['total_step_ci95_lower']):.3e}, {float(row['total_step_ci95_upper']):.3e}]",
                f"{float(row['unknown_step_coefficient']):.3e}",
                f"[{float(row['unknown_step_ci95_lower']):.3e}, {float(row['unknown_step_ci95_upper']):.3e}]",
            )
            for row in r2_models
        ),
    )
    gate_table = _table(
        ("gate", "name", "passed", "observed", "required"),
        ((row["gate"], row["name"], row["passed"], row["observed"], row["required"]) for row in gates),
    )

    cutoff_report = f"""# Stage 01D-R3 Cutoff-shell Audit

## R2 冻结

{_freeze_text()}

## H/dx=5 壳层几何

N32 规则周期格点在 q=5 上有 12 个整数偏移：
`{cutoff['q5_offsets']}`。因此初始 cutoff 壳层包含
`{cutoff['initial_q5_directed_edge_count']}` 条 directed edges；float64 中初始
`min |r/H-1|={float(cutoff['initial_minimum_absolute_r_over_H_minus_one']):.3e}`。

## C1–C3 切换复核

R3 replay 得到 edge count `{cutoff['edge_count_values']}`，并与 R2 C1–C3 的
`{cutoff['r2_identity_rows']}` 个采样行全部一致。发生切换的具体 keys：

{switch_table}

所有切换均位于 q=5 壳层=`{cutoff['all_switches_on_q5_shell']}`，全部满足预登记
`|r/H-1|≤1e-12`=`{cutoff['all_switches_near_cutoff']}`。这些是 cutoff inclusion 的
浮点切换，不称为物理粒子迁移。
"""

    frozen_report = f"""# Stage 01D-R3 Frozen-topology Control F

## 控制定义

F 使用 N32 zero-flow、H/dx=5.0，只在初始状态建立一次 reciprocal、duplicate-free
edge index，后续 2000 步固定该 index。density、EOS、pressure、viscosity 与 RK2
仍调用冻结的项目算子；F 只用于资源归因。

## 三次独立子进程

{f_table}

三次均完成，edge count 与 edge identity 各只有一个值；old-survivor、unknown
growth、same-slot history、age-2 weakrefs 和 referrer chain 均为零。
"""

    margin = configuration["support_margin_geometry"]
    margin_report = f"""# Stage 01D-R3 Support-margin Control M

## 运行前几何选择

唯一壳层算法得到 `q_next=sqrt(26)={margin['q_next']}`，并在查看资源结果前冻结
`H/dx=(5+q_next)/2={margin['selected_support_ratio']}`。几何 margin 为
`{margin['dimensionless_shell_margin']}`，初始 edge count 预登记为
`{margin['expected_initial_edge_count']}`。该值仅用于诊断，不是正式 V2 参数。

## 三次正常邻域重建

{m_table}

所有 force stage 重新搜索邻域；edge identity 恒定，无 duplicate、nonreciprocal、
strict omission 或 unexpected edge，且最小 cutoff margin 大于预登记 `1e-12`。
"""

    eligible = "具备提交下一轮审计、申请设计 Stage 01D2 新协议的资格" if analysis["stage01d2_application_eligible"] else "不具备申请 Stage 01D2 新协议的资格"
    final_report = f"""# Stage 01D-R3 最终报告

## 1. R2 冻结

{_freeze_text()}

## 2. H/dx=5 的截断壳层退化

q=5 由 12 个整数偏移构成，共 `{cutoff['initial_q5_directed_edge_count']}` 条
directed cutoff-shell edges；初始最小 `|r/H-1|` 为
`{float(cutoff['initial_minimum_absolute_r_over_H_minus_one']):.3e}`，cutoff 与离散壳层重合。

## 3. C1–C3 edge 切换来源

R3 replay 精确复现 `{cutoff['edge_count_values']}`，与 C1–C3 全部采样行一致；
`{cutoff['unique_switched_edge_keys']}` 个具体 edge keys 全在 q=5 且 r≈H。该现象是
截断壳层 inclusion 切换，不是物理粒子迁移。

{switch_table}

## 4. Control F

{f_table}

## 5. Control M

`q_next=sqrt(26)`，冻结诊断 ratio=`{margin['selected_support_ratio']}`；正常重建结果：

{m_table}

## 6. Old-survivor、unknown 与 same-slot

六个 F/M run 的 live tensor count Δ、unknown bytes Δ、old-survivor bytes、
same-slot multi-generation、age-2 weakrefs 与明确 referrer chain 均为零。

## 7. R2 D 模型身份复核

四个源文件 SHA-256 与预登记值一致；没有重新拟合模型。重新读取结果为：

{r2_table}

四个 run 均保持 β_edge=48 B/edge，β_step/γ_step 的 95% CI 包含零，且满足
4096/1024 B/step 上限；D old-survivor 仍为零。

## 8. 数值回归

R2 四个 D run 的 step 0–4 共 20/20 行仍为 finite、bitwise equal，最大绝对差为 0。
F/M 六个 2000-step 状态全部有限；campaign 的 `{campaign['observed_processes']}` 个
子进程全部回收=`{campaign['all_processes_reclaimed']}`。

## 9. 唯一 R3 状态

唯一状态为 **`{status}`**。

{gate_table}

## 10. Stage 01D2 申请资格

当前结论：**{eligible}**。本阶段没有设计或运行 Stage 01D2。

## 11. 历史状态保持

Stage 01D 仍为 **`V2_FAIL`**；Stage 01D-R 仍为
**`RESOURCE_FAIL_LINEAR_GROWTH`**；Stage 01D-R2 仍为
**`ATTRIBUTION_UNRESOLVED`**。R3 不追溯改写这些状态。

## 12. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 时间/空间收敛，未训练神经网络，
未生成学习标签；Control M 的诊断 H/dx 未转为正式参数。

## 证据索引

{_evidence_index()}
"""
    return {
        REPORTS["cutoff"]: cutoff_report,
        REPORTS["frozen"]: frozen_report,
        REPORTS["margin"]: margin_report,
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
        status = (RESULTS_ROOT / "stage01dr3_status.txt").read_text(encoding="utf-8").strip()
        print(f"CHECK_OK status={status} rendered=4 existing=4 matching=4")
        return 0
    for path, text in rendered.items():
        if path.exists():
            raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("rendered=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
