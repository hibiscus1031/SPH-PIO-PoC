"""Apply the frozen Stage 01G-E evaluator to completed Stage 01G runs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01g_validation_execution"
EVALUATOR_ROOT = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(EVALUATOR_ROOT))

from evaluator.gate_rules import evaluate_acoustic_gates, evaluate_hard_safety, evaluate_shear_gates  # noqa: E402
from evaluator.report_generator import render_qualification_summary  # noqa: E402
from evaluator.uncertainty_report import build_uncertainty_report  # noqa: E402


SHEAR_IDS = (
    "g_shear_n24",
    "g_shear_n32",
    "g_shear_n48",
    "g_shear_n32_dt_half",
    "g_shear_n48_rep2",
)
ACOUSTIC_IDS = (
    "g_acoustic_e5e3_n24",
    "g_acoustic_e5e3_n32",
    "g_acoustic_e5e3_n48",
    "g_acoustic_e5e3_n32_dt_half",
    "g_acoustic_e5e3_n48_rep2",
    "g_acoustic_e2p5e3_n48",
    "g_acoustic_e1e2_n48",
)
NEW_REPORTS = (
    ROOT / "07_reports/stage01g_execution_shear_results.md",
    ROOT / "07_reports/stage01g_execution_acoustic_results.md",
    ROOT / "07_reports/stage01g_execution_uncertainty.md",
    ROOT / "07_reports/stage01g_execution_v2_qualification.md",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, value: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def load_runs(run_ids: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    runs: dict[str, Any] = {}
    missing: list[str] = []
    for run_id in run_ids:
        result = STAGE / "runs" / run_id / "evaluator_result.json"
        marker = STAGE / "runs" / run_id / "status.json"
        if not result.exists() or not marker.exists():
            missing.append(run_id)
            continue
        if json.loads(marker.read_text())["status"] != "PASS":
            missing.append(run_id)
            continue
        runs[run_id] = json.loads(result.read_text())
    return runs, missing


def provenance_audit(run_ids: tuple[str, ...]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    for run_id in run_ids:
        path = STAGE / "runs" / run_id / "provenance.json"
        if not path.exists():
            checks[run_id] = False
            continue
        value = json.loads(path.read_text())
        required = (
            "checkpoint_file_sha256",
            "reference_file_sha256",
            "evaluator_result_sha256",
            "trajectory_content_sha256",
            "reference_content_sha256",
            "config_sha256",
            "run_matrix_sha256",
            "metric_contract_sha256",
            "code_git_hash",
            "python_executable",
            "python_version",
            "torch_version",
            "numpy_version",
            "device",
            "dtype",
        )
        checks[run_id] = (
            all(key in value and value[key] not in (None, "") for key in required)
            and value["checkpoint_file_sha256"] == sha256(STAGE / "checkpoints" / f"{run_id}.npz")
            and value["reference_file_sha256"] == sha256(STAGE / "references" / f"{run_id}.npz")
            and value["evaluator_result_sha256"] == sha256(STAGE / "runs" / run_id / "evaluator_result.json")
            and value["device"] == "cpu"
            and value["dtype"] == "float64"
        )
    return {
        "run_checks": checks,
        "run_count": len(checks),
        "complete": len(checks) == 12 and all(checks.values()),
    }


def determinism_audit() -> dict[str, Any]:
    pairs = {
        "shear_n48_repeat": ("g_shear_n48", "g_shear_n48_rep2"),
        "acoustic_n48_repeat": ("g_acoustic_e5e3_n48", "g_acoustic_e5e3_n48_rep2"),
    }
    results: dict[str, Any] = {}
    for name, (first, second) in pairs.items():
        paths = [STAGE / "runs" / run_id / "provenance.json" for run_id in (first, second)]
        if not all(path.exists() for path in paths):
            results[name] = {"status": "MISSING"}
            continue
        left, right = (json.loads(path.read_text()) for path in paths)
        trajectory = left["trajectory_content_sha256"] == right["trajectory_content_sha256"]
        reference = left["reference_content_sha256"] == right["reference_content_sha256"]
        results[name] = {
            "trajectory_bitwise_identical": trajectory,
            "reference_bitwise_identical": reference,
            "status": "PASS" if trajectory and reference else "FAIL",
        }
    return {
        "pairs": results,
        "status": "PASS" if all(item["status"] == "PASS" for item in results.values()) else "FAIL",
    }


def gate_table(gates: dict[str, Any]) -> str:
    lines = ["| Gate | Status |", "|---|---|"]
    for name, result in sorted(gates["gates"].items()):
        lines.append(f"| {name} | {result['status']} |")
    return "\n".join(lines)


def run_table(run_ids: tuple[str, ...], runs: dict[str, Any], fields: tuple[str, ...]) -> str:
    lines = ["| Run ID | " + " | ".join(fields) + " |", "|---|" + "---:|" * len(fields)]
    for run_id in run_ids:
        if run_id not in runs:
            lines.append(f"| `{run_id}` | " + " | ".join("MISSING" for _ in fields) + " |")
            continue
        summary = runs[run_id]["summary"]
        values = []
        for field in fields:
            value = summary[field]
            values.append(f"{value:.12g}" if isinstance(value, float) else str(value))
        lines.append(f"| `{run_id}` | " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_manifest() -> None:
    manifest = STAGE / "manifests/stage01g_execution_evidence_sha256.csv"
    if manifest.exists():
        raise RuntimeError("refusing to overwrite final evidence manifest")
    paths: list[Path] = []
    for directory in (STAGE / "runs", STAGE / "references", STAGE / "checkpoints", STAGE / "logs", STAGE / "results"):
        paths.extend(path for path in directory.rglob("*") if path.is_file() and path.name != ".preflight-stop")
    paths.extend(NEW_REPORTS)
    paths.extend((STAGE / "stage01g_worker.py", STAGE / "run_stage01g_campaign.py", STAGE / "evaluate_stage01g_execution.py"))
    old_results = {STAGE / "results/preflight_audit.json", STAGE / "results/stage01g_evaluation.json"}
    paths = sorted({path for path in paths if path not in old_results})
    with manifest.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("path", "sha256", "classification"), lineterminator="\n")
        writer.writeheader()
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            if "/runs/" in relative:
                classification = "run_evidence"
            elif "/references/" in relative:
                classification = "independent_reference"
            elif "/checkpoints/" in relative:
                classification = "numerical_checkpoint"
            elif "/logs/" in relative:
                classification = "execution_log"
            elif relative.startswith("07_reports/"):
                classification = "execution_report"
            elif relative.endswith(".py"):
                classification = "execution_code"
            else:
                classification = "aggregate_result"
            writer.writerow({"path": relative, "sha256": sha256(path), "classification": classification})


def main() -> int:
    output_paths = (
        STAGE / "results/stage01g_shear_gates.json",
        STAGE / "results/stage01g_acoustic_gates.json",
        STAGE / "results/stage01g_execution_uncertainty.json",
        STAGE / "results/stage01g_execution_determinism.json",
        STAGE / "results/stage01g_execution_provenance.json",
        STAGE / "results/stage01g_execution_evaluation.json",
        STAGE / "manifests/stage01g_execution_evidence_sha256.csv",
        *NEW_REPORTS,
    )
    if any(path.exists() for path in output_paths):
        raise RuntimeError("refusing to overwrite existing aggregate execution evidence")

    shear, missing_shear = load_runs(SHEAR_IDS)
    acoustic, missing_acoustic = load_runs(ACOUSTIC_IDS)
    complete_matrix = not missing_shear and not missing_acoustic
    shear_gates = evaluate_shear_gates(shear) if not missing_shear else {"gates": {}, "status": "NOT_EVALUATED"}
    acoustic_gates = evaluate_acoustic_gates(acoustic) if not missing_acoustic else {"gates": {}, "status": "NOT_EVALUATED"}
    uncertainty = build_uncertainty_report(shear, acoustic)
    provenance = provenance_audit(SHEAR_IDS + ACOUSTIC_IDS)
    determinism = determinism_audit()
    hard_safety = {
        run_id: evaluate_hard_safety(result["diagnostics"])
        for run_id, result in {**shear, **acoustic}.items()
    }
    hard_safety_pass = len(hard_safety) == 12 and all(item["status"] == "PASS" for item in hard_safety.values())
    if not complete_matrix:
        unique_status = "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    elif (
        shear_gates["status"] == "PASS"
        and acoustic_gates["status"] == "PASS"
        and hard_safety_pass
        and uncertainty["complete"]
        and provenance["complete"]
        and determinism["status"] == "PASS"
    ):
        unique_status = "V2_QUALIFICATION_PASS"
    else:
        unique_status = "V2_QUALIFICATION_FAIL"
    evaluation = {
        "executed_run_count": len(shear) + len(acoustic),
        "executed_run_ids": list(shear) + list(acoustic),
        "missing_run_ids": missing_shear + missing_acoustic,
        "shear_gates": shear_gates["status"],
        "acoustic_gates": acoustic_gates["status"],
        "hard_safety": "PASS" if hard_safety_pass else "FAIL",
        "uncertainty_complete": uncertainty["complete"],
        "provenance_complete": provenance["complete"],
        "determinism": determinism["status"],
        "current_v2_status": unique_status,
        "downstream": {
            "v3_started": False,
            "stage02_started": False,
            "training_started": False,
            "label_generation_started": False,
        },
        "unique_status": unique_status,
    }

    write_json(STAGE / "results/stage01g_shear_gates.json", shear_gates)
    write_json(STAGE / "results/stage01g_acoustic_gates.json", acoustic_gates)
    write_json(STAGE / "results/stage01g_execution_uncertainty.json", uncertainty)
    write_json(STAGE / "results/stage01g_execution_determinism.json", determinism)
    write_json(STAGE / "results/stage01g_execution_provenance.json", provenance)
    write_json(STAGE / "results/stage01g_execution_evaluation.json", evaluation)

    shear_report = "\n\n".join(
        (
            "# Stage 01G execution — Shear results",
            run_table(SHEAR_IDS, shear, ("velocity_relative_l2", "position_relative_l2", "decay_rate_relative_error", "density_drift_linf", "transverse_leakage")),
            "## Frozen gates\n\n" + gate_table(shear_gates) if shear_gates["gates"] else "## Frozen gates\n\nNot evaluated: incomplete evidence.",
            f"Phase A status: **{shear_gates['status']}**.",
        )
    )
    acoustic_report = "\n\n".join(
        (
            "# Stage 01G execution — Acoustic results",
            run_table(ACOUSTIC_IDS, acoustic, ("phase_speed_relative_error", "density_fundamental_amplitude_relative_error", "velocity_fundamental_amplitude_relative_error", "density_signal_normalized_l2", "velocity_signal_normalized_l2", "second_harmonic_ratio")),
            "## Frozen gates\n\n" + gate_table(acoustic_gates) if acoustic_gates["gates"] else "## Frozen gates\n\nNot evaluated: incomplete evidence.",
            f"Phase B status: **{acoustic_gates['status']}**.",
        )
    )
    uncertainty_lines = ["# Stage 01G execution — Uncertainty", ""]
    for name, component in uncertainty["components"].items():
        uncertainty_lines.append(f"- `{name}`: **{component['status']}**")
    uncertainty_lines.extend(("", f"Complete: **{uncertainty['complete']}**.", "", "No single total GCI was generated; the frozen statement remains `GCI not justified`."))
    qualification = render_qualification_summary(shear_gates, acoustic_gates, uncertainty, provenance["complete"])
    qualification += (
        "\n## Execution controls\n\n"
        f"- Hard safety: `{evaluation['hard_safety']}`\n"
        f"- Determinism: `{evaluation['determinism']}`\n"
        f"- Executed runs: `{evaluation['executed_run_count']}/12`\n"
        "- V3 started: `False`\n"
        "- Stage 02 started: `False`\n"
        "- Training started: `False`\n"
        "- Label generation started: `False`\n\n"
        "## Unique status\n\n"
        f"`{unique_status}`\n"
    )
    write_text(NEW_REPORTS[0], shear_report)
    write_text(NEW_REPORTS[1], acoustic_report)
    write_text(NEW_REPORTS[2], "\n".join(uncertainty_lines))
    write_text(NEW_REPORTS[3], qualification)
    build_manifest()
    print(json.dumps({"unique_status": unique_status, "executed_run_count": evaluation["executed_run_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
