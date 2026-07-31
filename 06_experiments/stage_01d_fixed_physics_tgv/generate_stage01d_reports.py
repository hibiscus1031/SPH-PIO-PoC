"""Generate the eight Stage 01D Markdown reports from retained evidence.

This module is deliberately a read-only post-processor for numerical evidence.
It never launches a trajectory or re-evaluates the V2 decision.  The sole V2
status is read from ``stage01d_v2_status.txt`` and must be one of the three
pre-registered values.

Report writes are no-clobber and atomic: complete temporary files are linked
into place only when the target names do not already exist.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from functools import lru_cache
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
EXPERIMENT_ROOT_RELATIVE = Path(
    "06_experiments/stage_01d_fixed_physics_tgv"
)
INTEGRATOR_ROOT_RELATIVE = Path(
    "06_experiments/stage_01d_integrator_verification"
)
REPORT_ROOT_RELATIVE = Path("07_reports")

ALLOWED_FINAL_STATUSES = (
    "V2_PASS",
    "V2_CONDITIONAL",
    "V2_FAIL",
)
ACCEPTED_RUN_STATUSES = frozenset(
    {
        "accepted",
        "complete",
        "completed",
        "ok",
        "pass",
        "passed",
        "success",
    }
)

REPORT_FILENAMES = (
    "stage_01d_solver_assembly_audit.md",
    "stage_01d_integrator_verification.md",
    "stage_01d_time_convergence.md",
    "stage_01d_space_convergence.md",
    "stage_01d_support_family_comparison.md",
    "stage_01d_disorder_robustness.md",
    "stage_01d_model_form_assessment.md",
    "stage_01d_final_v2_report.md",
)

DERIVED_TABLE_FILENAMES = {
    "integrator_gate": "integrator_gate_evidence.csv",
    "time": "time_convergence_metrics.csv",
    "space": "space_convergence_metrics.csv",
    "disorder": "disorder_summary.csv",
    "mach": "mach_summary.csv",
    "gates": "stage01d_gate_evidence.csv",
}

SOLVER_SOURCE_RELATIVE_PATHS = (
    Path("01_solver/dynamic_solver/state.py"),
    Path("01_solver/dynamic_solver/density.py"),
    Path("01_solver/dynamic_solver/equation_of_state.py"),
    Path("01_solver/dynamic_solver/acceleration.py"),
    Path("01_solver/dynamic_solver/integrator.py"),
    Path("01_solver/dynamic_solver/diagnostics.py"),
    Path("01_solver/dynamic_solver/taylor_green.py"),
    Path("01_solver/dynamic_solver/periodic_rollout.py"),
)

RUN_VIEW_COLUMNS = (
    ("run_id", "run_id"),
    ("protocol", "protocol"),
    ("status", "status"),
    ("resolution", "N"),
    ("support_family", "support family"),
    ("support_ratio", "H/dx"),
    ("dt", "dt"),
    ("t_final", "t_final"),
    ("layout", "layout"),
    ("seed", "seed"),
    ("sound_speed", "c_s"),
    ("mass_reference_density", "mass reference density"),
    ("eos_reference_density", "EOS reference density"),
    ("final_velocity_relative_l2", "final velocity rel. L2"),
    (
        "final_modal_amplitude_relative_error",
        "final modal rel. error",
    ),
    (
        "final_kinetic_energy_relative_error",
        "final energy rel. error",
    ),
    (
        "maximum_density_fluctuation_relative_rms",
        "max density fluct. rel. RMS",
    ),
    ("maximum_mach", "max Mach"),
    (
        "maximum_momentum_drift_normalized",
        "max momentum drift (norm.)",
    ),
    (
        "maximum_angular_momentum_drift_normalized",
        "max angular drift (norm.)",
    ),
    ("minimum_separation_over_dx", "min separation/dx"),
    ("minimum_neighbor_count", "neighbor min"),
    ("maximum_neighbor_count", "neighbor max"),
    ("edge_count", "edge count"),
    ("wall_clock_seconds", "wall s"),
    ("mean_step_seconds", "mean step s"),
    ("peak_rss_bytes", "peak RSS bytes"),
)

ENDPOINT_VIEW_COLUMNS = (
    ("run_id", "run_id"),
    ("time", "last recorded t"),
    ("velocity_error_l1", "velocity L1"),
    ("velocity_relative_l2", "velocity rel. L2"),
    ("velocity_error_linf", "velocity Linf"),
    ("modal_amplitude_error", "modal abs. error"),
    ("kinetic_energy_error", "energy abs. error"),
    (
        "density_fluctuation_relative_rms",
        "density fluct. rel. RMS",
    ),
    ("maximum_mach", "max Mach"),
    ("momentum_drift_absolute", "momentum drift abs."),
    ("momentum_drift_normalized", "momentum drift norm."),
    (
        "angular_momentum_drift_absolute",
        "angular drift abs.",
    ),
    (
        "angular_momentum_drift_normalized",
        "angular drift norm.",
    ),
    ("velocity_divergence_l2", "divergence L2"),
    ("accumulated_viscous_power", "viscous power"),
    ("minimum_separation", "min separation"),
    ("neighbor_count_mean", "neighbor mean"),
    ("neighbor_count_min", "neighbor min"),
    ("neighbor_count_max", "neighbor max"),
    ("neighbor_duplicate_edge_count", "duplicate edges"),
    (
        "neighbor_omitted_strict_support_edge_count",
        "strict-support omissions",
    ),
    (
        "neighbor_nonreciprocal_nonself_edge_count",
        "nonreciprocal edges",
    ),
    ("wall_clock_seconds", "wall s"),
    ("peak_rss_bytes", "peak RSS bytes"),
)


class ReportEvidenceError(RuntimeError):
    """Raised when report inputs are absent, ambiguous, or malformed."""


@dataclass(frozen=True)
class CsvTable:
    path: Path
    fields: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class Artifact:
    path: Path
    exists: bool


@dataclass(frozen=True)
class BranchState:
    name: str
    observed_runs: int
    expected_runs: int
    state: str
    reason: str


@dataclass
class Evidence:
    project_root: Path
    experiment_root: Path
    results_root: Path
    config_path: Path
    configuration: dict[str, Any]
    manifest: CsvTable
    run_summary: CsvTable
    samples: dict[str, CsvTable]
    sample_artifacts: dict[str, Artifact]
    run_artifacts: tuple[Artifact, ...]
    integrator_raw: CsvTable
    dynamic_autograd: CsvTable
    stage01c_autograd_regression: CsvTable | None
    stage01c_autograd_baseline: CsvTable
    derived: dict[str, CsvTable]
    status_path: Path
    final_status: str
    solver_sources: tuple[Path, ...]
    stage01c_gate_status_path: Path
    stage01c_gate_status: str
    v0_source_path: Path
    v0_status: str
    v3_prior_status: str
    stage01c_final_report_path: Path
    generator_path: Path

    @property
    def gate_rows(self) -> tuple[dict[str, str], ...]:
        return self.derived["gates"].rows

    @classmethod
    def load(
        cls,
        project_root: Path,
        *,
        experiment_root: Path | None = None,
        integrator_path: Path | None = None,
    ) -> "Evidence":
        project_root = project_root.resolve()
        experiment_root = (
            (project_root / EXPERIMENT_ROOT_RELATIVE).resolve()
            if experiment_root is None
            else experiment_root.resolve()
        )
        _require_inside_project(
            experiment_root,
            project_root,
            label="Stage 01D experiment root",
        )
        results_root = experiment_root / "results"
        config_path = (
            experiment_root
            / "configs"
            / "preregistered_primary_tgv.yml"
        )
        configuration = _read_yaml(config_path)
        _validate_configuration(configuration, config_path)

        manifest = _read_csv(
            results_root / "stage01c_sha256_manifest.csv",
            label="Stage 01C SHA-256 manifest",
        )
        run_summary = _read_csv(
            results_root / "run_summary.csv",
            label="Stage 01D run summary",
        )
        _require_fields(
            run_summary,
            ("run_id", "protocol", "status"),
        )
        run_ids = [_required_cell(row, "run_id") for row in run_summary.rows]
        if len(run_ids) != len(set(run_ids)):
            raise ReportEvidenceError(
                f"{_safe_relative(run_summary.path, project_root)}: "
                "duplicate run_id values"
            )

        samples: dict[str, CsvTable] = {}
        sample_artifacts: dict[str, Artifact] = {}
        all_run_artifacts: list[Artifact] = []
        for row in run_summary.rows:
            run_id = _required_cell(row, "run_id")
            accepted = _is_accepted(row.get("status", ""))
            sample_path = _recorded_artifact_path(
                row.get("sample_table_path", ""),
                project_root=project_root,
                experiment_root=experiment_root,
                default=(
                    results_root
                    / "trajectory_samples"
                    / f"{run_id}.csv"
                ),
            )
            sample_artifact = Artifact(
                path=sample_path,
                exists=sample_path.is_file(),
            )
            sample_artifacts[run_id] = sample_artifact
            all_run_artifacts.append(sample_artifact)
            if sample_path.is_file():
                sample = _read_csv(
                    sample_path,
                    label=f"trajectory samples for {run_id}",
                    allow_empty=not accepted,
                )
                if sample.rows:
                    sample_run_ids = {
                        value
                        for value in (
                            item.get("run_id", "").strip()
                            for item in sample.rows
                        )
                        if value
                    }
                    if sample_run_ids and sample_run_ids != {run_id}:
                        raise ReportEvidenceError(
                            f"{_safe_relative(sample_path, project_root)}: "
                            f"sample run_id values {sorted(sample_run_ids)} "
                            f"do not equal {run_id!r}"
                        )
                samples[run_id] = sample
            elif accepted:
                raise ReportEvidenceError(
                    "accepted trajectory is missing its sample table: "
                    f"{run_id} -> "
                    f"{_safe_relative(sample_path, project_root)}"
                )

            for column in (
                "state_path",
                "config_path",
                "stdout_log_path",
                "stderr_log_path",
                "failure_evidence_path",
            ):
                recorded = row.get(column, "").strip()
                if not recorded:
                    continue
                artifact_path = _recorded_artifact_path(
                    recorded,
                    project_root=project_root,
                    experiment_root=experiment_root,
                    default=None,
                )
                all_run_artifacts.append(
                    Artifact(
                        path=artifact_path,
                        exists=artifact_path.is_file(),
                    )
                )

        if integrator_path is None:
            integrator_path = _single_existing(
                (
                    project_root
                    / INTEGRATOR_ROOT_RELATIVE
                    / "results"
                    / "integrator_verification.csv",
                    project_root
                    / INTEGRATOR_ROOT_RELATIVE
                    / "results"
                    / "integrator_order.csv",
                ),
                label="raw Stage 01D integrator CSV",
            )
        else:
            integrator_path = integrator_path.resolve()
            _require_inside_project(
                integrator_path,
                project_root,
                label="raw Stage 01D integrator CSV",
            )
            _require_file(
                integrator_path,
                label="raw Stage 01D integrator CSV",
            )
        integrator_raw = _read_csv(
            integrator_path,
            label="raw Stage 01D integrator CSV",
        )

        dynamic_autograd = _read_csv(
            results_root / "dynamic_autograd_fd.csv",
            label="Stage 01D dynamic AD CSV",
        )
        stage01c_regression_path = (
            results_root / "stage01c_autograd_regression.csv"
        )
        stage01c_regression = (
            _read_csv(
                stage01c_regression_path,
                label="current Stage 01C AD regression CSV",
            )
            if stage01c_regression_path.is_file()
            else None
        )
        stage01c_baseline = _read_csv(
            project_root
            / "06_experiments"
            / "stage_01c_autograd"
            / "results"
            / "native_autograd_fd.csv",
            label="frozen Stage 01C AD baseline CSV",
        )

        derived: dict[str, CsvTable] = {}
        for key, filename in DERIVED_TABLE_FILENAMES.items():
            derived[key] = _read_csv(
                results_root / filename,
                label=f"Stage 01D evaluator product {filename}",
                allow_empty=key in {"time", "space", "disorder", "mach"},
            )

        status_path = results_root / "stage01d_v2_status.txt"
        final_status = _read_final_status(status_path)
        allowed = tuple(
            _nested(
                configuration,
                "v2_decision",
                "allowed_status",
            )
        )
        if allowed != ALLOWED_FINAL_STATUSES:
            raise ReportEvidenceError(
                "pre-registered allowed V2 statuses drifted: "
                f"{allowed!r}"
            )
        _validate_status_evidence(
            derived["gates"],
            final_status,
        )

        solver_sources = tuple(
            (project_root / path).resolve()
            for path in SOLVER_SOURCE_RELATIVE_PATHS
        )
        for source in solver_sources:
            _require_file(source, label="dynamic solver source")
            _require_inside_project(
                source,
                project_root,
                label="dynamic solver source",
            )

        stage01c_gate_status_path = (
            project_root
            / "06_experiments"
            / "stage_01c_operator_candidates"
            / "results"
            / "stage01c_gate_status.txt"
        )
        stage01c_gate_status = _single_nonblank_line(
            stage01c_gate_status_path,
            label="Stage 01C gate status",
        )
        if stage01c_gate_status != "C1_PASS_C2_PASS_C3_PASS_C4_PASS":
            raise ReportEvidenceError(
                "unexpected frozen Stage 01C gate status: "
                f"{stage01c_gate_status!r}"
            )

        v0_source_path = (
            project_root
            / "07_reports"
            / "stage_01_scope_reclassification.md"
        )
        v0_text = _read_text(v0_source_path)
        v0_status = _extract_prior_stage_status(
            v0_text,
            "V0 engineering executability",
            source=v0_source_path,
        )
        v3_prior_status = _extract_prior_stage_status(
            v0_text,
            "V3 reference qualification",
            source=v0_source_path,
        )
        stage01c_final_report_path = (
            project_root
            / "07_reports"
            / "stage_01c_final_requalification.md"
        )
        _require_file(
            stage01c_final_report_path,
            label="Stage 01C final report",
        )

        evidence = cls(
            project_root=project_root,
            experiment_root=experiment_root,
            results_root=results_root,
            config_path=config_path,
            configuration=configuration,
            manifest=manifest,
            run_summary=run_summary,
            samples=samples,
            sample_artifacts=sample_artifacts,
            run_artifacts=tuple(_unique_artifacts(all_run_artifacts)),
            integrator_raw=integrator_raw,
            dynamic_autograd=dynamic_autograd,
            stage01c_autograd_regression=stage01c_regression,
            stage01c_autograd_baseline=stage01c_baseline,
            derived=derived,
            status_path=status_path,
            final_status=final_status,
            solver_sources=solver_sources,
            stage01c_gate_status_path=stage01c_gate_status_path,
            stage01c_gate_status=stage01c_gate_status,
            v0_source_path=v0_source_path,
            v0_status=v0_status,
            v3_prior_status=v3_prior_status,
            stage01c_final_report_path=stage01c_final_report_path,
            generator_path=Path(__file__).resolve(),
        )
        evidence.validate_semantics()
        return evidence

    def validate_semantics(self) -> None:
        _require_fields(
            self.integrator_raw,
            ("problem", "dt", "error_L2"),
        )
        _require_fields(
            self.dynamic_autograd,
            (
                "parameter",
                "steps",
                "autograd_gradient",
                "finite_difference_gradient",
                "relative_difference",
                "status",
            ),
        )
        _require_fields(
            self.derived["gates"],
            (
                "gate",
                "check",
                "passed",
                "observed",
                "threshold",
                "source",
                "severity",
            ),
        )
        _validate_manifest(self)
        _validate_gci_evidence(self.derived["space"])
        _validate_accepted_sample_audits(self)


def _normal_token(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value).strip().lower(),
    ).strip("_")


def _nested(record: Mapping[str, Any], *keys: str) -> Any:
    current: Any = record
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        if not isinstance(current, Mapping) or key not in current:
            raise ReportEvidenceError(
                "pre-registration is missing "
                + ".".join(traversed)
            )
        current = current[key]
    return current


def _read_text(path: Path) -> str:
    _require_file(path, label="text evidence")
    try:
        return path.read_text(encoding="utf-8")
    except Exception as error:
        raise ReportEvidenceError(
            f"cannot read {path}: {error}"
        ) from error


def _read_yaml(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    try:
        value = yaml.safe_load(text)
    except Exception as error:
        raise ReportEvidenceError(
            f"cannot parse YAML {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ReportEvidenceError(
            f"YAML root must be a mapping: {path}"
        )
    return value


def _read_csv(
    path: Path,
    *,
    label: str,
    allow_empty: bool = False,
) -> CsvTable:
    _require_file(path, label=label)
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise ReportEvidenceError(
                    f"{label} has no header: {path}"
                )
            fields = tuple(reader.fieldnames)
            if any(not field or not field.strip() for field in fields):
                raise ReportEvidenceError(
                    f"{label} has a blank column: {path}"
                )
            if len(fields) != len(set(fields)):
                raise ReportEvidenceError(
                    f"{label} has duplicate columns: {path}"
                )
            rows: list[dict[str, str]] = []
            for index, row in enumerate(reader, start=2):
                if None in row:
                    raise ReportEvidenceError(
                        f"{label} has extra cells at line {index}: {path}"
                    )
                if any(value is None for value in row.values()):
                    raise ReportEvidenceError(
                        f"{label} has short row at line {index}: {path}"
                    )
                rows.append(
                    {key: str(value) for key, value in row.items()}
                )
    except ReportEvidenceError:
        raise
    except Exception as error:
        raise ReportEvidenceError(
            f"cannot read {label} {path}: {error}"
        ) from error
    if not rows and not allow_empty:
        raise ReportEvidenceError(f"{label} is empty: {path}")
    return CsvTable(path=path.resolve(), fields=fields, rows=tuple(rows))


def _single_nonblank_line(path: Path, *, label: str) -> str:
    text = _read_text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ReportEvidenceError(
            f"{label} must contain exactly one nonblank line: {path}"
        )
    return lines[0]


def _read_final_status(path: Path) -> str:
    status = _single_nonblank_line(path, label="Stage 01D V2 status")
    if status not in ALLOWED_FINAL_STATUSES:
        raise ReportEvidenceError(
            f"disallowed Stage 01D final status {status!r}: {path}"
        )
    return status


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise ReportEvidenceError(f"missing {label}: {path}")


def _require_inside_project(
    path: Path,
    project_root: Path,
    *,
    label: str,
) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as error:
        raise ReportEvidenceError(
            f"{label} is outside the project root"
        ) from error


def _safe_relative(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return f"<EXTERNAL_PATH_REDACTED>/{path.name}"


def _single_existing(
    candidates: Sequence[Path],
    *,
    label: str,
) -> Path:
    found = [path.resolve() for path in candidates if path.is_file()]
    if len(found) != 1:
        raise ReportEvidenceError(
            f"{label} requires exactly one file; found "
            f"{[_safe_relative(path, PROJECT_ROOT) for path in found]}"
        )
    return found[0]


def _recorded_artifact_path(
    value: str,
    *,
    project_root: Path,
    experiment_root: Path,
    default: Path | None,
) -> Path:
    text = value.strip()
    if not text:
        if default is None:
            raise ReportEvidenceError("blank recorded artifact path")
        path = default.resolve()
    else:
        raw = Path(text)
        if raw.is_absolute():
            path = raw.resolve()
        else:
            project_candidate = (project_root / raw).resolve()
            experiment_candidate = (experiment_root / raw).resolve()
            if project_candidate.exists() or not experiment_candidate.exists():
                path = project_candidate
            else:
                path = experiment_candidate
    _require_inside_project(
        path,
        project_root,
        label="recorded artifact",
    )
    return path


def _unique_artifacts(
    artifacts: Iterable[Artifact],
) -> list[Artifact]:
    by_path: dict[Path, Artifact] = {}
    for artifact in artifacts:
        existing = by_path.get(artifact.path)
        by_path[artifact.path] = Artifact(
            path=artifact.path,
            exists=(
                artifact.exists
                if existing is None
                else existing.exists or artifact.exists
            ),
        )
    return [by_path[path] for path in sorted(by_path, key=str)]


def _validate_configuration(
    configuration: Mapping[str, Any],
    path: Path,
) -> None:
    if configuration.get("stage") != "01D":
        raise ReportEvidenceError(f"wrong stage in {path}")
    if (
        configuration.get("status")
        != "PREREGISTERED_BEFORE_FIRST_STAGE_01D_TGV_RUN"
    ):
        raise ReportEvidenceError(
            f"configuration is not marked pre-registered: {path}"
        )
    backend = _nested(configuration, "backend")
    if backend.get("device") != "cpu" or backend.get("dtype") != "float64":
        raise ReportEvidenceError(
            "Stage 01D report generator requires the pre-registered "
            "CPU/float64 primary backend"
        )


def _required_cell(row: Mapping[str, str], field: str) -> str:
    value = row.get(field, "").strip()
    if not value:
        raise ReportEvidenceError(f"blank required field {field!r}")
    return value


def _require_fields(table: CsvTable, fields: Sequence[str]) -> None:
    missing = [field for field in fields if field not in table.fields]
    if missing:
        raise ReportEvidenceError(
            f"{table.path} is missing columns {missing}"
        )


def _parse_bool(value: Any, *, source: str) -> bool:
    token = _normal_token(value)
    if token in {"true", "1", "yes", "pass", "passed"}:
        return True
    if token in {"false", "0", "no", "fail", "failed"}:
        return False
    raise ReportEvidenceError(
        f"invalid boolean {value!r} in {source}"
    )


def _optional_bool(value: Any) -> bool | None:
    text = str(value).strip()
    if not text:
        return None
    return _parse_bool(text, source="CSV evidence")


def _finite_float(value: Any, *, source: str) -> float:
    text = str(value).strip()
    if not text:
        raise ReportEvidenceError(f"blank numeric value in {source}")
    try:
        result = float(text)
    except ValueError as error:
        raise ReportEvidenceError(
            f"invalid number {value!r} in {source}"
        ) from error
    if not math.isfinite(result):
        raise ReportEvidenceError(
            f"non-finite number {value!r} in {source}"
        )
    return result


def _is_accepted(value: Any) -> bool:
    return _normal_token(value) in ACCEPTED_RUN_STATUSES


def _extract_prior_stage_status(
    text: str,
    label: str,
    *,
    source: Path,
) -> str:
    pattern = re.compile(
        rf"\|\s*{re.escape(label)}\s*\|\s*\*\*(.+?)\*\*\s*\|",
        flags=re.IGNORECASE,
    )
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ReportEvidenceError(
            f"cannot extract unique {label!r} status from {source}"
        )
    return matches[0].strip()


def _validate_status_evidence(
    gates: CsvTable,
    status: str,
) -> None:
    _require_fields(gates, ("check", "observed"))
    final_rows = [
        row
        for row in gates.rows
        if _normal_token(row.get("check", ""))
        in {"unique_final_status", "final_v2_status"}
    ]
    if len(final_rows) != 1:
        raise ReportEvidenceError(
            f"{gates.path}: expected one final-status evidence row"
        )
    observed = final_rows[0].get("observed", "").strip()
    if observed != status:
        raise ReportEvidenceError(
            "status file and gate evidence disagree: "
            f"{status!r} != {observed!r}"
        )


def _validate_manifest(evidence: Evidence) -> None:
    _require_fields(
        evidence.manifest,
        (
            "path",
            "frozen_commit",
            "frozen_sha256",
            "current_sha256",
            "exists",
            "matches_frozen_commit",
        ),
    )
    if not evidence.manifest.rows:
        raise ReportEvidenceError("Stage 01C manifest is empty")
    expected_commit = str(
        _nested(
            evidence.configuration,
            "frozen_stage_01c",
            "commit",
        )
    )
    for row in evidence.manifest.rows:
        if row["frozen_commit"] != expected_commit:
            raise ReportEvidenceError(
                "Stage 01C manifest contains a different frozen commit"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", row["frozen_sha256"]):
            raise ReportEvidenceError(
                "invalid frozen SHA-256 in Stage 01C manifest"
            )
        exists = _parse_bool(
            row["exists"],
            source=str(evidence.manifest.path),
        )
        if exists and not re.fullmatch(
            r"[0-9a-f]{64}",
            row["current_sha256"],
        ):
            raise ReportEvidenceError(
                "existing manifest entry has invalid current SHA-256"
            )
        if not exists and row["current_sha256"].strip():
            raise ReportEvidenceError(
                "missing manifest entry unexpectedly has a current SHA-256"
            )


def _validate_gci_evidence(table: CsvTable) -> None:
    if not table.rows or "gci_computed" not in table.fields:
        return
    for row in table.rows:
        computed = _optional_bool(row.get("gci_computed", ""))
        eligible = _optional_bool(row.get("gci_eligible", ""))
        if computed is True and eligible is not True:
            raise ReportEvidenceError(
                f"{table.path}: GCI is recorded without eligibility"
            )


def _validate_accepted_sample_audits(evidence: Evidence) -> None:
    required = (
        "pressure_relative_pair_force_residual",
        "viscosity_relative_pair_force_residual",
        "assembled_relative_internal_force",
        "accumulated_viscous_power",
        "pair_direct_viscous_power",
        "momentum_drift_absolute",
        "angular_momentum_drift_absolute",
        "state_all_finite",
        "neighbor_duplicate_edge_count",
        "neighbor_omitted_strict_support_edge_count",
        "neighbor_nonreciprocal_nonself_edge_count",
    )
    for run in evidence.run_summary.rows:
        if not _is_accepted(run.get("status", "")):
            continue
        run_id = _required_cell(run, "run_id")
        sample = evidence.samples.get(run_id)
        if sample is None or not sample.rows:
            raise ReportEvidenceError(
                f"accepted run {run_id} has no sample rows"
            )
        _require_fields(sample, required)
        for row_index, row in enumerate(sample.rows):
            if not _parse_bool(
                row["state_all_finite"],
                source=f"{sample.path}:row {row_index + 2}",
            ):
                continue
            for field in required:
                if field == "state_all_finite":
                    continue
                _finite_float(
                    row[field],
                    source=f"{sample.path}:{field}:row {row_index + 2}",
                )


def _gate_rows(
    evidence: Evidence,
    *gate_names: str,
) -> list[dict[str, str]]:
    names = {_normal_token(name) for name in gate_names}
    return [
        row
        for row in evidence.gate_rows
        if _normal_token(row.get("gate", "")) in names
    ]


def _protocol_rows(
    evidence: Evidence,
    *protocols: str,
) -> list[dict[str, str]]:
    names = {_normal_token(value) for value in protocols}
    return [
        row
        for row in evidence.run_summary.rows
        if _normal_token(row.get("protocol", "")) in names
    ]


def _first_recorded_failure(
    rows: Iterable[Mapping[str, str]],
) -> str | None:
    for row in rows:
        if _is_accepted(row.get("status", "")):
            continue
        parts = [
            f"run_id={row.get('run_id', '').strip() or 'UNRECORDED'}",
            f"status={row.get('status', '').strip() or 'UNRECORDED'}",
        ]
        for field in (
            "failure_class",
            "failure_reason",
            "first_failure_step",
            "first_failure_time",
        ):
            value = row.get(field, "").strip()
            if value:
                parts.append(f"{field}={value}")
        return "; ".join(parts)
    return None


def _failed_hard_gate_reason(
    evidence: Evidence,
    gate_names: Sequence[str],
) -> str | None:
    names = {_normal_token(value) for value in gate_names}
    for row in evidence.gate_rows:
        if _normal_token(row.get("gate", "")) not in names:
            continue
        if _normal_token(row.get("severity", "")) != "hard":
            continue
        try:
            passed = _parse_bool(
                row.get("passed", ""),
                source=str(evidence.derived["gates"].path),
            )
        except ReportEvidenceError:
            continue
        if passed:
            continue
        return (
            f"gate={row.get('gate', '')}; "
            f"check={row.get('check', '')}; "
            f"observed={row.get('observed', '')}; "
            f"source={row.get('source', '')}"
        )
    return None


def _branch_state(
    evidence: Evidence,
    *,
    name: str,
    protocols: Sequence[str],
    expected_runs: int,
    predecessor_gates: Sequence[str],
    derived_rows: Sequence[Mapping[str, str]] = (),
) -> BranchState:
    runs = _protocol_rows(evidence, *protocols)
    observed = len(runs)
    if observed == 0:
        state = "NOT_RUN"
    elif observed < expected_runs:
        state = "PARTIAL — REMAINDER NOT_RUN"
    else:
        state = "COMPLETE"

    reason = ""
    if state != "COMPLETE":
        reason = _first_recorded_failure(runs) or ""
        if not reason:
            for row in derived_rows:
                status = _normal_token(
                    row.get("execution_status", row.get("status", ""))
                )
                if status not in {"not_run", "blocked", "skipped"}:
                    continue
                reason = (
                    row.get("not_run_reason", "").strip()
                    or row.get("reason", "").strip()
                    or row.get("failure_reason", "").strip()
                    or row.get("detail", "").strip()
                )
                if reason:
                    break
        if not reason:
            predecessor_protocols = (
                "zero_flow",
                "smoke_n16",
                "smoke_n32",
                "time_convergence",
                "space_convergence",
                "support_family_comparison",
            )
            reason = (
                _first_recorded_failure(
                    _protocol_rows(evidence, *predecessor_protocols)
                )
                or ""
            )
        if not reason:
            reason = (
                _failed_hard_gate_reason(
                    evidence,
                    predecessor_gates,
                )
                or "机器证据未记录未执行原因；报告不得推断。"
            )
    return BranchState(
        name=name,
        observed_runs=observed,
        expected_runs=expected_runs,
        state=state,
        reason=reason,
    )


def _branch_paragraph(branch: BranchState) -> str:
    text = (
        f"执行状态：**{branch.state}**。run summary 中观察到 "
        f"{branch.observed_runs}/{branch.expected_runs} 个预期轨迹。"
    )
    if branch.reason:
        text += f"\n\n未执行或未完成原因（原样来自证据）：`{_md(branch.reason)}`。"
    return text


def _latest_sample_rows(
    evidence: Evidence,
    runs: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for run in runs:
        run_id = _required_cell(run, "run_id")
        table = evidence.samples.get(run_id)
        if table is None or not table.rows:
            output.append(
                {
                    "run_id": run_id,
                    "time": "NOT_AVAILABLE",
                }
            )
            continue
        if "time" in table.fields:
            latest = max(
                table.rows,
                key=lambda row: _finite_float(
                    row["time"],
                    source=f"{table.path}:time",
                ),
            )
        else:
            latest = table.rows[-1]
        output.append({"run_id": run_id, **latest})
    return output


def _sample_extreme(
    evidence: Evidence,
    field: str,
    *,
    accepted_only: bool,
    mode: str,
) -> tuple[float | None, str | None]:
    values: list[tuple[float, str]] = []
    for run in evidence.run_summary.rows:
        if accepted_only and not _is_accepted(run.get("status", "")):
            continue
        run_id = _required_cell(run, "run_id")
        sample = evidence.samples.get(run_id)
        if sample is None or field not in sample.fields:
            continue
        for row in sample.rows:
            text = row.get(field, "").strip()
            if not text:
                continue
            values.append(
                (
                    _finite_float(
                        text,
                        source=f"{sample.path}:{field}",
                    ),
                    run_id,
                )
            )
    if not values:
        return None, None
    selected = max(values) if mode == "max" else min(values)
    return selected


def _conservation_rows(evidence: Evidence) -> list[dict[str, Any]]:
    thresholds = _nested(
        evidence.configuration,
        "dynamic_conservation_thresholds",
    )
    metrics = (
        (
            "pressure_relative_pair_force_residual",
            "max",
            thresholds["maximum_relative_pair_force_residual"],
            "<=",
        ),
        (
            "viscosity_relative_pair_force_residual",
            "max",
            thresholds["maximum_relative_pair_force_residual"],
            "<=",
        ),
        (
            "relative_total_internal_force",
            "max",
            thresholds[
                "maximum_characteristic_normalized_internal_force_residual"
            ],
            "<=",
        ),
        (
            "assembled_relative_internal_force",
            "max",
            thresholds[
                "maximum_characteristic_normalized_internal_force_residual"
            ],
            "<=",
        ),
        (
            "accumulated_viscous_power",
            "max",
            thresholds["viscous_power_positive_absolute_tolerance"],
            "<=",
        ),
        (
            "pair_direct_viscous_power",
            "max",
            thresholds["viscous_power_positive_absolute_tolerance"],
            "<=",
        ),
        ("momentum_drift_absolute", "max", "diagnostic", ""),
        ("angular_momentum_drift_absolute", "max", "diagnostic", ""),
        ("minimum_separation", "min", "diagnostic", ""),
        ("neighbor_duplicate_edge_count", "max", 0, "=="),
        (
            "neighbor_omitted_strict_support_edge_count",
            "max",
            0,
            "==",
        ),
        (
            "neighbor_nonreciprocal_nonself_edge_count",
            "max",
            0,
            "==",
        ),
    )
    rows: list[dict[str, Any]] = []
    for field, mode, threshold, comparator in metrics:
        value, run_id = _sample_extreme(
            evidence,
            field,
            accepted_only=True,
            mode=mode,
        )
        rows.append(
            {
                "quantity": field,
                "accepted-sample extreme": value,
                "run_id": run_id,
                "threshold/role": (
                    f"{comparator} {threshold}"
                    if comparator
                    else threshold
                ),
            }
        )
    return rows


def _autograd_facts(evidence: Evidence) -> dict[str, Any]:
    rows = evidence.dynamic_autograd.rows
    pass_count = sum(
        _normal_token(row.get("status", "")) in {"pass", "passed"}
        for row in rows
    )
    short_values: list[float] = []
    step16_finite_nonzero = 0
    topology_claims: set[str] = set()
    for row in rows:
        steps = int(
            _finite_float(
                row.get("steps", ""),
                source=f"{evidence.dynamic_autograd.path}:steps",
            )
        )
        relative = _finite_float(
            row.get("relative_difference", ""),
            source=(
                f"{evidence.dynamic_autograd.path}:relative_difference"
            ),
        )
        if steps in {1, 3, 5, 8}:
            short_values.append(relative)
        if steps == 16:
            finite = _optional_bool(row.get("finite", ""))
            nonzero = _optional_bool(row.get("nonzero", ""))
            if finite is True and nonzero is True:
                step16_finite_nonzero += 1
        topology_claims.add(
            row.get("topology_differentiability_claimed", "").strip()
            or "UNRECORDED"
        )
    return {
        "row_count": len(rows),
        "pass_count": pass_count,
        "short_max_relative_difference": (
            max(short_values) if short_values else None
        ),
        "step16_finite_nonzero_count": step16_finite_nonzero,
        "topology_claim_values": ", ".join(sorted(topology_claims)),
    }


def _resource_overview(evidence: Evidence) -> list[dict[str, str]]:
    columns = [
        "run_id",
        "protocol",
        "status",
        "particle_count",
        "edge_count",
        "wall_clock_seconds",
        "mean_step_seconds",
        "peak_rss_bytes",
        "thermal_slowdown_fraction",
        "sustained_memory_pressure",
        "memory_growth_with_step",
    ]
    return [
        {column: row.get(column, "") for column in columns}
        for row in evidence.run_summary.rows
    ]


def _failure_rows(evidence: Evidence) -> list[dict[str, str]]:
    columns = (
        "run_id",
        "protocol",
        "status",
        "failure_class",
        "failure_reason",
        "first_failure_step",
        "first_failure_time",
        "failure_evidence_path",
    )
    return [
        {column: row.get(column, "") for column in columns}
        for row in evidence.run_summary.rows
        if not _is_accepted(row.get("status", ""))
    ]


def _manifest_facts(evidence: Evidence) -> dict[str, Any]:
    rows = evidence.manifest.rows
    return {
        "files": len(rows),
        "exists": sum(
            _parse_bool(
                row["exists"],
                source=str(evidence.manifest.path),
            )
            for row in rows
        ),
        "matches": sum(
            _parse_bool(
                row["matches_frozen_commit"],
                source=str(evidence.manifest.path),
            )
            for row in rows
        ),
        "commit": str(
            _nested(
                evidence.configuration,
                "frozen_stage_01c",
                "commit",
            )
        ),
    }


def _git_target(project_root: Path, reference: str) -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", f"{reference}^{{}}"),
            cwd=project_root,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise ReportEvidenceError(
            f"cannot resolve required git reference {reference!r}"
        ) from error
    value = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ReportEvidenceError(
            f"invalid git object for {reference!r}"
        )
    return value


def _format_number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "NONFINITE"
        if value == 0.0:
            return "0"
        magnitude = abs(value)
        if magnitude < 1.0e-3 or magnitude >= 1.0e5:
            return f"{value:.6e}"
        return f"{value:.7g}"
    text = str(value).strip()
    if not text:
        return "—"
    if re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?",
        text,
    ):
        try:
            return _format_number(float(text))
        except ValueError:
            pass
    return text


def _md(value: Any) -> str:
    return (
        _format_number(value)
        .replace("\n", "<br>")
        .replace("\r", "")
        .replace("|", r"\|")
    )


def _markdown_table(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[tuple[str, str]],
) -> str:
    if not rows:
        return "_无记录。_"
    available = {
        key
        for row in rows
        for key in row
    }
    selected = [
        (key, label) for key, label in columns if key in available
    ]
    if not selected:
        return "_无可显示字段。_"
    header = "| " + " | ".join(label for _, label in selected) + " |"
    divider = "|" + "|".join("---" for _ in selected) + "|"
    body = [
        "| "
        + " | ".join(_md(row.get(key)) for key, _ in selected)
        + " |"
        for row in rows
    ]
    return "\n".join((header, divider, *body))


def _gate_table(rows: Sequence[Mapping[str, Any]]) -> str:
    return _markdown_table(
        rows,
        (
            ("gate", "gate"),
            ("check", "check"),
            ("passed", "passed"),
            ("observed", "observed"),
            ("threshold", "threshold"),
            ("severity", "severity"),
            ("source", "source"),
            ("detail", "detail"),
        ),
    )


@lru_cache(maxsize=None)
def _sha256_cached(path_text: str) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _evidence_index(
    evidence: Evidence,
    paths: Iterable[Path],
) -> str:
    unique = sorted(
        {path.resolve() for path in paths},
        key=lambda path: _safe_relative(path, evidence.project_root),
    )
    rows: list[dict[str, Any]] = []
    for path in unique:
        _require_inside_project(
            path,
            evidence.project_root,
            label="report evidence",
        )
        if path.is_file():
            rows.append(
                {
                    "path": f"`{_safe_relative(path, evidence.project_root)}`",
                    "SHA-256": f"`{_sha256_cached(str(path))}`",
                    "bytes": path.stat().st_size,
                }
            )
        else:
            rows.append(
                {
                    "path": f"`{_safe_relative(path, evidence.project_root)}`",
                    "SHA-256": "MISSING",
                    "bytes": "MISSING",
                }
            )
    return _markdown_table(
        rows,
        (
            ("path", "evidence path"),
            ("SHA-256", "SHA-256"),
            ("bytes", "bytes"),
        ),
    )


def _base_paths(evidence: Evidence) -> list[Path]:
    return [
        evidence.config_path,
        evidence.run_summary.path,
        evidence.derived["gates"].path,
        evidence.status_path,
        evidence.generator_path,
    ]


def _sample_paths_for_runs(
    evidence: Evidence,
    runs: Iterable[Mapping[str, str]],
) -> list[Path]:
    paths: list[Path] = []
    for run in runs:
        run_id = _required_cell(run, "run_id")
        artifact = evidence.sample_artifacts.get(run_id)
        if artifact is not None:
            paths.append(artifact.path)
    return paths


def _date_line(evidence: Evidence) -> str:
    return f"日期：{evidence.configuration.get('date', 'UNRECORDED')}"


def _equation_text(evidence: Evidence) -> str:
    equations = _nested(evidence.configuration, "equations")
    return f"""完整状态由 `positions`、`velocities`、`masses`、`densities`、
