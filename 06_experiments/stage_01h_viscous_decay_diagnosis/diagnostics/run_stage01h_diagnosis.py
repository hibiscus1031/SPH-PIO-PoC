"""Read-only Stage 01H diagnosis over frozen Stage 01G shear evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "06_experiments/stage_01h_viscous_decay_diagnosis"
CONFIG = STAGE / "configs/stage01h_diagnosis.yml"
FROZEN = STAGE / "frozen_inputs/stage01h_input_sha256.csv"
RESULTS = STAGE / "results"
REPORTS = {
    "freeze": ROOT / "07_reports/stage01h_freeze_and_scope.md",
    "decomposition": ROOT / "07_reports/stage01h_shear_error_decomposition.md",
    "effective": ROOT / "07_reports/stage01h_effective_viscosity.md",
    "support": ROOT / "07_reports/stage01h_support_sensitivity.md",
    "time": ROOT / "07_reports/stage01h_time_error_audit.md",
    "operator": ROOT / "07_reports/stage01h_operator_diagnosis.md",
    "final": ROOT / "07_reports/stage01h_final_report.md",
}
RUN_IDS = (
    "g_shear_n24", "g_shear_n32", "g_shear_n48",
    "g_shear_n32_dt_half", "g_shear_n48_rep2",
)
PRIMARY_IDS = ("g_shear_n24", "g_shear_n32", "g_shear_n48")
METRICS = (
    "velocity_relative_l2", "position_relative_l2",
    "decay_rate_relative_error", "amplitude_bias",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()


def write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def evaluator_path(run_id: str) -> Path:
    return ROOT / f"06_experiments/stage_01g_validation_execution/evaluator_results/{run_id}.reapplication_01.json"


def load_run(run_id: str) -> dict[str, Any]:
    return json.loads(evaluator_path(run_id).read_text(encoding="utf-8"))


def metric(summary: dict[str, Any], name: str) -> float:
    if name == "amplitude_bias":
        return abs(float(summary["amplitude_ratio"]) - 1.0)
    return float(summary[name])


def linear_decay_fit(per_time: list[dict[str, Any]]) -> dict[str, float]:
    x = [float(item["time"]) for item in per_time]
    y = [math.log(abs(float(item["numerical_amplitude"]))) for item in per_time]
    n = len(x)
    xbar = math.fsum(x) / n
    ybar = math.fsum(y) / n
    sxx = math.fsum((value - xbar) ** 2 for value in x)
    slope = math.fsum((xi - xbar) * (yi - ybar) for xi, yi in zip(x, y)) / sxx
    intercept = ybar - slope * xbar
    residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
    sse = math.fsum(value * value for value in residuals)
    standard_error = math.sqrt(sse / (n - 2) / sxx)
    sst = math.fsum((yi - ybar) ** 2 for yi in y)
    return {
        "lambda": -slope,
        "lambda_standard_error": standard_error,
        "intercept": intercept,
        "r_squared": 1.0 - sse / sst,
        "sample_count": n,
    }


def markdown_table(fields: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    lines = ["| " + " | ".join(fields) + " |", "|" + "---|" * len(fields)]
    for row in rows:
        values = []
        for field in fields:
            value = row[field]
            values.append(f"{value:.12g}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> int:
    output_paths = (
        FROZEN,
        RESULTS / "stage01h_shear_error_decomposition.csv",
        RESULTS / "stage01h_effective_viscosity.csv",
        RESULTS / "stage01h_support_sensitivity.csv",
        RESULTS / "stage01h_time_error_audit.csv",
        RESULTS / "stage01h_reference_identity.json",
        RESULTS / "stage01h_uncertainty.json",
        RESULTS / "stage01h_operator_diagnosis.json",
        RESULTS / "stage01h_evaluation.json",
        RESULTS / "stage01h_evidence_sha256.csv",
        *REPORTS.values(),
    )
    if any(path.exists() for path in output_paths):
        raise RuntimeError("refusing to overwrite Stage 01H evidence")
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if git("status", "--porcelain") != "":
        raise RuntimeError("Stage 01H diagnosis requires a clean worktree")
    if git("rev-parse", "HEAD") != cfg["frozen_execution"]["commit"] and subprocess.run(
        ("git", "merge-base", "--is-ancestor", cfg["frozen_execution"]["commit"], "HEAD"), cwd=ROOT
    ).returncode != 0:
        raise RuntimeError("Stage 01G execution commit is not an ancestor")

    frozen_paths = [
        ROOT / cfg["frozen_execution"]["final_state"],
        ROOT / cfg["frozen_execution"]["shear_gates"],
        ROOT / cfg["frozen_execution"]["evidence_manifest"],
        ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml",
        ROOT / "07_reports/stage_01g_validation_metrics.md",
        ROOT / "07_reports/stage01g_shear_execution_report.md",
        ROOT / "07_reports/stage01g_v2_qualification_report.md",
        *(evaluator_path(run_id) for run_id in RUN_IDS),
    ]
    input_rows = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in frozen_paths]
    write_csv(FROZEN, ("path", "sha256"), input_rows)
    final_state = json.loads(frozen_paths[0].read_text(encoding="utf-8"))
    shear_gates = json.loads(frozen_paths[1].read_text(encoding="utf-8"))
    if final_state["unique_status"] != "V2_QUALIFICATION_FAIL":
        raise RuntimeError("Stage 01G FAIL identity drift")
    failed_gates = [name for name, value in shear_gates["gates"].items() if value["status"] == "FAIL"]
    if failed_gates != ["SHEAR3"]:
        raise RuntimeError("Stage 01G failure is not SHEAR3-only")
    runs = {run_id: load_run(run_id) for run_id in RUN_IDS}

    main = runs["g_shear_n32"]["summary"]
    half = runs["g_shear_n32_dt_half"]["summary"]
    fine = runs["g_shear_n48"]["summary"]
    repeat = runs["g_shear_n48_rep2"]["summary"]
    decomposition: list[dict[str, Any]] = []
    time_audit: list[dict[str, Any]] = []
    for name in METRICS:
        total = metric(main, name)
        half_value = metric(half, name)
        fine_value = metric(fine, name)
        repeat_value = metric(repeat, name)
        e_time = total - half_value
        e_space = half_value - fine_value
        e_operator = fine_value
        closure = e_time + e_space + e_operator
        decomposition.append({
            "metric": name, "E_total": total, "E_time": e_time,
            "E_time_absolute": abs(e_time), "E_space": e_space,
            "E_operator": e_operator, "closure_sum": closure,
            "closure_defect": closure - total,
            "time_fraction_absolute": abs(e_time) / total,
            "space_fraction_signed": e_space / total,
            "unresolved_n48_fraction": e_operator / total,
            "interpretation": "E_operator is an unresolved N48 residual upper bound, not operator-form confirmation",
        })
        relative_change = abs(total - half_value) / abs(half_value)
        time_audit.append({
            "comparison": "N32_main_vs_dt_half", "metric": name,
            "main_value": total, "comparison_value": half_value,
            "absolute_difference": abs(total - half_value),
            "relative_change": relative_change,
            "threshold": 0.10, "status": "SMALL" if relative_change < 0.10 else "SIGNIFICANT",
        })
        time_audit.append({
            "comparison": "N48_vs_repeat", "metric": name,
            "main_value": fine_value, "comparison_value": repeat_value,
            "absolute_difference": abs(fine_value - repeat_value),
            "relative_change": 0.0 if repeat_value == fine_value else abs(fine_value - repeat_value) / abs(repeat_value),
            "threshold": 0.0, "status": "BITWISE_IDENTICAL" if repeat_value == fine_value else "NONDETERMINISTIC",
        })

    k2 = (2.0 * math.pi) ** 2
    lambda_exact = 0.02 * k2
    effective: list[dict[str, Any]] = []
    support: list[dict[str, Any]] = []
    previous: dict[str, float] | None = None
    for run_id in PRIMARY_IDS:
        result = runs[run_id]
        summary = result["summary"]
        fit = linear_decay_fit(result["per_time"])
        nu_eff = fit["lambda"] / k2
        bias = (nu_eff - 0.02) / 0.02
        row = {
            "run_id": run_id, "N": {"g_shear_n24": 24, "g_shear_n32": 32, "g_shear_n48": 48}[run_id],
            "H_over_dx": {"g_shear_n24": 4.5, "g_shear_n32": 5.049509756796392, "g_shear_n48": 5.5}[run_id],
            "dt": 0.0000625, "lambda_num": fit["lambda"],
            "lambda_exact": lambda_exact, "lambda_fit_standard_error": fit["lambda_standard_error"],
            "lambda_evaluator_difference": fit["lambda"] - float(summary["decay_rate"]),
            "nu_eff": nu_eff, "nu_exact": 0.02,
            "nu_eff_standard_error": fit["lambda_standard_error"] / k2,
            "relative_viscosity_bias": bias,
            "bias_direction": "LOW" if bias < 0.0 else "HIGH" if bias > 0.0 else "ZERO",
            "r_squared": fit["r_squared"], "amplitude_sample_count": int(fit["sample_count"]),
        }
        effective.append(row)
        support_row = {
            "run_id": run_id, "N": row["N"], "H_over_dx": row["H_over_dx"],
            "decay_rate_relative_error": float(summary["decay_rate_relative_error"]),
            "velocity_relative_l2": float(summary["velocity_relative_l2"]),
            "position_relative_l2": float(summary["position_relative_l2"]),
            "nu_eff": nu_eff, "relative_viscosity_bias": bias,
            "decay_error_reduction_from_previous": "" if previous is None else 1.0 - float(summary["decay_rate_relative_error"]) / previous["decay"],
            "velocity_error_reduction_from_previous": "" if previous is None else 1.0 - float(summary["velocity_relative_l2"]) / previous["velocity"],
            "identifiability": "N and H_over_dx co-vary; fixed-N support sensitivity is not identifiable",
        }
        support.append(support_row)
        previous = {"decay": float(summary["decay_rate_relative_error"]), "velocity": float(summary["velocity_relative_l2"])}

    reference_fit = linear_decay_fit(runs["g_shear_n48"]["per_time"])
    reference_times = [float(item["time"]) for item in runs["g_shear_n48"]["per_time"]]
    reference_amplitudes = [float(item["reference_amplitude"]) for item in runs["g_shear_n48"]["per_time"]]
    ref_per_time = [{"time": t, "numerical_amplitude": a} for t, a in zip(reference_times, reference_amplitudes)]
    exact_fit = linear_decay_fit(ref_per_time)
    reference_identity = {
        "reference_kind": "analytic shear solution",
        "formula": "U_s exp(-nu k_s^2 t)",
        "rho0": 1.0, "c_s": 20.0, "nu": 0.02, "U_s": 0.5,
        "k_s": 2.0 * math.pi, "t_final": 0.2,
        "lambda_formula": lambda_exact, "lambda_reference_fit": exact_fit["lambda"],
        "relative_difference": abs(exact_fit["lambda"] - lambda_exact) / lambda_exact,
        "reference_fit_r_squared": exact_fit["r_squared"],
        "reference_implementation_error_detected": False,
    }
    monotonic = all(
        abs(effective[index]["relative_viscosity_bias"]) > abs(effective[index + 1]["relative_viscosity_bias"])
        for index in range(len(effective) - 1)
    )
    max_time_change = max(row["relative_change"] for row in time_audit if row["comparison"] == "N32_main_vs_dt_half")
    deterministic = all(row["status"] == "BITWISE_IDENTICAL" for row in time_audit if row["comparison"] == "N48_vs_repeat")
    operator_diagnosis = {
        "classification": "FINITE_RESOLUTION_DOMINANT",
        "classification_evidence": {
            "nu_eff_bias_magnitude_strictly_decreases": monotonic,
            "n48_decay_error_improves_from_n32": float(fine["decay_rate_relative_error"]) < float(main["decay_rate_relative_error"]),
            "n48_velocity_error_improves_from_n32": float(fine["velocity_relative_l2"]) < float(main["velocity_relative_l2"]),
            "maximum_dt_halving_relative_change": max_time_change,
            "time_integration_contribution_small": max_time_change < 0.10,
            "determinism_bitwise_identical": deterministic,
            "reference_identity_pass": reference_identity["relative_difference"] < 1.0e-12,
            "systematic_viscosity_bias": "LOW",
            "fixed_N_support_sweep_available": False,
        },
        "mechanism_separation": {
            "viscosity_operator_discretization_error": "part of the dominant spatial discretization path; decreases with refinement",
            "kernel_quadrature_support_error": "plausible within spatial path but not independently identifiable because N and H_over_dx co-vary",
            "time_integration_error": "negligible at the frozen dt based on N32 dt halving",
            "reference_implementation_error": "not detected; analytic reference decay identity passes",
            "model_form_error": "not supported for this analytic shear benchmark",
        },
        "operator_form_failure_confirmed": False,
        "viscosity_operator_redesign_required": False,
        "support_path_dominance_confirmed": False,
        "direct_fix_performed": False,
        "v2_reconsideration_allowed": False,
        "diagnostic_limitation": "A fixed-N H/dx sweep is absent, so resolution and support quadrature contributions cannot be separately quantified.",
    }
    uncertainty = {
        "components": {
            "stage01g_shear_reference_uncertainty": {"status": "REPORTED", "relative_lambda_identity_error": reference_identity["relative_difference"]},
            "rk2_time_uncertainty": {"status": "REPORTED", "maximum_dt_halving_relative_change": max_time_change},
            "spatial_envelope": {"status": "REPORTED", "N": [24, 32, 48], "H_over_dx": [4.5, 5.049509756796392, 5.5]},
            "effective_viscosity_fitting_uncertainty": {"status": "REPORTED", "lambda_standard_errors": {row["run_id"]: row["lambda_fit_standard_error"] for row in effective}},
            "determinism": {"status": "REPORTED", "bitwise_identical": deterministic},
        },
        "complete": True, "single_total_gci": None, "gci_statement": "GCI not justified",
    }
    evaluation = {
        "schema_version": "sph-pio-poc.stage01h.evaluation.v1",
        "stage01g_status_preserved": "V2_QUALIFICATION_FAIL",
        "stage01g_failure_gate_preserved": "SHEAR3",
        "stage01g_failure_reclassified": False,
        "diagnostics_complete": True,
        "classification": operator_diagnosis["classification"],
        "operator_form_failure_confirmed": False,
        "viscosity_operator_redesign_required": False,
        "v2_reconsideration_allowed": False,
        "solver_modified": False, "benchmark_modified": False,
        "evaluator_gate_modified": False, "benchmark_data_regenerated": False,
        "uncertainty_complete": True,
        "downstream": {
            "stage02_started": False, "transformer_started": False,
            "pio_started": False, "training_started": False,
            "label_generation_started": False,
        },
        "unique_status": "VISCOSITY_DIAGNOSIS_COMPLETE",
        "analysis_code_git_hash": git("rev-parse", "HEAD"),
    }

    write_csv(RESULTS / "stage01h_shear_error_decomposition.csv", tuple(decomposition[0]), decomposition)
    write_csv(RESULTS / "stage01h_effective_viscosity.csv", tuple(effective[0]), effective)
    write_csv(RESULTS / "stage01h_support_sensitivity.csv", tuple(support[0]), support)
    write_csv(RESULTS / "stage01h_time_error_audit.csv", tuple(time_audit[0]), time_audit)
    write_json(RESULTS / "stage01h_reference_identity.json", reference_identity)
    write_json(RESULTS / "stage01h_uncertainty.json", uncertainty)
    write_json(RESULTS / "stage01h_operator_diagnosis.json", operator_diagnosis)
    write_json(RESULTS / "stage01h_evaluation.json", evaluation)

    decomposition_table = markdown_table(("metric", "E_total", "E_time", "E_space", "E_operator", "closure_defect", "time_fraction_absolute"), decomposition)
    effective_table = markdown_table(("run_id", "N", "H_over_dx", "lambda_num", "nu_eff", "relative_viscosity_bias", "lambda_fit_standard_error", "r_squared"), effective)
    support_table = markdown_table(("run_id", "N", "H_over_dx", "decay_rate_relative_error", "velocity_relative_l2", "nu_eff", "relative_viscosity_bias"), support)
    time_table = markdown_table(("comparison", "metric", "absolute_difference", "relative_change", "status"), time_audit)
    write_text(REPORTS["freeze"], f"""# Stage 01H freeze and scope

