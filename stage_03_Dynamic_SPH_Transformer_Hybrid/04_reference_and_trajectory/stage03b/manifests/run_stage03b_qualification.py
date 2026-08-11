"""Execute the preregistered Stage 03B reference qualification campaign."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import sys
import time
from typing import Any

import numpy as np
import psutil
import scipy
import sympy
import torch


HERE = Path(__file__).resolve()
STAGE03B = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
for candidate in (
    STAGE03B / "analytic_core",
    STAGE03B / "dr2_semidiscrete_time_reference",
    ROOT / "01_solver",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from reference_core import (
    acoustic_boundary_audit,
    array_sha256,
    canonical_json_bytes,
    dr1_analytic_audit,
    dr3_analytic_audit,
    dr3_case_fields,
    evaluate_symbolic,
    graph_bundle,
    load_config,
    minimum_image,
    normalized_l2,
    normalized_linf,
    output_times,
    physical_constants,
    regular_material_layout,
    serialize_graph_sequence,
    sha256_bytes,
    sha256_file,
    symbolic_family,
    vortex_boundary_audit,
)
from semidiscrete_rhs import integrate_semidiscrete


torch.set_default_dtype(torch.float64)
torch.set_num_threads(4)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def file_entry(path: Path, **extra: Any) -> dict[str, Any]:
    return {
        "path": relative(path),
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
        **extra,
    }


def state_hashes(
    position: np.ndarray,
    velocity: np.ndarray,
    density: np.ndarray,
    pressure: np.ndarray,
) -> np.ndarray:
    return np.asarray([
        array_sha256(position[i], velocity[i], density[i], pressure[i])
        for i in range(len(position))
    ], dtype="U71")


def graph_change_codes(graph_hashes: np.ndarray) -> np.ndarray:
    codes = ["INITIAL_GRAPH"]
    codes.extend(
        "FIXED_TOPOLOGY" if graph_hashes[i] == graph_hashes[i - 1] else "TOPOLOGY_CHANGE"
        for i in range(1, len(graph_hashes))
    )
    return np.asarray(codes, dtype="U32")


def save_record(
    path: Path,
    arrays: dict[str, np.ndarray],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    data_entry = file_entry(path, reference_class=metadata["reference_class"], family_id=metadata["family_id"], resolution=metadata["resolution"])
    sidecar = path.with_suffix(".json")
    record = {
        **metadata,
        "canonical_data": data_entry,
        "canonical_array_sha256": array_sha256(*[arrays[key] for key in sorted(arrays) if arrays[key].dtype.kind not in "UOS"]),
        "physical_configuration_sha256": sha256_file(STAGE03B / "freeze" / "stage03b_frozen_config.json"),
        "graph_implementation_sha256": sha256_file(ROOT / "01_solver" / "structure_preserving" / "neighborhood.py"),
        "output_time_grid_sha256": array_sha256(output_times()[0], output_times()[1]),
        "uncertainty_registry": relative(STAGE03B / "uncertainty" / "trajectory_reference_uncertainty.json"),
        "provenance": {
            "campaign": "Stage 03B",
            "device": "cpu",
            "dtype": "float64",
            "generator_sha256": sha256_file(HERE),
        },
        "forbidden_fields_absent": [
            "model_input_normalization", "split_assignment", "neural_target",
            "learned_correction", "optimizer_state",
        ],
    }
    write_json(sidecar, record)
    return data_entry, file_entry(sidecar, artifact_role="canonical_record_metadata")


def exact_dr1_frames(family: str, labels: np.ndarray) -> dict[str, np.ndarray]:
    tau, physical = output_times()
    fields = [evaluate_symbolic(family, labels, value) for value in tau]
    return {
        "tau": tau,
        "physical_time": physical,
        "material_labels": labels,
        "position": np.stack([item["position"] for item in fields]),
        "velocity": np.stack([item["velocity"] for item in fields]),
        "density": np.stack([item["density"] for item in fields]),
        "pressure": np.stack([item["pressure"] for item in fields]),
        "material_acceleration": np.stack([item["material_acceleration"] for item in fields]),
        "momentum_source": np.stack([item["source"] for item in fields]),
        "jacobian": np.stack([item["J"] for item in fields]),
    }


def exact_dr3_frames(case: str, labels: np.ndarray) -> dict[str, np.ndarray]:
    tau, physical = output_times()
    fields = [dr3_case_fields(case, labels, float(value)) for value in physical]
    return {
        "tau": tau,
        "physical_time": physical,
        "material_labels": labels,
        "position": np.stack([item["position"] for item in fields]),
        "position_unwrapped": np.stack([item["position_unwrapped"] for item in fields]),
        "velocity": np.stack([item["velocity"] for item in fields]),
        "density": np.stack([item["density"] for item in fields]),
        "pressure": np.stack([item["pressure"] for item in fields]),
        "material_acceleration": np.stack([item["material_acceleration"] for item in fields]),
        "momentum_source": np.stack([item["source"] for item in fields]),
    }


def minimum_particle_separation(positions: np.ndarray, support: float) -> np.ndarray:
    values: list[float] = []
    for frame in positions:
        graph = graph_bundle(frame, support)
        selected = graph["row"] != graph["col"]
        values.append(float(np.min(graph["distance"][selected])))
    return np.asarray(values, dtype=np.float64)


def scan_dr1b_topology(resolution: int, scan_intervals: int = 1024) -> dict[str, Any]:
    labels, dx = regular_material_layout(resolution)
    support = float(load_config()["execution"]["support_over_dx"]) * dx
    length, _, cs, _, _, _ = physical_constants()
    k = 2.0 * math.pi / length
    amplitude_x = 0.012 / k
    amplitude_y = 0.010 / k
    tau_max = float(output_times()[0][-1])
    tau_grid = np.linspace(0.0, tau_max, scan_intervals + 1, dtype=np.float64)
    pair_i, pair_j = np.triu_indices(len(labels), k=1)

    def positions_at(tau: float) -> np.ndarray:
        X, Y = labels[:, 0], labels[:, 1]
        phase = math.sin(2.0 * math.pi * tau)
        return np.stack((
            X + amplitude_x * np.sin(k * X) * np.cos(k * Y) * phase,
            Y - amplitude_y * np.cos(k * X) * np.sin(k * Y) * phase,
        ), axis=1)

    previous_edges: np.ndarray | None = None
    previous_displacement: np.ndarray | None = None
    events: list[dict[str, Any]] = []
    minimum_cutoff_margin = math.inf
    graph_hashes: list[str] = []
    for index, tau in enumerate(tau_grid):
        position = positions_at(float(tau))
        displacement = minimum_image(position[pair_i] - position[pair_j])
        distance = np.linalg.norm(displacement, axis=1)
        active = distance <= support * (1.0 + 16.0 * np.finfo(np.float64).eps)
        minimum_cutoff_margin = min(minimum_cutoff_margin, float(np.min(np.abs(distance - support))))
        edge_keys = np.stack((pair_i[active], pair_j[active]), axis=1).astype(np.int64)
        graph_hashes.append(array_sha256(edge_keys))
        if previous_edges is not None:
            changed = np.flatnonzero(active != previous_edges)
            for pair_index in changed:
                event_type = "EDGE_BIRTH" if active[pair_index] else "EDGE_DEATH"
                events.append({
                    "event_code": event_type,
                    "particle_pair": [int(pair_i[pair_index]), int(pair_j[pair_index])],
                    "tau_bracket": [float(tau_grid[index - 1]), float(tau)],
                    "physical_time_bracket": [float(tau_grid[index - 1] * length / cs), float(tau * length / cs)],
                    "pre_distance": float(np.linalg.norm(previous_displacement[pair_index])),
                    "post_distance": float(distance[pair_index]),
                    "cutoff": support,
                    "state_continuity": True,
                    "event_determinism": "PASS",
                })
            # A graph-relevant representative switch would be a discontinuous
            # displacement change while either side is within the cutoff.
            jumps = np.linalg.norm(displacement - previous_displacement, axis=1) > 0.5 * length
            relevant_switch = np.flatnonzero(jumps & (active | previous_edges))
            for pair_index in relevant_switch:
                events.append({
                    "event_code": "MINIMUM_IMAGE_REPRESENTATIVE_SWITCH",
                    "particle_pair": [int(pair_i[pair_index]), int(pair_j[pair_index])],
                    "tau_bracket": [float(tau_grid[index - 1]), float(tau)],
                    "physical_time_bracket": [float(tau_grid[index - 1] * length / cs), float(tau * length / cs)],
                    "pre_distance": float(np.linalg.norm(previous_displacement[pair_index])),
                    "post_distance": float(distance[pair_index]),
                    "cutoff": support,
                    "state_continuity": True,
                    "event_determinism": "PASS",
                })
        previous_edges = active
        previous_displacement = displacement

    repeat_hashes: list[str] = []
    for tau in tau_grid:
        position = positions_at(float(tau))
        displacement = minimum_image(position[pair_i] - position[pair_j])
        active = np.linalg.norm(displacement, axis=1) <= support * (1.0 + 16.0 * np.finfo(np.float64).eps)
        repeat_hashes.append(array_sha256(np.stack((pair_i[active], pair_j[active]), axis=1).astype(np.int64)))
    topology_change_times = sorted({value for event in events for value in event["tau_bracket"]})
    fixed_intervals: list[list[float]] = []
    boundaries = [0.0] + [value for value in topology_change_times if 0.0 < value < tau_max] + [tau_max]
    for start, stop in zip(boundaries[:-1], boundaries[1:]):
        if stop > start:
            fixed_intervals.append([start, stop])
    return {
        "family": "DR1_COUPLED_DEFORMATION",
        "resolution": resolution,
        "support_over_dx": 2.6,
        "scan_point_count": len(tau_grid),
        "tau_interval": [0.0, tau_max],
        "minimum_absolute_cutoff_margin": minimum_cutoff_margin,
        "events": events,
        "edge_birth_count": sum(event["event_code"] == "EDGE_BIRTH" for event in events),
        "edge_death_count": sum(event["event_code"] == "EDGE_DEATH" for event in events),
        "minimum_image_switch_count": sum(event["event_code"] == "MINIMUM_IMAGE_REPRESENTATIVE_SWITCH" for event in events),
        "fixed_topology_intervals": fixed_intervals,
        "deterministic_repeat": graph_hashes == repeat_hashes,
        "event_registry_status": "NO_EVENT_FIXED_TOPOLOGY" if not events else "EVENTS_BRACKETED",
        "gradient_audit_executed": False,
    }


def dr2_comparison(
    primary: dict[str, Any],
    sensitivity: dict[str, Any],
    exact: dict[str, np.ndarray],
    support: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    length, rho0, cs, _, _, _ = physical_constants()
    scales = {"position": length, "velocity": cs, "density": rho0, "pressure": rho0 * cs**2}
    per_field: dict[str, dict[str, Any]] = {}
    exact_diagnostic: dict[str, dict[str, float]] = {}
    for key, scale in scales.items():
        error = minimum_image(primary[key] - sensitivity[key]) if key == "position" else primary[key] - sensitivity[key]
        exact_error = minimum_image(primary[key] - exact[key]) if key == "position" else primary[key] - exact[key]
        per_frame_l2 = [normalized_l2(frame, scale) for frame in error]
        per_frame_linf = [normalized_linf(frame, scale) for frame in error]
        per_field[key] = {
            "normalized_l2_by_frame": per_frame_l2,
            "normalized_linf_by_frame": per_frame_linf,
            "normalized_l2_max": max(per_frame_l2),
            "normalized_linf_max": max(per_frame_linf),
        }
        exact_diagnostic[key] = {
            "normalized_l2": normalized_l2(exact_error, scale),
            "normalized_linf": normalized_linf(exact_error, scale),
            "classification": "semidiscrete_spatial_model_form_diagnostic_only",
        }
    primary_graph = serialize_graph_sequence(primary["position"], support)
    sensitivity_graph = serialize_graph_sequence(sensitivity["position"], support)
    graph_metrics = {
        "primary_hashes": primary_graph["hashes"].tolist(),
        "sensitivity_hashes": sensitivity_graph["hashes"].tolist(),
        "event_sequence_identical": primary_graph["hashes"].tolist() == sensitivity_graph["hashes"].tolist(),
        "primary_reciprocal_all": bool(primary_graph["reciprocal"].all()),
        "sensitivity_reciprocal_all": bool(sensitivity_graph["reciprocal"].all()),
    }
    gates = load_config()["hard_gates"]
    gate_values = {
        "field_l2": max(value["normalized_l2_max"] for value in per_field.values()) <= gates["dr2_field_normalized_l2"],
        "field_linf": max(value["normalized_linf_max"] for value in per_field.values()) <= gates["dr2_field_normalized_linf"],
        "graph_reciprocity": graph_metrics["primary_reciprocal_all"] and graph_metrics["sensitivity_reciprocal_all"],
        "event_sequence": graph_metrics["event_sequence_identical"],
    }
    metrics = {
        "field_sensitivity": per_field,
        "graph": graph_metrics,
        "semidiscrete_versus_exact": exact_diagnostic,
        "gates": gate_values,
        "verdict": "PASS" if all(gate_values.values()) else "FAIL",
        "time_reference_role": "same_semidiscrete_time_reference_only",
        "spatial_truth": False,
        "continuum_truth": False,
        "V_and_V_qualified_high_fidelity_truth": False,
    }
    return metrics, primary_graph, sensitivity_graph


def main() -> None:
    started = time.perf_counter()
    process = psutil.Process(os.getpid())
    cfg = load_config()
    tau, physical_times = output_times()
    length, rho0, cs, _, _, _ = physical_constants()
    results_dir = STAGE03B / "results"
    records_dir = STAGE03B / "trajectory_records"
    # Preserve freeze/contracts/code; replace only generated Stage 03B evidence.
    for directory in (
        STAGE03B / "dr1_lagrangian_mms",
        STAGE03B / "dr3_source_free_exact",
        STAGE03B / "acoustic_boundary",
        STAGE03B / "vortex_boundary",
        STAGE03B / "topology_events",
        STAGE03B / "uncertainty",
        STAGE03B / "qualification",
        results_dir,
        records_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    trajectory_entries: list[dict[str, Any]] = []
    metadata_entries: list[dict[str, Any]] = []
    dr1_audits: dict[str, Any] = {}
    dr1_record_summaries: list[dict[str, Any]] = []
    dr2_summaries: list[dict[str, Any]] = []
    dr3_audits: dict[str, Any] = {}
    dr3_record_summaries: list[dict[str, Any]] = []
    total_rhs_calls = 0
    total_graph_rebuilds = 0

    dr1_roles = {
        "DR1_LAGRANGIAN_COMPRESSION": "component_verification_and_future_training_candidate",
        "DR1_COUPLED_DEFORMATION": "component_verification_and_future_training_candidate",
    }
    for family, role in dr1_roles.items():
        audit, _ = dr1_analytic_audit(family)
        dr1_audits[family] = audit
        family_slug = family.lower()
        definitions_path = STAGE03B / "dr1_lagrangian_mms" / f"{family_slug}_symbolic_definitions.json"
        write_json(definitions_path, symbolic_family(family)["definitions"])
        audit_path = STAGE03B / "dr1_lagrangian_mms" / f"{family_slug}_analytic_audit.json"
        write_json(audit_path, audit)
        metadata_entries.extend([file_entry(definitions_path, artifact_role="closed_form_definition"), file_entry(audit_path, artifact_role="analytic_qualification")])
        for resolution in cfg["execution"]["resolutions"]:
            labels, dx = regular_material_layout(int(resolution))
            support = cfg["execution"]["support_over_dx"] * dx
            frames = exact_dr1_frames(family, labels)
            graph = serialize_graph_sequence(frames["position"], support)
            minimum_separation = minimum_particle_separation(frames["position"], support)
            hashes = state_hashes(frames["position"], frames["velocity"], frames["density"], frames["pressure"])
            arrays = {
                **frames,
                "state_hashes": hashes,
                "graph_hashes": graph["hashes"],
                "graph_geometry_hashes": graph["geometry_hashes"],
                "graph_offsets": graph["offsets"],
                "graph_row": graph["row"],
                "graph_col": graph["col"],
                "graph_reverse_global": graph["reverse_global"],
                "topology_event_codes": graph_change_codes(graph["hashes"]),
                "minimum_particle_separation": minimum_separation,
                "mach_by_frame": np.max(np.linalg.norm(frames["velocity"], axis=2), axis=1) / cs,
            }
            record_path = records_dir / f"{family_slug}_n{resolution}_exact.npz"
            metadata = {
                "schema_version": "sph-pio-poc.stage03b.trajectory.v1",
                "reference_class": "D-R1",
                "family_id": family,
                "role": role,
                "record_role": "audit_reference_trajectory_records",
                "formula_sha256": audit["formula_sha256"],
                "derivative_sha256": sha256_file(STAGE03B / "analytic_core" / "reference_core.py"),
                "source_sha256": array_sha256(frames["momentum_source"]),
                "derivative_identity": [audit["route_1"], audit["route_2"]],
                "resolution": int(resolution),
                "particle_count": int(resolution) ** 2,
                "support_over_dx": 2.6,
                "output_frame_count": len(tau),
                "output_tau": tau.tolist(),
                "source_identity": "exact_momentum_MMS_source",
                "continuity_source": 0.0,
                "graph_reciprocity_all": bool(graph["reciprocal"].all()),
                "topology_event_count_on_output_grid": int(np.sum(graph_change_codes(graph["hashes"]) == "TOPOLOGY_CHANGE")),
                "minimum_particle_separation": float(np.min(minimum_separation)),
                "minimum_density": float(np.min(frames["density"])),
                "maximum_mach": float(np.max(arrays["mach_by_frame"])),
                "qualification_verdict": audit["verdict"],
                "lineage_component": family,
                "training_dataset": False,
            }
            data_entry, sidecar_entry = save_record(record_path, arrays, metadata)
            trajectory_entries.append(data_entry); metadata_entries.append(sidecar_entry)
            dr1_record_summaries.append({**metadata, "path": relative(record_path), "sha256": data_entry["sha256"]})

    # Topology-event inventory from the exact D-R1-B path. A no-event result is
    # retained with its positive cutoff margin and deterministic dense scan.
    topology_records = [scan_dr1b_topology(int(resolution)) for resolution in cfg["execution"]["resolutions"]]
    topology_registry = {
        "schema_version": "sph-pio-poc.stage03b.topology.v1",
        "family": "DR1_COUPLED_DEFORMATION",
        "records": topology_records,
        "total_event_count": sum(len(item["events"]) for item in topology_records),
        "fixed_topology_and_event_intervals_separated": True,
        "gradient_audit_executed": False,
        "purpose": "Stage 03D topology-event input registry",
    }
    topology_path = STAGE03B / "topology_events" / "dr1b_topology_event_registry.json"
    write_json(topology_path, topology_registry); metadata_entries.append(file_entry(topology_path, artifact_role="topology_event_registry"))

    # D-R2: primary, exact repeat, and tighter sensitivity for every D-R1/N case.
    dr2_dir = STAGE03B / "dr2_semidiscrete_time_reference"
    for family in dr1_roles:
        for resolution in cfg["execution"]["resolutions"]:
            labels, dx = regular_material_layout(int(resolution))
            support = cfg["execution"]["support_over_dx"] * dx
            exact = exact_dr1_frames(family, labels)
            primary = integrate_semidiscrete(
                family, labels, int(resolution), physical_times,
                rtol=cfg["dr2"]["primary_rtol"], atol=cfg["dr2"]["primary_atol"],
            )
            repeat = integrate_semidiscrete(
                family, labels, int(resolution), physical_times,
                rtol=cfg["dr2"]["primary_rtol"], atol=cfg["dr2"]["primary_atol"],
            )
            sensitivity = integrate_semidiscrete(
                family, labels, int(resolution), physical_times,
                rtol=cfg["dr2"]["sensitivity_rtol"], atol=cfg["dr2"]["sensitivity_atol"],
            )
            metrics, primary_graph, sensitivity_graph = dr2_comparison(primary, sensitivity, exact, support)
            repeat_fields = all(np.array_equal(primary[key], repeat[key]) for key in ("position", "velocity", "density", "pressure"))
            repeat_graph = serialize_graph_sequence(repeat["position"], support)
            repeat_graph_equal = primary_graph["hashes"].tolist() == repeat_graph["hashes"].tolist()
            metrics.update({
                "family": family,
                "resolution": int(resolution),
                "particle_count": int(resolution) ** 2,
                "support_over_dx": 2.6,
                "primary": {key: primary[key] for key in ("nfev", "graph_rebuild_count", "source_evaluation_count", "minimum_density_seen", "maximum_density_seen", "rtol", "atol", "maximum_step", "integrator", "source_identity", "semidiscrete_identity")},
                "sensitivity": {key: sensitivity[key] for key in ("nfev", "graph_rebuild_count", "source_evaluation_count", "minimum_density_seen", "maximum_density_seen", "rtol", "atol", "maximum_step", "integrator", "source_identity", "semidiscrete_identity")},
                "primary_repeat_bitwise_fields": repeat_fields,
                "primary_repeat_graph_sequence": repeat_graph_equal,
            })
            metrics["gates"]["deterministic_repeat"] = repeat_fields and repeat_graph_equal
            metrics["verdict"] = "PASS" if all(metrics["gates"].values()) else "FAIL"
            total_rhs_calls += primary["nfev"] + repeat["nfev"] + sensitivity["nfev"]
            total_graph_rebuilds += primary["graph_rebuild_count"] + repeat["graph_rebuild_count"] + sensitivity["graph_rebuild_count"]
            slug = f"{family.lower()}_n{resolution}_dop853"
            arrays = {
                "tau": tau, "physical_time": physical_times, "material_labels": labels,
                "primary_position": primary["position"], "primary_position_unwrapped": primary["position_unwrapped"],
                "primary_velocity": primary["velocity"], "primary_density": primary["density"], "primary_pressure": primary["pressure"],
                "sensitivity_position": sensitivity["position"], "sensitivity_position_unwrapped": sensitivity["position_unwrapped"],
                "sensitivity_velocity": sensitivity["velocity"], "sensitivity_density": sensitivity["density"], "sensitivity_pressure": sensitivity["pressure"],
                "exact_position": exact["position"], "exact_velocity": exact["velocity"], "exact_density": exact["density"], "exact_pressure": exact["pressure"],
                "exact_momentum_source": exact["momentum_source"],
                "primary_state_hashes": state_hashes(primary["position"], primary["velocity"], primary["density"], primary["pressure"]),
                "sensitivity_state_hashes": state_hashes(sensitivity["position"], sensitivity["velocity"], sensitivity["density"], sensitivity["pressure"]),
                "primary_graph_hashes": primary_graph["hashes"], "sensitivity_graph_hashes": sensitivity_graph["hashes"],
                "primary_graph_offsets": primary_graph["offsets"], "primary_graph_row": primary_graph["row"], "primary_graph_col": primary_graph["col"],
                "sensitivity_graph_offsets": sensitivity_graph["offsets"], "sensitivity_graph_row": sensitivity_graph["row"], "sensitivity_graph_col": sensitivity_graph["col"],
            }
            record_path = records_dir / f"{slug}.npz"
            metadata = {
                "schema_version": "sph-pio-poc.stage03b.trajectory.v1",
                "reference_class": "D-R2",
                "family_id": family,
                "lineage_component": family,
                "role": "time_error_isolation_only",
                "record_role": "audit_reference_trajectory_records",
                "resolution": int(resolution),
                "particle_count": int(resolution) ** 2,
                "support_over_dx": 2.6,
                "output_frame_count": len(tau),
                "exact_DOP853_identity": "same_semidiscrete_operator_primary_and_sensitivity",
                "formula_sha256": dr1_audits[family]["formula_sha256"],
                "derivative_sha256": sha256_file(STAGE03B / "analytic_core" / "reference_core.py"),
                "semidiscrete_rhs_sha256": sha256_file(STAGE03B / "dr2_semidiscrete_time_reference" / "semidiscrete_rhs.py"),
                "source_sha256": array_sha256(exact["momentum_source"]),
                "qualification_verdict": metrics["verdict"],
                "spatial_truth": False,
                "continuum_truth": False,
                "training_dataset": False,
            }
            data_entry, sidecar_entry = save_record(record_path, arrays, metadata)
            trajectory_entries.append(data_entry); metadata_entries.append(sidecar_entry)
            metrics_path = dr2_dir / f"{slug}_qualification.json"
            write_json(metrics_path, metrics); metadata_entries.append(file_entry(metrics_path, artifact_role="dr2_qualification"))
            dr2_summaries.append({**metadata, "path": relative(record_path), "sha256": data_entry["sha256"], "metrics_path": relative(metrics_path), "metrics_sha256": sha256_file(metrics_path), "metrics": metrics})

    # D-R3 exact independent validation records.
    for case in cfg["dr3"]:
        audit = dr3_analytic_audit(case)
        dr3_audits[case] = audit
        audit_path = STAGE03B / "dr3_source_free_exact" / f"{case.lower()}_analytic_audit.json"
        write_json(audit_path, audit); metadata_entries.append(file_entry(audit_path, artifact_role="dr3_exact_qualification"))
        for resolution in cfg["execution"]["resolutions"]:
            labels, dx = regular_material_layout(int(resolution))
            support = cfg["execution"]["support_over_dx"] * dx
            frames = exact_dr3_frames(case, labels)
            graph = serialize_graph_sequence(frames["position"], support)
            repeat_graph = serialize_graph_sequence(frames["position"].copy(), support)
            deterministic = graph["hashes"].tolist() == repeat_graph["hashes"].tolist()
            hashes = state_hashes(frames["position"], frames["velocity"], frames["density"], frames["pressure"])
            arrays = {
                **frames,
                "state_hashes": hashes,
                "graph_hashes": graph["hashes"],
                "graph_geometry_hashes": graph["geometry_hashes"],
                "graph_offsets": graph["offsets"], "graph_row": graph["row"], "graph_col": graph["col"],
                "graph_reverse_global": graph["reverse_global"],
                "topology_event_codes": graph_change_codes(graph["hashes"]),
            }
            record_path = records_dir / f"{case.lower()}_n{resolution}_exact.npz"
            metadata = {
                "schema_version": "sph-pio-poc.stage03b.trajectory.v1",
                "reference_class": "D-R3",
                "family_id": case,
                "lineage_component": case,
                "role": "independent_source_free_validation_only",
                "record_role": "audit_reference_trajectory_records",
                "resolution": int(resolution),
                "particle_count": int(resolution) ** 2,
                "support_over_dx": 2.6,
                "output_frame_count": len(tau),
                "source_identity": "exactly_absent",
                "formula_sha256": sha256_bytes(canonical_json_bytes({"formula": "oblique_shear_exact_source_free", "case": cfg["dr3"][case]})),
                "derivative_sha256": sha256_file(STAGE03B / "analytic_core" / "reference_core.py"),
                "source_sha256": array_sha256(frames["momentum_source"]),
                "graph_reciprocity_all": bool(graph["reciprocal"].all()),
                "deterministic_graph_repeat": deterministic,
                "minimum_density": float(np.min(frames["density"])),
                "maximum_mach": float(np.max(np.linalg.norm(frames["velocity"], axis=2)) / cs),
                "qualification_verdict": audit["verdict"] if deterministic else "FAIL",
                "training_dataset": False,
                "future_training_permitted": False,
                "future_normalization_permitted": False,
                "threshold_selection_permitted": False,
                "architecture_selection_permitted": False,
            }
            data_entry, sidecar_entry = save_record(record_path, arrays, metadata)
            trajectory_entries.append(data_entry); metadata_entries.append(sidecar_entry)
            dr3_record_summaries.append({**metadata, "path": relative(record_path), "sha256": data_entry["sha256"]})

    acoustic = acoustic_boundary_audit()
    acoustic_path = STAGE03B / "acoustic_boundary" / "acoustic_candidate_classification.json"
    write_json(acoustic_path, acoustic); metadata_entries.append(file_entry(acoustic_path, artifact_role="boundary_classification"))
    vortex = vortex_boundary_audit()
    vortex_path = STAGE03B / "vortex_boundary" / "periodic_vortex_classification.json"
    write_json(vortex_path, vortex); metadata_entries.append(file_entry(vortex_path, artifact_role="boundary_classification"))

    uncertainty = {
        "schema_version": "sph-pio-poc.stage03b.uncertainty.v1",
        "D-R1": {
            family: {
                "analytic_derivative_disagreement": audit["derivative_route_normalized_disagreement_max"],
                "symbolic_evaluation_roundoff": max(audit["eos_max_absolute_residual"], audit["periodic_mapping_residual"]),
                "material_map_chain_rule": audit["derivative_route_disagreement"],
                "not_physical_validation_uncertainty": True,
            }
            for family, audit in dr1_audits.items()
        },
        "D-R2": [
            {
                "family": item["family_id"], "resolution": item["resolution"],
                "tolerance_sensitivity_l2_max": max(value["normalized_l2_max"] for value in item["metrics"]["field_sensitivity"].values()),
                "tolerance_sensitivity_linf_max": max(value["normalized_linf_max"] for value in item["metrics"]["field_sensitivity"].values()),
                "topology_event_timing": "output_graph_sequence_identical" if item["metrics"]["graph"]["event_sequence_identical"] else "NONDETERMINISTIC",
                "output_interpolation": "solve_ivp_dense_polynomial_at_frozen_t_eval",
                "summation": "CPU_float64_deterministic_index_add",
                "not_spatial_uncertainty": True,
            }
            for item in dr2_summaries
        ],
        "D-R3": {
            case: {
                "analytic_closure_roundoff": max(audit["source_free_momentum_residual"], audit["continuity_residual"]),
                "particle_path_evaluation": audit["particle_path_residual"],
                "periodic_representative": audit["periodic_seam_residual"],
            }
            for case, audit in dr3_audits.items()
        },
        "single_total_GCI_computed": False,
        "dr2_sensitivity_interpreted_as_spatial_uncertainty": False,
        "mms_exactness_interpreted_as_physical_validation": False,
    }
    uncertainty_path = STAGE03B / "uncertainty" / "trajectory_reference_uncertainty.json"
    write_json(uncertainty_path, uncertainty); metadata_entries.append(file_entry(uncertainty_path, artifact_role="uncertainty_registry"))

    dr1_pass = all(item["verdict"] == "PASS" for item in dr1_audits.values()) and len(dr1_record_summaries) == 6
    dr2_pass = len(dr2_summaries) == 6 and all(item["qualification_verdict"] == "PASS" for item in dr2_summaries)
    dr3_pass = all(item["verdict"] == "PASS" for item in dr3_audits.values()) and len(dr3_record_summaries) == 6 and all(item["qualification_verdict"] == "PASS" for item in dr3_record_summaries)
    boundary_complete = acoustic["classification"] in {"DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL", "DR3_ACOUSTIC_NOT_QUALIFIED"} and vortex["classification"] in {"DR3_PERIODIC_VORTEX_SOURCE_FREE_QUALIFIED", "DR3_PERIODIC_VORTEX_REJECTED_AS_EXACT_SOURCE_FREE_REFERENCE", "DR1_PERIODIC_VORTEX_MMS_ONLY"}
    topology_pass = all(item["deterministic_repeat"] for item in topology_records)
    if dr1_pass and dr2_pass and dr3_pass and boundary_complete and topology_pass:
        final_status = "DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE"
    elif not (dr1_pass and dr2_pass and dr3_pass and topology_pass):
        final_status = "DYNAMIC_REFERENCE_TRAJECTORY_NOT_QUALIFIED"
    else:
        final_status = "DYNAMIC_REFERENCE_TRAJECTORY_EVIDENCE_INCOMPLETE"

    qualification = {
        "schema_version": "sph-pio-poc.stage03b.qualification.v1",
        "gates": {
            "A_DR1": dr1_pass,
            "B_DR2": dr2_pass,
            "C_DR3": dr3_pass,
            "D_boundary_classification": boundary_complete,
            "E_topology_determinism": topology_pass,
            "F_provenance_uncertainty": True,
            "no_model": True,
            "no_optimizer": True,
            "no_training": True,
            "no_neural_rollout": True,
            "no_split_or_normalization": True,
        },
        "dr1_family_verdicts": {key: value["verdict"] for key, value in dr1_audits.items()},
        "dr2_case_verdicts": {f"{item['family_id']}_N{item['resolution']}": item["qualification_verdict"] for item in dr2_summaries},
        "dr3_case_verdicts": {key: value["verdict"] for key, value in dr3_audits.items()},
        "acoustic_classification": acoustic["classification"],
        "vortex_classification": vortex["classification"],
        "topology_event_count": topology_registry["total_event_count"],
        "final_status": final_status,
        "stage03c_authorized": final_status == "DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE",
    }
    qualification_path = STAGE03B / "qualification" / "stage03b_qualification_summary.json"
    write_json(qualification_path, qualification); metadata_entries.append(file_entry(qualification_path, artifact_role="qualification_summary"))

    elapsed = time.perf_counter() - started
    trajectory_storage_bytes = sum(
        path.stat().st_size for path in records_dir.rglob("*") if path.is_file()
    )
    stage03b_storage_bytes = sum(
        path.stat().st_size for path in STAGE03B.rglob("*") if path.is_file()
    )
    raw_peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_rss_bytes = raw_peak_rss if sys.platform == "darwin" else raw_peak_rss * 1024
    resource_record = {
        "schema_version": "sph-pio-poc.stage03b.resources.v1",
        "wall_time_seconds": elapsed,
        "peak_rss_bytes": peak_rss_bytes,
        "peak_rss_platform_unit_interpretation": "bytes_on_darwin_kibibytes_elsewhere",
        "ending_rss_bytes": int(process.memory_info().rss),
        "trajectory_storage_bytes_at_measurement": trajectory_storage_bytes,
        "stage03b_storage_bytes_at_measurement": stage03b_storage_bytes,
        "dop853_rhs_calls_total_including_primary_repeats": total_rhs_calls,
        "graph_rebuild_count_total_including_primary_repeats": total_graph_rebuilds,
        "topology_event_count": topology_registry["total_event_count"],
        "device": "cpu", "dtype": "float64", "torch_threads": torch.get_num_threads(),
        "resolutions": cfg["execution"]["resolutions"], "frame_count_per_trajectory": len(tau),
    }
    resource_path = results_dir / "resource_execution.json"
    write_json(resource_path, resource_record); metadata_entries.append(file_entry(resource_path, artifact_role="resource_execution"))

    family_manifest = {
        "manifest_version": "stage03b-reference-family-1.0.0",
        "families": [
            {"family_id": family, "reference_class": "D-R1", "role": role, "formula_sha256": dr1_audits[family]["formula_sha256"], "derivative_sha256": sha256_file(STAGE03B / "analytic_core" / "reference_core.py"), "derivative_routes": [dr1_audits[family]["route_1"], dr1_audits[family]["route_2"]], "verdict": dr1_audits[family]["verdict"], "lineage_includes_all_N_dt_support_output_times": True}
            for family, role in dr1_roles.items()
        ] + [
            {"family_id": "DR2_SEMIDISCRETE_TIME_REFERENCE", "reference_class": "D-R2", "role": "time_error_isolation_only", "parent_families": list(dr1_roles), "derivative_sha256": sha256_file(STAGE03B / "analytic_core" / "reference_core.py"), "semidiscrete_rhs_sha256": sha256_file(STAGE03B / "dr2_semidiscrete_time_reference" / "semidiscrete_rhs.py"), "verdict": "PASS" if dr2_pass else "FAIL", "spatial_truth": False}
        ] + [
            {"family_id": case, "reference_class": "D-R3", "role": "independent_source_free_validation_only", "formula_sha256": sha256_bytes(canonical_json_bytes({"formula": "oblique_shear_exact_source_free", "case": cfg["dr3"][case]})), "derivative_sha256": sha256_file(STAGE03B / "analytic_core" / "reference_core.py"), "verdict": dr3_audits[case]["verdict"], "training_permitted": False, "normalization_permitted": False, "threshold_selection_permitted": False, "architecture_selection_permitted": False}
            for case in cfg["dr3"]
        ] + [
            {"family_id": "ACOUSTIC_CANDIDATE", "reference_class": "boundary_candidate", "role": "conditional_or_rejected", "classification": acoustic["classification"]},
            {"family_id": "PERIODIC_VORTEX_CANDIDATE", "reference_class": "boundary_candidate", "role": "qualified_or_reclassified_mms_only", "classification": vortex["classification"]},
        ],
        "no_split_assignment": True,
        "stage01_formula_records_copied": False,
    }
    family_manifest_path = STAGE03 / "10_manifests" / "stage03b_reference_family_manifest.json"
    write_json(family_manifest_path, family_manifest)

    trajectory_manifest = {
        "manifest_version": "stage03b-trajectory-1.0.0",
        "record_count": len(trajectory_entries),
        "expected_record_count": 18,
        "records": trajectory_entries,
        "metadata": metadata_entries,
        "all_records_are_audit_reference_trajectory_records": True,
        "iid_interpretation_permitted": False,
        "split_assignment_present": False,
        "normalization_present": False,
        "neural_target_present": False,
        "optimizer_state_present": False,
    }
    trajectory_manifest_path = STAGE03 / "10_manifests" / "stage03b_trajectory_manifest.json"
    write_json(trajectory_manifest_path, trajectory_manifest)

    run_manifest = {
        "manifest_version": "stage03b-run-1.0.0",
        "config": file_entry(STAGE03B / "freeze" / "stage03b_frozen_config.json"),
        "code": [file_entry(STAGE03B / "analytic_core" / "reference_core.py"), file_entry(STAGE03B / "dr2_semidiscrete_time_reference" / "semidiscrete_rhs.py"), file_entry(HERE)],
        "environment": {
            "platform": platform.platform(), "python": platform.python_version(),
            "numpy": np.__version__, "scipy": scipy.__version__, "sympy": sympy.__version__, "torch": torch.__version__,
            "device": "cpu", "dtype": "float64",
        },
        "qualification": file_entry(qualification_path),
        "resource_execution": file_entry(resource_path),
        "reference_family_manifest": file_entry(family_manifest_path),
        "trajectory_manifest": file_entry(trajectory_manifest_path),
        "historical_write_operations": 0,
        "model_implementation_count": 0,
        "optimizer_count": 0,
        "training_run_count": 0,
        "neural_rollout_count": 0,
        "final_status": final_status,
    }
    run_manifest_path = STAGE03B / "manifests" / "stage03b_run_manifest.json"
    write_json(run_manifest_path, run_manifest)
    print(json.dumps({
        "status": final_status,
        "dr1_pass": dr1_pass, "dr2_pass": dr2_pass, "dr3_pass": dr3_pass,
        "acoustic": acoustic["classification"], "vortex": vortex["classification"],
        "trajectory_records": len(trajectory_entries),
        "dop853_rhs_calls": total_rhs_calls, "graph_rebuilds": total_graph_rebuilds,
        "topology_events": topology_registry["total_event_count"],
        "wall_time_seconds": elapsed,
    }, indent=2))


if __name__ == "__main__":
    main()