`pressures`、`supports`、周期域和物理时间组成。预登记与实现采用：

\\[
\\rho_i=\\sum_j m_jW_{{ij}},
\\qquad
p_i=c_s^2(\\rho_i-\\rho_0),
\\]

\\[
\\mathbf f^p_{{ij}}=
-m_im_j\\left(\\frac{{p_i}}{{\\rho_i^2}}+
\\frac{{p_j}}{{\\rho_j^2}}\\right)\\nabla_iW_{{ij}},
\\]

\\[
\\mathbf f^\\nu_{{ij}}=
m_im_j\\Gamma_{{ij}}(\\mathbf v_j-\\mathbf v_i),
\\qquad
\\Gamma_{{ij}}={_md(equations['viscosity_gamma'])}.
\\]

密度、EOS、压力和两项内部作用在每个完整力阶段重新计算。配置明确记录
`background_pressure={equations['background_pressure']}`、
`pressure_clipping={equations['pressure_clipping']}`、
`artificial_viscosity={equations['artificial_viscosity']}`、
`particle_shifting={equations['particle_shifting']}` 和
`density_diffusion={equations['density_diffusion']}`。这些是冻结设计事实；
是否通过由机器 gate 与轨迹样本决定。"""


def _integrator_algorithm_text(evidence: Evidence) -> str:
    integrator = _nested(evidence.configuration, "integrator")
    return f"""时间推进器为 `{integrator['name']}`。对同步状态
