"""One-process Stage 01D-R3 Control F or M worker."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_topology_confirmation.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
R2_WORKER_PATH = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution" / "stage01dr2_worker.py"

from resource_diagnostics.cutoff_shell_audit import select_mid_shell_support  # noqa: E402
from resource_diagnostics.frozen_topology_control import (  # noqa: E402
    FrozenReciprocalTopology,
    evaluate_frozen_topology_acceleration,
    freeze_initial_topology,
)
from resource_diagnostics.support_margin_control import (  # noqa: E402
    edge_identity_sha256,
    lightweight_topology_invariants,
    make_margin_pair_set,
    minimum_cutoff_margin_ratio,
)
from structure_preserving.neighborhood import audit_periodic_neighborhood  # noqa: E402


def _load_r2_worker() -> Any:
    specification = importlib.util.spec_from_file_location("stage01dr2_frozen_worker", R2_WORKER_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load frozen R2 worker")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


R2 = _load_r2_worker()
SCHEMA = "sph-pio-poc.stage01dr3.worker.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary": RESULTS_ROOT / "run_summaries" / f"{run_id}.json",
        "config": RESULTS_ROOT / "run_configs" / f"{run_id}.json",
        "memory": RESULTS_ROOT / "memory_samples" / f"{run_id}.jsonl",
        "ledger_summary": RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv",
        "ledger_tensors": RESULTS_ROOT / "ledger_tensors" / f"{run_id}.jsonl",
        "weakref": RESULTS_ROOT / "weakref_lifetime" / f"{run_id}.csv",
        "referrers": RESULTS_ROOT / "referrer_chains" / f"{run_id}.json",
        "topology": RESULTS_ROOT / "topology_samples" / f"{run_id}.csv",
        "failure": RESULTS_ROOT / "failures" / f"{run_id}.txt",
    }


def _probe_configuration(configuration: Mapping[str, Any], control: str) -> dict[str, Any]:
    physics = configuration["physics"]
    return {
        "physics": {
            "resolution": int(physics["resolution"]),
            "support_ratio": float(configuration["controls"][control]["support_ratio"]),
            "reference_density": 1.0,
            "velocity_amplitude": 1.0,
            "physical_viscosity": float(physics["physical_viscosity"]),
            "sound_speed": float(physics["sound_speed"]),
            "seed": int(physics["seed"]),
            "domain_minimum": list(physics["domain_minimum"]),
            "domain_maximum": list(physics["domain_maximum"]),
            "time_step": float(physics["time_step"]),
        },
        "controls": {"D": {"steps": int(configuration["controls"][control]["steps"])}},
        "sampling": {
            "ledger_interval_steps": int(configuration["sampling"]["ledger_interval_steps"]),
            "mandatory_steps": list(configuration["sampling"]["mandatory_steps"]),
            "confirmation_mandatory_steps": list(configuration["sampling"]["mandatory_steps"]),
            "current_rss_stop_bytes": int(configuration["sampling"]["current_rss_stop_bytes"]),
            "system_memory_free_percentage_stop": float(configuration["sampling"]["system_memory_free_percentage_stop"]),
        },
    }


class TopologyObserver:
    def __init__(self, configuration: Mapping[str, Any], control: str) -> None:
        self.configuration = configuration
        self.control = control
        self.call_count = 0
        self.frozen: FrozenReciprocalTopology | None = None
        self.edge_counts: set[int] = set()
        self.edge_identities: set[str] = set()
        self.maximum_duplicate_edges = 0
        self.maximum_nonreciprocal_edges = 0
        self.maximum_omitted_strict_edges = 0
        self.maximum_unexpected_edges = 0
        self.minimum_cutoff_margin = float("inf")
        self.topology_rows: list[dict[str, Any]] = []
        self.margin_pairs: Any | None = None

    def evaluate(self, state: Any, parameters: Any) -> Any:
        self.call_count += 1
        true_evaluator = self.true_evaluator
        if self.control == "F":
            if self.frozen is None:
                self.frozen = freeze_initial_topology(state)
            evaluation = evaluate_frozen_topology_acceleration(
                state, parameters, self.frozen
            )
        else:
            evaluation = true_evaluator(state, parameters)
        invariant = lightweight_topology_invariants(evaluation.neighborhood)
        self.edge_counts.add(int(invariant["edge_count"]))
        self.edge_identities.add(str(invariant["edge_identity_sha256"]))
        self.maximum_duplicate_edges = max(
            self.maximum_duplicate_edges, int(invariant["duplicate_edge_count"])
        )
        self.maximum_nonreciprocal_edges = max(
            self.maximum_nonreciprocal_edges,
            int(invariant["nonreciprocal_edge_count"]),
        )
        if self.margin_pairs is None:
            selection = select_mid_shell_support(int(self.configuration["physics"]["resolution"]))
            extent = float(state.domain_extent[0])
            dx = extent / int(self.configuration["physics"]["resolution"])
            self.margin_pairs = make_margin_pair_set(
                resolution=int(self.configuration["physics"]["resolution"]),
                dx=dx,
                lower_shell=selection.target_shell,
                upper_shell=selection.next_shell,
            )
        margin = minimum_cutoff_margin_ratio(
            state,
            self.margin_pairs,
            float(self.configuration["controls"][self.control]["support_ratio"]),
        )
        self.minimum_cutoff_margin = min(self.minimum_cutoff_margin, margin)
        full_audit = self.call_count in {
            int(value)
            for value in self.configuration["sampling"]["full_topology_audit_force_call_indices"]
        }
        omitted = 0
        unexpected = 0
        if full_audit:
            audit = audit_periodic_neighborhood(state.positions, evaluation.neighborhood)
            omitted = int(audit["omitted_strict_support_edge_count"])
            unexpected = int(audit["unexpected_edge_count"])
            self.maximum_omitted_strict_edges = max(
                self.maximum_omitted_strict_edges, omitted
            )
            self.maximum_unexpected_edges = max(
                self.maximum_unexpected_edges, unexpected
            )
        self.topology_rows.append(
            {
                "force_call_index": self.call_count,
                "state_time": float(state.time),
                "edge_count": int(invariant["edge_count"]),
                "edge_identity_sha256": invariant["edge_identity_sha256"],
                "duplicate_edge_count": int(invariant["duplicate_edge_count"]),
                "nonreciprocal_edge_count": int(invariant["nonreciprocal_edge_count"]),
                "dimensionless_cutoff_margin": float(margin),
                "full_audit": bool(full_audit),
                "omitted_strict_support_edge_count": omitted,
                "unexpected_edge_count": unexpected,
            }
        )
        return evaluation

    def summary(self) -> dict[str, Any]:
        return {
            "force_evaluation_count": self.call_count,
            "unique_force_stage_edge_counts": len(self.edge_counts),
            "force_stage_edge_counts": sorted(self.edge_counts),
            "unique_force_stage_edge_identities": len(self.edge_identities),
            "maximum_duplicate_edge_count": self.maximum_duplicate_edges,
            "maximum_nonreciprocal_edge_count": self.maximum_nonreciprocal_edges,
            "maximum_omitted_strict_support_edge_count": self.maximum_omitted_strict_edges,
            "maximum_unexpected_edge_count": self.maximum_unexpected_edges,
            "minimum_dimensionless_cutoff_margin": self.minimum_cutoff_margin,
            "frozen_edge_identity_sha256": None if self.frozen is None else self.frozen.edge_key_sha256,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--control", choices=("F", "M"), required=True)
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    if Path(args.config).resolve() != CONFIG_PATH.resolve() or Path(args.output_root).resolve() != RESULTS_ROOT.resolve():
        raise SystemExit("only official Stage 01D-R3 paths are allowed")
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("Stage 01D-R3 requires the sph-pio-poc environment")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    run_id = f"stage01dr3_{args.control.lower()}_r{args.repeat}"
    paths = _paths(run_id)
    required = ("summary", "config", "memory", "ledger_summary", "ledger_tensors", "weakref", "referrers", "topology")
    existing = [paths[key] for key in required if paths[key].exists()]
    if existing:
        raise RuntimeError("refusing to overwrite R3 worker outputs")
    config_hash = _sha256(CONFIG_PATH)
    git_hash = _git_hash()
    _write_json(
        paths["config"],
        {
            "schema_version": SCHEMA,
            "run_id": run_id,
            "control": args.control,
            "repeat": args.repeat,
            "steps": int(configuration["controls"][args.control]["steps"]),
            "support_ratio": float(configuration["controls"][args.control]["support_ratio"]),
            "config_sha256": config_hash,
            "git_hash": git_hash,
        },
    )
    memory_sink = R2.JsonlSink(paths["memory"])
    ledger_summary_sink = R2.CsvSink(paths["ledger_summary"])
    ledger_tensor_sink = R2.JsonlSink(paths["ledger_tensors"])
    weakref_sink = R2.CsvSink(paths["weakref"])
    topology_sink = R2.CsvSink(paths["topology"])
    sinks = [memory_sink, ledger_summary_sink, ledger_tensor_sink, weakref_sink, topology_sink]
    sampler = R2.MemorySampler(
        run_id=run_id,
        particle_count=1024,
        row_sink=memory_sink.emit,
        retain_rows=False,
    )
    summary: dict[str, Any] = {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "control": args.control,
        "repeat": args.repeat,
        "planned_steps": int(configuration["controls"][args.control]["steps"]),
        "completed_steps": 0,
        "status": "FAIL",
        "config_sha256": config_hash,
        "git_hash": git_hash,
        "pid": os.getpid(),
    }
    observer = TopologyObserver(configuration, args.control)
    observer.true_evaluator = R2.periodic_rollout_module.evaluate_internal_acceleration
    true_evaluator = observer.true_evaluator
    try:
        R2.periodic_rollout_module.evaluate_internal_acceleration = observer.evaluate
        result = R2._run_solver_control(
            control="C",
            steps=int(configuration["controls"][args.control]["steps"]),
            configuration=_probe_configuration(configuration, args.control),
            sampler=sampler,
            ledger_summary_sink=ledger_summary_sink,
            ledger_tensor_sink=ledger_tensor_sink,
            weakref_sink=weakref_sink,
            numerical_sink=None,
        )
        referrer_rows = result.pop("referrer_rows")
        for row in observer.topology_rows:
            topology_sink.emit(row)
        _write_json(
            paths["referrers"],
            {"schema_version": SCHEMA, "run_id": run_id, "rows": referrer_rows},
        )
        summary.update(result)
        summary.update(observer.summary())
        summary["status"] = "PASS" if (
            result["all_state_values_finite"]
            and int(result["completed_steps"]) == int(summary["planned_steps"])
        ) else "FAIL"
    except BaseException as error:
        paths["failure"].parent.mkdir(parents=True, exist_ok=True)
        paths["failure"].write_text(
            "".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"),
            encoding="utf-8",
        )
        summary.update(
            {
                "status": "FAIL",
                "failure_type": type(error).__name__,
                "failure_message": str(error).replace(str(Path.home()), "<HOME>"),
                "failure_path": _relative(paths["failure"]),
            }
        )
    finally:
        R2.periodic_rollout_module.evaluate_internal_acceleration = true_evaluator
        for sink in reversed(sinks):
            sink.close()
    _write_json(paths["summary"], summary)
    print(json.dumps({"run_id": run_id, "status": summary["status"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
