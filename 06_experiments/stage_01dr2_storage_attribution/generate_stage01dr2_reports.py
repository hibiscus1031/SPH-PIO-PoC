"""Deterministic report renderer for completed Stage 01D-R2 evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_storage_attribution.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
REPORTS_ROOT = PROJECT_ROOT / "07_reports"
REPORT_PATHS = {
    "inventory": REPORTS_ROOT / "stage_01dr2_inventory_validation.md",
    "storage": REPORTS_ROOT / "stage_01dr2_storage_attribution.md",
    "edge": REPORTS_ROOT / "stage_01dr2_edge_count_correlation.md",
    "weakref": REPORTS_ROOT / "stage_01dr2_weakref_lifetime.md",
    "final": REPORTS_ROOT / "stage_01dr2_final_report.md",
}


def _read_csv(name: str) -> list[dict[str, str]]:
    with (RESULTS_ROOT / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_csv_optional(name: str) -> list[dict[str, str]]:
    path = RESULTS_ROOT / name
    return _read_csv(name) if path.exists() else []


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    header = list(headers)
    rendered = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        rendered.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(rendered)


def _bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _fmt_bytes(value: Any) -> str:
    number = float(value)
    return f"{number:,.0f} B ({number / 1.0e6:.3f} MB)"


def _freeze_text() -> str:
    target = subprocess.check_output(
        ("git", "rev-parse", "stage-01dr-resource-fail-live-bytes-gate^{}"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()
    return (
        "Stage 01D-R 诊断协议提交为 `0d562a4d8ed662c33797b738cd0f7ae9c00c1618`，"
        "最终证据提交为 `3f5d2d5033cfadd559cc278c4f828b40bc40d324`。"
        f"Annotated tag `stage-01dr-resource-fail-live-bytes-gate` target 为 `{target}`。"
        "旧状态 `RESOURCE_FAIL_LINEAR_GROWTH` 与 Stage 01D 的 `V2_FAIL` 均未修改。"
    )


def _evidence_index() -> str:
    candidates = [
        CONFIG_PATH,
        RESULTS_ROOT / "campaign_summary.json",
        RESULTS_ROOT / "inventory_validation_summary.csv",
        RESULTS_ROOT / "weakref_lifetime_summary.csv",
        RESULTS_ROOT / "fixed_topology_summary.csv",
        RESULTS_ROOT / "edge_working_set_models.csv",
        RESULTS_ROOT / "numerical_regression_summary.csv",
        RESULTS_ROOT / "attribution_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dr2_attribution_status.txt",
    ]
    rows = []
    for path in candidates:
        if not path.exists():
            continue
        rows.append((path.relative_to(PROJECT_ROOT).as_posix(), _sha256(path), path.stat().st_size))
    return _table(("path", "SHA-256", "bytes"), ((f"`{path}`", digest, size) for path, digest, size in rows))


def render_reports() -> dict[Path, str]:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    summary = _read_json(RESULTS_ROOT / "analysis_summary.json")
    inventory = _read_csv("inventory_validation_summary.csv")
    lifetime = _read_csv_optional("weakref_lifetime_summary.csv")
    fixed = _read_csv_optional("fixed_topology_summary.csv")
    models = _read_csv_optional("edge_working_set_models.csv")
    numerical = _read_csv_optional("numerical_regression_summary.csv")
    gates = _read_csv("attribution_gate_evidence.csv")
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    status = (RESULTS_ROOT / "stage01dr2_attribution_status.txt").read_text(encoding="utf-8").strip()

    inventory_table = _table(
        ("run", "iterations", "tensor Δ", "storage Δ", "fixture tensors", "unique storages", "PASS"),
        (
            (
                row["run_id"],
                row["iterations"],
                row["tensor_count_delta"],
                _fmt_bytes(row["unique_storage_bytes_delta"]),
                row["fixture_tensor_count"],
                row["fixture_unique_storage_count"],
                row["pass"],
            )
            for row in inventory
        ),
    )
    lifetime_table = _table(
        ("run", "GC checkpoints", "age-2 alive refs", "old storage count", "old bytes", "same-slot history", "PASS"),
        (
            (
                row["run_id"],
                row["gc_checkpoint_count"],
                row["maximum_age2_alive_tensor_reference_count"],
                row["maximum_old_survivor_storage_count"],
                _fmt_bytes(row["maximum_old_survivor_bytes"]),
                row["maximum_same_slot_multiple_generation_count"],
                row["pass"],
            )
            for row in lifetime
        ),
    )
    fixed_table = _table(
        ("run", "edges", "edge values", "tensor-count Δ", "unknown-byte Δ", "old-byte Δ", "PASS"),
        (
            (
                row["run_id"],
                row["directed_edge_count"],
                row["unique_directed_edge_counts"],
                row["live_tensor_count_delta"],
                _fmt_bytes(row["unknown_live_bytes_delta"]),
                _fmt_bytes(row["old_survivor_bytes_delta"]),
                row["pass"],
            )
            for row in fixed
        ),
    )
    model_table = _table(
        ("run", "β_edge B/edge", "β_step B/step", "β_step 95% CI", "γ_step B/step", "γ_step 95% CI", "PASS"),
        (
            (
                row["run_id"],
                f"{float(row['total_edge_coefficient']):.6f}",
                f"{float(row['total_step_coefficient']):.6f}",
                f"[{float(row['total_step_ci95_lower']):.6f}, {float(row['total_step_ci95_upper']):.6f}]",
                f"{float(row['unknown_step_coefficient']):.6f}",
                f"[{float(row['unknown_step_ci95_lower']):.6f}, {float(row['unknown_step_ci95_upper']):.6f}]",
                row["pass"],
            )
            for row in models
        ),
    )
    numerical_table = _table(
        ("run", "rows", "finite+bitwise", "max abs Δ", "PASS"),
        ((row["run_id"], row["rows"], row["bitwise_and_finite_rows"], row["maximum_absolute_difference"], row["pass"]) for row in numerical),
    )
    gate_table = _table(
        ("gate", "name", "passed", "observed", "required"),
        ((row["gate"], row["name"], row["passed"], row["observed"], row["required"]) for row in gates),
    )

    inventory_report = f"""# Stage 01D-R2 Tensor Inventory 自验证