\\((\\mathbf x^n,\\mathbf v^n)\\) 先计算完整起点作用，再构造

\\[
\\mathbf x^{{n+1/2}}=\\operatorname{{wrap}}
(\\mathbf x^n+\\tfrac12\\Delta t\\,\\mathbf v^n),\\qquad
\\mathbf v^{{n+1/2}}=\\mathbf v^n+
\\tfrac12\\Delta t\\,\\mathbf a^n .
\\]

中点重新建立周期互易邻域并重新计算密度、EOS 与内部加速度，随后

\\[
\\mathbf x^{{n+1}}=\\operatorname{{wrap}}
(\\mathbf x^n+\\Delta t\\,\\mathbf v^{{n+1/2}}),\\qquad
\\mathbf v^{{n+1}}=\\mathbf v^n+
\\Delta t\\,\\mathbf a^{{n+1/2}} .
\\]

接受步之后再同步终点密度和压力。预登记每步力阶段数为
{integrator['force_stages_per_step']}；独立 ODE 表负责证明实际阶数，报告
不凭 `RK2` 名称宣称二阶。"""


def _tgv_parameter_table(evidence: Evidence) -> str:
    tgv = _nested(evidence.configuration, "primary_tgv")
    backend = _nested(evidence.configuration, "backend")
    rows = [
        {"parameter": "domain", "value": "[-1,1) x [-1,1), periodic"},
        {"parameter": "rho0", "value": tgv["rho0"]},
        {"parameter": "U0", "value": tgv["U0"]},
        {"parameter": "L", "value": tgv["L"]},
        {"parameter": "nu", "value": tgv["physical_viscosity"]},
        {"parameter": "Re", "value": tgv["reynolds_number"]},
        {"parameter": "c_s", "value": tgv["sound_speed"]},
        {"parameter": "nominal Ma0", "value": tgv["nominal_mach"]},
        {"parameter": "t_final", "value": tgv["final_time"]},
        {"parameter": "device", "value": backend["device"]},
        {"parameter": "dtype", "value": backend["dtype"]},
    ]
    return _markdown_table(rows, (("parameter", "parameter"), ("value", "value")))


def _modal_definition_text() -> str:
    return r"""令