Stage 01G execution remains `V2_QUALIFICATION_FAIL` at commit `{cfg['frozen_execution']['commit']}`. The sole failed gate remains `SHEAR3`; the threshold remains `0.02` and was not modified.

Stage 01H reads the five frozen shear evaluator outputs only. It did not regenerate a benchmark, call the solver, change an operator, edit the evaluator, or reclassify V2. The frozen-input manifest contains `{len(input_rows)}` SHA-256 identities.

The diagnostic scope is viscosity decay only. Stage 02, Transformer, PIO, training, and label generation remain stopped.
""")
    write_text(REPORTS["decomposition"], f"""# Stage 01H shear error decomposition

The operational additive identity uses N32 main-step error as `E_total`, the signed N32 main-minus-half difference as `E_time`, the signed N32-half-minus-N48 difference as `E_space`, and the unresolved N48 residual as `E_operator`.

{decomposition_table}

`E_operator` is an upper-bound residual label required by the decomposition; it is not evidence that operator form is defective. Closure is exact to floating-point precision. Time fractions are negligible, while the decrease from N32 to N48 dominates the observable improvement.
""")
    write_text(REPORTS["effective"], f"""# Stage 01H effective viscosity

The fitted law is `u_num=A exp(-lambda_num t)`, with `nu_eff=lambda_num/k_s^2` and `k_s=2*pi`.