## 冻结与目的

{_freeze_text()}

本报告只验证测量器；Control A 不调用 solver。固定 Tensor 集合包含 base、两个 view
和独立 storage，生产 inventory 连续调用 1000 次，每次删除局部结果、执行
`gc.collect()`，再进行独立轻量计数。

## 三次独立子进程结果

{inventory_table}

storage key 明确采用 `(device, data_ptr, nbytes)`；base 与 view 只计一次。
`inventory_results_globally_retained=false`，正式结果不保存 Tensor 对象或 storage。

## 判定

Inventory gate 为 **{'PASS' if summary['inventory_pass'] else 'FAIL'}**。
若该 gate 失败，协议要求停止 B/C/D 并选择 `INVENTORY_INSTRUMENTATION_BIAS`。
"""

    storage_report = f"""# Stage 01D-R2 Semantic Storage Attribution

## 语义 ledger

Ledger 在创建/返回边界显式登记 current state、current neighborhood、density/EOS、
pressure、viscosity、RK2 midpoint、diagnostics、archive、monitor 和 unknown；不按 shape
猜测。登记表仅保存 weakref 与标量元数据，storage 按 `(device, data_ptr, nbytes)` 去重。

每个稀疏检查点分别输出 `live_total_bytes`、`current_state_bytes`、
`current_edge_dependent_bytes`、`current_force_workspace_bytes`、`monitor_bytes`、
`unknown_live_bytes` 与 `old_survivor_bytes`。中点位置/速度通过不改变公式的临时
evaluation observer 在创建边界登记；冻结 integrator 源文件没有改动。

## 固定拓扑 B/C

{fixed_table}

## 生命周期与持有链

{lifetime_table}

明确持有链数量为 `{sum(int(row['explicit_referrer_chain_count']) for row in lifetime)}`。
本阶段记录 `retention_fix_applied={str(summary['retention_fix_applied']).lower()}`。
"""

    edge_report = f"""# Stage 01D-R2 Edge-count Correlation

## 模型与阈值

对每个 D run 拟合冻结模型：

`live_tensor_bytes = beta0 + beta_edge * edge_count + beta_step * step`

`unknown_live_bytes = gamma0 + gamma_edge * edge_count + gamma_step * step`

估计器为 Huber IRLS；每个模型使用 `{configuration['working_set_model']['bootstrap_samples']}`
次预登记 bootstrap。β_step 近零上限为
`{configuration['working_set_model']['adjusted_step_near_zero_absolute_bytes_per_step']}` B/step，
γ_step 上限为 `{configuration['working_set_model']['unknown_step_near_zero_absolute_bytes_per_step']}`
B/step，且两者 95% CI 均须包含 0。

## 结果

{model_table}

该多变量判定不会把 total live bytes 对 step 的一元正相关直接解释为 retention。
"""

    weakref_report = f"""# Stage 01D-R2 Weakref Lifetime

## 追踪协议

每个 accepted step 对旧 positions/velocities/densities/pressures、midpoint
positions/velocities/neighborhood、start/endpoint neighborhood 及 pressure/viscosity
结果建立 weakref。当前工作集 storage key 会从 old-survivor 集合中排除；age≥2 且
不属于当前 state/neighborhood/workspace 的存活 storage 才算真实旧对象。

