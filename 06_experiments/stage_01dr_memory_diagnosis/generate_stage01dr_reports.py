"""Generate the five Stage 01D-R reports from immutable retained evidence.

This program is a read-only post-processor for numerical evidence.  It never
imports or invokes the rollout worker or the campaign analyzer.  Report writes
are no-clobber and each target is installed atomically from a complete
temporary file.  ``--check`` validates all evidence and renders in memory
without creating reports; any existing report must match byte-for-byte.
"""

from __future__ import annotations

import argparse
import ast
import csv
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_RELATIVE = Path("06_experiments/stage_01dr_memory_diagnosis")
REPORT_RELATIVE = Path("07_reports")
CONFIG_RELATIVE = (
    EXPERIMENT_RELATIVE / "configs" / "preregistered_memory_diagnosis.yml"
)

REPORT_FILENAMES = (
    "stage_01dr_code_retention_audit.md",
    "stage_01dr_memory_component_audit.md",
    "stage_01dr_reproduction_report.md",
    "stage_01dr_resource_requalification.md",
    "stage_01dr_final_report.md",
)

ALLOWED_RESOURCE_STATUSES = (
    "RESOURCE_PASS_ALLOCATOR_PLATEAU",
    "RESOURCE_PASS_AFTER_RETENTION_FIX",
    "RESOURCE_CONDITIONAL",
    "RESOURCE_FAIL_LINEAR_GROWTH",
    "RESOURCE_FAIL_UNRESOLVED",
)

EXPECTED_GATE_IDS = (
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "P",
    "N16",
    "REG",
    "SENTINEL",
    "STATUS",
)

ANALYSIS_FILENAMES = {
    "summary": "analysis_summary.json",
    "status": "stage01dr_resource_status.txt",
    "runs": "memory_run_metrics.csv",
    "variants": "variant_summary.csv",
    "overhead": "diagnostics_overhead.csv",
    "archive": "archive_assessment.csv",
    "sentinel": "graph_sentinel_summary.csv",
    "gates": "resource_gate_evidence.csv",
}


class ReportEvidenceError(RuntimeError):
    """Raised when report evidence is absent, inconsistent, or unsafe."""


@dataclass(frozen=True)
class CsvTable:
    path: Path
    fieldnames: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class StaticFinding:
    number: int
    question: str
    answer: str
    retention_assessment: str
    evidence: str
    minimal_reproducer: str


@dataclass(frozen=True)
class Evidence:
    project_root: Path
    experiment_root: Path
    config_path: Path
    configuration: dict[str, Any]
    config_sha256: str
    manifest: CsvTable
    manifest_artifacts: tuple[Path, ...]
    freeze_facts: dict[str, Any]
    old_status_path: Path
    old_run_summary: CsvTable
    old_n32_row: dict[str, str]
    old_n32_samples: CsvTable
    old_failure_path: Path
    analysis_summary_path: Path
    analysis_summary: dict[str, Any]
    resource_status_path: Path
    resource_status: str
    run_metrics: CsvTable
    variant_summary: CsvTable
    diagnostics_overhead: CsvTable
    archive_assessment: CsvTable
    graph_sentinel: CsvTable
    resource_gates: CsvTable
    figure_paths: tuple[Path, ...]
    retention_fix_evidence: dict[str, Any]
    retention_fix_artifacts: tuple[Path, ...]
    static_findings: tuple[StaticFinding, ...]
    generator_path: Path

    @classmethod
    def load(
        cls,
        project_root: Path,
        *,
        experiment_root: Path | None = None,
    ) -> "Evidence":
        root = project_root.resolve()
        if not root.is_dir():
            raise ReportEvidenceError(f"project root is not a directory: {root}")
        experiment = (
            root / EXPERIMENT_RELATIVE
            if experiment_root is None
            else experiment_root.resolve()
        )
        _require_inside(experiment, root, label="Stage 01D-R experiment root")
        if not experiment.is_dir():
            raise ReportEvidenceError(
                f"Stage 01D-R experiment root is missing: {experiment}"
            )

        config_path = experiment / "configs" / "preregistered_memory_diagnosis.yml"
        configuration = _read_yaml(config_path, label="Stage 01D-R preregistration")
        _validate_configuration(configuration)
        config_sha256 = _sha256(config_path)

        manifest_path = _resolve_project_path(
            root,
            _nested(configuration, "frozen_stage_01d", "sha256_manifest"),
            label="Stage 01D freeze manifest",
        )
        manifest = _read_csv(
            manifest_path,
            label="Stage 01D freeze manifest",
            required=("category", "path", "sha256", "bytes"),
        )
        manifest_artifacts, freeze_facts = _validate_freeze(
            root,
            configuration,
            manifest,
        )

        status_rows = [
            row for row in manifest.rows if row["category"] == "status"
        ]
        run_rows = [
            row for row in manifest.rows if row["category"] == "run_summary"
        ]
        failure_rows = [
            row for row in manifest.rows if row["category"] == "failure_stack"
        ]
        if len(status_rows) != 1 or len(run_rows) != 1 or len(failure_rows) != 1:
            raise ReportEvidenceError(
                "freeze manifest must identify one old status, run summary, "
                "and failure stack"
            )
        old_status_path = _resolve_project_path(
            root, status_rows[0]["path"], label="frozen Stage 01D status"
        )
        if old_status_path.read_bytes() != b"V2_FAIL\n":
            raise ReportEvidenceError("frozen Stage 01D status is not V2_FAIL")
        old_run_summary = _read_csv(
            _resolve_project_path(
                root, run_rows[0]["path"], label="frozen Stage 01D run summary"
            ),
            label="frozen Stage 01D run summary",
            required=(
                "run_id",
                "protocol",
                "status",
                "failure_class",
                "failure_reason",
                "first_failure_step",
                "first_failure_time",
                "resolution",
                "current_rss_initial_bytes",
                "current_rss_final_bytes",
                "all_states_finite",
                "memory_growth_with_step",
                "sustained_memory_pressure",
                "sample_table_path",
                "failure_evidence_path",
            ),
        )
        n32_candidates = [
            row
            for row in old_run_summary.rows
            if row.get("protocol") == "smoke_n32"
            and row.get("resolution") == "32"
        ]
        if len(n32_candidates) != 1:
            raise ReportEvidenceError(
                "frozen run summary does not contain exactly one N32 smoke run"
            )
        old_n32_row = n32_candidates[0]
        _validate_old_n32(old_n32_row)
        old_n32_samples = _read_csv(
            _resolve_project_path(
                root,
                old_n32_row["sample_table_path"],
                label="frozen N32 sample table",
            ),
            label="frozen N32 sample table",
            required=(
                "step",
                "time",
                "current_rss_bytes",
                "peak_rss_bytes",
                "neighbor_edge_count",
                "state_all_finite",
            ),
        )
        _validate_old_samples(old_n32_row, old_n32_samples)
        old_failure_path = _resolve_project_path(
            root,
            failure_rows[0]["path"],
            label="frozen N32 failure stack",
        )
        if old_n32_row["failure_evidence_path"] != _relative(
            old_failure_path, root
        ):
            raise ReportEvidenceError(
                "frozen N32 failure path differs from freeze manifest"
            )
        failure_text = old_failure_path.read_text(encoding="utf-8")
        if "sustained current RSS growth" not in failure_text:
            raise ReportEvidenceError(
                "frozen N32 failure stack omits the retained RSS reason"
            )

        results_root = experiment / "results"
        analysis_summary_path = results_root / ANALYSIS_FILENAMES["summary"]
        analysis_summary = _read_json(
            analysis_summary_path, label="Stage 01D-R analysis summary"
        )
        resource_status_path = results_root / ANALYSIS_FILENAMES["status"]
        resource_status = _read_status(resource_status_path)
        run_metrics = _read_csv(
            results_root / ANALYSIS_FILENAMES["runs"],
            label="Stage 01D-R run metrics",
            required=(
                "run_id",
                "resolution",
                "variant",
                "repeat",
                "completion_pass",
                "provenance_pass",
                "sampling_coverage_pass",
                "process_reclamation_pass",
                "numerical_pass",
                "first_quartile_rss_median_bytes",
                "final_quartile_rss_median_bytes",
                "final_minus_first_rss_bytes",
                "rss_theil_sen_bytes_per_step",
                "rss_bootstrap_ci95_lower_bytes_per_step",
                "rss_bootstrap_ci95_upper_bytes_per_step",
                "tensor_count_theil_sen_per_step",
                "tensor_bytes_theil_sen_per_step",
                "tracemalloc_theil_sen_bytes_per_step",
                "gc_object_theil_sen_per_step",
                "rss_slope_limit_pass",
                "rss_quartile_limit_pass",
                "archive_write_count",
                "archive_checkpoint_count",
                "archive_current_rss_delta_bytes",
                "archive_path",
                "mean_step_wall_seconds",
                "final_edge_count",
                "config_hash",
                "git_hash",
                "memory_sample_path",
                "summary_path",
                "process_exit_path",
                "numerical_path",
            ),
        )
        variant_summary = _read_csv(
            results_root / ANALYSIS_FILENAMES["variants"],
            label="Stage 01D-R variant summary",
            required=(
                "resolution",
                "variant",
                "repeat_count",
                "completed_count",
                "all_numerical_pass",
                "all_sampling_pass",
                "all_reclaimed",
                "median_final_quartile_rss_bytes",
                "median_rss_slope_bytes_per_step",
                "rss_significant_positive_repeat_count",
                "tensor_count_positive_repeat_count",
                "tensor_bytes_positive_repeat_count",
                "tracemalloc_positive_repeat_count",
                "gc_object_positive_repeat_count",
            ),
        )
        diagnostics_overhead = _read_csv(
            results_root / ANALYSIS_FILENAMES["overhead"],
            label="Stage 01D-R diagnostics overhead",
            required=(
                "resolution",
                "a_median_final_quartile_rss_bytes",
                "b_median_final_quartile_rss_bytes",
                "b_minus_a_bounded_extra_bytes",
                "b_minus_a_fraction_of_a",
                "pass",
            ),
        )
        archive_assessment = _read_csv(
            results_root / ANALYSIS_FILENAMES["archive"],
            label="Stage 01D-R archive assessment",
            required=(
                "run_id",
                "resolution",
                "repeat",
                "variant",
                "solver_completed",
                "archive_only_failure",
                "archive_localized",
                "archive_overhead_bounded",
                "archive_contract_detail",
            ),
        )
        graph_sentinel = _read_csv(
            results_root / ANALYSIS_FILENAMES["sentinel"],
            label="Stage 01D-R graph sentinel",
            required=(
                "run_id",
                "mode",
                "status",
                "reachable_grad_graph_node_count",
                "final_positions_has_grad_fn",
                "final_velocities_has_grad_fn",
                "final_current_rss_bytes",
                "final_live_tensor_count",
                "final_live_tensor_unique_storage_bytes",
                "process_reclaimed",
                "identity_pass",
            ),
        )
        resource_gates = _read_csv(
            results_root / ANALYSIS_FILENAMES["gates"],
            label="Stage 01D-R resource gates",
            required=(
                "gate",
                "check",
                "passed",
                "observed",
                "threshold",
                "source",
                "severity",
                "detail",
            ),
        )
        figure_paths, retention_fix_artifacts = _validate_analysis(
            root,
            configuration,
            config_sha256,
            analysis_summary,
            resource_status,
            run_metrics,
            variant_summary,
            diagnostics_overhead,
            archive_assessment,
            graph_sentinel,
            resource_gates,
        )
        retention_fix_evidence = dict(
            _nested(configuration, "retention_fix_evidence")
        )
        generator_path = Path(__file__).resolve()
        static_findings = _static_retention_findings(root)
        return cls(
            project_root=root,
            experiment_root=experiment,
            config_path=config_path,
            configuration=configuration,
            config_sha256=config_sha256,
            manifest=manifest,
            manifest_artifacts=manifest_artifacts,
            freeze_facts=freeze_facts,
            old_status_path=old_status_path,
            old_run_summary=old_run_summary,
            old_n32_row=old_n32_row,
            old_n32_samples=old_n32_samples,
            old_failure_path=old_failure_path,
            analysis_summary_path=analysis_summary_path,
            analysis_summary=analysis_summary,
            resource_status_path=resource_status_path,
            resource_status=resource_status,
            run_metrics=run_metrics,
            variant_summary=variant_summary,
            diagnostics_overhead=diagnostics_overhead,
            archive_assessment=archive_assessment,
            graph_sentinel=graph_sentinel,
            resource_gates=resource_gates,
            figure_paths=figure_paths,
            retention_fix_evidence=retention_fix_evidence,
            retention_fix_artifacts=retention_fix_artifacts,
            static_findings=static_findings,
            generator_path=generator_path,
        )