\[
\boldsymbol\phi(\mathbf x)=
[-\sin(\pi x)\cos(\pi y),\ \cos(\pi x)\sin(\pi y)] ,
\]
则代码记录的 TGV modal amplitude 是质量加权投影
\[
A_h(t)=
\frac{\sum_i m_i\,\mathbf v_i(t)\cdot\boldsymbol\phi(\mathbf x_i(t))}
{\sum_i m_i\,\lVert\boldsymbol\phi(\mathbf x_i(t))\rVert^2}.
\]
解析幅值为 \(A(t)=U_0\exp(-2\nu\pi^2t)\)。离散总动能为
\(E_h=\frac12\sum_i m_i\lVert\mathbf v_i\rVert^2\)，轨迹诊断的参考衰减为
\(E_{\mathrm{ref}}(t)=E_h(0)\exp(-4\nu\pi^2t)\)。"""


def _render_solver_assembly(evidence: Evidence) -> str:
    manifest = _manifest_facts(evidence)
    frozen = _nested(evidence.configuration, "frozen_stage_01c")
    actual_stage01c = _git_target(
        evidence.project_root,
        str(frozen["tag"]),
    )
    actual_stage01b = _git_target(
        evidence.project_root,
        str(frozen["stage_01b_tag"]),
    )
    freeze_rows = [
        {
            "item": "Stage 01C commit",
            "expected": frozen["commit"],
            "observed": actual_stage01c,
        },
        {
            "item": "Stage 01C annotated tag",
            "expected": frozen["required_tag_target"],
            "observed": actual_stage01c,
        },
        {
            "item": "Stage 01B tag",
            "expected": frozen["required_stage_01b_target"],
            "observed": actual_stage01b,
        },
        {
            "item": "manifest matches",
            "expected": manifest["files"],
            "observed": manifest["matches"],
        },
    ]
    zero_runs = _protocol_rows(evidence, "zero_flow")
    zero_endpoints = _latest_sample_rows(evidence, zero_runs)
    ad = _autograd_facts(evidence)
    evidence_paths = (
        _base_paths(evidence)
        + [evidence.manifest.path, evidence.stage01c_gate_status_path]
        + list(evidence.solver_sources)
        + _sample_paths_for_runs(evidence, evidence.run_summary.rows)
        + [evidence.dynamic_autograd.path]
    )
    return f"""# Stage 01D 动态求解器组装审计

