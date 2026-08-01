"""One-process worker for a single Stage 01D-R diagnostic case.

Only standard-library modules and the lightweight RSS sampler are imported
before the ``process_start`` observation. Every invocation owns exactly one
rollout or one frozen-state regression and never runs a report generator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_CONFIG_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01dr_memory_diagnosis"
    / "configs"
    / "preregistered_memory_diagnosis.yml"
)
OFFICIAL_RESULTS_ROOT = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01dr_memory_diagnosis"
    / "results"
)
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from resource_diagnostics.rss_sampler import MemorySampler  # noqa: E402


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()


def _redact(value: str) -> str:
    rendered = value.replace(str(PROJECT_ROOT), "<PROJECT_ROOT>")
    rendered = rendered.replace(str(Path.home()), "<HOME>")
    return re.sub(r"/Users/[^/\\s:]+", "<HOME>", rendered)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _atomic_write_text(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite immutable output: {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise RuntimeError(f"stale temporary output exists: {_relative(temporary)}")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            dict(value),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
    )


def _fieldnames(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                ordered.append(str(key))
    return ordered


def _atomic_write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    if path.exists():
        raise RuntimeError(f"refusing to overwrite immutable output: {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=_fieldnames(rows),
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


class _StreamingCsvSink:
    """Flush scalar progress rows so a caught failure retains prior evidence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: Any | None = None
        self.writer: csv.DictWriter | None = None
        self.fieldnames: list[str] | None = None

    def emit(self, row: Mapping[str, Any]) -> None:
        keys = [str(key) for key in row]
        if self.stream is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = self.path.open("x", newline="", encoding="utf-8")
            self.fieldnames = keys
            self.writer = csv.DictWriter(
                self.stream,
                fieldnames=self.fieldnames,
                lineterminator="\n",
                extrasaction="raise",
            )
            self.writer.writeheader()
        elif set(keys) != set(self.fieldnames or []):
            raise RuntimeError(
                f"streaming CSV schema changed for {self.path.name}"
            )
        assert self.writer is not None
        assert self.stream is not None
        self.writer.writerow(dict(row))
        self.stream.flush()

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def _artifact_paths(output_root: Path, run_id: str) -> dict[str, Path]:
    experiment_root = output_root.parent
    return {
        "memory": output_root / "memory_samples" / f"{run_id}.jsonl",
        "diagnostics": output_root / "diagnostic_samples" / f"{run_id}.csv",
        "numerical": output_root / "numerical_samples" / f"{run_id}.csv",
        "retention": output_root / "retention_samples" / f"{run_id}.csv",
        "summary": output_root / "run_summaries" / f"{run_id}.json",
        "config": output_root / "run_configs" / f"{run_id}.json",
        "failure": output_root / "failures" / f"{run_id}.txt",
        "archive": experiment_root / "snapshots" / f"{run_id}.npz",
    }


def _classify_failure(error: BaseException) -> str:
    text = str(error).lower()
    if isinstance(error, MemoryError) or "rss safety" in text:
        return "RESOURCE_SAFETY_STOP"
    if isinstance(error, FloatingPointError) or "nonfinite" in text:
        return "NONFINITE_STATE"
    if "topology" in text:
        return "NEIGHBOR_TOPOLOGY_DEFECT"
    if "force residual" in text or "viscous power" in text:
        return "NUMERICAL_GATE_FAILURE"
    return "WORKER_EXCEPTION"


def _run_id(args: argparse.Namespace) -> str:
    if args.numeric_regression:
        return f"stage01dr_frozen_regression_n{args.resolution}"
    if args.variant == "D":
        return f"stage01dr_d_{args.mode}_n{args.resolution}_r{args.repeat}"
    return f"stage01dr_n{args.resolution}_v{args.variant.lower()}_r{args.repeat}"


def _assert_isolated_environment(expected_name: str) -> None:
    prefix_name = Path(sys.prefix).resolve().name
    if prefix_name != expected_name:
        raise RuntimeError(
            f"Stage 01D-R requires isolated environment {expected_name!r}; "
            f"interpreter prefix is {prefix_name!r}"
        )


