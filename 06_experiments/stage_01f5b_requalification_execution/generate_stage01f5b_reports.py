"""Generate the eleven immutable Stage 01F5B Markdown reports from evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
REPORTS = ROOT / "07_reports"


def load(relative: str) -> dict[str, Any]:
    return json.loads((STAGE / relative).read_text())


def write(name: str, text: str) -> None:
    path = REPORTS / name
    if path.exists():
        if name == "stage_01f5b_freeze_and_preflight.md":
            return
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def gate_table(values: dict[str, bool]) -> str:
    lines = ["| Gate | Result |", "|---|---|"]
    lines += [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in values.items()]
    return "\n".join(lines)


def combination_table(cases: dict[str, Any], kind: str) -> str:
    lines = ["| Dataset | MMS | Combination | fitted p | fine local median | fine time/platform | total/platform distance |", "|---|---|---|---:|---:|---:|---:|"]
    for key, case in cases.items():
        if not key.startswith(kind):
            continue
        for name, item in case["combinations"].items():
            lines.append(f"| {case['label']} | {case['solution']} | {name} | {item['fitted_order']:.8g} | {item['finest_three_local_order_median']:.8g} | {item['finest_time_space_ratio']:.8g} | {item['finest_total_platform_relative_distance']:.8g} |")
    return "\n".join(lines)


def main() -> int:
    preflight = load("results/preflight_audit_attempt2.json")
    preflight_attempt1 = load("results/preflight_audit.json")
    references = load("results/reference_qualification.json")
    temporal = load("results/time_and_platform_analysis.json")
    space_step = load("manifests/space_step_decision.json")
    spatial = load("results/spatial_analysis.json")
    n64 = load("manifests/n64_trigger_decision.json")
    determinism = load("results/determinism.json")
    evaluation = load("results/stage01f5b_evaluation.json")
    with (STAGE / "results/run_status_table.csv").open() as stream:
        run_rows = list(csv.DictReader(stream))

    write("stage_01f5b_freeze_and_preflight.md", f"""# Stage 01F5B freeze and preflight

Stage 01F5-Q evidence commit `8ab58b8647c1dd1e5cfe71a77cf6ec71c93a1484`, status `FORMAL_SPACE_EXECUTION_BUNDLE_READY`, and annotated tag `stage-01f5q-formal-space-execution-bundle-ready` were frozen before execution. The numerical-source identity is commit `38487d66b40fa2c8dd65eb7aa6c279da4a8e5e2c`; no file under `01_solver` or `05_metrics` was modified.

{gate_table(preflight['checks'])}

Preflight status: `{preflight['status']}`. The bundle v3, 69-row matrix, 69/69 dry resolution, canonical T/P/H/S/safety hashes, output uniqueness, scalar-only parent contract, solver-free child smoke, disk gate, and complete pytest suite were checked before the first numerical trajectory. The preserved first attempt has status `{preflight_attempt1['status']}` because it used the non-frozen base Python without diffSPH; no numerical run was launched before the frozen-environment retry.
""")

    ref_lines = ["| Reference family | position L∞ qualified | velocity L∞ qualified | Status |", "|---|---|---|---|"]
    for prefix, item in references["items"].items():
        ref_lines.append(f"| {prefix} | {item['checks']['position_sensitivity']} | {item['checks']['velocity_sensitivity']} | {item['status']} |")
    write("stage_01f5b_reference_qualification.md", "# Stage 01F5B reference qualification\n\n" + "\n".join(ref_lines) + f"\n\nOverall reference status: `{references['status']}`. Each listed family used three new production-sparse DOP853 runs, continuous unwrapped coordinates, reciprocal topology auditing, and at least ten sparse/dense acceleration comparisons; no Stage 01F3B/01F3C reference was substituted.")

    write("stage_01f5b_main_time_requalification.md", f"""# Stage 01F5B main time requalification

The primary temporal error is the vector difference `q_RK2 - q_semidiscrete`, evaluated for position and velocity with endpoint vector-L2 and 16-time integrated vector-RMS norms.

{combination_table(temporal['cases'], 'main_')}

