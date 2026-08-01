"""Independent worker for one Stage 01D-R2 attribution control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Callable, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

OFFICIAL_CONFIG = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01dr2_storage_attribution"
    / "configs"
    / "preregistered_storage_attribution.yml"
)
OFFICIAL_RESULTS = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01dr2_storage_attribution"
    / "results"
)

from dynamic_solver import periodic_rollout as periodic_rollout_module  # noqa: E402
from dynamic_solver.acceleration import (  # noqa: E402
    DynamicPhysicalParameters,
    ForceEvaluation,
    evaluate_internal_acceleration,
)
from dynamic_solver.periodic_rollout import (  # noqa: E402
    explicit_midpoint_dynamic_step,
    prepare_dynamic_state,
)
from dynamic_solver.state import DynamicSPHState  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402
from resource_diagnostics.inventory_self_test import run_inventory_self_test  # noqa: E402
from resource_diagnostics.referrer_audit import audit_direct_referrers  # noqa: E402
from resource_diagnostics.rss_sampler import MemorySampler  # noqa: E402
from resource_diagnostics.semantic_tensor_ledger import SemanticTensorLedger  # noqa: E402
from resource_diagnostics.storage_lifetime_tracker import (  # noqa: E402
    StorageLifetimeTracker,
    storage_keys,
)
from resource_diagnostics.weakref_tracker import walk_tensors  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402


SCHEMA = "sph-pio-poc.stage01dr2.worker.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_hash() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True
    ).strip()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _redact(text: str) -> str:
    return text.replace(str(Path.home()), "<HOME>").replace(
        str(PROJECT_ROOT), "<PROJECT_ROOT>"
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class CsvSink:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: Any | None = None
        self.writer: csv.DictWriter | None = None
        self.fieldnames: list[str] | None = None

    def emit(self, row: Mapping[str, Any]) -> None:
        normalized = {
            key: (
                json.dumps(value, sort_keys=True, separators=(",", ":"))
                if isinstance(value, (dict, list, tuple, set))
                else value
            )
            for key, value in row.items()
        }
        if self.stream is None:
            if self.path.exists():
                raise RuntimeError(f"refusing to overwrite {_relative(self.path)}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = self.path.open("x", newline="", encoding="utf-8")
            self.fieldnames = list(normalized)
            self.writer = csv.DictWriter(
                self.stream, fieldnames=self.fieldnames, lineterminator="\n"
            )
            self.writer.writeheader()
        if set(normalized) != set(self.fieldnames or []):
            raise RuntimeError(f"CSV schema changed for {self.path.name}")
        assert self.writer is not None and self.stream is not None
        self.writer.writerow(normalized)
        self.stream.flush()

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


class JsonlSink:
    def __init__(self, path: Path) -> None:
        if path.exists():
            raise RuntimeError(f"refusing to overwrite {_relative(path)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.stream = path.open("x", encoding="utf-8")

    def emit(self, row: Mapping[str, Any]) -> None:
        self.stream.write(json.dumps(dict(row), sort_keys=True, allow_nan=False) + "\n")
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary": OFFICIAL_RESULTS / "run_summaries" / f"{run_id}.json",
        "config": OFFICIAL_RESULTS / "run_configs" / f"{run_id}.json",
        "memory": OFFICIAL_RESULTS / "memory_samples" / f"{run_id}.jsonl",
        "inventory": OFFICIAL_RESULTS / "inventory_validation" / f"{run_id}.csv",
        "ledger_summary": OFFICIAL_RESULTS / "ledger_summary" / f"{run_id}.csv",
        "ledger_tensors": OFFICIAL_RESULTS / "ledger_tensors" / f"{run_id}.jsonl",
        "weakref": OFFICIAL_RESULTS / "weakref_lifetime" / f"{run_id}.csv",
        "numerical": OFFICIAL_RESULTS / "numerical_regression" / f"{run_id}.csv",
        "referrers": OFFICIAL_RESULTS / "referrer_chains" / f"{run_id}.json",
        "failure": OFFICIAL_RESULTS / "failures" / f"{run_id}.txt",
    }


def _assert_new(paths: Mapping[str, Path], control: str) -> None:
    keys = {"summary", "config", "memory"}
    if control == "A":
        keys.add("inventory")
    else:
        keys.update({"ledger_summary", "ledger_tensors", "weakref", "referrers"})
    if control == "D":
        keys.add("numerical")
    existing = [paths[key] for key in keys if paths[key].exists()]
    if existing:
        raise RuntimeError(
            "worker outputs already exist: " + ", ".join(_relative(path) for path in existing)
        )


def _run_id(control: str, repeat: int, steps: int, primary_steps: int) -> str:
    if control == "D" and steps != primary_steps:
        return f"stage01dr2_d_confirm_{steps}"
    return f"stage01dr2_{control.lower()}_r{repeat}"


def _sample_steps(configuration: Mapping[str, Any], steps: int) -> set[int]:
    interval = int(configuration["sampling"]["ledger_interval_steps"])
    selected = set(range(0, steps + 1, interval))
    mandatory_key = (
        "confirmation_mandatory_steps"
        if steps > int(configuration["controls"]["D"]["steps"])
        else "mandatory_steps"
    )
    selected.update(
        int(value)
        for value in configuration["sampling"][mandatory_key]
        if int(value) <= steps
    )
    selected.add(steps)
    return selected


def _initialize(configuration: Mapping[str, Any], *, zero_flow: bool) -> tuple[DynamicSPHState, DynamicPhysicalParameters, float]:
    physics = configuration["physics"]
    state = initialize_taylor_green_state(
        int(physics["resolution"]),
        support_ratio=float(physics["support_ratio"]),
        reference_density=float(physics["reference_density"]),
        velocity_amplitude=float(physics["velocity_amplitude"]),
        physical_viscosity=float(physics["physical_viscosity"]),
        sound_speed=float(physics["sound_speed"]),
        jitter_fraction=0.0,
        seed=int(physics["seed"]),
        domain_minimum=tuple(float(value) for value in physics["domain_minimum"]),
        domain_maximum=tuple(float(value) for value in physics["domain_maximum"]),
    )
    reference_density = float(physics["reference_density"])
    if zero_flow:
        state = state.with_updates(velocities=torch.zeros_like(state.velocities))
        reference_density = float(state.densities.mean())
    parameters = DynamicPhysicalParameters(
        reference_density=reference_density,
        sound_speed=float(physics["sound_speed"]),
        physical_viscosity=float(physics["physical_viscosity"]),
    )
    return state, parameters, float(physics["time_step"])


def _register_state(
    ledger: SemanticTensorLedger,
    state: DynamicSPHState,
    *,
    generation: int,
    current: bool,
    category: str = "current_state",
) -> None:
    ledger.register_many(
        {
            "positions": state.positions,
            "velocities": state.velocities,
            "masses": state.masses,
            "densities": state.densities,
            "pressures": state.pressures,
            "supports": state.supports,
            "domain_min": state.domain_min,
            "domain_max": state.domain_max,
        },
        category=category,
        generation=generation,
        current=current,
    )


def _register_evaluation(
    ledger: SemanticTensorLedger,
    evaluation: ForceEvaluation,
    *,
    generation: int,
    current: bool,
    midpoint: bool = False,
) -> None:
    neighborhood = evaluation.neighborhood
    if midpoint:
        category_map = {
            "neighborhood": "RK2_midpoint",
            "density": "RK2_midpoint",
            "pressure": "RK2_midpoint",
            "pressure_force": "RK2_midpoint",
            "viscosity_force": "RK2_midpoint",
            "workspace": "RK2_midpoint",
        }
    else:
        category_map = {
            "neighborhood": "current_neighborhood",
            "density": "current_density_EOS",
            "pressure": "current_density_EOS",
            "pressure_force": "current_pressure_force",
            "viscosity_force": "current_viscosity_force",
            "workspace": "diagnostics_temporary",
        }
    ledger.register_many(
        {
            f"neighborhood.{name}": getattr(neighborhood, name)
            for name in (
                "row",
                "col",
                "displacement",
                "distance",
                "edge_support",
                "particle_support",
                "domain_min",
                "domain_max",
            )
        },
        category=category_map["neighborhood"],
        generation=generation,
        current=current,
    )
    ledger.register(evaluation.densities, category=category_map["density"], slot="evaluation.densities", generation=generation, current=current)
    ledger.register(evaluation.pressures, category=category_map["pressure"], slot="evaluation.pressures", generation=generation, current=current)
    ledger.register(evaluation.pressure_force, category=category_map["pressure_force"], slot="evaluation.pressure_force", generation=generation, current=current)
    ledger.register(evaluation.viscosity_force, category=category_map["viscosity_force"], slot="evaluation.viscosity_force", generation=generation, current=current)
    ledger.register(evaluation.total_force, category=category_map["workspace"], slot="evaluation.total_force", generation=generation, current=current)
    ledger.register(evaluation.acceleration, category=category_map["workspace"], slot="evaluation.acceleration", generation=generation, current=current)


def _watch_old_state(tracker: StorageLifetimeTracker, state: DynamicSPHState, step: int) -> None:
    tracker.watch(generation=step, semantic_slot="old_positions", value=state.positions)
    tracker.watch(generation=step, semantic_slot="old_velocities", value=state.velocities)
    tracker.watch(generation=step, semantic_slot="old_densities", value=state.densities)
    tracker.watch(generation=step, semantic_slot="old_pressures", value=state.pressures)


def _safe_memory_sample(
    sampler: MemorySampler,
    *,
    configuration: Mapping[str, Any],
    phase: str,
    step: int,
    edge_count: int,
    ledger_summary: Mapping[str, Any] | None = None,
    lifetime: Mapping[str, Any] | None = None,
) -> None:
    inventory = None
    if ledger_summary is not None:
        inventory = {
            **ledger_summary,
            "live_tensor_unique_storage_bytes": int(ledger_summary["live_total_bytes"]),
        }
    row = sampler.sample(
        phase=phase,
        step=step,
        edge_count=edge_count,
        tensor_inventory=inventory,
        retention=lifetime,
        include_system_pressure=step % 100 == 0,
    )
    if int(row["current_rss_bytes"]) > int(configuration["sampling"]["current_rss_stop_bytes"]):
        raise MemoryError("Stage 01D-R2 current RSS safety stop")
    free = row.get("system_memory_free_percent")
    if free is not None and float(free) < float(configuration["sampling"]["system_memory_free_percentage_stop"]):
        raise MemoryError("Stage 01D-R2 system memory pressure stop")


def _numerical_row(
    *,
    reference: Mapping[str, np.ndarray],
    step: int,
    state: DynamicSPHState,
    evaluation: ForceEvaluation,
) -> dict[str, Any]:
    index = int(np.nonzero(reference["steps"] == step)[0][0])
    observed = {
        "positions": state.positions,
        "velocities": state.velocities,
        "densities": evaluation.densities,
        "pressures": evaluation.pressures,
    }
    comparisons: dict[str, Any] = {}
    all_bitwise = True
    maximum_absolute = 0.0
    for field, tensor in observed.items():
        array = tensor.detach().cpu().contiguous().numpy()
        target = reference[field][index]
        bitwise = bool(np.array_equal(array, target))
        absolute = float(np.max(np.abs(array - target)))
        comparisons[field] = {"bitwise_equal": bitwise, "maximum_absolute_difference": absolute}
        all_bitwise = all_bitwise and bitwise
        maximum_absolute = max(maximum_absolute, absolute)
    return {
        "step": int(step),
        "all_state_values_finite": bool(
            all(torch.isfinite(value).all() for value in observed.values())
        ),
        "all_fields_bitwise_equal": bool(all_bitwise),
        "maximum_absolute_difference": float(maximum_absolute),
        "field_comparisons": comparisons,
    }


def _emit_ledger_checkpoint(
    *,
    step: int,
    ledger: SemanticTensorLedger,
    tracker: StorageLifetimeTracker,
    current_values: tuple[Any, ...],
    directed_edge_count: int,
    unique_pair_count: int,
    ledger_summary_sink: CsvSink,
    ledger_tensor_sink: JsonlSink,
    weakref_sink: CsvSink,
    referrer_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_keys = storage_keys(current_values)
    lifetime = tracker.observe(
        current_step=step, current_storage_keys=current_keys, collect=True
    )
    old_keys = set(lifetime.pop("old_survivor_storage_keys"))
    snapshot = ledger.snapshot(step=step, old_survivor_storage_keys=old_keys)
    snapshot["summary"]["directed_edge_count"] = int(directed_edge_count)
    snapshot["summary"]["unique_pair_count"] = int(unique_pair_count)
    ledger_summary_sink.emit(snapshot["summary"])
    for tensor_row in snapshot["tensors"]:
        ledger_tensor_sink.emit(tensor_row)
    weakref_sink.emit(lifetime)
    if lifetime["old_survivor_storage_count"]:
        survivors = tracker.surviving_tensor_objects(
            current_step=step,
            current_storage_keys=current_keys,
            minimum_age=2,
        )
        try:
            for slot, generation, value in survivors:
                referrer_rows.append(
                    {
                        "step": int(step),
                        "semantic_slot": slot,
                        "generation": int(generation),
                        "audit": audit_direct_referrers(value),
                    }
                )
        finally:
            del survivors
    tracker.prune(current_step=step)
    return snapshot["summary"], lifetime


def _run_static(
    *,
    configuration: Mapping[str, Any],
    sampler: MemorySampler,
    inventory_sink: CsvSink,
) -> dict[str, Any]:
    iterations = int(configuration["controls"]["A"]["iterations"])
    _safe_memory_sample(sampler, configuration=configuration, phase="before_inventory_loop", step=0, edge_count=0)
    result = run_inventory_self_test(iterations=iterations, row_sink=inventory_sink.emit)
    _safe_memory_sample(sampler, configuration=configuration, phase="after_inventory_loop", step=iterations, edge_count=0)
    return result


def _run_solver_control(
    *,
    control: str,
    steps: int,
    configuration: Mapping[str, Any],
    sampler: MemorySampler,
    ledger_summary_sink: CsvSink,
    ledger_tensor_sink: JsonlSink,
    weakref_sink: CsvSink,
    numerical_sink: CsvSink | None,
) -> dict[str, Any]:
    selected = _sample_steps(configuration, steps)
    ledger = SemanticTensorLedger()
    tracker = StorageLifetimeTracker(maximum_age=4)
    referrer_rows: list[dict[str, Any]] = []
    zero_flow = control == "C"
    state, parameters, dt = _initialize(configuration, zero_flow=zero_flow)
    if control in {"C", "D"}:
        state, evaluation = prepare_dynamic_state(state, parameters)
    else:
        evaluation = evaluate_internal_acceleration(state, parameters)
    _register_evaluation(ledger, evaluation, generation=0, current=True)
    _register_state(ledger, state, generation=0, current=True)
    initial_positions = state.positions.detach().clone() if zero_flow else None
    edge_counts: list[int] = [int(evaluation.neighborhood.row.numel())]
    maximum_old_survivor_bytes = 0
    maximum_old_survivor_count = 0
    maximum_unknown_bytes = 0
    reference: dict[str, np.ndarray] | None = None
    numerical_rows_pass = True
    if control == "D":
        reference_path = PROJECT_ROOT / configuration["numerical_regression"]["reference_archive"]
        with np.load(reference_path) as archive:
            reference = {key: archive[key].copy() for key in archive.files}
        assert numerical_sink is not None
        initial_numerical_row = _numerical_row(
            reference=reference, step=0, state=state, evaluation=evaluation
        )
        numerical_rows_pass = bool(
            initial_numerical_row["all_state_values_finite"]
            and initial_numerical_row["all_fields_bitwise_equal"]
        )
        numerical_sink.emit(initial_numerical_row)
    initial_unique_pairs = int(
        (evaluation.neighborhood.row <= evaluation.neighborhood.col).sum()
    )
    summary0, lifetime0 = _emit_ledger_checkpoint(
        step=0,
        ledger=ledger,
        tracker=tracker,
        current_values=(state, evaluation),
        directed_edge_count=edge_counts[0],
        unique_pair_count=initial_unique_pairs,
        ledger_summary_sink=ledger_summary_sink,
        ledger_tensor_sink=ledger_tensor_sink,
        weakref_sink=weakref_sink,
        referrer_rows=referrer_rows,
    )
    _safe_memory_sample(
        sampler,
        configuration=configuration,
        phase="initial_state",
        step=0,
        edge_count=edge_counts[0],
        ledger_summary=summary0,
        lifetime=lifetime0,
    )
    started = time.perf_counter()
    maximum_position_drift = 0.0
    maximum_velocity = 0.0
    for step in range(1, steps + 1):
        if control == "B":
            old_evaluation = evaluation
            ledger.mark_noncurrent(walk_tensors(old_evaluation))
            tracker.watch(generation=step, semantic_slot="start_stage_neighborhood", value=old_evaluation.neighborhood)
            tracker.watch(generation=step, semantic_slot="pressure_pair_result", value=old_evaluation.pressure_force)
            tracker.watch(generation=step, semantic_slot="viscosity_pair_result", value=old_evaluation.viscosity_force)
            evaluation = evaluate_internal_acceleration(state, parameters)
            _register_evaluation(ledger, evaluation, generation=step, current=True)
            tracker.watch(generation=step, semantic_slot="endpoint_neighborhood", value=evaluation.neighborhood)
            del old_evaluation
        else:
            old_state = state
            old_evaluation = evaluation
            ledger.mark_noncurrent(walk_tensors(old_state))
            ledger.mark_noncurrent(walk_tensors(old_evaluation))
            _watch_old_state(tracker, old_state, step)
            tracker.watch(generation=step, semantic_slot="start_stage_neighborhood", value=old_evaluation.neighborhood)
            original_evaluator = periodic_rollout_module.evaluate_internal_acceleration
            call_number = 0

            def observed_evaluator(
                observed_state: DynamicSPHState,
                observed_parameters: DynamicPhysicalParameters,
            ) -> ForceEvaluation:
                nonlocal call_number
                call_number += 1
                observed_evaluation = original_evaluator(observed_state, observed_parameters)
                if call_number == 1:
                    _register_state(ledger, observed_state, generation=step, current=False, category="RK2_midpoint")
                    _register_evaluation(ledger, observed_evaluation, generation=step, current=False, midpoint=True)
                    tracker.watch(generation=step, semantic_slot="midpoint_positions", value=observed_state.positions)
                    tracker.watch(generation=step, semantic_slot="midpoint_velocities", value=observed_state.velocities)
                    tracker.watch(generation=step, semantic_slot="midpoint_neighborhood", value=observed_evaluation.neighborhood)
                    tracker.watch(generation=step, semantic_slot="pressure_pair_result", value=observed_evaluation.pressure_force)
                    tracker.watch(generation=step, semantic_slot="viscosity_pair_result", value=observed_evaluation.viscosity_force)
                elif call_number == 2:
                    _register_evaluation(ledger, observed_evaluation, generation=step, current=True)
                    tracker.watch(generation=step, semantic_slot="endpoint_neighborhood", value=observed_evaluation.neighborhood)
                return observed_evaluation

            periodic_rollout_module.evaluate_internal_acceleration = observed_evaluator
            try:
                result = explicit_midpoint_dynamic_step(
                    state,
                    dt=dt,
                    parameters=parameters,
                    start_evaluation=evaluation,
                )
            finally:
                periodic_rollout_module.evaluate_internal_acceleration = original_evaluator
            if call_number != 2:
                raise RuntimeError(f"expected two force stages, observed {call_number}")
            state = result.state
            evaluation = result.end_evaluation
            _register_state(ledger, state, generation=step, current=True)
            del result, old_state, old_evaluation, observed_evaluator
            if zero_flow:
                assert initial_positions is not None
                maximum_position_drift = max(
                    maximum_position_drift,
                    float((state.positions - initial_positions).abs().max()),
                )
                maximum_velocity = max(maximum_velocity, float(state.velocities.abs().max()))
        edge_count = int(evaluation.neighborhood.row.numel())
        edge_counts.append(edge_count)
        current_keys = storage_keys((state, evaluation))
        lifetime = tracker.observe(
            current_step=step, current_storage_keys=current_keys, collect=False
        )
        lifetime.pop("old_survivor_storage_keys")
        weakref_sink.emit(lifetime)
        maximum_old_survivor_bytes = max(maximum_old_survivor_bytes, int(lifetime["old_survivor_bytes"]))
        maximum_old_survivor_count = max(maximum_old_survivor_count, int(lifetime["old_survivor_storage_count"]))
        if control == "D" and step <= 4:
            assert reference is not None and numerical_sink is not None
            numerical_row = _numerical_row(reference=reference, step=step, state=state, evaluation=evaluation)
            numerical_rows_pass = bool(
                numerical_rows_pass
                and numerical_row["all_state_values_finite"]
                and numerical_row["all_fields_bitwise_equal"]
            )
            numerical_sink.emit(numerical_row)
        if step in selected:
            ledger_summary, collected_lifetime = _emit_ledger_checkpoint(
                step=step,
                ledger=ledger,
                tracker=tracker,
                current_values=(state, evaluation),
                directed_edge_count=edge_count,
                unique_pair_count=int(
                    (evaluation.neighborhood.row <= evaluation.neighborhood.col).sum()
                ),
                ledger_summary_sink=ledger_summary_sink,
                ledger_tensor_sink=ledger_tensor_sink,
                weakref_sink=weakref_sink,
                referrer_rows=referrer_rows,
            )
            maximum_old_survivor_bytes = max(maximum_old_survivor_bytes, int(collected_lifetime["old_survivor_bytes"]))
            maximum_old_survivor_count = max(maximum_old_survivor_count, int(collected_lifetime["old_survivor_storage_count"]))
            maximum_unknown_bytes = max(maximum_unknown_bytes, int(ledger_summary["unknown_live_bytes"]))
            _safe_memory_sample(
                sampler,
                configuration=configuration,
                phase="solver_checkpoint",
                step=step,
                edge_count=edge_count,
                ledger_summary=ledger_summary,
                lifetime=collected_lifetime,
            )
    elapsed = time.perf_counter() - started
    finite = all(
        bool(torch.isfinite(value).all())
        for value in (state.positions, state.velocities, evaluation.densities, evaluation.pressures)
    )
    numerical_pass = bool(numerical_rows_pass)
    return {
        "completed_steps": int(steps),
        "planned_steps": int(steps),
        "all_state_values_finite": bool(finite),
        "initial_edge_count": int(edge_counts[0]),
        "final_edge_count": int(edge_counts[-1]),
        "unique_edge_count_values": len(set(edge_counts)),
        "minimum_edge_count": min(edge_counts),
        "maximum_edge_count": max(edge_counts),
        "maximum_old_survivor_bytes": int(maximum_old_survivor_bytes),
        "maximum_old_survivor_storage_count": int(maximum_old_survivor_count),
        "maximum_unknown_live_bytes": int(maximum_unknown_bytes),
        "referrer_chain_count": len(referrer_rows),
        "referrer_rows": referrer_rows,
        "mean_step_wall_seconds": float(elapsed / steps),
        "maximum_zero_flow_position_drift": float(maximum_position_drift),
        "maximum_zero_flow_velocity": float(maximum_velocity),
        "numerical_regression_collected": bool(reference is not None),
        "numerical_pass": bool(numerical_pass),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--control", choices=("A", "B", "C", "D"), required=True)
    parser.add_argument("--repeat", type=int, required=True)
    parser.add_argument("--steps", type=int, required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    output_root = Path(args.output_root).resolve()
    if config_path != OFFICIAL_CONFIG.resolve() or output_root != OFFICIAL_RESULTS.resolve():
        raise SystemExit("only official Stage 01D-R2 paths are allowed")
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("Stage 01D-R2 requires the sph-pio-poc environment")
    configuration = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    primary_steps = int(configuration["controls"][args.control].get("steps", configuration["controls"][args.control].get("iterations")))
    allowed_steps = {primary_steps}
    if args.control == "D":
        allowed_steps.add(int(configuration["controls"]["D"]["confirmation_steps"]))
    if args.steps not in allowed_steps:
        raise SystemExit("steps do not match the preregistered control")
    if args.repeat not in {1, 2, 3} and args.steps == primary_steps:
        raise SystemExit("primary repeat must be 1, 2, or 3")
    run_id = _run_id(args.control, args.repeat, args.steps, primary_steps)
    paths = _paths(run_id)
    _assert_new(paths, args.control)
    config_hash = _sha256(config_path)
    git_hash = _git_hash()
    _write_json(
        paths["config"],
        {
            "schema_version": SCHEMA,
            "run_id": run_id,
            "control": args.control,
            "repeat": args.repeat,
            "steps": args.steps,
            "config_sha256": config_hash,
            "git_hash": git_hash,
        },
    )
    memory_sink = JsonlSink(paths["memory"])
    sampler = MemorySampler(
        run_id=run_id,
        particle_count=0 if args.control == "A" else 1024,
        row_sink=memory_sink.emit,
        retain_rows=False,
    )
    sinks: list[Any] = [memory_sink]
    summary: dict[str, Any] = {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "control": args.control,
        "repeat": int(args.repeat),
        "planned_steps": int(args.steps),
        "completed_steps": 0,
        "status": "FAIL",
        "config_sha256": config_hash,
        "git_hash": git_hash,
        "pid": os.getpid(),
    }
    try:
        if args.control == "A":
            inventory_sink = CsvSink(paths["inventory"])
            sinks.append(inventory_sink)
            result = _run_static(
                configuration=configuration,
                sampler=sampler,
                inventory_sink=inventory_sink,
            )
            summary.update(result)
            summary["completed_steps"] = int(args.steps)
            passed = bool(result["inventory_self_retention_pass"] and result["view_and_base_deduplication_pass"])
        else:
            ledger_summary_sink = CsvSink(paths["ledger_summary"])
            ledger_tensor_sink = JsonlSink(paths["ledger_tensors"])
            weakref_sink = CsvSink(paths["weakref"])
            sinks.extend((ledger_summary_sink, ledger_tensor_sink, weakref_sink))
            numerical_sink = None
            if args.control == "D":
                numerical_sink = CsvSink(paths["numerical"])
                sinks.append(numerical_sink)
            result = _run_solver_control(
                control=args.control,
                steps=args.steps,
                configuration=configuration,
                sampler=sampler,
                ledger_summary_sink=ledger_summary_sink,
                ledger_tensor_sink=ledger_tensor_sink,
                weakref_sink=weakref_sink,
                numerical_sink=numerical_sink,
            )
            referrer_rows = result.pop("referrer_rows")
            _write_json(
                paths["referrers"],
                {"schema_version": SCHEMA, "run_id": run_id, "rows": referrer_rows},
            )
            summary.update(result)
            passed = bool(result["all_state_values_finite"] and result["completed_steps"] == args.steps)
        summary["status"] = "PASS" if passed else "FAIL"
    except BaseException as error:
        rendered = _redact("".join(traceback.format_exception(error)))
        paths["failure"].parent.mkdir(parents=True, exist_ok=True)
        paths["failure"].write_text(rendered, encoding="utf-8")
        summary.update(
            {
                "status": "FAIL",
                "failure_type": type(error).__name__,
                "failure_message": _redact(str(error)),
                "failure_path": _relative(paths["failure"]),
            }
        )
    finally:
        for sink in reversed(sinks):
            sink.close()
    _write_json(paths["summary"], summary)
    print(json.dumps({"run_id": run_id, "status": summary["status"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
