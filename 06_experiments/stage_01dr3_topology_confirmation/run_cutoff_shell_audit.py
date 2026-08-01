"""Replay the deterministic R2 zero-flow cutoff switching for T1 evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr3_topology_confirmation"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_topology_confirmation.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
R2_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution" / "results"

import torch  # noqa: E402

from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402
from resource_diagnostics.cutoff_shell_audit import (  # noqa: E402
    edge_keys,
    offsets_on_shell,
    particle_offset,
    switched_edge_keys,
)
from structure_preserving.neighborhood import minimum_image  # noqa: E402


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
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _r2_sample_maps() -> dict[int, dict[int, int]]:
    maps: dict[int, dict[int, int]] = {}
    for repeat in (1, 2, 3):
        path = R2_RESULTS / "ledger_summary" / f"stage01dr2_c_r{repeat}.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            maps[repeat] = {
                int(row["step"]): int(row["directed_edge_count"])
                for row in csv.DictReader(stream)
            }
    return maps


def main() -> int:
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("cutoff audit requires the sph-pio-poc environment")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    sequence_path = RESULTS_ROOT / "cutoff_edge_count_sequence.csv"
    switches_path = RESULTS_ROOT / "cutoff_switch_edges.csv"
    identity_path = RESULTS_ROOT / "r2_c_sample_identity.csv"
    summary_path = RESULTS_ROOT / "cutoff_shell_audit_summary.json"
    if any(path.exists() for path in (sequence_path, switches_path, identity_path, summary_path)):
        raise RuntimeError("cutoff audit outputs already exist")
    physics = configuration["physics"]
    resolution = int(physics["resolution"])
    support_ratio = float(configuration["cutoff_shell"]["target_support_ratio"])
    state = initialize_taylor_green_state(
        resolution,
        support_ratio=support_ratio,
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
    state, evaluation = prepare_dynamic_state(state, parameters)
    initial_keys = edge_keys(
        evaluation.neighborhood.row,
        evaluation.neighborhood.col,
        state.particle_count,
    )
    dx = float(state.domain_extent[0]) / resolution
    q = evaluation.neighborhood.distance / dx
    shell_mask = torch.abs(q - 5.0) <= 1.0e-12
    initial_shell_edge_count = int(shell_mask.sum())
    initial_minimum_relative_cutoff_distance = float(
        torch.min(
            torch.abs(
                evaluation.neighborhood.distance[shell_mask]
                / evaluation.neighborhood.edge_support[shell_mask]
                - 1.0
            )
        )
    )
    r2_maps = _r2_sample_maps()
    sequence_rows: list[dict[str, Any]] = []
    switch_rows: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    count_values: set[int] = set()
    all_finite = True
    replay_steps = int(configuration["cutoff_shell"]["replay_steps"])
    cutoff_tolerance = float(configuration["cutoff_shell"]["near_cutoff_absolute_ratio_tolerance"])

    def record(step: int) -> None:
        nonlocal all_finite
        current_keys = edge_keys(
            evaluation.neighborhood.row,
            evaluation.neighborhood.col,
            state.particle_count,
        )
        removed, added = switched_edge_keys(initial_keys, current_keys)
        edge_count = int(current_keys.numel())
        count_values.add(edge_count)
        sequence_rows.append(
            {
                "step": step,
                "edge_count": edge_count,
                "removed_vs_initial": int(removed.numel()),
                "added_vs_initial": int(added.numel()),
            }
        )
        for action, keys in (("removed", removed), ("added", added)):
            for key in keys.tolist():
                row = int(key) // state.particle_count
                col = int(key) % state.particle_count
                offset_x, offset_y = particle_offset(row, col, resolution)
                displacement = minimum_image(
                    state.positions[row] - state.positions[col],
                    state.domain_extent,
                )
                relative = float(torch.linalg.vector_norm(displacement) / state.supports[row])
                switch_rows.append(
                    {
                        "step": step,
                        "edge_count": edge_count,
                        "action": action,
                        "edge_key": int(key),
                        "row": row,
                        "col": col,
                        "offset_x": offset_x,
                        "offset_y": offset_y,
                        "lattice_shell": float((offset_x**2 + offset_y**2) ** 0.5),
                        "relative_distance_r_over_H": relative,
                        "absolute_relative_cutoff_distance": abs(relative - 1.0),
                        "near_cutoff": abs(relative - 1.0) <= cutoff_tolerance,
                    }
                )
        for repeat, samples in r2_maps.items():
            if step in samples:
                identity_rows.append(
                    {
                        "repeat": repeat,
                        "step": step,
                        "r2_edge_count": samples[step],
                        "r3_replay_edge_count": edge_count,
                        "identical": samples[step] == edge_count,
                    }
                )
        all_finite = bool(
            all_finite
            and torch.isfinite(state.positions).all()
            and torch.isfinite(state.velocities).all()
            and torch.isfinite(evaluation.densities).all()
            and torch.isfinite(evaluation.pressures).all()
        )

    with torch.no_grad():
        record(0)
        for step in range(1, replay_steps + 1):
            result = explicit_midpoint_dynamic_step(
                state,
                dt=float(physics["time_step"]),
                parameters=parameters,
                start_evaluation=evaluation,
            )
            state = result.state
            evaluation = result.end_evaluation
            record(step)
    if not switch_rows:
        raise RuntimeError("replay did not reproduce cutoff switching")
    all_switches_q5 = all(float(row["lattice_shell"]) == 5.0 for row in switch_rows)
    all_switches_near_cutoff = all(bool(row["near_cutoff"]) for row in switch_rows)
    identity_pass = all(bool(row["identical"]) for row in identity_rows)
    _write_csv(sequence_path, sequence_rows)
    _write_csv(switches_path, switch_rows)
    _write_csv(identity_path, identity_rows)
    _write_json(
        summary_path,
        {
            "schema_version": "sph-pio-poc.stage01dr3.cutoff-audit.v1",
            "git_hash": _git_hash(),
            "config_sha256": _sha256(CONFIG_PATH),
            "resolution": resolution,
            "support_ratio": support_ratio,
            "q5_offsets": [list(value) for value in offsets_on_shell(resolution, 5.0)],
            "expected_q5_offset_count": 12,
            "initial_q5_directed_edge_count": initial_shell_edge_count,
            "initial_minimum_absolute_r_over_H_minus_one": initial_minimum_relative_cutoff_distance,
            "edge_count_values": sorted(count_values),
            "unique_switched_edge_keys": len({int(row["edge_key"]) for row in switch_rows}),
            "all_switches_on_q5_shell": all_switches_q5,
            "all_switches_near_cutoff": all_switches_near_cutoff,
            "r2_c_sample_identity_pass": identity_pass,
            "r2_identity_rows": len(identity_rows),
            "all_state_values_finite": all_finite,
            "physical_particle_migration_claimed": False,
        },
    )
    print(json.dumps({"edge_count_values": sorted(count_values), "switch_keys": len({int(row['edge_key']) for row in switch_rows}), "identity_pass": identity_pass}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