{gate_table({key: temporal['main_checks'][key] for key in ('T1','T2','T3','T4','T5')})}
""")

    diagnostics = []
    for key, case in temporal["cases"].items():
        if key.startswith("main_"):
            for row in case["rows"]:
                for field in ("position", "velocity"):
                    for norm in ("endpoint", "integrated"):
                        item = row["fields"][field][norm]
                        diagnostics.append(f"| {case['solution']} | {row['dt']:.8g} | {field}-{norm} | {item['cross_term']:.8g} | {item['cosine']:.8g} | {item['reconstruction_absolute_residual']:.3g} | {item['platform_approach']} |")
    write("stage_01f5b_main_plateau_assessment.md", "# Stage 01F5B main plateau assessment\n\n`e_total = e_space + e_time`; therefore `||e_total||² = ||e_space||² + ||e_time||² + 2<e_space,e_time>`. Cross-term sign and platform-approach direction are diagnostics, not gates.\n\n| MMS | dt | combination | cross term | cosine | reconstruction residual | approach |\n|---|---:|---|---:|---:|---:|---|\n" + "\n".join(diagnostics) + "\n\n" + gate_table({key: temporal["main_checks"][key] for key in ("P1", "P2", "P3")}))

    held = dict(temporal["heldout_checks"])
    held["H5"] = evaluation["heldout_checks"]["H5"]
    write("stage_01f5b_heldout_requalification.md", f"""# Stage 01F5B held-out requalification

The prospectively sealed N28, `H/dx=4.75` held-out configuration was not used in protocol design and was executed with five frozen time steps and new three-level references.

{combination_table(temporal['cases'], 'heldout_')}

{gate_table(held)}

Total exact-error monotonicity, cross-term sign agreement with the main configuration, and a shared platform-approach direction were not required.
""")

    decision_rows = ["| MMS/field | coarse error | fine error | relative change |", "|---|---:|---:|---:|"]
    for key, item in space_step["comparisons"].items():
        decision_rows.append(f"| {key} | {item['dt_6p25e5_error']:.10g} | {item['dt_3p125e5_error']:.10g} | {item['relative_change']:.10g} |")
    write("stage_01f5b_space_step_decision.md", "# Stage 01F5B immutable space-step decision\n\n" + "\n".join(decision_rows) + f"\n\nMaximum relative change: `{space_step['maximum_relative_change']:.12g}`. Chosen `dt_space={space_step['chosen_dt_space']}`, `{space_step['formal_space_steps']}` steps to `t_final=0.02`. The decision was written before Phase G/H and is marked `immutable=true`.")

    spatial_rows = ["| MMS | field | N16 | N24 | N32 | N48 | slope |", "|---|---|---:|---:|---:|---:|---:|"]
    for solution, case in spatial["cases"].items():
        for field, item in case["fields"].items():
            values = item["errors"]
            spatial_rows.append(f"| {solution} | {field} | {values[0]:.8g} | {values[1]:.8g} | {values[2]:.8g} | {values[3]:.8g} | {item['global_slope']:.8g} |")
    write("stage_01f5b_spatial_requalification.md", "# Stage 01F5B spatial requalification\n\n" + "\n".join(spatial_rows) + "\n\n" + gate_table(spatial["checks"]) + "\n\nAny positive conclusion applies only to the preregistered **increasing-neighbor consistency path**; it is not fixed-stencil single-parameter h convergence.")

    trigger_lines = ["| MMS | field | nonmonotone | N48/N32 >0.95 | sign inconsistent | asymptotic unclear |", "|---|---|---|---|---|---|"]
    for row in n64["trigger_rows"]:
        trigger_lines.append(f"| {row['solution']} | {row['field']} | {row['any_primary_error_nonmonotone']} | {row['n48_n32_ratio_greater_than_0p95']} | {row['local_order_sign_inconsistent']} | {row['near_asymptotic_entry_unclear']} |")
    k_rows = [row for row in run_rows if row["conditional"] == "true"]
    retry = evaluation["infrastructure_retry_reconciliation"]
    write("stage_01f5b_n64_branch.md", "# Stage 01F5B N64 branch\n\n" + "\n".join(trigger_lines) + f"\n\nImmutable decision: `{n64['decision']}`.\n\nThe original `{retry['original_run_id']}` raw status remains `{retry['original_raw_status']}`. It generated no numerical state and retained the original pure-infrastructure failure evidence. The protocol-authorized unique `{retry['retry_run_id']}` status is `{retry['retry_raw_status']}`; the effective frozen-DAG predecessor status is `{retry['effective_predecessor_status']}`.\n\n| Conditional run | Raw status | Effective status |\n|---|---|---|\n" + "\n".join(f"| {row['run_id']} | {row['status']} | {row['effective_status']} |" for row in k_rows))

    write("stage_01f5b_balance_resources_determinism.md", "# Stage 01F5B balance, resources, and determinism\n\nAll numerical summaries retain pair-force, internal-force, assembly, momentum, viscous-power, minimum-separation, topology, source-call, RSS, and step-time gates. A hard-safety failure cannot be overridden by order, plateau, or GCI evidence.\n\n| Base | Repeat | Status |\n|---|---|---|\n" + "\n".join(f"| {row['base']} | {row['repeat']} | {row['status']} |" for row in determinism["pairs"]) + f"\n\nSix-pair determinism status: `{determinism['status']}`. Arrays, masses, common times, edge hashes, topology-event hash, and numerical scalar summaries were compared bitwise.")

    gci_lines = ["| MMS | field | Qualification | Statement |", "|---|---|---|---|"]
    for solution, fields in evaluation["gci"].items():
        for field, item in fields.items():
            gci_lines.append(f"| {solution} | {field} | {'PASS' if item['qualified'] else 'NOT JUSTIFIED'} | {item['statement']} |")
    write("stage_01f5b_uncertainty_and_gci.md", "# Stage 01F5B uncertainty and GCI\n\nReference uncertainty was evaluated separately for position/velocity and endpoint/integrated norms. GCI is variable-specific and is not required for the overall status.\n\n" + "\n".join(gci_lines))

    status_table = ["| Run ID | Category | Raw status | Effective status |", "|---|---|---|---|"] + [f"| {row['run_id']} | {row['category']} | {row['status']} | {row['effective_status']} |" for row in run_rows]
    eligibility = "eligible to apply for Stage 01G design" if evaluation["stage01g_application_eligible"] else "not eligible to apply for Stage 01G"
    write("stage_01f5b_final_report.md", f"""# Stage 01F5B final report

