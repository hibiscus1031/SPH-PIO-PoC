"""One-process R5 GC-control or instrumentation-isolation rollout."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from typing import Any, Mapping

import torch
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr5_gc_cycle_localization"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_gc_cycle_localization.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"

from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
import dynamic_solver.periodic_rollout as rollout_module  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402
from resource_diagnostics.frozen_topology_control import (  # noqa: E402
    evaluate_frozen_topology_acceleration,
    freeze_initial_topology,
)
from resource_diagnostics.gc_cycle_tracker import GCCycleTracker  # noqa: E402
from resource_diagnostics.gc_schedule_probe import gc_scalar_snapshot, timed_collect  # noqa: E402
from resource_diagnostics.instrumentation_isolation import (  # noqa: E402
    ISOLATION_COMPONENTS,
    external_gc_type_snapshot,
    low_intrusion_rss_bytes,
)
from resource_diagnostics.semantic_tensor_ledger import SemanticTensorLedger  # noqa: E402
from resource_diagnostics.storage_lifetime_tracker import storage_keys  # noqa: E402
from resource_diagnostics.support_margin_control import edge_identity_sha256  # noqa: E402
from resource_diagnostics.weakref_tracker import walk_tensors  # noqa: E402
from structure_preserving.neighborhood import tensor_sha256  # noqa: E402


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
        writer.writerows(rows)


def _register_state(ledger: SemanticTensorLedger, state: Any, *, step: int) -> None:
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
        category="current_state",
        generation=step,
        current=True,
    )


def _register_evaluation(ledger: SemanticTensorLedger, evaluation: Any, *, step: int) -> None:
    neighborhood = evaluation.neighborhood
    ledger.register_many(
        {
            f"neighborhood.{name}": getattr(neighborhood, name)
            for name in (
                "row", "col", "displacement", "distance", "edge_support",
                "particle_support", "domain_min", "domain_max",
            )
        },
        category="current_neighborhood",
        generation=step,
        current=True,
    )
    ledger.register_many(
        {"evaluation.densities": evaluation.densities, "evaluation.pressures": evaluation.pressures},
        category="current_density_EOS",
        generation=step,
        current=True,
    )
    ledger.register(evaluation.pressure_force, category="current_pressure_force", slot="evaluation.pressure_force", generation=step)
    ledger.register(evaluation.viscosity_force, category="current_viscosity_force", slot="evaluation.viscosity_force", generation=step)
    ledger.register(evaluation.total_force, category="diagnostics_temporary", slot="evaluation.total_force", generation=step)
    ledger.register(evaluation.acceleration, category="diagnostics_temporary", slot="evaluation.acceleration", generation=step)


def _numerical_row(step: int, state: Any, evaluation: Any) -> dict[str, Any]:
    values = {
        "positions": state.positions,
        "velocities": state.velocities,
        "densities": evaluation.densities,
        "pressures": evaluation.pressures,
    }
    return {
        "step": step,
        **{f"{name}_sha256": tensor_sha256(value) for name, value in values.items()},
        "all_finite": all(bool(torch.isfinite(value).all()) for value in values.values()),
    }


def _run_rollout(
    *,
    configuration: Mapping[str, Any],
    run_id: str,
    mode: str,
    repeat: int,
) -> dict[str, Any]:
    physics = configuration["physics"]
    is_localization = mode == "L1"
    is_gc_control = mode.startswith("G")
    if is_localization:
        steps = int(configuration["localization"]["steps"])
    elif is_gc_control:
        steps = int(configuration["gc_controls"]["steps"])
    else:
        steps = int(configuration["isolation"]["steps"])
    components = frozenset({"weakref_tracker", "semantic_ledger", "observer_callback"}) if (is_gc_control or is_localization) else ISOLATION_COMPONENTS[mode]
    tracker_enabled = "weakref_tracker" in components
    ledger_enabled = "semantic_ledger" in components
    observer_enabled = "observer_callback" in components
    capture = run_id == str(configuration["localization"]["provenance_capture_run"])
    tracker = GCCycleTracker(
        minimum_old_age=int(configuration["classification"]["minimum_old_age_accepted_steps"]),
        capture_provenance=capture,
    ) if tracker_enabled else None
    ledger = SemanticTensorLedger() if ledger_enabled else None
    observer_rows: list[dict[str, Any]] = []
    lifetime_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    external_rows: list[dict[str, Any]] = []
    numerical_rows: list[dict[str, Any]] = []
    gc_mode = configuration["gc_controls"]["modes"].get(mode, {})
    was_enabled = gc.isenabled()
    if bool(gc_mode.get("disable_gc", False)):
        gc.disable()
    else:
        gc.enable()
    state = initialize_taylor_green_state(
        int(physics["resolution"]),
        support_ratio=float(physics["support_ratio"]),
        reference_density=1.0,
        velocity_amplitude=1.0,
        physical_viscosity=float(physics["physical_viscosity"]),
        sound_speed=float(physics["sound_speed"]),
        jitter_fraction=0.0,
        seed=int(physics["seed"]),
        domain_minimum=tuple(float(value) for value in physics["domain_minimum"]),
        domain_maximum=tuple(float(value) for value in physics["domain_maximum"]),
    )
    state = state.with_updates(velocities=torch.zeros_like(state.velocities))
    parameters = DynamicPhysicalParameters(
        reference_density=float(state.densities.mean()),
        sound_speed=float(physics["sound_speed"]),
        physical_viscosity=float(physics["physical_viscosity"]),
    )
    topology = freeze_initial_topology(state)
    true_evaluator = rollout_module.evaluate_internal_acceleration
    force_call = 0
    active_step = 0

    def evaluator(current_state: Any, current_parameters: Any) -> Any:
        nonlocal force_call
        force_call += 1
        evaluation = evaluate_frozen_topology_acceleration(current_state, current_parameters, topology)
        if observer_enabled:
            observer_rows.append(
                {
                    "force_call": force_call,
                    "accepted_step": active_step,
                    "edge_count": int(evaluation.neighborhood.row.numel()),
                    "edge_identity_sha256": edge_identity_sha256(evaluation.neighborhood),
                }
            )
        return evaluation

    rollout_module.evaluate_internal_acceleration = evaluator
    post_disabled_collect: dict[str, Any] = {
        "post_disabled_collect_objects": 0,
        "post_disabled_collect_wall_seconds": 0.0,
    }
    try:
        state, evaluation = prepare_dynamic_state(state, parameters)
        initial_positions = state.positions.detach().clone()
        if tracker is not None:
            tracker.register_current(step=0, named_values={"state": state, "evaluation": evaluation})
        if ledger is not None:
            _register_state(ledger, state, step=0)
            _register_evaluation(ledger, evaluation, step=0)
        numerical_rows.append(_numerical_row(0, state, evaluation))
        for step in range(1, steps + 1):
            active_step = step
            old_state = state
            old_evaluation = evaluation
            if tracker is not None:
                for slot in ("positions", "velocities", "densities", "pressures"):
                    tracker.watch_replacement(
                        generation=step - 1,
                        replacement_step=step,
                        semantic_slot=f"old_state.{slot}",
                        value=getattr(old_state, slot),
                    )
                tracker.watch_replacement(
                    generation=step - 1,
                    replacement_step=step,
                    semantic_slot="start_stage_neighborhood",
                    value=old_evaluation.neighborhood,
                )
            if ledger is not None:
                ledger.mark_noncurrent(walk_tensors(old_state))
                ledger.mark_noncurrent(walk_tensors(old_evaluation))
            started = time.perf_counter()
            result = explicit_midpoint_dynamic_step(
                state,
                dt=float(physics["time_step"]),
                parameters=parameters,
                start_evaluation=evaluation,
            )
            step_wall = time.perf_counter() - started
            if tracker is not None:
                tracker.watch_replacement(
                    generation=step - 1,
                    replacement_step=step,
                    semantic_slot="midpoint_neighborhood",
                    value=result.midpoint_evaluation.neighborhood,
                )
                tracker.watch_replacement(
                    generation=step - 1,
                    replacement_step=step,
                    semantic_slot="endpoint_neighborhood",
                    value=result.end_evaluation.neighborhood,
                )
            state = result.state
            evaluation = result.end_evaluation
            if tracker is not None:
                tracker.register_current(step=step, named_values={"state": state, "evaluation": evaluation})
            if ledger is not None:
                _register_state(ledger, state, step=step)
                _register_evaluation(ledger, evaluation, step=step)
            del result, old_state, old_evaluation
            manual = {"manual_gc_collected_objects": 0, "manual_gc_wall_seconds": 0.0}
            if mode == "G3" and step % int(gc_mode["collect_interval_steps"]) == 0:
                manual = timed_collect()
            lifetime = tracker.observe(step=step) if tracker is not None else {
                "retired_old_survivor_count": -1,
                "retired_old_survivor_bytes": -1,
                "same_slot_multigeneration_count": -1,
                "maximum_retired_generations_in_one_slot": -1,
                "retired_slot_count": -1,
            }
            current_keys = storage_keys((state, evaluation))
            current_live_bytes = int(sum(key[2] for key in current_keys))
            gc_row = gc_scalar_snapshot()
            lifetime_rows.append(
                {
                    "step": step,
                    **lifetime,
                    **gc_row,
                    **manual,
                    "current_rss_bytes": low_intrusion_rss_bytes(),
                    "live_current_tensor_bytes": current_live_bytes,
                    "edge_count": int(evaluation.neighborhood.row.numel()),
                    "step_wall_seconds": step_wall,
                }
            )
            if ledger is not None and step % 25 == 0:
                ledger_rows.append(ledger.snapshot(step=step)["summary"])
            if mode == "I0" and step % int(configuration["isolation"]["external_checkpoint_interval_steps"]) == 0:
                external_rows.append({"step": step, **external_gc_type_snapshot(), "current_rss_bytes": low_intrusion_rss_bytes()})
            if step <= 4:
                numerical_rows.append(_numerical_row(step, state, evaluation))
            if tracker is not None and step % 25 == 0:
                tracker.prune(step=step)
        finite = all(
            bool(torch.isfinite(value).all())
            for value in (state.positions, state.velocities, evaluation.densities, evaluation.pressures)
        )
        maximum_position_drift = float((state.positions - initial_positions).abs().max())
        maximum_velocity = float(state.velocities.abs().max())
    finally:
        rollout_module.evaluate_internal_acceleration = true_evaluator
        if mode == "G2":
            gc.enable()
            collected = timed_collect()
            post_disabled_collect = {
                "post_disabled_collect_objects": collected["manual_gc_collected_objects"],
                "post_disabled_collect_wall_seconds": collected["manual_gc_wall_seconds"],
            }
        elif not was_enabled:
            gc.disable()
    paths = {
        "lifetime": RESULTS_ROOT / "lifetime_curves" / f"{run_id}.csv",
        "ledger": RESULTS_ROOT / "ledger_samples" / f"{run_id}.csv",
        "external": RESULTS_ROOT / "external_type_counts" / f"{run_id}.csv",
        "observer": RESULTS_ROOT / "observer_samples" / f"{run_id}.csv",
        "numeric": RESULTS_ROOT / "numerical_hashes" / f"{run_id}.csv",
        "instances": RESULTS_ROOT / "retired_instances" / f"{run_id}.csv",
        "graphs": RESULTS_ROOT / "referrer_graphs" / f"{run_id}.json",
    }
    _write_csv(paths["lifetime"], lifetime_rows)
    _write_csv(paths["numeric"], numerical_rows)
    if ledger_rows:
        _write_csv(paths["ledger"], ledger_rows)
    if external_rows:
        _write_csv(paths["external"], external_rows)
    if observer_rows:
        _write_csv(paths["observer"], observer_rows)
    if tracker is not None and tracker.instance_rows:
        _write_csv(paths["instances"], tracker.instance_rows)
        _write_json(paths["graphs"], {"run_id": run_id, "graphs": tracker.referrer_graphs})
    return {
        "run_id": run_id,
        "mode": mode,
        "repeat": repeat,
        "steps": steps,
        "components": sorted(components),
        "completed_steps": steps,
        "all_state_values_finite": finite,
        "maximum_zero_flow_position_drift": maximum_position_drift,
        "maximum_zero_flow_velocity": maximum_velocity,
        "unique_edge_counts": len({int(row["edge_count"]) for row in lifetime_rows}),
        "edge_count_values": sorted({int(row["edge_count"]) for row in lifetime_rows}),
        "maximum_retired_old_survivor_count": max(int(row["retired_old_survivor_count"]) for row in lifetime_rows),
        "maximum_retired_old_survivor_bytes": max(int(row["retired_old_survivor_bytes"]) for row in lifetime_rows),
        "maximum_same_slot_multigeneration_count": max(int(row["same_slot_multigeneration_count"]) for row in lifetime_rows),
        "maximum_retired_generations_in_one_slot": max(int(row["maximum_retired_generations_in_one_slot"]) for row in lifetime_rows),
        "maximum_current_rss_bytes": max(int(row["current_rss_bytes"]) for row in lifetime_rows),
        "current_tensor_bytes_delta": int(lifetime_rows[-1]["live_current_tensor_bytes"]) - int(lifetime_rows[0]["live_current_tensor_bytes"]),
        "manual_gc_total_wall_seconds": sum(float(row["manual_gc_wall_seconds"]) for row in lifetime_rows),
        "manual_gc_total_collected_objects": sum(int(row["manual_gc_collected_objects"]) for row in lifetime_rows),
        "provenance_instance_count": 0 if tracker is None else len(tracker.instance_rows),
        "referrer_graph_count": 0 if tracker is None else len(tracker.referrer_graphs),
        **post_disabled_collect,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("L1", "G1", "G2", "G3", "I0", "I1", "I2", "I3", "I4"), required=True)
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("R5 worker requires sph-pio-poc")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.mode.startswith("I") and args.mode not in set(configuration["isolation"]["modes"]):
        raise SystemExit("isolation mode is not preregistered")
    run_id = f"stage01dr5_{args.mode.lower()}_r{args.repeat}"
    summary_path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
    failure_path = RESULTS_ROOT / "failures" / f"{run_id}.txt"
    if summary_path.exists():
        raise RuntimeError("refusing to overwrite R5 worker summary")
    summary: dict[str, Any] = {
        "run_id": run_id,
        "mode": args.mode,
        "repeat": args.repeat,
        "pid": os.getpid(),
        "git_hash": _git_hash(),
        "config_sha256": _sha256(CONFIG_PATH),
        "status": "FAIL",
    }
    try:
        result = _run_rollout(configuration=configuration, run_id=run_id, mode=args.mode, repeat=args.repeat)
        summary.update(result)
        summary["status"] = "PASS" if result["all_state_values_finite"] and int(result["completed_steps"]) > 0 else "FAIL"
    except BaseException as error:
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        failure_path.write_text(
            "".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"),
            encoding="utf-8",
        )
        summary.update(
            failure_type=type(error).__name__,
            failure_message=str(error).replace(str(Path.home()), "<HOME>"),
            failure_path=failure_path.relative_to(PROJECT_ROOT).as_posix(),
        )
    _write_json(summary_path, summary)
    print(json.dumps({"run_id": run_id, "status": summary["status"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