{_date_line(evidence)}

最终 V2 状态文件记录：**`{evidence.final_status}`**。本报告只审计组装、
冻结 provenance 和已有机器 gate，不重新运行 TGV。

## 1. Stage 01C 冻结与 provenance

{_markdown_table(freeze_rows, (("item", "item"), ("expected", "expected"), ("observed", "observed")))}

Stage 01C 机器状态为 `{evidence.stage01c_gate_status}`。冻结清单共
{manifest['files']} 项，其中 {manifest['exists']} 项存在、{manifest['matches']}
项与冻结提交 SHA-256 一致。若这些数字不相等，事实会保留在本表，不能被
报告文字改写为通过。

## 2. 状态、密度、EOS 和内部作用

{_equation_text(evidence)}

## 3. 二阶显式中点组装

{_integrator_algorithm_text(evidence)}

## 4. 零流平衡证据

{_markdown_table(zero_runs, RUN_VIEW_COLUMNS)}

{_markdown_table(zero_endpoints, ENDPOINT_VIEW_COLUMNS)}

{_gate_table(_gate_rows(evidence, "Z"))}

## 5. 动态守恒和耗散

以下极值直接遍历 run summary 中所有 accepted 轨迹的每个保留采样点。
角动量仅作诊断；Stage 01C 已说明速度差黏性作用不保证逐 pair 中心力。

{_markdown_table(_conservation_rows(evidence), (("quantity", "quantity"), ("accepted-sample extreme", "extreme"), ("run_id", "run_id"), ("threshold/role", "threshold/role")))}

{_gate_table(_gate_rows(evidence, "C"))}

## 6. 完整动态自动微分

| quantity | observed |
|---|---:|
| dynamic AD rows | {_md(ad['row_count'])} |
| dynamic AD PASS rows | {_md(ad['pass_count'])} |
| 1/3/5/8-step maximum relative difference | {_md(ad['short_max_relative_difference'])} |
| 16-step finite and nonzero rows | {_md(ad['step16_finite_nonzero_count'])} |
| topology differentiability claim values | {_md(ad['topology_claim_values'])} |

{_gate_table(_gate_rows(evidence, "AD"))}

邻居索引选择仍是离散、非光滑过程；本报告不把连续 tensor value path
扩展解释为拓扑可微性。

## 7. 证据索引

{_evidence_index(evidence, evidence_paths)}
"""


def _render_integrator(evidence: Evidence) -> str:
    raw_columns = (
        ("problem", "problem"),
        ("method", "method"),
        ("dt", "dt"),
        ("steps", "steps"),
        ("error_L2", "error L2"),
        ("observed_order", "pair observed order"),
        ("git_hash", "git hash"),
        ("config_sha256", "config SHA-256"),
    )
    derived_columns = (
        ("problem", "problem"),
        ("all_required_dt_present", "all dt present"),
        ("every_error_level_decreases", "errors decrease"),
        ("fitted_order", "fitted order"),
        ("fitted_order_minimum", "fitted minimum"),
        ("finest_pair_observed_order", "finest pair order"),
        ("finest_pair_order_minimum", "finest minimum"),
        ("pass", "pass"),
        ("source", "source"),
    )
    paths = _base_paths(evidence) + [
        evidence.integrator_raw.path,
        evidence.derived["integrator_gate"].path,
    ]
    return f"""# Stage 01D 时间积分器验证

{_date_line(evidence)}

本报告使用两个独立 ODE 的实际 CSV；没有用求解器名称替代阶数证据。

## 1. 预登记问题

- 标量：`{_nested(evidence.configuration, 'integrator', 'scalar_ode', 'equation')}`；
- 耦合：`{_nested(evidence.configuration, 'integrator', 'coupled_ode', 'equation')}`；
- 时间步：`{json.dumps(_nested(evidence.configuration, 'integrator', 'time_steps'))}`。

## 2. 原始误差序列

{_markdown_table(evidence.integrator_raw.rows, raw_columns)}

## 3. evaluator 阶数门

{_markdown_table(evidence.derived['integrator_gate'].rows, derived_columns)}

{_gate_table(_gate_rows(evidence, "I"))}

只有 `both_ode_integrator_gates` 的机器记录通过，TGV 前置积分器门才可视为
通过；本报告不另行放宽 fitted-order 或 finest-pair 阈值。

## 4. 证据索引

{_evidence_index(evidence, paths)}
"""


def _time_branch(evidence: Evidence) -> BranchState:
    expected = len(
        _nested(evidence.configuration, "time_convergence", "time_steps")
    )
    return _branch_state(
        evidence,
        name="time convergence",
        protocols=("time_convergence",),
        expected_runs=expected,
        predecessor_gates=("I", "Z", "SMOKE"),
        derived_rows=evidence.derived["time"].rows,
    )


def _render_time(evidence: Evidence) -> str:
    branch = _time_branch(evidence)
    runs = _protocol_rows(evidence, "time_convergence")
    derived = evidence.derived["time"].rows
    endpoints = [
        row
        for row in derived
        if _normal_token(row.get("record_type", ""))
        == "analytic_endpoint"
    ]
    self_rows: dict[tuple[str, str], dict[str, str]] = {}
    for row in derived:
        if (
            _normal_token(row.get("record_type", ""))
            != "velocity_self_difference"
        ):
            continue
        key = (
            row.get("coarse_run_id", ""),
            row.get("fine_run_id", ""),
        )
        self_rows[key] = row
    endpoint_columns = (
        ("run_id", "run_id"),
        ("dt", "dt"),
        ("velocity_error_l1", "velocity L1"),
        ("velocity_relative_l2", "velocity rel. L2"),
        ("velocity_error_linf", "velocity Linf"),
        ("modal_amplitude_error", "modal error"),
        ("kinetic_energy_error", "energy error"),
        ("modal_observed_order", "modal observed order"),
        ("trajectory_finite", "finite"),
        ("sample_count", "samples"),
        ("analytic_platform_at_this_refinement", "platform"),
    )
    self_columns = (
        ("coarse_run_id", "coarse run"),
        ("fine_run_id", "fine run"),
        ("coarse_dt", "coarse dt"),
        ("fine_dt", "fine dt"),
        ("self_pair_trajectory_rms", "trajectory RMS difference"),
        ("self_pair_final_l2", "final L2 difference"),
        ("self_pair_observed_order", "observed order"),
        ("credible_time_trend_pass", "credible trend"),
    )
    paths = (
        _base_paths(evidence)
        + [evidence.derived["time"].path]
        + _sample_paths_for_runs(evidence, runs)
    )
    return f"""# Stage 01D TGV 时间收敛报告

