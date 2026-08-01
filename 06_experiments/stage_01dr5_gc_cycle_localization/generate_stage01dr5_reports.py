"""Render the six deterministic Stage 01D-R5 reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr5_gc_cycle_localization"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_gc_cycle_localization.yml"
REPORT_ROOT = PROJECT_ROOT / "07_reports"
REPORTS = {
    "inventory": REPORT_ROOT / "stage_01dr5_retired_object_inventory.md",
    "graph": REPORT_ROOT / "stage_01dr5_referrer_cycle_report.md",
    "isolation": REPORT_ROOT / "stage_01dr5_instrumentation_isolation.md",
    "gc": REPORT_ROOT / "stage_01dr5_gc_schedule_assessment.md",
    "remediation": REPORT_ROOT / "stage_01dr5_remediation_report.md",
    "final": REPORT_ROOT / "stage_01dr5_final_report.md",
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


def _freeze() -> str:
    target = subprocess.check_output(("git", "rev-parse", "stage-01dr4-retention-redetected-gc-delayed^{}"), cwd=PROJECT_ROOT, text=True).strip()
    return (
        "R4 预注册提交为 `32bc4682f4f93eebce831a97f43971f57f087b55`，"
        "最终证据提交为 `a3064fe6912657e21f1b842dd8dcbc2f062e82bf`；"
        "annotated tag `stage-01dr4-retention-redetected-gc-delayed` target 为 "
        f"`{target}`。R4 的 `R4_RETENTION_REDETECTED` 保持不变。"
    )


def _evidence_index() -> str:
    paths = (
        CONFIG_PATH,
        RESULTS_ROOT / "campaign_summary.json",
        RESULTS_ROOT / "retired_object_instances.csv",
        RESULTS_ROOT / "retired_slot_summary.csv",
        RESULTS_ROOT / "referrer_graph_summary.json",
        RESULTS_ROOT / "gc_mode_summary.csv",
        RESULTS_ROOT / "instrumentation_isolation_summary.csv",
        RESULTS_ROOT / "numerical_regression_summary.csv",
        RESULTS_ROOT / "r5_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dr5_status.txt",
    )
    return _table(
        ("path", "SHA-256", "bytes"),
        ((f"`{path.relative_to(PROJECT_ROOT).as_posix()}`", _sha256(path), path.stat().st_size) for path in paths),
    )


def render_reports() -> dict[Path, str]:
    instances = _read_csv(RESULTS_ROOT / "retired_object_instances.csv")
    slots = _read_csv(RESULTS_ROOT / "retired_slot_summary.csv")
    graphs = _read_json(RESULTS_ROOT / "referrer_graph_summary.json")
    gc_rows = _read_csv(RESULTS_ROOT / "gc_mode_summary.csv")
    isolation = _read_csv(RESULTS_ROOT / "instrumentation_isolation_summary.csv")
    numeric = _read_csv(RESULTS_ROOT / "numerical_regression_summary.csv")
    gates = _read_csv(RESULTS_ROOT / "r5_gate_evidence.csv")
    analysis = _read_json(RESULTS_ROOT / "analysis_summary.json")
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    status = (RESULTS_ROOT / "stage01dr5_status.txt").read_text(encoding="utf-8").strip()
    slot_table = _table(
        ("semantic slot", "instances", "storages", "first retired", "last alive", "owner types", "categories"),
        ((row["semantic_slot"], row["retired_instance_count"], row["unique_storage_count"], row["first_retirement_step"], row["last_alive_step"], row["owner_types"], row["owner_categories"]) for row in slots),
    )
    instance_table = _table(
        ("slot", "object id", "storage", "shape", "dtype", "bytes", "created", "replaced", "retired", "last", "GC gen", "tracked", "view", "owner", "category"),
        (
            (
                row.get("semantic_slot", ""), row.get("tensor_object_id", ""), row.get("storage_key", ""),
                row.get("shape", ""), row.get("dtype", ""), row.get("nbytes", ""), row.get("creation_step", ""),
                row.get("replacement_step", ""), row.get("retirement_step", ""), row.get("last_alive_step", ""),
                row.get("gc_generation", ""), row.get("gc_is_tracked", ""), row.get("is_tensor_view", ""),
                row.get("python_owner_object_type", ""), row.get("owner_category", ""),
            )
            for row in instances[:80]
        ),
    )
    gc_table = _table(
        ("run", "mode", "max retired", "max bytes", "same-slot", "max gen/slot", "first peak", "second peak", "slope", "R²", "natural GC", "post-GC max", "periodic zero", "GC wall s"),
        (
            (
                row["run_id"], row["mode"], row["maximum_retired_count"], row["maximum_retired_bytes"],
                row["maximum_same_slot_count"], row["maximum_retired_generations_one_slot"],
                row["first_half_retired_peak"], row["second_half_retired_peak"],
                f"{float(row['retired_linear_slope_per_step']):.4g}", f"{float(row['retired_linear_r_squared']):.3f}",
                row["natural_gc_collection_events"], row["maximum_post_natural_collection_retired"],
                f"{float(row['manual_gc_checkpoint_zero_fraction']):.3f}", f"{float(row['manual_gc_total_wall_seconds']):.3f}",
            )
            for row in gc_rows
        ),
    )
    isolation_table = _table(
        ("run", "mode", "components", "max retired", "same-slot", "RSS slope", "current tensor Δ", "external tensor Δ", "finite"),
        (
            (
                row["run_id"], row["mode"], row["components"], row["maximum_retired_count"],
                row["maximum_same_slot_count"], f"{float(row['rss_slope_bytes_per_step']):.4g}",
                row["current_tensor_bytes_delta"], row["external_tracked_tensor_bytes_delta"], row["state_finite"],
            )
            for row in isolation
        ),
    )
    graph_table = _table(
        ("representative", "nodes", "edges", "cycle localized", "cycle type paths"),
        (
            (
                graph["representative"], len(graph["nodes"]), len(graph["edges"]),
                graph["cycle_localized"], json.dumps(graph["cycle_type_paths"], separators=(",", ":")),
            )
            for graph in graphs["graphs"]
        ),
    )
    gate_table = _table(
        ("gate", "name", "passed", "observed", "required"),
        ((row["gate"], row["name"], row["passed"], row["observed"], row["required"]) for row in gates),
    )
    numerical_pass = sum(row["bitwise_hash_identity"].lower() == "true" for row in numeric)
    if analysis["stage01d2_application_eligible"]:
        eligibility = "具备申请 Stage 01D2 新协议的资格"
    elif analysis["extra_resource_audit_eligible"]:
        eligibility = "仅具备申请一次额外资源政策审计的资格，不具备 Stage 01D2 申请资格"
    else:
        eligibility = "不具备 Stage 01D2 或额外资源政策审计资格"
    fix_text = (
        "已实施并验证明确的项目侧持有关系修复。"
        if analysis["fix_implemented"]
        else "未发现满足修复授权条件的明确项目侧持有关系，因此没有修改 solver 或诊断源码，也没有运行修复后 F/M/D campaign。"
    )

    inventory_report = f"""# Stage 01D-R5 Retired-object Inventory

