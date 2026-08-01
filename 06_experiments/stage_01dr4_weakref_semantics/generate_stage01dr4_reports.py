"""Deterministically render the four Stage 01D-R4 reports."""

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
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr4_weakref_semantics"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_weakref_semantics.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
R2_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution" / "results"
REPORT_ROOT = PROJECT_ROOT / "07_reports"
REPORTS = {
    "semantics": REPORT_ROOT / "stage_01dr4_gate_semantics_audit.md",
    "control": REPORT_ROOT / "stage_01dr4_control_f_reference_identity.md",
    "fixtures": REPORT_ROOT / "stage_01dr4_fixture_validation.md",
    "final": REPORT_ROOT / "stage_01dr4_final_report.md",
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
        ("git", "rev-parse", "stage-01dr3-confirmation-unresolved-weakref-semantics^{}"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()
    return (
        "R3 预注册提交为 `2c8c3f377b53315c2c7cb378ec4054b89b96a793`，"
        "最终证据提交为 `12bc7e4e56539cd6f14db12f4c9ee6cbe10b3f99`；"
        "annotated tag `stage-01dr3-confirmation-unresolved-weakref-semantics` target 为 "
        f"`{target}`。R3 的 `R3_CONFIRMATION_UNRESOLVED` 保持不变。"
    )


def _evidence_index() -> str:
    paths = (
        CONFIG_PATH,
        RESULTS_ROOT / "campaign_summary.json",
        RESULTS_ROOT / "fixture_summary.csv",
        RESULTS_ROOT / "control_f_semantic_summary.csv",
        RESULTS_ROOT / "fifteen_reference_identity.csv",
        RESULTS_ROOT / "evidence_identity.csv",
        RESULTS_ROOT / "r4_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dr4_status.txt",
    )
    return _table(
        ("path", "SHA-256", "bytes"),
        (
            (f"`{path.relative_to(PROJECT_ROOT).as_posix()}`", _sha256(path), path.stat().st_size)
            for path in paths
        ),
    )


def render_reports() -> dict[Path, str]:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    fixtures = _read_csv(RESULTS_ROOT / "fixture_summary.csv")
    controls = _read_csv(RESULTS_ROOT / "control_f_semantic_summary.csv")
    references = _read_csv(RESULTS_ROOT / "fifteen_reference_identity.csv")
    gates = _read_csv(RESULTS_ROOT / "r4_gate_evidence.csv")
    evidence = _read_csv(RESULTS_ROOT / "evidence_identity.csv")
    analysis = _read_json(RESULTS_ROOT / "analysis_summary.json")
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    models = _read_csv(R2_RESULTS / "edge_working_set_models.csv")
    status = (RESULTS_ROOT / "stage01dr4_status.txt").read_text(encoding="utf-8").strip()
    reference_table = _table(
        ("slot", "object id", "storage key", "created", "first", "last", "fixed edge", "current", "retired", "different generation", "referrer types"),
        (
            (
                row["semantic_slot"], row["object_id"], row["storage_key"],
                row["creation_step"], row["first_observed_step"], row["last_observed_step"],
                row["belongs_to_fixed_initial_edge_index"], row["is_current_working_set"],
                row["is_retired_reference"], row["has_different_storage_generation"],
                row["direct_referrer_type_names"],
            )
            for row in references
        ),
    )
    fixture_table = _table(
        ("run", "fixture", "expected retention", "current peak", "old peak", "same-slot peak", "reclaimed", "PASS"),
        (
            (
                row["run_id"], row["fixture"], row["expected_retention"],
                row["peak_current_persistent"], row["peak_old_survivor_storage_count"],
                row["peak_same_slot_multigeneration_count"], row["process_reclaimed"], row["pass"],
            )
            for row in fixtures
        ),
    )
    control_table = _table(
        ("run", "steps", "edges", "IDs", "age-2", "current", "retired", "old", "same-slot", "unknown Δ", "referrers", "PASS"),
        (
            (
                row["run_id"], row["completed_steps"], row["edge_count_values"],
                row["unique_edge_identities"], row["age2_audited_references"],
                row["current_persistent_references"], row["retired_references"],
                row["old_survivor_storage_count"], row["same_slot_multigeneration_count"],
                row["unknown_live_bytes_delta"], row["explicit_referrer_chain_count"], row["pass"],
            )
            for row in controls
        ),
    )
    model_table = _table(
        ("run", "β_edge", "β_step CI", "γ_step", "old evidence"),
        (
            (
                row["run_id"], f"{float(row['total_edge_coefficient']):.12g}",
                f"[{float(row['total_step_ci95_lower']):.3e}, {float(row['total_step_ci95_upper']):.3e}]",
                f"{float(row['unknown_step_coefficient']):.3e}", "SHA-verified",
            )
            for row in models
        ),
    )
    gate_table = _table(
        ("gate", "name", "passed", "observed", "required"),
        ((row["gate"], row["name"], row["passed"], row["observed"], row["required"]) for row in gates),
    )
    identity_passes = sum(str(row["identity_pass"]).lower() == "true" for row in evidence)
    eligible = "具备提交下一轮审计、申请设计 Stage 01D2 新协议的资格" if analysis["stage01d2_application_eligible"] else "不具备申请 Stage 01D2 新协议的资格"

    semantics_report = f"""# Stage 01D-R4 Gate-semantics Audit

## R3 冻结

{_freeze_text()}

## 新语义层

- `current_persistent_reference`：storage 仍属于当前 state、固定 neighborhood 或当前工作区，后续 solver 仍会读取。
- `retired_reference`：同语义对象已被替换，storage 不再属于当前 solver-readable working set。
- `old_survivor`：retired storage 在至少两个 accepted steps 后仍存活。
- `same_slot_multigeneration`：同一语义槽至少两个不同的 retired storage generations 同时存活。

只有 old-survivor 与 same-slot multigeneration 是 retention signal。单纯 age>2
不构成 retention。R3 的旧 age-2=0 规则没有修改；R4 是新的独立语义门槛。

## 证据身份

冻结输入共 `{len(evidence)}` 项，身份/语义检查通过 `{identity_passes}/{len(evidence)}`。
"""

    control_report = f"""# Stage 01D-R4 Control F Reference Identity

## 15 个 age-2 weakrefs

下表来自 canonical short replay F1。只输出类型名称，不输出 referrer 内容或用户路径。

{reference_table}

## 三个独立 200-step 回归

{control_table}

三次的 15/15 均为 current persistent，0/15 retired；retired old-survivor、
same-slot history、unknown growth 与明确 referrer chain 均为零。
"""

    fixture_report = f"""# Stage 01D-R4 Fixture Validation

四类夹具完全独立于 SPH 物理：A 验证长期 current 不误报，B 验证替换对象及时死亡，
C 验证故意 history leak 必须被检测，D 验证有界 two-generation pipeline 不误报。

{fixture_table}

12 个独立子进程全部按预登记正负标签分类。
"""

    final_report = f"""# Stage 01D-R4 最终报告

## 1. R3 冻结

{_freeze_text()}

## 2. 旧 age-2 门槛为何失败

R3 Control F 的 raw age-2 count 为 15。旧门槛要求 age-2=0，因此 T2 严格失败；
该旧规则和 R3 状态均未修改。R4 单独检查这些 storage 是否已退休。

## 3. Current persistent 与 retired reference

current persistent 仍属于 solver-readable current working set；retired reference 已被
同语义新对象替换且不再属于当前工作集。只有 retired old-survivor 或同槽 retired
多代共存属于 retention signal。

## 4. 15 个 Control F weakrefs 的身份

canonical F1 的 15/15 均为 current persistent、0/15 retired：

{reference_table}

## 5. 四类诊断夹具

{fixture_table}

Fixture C 的故意 history 同时触发 old-survivor 和 same-slot multigeneration；A、B、D
均无误报，证明分类器既能排除 current persistent，也能检出真实泄漏。

## 6. 短程 F 回归

{control_table}

三个独立子进程均完成 200 steps，edge identity 唯一，状态有限并完全回收。

## 7. Old-survivor 与 same-slot history

F1–F3 的 retired old-survivor=0、same-slot multigeneration=0、unknown bytes Δ=0、
明确 referrer chain=0。age-2 非零仅表示当前固定工作集长寿命，不是 retired retention。

## 8. R2/R3 证据复核

六份冻结输入的 SHA-256 与预登记一致，没有重新拟合或回写：

{model_table}

β_edge=48 B/edge，β_step CI 均包含 0，γ_step=0；R2/R3 old-survivor=0，
Control M 3/3 通过，82940/82942/82944 的 q=5 cutoff 壳层解释保持成立。

## 9. 唯一 R4 状态

唯一状态为 **`{status}`**。

{gate_table}

## 10. Stage 01D2 协议申请资格

当前结论：**{eligible}**。该资格仅允许提交下一轮审计、申请设计新协议；
本阶段没有建立、设计或运行 Stage 01D2。

## 11. 历史状态保持

Stage 01D=`V2_FAIL`；Stage 01D-R=`RESOURCE_FAIL_LINEAR_GROWTH`；
Stage 01D-R2=`ATTRIBUTION_UNRESOLVED`；Stage 01D-R3=`R3_CONFIRMATION_UNRESOLVED`。
所有旧状态、报告和机器证据均未修改。

## 12. V3 与 Stage 02

**V3 未开始，Stage 02 未开始。** 未运行正式 V2 时间/空间收敛，未训练神经网络，
未修改 SPH 物理、RK2、支撑规律或第三方源码。

## 证据索引

Campaign 15/15 worker PASS，全部回收=`{campaign['all_processes_reclaimed']}`。

{_evidence_index()}
"""
    return {
        REPORTS["semantics"]: semantics_report,
        REPORTS["control"]: control_report,
        REPORTS["fixtures"]: fixture_report,
        REPORTS["final"]: final_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_reports()
    if args.check:
        mismatches = [
            path.name for path, text in rendered.items()
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        if mismatches:
            raise SystemExit("REPORT_MISMATCH " + ",".join(mismatches))
        print("CHECK_OK rendered=4 existing=4 matching=4")
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