## 结果

{lifetime_table}

稀疏 `gc.collect()` 后的 old-survivor gate 为
**{'PASS' if summary['lifetime_pass'] else 'FAIL'}**。只有确认 survivor 时才运行
脱敏 `gc.get_referrers()`；审计不输出对象内容、路径或局部变量值。
"""

    eligible = "具备提交下一轮审计、申请设计新 Stage 01D2 协议的资格" if summary["stage01d2_application_eligible"] else "不具备申请新 Stage 01D2 协议的资格"
    final_report = f"""# Stage 01D-R2 最终报告

## 1. Stage 01D-R 冻结

{_freeze_text()}

## 2. Gate G 为什么失败

Stage 01D-R 的 Gate G 在 N16/N32、A/B/C 六个组合中均观察到 3/3 次
live-tensor estimated bytes 正斜率，而 live tensor count、tracemalloc 与 GC tracked
objects 未同步增长。旧协议按预登记规则保守选择 `RESOURCE_FAIL_LINEAR_GROWTH`；R2
不改写该失败，只进一步区分当前工作集尺寸与历史 storage。

## 3. Tensor inventory 自验证

{inventory_table}

Inventory 自保留判定为 **{'PASS' if summary['inventory_pass'] else 'FAIL'}**。

## 4. Semantic storage ledger

所有 project-owned Tensor 均在可观察的创建/返回边界显式注册语义；每条明细包含
object id、data_ptr、nbytes、shape、stride、dtype、device、requires_grad、grad_fn、
view/base storage id 和 semantic slot。多个 view 共享的 storage 只计一次。

## 5. Weakref 生命周期

{lifetime_table}

## 6. A/B/C/D 控制

Control A 为 1000 次静态 inventory；B 为冻结 N32 state 的 1000 次 force evaluation；
C 为固定拓扑 zero-flow N32 1000 步；D 为冻结 TGV N32 1000 步、三次重复。
D 三次安全完成后按条件执行一次 2000-step 确认。Campaign 完成
`{campaign['observed_runs']}` 个独立子进程，全部回收=
`{campaign['all_observed_processes_reclaimed']}`。

## 7. Edge count 与 live-byte 相关性

{model_table}

## 8. Current working set 与 old survivor 分离

{fixed_table}

total live bytes 仅用于描述当前进程；真正 retention gate 只使用非当前、age≥2 的
old-survivor storage、相同语义槽的多代并存以及 unknown 的 edge-adjusted step 项。

## 9. 明确持有链

确认的直接持有链数量为
`{sum(int(row['explicit_referrer_chain_count']) for row in lifetime)}`；
`explicit_retention_detected={str(summary['explicit_retention_detected']).lower()}`。

## 10. 修复及 before/after

`retention_fix_applied=false`。没有明确持有链时不允许实施修复，因此本阶段没有
before/after 修复曲线，也没有修改 density、EOS、pressure、viscosity、RK2、dt、
H/dx、nu、c_s、layout 或第三方源码。

## 11. 数值回归

{numerical_table}

冻结 N32 step 0–4 的 positions、velocities、densities、pressures 使用 float64 bitwise
比较；numerical gate 为 **{'PASS' if summary['numerical_regression_pass'] else 'FAIL'}**。

## 12. 唯一归因状态

唯一状态为 **`{status}`**。

{gate_table}

## 13. Stage 01D2 申请资格

当前结论：**{eligible}**。即使具备资格，本阶段也没有创建或运行 Stage 01D2。

## 14. 历史失败状态保持

Stage 01D 仍为 **`V2_FAIL`**；Stage 01D-R 仍为
**`RESOURCE_FAIL_LINEAR_GROWTH`**。R2 归因不具追溯改写效力。

## 15. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 时间/空间收敛，未训练神经网络，
未实现 MLP、Transformer 或 attention。

## 证据索引

{_evidence_index()}
"""
    return {
        REPORT_PATHS["inventory"]: inventory_report,
        REPORT_PATHS["storage"]: storage_report,
        REPORT_PATHS["edge"]: edge_report,
        REPORT_PATHS["weakref"]: weakref_report,
        REPORT_PATHS["final"]: final_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_reports()
    if args.check:
        mismatches = []
        for path, text in rendered.items():
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                mismatches.append(path.name)
        if mismatches:
            raise SystemExit("REPORT_MISMATCH " + ",".join(mismatches))
        status = (RESULTS_ROOT / "stage01dr2_attribution_status.txt").read_text(encoding="utf-8").strip()
        print(f"CHECK_OK status={status} rendered=5 existing=5 matching=5")
        return 0
    for path, text in rendered.items():
        if path.exists():
            raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("rendered=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