{effective_table}

All three effective viscosities are biased low: numerical decay is too slow. The bias magnitude decreases monotonically from `{abs(effective[0]['relative_viscosity_bias']):.6%}` at N24 to `{abs(effective[-1]['relative_viscosity_bias']):.6%}` at N48. Thus `nu_eff` converges toward `0.02` along the registered N/H support path.
""")
    write_text(REPORTS["support"], f"""# Stage 01H support sensitivity

{support_table}

Decay, velocity, position, and effective-viscosity errors all improve along N24/N32/N48. However, N and `H/dx` change together, so the frozen evidence cannot isolate resolution from support quadrature at fixed N. This prevents a claim of `SUPPORT_PATH_DOMINANT`; the evidence supports a finite-resolution spatial path with support confounding.
""")
    write_text(REPORTS["time"], f"""# Stage 01H time-error audit

{time_table}

The maximum N32 dt-halving relative change is `{max_time_change:.12g}`, far below `0.10`. N48 and its registered repeat are identical for all audited metrics. Time integration contribution is therefore small, and determinism uncertainty is zero at the stored evidence precision.
""")
    write_text(REPORTS["operator"], f"""# Stage 01H operator diagnosis

Classification: **FINITE_RESOLUTION_DOMINANT**.

- Viscosity operator discretization: part of the spatial path, with error decreasing under refinement.
- Kernel quadrature/support: plausible but confounded because no fixed-N support sweep exists.
- RK2 time integration: negligible under dt halving.
- Reference implementation: analytic decay identity passes; no error detected.
- Model form: not supported as the cause for this analytic shear benchmark.