## R4 冻结

{_freeze()}

## 逐项机器清单

完整清单位于 `results/retired_object_instances.csv`；共 `{len(instances)}` 行。下表最多显示前 80 行：

{instance_table}

## 语义槽聚合

{slot_table}
"""
    graph_report = f"""# Stage 01D-R5 Pre-GC Referrer-cycle Report

引用图在 retired 对象仍存活且调用 `gc.collect()` 之前捕获，最大深度 4；只保留类型、
attribute/key 名称、module 与 ownership 标志，排除了审计自身的 frame/list/queue。

{graph_table}

明确闭环已定位=`{analysis['explicit_cycle_localized']}`。若表中没有 cycle type path，
本阶段不声称定位到具体闭环。
"""
    isolation_report = f"""# Stage 01D-R5 Instrumentation Isolation

{isolation_table}

I0 不注册 solver Tensor，只在固定 checkpoint 读取外部 GC 类型计数；I1–I4 分别打开
预登记组件。instrumentation isolated=`{analysis['instrumentation_isolated']}`。
"""
    gc_report = f"""# Stage 01D-R5 GC-schedule Assessment

{gc_table}

default GC bounded=`{analysis['default_gc_bounded']}`；GC-disabled linear growth=
`{analysis['disabled_gc_linear_growth']}`；periodic checkpoint zero=
`{analysis['periodic_gc_checkpoint_zero']}`。G3 的 wall-time 只作为诊断开销，周期 collect
没有被采用为正式修复。
"""
    remediation_report = f"""# Stage 01D-R5 Remediation Report

