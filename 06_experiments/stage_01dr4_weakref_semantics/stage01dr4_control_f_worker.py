"""Short frozen-topology semantic replay for Stage 01D-R4."""

from __future__ import annotations

import argparse
import csv
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
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr4_weakref_semantics"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_weakref_semantics.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
R3_WORKER_PATH = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation" / "stage01dr3_worker.py"

from resource_diagnostics.storage_lifetime_tracker import StorageLifetimeTracker  # noqa: E402
from resource_diagnostics.weakref_semantics import WeakrefSemanticGate  # noqa: E402
from resource_diagnostics.weakref_tracker import tensor_storage_key  # noqa: E402


def _load_r3_worker() -> Any:
    specification = importlib.util.spec_from_file_location("stage01dr3_frozen_worker_for_r4", R3_WORKER_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load frozen R3 worker")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


R3 = _load_r3_worker()
R2 = R3.R2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            encoded["direct_referrer_type_names"] = json.dumps(
                row["direct_referrer_type_names"], separators=(",", ":")
            )
            writer.writerow(encoded)


def _r3_configuration(configuration: Mapping[str, Any]) -> dict[str, Any]:
    control = configuration["control_f"]
    return {
        "physics": {
            "resolution": int(control["resolution"]),
            "physical_viscosity": float(control["physical_viscosity"]),
            "sound_speed": float(control["sound_speed"]),
            "seed": int(control["seed"]),
            "domain_minimum": list(control["domain_minimum"]),
            "domain_maximum": list(control["domain_maximum"]),
            "time_step": float(control["time_step"]),
        },
        "controls": {
            "F": {
                "support_ratio": float(control["support_ratio"]),
                "steps": int(control["steps"]),
            }
        },
        "sampling": dict(configuration["sampling"]),
    }


class SemanticLifetimeAdapter(StorageLifetimeTracker):
    """Preserve the R3 tracker while adding the independent R4 semantic gate."""

    def __init__(self, *, maximum_age: int = 4, target_step: int) -> None:
        super().__init__(maximum_age=maximum_age)
        self.semantic_gate = WeakrefSemanticGate()
        self.target_step = int(target_step)
        self.fixed_edge_storage_keys: set[tuple[str, int, int]] = set()
        self.final_audit_rows: list[dict[str, Any]] = []
        self.final_semantic_summary: dict[str, Any] = {}
        self.maximum_semantic_old_storage_count = 0
        self.maximum_semantic_same_slot_count = 0

    def watch(self, *, generation: int, semantic_slot: str, value: Any) -> None:
        super().watch(generation=generation, semantic_slot=semantic_slot, value=value)
        self.semantic_gate.watch(
            generation=generation,
            semantic_slot=semantic_slot,
            value=value,
        )

    def observe(
        self,
        *,
        current_step: int,
        current_storage_keys: set[tuple[str, int, int]],
        collect: bool,
    ) -> dict[str, Any]:
        original = super().observe(
            current_step=current_step,
            current_storage_keys=current_storage_keys,
            collect=collect,
        )
        semantic = self.semantic_gate.observe(
            current_step=current_step,
            current_storage_keys=current_storage_keys,
            collect=False,
        )
        self.maximum_semantic_old_storage_count = max(
            self.maximum_semantic_old_storage_count,
            int(semantic["old_survivor_storage_count"]),
        )
        self.maximum_semantic_same_slot_count = max(
            self.maximum_semantic_same_slot_count,
            int(semantic["same_slot_multigeneration_count"]),
        )
        if int(current_step) == self.target_step:
            self.final_audit_rows = self.semantic_gate.audit_rows(
                current_step=current_step,
                include_referrers=True,
                fixed_edge_storage_keys=self.fixed_edge_storage_keys,
            )
            self.final_semantic_summary = dict(semantic)
        return original


class SemanticTopologyObserver(R3.TopologyObserver):
    def __init__(
        self,
        configuration: Mapping[str, Any],
        adapter_holder: dict[str, SemanticLifetimeAdapter],
    ) -> None:
        super().__init__(configuration, "F")
        self.adapter_holder = adapter_holder

    def evaluate(self, state: Any, parameters: Any) -> Any:
        evaluation = super().evaluate(state, parameters)
        accepted_step = self.call_count // 2
        adapter = self.adapter_holder.get("tracker")
        if adapter is not None:
            adapter.semantic_gate.register_current(
                step=accepted_step,
                named_values={
                    "current_state": state,
                    "current_frozen_neighborhood": evaluation.neighborhood,
                    "current_force_workspace": evaluation,
                },
            )
            if self.frozen is not None:
                adapter.fixed_edge_storage_keys = {
                    tensor_storage_key(self.frozen.row),
                    tensor_storage_key(self.frozen.col),
                }
        return evaluation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("R4 Control F requires sph-pio-poc")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    r3_configuration = _r3_configuration(configuration)
    run_id = f"stage01dr4_f_r{args.repeat}"
    paths = {
        "summary": RESULTS_ROOT / "run_summaries" / f"{run_id}.json",
        "config": RESULTS_ROOT / "run_configs" / f"{run_id}.json",
        "memory": RESULTS_ROOT / "memory_samples" / f"{run_id}.jsonl",
        "ledger": RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv",
        "ledger_tensors": RESULTS_ROOT / "ledger_tensors" / f"{run_id}.jsonl",
        "weakref": RESULTS_ROOT / "weakref_lifetime" / f"{run_id}.csv",
        "topology": RESULTS_ROOT / "topology_samples" / f"{run_id}.csv",
        "audit": RESULTS_ROOT / "semantic_weakref_audit" / f"{run_id}.csv",
        "semantic": RESULTS_ROOT / "semantic_summaries" / f"{run_id}.json",
        "referrers": RESULTS_ROOT / "referrer_chains" / f"{run_id}.json",
        "failure": RESULTS_ROOT / "failures" / f"{run_id}.txt",
    }
    if any(path.exists() for key, path in paths.items() if key != "failure"):
        raise RuntimeError("refusing to overwrite R4 Control F output")
    config_hash = _sha256(CONFIG_PATH)
    git_hash = _git_hash()
    _write_json(
        paths["config"],
        {
            "run_id": run_id,
            "repeat": args.repeat,
            "steps": int(configuration["control_f"]["steps"]),
            "git_hash": git_hash,
            "config_sha256": config_hash,
        },
    )
    memory_sink = R2.JsonlSink(paths["memory"])
    ledger_sink = R2.CsvSink(paths["ledger"])
    ledger_tensor_sink = R2.JsonlSink(paths["ledger_tensors"])
    weakref_sink = R2.CsvSink(paths["weakref"])
    topology_sink = R2.CsvSink(paths["topology"])
    sinks = (memory_sink, ledger_sink, ledger_tensor_sink, weakref_sink, topology_sink)
    sampler = R2.MemorySampler(
        run_id=run_id,
        particle_count=int(configuration["control_f"]["particles"]),
        row_sink=memory_sink.emit,
        retain_rows=False,
    )
    summary: dict[str, Any] = {
        "run_id": run_id,
        "repeat": args.repeat,
        "planned_steps": int(configuration["control_f"]["steps"]),
        "completed_steps": 0,
        "git_hash": git_hash,
        "config_sha256": config_hash,
        "pid": os.getpid(),
        "status": "FAIL",
    }
    holder: dict[str, SemanticLifetimeAdapter] = {}
    original_tracker_class = R2.StorageLifetimeTracker

    def tracker_factory(*, maximum_age: int = 4) -> SemanticLifetimeAdapter:
        tracker = SemanticLifetimeAdapter(
            maximum_age=maximum_age,
            target_step=int(configuration["control_f"]["steps"]),
        )
        holder["tracker"] = tracker
        return tracker

    observer = SemanticTopologyObserver(r3_configuration, holder)
    observer.true_evaluator = R2.periodic_rollout_module.evaluate_internal_acceleration
    true_evaluator = observer.true_evaluator
    try:
        R2.StorageLifetimeTracker = tracker_factory
        R2.periodic_rollout_module.evaluate_internal_acceleration = observer.evaluate
        result = R2._run_solver_control(
            control="C",
            steps=int(configuration["control_f"]["steps"]),
            configuration=R3._probe_configuration(r3_configuration, "F"),
            sampler=sampler,
            ledger_summary_sink=ledger_sink,
            ledger_tensor_sink=ledger_tensor_sink,
            weakref_sink=weakref_sink,
            numerical_sink=None,
        )
        for row in observer.topology_rows:
            topology_sink.emit(row)
        tracker = holder["tracker"]
        if observer.frozen is None:
            raise RuntimeError("frozen topology was not captured")
        audit_rows = tracker.final_audit_rows
        semantic = tracker.final_semantic_summary
        if not audit_rows or not semantic:
            raise RuntimeError("target-step semantic snapshot was not captured")
        semantic.update(
            audited_rows=len(audit_rows),
            fixed_initial_edge_index_rows=sum(
                bool(row["belongs_to_fixed_initial_edge_index"]) for row in audit_rows
            ),
            all_audited_current_persistent=all(
                row["semantic_class"] == "current_persistent_reference" for row in audit_rows
            ),
            all_audited_not_retired=all(
                not bool(row["is_retired_reference"]) for row in audit_rows
            ),
            maximum_semantic_old_survivor_storage_count=tracker.maximum_semantic_old_storage_count,
            maximum_semantic_same_slot_multigeneration_count=tracker.maximum_semantic_same_slot_count,
        )
        _write_csv(paths["audit"], audit_rows)
        _write_json(paths["semantic"], semantic)
        _write_json(
            paths["referrers"],
            {"run_id": run_id, "rows": result.pop("referrer_rows")},
        )
        summary.update(result)
        summary.update(observer.summary())
        summary["semantic_audited_rows"] = len(audit_rows)
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
            failure_type=type(error).__name__,
            failure_message=str(error).replace(str(Path.home()), "<HOME>"),
            failure_path=paths["failure"].relative_to(PROJECT_ROOT).as_posix(),
        )
    finally:
        R2.StorageLifetimeTracker = original_tracker_class
        R2.periodic_rollout_module.evaluate_internal_acceleration = true_evaluator
        for sink in reversed(sinks):
            sink.close()
    _write_json(paths["summary"], summary)
    print(json.dumps({"run_id": run_id, "status": summary["status"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