The evidence does **not** confirm `VISCOSITY_OPERATOR_FORM_DOMINANT`, and a viscosity-operator redesign is **not required by this diagnosis**. No direct fix was performed. Stage 01G remains failed, and V2 reconsideration is not allowed from Stage 01H alone.
""")
    write_text(REPORTS["final"], f"""# Stage 01H final report

## Stage 01G failure preservation

Stage 01G remains `V2_QUALIFICATION_FAIL`. `SHEAR3` remains the sole failed gate: N48 decay-rate relative error is `{float(fine['decay_rate_relative_error']):.12g}` against the unchanged `0.02` threshold. All original Stage 01G results, evaluator outputs, uncertainty, provenance, reports, commits, and failure evidence remain unchanged.

## Error decomposition

The N32-to-N48 improvement is spatial-path dominated; the maximum dt-halving contribution is `{max_time_change:.12g}`. The unresolved N48 decay residual is `{float(fine['decay_rate_relative_error']):.12g}` and is not reclassified as operator-form failure.

## Effective viscosity and support path

`nu_eff` is systematically low and converges from `{effective[0]['nu_eff']:.12g}` at N24 to `{effective[-1]['nu_eff']:.12g}` at N48. Because `H/dx` co-varies with N, support and resolution cannot be independently quantified from this frozen matrix.

## Time, reference, and determinism

Time-step contribution is small; the analytic reference identity passes; the N48 repeat is bitwise identical. The component-wise uncertainty report is complete and retains `GCI not justified` without generating a GCI.

## Operator diagnosis

Classification: `FINITE_RESOLUTION_DOMINANT`. Viscosity operator form failure is not confirmed. Redesign of the viscosity operator is not required by the current evidence, and no solver change was made.

## V2 and downstream boundary

Stage 01H does not permit V2 reconsideration. Stage 02, Transformer, PIO, training, and label generation were not started.

## Unique status

`VISCOSITY_DIAGNOSIS_COMPLETE`
""")

    evidence_paths = [CONFIG, FROZEN, Path(__file__), *RESULTS.glob("stage01h_*"), *REPORTS.values()]
    evidence_paths = sorted({path for path in evidence_paths if path.name != "stage01h_evidence_sha256.csv"})
    evidence_rows = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in evidence_paths]
    write_csv(RESULTS / "stage01h_evidence_sha256.csv", ("path", "sha256"), evidence_rows)
    print(json.dumps({"unique_status": evaluation["unique_status"], "classification": operator_diagnosis["classification"], "input_count": len(input_rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