{_date_line(evidence)}

{_branch_paragraph(branch)}

## 1. 固定配置

`N={_nested(evidence.configuration, 'time_convergence', 'resolution')}`，
`H/dx={_nested(evidence.configuration, 'time_convergence', 'support_ratio')}`，
`t_final={_nested(evidence.configuration, 'time_convergence', 'final_time')}`，
时间步为
`{json.dumps(_nested(evidence.configuration, 'time_convergence', 'time_steps'))}`。

{_modal_definition_text()}

## 2. 解析终点误差

{_markdown_table(endpoints, endpoint_columns)}

## 3. 21 个共同物理时刻的连续 dt 自收敛

{_markdown_table(list(self_rows.values()), self_columns)}

完整 21 点逐时刻差保存在 evaluator CSV，不在 Markdown 中删减或重新拟合。
若解析误差进入平台，报告只保留 `time_platform_detected` 的机器记录，不强制
宣称二阶。

## 4. 轨迹终点与运行诊断

{_markdown_table(_latest_sample_rows(evidence, runs), ENDPOINT_VIEW_COLUMNS)}

## 5. 时间 gate

{_gate_table(_gate_rows(evidence, "T"))}

## 6. 证据索引

{_evidence_index(evidence, paths)}
"""


def _space_branch(evidence: Evidence) -> BranchState:
    expected = len(
        _nested(
            evidence.configuration,
            "space_convergence",
            "primary_resolutions",
        )
    )
    return _branch_state(
        evidence,
        name="space convergence",
        protocols=("space_convergence",),
        expected_runs=expected,
        predecessor_gates=("I", "Z", "SMOKE", "T"),
        derived_rows=evidence.derived["space"].rows,
    )


def _space_metric_columns() -> tuple[tuple[str, str], ...]:
    return (
        ("support_family", "support family"),
        ("metric", "metric"),
        ("support_ratio_n16", "H/dx N16"),
        ("support_ratio_n24", "H/dx N24"),
        ("support_ratio_n32", "H/dx N32"),
        ("error_n16", "error N16"),
        ("error_n24", "error N24"),
        ("error_n32", "error N32"),
        ("ratio_n32_over_n16", "N32/N16"),
        (
            "fitted_log_error_log_dx_slope",
            "fitted log(error)-log(dx) slope",
        ),
        ("pair_order_n16_n24", "order 16->24"),
        ("pair_order_n24_n32", "order 24->32"),
        ("strictly_monotone_decreasing", "strict monotone"),
        ("near_asymptotic_order_agreement", "near asymptotic"),
        ("gci_eligible", "GCI eligible"),
        ("gci_computed", "GCI computed"),
    )


def _render_space(evidence: Evidence) -> str:
    branch = _space_branch(evidence)
    runs = _protocol_rows(evidence, "space_convergence")
    metrics = [
        row
        for row in evidence.derived["space"].rows
        if _normal_token(row.get("support_family", ""))
        == "increasing_neighbor"
    ]
    n48 = [
        row
        for row in runs
        if row.get("resolution", "").strip() == "48"
    ]
    n48_text = (
        "N=48 已执行并保留。"
        if n48
        else (
            "**NOT_RUN（可选确认点）**。现有证据没有 N=48 轨迹；是否满足 "
            "N=32 的 RSS/预计时长门应以 gate 与 run summary 为准，报告不推断。"
        )
    )
    paths = (
        _base_paths(evidence)
        + [evidence.derived["space"].path]
        + _sample_paths_for_runs(evidence, runs)
    )
    return f"""# Stage 01D TGV 空间收敛报告

{_date_line(evidence)}

{_branch_paragraph(branch)}

## 1. 主路线

固定 `dt={_nested(evidence.configuration, 'space_convergence', 'time_step')}`、
`t_final={_nested(evidence.configuration, 'space_convergence', 'final_time')}`。
主分辨率与支撑比来自
`space_convergence.resolutions_and_support_ratios`，没有根据结果改值。

{_markdown_table(metrics, _space_metric_columns())}

## 2. 终点误差与运行量

{_markdown_table(_latest_sample_rows(evidence, runs), ENDPOINT_VIEW_COLUMNS)}

## 3. 可选 N=48

{n48_text}

{_markdown_table(n48, RUN_VIEW_COLUMNS)}

## 4. Richardson/GCI 边界

本生成器不计算 Richardson 外推或 GCI。`gci_eligible` 仅转录 evaluator
对单调和近渐近条件的检查；任何 `gci_computed=True` 都必须同时有
`gci_eligible=True`，否则生成器拒绝报告。

## 5. 空间 gate

{_gate_table(_gate_rows(evidence, "S"))}

## 6. 证据索引

{_evidence_index(evidence, paths)}
"""


def _support_branch(evidence: Evidence) -> BranchState:
    config = _nested(evidence.configuration, "support_family_comparison")
    # The increasing-neighbor side is exactly the three primary space runs.
    # Only the constant-neighbor counterparts are additional run-summary rows.
    expected = len(config["resolutions"])
    return _branch_state(
        evidence,
        name="support family comparison",
        protocols=("support_family_comparison",),
        expected_runs=expected,
        predecessor_gates=("I", "Z", "SMOKE", "T", "S"),
        derived_rows=evidence.derived["space"].rows,
    )


def _render_support(evidence: Evidence) -> str:
    branch = _support_branch(evidence)
    runs = _protocol_rows(evidence, "support_family_comparison")
    metrics = evidence.derived["space"].rows
    paths = (
        _base_paths(evidence)
        + [evidence.derived["space"].path]
        + _sample_paths_for_runs(evidence, runs)
    )
    return f"""# Stage 01D 动态支撑族比较

{_date_line(evidence)}

{_branch_paragraph(branch)}

## 1. 比较设计

相同 fixed physics、规则布局、`dt={_nested(evidence.configuration, 'support_family_comparison', 'time_step')}`、
`t_final={_nested(evidence.configuration, 'support_family_comparison', 'final_time')}`。
constant-neighbor 使用 `H/dx=4`；increasing-neighbor 使用预登记的
`4.0, 4.5, 5.0`。配置明确禁止预设有限分辨率赢家。

## 2. 三个主误差及空间趋势

{_markdown_table(metrics, _space_metric_columns())}

## 3. 轨迹误差、成本与邻居数

{_markdown_table(runs, RUN_VIEW_COLUMNS)}

{_markdown_table(_latest_sample_rows(evidence, runs), ENDPOINT_VIEW_COLUMNS)}

## 4. 机器 gate

{_gate_table([row for row in _gate_rows(evidence, "S") if "support" in _normal_token(row.get("check", ""))])}

表格用于判断静态 truncation–quadrature tradeoff 是否出现在完整动态中；
生成器不从缺失、非单调或失败轨迹补造优胜结论。

## 5. 证据索引

{_evidence_index(evidence, paths)}
"""


def _disorder_branch(evidence: Evidence) -> BranchState:
    layouts = _nested(
        evidence.configuration,
        "disorder_robustness",
        "layouts",
    )
    expected = sum(len(seeds) for seeds in layouts.values())
    return _branch_state(
        evidence,
        name="disorder robustness",
        protocols=("disorder_robustness",),
        expected_runs=expected,
        predecessor_gates=("I", "Z", "SMOKE", "T", "S"),
        derived_rows=evidence.derived["disorder"].rows,
    )


def _render_disorder(evidence: Evidence) -> str:
    branch = _disorder_branch(evidence)
    runs = _protocol_rows(evidence, "disorder_robustness")
    summary_columns = (
        ("layout", "layout"),
        ("seeds", "seeds"),
        ("expected_seed_count", "expected"),
        ("observed_seed_count", "observed"),
        ("accepted_count", "accepted"),
        ("finite_count", "finite"),
        ("topology_pass_count", "topology pass"),
        ("core_gate_pass_count", "core gate pass"),
        ("failure_count", "failures"),
        ("first_failure_time", "first failure t"),
        ("layout_pass", "layout pass"),
        ("minimum_separation_over_dx", "min separation/dx"),
        (
            "velocity_relative_l2_max",
            "velocity rel. L2 max",
        ),
        (
            "modal_amplitude_error_max",
            "modal error max",
        ),
        (
            "kinetic_energy_error_max",
            "energy error max",
        ),
        (
            "density_fluctuation_relative_rms_max",
            "density fluct. max",
        ),
        (
            "momentum_drift_normalized_max",
            "momentum drift max",
        ),
    )
    seed_mapping = _nested(
        evidence.configuration,
        "disorder_robustness",
    )
    paths = (
        _base_paths(evidence)
        + [evidence.derived["disorder"].path]
        + _sample_paths_for_runs(evidence, runs)
    )
    return f"""# Stage 01D 动态粒子无序稳健性

{_date_line(evidence)}

{_branch_paragraph(branch)}

## 1. 预登记布局和种子

`N={seed_mapping['resolution']}`、`dt={seed_mapping['time_step']}`、
`H/dx={seed_mapping['support_ratio']}`、`t_final={seed_mapping['final_time']}`。
种子映射规则：{seed_mapping['seed_mapping_rule']}。

| layout | seeds |
|---|---|
| regular | `{json.dumps(seed_mapping['layouts']['regular'])}` |
| jitter_05 | `{json.dumps(seed_mapping['layouts']['jitter_05'])}` |
| jitter_10 | `{json.dumps(seed_mapping['layouts']['jitter_10'])}` |

## 2. evaluator 布局汇总

{_markdown_table(evidence.derived['disorder'].rows, summary_columns)}

## 3. 逐轨迹最后可用样本

{_markdown_table(_latest_sample_rows(evidence, runs), ENDPOINT_VIEW_COLUMNS)}

## 4. 失败轨迹

{_markdown_table(_failure_rows_for_protocols(evidence, ('disorder_robustness',)), (("run_id", "run_id"), ("status", "status"), ("failure_class", "class"), ("failure_reason", "reason"), ("first_failure_time", "failure t"), ("failure_evidence_path", "failure evidence")))}

## 5. 动态无序 gate

{_gate_table(_gate_rows(evidence, "D"))}

本部分只描述预登记的 7 个轨迹，不把三个种子解释为完整随机不确定性。

## 6. 证据索引