def _preflight_new_artifacts(
    paths: Mapping[str, Path],
    *,
    numeric_regression: bool,
    variant: str,
) -> None:
    keys = {"memory", "summary", "config", "failure"}
    if numeric_regression:
        keys.add("numerical")
    else:
        keys.update({"diagnostics", "numerical", "retention"})
    if variant == "C" and not numeric_regression:
        keys.add("archive")
    candidates: list[Path] = []
    for key in sorted(keys):
        path = paths[key]
        candidates.append(path)
        candidates.append(path.with_name(path.name + ".tmp"))
        if key == "archive":
            candidates.append(path.with_name(path.name + ".tmp.npz"))
    existing = [path for path in candidates if path.exists()]
    if existing:
        raise RuntimeError(
            "refusing to overwrite existing worker artifact or temporary: "
            + ", ".join(_relative(path) for path in existing)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--variant", choices=("A", "B", "C", "D"), default="A")
    parser.add_argument("--resolution", type=int, choices=(16, 32), required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--mode", choices=("no_grad", "grad_enabled"), default=None)
    parser.add_argument("--numeric-regression", action="store_true")
    args = parser.parse_args()

    run_id = _run_id(args)
    config_path = Path(args.config).resolve()
    output_root = Path(args.output_root).resolve()
    if config_path != OFFICIAL_CONFIG_PATH.resolve():
        raise SystemExit("only the frozen Stage 01D-R configuration is allowed")
    if output_root != OFFICIAL_RESULTS_ROOT.resolve():
        raise SystemExit("only the Stage 01D-R results root is allowed")
    if args.numeric_regression and (args.variant != "A" or args.mode is not None):
        raise SystemExit("numeric regression must use the coordinator contract")
    if args.variant == "D" and args.mode is None:
        raise SystemExit("Variant D requires --mode")
    if args.variant != "D" and args.mode is not None:
        raise SystemExit("only Variant D accepts --mode")
    paths = _artifact_paths(output_root, run_id)
    _preflight_new_artifacts(
        paths,
        numeric_regression=args.numeric_regression,
        variant=args.variant,
    )
    paths["memory"].parent.mkdir(parents=True, exist_ok=True)
    memory_stream = paths["memory"].open("x", encoding="utf-8")

    def emit_memory_row(row: Mapping[str, Any]) -> None:
        memory_stream.write(_canonical_json(dict(row)) + "\n")
        memory_stream.flush()

    sampler = MemorySampler(
        run_id=run_id,
        particle_count=args.resolution**2,
        row_sink=emit_memory_row,
        retain_rows=False,
    )
    sampler.sample(
        phase="process_start",
        step=None,
        edge_count=None,
        include_system_pressure=True,
        note="before_numpy_torch_yaml_imports;pre_tensor_inventory",
    )

    # Heavy imports intentionally occur after process_start.
    import numpy as np  # noqa: PLC0415
    import torch  # noqa: PLC0415
    import yaml  # noqa: PLC0415

    from resource_diagnostics.rollout_memory_probe import (  # noqa: PLC0415
        ProbeArtifacts,
        run_frozen_state_regression,
        run_graph_sentinel,
        run_qualifying_probe,
        sample_memory_checkpoint,
    )

    configuration = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(configuration, dict):
        raise SystemExit("preregistered configuration must be a mapping")
    if configuration.get("status") != "PREREGISTERED_BEFORE_FIRST_STAGE_01DR_ROLLOUT":
        raise SystemExit("Stage 01D-R configuration is not preregistered")
    _assert_isolated_environment(
        str(configuration["backend"]["python_environment"])
    )
    config_hash = _sha256(config_path)
    git_hash = _git_hash()
    resolved = {
        "schema_version": "sph-pio-poc.stage01dr.worker-config.v1",
        "run_id": run_id,
        "variant": "NUMERIC_REGRESSION" if args.numeric_regression else args.variant,
        "resolution": args.resolution,
        "repeat": args.repeat,
        "mode": args.mode,
        "config_path": _relative(config_path),
        "config_sha256": config_hash,
        "git_hash": git_hash,
        "pid": os.getpid(),
        "python_version": sys.version.split()[0],
        "python_executable_name": Path(sys.executable).name,
        "numpy_version": np.__version__,
        "torch_version": torch.__version__,
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "one_rollout_per_process": True,
    }
    resolved["resolved_config_sha256"] = hashlib.sha256(
        _canonical_json(resolved).encode("utf-8")
    ).hexdigest()
    _atomic_write_json(paths["config"], resolved)

    streaming_sinks: list[_StreamingCsvSink] = []
    if args.numeric_regression:
        artifacts = ProbeArtifacts()
    else:
        diagnostic_sink = _StreamingCsvSink(paths["diagnostics"])
        numerical_sink = _StreamingCsvSink(paths["numerical"])
        retention_sink = _StreamingCsvSink(paths["retention"])
        streaming_sinks.extend(
            (diagnostic_sink, numerical_sink, retention_sink)
        )
        artifacts = ProbeArtifacts(
            diagnostic_sink=diagnostic_sink.emit,
            numerical_sink=numerical_sink.emit,
            retention_sink=retention_sink.emit,
        )
    status = "PASS"
    failure_class = ""
    failure_reason = ""
    return_code = 0
    try:
        sample_memory_checkpoint(
            sampler,
            configuration=configuration,
            phase="imports_complete",
            step=None,
            edge_count=None,
            step_wall_seconds=None,
            tracker=None,
            force_inventory=True,
            note="numpy_torch_yaml_solver_imports_complete",
        )
        if args.numeric_regression:
            comparison_records = run_frozen_state_regression(
                configuration=configuration,
                resolution=args.resolution,
            )
            for record in comparison_records:
                record["run_id"] = run_id
            artifacts.comparison_records.extend(comparison_records)
            if not all(
                bool(row["shape_exact"])
                and bool(row["dtype_exact"])
                and bool(row["bitwise_equal"])
                and bool(row["within_preregistered_tolerance"])
                for row in artifacts.comparison_records
            ):
                raise RuntimeError("frozen first-four state regression failed")
            artifacts.summary.update(
                {
                    "schema_version": "sph-pio-poc.stage01dr.numeric-regression.v1",
                    "run_id": run_id,
                    "variant": "NUMERIC_REGRESSION",
                    "resolution": args.resolution,
                    "status": "PASS",
                    "row_count": len(artifacts.comparison_records),
                    "bitwise_equal_count": sum(
                        bool(row["bitwise_equal"])
                        for row in artifacts.comparison_records
                    ),
                    "tolerance_pass_count": sum(
                        bool(row["within_preregistered_tolerance"])
                        for row in artifacts.comparison_records
                    ),
                    "config_hash": config_hash,
                    "git_hash": git_hash,
                }
            )
            sample_memory_checkpoint(
                sampler,
                configuration=configuration,
                phase="before_process_exit",
                step=4,
                edge_count=None,
                step_wall_seconds=None,
                tracker=None,
                force_inventory=True,
                note="numeric_regression_complete",
            )
        elif args.variant == "D":
            if args.mode is None:
                raise ValueError("Variant D requires --mode")
            run_graph_sentinel(
                configuration=configuration,
                run_id=run_id,
                mode=args.mode,
                config_hash=config_hash,
                git_hash=git_hash,
                sampler=sampler,
                artifacts=artifacts,
            )
        else:
            run_qualifying_probe(
                configuration=configuration,
                run_id=run_id,
                variant=args.variant,
                resolution=args.resolution,
                config_hash=config_hash,
                git_hash=git_hash,
                sampler=sampler,
                artifacts=artifacts,
                archive_path=(paths["archive"] if args.variant == "C" else None),
            )
    except BaseException as error:  # preserve the complete worker failure
        status = "FAIL"
        failure_class = _classify_failure(error)
        failure_reason = _redact(f"{type(error).__name__}: {error}")
        last_phase = str(
            artifacts.summary.get("last_completed_phase", "unknown")
        )
        if (
            args.variant == "C"
            and bool(artifacts.summary.get("solver_completed"))
            and last_phase == "before_archive"
        ):
            failure_phase = "archive"
        elif last_phase in {
            "initial_state_complete",
            "first_neighborhood_complete",
            "accepted_solver_step",
        }:
            failure_phase = "solver"
        else:
            failure_phase = last_phase
        artifacts.summary["failure_phase"] = failure_phase
        rendered = _redact(traceback.format_exc())
        _atomic_write_text(paths["failure"], rendered)
        return_code = 2

    for sink in streaming_sinks:
        sink.close()
    if args.numeric_regression:
        _atomic_write_csv(paths["numerical"], artifacts.comparison_records)
    memory_stream.close()
    summary = {
        **artifacts.summary,
        "schema_version": artifacts.summary.get(
            "schema_version", "sph-pio-poc.stage01dr.worker-summary.v1"
        ),
        "run_id": run_id,
        "status": status,
        "failure_class": failure_class,
        "failure_reason": failure_reason,
        "config_hash": config_hash,
        "git_hash": git_hash,
        "pid": os.getpid(),
        "memory_sample_count": sampler.sample_count,
        "memory_sample_path": _relative(paths["memory"]),
        "numerical_sample_path": (
            _relative(paths["numerical"]) if paths["numerical"].exists() else ""
        ),
        "diagnostic_sample_path": (
            _relative(paths["diagnostics"])
            if paths["diagnostics"].exists()
            else ""
        ),
        "retention_sample_path": (
            _relative(paths["retention"]) if paths["retention"].exists() else ""
        ),
        "failure_evidence_path": (
            _relative(paths["failure"]) if paths["failure"].exists() else ""
        ),
        "worker_config_path": _relative(paths["config"]),
    }
    _atomic_write_json(paths["summary"], summary)
    print(
        _canonical_json(
            {
                "run_id": run_id,
                "status": status,
                "failure_class": failure_class,
                "completed_steps": summary.get("completed_steps"),
                "memory_samples": sampler.sample_count,
            }
        )
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