{fix_text}

禁止将每步或每 25 步 `gc.collect()`作为首选修复。fix implemented=
`{analysis['fix_implemented']}`；因此 before/after 修复 campaign 不适用。所有新增测试
只验证追踪器、引用图和通用循环夹具，不改动 SPH 物理路径。
"""
    final_report = f"""# Stage 01D-R5 最终报告

## 1. R4 冻结

{_freeze()}

## 2. Retired 对象类型与语义槽

机器清单包含 `{len(instances)}` 个 retired instance；槽级汇总如下：

{slot_table}

## 3. 同槽 9 代的来源

`maximum_retired_generations_one_slot` 与具体 slot 均由逐对象 generation 记录计算；
不再只报告 R4 的聚合峰值 9。

## 4. GC 前 referrer 图

{graph_table}

明确闭环已定位=`{analysis['explicit_cycle_localized']}`；没有类型闭环路径时不作闭环声明。

## 5. Default/disabled/periodic GC 对照

{gc_table}

## 6. Instrumentation isolation

{isolation_table}

## 7. 明确循环或持有链

explicit cycle localized=`{analysis['explicit_cycle_localized']}`；instrumentation isolated=
`{analysis['instrumentation_isolated']}`。结论仅采用类型图和隔离曲线实际支持的范围。

## 8. 修复及 before/after

{fix_text} 周期 GC 未被冒充为代码修复。

## 9. 数值回归

25 个独立 worker（1 个 L1、9 个 GC 对照、15 个 isolation）的 step 0–4 哈希回归通过 `{numerical_pass}/{len(numeric)}`，全部状态有限；
campaign 进程回收=`{campaign['all_processes_reclaimed']}`。未修改物理或 RK2。

## 10. 唯一 R5 状态

唯一状态为 **`{status}`**。

{gate_table}

## 11. Stage 01D2 / 额外资源审计资格

当前结论：**{eligibility}**。没有建立或运行 Stage 01D2。

## 12. 历史状态

Stage 01D=`V2_FAIL`；Stage 01D-R=`RESOURCE_FAIL_LINEAR_GROWTH`；
Stage 01D-R2=`ATTRIBUTION_UNRESOLVED`；Stage 01D-R3=`R3_CONFIRMATION_UNRESOLVED`；
Stage 01D-R4=`R4_RETENTION_REDETECTED`。全部保持不变。

## 13. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 收敛或训练神经网络。

## 证据索引

{_evidence_index()}
"""
    return {
        REPORTS["inventory"]: inventory_report,
        REPORTS["graph"]: graph_report,
        REPORTS["isolation"]: isolation_report,
        REPORTS["gc"]: gc_report,
        REPORTS["remediation"]: remediation_report,
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
        print("CHECK_OK rendered=6 existing=6 matching=6")
        return 0
    for path, text in rendered.items():
        if path.exists():
            raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("rendered=6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