{_evidence_index(evidence, paths)}
"""


def _mach_branch(evidence: Evidence) -> BranchState:
    expected = len(
        _nested(
            evidence.configuration,
            "mach_sensitivity",
            "sound_speeds",
        )
    )
    return _branch_state(
        evidence,
        name="Mach sensitivity",
        protocols=("mach_sensitivity",),
        expected_runs=expected,
        predecessor_gates=("I", "Z", "SMOKE", "T", "S"),
        derived_rows=evidence.derived["mach"].rows,
    )


def _render_model_form(evidence: Evidence) -> str:
    branch = _mach_branch(evidence)
    runs = _protocol_rows(evidence, "mach_sensitivity")
    columns = (
        ("run_id", "run_id"),
        ("sound_speed", "c_s"),
        ("nominal_mach", "nominal Ma"),
        ("velocity_relative_l2", "velocity rel. L2"),
        (
            "density_fluctuation_relative_rms",
            "density fluct. rel. RMS",
        ),
        ("maximum_mach", "max Mach"),
        ("pressure_absolute_maximum", "max |p|"),
        ("wall_clock_seconds", "wall s"),
        ("peak_rss_bytes", "peak RSS bytes"),
        ("acoustic_cfl", "acoustic CFL"),
        ("accepted", "accepted"),
        ("trajectory_finite", "finite"),
        ("core_gate_pass", "core gates"),
        ("run_pass", "run pass"),
        (
            "velocity_error_improves_as_mach_decreases",
            "velocity improves",
        ),
        (
            "density_fluctuation_improves_as_mach_decreases",
            "density improves",
        ),
        (
            "weak_compressibility_model_form_classification",
            "classification",
        ),
    )
    paths = (
        _base_paths(evidence)
        + [evidence.derived["mach"].path]
        + _sample_paths_for_runs(evidence, runs)
    )
    return f"""# Stage 01D 弱可压模型形式评估

{_date_line(evidence)}

{_branch_paragraph(branch)}

## 1. 设计

规则布局 `N={_nested(evidence.configuration, 'mach_sensitivity', 'resolution')}`、
`dt={_nested(evidence.configuration, 'mach_sensitivity', 'time_step')}`、
`H/dx={_nested(evidence.configuration, 'mach_sensitivity', 'support_ratio')}`、
`t_final={_nested(evidence.configuration, 'mach_sensitivity', 'final_time')}`。
预登记 `c_s={json.dumps(_nested(evidence.configuration, 'mach_sensitivity', 'sound_speeds'))}`
与名义 Mach
`{json.dumps(_nested(evidence.configuration, 'mach_sensitivity', 'nominal_mach_numbers'))}`。

## 2. 误差、密度、压力、稳定性诊断和成本

{_markdown_table(evidence.derived['mach'].rows, columns)}

`acoustic_cfl` 是预登记的 time-step stability diagnostic。配置没有登记一个
把它直接变成“稳定余量通过线”的额外阈值，因此报告不事后发明阈值。增大
`c_s` 的 wall time、peak RSS 和 acoustic CFL 均保留在表中。

## 3. 逐轨迹最后可用样本

{_markdown_table(_latest_sample_rows(evidence, runs), ENDPOINT_VIEW_COLUMNS)}

## 4. 模型形式 gate

{_gate_table(_gate_rows(evidence, "M"))}

模型形式结论只转录 evaluator 的三点趋势与 classification；如果速度误差不随
Mach 降低而改善，报告不得把主要误差归给弱可压模型形式。

## 5. 证据索引

{_evidence_index(evidence, paths)}
"""


def _failure_rows_for_protocols(
    evidence: Evidence,
    protocols: Sequence[str],
) -> list[dict[str, str]]:
    names = {_normal_token(value) for value in protocols}
    return [
        row
        for row in _failure_rows(evidence)
        if _normal_token(row.get("protocol", "")) in names
    ]


def _status_table(evidence: Evidence) -> str:
    v3 = (
        "NOT STARTED"
        if _normal_token(evidence.v3_prior_status) == "not_started"
        else evidence.v3_prior_status
    )
    rows = [
        {
            "level": "V0",
            "status": evidence.v0_status,
            "basis": _safe_relative(
                evidence.v0_source_path,
                evidence.project_root,
            ),
        },
        {
            "level": "V1",
            "status": "REQUALIFIED — C1/C2/C3/C4 PASS",
            "basis": _safe_relative(
                evidence.stage01c_gate_status_path,
                evidence.project_root,
            ),
        },
        {
            "level": "V2",
            "status": evidence.final_status,
            "basis": _safe_relative(
                evidence.status_path,
                evidence.project_root,
            ),
        },
        {
            "level": "V3",
            "status": v3,
            "basis": _safe_relative(
                evidence.v0_source_path,
                evidence.project_root,
            ),
        },
    ]
    return _markdown_table(
        rows,
        (
            ("level", "level"),
            ("status", "current status"),
            ("basis", "direct evidence"),
        ),
    )


def _v3_decision(evidence: Evidence) -> str:
    if evidence.final_status == "V2_PASS":
        return (
            "**允许进入 V3 的独立预登记与资格化工作。** 这不等于 V3 已通过，"
            "也不自动授权 Stage 02。"
        )
    return (
        f"**不允许由本报告放行 V3。** 当前唯一 V2 状态为 "
        f"`{evidence.final_status}`；只有新的、明确授权才能改变该边界。"
    )


def _summary_gate_value(
    evidence: Evidence,
    gate: str,
) -> str:
    rows = _gate_rows(evidence, gate)
    if not rows:
        return "NOT_RECORDED"
    if all(
        _normal_token(row.get("severity", "")) == "not_run"
        for row in rows
    ):
        return "NOT_RUN"
    rows = [
        row
        for row in rows
        if _normal_token(row.get("severity", "")) != "not_run"
    ]
    if not rows:
        return "NOT_RUN"
    hard = [
        row
        for row in rows
        if _normal_token(row.get("severity", "")) == "hard"
    ]
    selected = hard or rows
    parsed = [
        _optional_bool(row.get("passed", ""))
        for row in selected
    ]
    if parsed and all(value is True for value in parsed):
        return "PASS"
    if any(value is False for value in parsed):
        return "FAIL"
    return "RECORDED"


def _all_evidence_paths(evidence: Evidence) -> list[Path]:
    paths = (
        _base_paths(evidence)
        + [
            evidence.manifest.path,
            evidence.integrator_raw.path,
            evidence.dynamic_autograd.path,
            evidence.stage01c_autograd_baseline.path,
            evidence.stage01c_gate_status_path,
            evidence.v0_source_path,
            evidence.stage01c_final_report_path,
        ]
        + [table.path for table in evidence.derived.values()]
        + list(evidence.solver_sources)
        + [
            artifact.path
            for artifact in evidence.sample_artifacts.values()
        ]
        + [artifact.path for artifact in evidence.run_artifacts]
    )
    if evidence.stage01c_autograd_regression is not None:
        paths.append(evidence.stage01c_autograd_regression.path)
    return paths


def _render_final(evidence: Evidence) -> str:
    time_branch = _time_branch(evidence)
    space_branch = _space_branch(evidence)
    support_branch = _support_branch(evidence)
    disorder_branch = _disorder_branch(evidence)
    mach_branch = _mach_branch(evidence)
    manifest = _manifest_facts(evidence)
    ad = _autograd_facts(evidence)
    failures = _failure_rows(evidence)
    frozen = _nested(evidence.configuration, "frozen_stage_01c")
    stage01c_target = _git_target(
        evidence.project_root,
        str(frozen["tag"]),
    )
    stage01b_target = _git_target(
        evidence.project_root,
        str(frozen["stage_01b_tag"]),
    )
    tgv = _nested(evidence.configuration, "primary_tgv")
    all_paths = _all_evidence_paths(evidence)
    return f"""# Stage 01D 固定物理动态解验证最终 V2 报告

{_date_line(evidence)}

## 最终状态

**`{evidence.final_status}`**

该状态逐字来自
`{_safe_relative(evidence.status_path, evidence.project_root)}`，并与
`stage01d_gate_evidence.csv` 的唯一状态行一致。报告生成器不重新判定、
升级或降级 V2，最终状态不存在第四种取值。

## 1. Stage 01C 冻结与 provenance

- 冻结提交：`{frozen['commit']}`；
- annotated tag `{frozen['tag']}` 实际解析到 `{stage01c_target}`；
- Stage 01B tag `{frozen['stage_01b_tag']}` 实际解析到
  `{stage01b_target}`；
- Stage 01C 机器状态：`{evidence.stage01c_gate_status}`；
- SHA-256 清单：{manifest['matches']}/{manifest['files']} 项匹配冻结提交。

这些事实来自冻结清单、git tag 对象和 Stage 01C 状态文件；未修改任何
Stage 00–01C 文件。

## 2. 动态求解器方程和算法

完整状态、周期 wrapping、互易无重复邻域、每阶段重算和 explicit midpoint
实现由 `01_solver/dynamic_solver/` 下八个源文件定义。各源文件实际
SHA-256 收录在本报告证据索引。

{_integrator_algorithm_text(evidence)}

## 3. 密度、EOS、压力和黏性形式

{_equation_text(evidence)}

## 4. 时间积分器验证

积分器 gate：**{_summary_gate_value(evidence, 'I')}**。原始 8 行 ODE
误差与 evaluator 的 fitted/finest-pair order 见
`{_safe_relative(evidence.integrator_raw.path, evidence.project_root)}` 和
`{_safe_relative(evidence.derived['integrator_gate'].path, evidence.project_root)}`。

{_markdown_table(evidence.derived['integrator_gate'].rows, (("problem", "problem"), ("every_error_level_decreases", "decreases"), ("fitted_order", "fitted order"), ("finest_pair_observed_order", "finest pair order"), ("pass", "pass")))}

## 5. 零流平衡

零流 gate：**{_summary_gate_value(evidence, 'Z')}**。

{_markdown_table(_protocol_rows(evidence, 'zero_flow'), RUN_VIEW_COLUMNS)}

{_markdown_table(_latest_sample_rows(evidence, _protocol_rows(evidence, 'zero_flow')), ENDPOINT_VIEW_COLUMNS)}

{_gate_table(_gate_rows(evidence, "Z"))}

## 6. 固定物理 TGV 参数

{_tgv_parameter_table(evidence)}

解析速度因子为 `{tgv['exact_velocity_factor']}`，能量衰减因子为
`{tgv['exact_energy_factor']}`。

{_modal_definition_text()}

## 7. 时间收敛

{_branch_paragraph(time_branch)}

时间 gate：**{_summary_gate_value(evidence, 'T')}**。解析终点、自收敛 21
共同时间点和平台标志见
`{_safe_relative(evidence.derived['time'].path, evidence.project_root)}`。

