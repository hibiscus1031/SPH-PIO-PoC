from __future__ import annotations

import csv
import gc
import json
from pathlib import Path
import sys
import weakref

import numpy as np
import pytest
import torch
import yaml

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.diagnostics import (
    collect_dynamic_diagnostics,
    validate_serializable_record,
)
from dynamic_solver.periodic_rollout import prepare_dynamic_state
from dynamic_solver.taylor_green import initialize_taylor_green_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = (
    PROJECT_ROOT / "06_experiments" / "stage_01dr_memory_diagnosis"
)
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))
import analyze_memory_diagnosis as memory_analysis  # noqa: E402


def test_stage01d_diagnostics_return_only_detached_json_scalars() -> None:
    state = initialize_taylor_green_state(6, support_ratio=2.0)
    state = state.with_updates(
        positions=state.positions.detach().clone().requires_grad_(True),
        velocities=state.velocities.detach().clone().requires_grad_(True),
    )
    state, evaluation = prepare_dynamic_state(
        state,
        DynamicPhysicalParameters(),
    )
    reference = weakref.ref(evaluation)
    with torch.no_grad():
        record = collect_dynamic_diagnostics(
            positions=state.positions,
            velocity=state.velocities,
            mass=state.masses,
            density=evaluation.densities,
            pressure=evaluation.pressures,
            sound_speed=20.0,
            neighborhood=evaluation.neighborhood,
            physical_viscosity=0.02,
            assembled_acceleration=evaluation.acceleration,
            time=0.0,
            run_id="detached_diagnostic_test",
            config_hash="0" * 64,
            git_hash="0" * 40,
            step=0,
            dt=5.0e-4,
        )

    validate_serializable_record(record, required_columns=True)
    json.dumps(record, allow_nan=False)
    forbidden = (torch.Tensor, np.ndarray, np.generic, dict, list, tuple, set)
    assert all(not isinstance(value, forbidden) for value in record.values())
    del evaluation
    gc.collect()
    assert reference() is None


def test_fractional_topology_value_cannot_be_truncated_to_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = yaml.safe_load(
        (
            EXPERIMENT_ROOT
            / "configs"
            / "preregistered_memory_diagnosis.yml"
        ).read_text()
    )
    run_id = "fractional_topology"
    topology = (
        "neighbor_duplicate_edge_count",
        "neighbor_missing_self_edge_count",
        "neighbor_nonreciprocal_nonself_edge_count",
        "neighbor_out_of_bounds_edge_count",
        "neighbor_omitted_strict_support_edge_count",
        "neighbor_unexpected_edge_count",
    )
    rows = []
    for step in configuration["sampling"]["minimal_safety_audit_steps"]:
        row = {
            "run_id": run_id,
            "step": step,
            "state_all_finite": True,
            "pressure_relative_pair_force_residual": 0.0,
            "viscosity_relative_pair_force_residual": 0.0,
            "relative_total_internal_force": 0.0,
            "viscous_power": 0.0,
            "momentum_drift_normalized": 0.0,
            "minimum_separation_over_dx": 1.0,
            **{key: 0 for key in topology},
        }
        rows.append(row)
    rows[-1]["neighbor_duplicate_edge_count"] = 0.5
    path = tmp_path / f"{run_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(memory_analysis, "NUMERICAL_ROOT", tmp_path)
    monkeypatch.setattr(memory_analysis, "PROJECT_ROOT", tmp_path)
    passed, evidence = memory_analysis._numerical_gate(
        run_id,
        configuration,
        {"variant": "A"},
    )
    assert passed is False
    assert evidence["topology_values_exact_nonnegative_integers"] is False