## 1. Frozen basis and identities

Stage 01F5-Q commit `8ab58b8647c1dd1e5cfe71a77cf6ec71c93a1484`, status `FORMAL_SPACE_EXECUTION_BUNDLE_READY`, tag `stage-01f5q-formal-space-execution-bundle-ready`, execution bundle v3, 69-row matrix, and 69/69 dry-resolution audit were frozen. Numerical source commit `38487d66b40fa2c8dd65eb7aa6c279da4a8e5e2c` and the complete source-tree SHA-256 manifest matched before execution.

## 2. Complete run status table

{chr(10).join(status_table)}

## 3. Reference qualification

Reference qualification: `{references['status']}`. All reference evidence is newly generated Stage 01F5B evidence using the production sparse RHS and frozen DOP853 levels.

## 4. N20 main time and plateau gates

{gate_table(temporal['main_checks'])}

Time-integrator convergence was evaluated against qualified semidiscrete references. Total exact error was used only for plateau gates. Vector cross terms, cosines, squared-norm reconstruction, and platform approach direction were reported but not promoted to qualification gates.

## 5. N28 held-out gates

{gate_table(evaluation['heldout_checks'])}

## 6. Space-step decision and formal spatial gates

The immutable Phase F decision selected `dt_space={space_step['chosen_dt_space']}`, `{space_step['formal_space_steps']}` steps, and `t_final=0.02` from the preregistered eight-field comparison.

{gate_table(spatial['checks'])}

The spatial claim is limited to increasing-neighbor consistency-path convergence and is not fixed-stencil single-h convergence.

## 7. N64 branch

The immutable N64 trigger decision was `{n64['decision']}` and the frozen DAG was followed. Conditional statuses are recorded in the full run table.

The original `f5_n64_smoke_a` infrastructure failure remains raw `FAIL`; it launched no solver and generated no numerical state. Its sole authorized `_infra_retry1` is recorded separately, and the evaluator validates parameter identity and all retained provenance before assigning the effective predecessor status. No scientific failure is reclassified by this mechanism.

The postexecution evaluator amendment is separately hash-sealed. Its scope is infrastructure-retry reconciliation only; it records no numerical-source, runner, configuration, scientific-gate, threshold, trigger, or execution-order change.

## 8. Safety, provenance, determinism, and GCI

{gate_table(evaluation['gate_blocks'])}

The source, conservation, topology, resource, and determinism evidence is retained per run. Six determinism pairs had overall status `{determinism['status']}`. GCI was evaluated independently by variable; where prerequisites failed, the only statement is `GCI not justified`.

## 9. Failures and limitations

No failed gate is masked by a platform interpretation or GCI. Reciprocal cutoff crossings and more than one edge identity are legal diagnostics; structural topology defects are hard failures. The one-shot no-overwrite/no-rerun rule remained in force.

## 10. Unique Stage 01F5B status

`{evaluation['unique_status']}`

The project is {eligibility}. Stage 01G was not started automatically.

Stage 01D2, Stage 01F3, Stage 01F3B, Stage 01F3C, and Stage 01F5-P historical states remain unchanged. V3, Stage 02, training, and label generation have not started.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