## 8. 空间收敛

{_branch_paragraph(space_branch)}

空间 gate：**{_summary_gate_value(evidence, 'S')}**。三个主误差的
log(error)–log(dx) 斜率、N32/N16 比值、单调性和 `gci_eligible` 全部来自
`{_safe_relative(evidence.derived['space'].path, evidence.project_root)}`。
本生成器没有计算 GCI。

## 9. 支撑族比较

{_branch_paragraph(support_branch)}

constant- 与 increasing-neighbor 的三个分辨率实际误差、运行时间和邻居数
分别保存在 derived space 表、run summary 与逐轨迹 CSV。没有预设有限
分辨率赢家。

## 10. 动态无序稳健性

{_branch_paragraph(disorder_branch)}

无序 gate：**{_summary_gate_value(evidence, 'D')}**。regular、5% jitter、
10% jitter 的布局汇总为：

{_markdown_table(evidence.derived['disorder'].rows, (("layout", "layout"), ("observed_seed_count", "runs"), ("accepted_count", "accepted"), ("failure_count", "failures"), ("layout_pass", "layout pass"), ("first_failure_time", "first failure t"), ("minimum_separation_over_dx", "min separation/dx")))}

## 11. Mach/模型形式评估

{_branch_paragraph(mach_branch)}

Mach gate：**{_summary_gate_value(evidence, 'M')}**。速度误差、密度波动、
最大 Mach、压力、acoustic CFL、wall time 与 RSS 均保存在：

{_markdown_table(evidence.derived['mach'].rows, (("sound_speed", "c_s"), ("nominal_mach", "nominal Ma"), ("velocity_relative_l2", "velocity rel. L2"), ("density_fluctuation_relative_rms", "density fluct."), ("maximum_mach", "max Mach"), ("pressure_absolute_maximum", "max |p|"), ("acoustic_cfl", "acoustic CFL"), ("wall_clock_seconds", "wall s"), ("peak_rss_bytes", "peak RSS"), ("weak_compressibility_model_form_classification", "classification"), ("run_pass", "run pass")))}

## 12. 动态守恒

以下数值直接来自所有 accepted 轨迹的保留采样点；压力/黏性 pair 残差与
实际组装的 \\(\\sum_i m_i\\mathbf a_i^{{internal}}\\) 分开报告。

{_markdown_table(_conservation_rows(evidence), (("quantity", "quantity"), ("accepted-sample extreme", "extreme"), ("run_id", "run_id"), ("threshold/role", "threshold/role")))}

机器守恒 gate：**{_summary_gate_value(evidence, 'C')}**。角动量是诊断量，
不是对非中心速度差黏性作用的结构守恒声明。

## 13. 自动微分回归

- full-dynamic AD：{ad['pass_count']}/{ad['row_count']} 行状态为 PASS；
- 1/3/5/8 步最大 AD–FD 相对差：
  `{_format_number(ad['short_max_relative_difference'])}`；
- 16 步 finite/nonzero：{ad['step16_finite_nonzero_count']} 行；
- topology claim 原始值：`{ad['topology_claim_values']}`；
- AD gate：**{_summary_gate_value(evidence, 'AD')}**。

邻域拓扑选择仍按离散、非光滑过程处理。

## 14. 资源使用

预登记停止线为 peak RSS
`{_nested(evidence.configuration, 'resource_stopping', 'peak_rss_bytes')}`
bytes、无 checkpoint 单实验预计
`{_nested(evidence.configuration, 'resource_stopping', 'projected_single_experiment_seconds_without_checkpoint')}`
seconds、后半段热降频增长
`{_nested(evidence.configuration, 'resource_stopping', 'second_half_mean_step_time_increase_fraction')}`。

{_markdown_table(_resource_overview(evidence), (("run_id", "run_id"), ("protocol", "protocol"), ("status", "status"), ("particle_count", "particles"), ("edge_count", "edges"), ("wall_clock_seconds", "wall s"), ("mean_step_seconds", "mean step s"), ("peak_rss_bytes", "peak RSS"), ("thermal_slowdown_fraction", "thermal slowdown"), ("sustained_memory_pressure", "memory pressure"), ("memory_growth_with_step", "RSS growth")))}

资源 gate：**{_summary_gate_value(evidence, 'R')}**。

## 15. 失败和限制

{_markdown_table(failures, (("run_id", "run_id"), ("protocol", "protocol"), ("status", "status"), ("failure_class", "failure class"), ("failure_reason", "failure reason"), ("first_failure_step", "step"), ("first_failure_time", "time"), ("failure_evidence_path", "failure evidence")))}

缺失或被硬门阻断的分支已在第 7–11 节标为 `NOT_RUN` 或
`PARTIAL — REMAINDER NOT_RUN`，并只引用机器证据中的原因。未记录的原因
明确保持“不可推断”，不补写有利解释。provenance gate：
**{_summary_gate_value(evidence, 'P')}**。

## 16. 当前 V0/V1/V2/V3 状态

{_status_table(evidence)}

## 17. 是否允许进入 V3

{_v3_decision(evidence)}

## 18. Stage 02 状态

**Stage 02 仍未开始。** 本阶段没有训练神经网络，没有实现
MLP/Transformer/attention，没有生成学习标签，也没有定义教师或学生求解器。
本报告不构成 Stage 02 授权。

## 19. 完整 V2 gate 矩阵

{_gate_table(evidence.gate_rows)}

## 20. 证据索引

下表给出本报告实际读取或直接引用的主证据路径、内容 SHA-256 与字节数。
路径均为项目相对路径，不写入用户名或主目录。

{_evidence_index(evidence, all_paths)}

## 最终声明

唯一最终状态保持为 **`{evidence.final_status}`**；Stage 02 未开始。
"""


def render_reports(evidence: Evidence) -> dict[str, str]:
    reports = {
        "stage_01d_solver_assembly_audit.md": _render_solver_assembly(
            evidence
        ),
        "stage_01d_integrator_verification.md": _render_integrator(
            evidence
        ),
        "stage_01d_time_convergence.md": _render_time(evidence),
        "stage_01d_space_convergence.md": _render_space(evidence),
        "stage_01d_support_family_comparison.md": _render_support(
            evidence
        ),
        "stage_01d_disorder_robustness.md": _render_disorder(evidence),
        "stage_01d_model_form_assessment.md": _render_model_form(
            evidence
        ),
        "stage_01d_final_v2_report.md": _render_final(evidence),
    }
    if tuple(reports) != REPORT_FILENAMES:
        raise ReportEvidenceError("internal report filename drift")
    normalized = {
        name: text.rstrip() + "\n"
        for name, text in reports.items()
    }
    _validate_rendered_reports(evidence, normalized)
    return normalized


def _validate_rendered_reports(
    evidence: Evidence,
    reports: Mapping[str, str],
) -> None:
    if set(reports) != set(REPORT_FILENAMES):
        raise ReportEvidenceError("not all eight reports were rendered")
    home_text = str(Path.home())
    for name, text in reports.items():
        if not text.startswith("# Stage 01D"):
            raise ReportEvidenceError(
                f"{name} does not begin with a Stage 01D heading"
            )
        if "## " not in text or "证据索引" not in text:
            raise ReportEvidenceError(
                f"{name} lacks sections or evidence index"
            )
        if home_text and home_text in text:
            raise ReportEvidenceError(
                f"{name} leaks an absolute home-directory path"
            )
        if "\r" in text:
            raise ReportEvidenceError(
                f"{name} contains non-LF line endings"
            )
    final = reports["stage_01d_final_v2_report.md"]
    if f"**`{evidence.final_status}`**" not in final:
        raise ReportEvidenceError("final report omits the sole V2 status")
    if "Stage 02 仍未开始" not in final:
        raise ReportEvidenceError(
            "final report omits the Stage 02 non-start statement"
        )
    for section in range(1, 19):
        if f"## {section}." not in final:
            raise ReportEvidenceError(
                f"final report is missing required item {section}"
            )


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
    output_root = output_root.resolve()
    targets = [output_root / name for name in REPORT_FILENAMES]
    collisions = [
        path for path in targets if path.exists() or path.is_symlink()
    ]
    if collisions:
        raise FileExistsError(
            "refusing to overwrite existing Stage 01D reports: "
            + ", ".join(str(path) for path in collisions)
        )
    for name in REPORT_FILENAMES:
        _atomic_write_new(output_root / name, reports[name])


def check_reports(
    reports: Mapping[str, str],
    *,
    output_root: Path,
) -> tuple[int, int]:
    present = 0
    matching = 0
    for name in REPORT_FILENAMES:
        path = output_root.resolve() / name
        if not path.is_file():
            continue
        present += 1
        if path.read_text(encoding="utf-8") != reports[name]:
            raise ReportEvidenceError(
                f"existing report differs from current evidence: {path}"
            )
        matching += 1
    return present, matching


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate eight Stage 01D Markdown reports from existing "
            "machine evidence; never run TGV."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Report directory; default is <project>/07_reports. "
            "Existing targets are never overwritten."
        ),
    )
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=None,
        help=(
            "Optional Stage 01D experiment root. It must remain inside "
            "the project; the default is the canonical experiment path."
        ),
    )
    parser.add_argument(
        "--integrator-csv",
        type=Path,
        default=None,
        help=(
            "Optional raw integrator CSV override inside the project. "
            "This is intended for isolated integration checks."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Validate all evidence and render in memory without writing. "
            "Existing reports, if present, must match byte-for-byte."
        ),
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    output_root = (
        (project_root / REPORT_ROOT_RELATIVE)
        if args.output_root is None
        else args.output_root.resolve()
    )
    try:
        evidence = Evidence.load(
            project_root,
            experiment_root=args.experiment_root,
            integrator_path=args.integrator_csv,
        )
        reports = render_reports(evidence)
        if args.check:
            present, matching = check_reports(
                reports,
                output_root=output_root,
            )
            print(
                "CHECK_OK "
                f"status={evidence.final_status} "
                f"rendered={len(reports)} "
                f"existing={present} matching={matching}"
            )
            return 0
        write_reports(reports, output_root=output_root)
    except (ReportEvidenceError, FileExistsError) as error:
        message = str(error)
        message = message.replace(
            str(project_root),
            "<PROJECT_ROOT>",
        )
        message = message.replace(str(Path.home()), "<HOME>")
        print(f"REPORT_ERROR: {message}", file=sys.stderr)
        return 2
    for name in REPORT_FILENAMES:
        path = (output_root / name).resolve()
        print(_safe_relative(path, project_root))
    print(evidence.final_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