def _nested(value: Mapping[Any, Any], *keys: Any) -> Any:
    current: Any = value
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        if not isinstance(current, Mapping) or key not in current:
            raise ReportEvidenceError(
                "missing configuration key: "
                + ".".join(str(item) for item in traversed)
            )
        current = current[key]
    return current


def _require_inside(path: Path, root: Path, *, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ReportEvidenceError(f"{label} escapes the project root") from error


def _relative(path: Path, root: Path) -> str:
    _require_inside(path, root, label="report evidence")
    return path.resolve().relative_to(root.resolve()).as_posix()


def _resolve_project_path(root: Path, value: Any, *, label: str) -> Path:
    text = str(value)
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReportEvidenceError(f"unsafe {label} path: {text}")
    path = (root / relative).resolve()
    _require_inside(path, root, label=label)
    if not path.is_file():
        raise ReportEvidenceError(f"missing {label}: {text}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_yaml(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ReportEvidenceError(f"missing {label}: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ReportEvidenceError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ReportEvidenceError(f"{label} must be a mapping")
    return value


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ReportEvidenceError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ReportEvidenceError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ReportEvidenceError(f"{label} must contain one JSON object")
    return value


def _read_jsonl(path: Path, *, label: str) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        raise ReportEvidenceError(f"missing {label}: {path}")
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ReportEvidenceError(
                    f"{label} row {line_number} is not a JSON object"
                )
            rows.append(value)
    except ReportEvidenceError:
        raise
    except Exception as error:
        raise ReportEvidenceError(f"cannot read {label}: {error}") from error
    if not rows:
        raise ReportEvidenceError(f"{label} contains no rows")
    return tuple(rows)


def _read_csv(
    path: Path,
    *,
    label: str,
    required: Sequence[str] = (),
) -> CsvTable:
    if not path.is_file():
        raise ReportEvidenceError(f"missing {label}: {path}")
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fieldnames = tuple(reader.fieldnames or ())
            rows = tuple(dict(row) for row in reader)
    except Exception as error:
        raise ReportEvidenceError(f"cannot read {label}: {error}") from error
    if not fieldnames:
        raise ReportEvidenceError(f"{label} has no header")
    missing = set(required) - set(fieldnames)
    if missing:
        raise ReportEvidenceError(
            f"{label} lacks required columns: {sorted(missing)}"
        )
    if not rows:
        raise ReportEvidenceError(f"{label} contains no rows")
    return CsvTable(path=path.resolve(), fieldnames=fieldnames, rows=rows)


def _read_status(path: Path) -> str:
    if not path.is_file():
        raise ReportEvidenceError(f"missing Stage 01D-R status: {path}")
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise ReportEvidenceError("Stage 01D-R status must be one LF line")
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise ReportEvidenceError("Stage 01D-R status is not ASCII") from error
    if value not in ALLOWED_RESOURCE_STATUSES:
        raise ReportEvidenceError(f"unknown Stage 01D-R status: {value}")
    return value


def _parse_bool(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ReportEvidenceError(f"invalid boolean for {label}: {value!r}")


def _finite_float(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ReportEvidenceError(f"invalid number for {label}: {value!r}") from error
    if not math.isfinite(result):
        raise ReportEvidenceError(f"nonfinite number for {label}: {value!r}")
    return result


def _integer(value: Any, *, label: str) -> int:
    number = _finite_float(value, label=label)
    if not number.is_integer():
        raise ReportEvidenceError(f"non-integer value for {label}: {value!r}")
    return int(number)


def _validate_configuration(configuration: Mapping[str, Any]) -> None:
    if configuration.get("stage") != "01D-R":
        raise ReportEvidenceError("configuration stage is not 01D-R")
    if (
        configuration.get("status")
        != "PREREGISTERED_BEFORE_FIRST_STAGE_01DR_ROLLOUT"
    ):
        raise ReportEvidenceError("Stage 01D-R configuration is not preregistered")
    scope = _nested(configuration, "scope")
    required_false = (
        "formal_v2_time_or_space_convergence",
        "v3_authorized",
        "stage_02_authorized",
        "neural_network_work",
        "learning_labels",
        "third_party_core_modification",
        "frozen_stage_01d_files_may_be_modified",
    )
    if not bool(scope.get("resource_diagnosis_only")):
        raise ReportEvidenceError("Stage 01D-R is not resource-only")
    if any(bool(scope.get(key)) for key in required_false):
        raise ReportEvidenceError("Stage 01D-R scope boundary was broadened")
    if _nested(configuration, "frozen_stage_01d", "retained_status") != "V2_FAIL":
        raise ReportEvidenceError("preregistration no longer retains V2_FAIL")
    allowed = tuple(_nested(configuration, "decision", "allowed_statuses"))
    if allowed != ALLOWED_RESOURCE_STATUSES:
        raise ReportEvidenceError("registered resource status vocabulary drifted")
    if (
        _nested(configuration, "decision", "old_stage_01d_status_must_remain")
        != "V2_FAIL"
    ):
        raise ReportEvidenceError("decision policy no longer freezes V2_FAIL")
    if not bool(
        _nested(
            configuration,
            "decision",
            "stage_01d2_may_only_be_recommended_not_started",
        )
    ):
        raise ReportEvidenceError("Stage 01D2 start boundary is not registered")
    retention_fix = _nested(configuration, "retention_fix_evidence")
    if not isinstance(retention_fix, Mapping):
        raise ReportEvidenceError("retention_fix_evidence must be a mapping")
    required_fix_keys = {
        "applied",
        "permitted_class",
        "failing_reproducer_path",
        "regression_test_path",
        "before_curve_path",
        "after_curve_path",
        "separate_commit",
        "rationale",
    }
    missing_fix_keys = required_fix_keys - set(retention_fix)
    if missing_fix_keys:
        raise ReportEvidenceError(
            "retention_fix_evidence lacks keys: "
            f"{sorted(missing_fix_keys)}"
        )
    if not isinstance(retention_fix.get("applied"), bool):
        raise ReportEvidenceError("retention_fix_evidence.applied must be boolean")


def _git(project_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=project_root,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise ReportEvidenceError(
            f"cannot resolve required git evidence: {' '.join(arguments)}"
        ) from error
    return completed.stdout.strip()


def _validate_freeze(
    project_root: Path,
    configuration: Mapping[str, Any],
    manifest: CsvTable,
) -> tuple[tuple[Path, ...], dict[str, Any]]:
    frozen = _nested(configuration, "frozen_stage_01d")
    expected_rows = int(frozen["expected_manifest_rows"])
    if len(manifest.rows) != expected_rows:
        raise ReportEvidenceError(
            f"freeze manifest has {len(manifest.rows)} rows, expected {expected_rows}"
        )
    categories: dict[str, int] = {}
    paths: list[Path] = []
    seen: set[str] = set()
    for row in manifest.rows:
        relative_text = row["path"]
        if relative_text in seen:
            raise ReportEvidenceError(
                f"duplicate freeze-manifest path: {relative_text}"
            )
        seen.add(relative_text)
        path = _resolve_project_path(
            project_root, relative_text, label="frozen Stage 01D artifact"
        )
        expected_digest = row["sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ReportEvidenceError(
                f"invalid manifest SHA-256 for {relative_text}"
            )
        if _sha256(path) != expected_digest:
            raise ReportEvidenceError(
                f"frozen Stage 01D hash mismatch: {relative_text}"
            )
        if path.stat().st_size != _integer(
            row["bytes"], label=f"manifest bytes for {relative_text}"
        ):
            raise ReportEvidenceError(
                f"frozen Stage 01D size mismatch: {relative_text}"
            )
        categories[row["category"]] = categories.get(row["category"], 0) + 1
        paths.append(path)
    expected_categories = {
        "report": 8,
        "status": 1,
        "gate_evidence": 1,
        "run_summary": 1,
        "failure_stack": 1,
        "state_archive": 3,
    }
    if categories != expected_categories:
        raise ReportEvidenceError(
            f"freeze manifest category mismatch: {categories}"
        )

    formal_commit = str(frozen["formal_run_commit"])
    final_commit = str(frozen["final_evidence_commit"])
    for label, commit in (
        ("formal Stage 01D run", formal_commit),
        ("final Stage 01D evidence", final_commit),
    ):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ReportEvidenceError(f"invalid {label} commit")
        if _git(project_root, "cat-file", "-t", commit) != "commit":
            raise ReportEvidenceError(f"missing {label} commit")
    tag = str(frozen["annotated_tag"])
    if _git(project_root, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise ReportEvidenceError("Stage 01D freeze tag is not annotated")
    tag_target = _git(project_root, "rev-list", "-n", "1", tag)
    required_target = str(frozen["required_tag_target"])
    if tag_target != required_target or tag_target != final_commit:
        raise ReportEvidenceError("Stage 01D freeze tag target mismatch")
    return tuple(paths), {
        "formal_run_commit": formal_commit,
        "final_evidence_commit": final_commit,
        "tag": tag,
        "tag_target": tag_target,
        "manifest_rows": len(manifest.rows),
        "categories": categories,
        "mismatches": 0,
        "old_status": "V2_FAIL",
    }


def _validate_old_n32(row: Mapping[str, str]) -> None:
    expected = {
        "status": "FAIL",
        "failure_class": "MEMORY_GROWTH",
        "failure_reason": "sustained current RSS growth",
        "first_failure_step": "4",
        "all_states_finite": "True",
        "memory_growth_with_step": "True",
        "sustained_memory_pressure": "False",
    }
    mismatches = {
        key: (row.get(key), value)
        for key, value in expected.items()
        if row.get(key) != value
    }
    if mismatches:
        raise ReportEvidenceError(f"frozen N32 failure evidence drift: {mismatches}")


def _validate_old_samples(
    summary: Mapping[str, str],
    samples: CsvTable,
) -> None:
    failure_step = _integer(
        summary["first_failure_step"], label="old N32 failure step"
    )
    steps = [_integer(row["step"], label="old N32 sample step") for row in samples.rows]
    if steps != list(range(failure_step + 1)):
        raise ReportEvidenceError(
            f"old N32 sample steps are not 0..{failure_step}: {steps}"
        )
    if len(samples.rows) != 5:
        raise ReportEvidenceError("old N32 resource decision was not based on five samples")
    rss = [
        _finite_float(row["current_rss_bytes"], label="old N32 current RSS")
        for row in samples.rows
    ]
    if rss[0] != _finite_float(
        summary["current_rss_initial_bytes"], label="old initial RSS"
    ) or rss[-1] != _finite_float(
        summary["current_rss_final_bytes"], label="old final RSS"
    ):
        raise ReportEvidenceError("old N32 sample and summary RSS values differ")


def _validate_analysis(
    project_root: Path,
    configuration: Mapping[str, Any],
    config_sha256: str,
    summary: Mapping[str, Any],
    status: str,
    run_metrics: CsvTable,
    variant_summary: CsvTable,
    diagnostics_overhead: CsvTable,
    archive_assessment: CsvTable,
    graph_sentinel: CsvTable,
    resource_gates: CsvTable,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    if summary.get("schema_version") != "sph-pio-poc.stage01dr.analysis-summary.v1":
        raise ReportEvidenceError("unknown Stage 01D-R analysis-summary schema")
    expected_summary = {
        "status": status,
        "old_stage01d_status": "V2_FAIL",
        "config_sha256": config_sha256,
        "qualifying_run_count": 18,
        "all_worker_count": 22,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise ReportEvidenceError(
                f"analysis summary mismatch for {key}: "
                f"{summary.get(key)!r} != {expected!r}"
            )
    boolean_summary_fields = (
        "confirmed_linear",
        "ambiguous_growth",
        "hard_complete",
        "variant_b_overhead_pass",
        "archive_localized",
        "archive_overhead_bounded",
        "numeric_regression_pass",
        "graph_sentinel_pass",
        "process_reclamation_pass",
        "retention_fix_applied",
        "retention_fix_contract_pass",
    )
    for key in boolean_summary_fields:
        if not isinstance(summary.get(key), bool):
            raise ReportEvidenceError(
                f"analysis summary field {key} must be boolean"
            )
    git_hash = str(summary.get("git_hash", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", git_hash):
        raise ReportEvidenceError("analysis summary has an invalid git hash")
    if _git(project_root, "cat-file", "-t", git_hash) != "commit":
        raise ReportEvidenceError("analysis git commit is unavailable")

    expected_runs = {
        (resolution, variant, repeat)
        for resolution in (16, 32)
        for variant in ("A", "B", "C")
        for repeat in (1, 2, 3)
    }
    observed_runs: set[tuple[int, str, int]] = set()
    run_identity_by_id: dict[str, tuple[int, str, int]] = {}
    for row in run_metrics.rows:
        identity = (
            _integer(row["resolution"], label="run resolution"),
            row["variant"],
            _integer(row["repeat"], label="run repeat"),
        )
        if identity in observed_runs:
            raise ReportEvidenceError(f"duplicate run metric identity: {identity}")
        observed_runs.add(identity)
        run_id = row["run_id"]
        if run_id in run_identity_by_id:
            raise ReportEvidenceError(f"duplicate run metric ID: {run_id}")
        run_identity_by_id[run_id] = identity
        if row["config_hash"] != config_sha256 or row["git_hash"] != git_hash:
            raise ReportEvidenceError(
                f"run metric provenance mismatch: {row['run_id']}"
            )
        memory_path = _resolve_project_path(
            project_root,
            row["memory_sample_path"],
            label=f"raw memory trace for {row['run_id']}",
        )
        raw_summary_path = _resolve_project_path(
            project_root,
            row["summary_path"],
            label=f"raw worker summary for {row['run_id']}",
        )
        raw_exit_path = _resolve_project_path(
            project_root,
            row["process_exit_path"],
            label=f"raw process-exit evidence for {row['run_id']}",
        )
        raw_summary = _read_json(
            raw_summary_path,
            label=f"raw worker summary for {row['run_id']}",
        )
        raw_exit = _read_json(
            raw_exit_path,
            label=f"raw process-exit evidence for {row['run_id']}",
        )
        for label, raw in (("summary", raw_summary), ("process exit", raw_exit)):
            if raw.get("run_id") != row["run_id"]:
                raise ReportEvidenceError(
                    f"raw {label} run identity mismatch: {row['run_id']}"
                )
            if raw.get("config_hash") != config_sha256 or raw.get(
                "git_hash"
            ) != git_hash:
                raise ReportEvidenceError(
                    f"raw {label} provenance mismatch: {row['run_id']}"
                )
        if (
            _integer(raw_summary.get("resolution"), label="raw summary resolution")
            != identity[0]
            or str(raw_summary.get("variant")) != identity[1]
        ):
            raise ReportEvidenceError(
                f"raw worker summary identity mismatch: {row['run_id']}"
            )
        if (
            _integer(raw_exit.get("resolution"), label="raw exit resolution")
            != identity[0]
            or str(raw_exit.get("variant")) != identity[1]
            or _integer(raw_exit.get("repeat"), label="raw exit repeat")
            != identity[2]
        ):
            raise ReportEvidenceError(
                f"raw process-exit identity mismatch: {row['run_id']}"
            )
        memory_rows = _read_jsonl(
            memory_path,
            label=f"raw memory trace for {row['run_id']}",
        )
        if any(item.get("run_id") != row["run_id"] for item in memory_rows):
            raise ReportEvidenceError(
                f"raw memory trace identity mismatch: {row['run_id']}"
            )
        indices = [
            _integer(item.get("sample_index"), label="memory sample index")
            for item in memory_rows
        ]
        if indices != list(range(len(indices))):
            raise ReportEvidenceError(
                f"raw memory sample indices are not contiguous: {row['run_id']}"
            )
        worker_config_value = raw_summary.get("worker_config_path")
        if worker_config_value:
            worker_config = _read_json(
                _resolve_project_path(
                    project_root,
                    worker_config_value,
                    label=f"worker config for {row['run_id']}",
                ),
                label=f"worker config for {row['run_id']}",
            )
            if (
                worker_config.get("run_id") != row["run_id"]
                or worker_config.get("config_sha256") != config_sha256
                or worker_config.get("git_hash") != git_hash
            ):
                raise ReportEvidenceError(
                    f"worker config provenance mismatch: {row['run_id']}"
                )
        numerical_path = row.get("numerical_path", "")
        if numerical_path:
            _resolve_project_path(
                project_root,
                numerical_path,
                label=f"numerical evidence for {row['run_id']}",
            )
        archive_path = row.get("archive_path", "")
        if archive_path:
            _resolve_project_path(
                project_root,
                archive_path,
                label=f"archive evidence for {row['run_id']}",
            )
        for key in (
            "completion_pass",
            "provenance_pass",
            "sampling_coverage_pass",
            "process_reclamation_pass",
            "numerical_pass",
            "rss_slope_limit_pass",
            "rss_quartile_limit_pass",
        ):
            _parse_bool(row[key], label=f"{row['run_id']} {key}")
    if observed_runs != expected_runs:
        raise ReportEvidenceError(
            f"qualifying run identities differ: {sorted(observed_runs)}"
        )

    expected_variants = {
        (resolution, variant)
        for resolution in (16, 32)
        for variant in ("A", "B", "C")
    }
    observed_variants = {
        (
            _integer(row["resolution"], label="variant resolution"),
            row["variant"],
        )
        for row in variant_summary.rows
    }
    if observed_variants != expected_variants or len(variant_summary.rows) != 6:
        raise ReportEvidenceError("variant summary does not cover N16/N32 A/B/C")
    if {
        _integer(row["resolution"], label="overhead resolution")
        for row in diagnostics_overhead.rows
    } != {16, 32} or len(diagnostics_overhead.rows) != 2:
        raise ReportEvidenceError("diagnostics overhead must contain N16 and N32")

    archive_ids: set[str] = set()
    for row in archive_assessment.rows:
        run_id = row["run_id"]
        if run_id in archive_ids:
            raise ReportEvidenceError(f"duplicate archive assessment ID: {run_id}")
        archive_ids.add(run_id)
        identity = (
            _integer(row["resolution"], label="archive resolution"),
            row["variant"],
            _integer(row["repeat"], label="archive repeat"),
        )
        if run_identity_by_id.get(run_id) != identity:
            raise ReportEvidenceError(
                f"archive assessment identity mismatch: {run_id}"
            )
        for key in (
            "solver_completed",
            "archive_only_failure",
            "archive_localized",
            "archive_overhead_bounded",
        ):
            _parse_bool(row[key], label=f"{run_id} {key}")
    if archive_ids != set(run_identity_by_id) or len(archive_assessment.rows) != 18:
        raise ReportEvidenceError(
            "archive assessment does not cover all 18 qualifying runs"
        )
    archive_localized = all(
        _parse_bool(row["archive_localized"], label="archive localized")
        for row in archive_assessment.rows
    )
    archive_bounded = all(
        _parse_bool(
            row["archive_overhead_bounded"], label="archive overhead bounded"
        )
        for row in archive_assessment.rows
    )
    if archive_localized != summary["archive_localized"]:
        raise ReportEvidenceError(
            "analysis summary and archive assessment disagree on localization"
        )
    if archive_bounded != summary["archive_overhead_bounded"]:
        raise ReportEvidenceError(
            "analysis summary and archive assessment disagree on bounded overhead"
        )

    sentinel_modes = {row["mode"] for row in graph_sentinel.rows}
    if sentinel_modes != {"no_grad", "grad_enabled"} or len(graph_sentinel.rows) != 2:
        raise ReportEvidenceError("graph sentinel must contain both registered modes")

    gate_ids = tuple(row["gate"] for row in resource_gates.rows)
    if set(gate_ids) != set(EXPECTED_GATE_IDS) or len(gate_ids) != len(
        EXPECTED_GATE_IDS
    ):
        raise ReportEvidenceError(f"resource gate IDs differ: {gate_ids}")
    status_rows = [row for row in resource_gates.rows if row["gate"] == "STATUS"]
    if len(status_rows) != 1 or status_rows[0]["observed"] != status:
        raise ReportEvidenceError("STATUS gate differs from resource status")
    if status_rows[0]["severity"] != "STATUS":
        raise ReportEvidenceError("STATUS gate severity is not STATUS")
    if not _parse_bool(status_rows[0]["passed"], label="gate STATUS"):
        raise ReportEvidenceError("STATUS gate must have passed=True")

    summary_gate_checks = {
        "REG": "numeric_regression_pass",
        "SENTINEL": "graph_sentinel_pass",
        "J": "process_reclamation_pass",
    }
    by_gate = {row["gate"]: row for row in resource_gates.rows}
    if _parse_bool(by_gate["I"]["passed"], label="gate I") != bool(
        archive_localized and archive_bounded
    ):
        raise ReportEvidenceError(
            "archive assessment and gate I disagree"
        )
    for gate, summary_key in summary_gate_checks.items():
        if _parse_bool(by_gate[gate]["passed"], label=f"gate {gate}") != bool(
            summary.get(summary_key)
        ):
            raise ReportEvidenceError(
                f"analysis summary and gate {gate} disagree"
            )

    figure_values = summary.get("figures")
    if not isinstance(figure_values, list) or len(figure_values) != 3:
        raise ReportEvidenceError("analysis summary must identify three figures")
    figures = tuple(
        _resolve_project_path(project_root, value, label="Stage 01D-R figure")
        for value in figure_values
    )
    if any(path.suffix.lower() != ".png" for path in figures):
        raise ReportEvidenceError("Stage 01D-R figures must be PNG files")

    fix_configuration = _nested(configuration, "retention_fix_evidence")
    retention_fix = bool(summary["retention_fix_applied"])
    if retention_fix != bool(fix_configuration["applied"]):
        raise ReportEvidenceError(
            "analysis summary and preregistered retention-fix flag disagree"
        )
    fix_contract = bool(summary["retention_fix_contract_pass"])
    required_fix_fields = (
        "permitted_class",
        "failing_reproducer_path",
        "regression_test_path",
        "before_curve_path",
        "after_curve_path",
        "separate_commit",
    )
    fix_artifacts: list[Path] = []
    if retention_fix:
        values_present = all(
            str(fix_configuration.get(key, "")).strip()
            for key in required_fix_fields
        )
        paths_valid = values_present
        for key in required_fix_fields[1:5]:
            candidate = (
                project_root / str(fix_configuration.get(key, ""))
            ).resolve()
            try:
                candidate.relative_to(project_root)
            except ValueError:
                paths_valid = False
                continue
            if not candidate.is_file():
                paths_valid = False
                continue
            fix_artifacts.append(candidate)
        commit_valid = False
        if values_present:
            completed = subprocess.run(
                (
                    "git",
                    "cat-file",
                    "-e",
                    f"{fix_configuration['separate_commit']}^{{commit}}",
                ),
                cwd=project_root,
                check=False,
                capture_output=True,
            )
            commit_valid = completed.returncode == 0
        observed_contract = bool(paths_valid and commit_valid)
        if fix_contract != observed_contract:
            raise ReportEvidenceError(
                "analysis summary and retention-fix artifact contract disagree"
            )
    elif not fix_contract:
        raise ReportEvidenceError(
            "unapplied retention fix must have a vacuously passing contract"
        )

    if status == "RESOURCE_PASS_AFTER_RETENTION_FIX" and not (
        retention_fix and fix_contract
    ):
        raise ReportEvidenceError(
            "AFTER_RETENTION_FIX status lacks a complete configured fix contract"
        )
    if status == "RESOURCE_PASS_ALLOCATOR_PLATEAU" and retention_fix:
        raise ReportEvidenceError(
            "allocator-plateau status cannot include an applied retention fix"
        )
    return figures, tuple(fix_artifacts)


def _line_number(text: str, needle: str, *, label: str) -> int:
    matches = [
        index
        for index, line in enumerate(text.splitlines(), start=1)
        if needle in line
    ]
    if not matches:
        raise ReportEvidenceError(f"static-audit anchor is missing: {label}")
    return matches[0]


def _cite(path: Path, line: int, root: Path) -> str:
    return f"`{_relative(path, root)}:{line}`"


def _static_retention_findings(
    project_root: Path,
) -> tuple[StaticFinding, ...]:
    solver_root = project_root / "01_solver" / "dynamic_solver"
    experiment_root = (
        project_root / "06_experiments" / "stage_01d_fixed_physics_tgv"
    )
    required = {
        "runner": experiment_root / "run_dynamic_verification.py",
        "rollout": solver_root / "periodic_rollout.py",
        "diagnostics": solver_root / "diagnostics.py",
        "state": solver_root / "state.py",
        "acceleration": solver_root / "acceleration.py",
        "reports": experiment_root / "generate_stage01d_reports.py",
    }
    source: dict[str, str] = {}
    for key, path in required.items():
        if not path.is_file():
            raise ReportEvidenceError(f"static-audit source is missing: {path}")
        source[key] = path.read_text(encoding="utf-8")
    scope_files = sorted(solver_root.glob("*.py")) + sorted(
        experiment_root.glob("*.py")
    )
    scope_text = "\n".join(path.read_text(encoding="utf-8") for path in scope_files)
    retain_graph_count = scope_text.count("retain_graph")
    hook_count = sum(
        scope_text.count(pattern)
        for pattern in (
            "register_forward_hook",
            "register_backward_hook",
            "register_full_backward_hook",
            "register_hook",
        )
    )
    partial_count = scope_text.count("functools.partial") + scope_text.count(
        "from functools import partial"
    )
    yield_count = 0
    for path in scope_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        yield_count += sum(
            isinstance(node, (ast.Yield, ast.YieldFrom)) for node in ast.walk(tree)
        )
    if retain_graph_count or hook_count or partial_count or yield_count:
        raise ReportEvidenceError(
            "static retention primitives changed; refresh the Stage 01D-R audit"
        )

    runner = required["runner"]
    rollout = required["rollout"]
    diagnostics = required["diagnostics"]
    state = required["state"]
    acceleration = required["acceleration"]
    reports = required["reports"]
    runner_text = source["runner"]
    rollout_text = source["rollout"]
    diagnostics_text = source["diagnostics"]
    state_text = source["state"]
    acceleration_text = source["acceleration"]
    reports_text = source["reports"]

    lines = {
        "no_grad": _line_number(runner_text, "with torch.no_grad():", label="no_grad"),
        "prepare": _line_number(
            runner_text,
            "state, evaluation = prepare_dynamic_state",
            label="initial prepare",
        ),
        "archive_lists": _line_number(
            runner_text,
            "archive_positions: list[np.ndarray]",
            label="archive list",
        ),
        "archive_append": _line_number(
            runner_text,
            "archive_positions.append(",
            label="archive append",
        ),
        "result": _line_number(
            runner_text,
            "result = explicit_midpoint_dynamic_step(",
            label="step result",
        ),
        "previous": _line_number(
            runner_text, "previous_position = state.positions", label="previous state"
        ),
        "traceback": _line_number(
            runner_text, "except Exception as error:", label="outer traceback"
        ),
        "observer_records": _line_number(
            rollout_text,
            "records: list[dict[str, Any]]",
            label="observer records",
        ),
        "observer_append": _line_number(
            rollout_text, "records.append(record)", label="observer append"
        ),
        "midpoint": _line_number(
            rollout_text, "midpoint_state = synchronized.with_updates(", label="midpoint"
        ),
        "step_result": _line_number(
            rollout_text, "class DynamicStepResult:", label="step result class"
        ),
        "tensor_float": _line_number(
            diagnostics_text, "def _tensor_float", label="diagnostic detach"
        ),
        "diagnostic_no_grad": _line_number(
            diagnostics_text, "with torch.no_grad():", label="diagnostic no_grad"
        ),
        "validator": _line_number(
            diagnostics_text,
            "def validate_serializable_record",
            label="diagnostic validator",
        ),
        "state_graph": _line_number(
            state_text,
            "The class validates but never detaches",
            label="state graph contract",
        ),
        "force_evaluation": _line_number(
            acceleration_text, "class ForceEvaluation:", label="force evaluation"
        ),
        "report_separate": _line_number(
            reports_text,
            "This module is deliberately a read-only post-processor",
            label="separate report process",
        ),
    }
    if "del result" in runner_text:
        raise ReportEvidenceError(
            "frozen Stage 01D result lifetime changed; refresh static audit"
        )

    return (
        StaticFinding(
            1,
            "普通前向 TGV 是否完整位于 torch.no_grad()",
            "NO（accepted RK2 step 为 YES）",
            "保护边界不完整；正式 float 输入未证明 graph 泄漏",
            f"{_cite(runner, lines['prepare'], project_root)}；"
            f"{_cite(runner, lines['no_grad'], project_root)}；"
            f"{_cite(state, lines['state_graph'], project_root)}",
            "用 requires-grad 哨兵记录 prepare、step、diagnostics 的 grad-enabled 状态。",
        ),
        StaticFinding(
            2,
            "是否存在 retain_graph=True",
            "NO",
            "未发现该保留源",
            f"两个审计目录 AST/文本扫描为 0；AD 调用未设置 retain_graph。",
            "AST 回归拒绝 backward/autograd 调用中的 retain_graph=True。",
        ),
        StaticFinding(
            3,
            "是否向列表、字典、闭包或全局变量保存 tensor",
            "YES（通用 observer）；正式 worker 为 NO",
            "潜在 O(sample)；当前正式路径未触发",
            f"{_cite(rollout, lines['observer_records'], project_root)}；"
            f"{_cite(rollout, lines['observer_append'], project_root)}",
            "observer 每步返回 positions tensor，比较 live tensor count 与纯标量 observer。",
        ),
        StaticFinding(
            4,
            "trajectory recorder 是否保存每步完整状态",
            "NO（完整 state）；短任务每步保存四个主要场",
            "checkpoint 数有界，但 NumPy payload 会累计",
            f"{_cite(runner, lines['archive_lists'], project_root)}；"
            f"{_cite(runner, lines['archive_append'], project_root)}",
            "比较 archive off、buffer only、stack、compression 四阶段内存。",
        ),
        StaticFinding(
            5,
            "是否保存中点状态",
            "NO（midpoint state）；midpoint evaluation 为 YES",
            "单步有界引用",
            f"{_cite(rollout, lines['midpoint'], project_root)}；"
            f"{_cite(rollout, lines['step_result'], project_root)}",
            "对 midpoint state/evaluation 建立 weakref，检查 del result 前后释放。",
        ),
        StaticFinding(
            6,
            "是否保存 edge index、pair displacement 或 pair force",
            "YES（运行时有界；无轨迹 archive）",
            "三套 evaluation 可提高平台与瞬时峰值",
            f"{_cite(acceleration, lines['force_evaluation'], project_root)}；"
            f"{_cite(rollout, lines['step_result'], project_root)}",
            "跟踪 row/displacement/force weakref 与 unique-storage bytes。",
        ),
        StaticFinding(
            7,
            "diagnostics 是否在写 CSV 前 detach 并转成 Python 标量",
            "YES",
            "未发现诊断记录持有 tensor",
            f"{_cite(diagnostics, lines['tensor_float'], project_root)}；"
            f"{_cite(diagnostics, lines['diagnostic_no_grad'], project_root)}；"
            f"{_cite(diagnostics, lines['validator'], project_root)}",
            "用 grad-bearing 输入生成 record，断言值域仅含 JSON 标量并写临时 CSV。",
        ),
        StaticFinding(
            8,
            "是否注册未移除的 forward/backward hooks",
            "NO",
            "未发现该保留源",
            "审计目录 hook 注册调用扫描为 0。",
            "AST 回归禁止 hook 注册，或要求 RemovableHandle 在 probe 后清零。",
        ),
        StaticFinding(
            9,
            "NPZ 是否在运行中积累所有状态",
            "YES（selected checkpoints）；长轨迹不是所有 solver steps",
            "有界 NumPy 历史与 archive 阶段副本",
            f"{_cite(runner, lines['archive_lists'], project_root)}；"
            f"{_cite(runner, lines['archive_append'], project_root)}",
            "记录每个 array.nbytes，并隔离 np.stack 与压缩阶段 RSS。",
        ),
        StaticFinding(
            10,
            "report generator 是否在 solver 子进程内执行",
            "NO",
            "solver 与报告内存隔离",
            f"{_cite(reports, lines['report_separate'], project_root)}",
            "spy worker argv，并断言 rollout 前后报告路径保持不存在/mtime 不变。",
        ),
        StaticFinding(
            11,
            "accepted step 后旧 state、中点和 force result 是否仍被引用",
            "YES（一个 step 的有界引用）",
            "确认的 O(E) 保留，不是 O(step·E) 历史",
            f"{_cite(runner, lines['previous'], project_root)}；"
            f"{_cite(runner, lines['result'], project_root)}；runner 无 del result",
            "提取 next state/end 后比较 del result, previous_position 前后的 weakref。",
        ),
        StaticFinding(
            12,
            "是否有 generator、partial 或 traceback 保留大型局部变量",
            "YES（异常恢复期 traceback）；generator/partial 为 NO",
            "仅晚期异常路径暂时持有 frame，不解释正常逐步增长",
            f"{_cite(runner, lines['traceback'], project_root)}；"
            "审计目录 Yield/partial 扫描为 0",
            "晚期注入 archive 异常，run_one 返回及 gc.collect 后检查 tensor weakref。",
        ),
    )


def _md(value: Any) -> str:
    if value is None or str(value) == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _markdown_table(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[tuple[str, str]],
) -> str:
    if not rows:
        return "无记录。"
    header = "| " + " | ".join(label for _, label in columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    body = [
        "| "
        + " | ".join(_md(row.get(key)) for key, _ in columns)
        + " |"
        for row in rows
    ]
    return "\n".join((header, divider, *body))


def _format_bytes(value: Any) -> str:
    number = _finite_float(value, label="byte value")
    return f"{number:,.0f} B ({number / 1.0e6:.3f} MB)"


def _format_slope(value: Any) -> str:
    number = _finite_float(value, label="slope")
    return f"{number:,.3f} B/step"


def _format_fraction(value: Any) -> str:
    number = _finite_float(value, label="fraction")
    return f"{100.0 * number:.3f}%"


def _pass_text(value: Any) -> str:
    return "PASS" if _parse_bool(value, label="reported pass") else "FAIL"


def _gate_by_id(evidence: Evidence, gate_id: str) -> dict[str, str]:
    selected = [row for row in evidence.resource_gates.rows if row["gate"] == gate_id]
    if len(selected) != 1:
        raise ReportEvidenceError(f"expected exactly one gate {gate_id}")
    return selected[0]


def _static_rows(evidence: Evidence) -> list[dict[str, Any]]:
    return [
        {
            "number": finding.number,
            "question": finding.question,
            "answer": finding.answer,
            "assessment": finding.retention_assessment,
            "evidence": finding.evidence,
        }
        for finding in evidence.static_findings
    ]


def _reproducer_rows(evidence: Evidence) -> list[dict[str, Any]]:
    return [
        {
            "number": finding.number,
            "finding": finding.answer,
            "reproducer": finding.minimal_reproducer,
        }
        for finding in evidence.static_findings
    ]


def _old_sample_rows(evidence: Evidence) -> list[dict[str, Any]]:
    return [
        {
            "step": row["step"],
            "time": row["time"],
            "current_rss": _format_bytes(row["current_rss_bytes"]),
            "peak_rss": _format_bytes(row["peak_rss_bytes"]),
            "edges": row["neighbor_edge_count"],
            "finite": row["state_all_finite"],
        }
        for row in evidence.old_n32_samples.rows
    ]


def _run_rows(evidence: Evidence) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected = sorted(
        evidence.run_metrics.rows,
        key=lambda row: (
            _integer(row["resolution"], label="run resolution"),
            row["variant"],
            _integer(row["repeat"], label="run repeat"),
        ),
    )
    for row in selected:
        rows.append(
            {
                "run_id": f"`{row['run_id']}`",
                "N": row["resolution"],
                "variant": row["variant"],
                "repeat": row["repeat"],
                "complete": _pass_text(row["completion_pass"]),
                "numeric": _pass_text(row["numerical_pass"]),
                "rss_first": _format_bytes(
                    row["first_quartile_rss_median_bytes"]
                ),
                "rss_final": _format_bytes(
                    row["final_quartile_rss_median_bytes"]
                ),
                "rss_delta": _format_bytes(row["final_minus_first_rss_bytes"]),
                "rss_slope": _format_slope(row["rss_theil_sen_bytes_per_step"]),
                "ci": (
                    "["
                    + _format_slope(
                        row["rss_bootstrap_ci95_lower_bytes_per_step"]
                    )
                    + ", "
                    + _format_slope(
                        row["rss_bootstrap_ci95_upper_bytes_per_step"]
                    )
                    + "]"
                ),
                "tensor_count": f"{float(row['tensor_count_theil_sen_per_step']):.6g}/step",
                "tensor_bytes": _format_slope(
                    row["tensor_bytes_theil_sen_per_step"]
                ),
                "tracemalloc": _format_slope(
                    row["tracemalloc_theil_sen_bytes_per_step"]
                ),
                "gc": f"{float(row['gc_object_theil_sen_per_step']):.6g}/step",
                "step_time": f"{float(row['mean_step_wall_seconds']):.6f} s",
                "edges": row["final_edge_count"],
            }
        )
    return rows


def _variant_rows(evidence: Evidence) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected = sorted(
        evidence.variant_summary.rows,
        key=lambda row: (
            _integer(row["resolution"], label="variant resolution"),
            row["variant"],
        ),
    )
    for row in selected:
        rows.append(
            {
                "N": row["resolution"],
                "variant": row["variant"],
                "complete": f"{row['completed_count']}/{row['repeat_count']}",
                "numeric": _pass_text(row["all_numerical_pass"]),
                "sampling": _pass_text(row["all_sampling_pass"]),
                "reclaimed": _pass_text(row["all_reclaimed"]),
                "final_rss": _format_bytes(
                    row["median_final_quartile_rss_bytes"]
                ),
                "rss_per_particle": _format_bytes(
                    float(row["median_final_quartile_rss_bytes"])
                    / (_integer(row["resolution"], label="variant N") ** 2)
                ),
                "rss_slope": _format_slope(
                    row["median_rss_slope_bytes_per_step"]
                ),
                "rss_positive": row["rss_significant_positive_repeat_count"],
                "tensor_count_positive": row[
                    "tensor_count_positive_repeat_count"
                ],
                "tensor_bytes_positive": row[
                    "tensor_bytes_positive_repeat_count"
                ],
                "trace_positive": row["tracemalloc_positive_repeat_count"],
                "gc_positive": row["gc_object_positive_repeat_count"],
            }
        )
    return rows


def _overhead_rows(evidence: Evidence) -> list[dict[str, Any]]:
    return [
        {
            "N": row["resolution"],
            "A": _format_bytes(row["a_median_final_quartile_rss_bytes"]),
            "B": _format_bytes(row["b_median_final_quartile_rss_bytes"]),
            "extra": _format_bytes(row["b_minus_a_bounded_extra_bytes"]),
            "fraction": _format_fraction(row["b_minus_a_fraction_of_a"]),
            "pass": _pass_text(row["pass"]),
        }
        for row in sorted(
            evidence.diagnostics_overhead.rows,
            key=lambda item: _integer(item["resolution"], label="overhead N"),
        )
    ]


def _archive_rows(evidence: Evidence) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sorted(
        (
            item
            for item in evidence.run_metrics.rows
            if item["variant"] == "C"
        ),
        key=lambda item: (
            _integer(item["resolution"], label="archive N"),
            _integer(item["repeat"], label="archive repeat"),
        ),
    ):
        rows.append(
            {
                "N": row["resolution"],
                "repeat": row["repeat"],
                "writes": row["archive_write_count"],
                "checkpoints": row["archive_checkpoint_count"],
                "archive_delta": _format_bytes(
                    row["archive_current_rss_delta_bytes"]
                ),
                "solver_quartile": _pass_text(row["rss_quartile_limit_pass"]),
                "solver_slope": _pass_text(row["rss_slope_limit_pass"]),
                "path": f"`{row['archive_path']}`",
            }
        )
    return rows


def _sentinel_rows(evidence: Evidence) -> list[dict[str, Any]]:
    return [
        {
            "mode": row["mode"],
            "status": row["status"],
            "graph_nodes": row["reachable_grad_graph_node_count"],
            "position_grad_fn": row["final_positions_has_grad_fn"],
            "velocity_grad_fn": row["final_velocities_has_grad_fn"],
            "rss": _format_bytes(row["final_current_rss_bytes"]),
            "live_tensors": row["final_live_tensor_count"],
            "tensor_bytes": _format_bytes(
                row["final_live_tensor_unique_storage_bytes"]
            ),
            "reclaimed": _pass_text(row["process_reclaimed"]),
            "identity": _pass_text(row["identity_pass"]),
        }
        for row in evidence.graph_sentinel.rows
    ]


def _gate_rows(evidence: Evidence) -> list[dict[str, Any]]:
    order = {gate: index for index, gate in enumerate(EXPECTED_GATE_IDS)}
    return [
        {
            "gate": row["gate"],
            "check": row["check"],
            "pass": _pass_text(row["passed"]),
            "observed": row["observed"],
            "threshold": row["threshold"],
            "source": f"`{row['source']}`",
            "severity": row["severity"],
            "detail": row["detail"],
        }
        for row in sorted(
            evidence.resource_gates.rows,
            key=lambda item: order[item["gate"]],
        )
    ]


def _n16_n32_rows(evidence: Evidence) -> list[dict[str, Any]]:
    by_key = {
        (int(row["resolution"]), row["variant"]): row
        for row in evidence.variant_summary.rows
    }
    rows: list[dict[str, Any]] = []
    for variant in ("A", "B", "C"):
        n16 = by_key[(16, variant)]
        n32 = by_key[(32, variant)]
        rss16 = float(n16["median_final_quartile_rss_bytes"])
        rss32 = float(n32["median_final_quartile_rss_bytes"])
        rows.append(
            {
                "variant": variant,
                "N16": _format_bytes(rss16),
                "N32": _format_bytes(rss32),
                "N16_per_particle": _format_bytes(rss16 / 256.0),
                "N32_per_particle": _format_bytes(rss32 / 1024.0),
                "N32_over_N16": f"{rss32 / rss16:.4f}",
                "N16_slope": _format_slope(
                    n16["median_rss_slope_bytes_per_step"]
                ),
                "N32_slope": _format_slope(
                    n32["median_rss_slope_bytes_per_step"]
                ),
            }
        )
    return rows


def _variant_protocol_rows(evidence: Evidence) -> list[dict[str, Any]]:
    variants = _nested(evidence.configuration, "variants")
    qualifying_steps = _nested(
        evidence.configuration, "resolutions", 32, "steps"
    )
    rows: list[dict[str, Any]] = []
    for variant in ("A", "B", "C", "D"):
        value = variants[variant]
        rows.append(
            {
                "variant": variant,
                "name": value["name"],
                "no_grad": value.get("torch_no_grad", "mode comparison"),
                "diagnostics": value.get(
                    "stage01d_scalar_diagnostics", "sentinel-only"
                ),
                "state_checkpoints": value.get(
                    "retained_full_state_checkpoints", False
                ),
                "archive": value.get("final_npz_archive", False),
                "steps": value.get("steps", qualifying_steps),
                "qualification": value.get("formal_resource_qualification", True),
            }
        )
    return rows


def _status_interpretation(evidence: Evidence) -> str:
    descriptions = {
        "RESOURCE_PASS_ALLOCATOR_PLATEAU": (
            "全部预登记完成性、数值、拓扑、post-warm-up RSS、tensor、"
            "diagnostics、archive 与子进程回收门均通过，且未应用项目侧"
            "保留修复；证据支持一次性分配/缓存后进入有界平台。"
        ),
        "RESOURCE_PASS_AFTER_RETENTION_FIX": (
            "已通过独立提交且带 before/after 证据的项目侧保留修复，修复后"
            "满足全部预登记资源门。"
        ),
        "RESOURCE_CONDITIONAL": (
            "solver post-warm-up 行为有界，但 diagnostics 或 archive 存在已隔离、"
            "可复现且超过预登记开销界限的成本。"
        ),
        "RESOURCE_FAIL_LINEAR_GROWTH": (
            "至少一个 N32 qualifying variant 在重复中确认 post-warm-up RSS、"
            "live tensor 或 Python memory 持续增长。"
        ),
        "RESOURCE_FAIL_UNRESOLVED": (
            "证据不完整、冲突或重复性不足，尚不能区分 allocator 缓存与"
            "项目侧持久引用。"
        ),
    }
    return descriptions[evidence.resource_status]


def _stage01d2_decision(evidence: Evidence) -> tuple[str, str]:
    if evidence.resource_status in {
        "RESOURCE_PASS_ALLOCATOR_PLATEAU",
        "RESOURCE_PASS_AFTER_RETENTION_FIX",
    }:
        return (
            "MAY_PREPARE_NOT_STARTED",
            "允许仅起草一个新的 Stage 01D2 V2 预注册协议；本报告不启动该协议。",
        )
    if evidence.resource_status == "RESOURCE_CONDITIONAL":
        return (
            "NOT_YET",
            "需先处理或正式接受已隔离的 diagnostics/archive 成本，当前不建立 Stage 01D2。",
        )
    return (
        "PROHIBITED",
        "资源重新资格未通过，当前不得建立或启动新的 Stage 01D2 V2 协议。",
    )


def _fix_text(evidence: Evidence) -> str:
    configured = evidence.retention_fix_evidence
    rationale = str(configured.get("rationale", "")).strip()
    if not bool(evidence.analysis_summary["retention_fix_applied"]):
        return (
            "本次分析记录 `retention_fix_applied=false`。未修改密度、EOS、压力、"
            "黏性、H/dx、dt、nu、c_s、RK2、布局或守恒结构，也没有可报告的"
            "before/after 修复曲线。静态审计发现的有界引用仅进入诊断假设，"
            "没有被事后改写成已修复缺陷。预登记理由："
            + (rationale or "未填写")
        )

    path_keys = {
        "failing_reproducer_path",
        "regression_test_path",
        "before_curve_path",
        "after_curve_path",
    }
    rows: list[dict[str, str]] = []
    for key in (
        "permitted_class",
        "failing_reproducer_path",
        "regression_test_path",
        "before_curve_path",
        "after_curve_path",
        "separate_commit",
        "rationale",
    ):
        raw = str(configured.get(key, "")).strip()
        if key in path_keys and raw:
            candidate = (evidence.project_root / raw).resolve()
            try:
                rendered = f"`{candidate.relative_to(evidence.project_root).as_posix()}`"
            except ValueError:
                rendered = "`<OUTSIDE_PROJECT>`"
        elif key == "separate_commit" and raw:
            rendered = f"`{raw}`"
        else:
            rendered = raw or "未提供"
        rows.append({"field": key, "value": rendered})
    contract = (
        "PASS"
        if bool(evidence.analysis_summary["retention_fix_contract_pass"])
        else "FAIL"
    )
    return (
        "分析记录 `retention_fix_applied=true`；配置证据契约为 **"
        + contract
        + "**。before/after 与独立提交证据如下：\n\n"
        + _markdown_table(
            rows,
            (("field", "field"), ("value", "value")),
        )
    )


def _evidence_index(evidence: Evidence, paths: Iterable[Path]) -> str:
    unique = sorted(
        {path.resolve() for path in paths},
        key=lambda path: _relative(path, evidence.project_root),
    )
    rows: list[dict[str, Any]] = []
    for path in unique:
        _require_inside(path, evidence.project_root, label="report evidence")
        if not path.is_file():
            raise ReportEvidenceError(
                f"report evidence disappeared: {_relative(path, evidence.project_root)}"
            )
        rows.append(
            {
                "path": f"`{_relative(path, evidence.project_root)}`",
                "sha256": f"`{_sha256(path)}`",
                "bytes": path.stat().st_size,
            }
        )
    return _markdown_table(
        rows,
        (("path", "path"), ("sha256", "SHA-256"), ("bytes", "bytes")),
    )


def _base_paths(evidence: Evidence) -> list[Path]:
    paths = [
        evidence.config_path,
        evidence.manifest.path,
        evidence.old_status_path,
        evidence.old_run_summary.path,
        evidence.old_n32_samples.path,
        evidence.old_failure_path,
        evidence.analysis_summary_path,
        evidence.resource_status_path,
        evidence.resource_gates.path,
        evidence.archive_assessment.path,
        evidence.generator_path,
    ]
    paths.extend(evidence.retention_fix_artifacts)
    return paths


def _boundary_statement() -> str:
    return (
        "Stage 01D 的既有状态仍为 **`V2_FAIL`**。Stage 01D-R 只重新评价"
        "资源行为，不回写旧状态；V3 与 Stage 02 均未开始。"
    )


def _render_code_retention(evidence: Evidence) -> str:
    source_paths = [
        evidence.project_root / "01_solver/dynamic_solver/periodic_rollout.py",
        evidence.project_root / "01_solver/dynamic_solver/acceleration.py",
        evidence.project_root / "01_solver/dynamic_solver/diagnostics.py",
        evidence.project_root / "01_solver/dynamic_solver/state.py",
        evidence.project_root
        / "06_experiments/stage_01d_fixed_physics_tgv/run_dynamic_verification.py",
        evidence.project_root
        / "06_experiments/stage_01d_fixed_physics_tgv/generate_stage01d_reports.py",
    ]
    test_paths = [
        evidence.project_root / "tests/test_stage01dr_forward_no_grad.py",
        evidence.project_root / "tests/test_stage01dr_diagnostics_detached.py",
        evidence.project_root / "tests/test_stage01dr_no_state_history_growth.py",
        evidence.project_root / "tests/test_stage01dr_neighbor_release.py",
        evidence.project_root / "tests/test_stage01dr_archive_isolation.py",
    ]
    existing_tests = [path for path in test_paths if path.is_file()]
    test_rows = [
        {
            "path": f"`{_relative(path, evidence.project_root)}`",
            "scope": path.stem.removeprefix("test_stage01dr_"),
            "claim": "source present; execution status is not inferred by this report generator",
        }
        for path in existing_tests
    ]
    return f"""# Stage 01D-R 代码保留审计

## 1. 审计边界

本报告静态读取冻结 Stage 01D 的 `01_solver/dynamic_solver/` 与
`06_experiments/stage_01d_fixed_physics_tgv/`。报告器不导入求解 worker，
不运行 trajectory，也不把静态可疑点直接解释为内存泄漏。

{_boundary_statement()}

## 2. 十二项直接回答

{_markdown_table(_static_rows(evidence), (("number", "#"), ("question", "问题"), ("answer", "YES/NO"), ("assessment", "retention 判断"), ("evidence", "文件与行号")))}

## 3. 生命周期判断

静态代码中没有确认的 `O(step)` torch-tensor 历史。正式 worker 的主要确认项是
`DynamicStepResult` 在下一次赋值前同时持有 start/midpoint/end 三套
`ForceEvaluation`，以及 selected checkpoint 的 detached NumPy 缓冲。
前者是一个 step 的 `O(E)` 有界引用，后者是 `O(checkpoint·N)`，均需要动态
inventory 判断平台与峰值，但不能仅凭源码宣称线性泄漏。

通用 `rollout_periodic` observer 可以原样保存 tensor 字典；冻结的正式 Stage 01D
worker 没有使用该 API。普通 accepted RK2 step 位于 `torch.no_grad()`，但完整
forward worker 没有统一的外层 guard；当前正式配置由普通 float 构造，因此这仍是
防回归边界，而不是对旧 N32 的已证实因果归因。

## 4. 最小复现建议

{_markdown_table(_reproducer_rows(evidence), (("number", "#"), ("finding", "静态结论"), ("reproducer", "最小复现/回归建议")))}

## 5. 已存在的测试入口

{_markdown_table(test_rows, (("path", "test source"), ("scope", "scope"), ("claim", "报告边界")))}

这些路径的存在不等同于测试已经通过；正式通过判断只能来自独立测试命令或
campaign/analysis 的机器证据。本报告不伪造 pytest 结果。

## 6. 静态结论

静态审计支持优先检查：完整 forward no-grad、三套 force evaluation 的 weakref
释放、diagnostics 临时分配、archive 四阶段及晚期异常 traceback。它不支持根据
五个旧 RSS 点宣称 Python 泄漏，也不支持忽略这些有界保留对平台与瞬时峰值的影响。

机器分析给出的唯一资源状态为 **`{evidence.resource_status}`**；静态报告不重新
推导或覆盖该状态。

## 证据索引

{_evidence_index(evidence, [*_base_paths(evidence), *source_paths, *existing_tests])}

## 最终边界

{_boundary_statement()}
"""


def _render_memory_component(evidence: Evidence) -> str:
    sampling = _nested(evidence.configuration, "sampling")
    warmup = _nested(evidence.configuration, "warmup")
    phase_rows = [
        {"phase": phase, "purpose": purpose}
        for phase, purpose in (
            ("process_start", "在 heavy imports 前建立进程基线"),
            ("imports_complete", "隔离 import/运行时装载成本"),
            ("initial_state_complete", "隔离初始状态分配"),
            ("first_neighborhood_complete", "隔离首个邻域与算子分配"),
            ("warmup_complete", "结束 step 0–25 allocator/warm-up 区"),
            ("solver_step", "对 step 26–500 进行 post-warm-up 评价"),
            ("before_archive", "记录 archive 前 current RSS"),
            ("after_archive", "定位 NPZ archive 增量"),
            ("before_process_exit", "记录退出前状态并验证父进程回收"),
        )
    ]
    figure_lines = "\n".join(
        f"- `{_relative(path, evidence.project_root)}`" for path in evidence.figure_paths
    )
    relevant_paths = [
        *_base_paths(evidence),
        evidence.run_metrics.path,
        evidence.variant_summary.path,
        evidence.diagnostics_overhead.path,
        evidence.graph_sentinel.path,
        *evidence.figure_paths,
    ]
    return f"""# Stage 01D-R 内存组件审计

## 1. 预登记测量结构

每个 rollout 位于独立串行子进程。current RSS 与 peak RSS 是不同字段；
tensor inventory 只在稀疏检查点运行。前 25 步是 allocator/warm-up 区，
step {warmup['post_warmup_first_step']}–{warmup['post_warmup_last_step']} 才进入
资源判定。

{_markdown_table(phase_rows, (("phase", "phase"), ("purpose", "用途")))}

solver RSS cadence 为每 {sampling['solver_step_interval']} 步一次；archive checkpoint
固定为 `{sampling['archive_checkpoint_steps']}`，不得按结果调整。

## 2. A/B/C/D 隔离变体

{_markdown_table(_variant_protocol_rows(evidence), (("variant", "variant"), ("name", "name"), ("no_grad", "no_grad"), ("diagnostics", "diagnostics"), ("state_checkpoints", "state checkpoints"), ("archive", "final NPZ"), ("steps", "steps"), ("qualification", "formal gate")))}

Variant D 仅作为 graph-retention sentinel，不进入正式资源资格判定。

## 3. 18 个 qualifying run

{_markdown_table(_run_rows(evidence), (("N", "N"), ("variant", "variant"), ("repeat", "repeat"), ("complete", "complete"), ("numeric", "numeric"), ("rss_first", "first-Q RSS"), ("rss_final", "final-Q RSS"), ("rss_delta", "final-first"), ("rss_slope", "Theil–Sen"), ("ci", "bootstrap 95% CI"), ("tensor_count", "tensor-count slope"), ("tensor_bytes", "tensor-byte slope"), ("tracemalloc", "tracemalloc slope"), ("gc", "GC-object slope"), ("step_time", "mean step"), ("edges", "final edges")))}

## 4. Variant 聚合与重复性

{_markdown_table(_variant_rows(evidence), (("N", "N"), ("variant", "variant"), ("complete", "complete"), ("numeric", "numeric"), ("sampling", "sampling"), ("reclaimed", "reclaimed"), ("final_rss", "median final-Q RSS"), ("rss_per_particle", "RSS/particle"), ("rss_slope", "median RSS slope"), ("rss_positive", "RSS positive repeats"), ("tensor_count_positive", "tensor-count positive"), ("tensor_bytes_positive", "tensor-byte positive"), ("trace_positive", "tracemalloc positive"), ("gc_positive", "GC positive")))}

## 5. Diagnostics 组件（B 相对 A）

{_markdown_table(_overhead_rows(evidence), (("N", "N"), ("A", "A final-Q RSS"), ("B", "B final-Q RSS"), ("extra", "bounded extra"), ("fraction", "fraction of A"), ("pass", "gate H")))}

该差异仅描述有 diagnostics 与最小 solver 的有界平台差，不等同于逐步泄漏。

## 6. Archive 组件（Variant C）

{_markdown_table(_archive_rows(evidence), (("N", "N"), ("repeat", "repeat"), ("writes", "writes"), ("checkpoints", "checkpoints"), ("archive_delta", "after-before RSS"), ("solver_quartile", "solver quartile"), ("solver_slope", "solver slope"), ("path", "archive")))}

Archive 写入发生在 solver step 结束后；只有 `before_archive` 到 `after_archive`
的增量可以归因于 archive。solver step 内的 post-warm-up 趋势必须由 A/B/C 的
`solver_step` 样本独立判断。

## 7. Graph sentinel

{_markdown_table(_sentinel_rows(evidence), (("mode", "mode"), ("status", "status"), ("graph_nodes", "reachable graph nodes"), ("position_grad_fn", "position grad_fn"), ("velocity_grad_fn", "velocity gradFn"), ("rss", "step-20 RSS"), ("live_tensors", "live tensors"), ("tensor_bytes", "tensor storage"), ("reclaimed", "reclaimed"), ("identity", "identity")))}

## 8. 图件

{figure_lines}

图件只可视化 retained machine evidence，不改变 gate 或唯一状态。

## 9. 组件结论

唯一资源状态为 **`{evidence.resource_status}`**。{_status_interpretation(evidence)}

## 证据索引

{_evidence_index(evidence, relevant_paths)}

## 最终边界

{_boundary_statement()}
"""


def _render_reproduction(evidence: Evidence) -> str:
    old = evidence.old_n32_row
    rss_initial = _finite_float(
        old["current_rss_initial_bytes"], label="old N32 initial RSS"
    )
    rss_final = _finite_float(
        old["current_rss_final_bytes"], label="old N32 final RSS"
    )
    regression_gate = _gate_by_id(evidence, "REG")
    sentinel_gate = _gate_by_id(evidence, "SENTINEL")
    relevant_paths = [
        *_base_paths(evidence),
        evidence.run_metrics.path,
        evidence.variant_summary.path,
        evidence.graph_sentinel.path,
    ]
    return f"""# Stage 01D-R 复现报告

## 1. 原 Stage 01D 触发事件

冻结 run `{old['run_id']}` 在 step `{old['first_failure_step']}`、物理时间
`{old['first_failure_time']}` 触发 **`{old['failure_class']}`**，保留原因是
`{old['failure_reason']}`。current RSS 从 {_format_bytes(rss_initial)} 增至
{_format_bytes(rss_final)}，区间差为 {_format_bytes(rss_final - rss_initial)}。
该运行的 `all_states_finite={old['all_states_finite']}`、
`sustained_memory_pressure={old['sustained_memory_pressure']}`；因此旧证据证明的是
预登记资源门被触发，不证明数值发散，也不证明泄漏机制。

{_markdown_table(_old_sample_rows(evidence), (("step", "step"), ("time", "time"), ("current_rss", "current RSS"), ("peak_rss", "peak RSS"), ("edges", "edges"), ("finite", "finite")))}

## 2. 为什么五个点不足以证明泄漏

旧 runner 在每个 sample 的 diagnostics **之前**采 current RSS，随后执行完整
topology audit、pair-force 重算和 RK2。step 0→1 因而混合首轮 diagnostics、
首次算子分配、CPU allocator/cache 以及一个 step 的 bounded result lifetime。
五个点全部位于新的 25-step warm-up 边界内，没有 post-warm-up quartile、稳健
斜率、重复性或 live tensor 同步证据，不能区分 allocator 平台与真实 retention。

## 3. 固定复现配置

N32 保持 particles=1024、H/dx=5.0、dt=5e-4、c_s=20、nu=0.02、regular、
seed=0、float64、CPU；N16 使用冻结 smoke 离散作为规模对照。A/B/C 各三个
独立子进程、500 步，D 比较 20 步 no-grad 与 grad-enabled。

## 4. A/B/C 重复结果

{_markdown_table(_variant_rows(evidence), (("N", "N"), ("variant", "variant"), ("complete", "complete"), ("numeric", "numeric"), ("reclaimed", "reclaimed"), ("final_rss", "median final-Q RSS"), ("rss_slope", "median RSS slope"), ("rss_positive", "RSS positive repeats"), ("tensor_count_positive", "tensor-count positive"), ("tensor_bytes_positive", "tensor-byte positive"), ("trace_positive", "tracemalloc positive"), ("gc_positive", "GC positive")))}

## 5. N16/N32 规模对照

{_markdown_table(_n16_n32_rows(evidence), (("variant", "variant"), ("N16", "N16 median RSS"), ("N32", "N32 median RSS"), ("N16_per_particle", "N16 RSS/particle"), ("N32_per_particle", "N32 RSS/particle"), ("N32_over_N16", "N32/N16"), ("N16_slope", "N16 slope"), ("N32_slope", "N32 slope")))}

## 6. Graph-retention sentinel

{_markdown_table(_sentinel_rows(evidence), (("mode", "mode"), ("status", "status"), ("graph_nodes", "graph nodes"), ("position_grad_fn", "position gradFn"), ("velocity_grad_fn", "velocity gradFn"), ("rss", "RSS"), ("live_tensors", "live tensors"), ("tensor_bytes", "tensor storage"), ("reclaimed", "reclaimed")))}

SENTINEL gate：**{_pass_text(sentinel_gate['passed'])}**；它只展示 autograd graph
对照，不纳入 A–J 的正式资源通过判定。

## 7. 冻结数值状态回归

REG gate：**{_pass_text(regression_gate['passed'])}**。observed：
`{regression_gate['observed']}`；threshold：`{regression_gate['threshold']}`。
该 gate 比较 N16/N32 的 step 0–4 positions、velocities、densities、pressures，
不把内存结论替代为数值结论。

## 8. 复现结论

唯一资源状态为 **`{evidence.resource_status}`**。{_status_interpretation(evidence)}
原 Stage 01D 的五点失败证据原样保留，没有被删除或重命名。

## 证据索引

{_evidence_index(evidence, relevant_paths)}

## 最终边界

{_boundary_statement()}
"""


def _threshold_rows(evidence: Evidence) -> list[dict[str, Any]]:
    analysis = _nested(evidence.configuration, "post_warmup_analysis")
    qualification = _nested(evidence.configuration, "qualification")
    return [
        {
            "criterion": "first/final quartile RSS delta",
            "threshold": _format_bytes(
                analysis["rss_final_minus_first_maximum_bytes"]
            ),
        },
        {
            "criterion": "first/final quartile fractional increase",
            "threshold": _format_fraction(
                analysis["rss_final_over_first_fractional_increase_maximum"]
            ),
        },
        {
            "criterion": "Theil–Sen RSS slope",
            "threshold": _format_slope(
                analysis["rss_robust_slope_maximum_bytes_per_step"]
            ),
        },
        {
            "criterion": "Variant B extra RSS",
            "threshold": (
                _format_bytes(qualification["variant_b_extra_memory_maximum_bytes"])
                + " and "
                + _format_fraction(
                    qualification[
                        "variant_b_extra_memory_fraction_of_a_maximum"
                    ]
                )
            ),
        },
        {
            "criterion": "Variant C archive increment",
            "threshold": (
                _format_bytes(
                    qualification[
                        "variant_c_archive_current_rss_increment_maximum_bytes"
                    ]
                )
                + " and "
                + _format_fraction(
                    qualification[
                        "variant_c_archive_current_rss_increment_fraction_maximum"
                    ]
                )
            ),
        },
        {
            "criterion": "current RSS safety stop",
            "threshold": _format_bytes(qualification["current_rss_stop_bytes"]),
        },
        {
            "criterion": "minimum separation/dx",
            "threshold": f">= {qualification['minimum_separation_over_dx']}",
        },
        {
            "criterion": "relative pair-force residual",
            "threshold": f"<= {qualification['maximum_relative_pair_force_residual']}",
        },
        {
            "criterion": "normalized internal force",
            "threshold": f"<= {qualification['maximum_characteristic_normalized_internal_force']}",
        },
    ]


def _render_resource_requalification(evidence: Evidence) -> str:
    decision, decision_text = _stage01d2_decision(evidence)
    relevant_paths = [
        *_base_paths(evidence),
        evidence.run_metrics.path,
        evidence.variant_summary.path,
        evidence.diagnostics_overhead.path,
        evidence.graph_sentinel.path,
    ]
    return f"""# Stage 01D-R 资源重新资格报告

## 1. 唯一状态

本阶段唯一资源状态为 **`{evidence.resource_status}`**。

{_status_interpretation(evidence)}

该状态只回答 frozen fixed-physics solver 的资源行为，不是新的 V2 solution
verification 结论。

## 2. 预登记阈值

{_markdown_table(_threshold_rows(evidence), (("criterion", "criterion"), ("threshold", "registered threshold")))}

## 3. A–J 与辅助硬门

{_markdown_table(_gate_rows(evidence), (("gate", "gate"), ("check", "check"), ("pass", "pass"), ("observed", "observed"), ("threshold", "threshold"), ("severity", "severity"), ("source", "source"), ("detail", "detail")))}

报告层不重新计算或覆盖 `STATUS`；status text、analysis summary 与 STATUS row
已经过三方一致性校验。

## 4. 完成性与数值安全

N32 A/B 要求 3/3 完成，C 要求至少 2/3；N16 九个 scale-control run、
N16/N32 step 0–4 冻结状态回归、所有 child reclamation、拓扑、finite state、
pair-force、internal-force、viscous-power 与 minimum-separation 均由相应 gate
单独记录。资源通过不能覆盖任何数值或 provenance 失败。

## 5. Post-warm-up 资源判定

判定仅使用 step 26–500。RSS 使用 Theil–Sen、first/final quartile median、
rolling 50-step increase 与 moving-block bootstrap；tensor count/storage、
tracemalloc 与 GC tracked objects 分开报告。单次正斜率不自动构成重复性失败。

## 6. Diagnostics 与 archive

Gate H 比较 B 相对 A 的 final-quartile 平台；Gate I 要求 C 的 archive 只在
solver 后写一次、checkpoint 列表精确匹配、solver slope/quartile 有界且
archive current-RSS 增量满足注册上限。peak RSS 从未被当作 current RSS。

## 7. Retention fix

{_fix_text(evidence)}

## 8. Stage 01D2 决策

决策：**`{decision}`**。{decision_text}

即使允许“准备”协议，也必须先重新预登记并由用户另行授权；本程序没有运行
时间/空间收敛，也没有启动 V3。

## 9. 旧状态与阶段边界

{_boundary_statement()}

Stage 01D-R 的资源状态不得替换 `stage01d_v2_status.txt`，不得据此宣称旧
N32 已完成 V2，也不得据此开始神经网络训练或生成标签。

## 证据索引

{_evidence_index(evidence, relevant_paths)}
"""


def _final_static_summary(evidence: Evidence) -> str:
    rows = [
        {
            "number": finding.number,
            "answer": finding.answer,
            "assessment": finding.retention_assessment,
        }
        for finding in evidence.static_findings
    ]
    return _markdown_table(
        rows,
        (("number", "#"), ("answer", "YES/NO"), ("assessment", "判断")),
    )


def _render_final(evidence: Evidence) -> str:
    old = evidence.old_n32_row
    decision, decision_text = _stage01d2_decision(evidence)
    regression_gate = _gate_by_id(evidence, "REG")
    relevant_paths = [
        *_base_paths(evidence),
        evidence.run_metrics.path,
        evidence.variant_summary.path,
        evidence.diagnostics_overhead.path,
        evidence.graph_sentinel.path,
        *evidence.figure_paths,
    ]
    return f"""# Stage 01D-R 最终报告

## 1. Stage 01D 冻结与旧 V2_FAIL 保留

正式运行提交为 `{evidence.freeze_facts['formal_run_commit']}`，最终证据提交及
annotated tag target 为 `{evidence.freeze_facts['final_evidence_commit']}`；tag 为
`{evidence.freeze_facts['tag']}`。SHA-256 清单包含
`{evidence.freeze_facts['manifest_rows']}` 项、mismatch=0。

Stage 01D 的既有状态仍为 **`V2_FAIL`**，本阶段没有回写任何旧报告、配置、
轨迹、日志或失败栈。

## 2. 原资源门为何触发

旧 N32 smoke 在 step `{old['first_failure_step']}` 观察到 current RSS 从
{_format_bytes(old['current_rss_initial_bytes'])} 增至
{_format_bytes(old['current_rss_final_bytes'])}，旧预登记规则据此给出
`{old['failure_class']}: {old['failure_reason']}`。状态全部有限、无 sustained
system-memory pressure；因此它是有效的旧资源门失败，不是数值发散证明。

## 3. 为什么五个采样点不足以证明泄漏

五点都位于新的 25-step allocator/warm-up 区，且 current RSS 在 diagnostics
之前采样，下一点会包含上一轮 diagnostics、邻域/force 临时分配与 allocator
缓存。没有 post-warm-up quartile、稳健斜率、重复性和同步 tensor/Python-memory
证据，不能在 allocator plateau 与真实 retention 之间作唯一判定。

## 4. 静态代码保留审计

{_final_static_summary(evidence)}

没有发现正式路径按 step 保存 torch-tensor 历史；确认的主要有界项是三套
force evaluation 的一个-step 生命周期与 selected NumPy checkpoint 缓冲。

## 5. A/B/C/D 四变体

{_markdown_table(_variant_protocol_rows(evidence), (("variant", "variant"), ("name", "name"), ("no_grad", "no_grad"), ("diagnostics", "diagnostics"), ("state_checkpoints", "checkpoints"), ("archive", "NPZ"), ("steps", "steps"), ("qualification", "formal")))}

A/B/C 各三次独立 qualifying process；D 为 20-step graph sentinel，不进入
正式资源 gate。

## 6. N16/N32 对照

{_markdown_table(_n16_n32_rows(evidence), (("variant", "variant"), ("N16", "N16 RSS"), ("N32", "N32 RSS"), ("N16_per_particle", "N16 RSS/particle"), ("N32_per_particle", "N32 RSS/particle"), ("N32_over_N16", "N32/N16"), ("N16_slope", "N16 slope"), ("N32_slope", "N32 slope")))}

## 7. Warm-up 与 post-warm-up 分离

step 0–25 仅定义 allocator/warm-up；step 26–500 才用于资源资格。first quartile
为 step 26–144，final quartile 为 382–500；所有 RSS slope、quartile 与 rolling
判定均遵循该冻结区间。

## 8. RSS、tracemalloc 与 tensor inventory

{_markdown_table(_variant_rows(evidence), (("N", "N"), ("variant", "variant"), ("complete", "complete"), ("final_rss", "median final-Q RSS"), ("rss_slope", "RSS slope"), ("rss_positive", "RSS positive repeats"), ("tensor_count_positive", "tensor-count positive"), ("tensor_bytes_positive", "tensor-byte positive"), ("trace_positive", "tracemalloc positive"), ("gc_positive", "GC positive")))}

## 9. Archive 与 solver 内存分离

{_markdown_table(_archive_rows(evidence), (("N", "N"), ("repeat", "repeat"), ("writes", "writes"), ("checkpoints", "checkpoints"), ("archive_delta", "archive RSS delta"), ("solver_quartile", "solver quartile"), ("solver_slope", "solver slope"), ("path", "archive")))}

Archive delta 只取 `after_archive-before_archive`；它不回灌 solver post-warm-up
slope。A/B 没有 NPZ，C 仅在预登记 checkpoint 形成结束后 archive。

## 10. 任何修复的 before/after

{_fix_text(evidence)}

## 11. 数值回归

REG gate 为 **{_pass_text(regression_gate['passed'])}**；observed=
`{regression_gate['observed']}`，threshold=`{regression_gate['threshold']}`。
该结果检查 finite state、守恒/拓扑诊断及冻结 step 0–4 状态；资源分析没有修改
密度、EOS、压力、黏性、H/dx、dt、nu、c_s、RK2 或布局。

## 12. 唯一资源状态

唯一资源状态为 **`{evidence.resource_status}`**。

{_status_interpretation(evidence)}

报告器只读取 status text、analysis summary 和 STATUS gate，不在报告层重新选择状态。

## 13. 是否允许建立新的 Stage 01D2 V2 协议

决策为 **`{decision}`**。{decision_text} 即使可以准备新协议，也没有在本阶段
启动时间/空间/扰动/Mach 收敛。

## 14. 旧 Stage 01D 状态

旧 Stage 01D **仍为 `V2_FAIL`**。Stage 01D-R 的任何资源通过、条件状态或失败
均不具追溯改写效力；旧 N32 failure stack 与三份 NPZ 继续由冻结清单保护。

## 15. Stage 02 与 V3

**Stage 02 仍未开始，V3 仍未开始。** 本阶段没有训练神经网络、实现 attention、
生成学习标签或定义教师/学生求解器。

## 证据索引

{_evidence_index(evidence, relevant_paths)}
"""


def render_reports(evidence: Evidence) -> dict[str, str]:
    reports = {
        "stage_01dr_code_retention_audit.md": _render_code_retention(evidence),
        "stage_01dr_memory_component_audit.md": _render_memory_component(evidence),
        "stage_01dr_reproduction_report.md": _render_reproduction(evidence),
        "stage_01dr_resource_requalification.md": _render_resource_requalification(
            evidence
        ),
        "stage_01dr_final_report.md": _render_final(evidence),
    }
    if tuple(reports) != REPORT_FILENAMES:
        raise ReportEvidenceError("internal Stage 01D-R report filename drift")
    normalized = {name: text.rstrip() + "\n" for name, text in reports.items()}
    _validate_rendered_reports(evidence, normalized)
    return normalized


def _validate_rendered_reports(
    evidence: Evidence,
    reports: Mapping[str, str],
) -> None:
    if tuple(reports) != REPORT_FILENAMES:
        raise ReportEvidenceError("not exactly five Stage 01D-R reports were rendered")
    private_fragments = (str(Path.home()), "/Users/")
    for name, text in reports.items():
        if not text.startswith("# Stage 01D-R"):
            raise ReportEvidenceError(f"{name} lacks a Stage 01D-R heading")
        if "## 证据索引" not in text:
            raise ReportEvidenceError(f"{name} lacks an evidence index")
        if "V2_FAIL" not in text:
            raise ReportEvidenceError(f"{name} omits the frozen V2_FAIL boundary")
        if "Stage 02" not in text or "V3" not in text:
            raise ReportEvidenceError(f"{name} omits Stage 02/V3 boundaries")
        if evidence.resource_status not in text:
            raise ReportEvidenceError(f"{name} omits the unique resource status")
        if "\r" in text:
            raise ReportEvidenceError(f"{name} contains non-LF line endings")
        if any(fragment and fragment in text for fragment in private_fragments):
            raise ReportEvidenceError(f"{name} leaks an absolute home path")
    final = reports["stage_01dr_final_report.md"]
    for section in range(1, 16):
        if f"## {section}." not in final:
            raise ReportEvidenceError(
                f"final Stage 01D-R report is missing required section {section}"
            )
    if f"唯一资源状态为 **`{evidence.resource_status}`**" not in final:
        raise ReportEvidenceError("final report does not state the unique status")
    if "旧 Stage 01D **仍为 `V2_FAIL`**" not in final:
        raise ReportEvidenceError("final report weakens the old V2_FAIL statement")
    if "Stage 02 仍未开始，V3 仍未开始" not in final:
        raise ReportEvidenceError("final report omits the non-start statement")


def _atomic_write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite report: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def write_reports(
    reports: Mapping[str, str],
    *,
    output_root: Path,
) -> None:
    destination = output_root.resolve()
    targets = [destination / name for name in REPORT_FILENAMES]
    collisions = [path for path in targets if path.exists() or path.is_symlink()]
    if collisions:
        raise FileExistsError(
            "refusing to overwrite existing Stage 01D-R reports: "
            + ", ".join(str(path) for path in collisions)
        )
    for name in REPORT_FILENAMES:
        _atomic_write_new(destination / name, reports[name])


def check_reports(
    reports: Mapping[str, str],
    *,
    output_root: Path,
) -> tuple[int, int]:
    present = 0
    matching = 0
    destination = output_root.resolve()
    for name in REPORT_FILENAMES:
        path = destination / name
        if not path.is_file():
            continue
        present += 1
        if path.read_text(encoding="utf-8") != reports[name]:
            raise ReportEvidenceError(
                f"existing Stage 01D-R report differs from evidence: {path}"
            )
        matching += 1
    return present, matching


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate five Stage 01D-R Markdown reports from existing memory "
            "campaign evidence; never execute a rollout or analyzer."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=None,
        help="Optional Stage 01D-R experiment root inside the project.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Report directory; default is <project>/07_reports. Existing "
            "targets are never overwritten."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate and render without writing; existing reports, if any, "
            "must match byte-for-byte."
        ),
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    output_root = (
        project_root / REPORT_RELATIVE
        if args.output_root is None
        else args.output_root.resolve()
    )
    try:
        evidence = Evidence.load(
            project_root,
            experiment_root=args.experiment_root,
        )
        reports = render_reports(evidence)
        if args.check:
            present, matching = check_reports(reports, output_root=output_root)
            print(
                "CHECK_OK "
                f"status={evidence.resource_status} "
                f"rendered={len(reports)} existing={present} matching={matching}"
            )
            return 0
        write_reports(reports, output_root=output_root)
    except (ReportEvidenceError, FileExistsError, OSError) as error:
        message = str(error).replace(str(project_root), "<PROJECT_ROOT>")
        message = message.replace(str(Path.home()), "<HOME>")
        print(f"REPORT_ERROR: {message}", file=sys.stderr)
        return 2
    for name in REPORT_FILENAMES:
        path = (output_root / name).resolve()
        try:
            rendered = path.relative_to(project_root).as_posix()
        except ValueError:
            rendered = path.name
        print(rendered)
    print(evidence.resource_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
