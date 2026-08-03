"""Aggregate frozen evaluator outputs and issue the unique Stage 01G V2 state."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stage01g_reapplication_contract import (  # noqa: E402
    ACOUSTIC_IDS, ALL_IDS, ATTEMPT_ID, CODE_FILES, PREFLIGHT_REPORT,
    PREFLIGHT_RESULT, ROOT, SHEAR_IDS, STAGE, attempt_run_dir,
    checkpoint_path, evaluator_path, execution_code_hashes, preflight_code_guard,
    read_json, reference_path, sha256, write_json_new, write_text_new,
)

EVALUATOR_ROOT = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(EVALUATOR_ROOT))
from evaluator.gate_rules import evaluate_acoustic_gates, evaluate_hard_safety, evaluate_shear_gates  # noqa: E402
from evaluator.uncertainty_report import build_uncertainty_report  # noqa: E402

RESULT_PATHS = {
    "shear_gates": STAGE / "results/stage01g_shear_gates_reapplication_01.json",
    "acoustic_gates": STAGE / "results/stage01g_acoustic_gates_reapplication_01.json",
    "hard_safety": STAGE / "results/stage01g_hard_safety_reapplication_01.json",
    "uncertainty": STAGE / "results/stage01g_uncertainty_reapplication_01.json",
    "determinism": STAGE / "results/stage01g_determinism_reapplication_01.json",
    "provenance": STAGE / "results/stage01g_provenance_reapplication_01.json",
    "evaluation": STAGE / "results/stage01g_evaluation_reapplication_01.json",
    "final_state": STAGE / "results/stage01g_execution_final_state.json",
}
REPORTS = {
    "shear": ROOT / "07_reports/stage01g_shear_execution_report.md",
    "acoustic": ROOT / "07_reports/stage01g_acoustic_execution_report.md",
    "uncertainty": ROOT / "07_reports/stage01g_uncertainty_report.md",
    "qualification": ROOT / "07_reports/stage01g_v2_qualification_report.md",
}
MANIFEST = STAGE / "manifests/stage01g_execution_evidence_sha256_reapplication_01.csv"


def load_runs(run_ids: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    runs: dict[str, Any] = {}
    missing: list[str] = []
    for run_id in run_ids:
        result_path = evaluator_path(run_id)
        status_path = attempt_run_dir(run_id) / "status_final.json"
        if not result_path.exists() or not status_path.exists() or read_json(status_path).get("status") != "EVIDENCE_COMPLETE":
            missing.append(run_id)
        else:
            runs[run_id] = read_json(result_path)
    return runs, missing


def provenance_audit() -> dict[str, Any]:
    preflight = read_json(PREFLIGHT_RESULT)
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    for run_id in ALL_IDS:
        run_dir = attempt_run_dir(run_id)
        provenance_path = run_dir / "provenance.json"
        status_path = run_dir / "status_final.json"
        summary_path = run_dir / "summary.json"
        required_paths = (provenance_path, status_path, summary_path, checkpoint_path(run_id), reference_path(run_id), evaluator_path(run_id))
        if not all(path.exists() for path in required_paths):
            checks[run_id] = False
            details[run_id] = {"missing": [path.relative_to(ROOT).as_posix() for path in required_paths if not path.exists()]}
            continue
        value, marker, summary = read_json(provenance_path), read_json(status_path), read_json(summary_path)
        required = (
            "trajectory_sha256", "reference_sha256", "metadata_sha256",
            "checkpoint_file_sha256", "reference_file_sha256", "evaluator_result_sha256",
            "trajectory_content_sha256", "reference_content_sha256", "config_sha256",
            "run_matrix_sha256", "metric_contract_sha256", "code_git_hash",
            "worker_sha256", "python_executable", "python_version", "torch_version",
            "numpy_version", "device", "dtype", "child_pid", "reference_kind",
        )
        passed = (
            all(value.get(key) not in (None, "") for key in required)
            and value["checkpoint_file_sha256"] == sha256(checkpoint_path(run_id))
            and value["reference_file_sha256"] == sha256(reference_path(run_id))
            and value["evaluator_result_sha256"] == sha256(evaluator_path(run_id))
            and value["worker_sha256"] == preflight["execution_code_sha256"][(HERE / "stage01g_reapplication_worker.py").relative_to(ROOT).as_posix()]
            and value["code_git_hash"] == preflight["git_head"]
            and value["device"] == "cpu" and value["dtype"] == "float64"
            and value["dimensions"] == 2 and value["boundary"] == "periodic"
            and value["default_cyclic_gc"] is True and value["torch_no_grad"] is True
            and value["in_loop_gc_collect"] is False and value["source_call_count"] == 0
            and value["child_pid"] == marker["pid"]
            and marker["child_reclaimed"] is True and marker["parent_scalar_only"] is True
            and summary["execution_status"] == "COMPLETE" and summary["evaluator_status"] == "COMPLETE"
        )
        checks[run_id] = passed
        details[run_id] = {"status": "PASS" if passed else "FAIL", "child_pid": marker["pid"]}
    preserved = {
        "canonical_type_error": (STAGE / "runs/g_shear_n24/failure.txt").exists(),
        "infra_retry1_key_error": (STAGE / "runs/g_shear_n24/failure.infra_retry1.txt").exists(),
        "infra_retry2_attribute_error": (STAGE / "runs/g_shear_n24/failure.infra_retry2.txt").exists(),
    }
    return {
        "run_checks": checks, "run_details": details,
        "execution_code_sha256": execution_code_hashes(),
        "historical_failure_evidence_preserved": preserved,
        "complete": len(checks) == 12 and all(checks.values()) and all(preserved.values()),
    }


def determinism_audit() -> dict[str, Any]:
    pairs = {
        "shear_n48_repeat": ("g_shear_n48", "g_shear_n48_rep2"),
        "acoustic_n48_repeat": ("g_acoustic_e5e3_n48", "g_acoustic_e5e3_n48_rep2"),
    }
    output: dict[str, Any] = {}
    for name, (left_id, right_id) in pairs.items():
        paths = (attempt_run_dir(left_id) / "provenance.json", attempt_run_dir(right_id) / "provenance.json")
        if not all(path.exists() for path in paths):
            output[name] = {"status": "MISSING"}
            continue
        left, right = (read_json(path) for path in paths)
        trajectory = left["trajectory_content_sha256"] == right["trajectory_content_sha256"]
        reference = left["reference_content_sha256"] == right["reference_content_sha256"]
        output[name] = {
            "trajectory_bitwise_identical": trajectory,
            "reference_bitwise_identical": reference,
            "status": "PASS" if trajectory and reference else "FAIL",
        }
    return {"pairs": output, "status": "PASS" if len(output) == 2 and all(item["status"] == "PASS" for item in output.values()) else "FAIL"}


def gate_table(gates: dict[str, Any]) -> str:
    return "\n".join(["| Gate | Status |", "|---|---|"] + [f"| `{name}` | {item['status']} |" for name, item in sorted(gates["gates"].items())])


def run_status_table() -> str:
    lines = ["| Run ID | Phase | Execution | Evaluator | Child reclaimed |", "|---|---|---|---|---|"]
    for run_id in ALL_IDS:
        run_dir = attempt_run_dir(run_id)
        marker = read_json(run_dir / "status_final.json") if (run_dir / "status_final.json").exists() else {}
        summary = read_json(run_dir / "summary.json") if (run_dir / "summary.json").exists() else {}
        lines.append(f"| `{run_id}` | {'A' if run_id in SHEAR_IDS else 'B'} | {marker.get('status', 'MISSING')} | {summary.get('evaluator_status', 'MISSING')} | {marker.get('child_reclaimed', False)} |")
    return "\n".join(lines)


def metric_table(run_ids: tuple[str, ...], runs: dict[str, Any], fields: tuple[str, ...]) -> str:
    lines = ["| Run ID | " + " | ".join(fields) + " |", "|---|" + "---:|" * len(fields)]
    for run_id in run_ids:
        summary = runs.get(run_id, {}).get("summary", {})
        values = []
        for field in fields:
            value = summary.get(field, "MISSING")
            values.append(f"{value:.12g}" if isinstance(value, float) else str(value))
        lines.append(f"| `{run_id}` | " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_manifest() -> None:
    if MANIFEST.exists():
        raise RuntimeError("refusing to overwrite final reapplication evidence manifest")
    paths: set[Path] = set(CODE_FILES) | set(REPORTS.values()) | {PREFLIGHT_REPORT, PREFLIGHT_RESULT}
    for run_id in ALL_IDS:
        paths.update(path for path in attempt_run_dir(run_id).rglob("*") if path.is_file())
        paths.update((checkpoint_path(run_id), reference_path(run_id), evaluator_path(run_id)))
        stdout = STAGE / "logs" / f"{run_id}.{ATTEMPT_ID}.stdout.log"
        stderr = STAGE / "logs" / f"{run_id}.{ATTEMPT_ID}.stderr.log"
        paths.update((stdout, stderr))
    paths.update(path for path in RESULT_PATHS.values() if path.exists())
    paths.update((STAGE / "results/stage01g_phase_a_execution_reapplication_01.json", STAGE / "results/stage01g_phase_b_execution_reapplication_01.json", STAGE / "manifests/stage01g_campaign_index_reapplication_01.csv"))
    with MANIFEST.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("path", "sha256", "classification"), lineterminator="\n")
        writer.writeheader()
        for path in sorted(paths):
            if not path.exists():
                continue
            relative = path.relative_to(ROOT).as_posix()
            classification = "execution_code" if path in CODE_FILES else "execution_report" if path in REPORTS.values() or path == PREFLIGHT_REPORT else "formal_run_evidence"
            writer.writerow({"path": relative, "sha256": sha256(path), "classification": classification})


def main() -> int:
    preflight_code_guard()
    if any(path.exists() for path in (*RESULT_PATHS.values(), *REPORTS.values(), MANIFEST)):
        raise RuntimeError("refusing to overwrite aggregate reapplication evidence")
    shear, missing_shear = load_runs(SHEAR_IDS)
    acoustic, missing_acoustic = load_runs(ACOUSTIC_IDS)
    complete_execution = not missing_shear and not missing_acoustic
    shear_gates = evaluate_shear_gates(shear) if not missing_shear else {"gates": {}, "status": "NOT_EVALUATED"}
    acoustic_gates = evaluate_acoustic_gates(acoustic) if not missing_acoustic else {"gates": {}, "status": "NOT_EVALUATED"}
    hard = {run_id: evaluate_hard_safety(result["diagnostics"]) for run_id, result in {**shear, **acoustic}.items()}
    hard_pass = len(hard) == 12 and all(item["status"] == "PASS" for item in hard.values())
    uncertainty = build_uncertainty_report(shear, acoustic)
    provenance = provenance_audit()
    determinism = determinism_audit()
    if not complete_execution or not provenance["complete"] or not uncertainty["complete"]:
        unique_status = "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    elif shear_gates["status"] != "PASS" or acoustic_gates["status"] != "PASS" or not hard_pass or determinism["status"] != "PASS":
        unique_status = "V2_QUALIFICATION_FAIL"
    else:
        unique_status = "V2_QUALIFICATION_PASS"
    run_statuses = {}
    for run_id in ALL_IDS:
        run_dir = attempt_run_dir(run_id)
        marker = read_json(run_dir / "status_final.json") if (run_dir / "status_final.json").exists() else {}
        summary = read_json(run_dir / "summary.json") if (run_dir / "summary.json").exists() else {}
        run_statuses[run_id] = {"execution": marker.get("status", "MISSING"), "evaluator": summary.get("evaluator_status", "MISSING")}
    final_state = {
        "schema_version": "sph-pio-poc.stage01g.execution-final-state.v1",
        "execution_identity": "Stage 01G Independent Validation Execution / reapplication_01",
        "run_statuses": run_statuses,
        "executed_run_count": len(shear) + len(acoustic),
        "missing_run_ids": missing_shear + missing_acoustic,
        "shear_gates": shear_gates["status"], "acoustic_gates": acoustic_gates["status"],
        "hard_safety": "PASS" if hard_pass else "FAIL",
        "uncertainty_complete": uncertainty["complete"],
        "provenance_complete": provenance["complete"],
        "determinism": determinism["status"],
        "unique_status": unique_status,
        "next_stage_qualified": unique_status == "V2_QUALIFICATION_PASS",
        "downstream": {"stage01h_started": False, "v3_started": False, "stage02_started": False, "training_started": False, "label_generation_started": False},
    }
    write_json_new(RESULT_PATHS["shear_gates"], shear_gates)
    write_json_new(RESULT_PATHS["acoustic_gates"], acoustic_gates)
    write_json_new(RESULT_PATHS["hard_safety"], {"runs": hard, "status": "PASS" if hard_pass else "FAIL"})
    write_json_new(RESULT_PATHS["uncertainty"], uncertainty)
    write_json_new(RESULT_PATHS["determinism"], determinism)
    write_json_new(RESULT_PATHS["provenance"], provenance)
    write_json_new(RESULT_PATHS["evaluation"], final_state)
    write_json_new(RESULT_PATHS["final_state"], final_state)

    shear_metrics = metric_table(SHEAR_IDS, shear, ("velocity_relative_l2", "velocity_linf", "position_relative_l2", "position_linf", "decay_rate_relative_error", "amplitude_ratio", "density_drift_linf", "pressure_linf", "transverse_leakage", "momentum_drift"))
    acoustic_metrics = metric_table(ACOUSTIC_IDS, acoustic, ("phase_speed_relative_error", "density_fundamental_amplitude_relative_error", "velocity_fundamental_amplitude_relative_error", "density_signal_normalized_l2", "velocity_signal_normalized_l2", "pressure_linf", "second_harmonic_ratio", "transverse_leakage", "mean_momentum_drift", "density_bias", "pressure_bias"))
    write_text_new(REPORTS["shear"], f"# Stage 01G shear execution report\n\n{shear_metrics}\n\n## SHEAR1–SHEAR8\n\n{gate_table(shear_gates) if shear_gates['gates'] else 'Not evaluated: incomplete evidence.'}\n\nPhase A evaluator status: **{shear_gates['status']}**.")
    write_text_new(REPORTS["acoustic"], f"# Stage 01G acoustic execution report\n\n{acoustic_metrics}\n\n## ACOUSTIC1–ACOUSTIC10\n\n{gate_table(acoustic_gates) if acoustic_gates['gates'] else 'Not evaluated: incomplete evidence.'}\n\nPhase B evaluator status: **{acoustic_gates['status']}**.")
    uncertainty_lines = "\n".join(f"- `{name}`: **{component['status']}**" for name, component in uncertainty["components"].items())
    write_text_new(REPORTS["uncertainty"], f"# Stage 01G uncertainty report\n\n{uncertainty_lines}\n\nComplete: **{uncertainty['complete']}**.\n\nNo synthetic total GCI was produced; the frozen limitation remains `GCI not justified`.")
    qualification = f"""# Stage 01G V2 qualification report

## Execution identity

Frozen Stage 01G + Stage 01G-E evaluator + approved preflight v2 + Stage 01G-R infrastructure, formal attempt `reapplication_01`.

## All 12 run statuses

{run_status_table()}

## Evaluator results

- SHEAR1–SHEAR8: `{shear_gates['status']}`
- ACOUSTIC1–ACOUSTIC10: `{acoustic_gates['status']}`
- Hard safety: `{'PASS' if hard_pass else 'FAIL'}`
- Determinism: `{determinism['status']}`

## Uncertainty and provenance

- Uncertainty complete: `{uncertainty['complete']}`
- Provenance complete: `{provenance['complete']}`
- Executed evidence: `{len(shear) + len(acoustic)}/12`

## Unique V2 status

`{unique_status}`

Next-stage qualified: `{unique_status == 'V2_QUALIFICATION_PASS'}`. No downstream stage was started automatically.
"""
    write_text_new(REPORTS["qualification"], qualification)
    build_manifest()
    print(json.dumps({"unique_status": unique_status, "executed_run_count": len(shear) + len(acoustic)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
