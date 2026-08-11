#!/usr/bin/env python3
"""Audit Stage 02I target conservation without modifying any target."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import lsqr, spsolve


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
ATTR_ROOT = STAGE_ROOT / "04_target_attribution"
CROOT = ATTR_ROOT / "conservation_closure"
QROOT = ATTR_ROOT / "qualified_spatial_targets"
GENERATOR_PATH = STAGE_ROOT / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F_SCRIPT_PATH = ATTR_ROOT / "semidiscrete_reference/construct_spatial_targets.py"
CONFIG_PATH = STAGE_ROOT / "03_dataset/generation/generation_configuration.yaml"
MATRIX_PATH = QROOT / "case_matrix/preregistered_stage02i_case_matrix.yaml"
TARGET_PATH = QROOT / "targets/spatial_target_candidates.json"
FREEZE_PATH = CROOT / "freeze/stage02ir_input_freeze_manifest.json"
SCOPE_PATH = CROOT / "freeze/stage02ir_scope_and_decision_rules.yaml"
H_RULES_PATH = ATTR_ROOT / "acceptance/reference_acceptance_rules.yaml"

FORCE_PATH = CROOT / "force_decomposition/force_decomposition.json"
SPH_PAIR_PATH = CROOT / "force_decomposition/sph_pairwise_cancellation_audit.json"
CONTINUUM_PATH = CROOT / "continuum_balance/continuum_momentum_balance.json"
QUADRATURE_PATH = CROOT / "particle_quadrature/particle_quadrature_audit.json"
REFERENCE_PAIR_PATH = CROOT / "particle_quadrature/reference_pair_conservation_comparison.json"
REPRESENTABILITY_PATH = CROOT / "pair_representability/pair_representability_audit.json"
JITTER_DECOMPOSITION_PATH = CROOT / "pair_representability/jitter_pair_node_decomposition.json"
ARCHITECTURE_PATH = CROOT / "architecture_scope/architecture_scope_decision.json"
QUALIFICATION_PATH = CROOT / "qualification/stage02ir_qualification.json"
MANIFEST_PATH = CROOT / "manifests/stage02ir_run_manifest.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def load_module(name: str, path: Path) -> Any:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json_no_overwrite(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def verify_freeze(freeze: dict[str, Any], targets: dict[str, Any]) -> None:
    for relative, expected in freeze["frozen_files"].items():
        if file_hash(REPO_ROOT / relative) != expected:
            raise RuntimeError(f"Frozen file changed: {relative}")
    current = {row["candidate_id"]: content_hash(row) for row in targets["candidates"]}
    if current != freeze["seven_target_record_hashes"]:
        raise RuntimeError("A frozen Stage 02I target record changed")


def runtime_case(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        **raw,
        "topology_control": "none",
        "time_horizon": 0.0,
        "trajectory_family": "stage02ir_same_timestamp_no_trajectory",
        "initial_condition_family": "analytic_periodic_vortex",
        "disorder_family": raw["disorder_identity"],
    }


def kahan_sum(values: np.ndarray) -> np.ndarray:
    total = np.zeros(values.shape[1], dtype=np.float64)
    compensation = np.zeros_like(total)
    for value in values:
        corrected = value - compensation
        updated = total + corrected
        compensation = (updated - total) - corrected
        total = updated
    return total


def ordered_sum(values: np.ndarray, reverse: bool = False) -> np.ndarray:
    total = np.zeros(values.shape[1], dtype=np.float64)
    iterable = values[::-1] if reverse else values
    for value in iterable:
        total = total + value
    return total


def summation_audit(values: np.ndarray) -> dict[str, Any]:
    forward = ordered_sum(values)
    reverse = ordered_sum(values, reverse=True)
    compensated = kahan_sum(values)
    sensitivity = max(
        float(np.linalg.norm(forward - reverse)),
        float(np.linalg.norm(forward - compensated)),
        float(np.linalg.norm(reverse - compensated)),
    )
    return {
        "forward": forward.tolist(),
        "reverse": reverse.tolist(),
        "Kahan_compensated": compensated.tolist(),
        "maximum_order_sensitivity_norm": sensitivity,
        "deterministic_repeat_Kahan_equal": bool(np.array_equal(compensated, kahan_sum(values.copy()))),
    }


def analytic_reference_components(state: dict[str, np.ndarray], config: dict[str, Any]) -> dict[str, np.ndarray]:
    length = float(config["domain"]["box_length"])
    wave_number = 2.0 * math.pi / length
    phase_x = wave_number * state["x"][:, 0]
    phase_y = wave_number * state["x"][:, 1]
    rho0 = float(config["physics"]["rho0"])
    c0 = float(config["physics"]["sound_speed"])
    density_amplitude = float(config["physics"]["density_amplitude"])
    nu = float(config["physics"]["kinematic_viscosity"])
    pressure_factor = c0 * c0 * rho0 * density_amplitude * wave_number
    gradient_pressure = pressure_factor * np.column_stack(
        (np.cos(phase_x) * np.sin(phase_y), np.sin(phase_x) * np.cos(phase_y))
    )
    laplacian_velocity = -2.0 * wave_number * wave_number * state["v"]
    pressure = -gradient_pressure / state["rho"][:, None]
    viscosity = nu * laplacian_velocity
    return {"pressure": pressure, "viscosity": viscosity, "total": pressure + viscosity}


def fourier_reference_components(state: dict[str, np.ndarray], config: dict[str, Any]) -> dict[str, np.ndarray]:
    length = float(config["domain"]["box_length"])
    modes = np.asarray([(kx, ky) for kx in range(-2, 3) for ky in range(-2, 3)], dtype=np.float64)
    phase = (2.0j * math.pi / length) * (
        state["x"][:, 0, None] * modes[None, :, 0]
        + state["x"][:, 1, None] * modes[None, :, 1]
    )
    matrix = np.exp(phase)
    pressure_value = float(config["physics"]["sound_speed"]) ** 2 * (
        state["rho"] - float(config["physics"]["rho0"])
    )
    coefficients = [np.linalg.lstsq(matrix, field, rcond=None)[0] for field in (pressure_value, state["v"][:, 0], state["v"][:, 1])]
    kx = (2.0 * math.pi / length) * modes[:, 0]
    ky = (2.0 * math.pi / length) * modes[:, 1]
    gradient_pressure = np.column_stack(
        ((matrix @ (1.0j * kx * coefficients[0])).real, (matrix @ (1.0j * ky * coefficients[0])).real)
    )
    laplacian_factor = -(kx * kx + ky * ky)
    laplacian_velocity = np.column_stack(
        (
            (matrix @ (laplacian_factor * coefficients[1])).real,
            (matrix @ (laplacian_factor * coefficients[2])).real,
        )
    )
    pressure = -gradient_pressure / state["rho"][:, None]
    viscosity = float(config["physics"]["kinematic_viscosity"]) * laplacian_velocity
    return {"pressure": pressure, "viscosity": viscosity, "total": pressure + viscosity}


def normalized_force(force: np.ndarray, nodal_force: np.ndarray) -> float:
    denominator = float(np.sum(np.linalg.norm(nodal_force, axis=1)))
    return float(np.linalg.norm(force) / denominator) if denominator > 0.0 else 0.0


def force_decomposition(
    matrix: dict[str, Any], targets: dict[str, dict[str, Any]], generator: Any, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    rows = []
    component_cache: dict[str, dict[str, np.ndarray]] = {}
    for raw in matrix["cases"]:
        case = runtime_case(raw)
        state = generator.initial_state(case, config)
        sph, _ = generator.sparse_rhs_components(state, case, config, apply_control=False)
        fourier = fourier_reference_components(state, config)
        analytic = analytic_reference_components(state, config)
        mass = float(config["physics"]["rho0"]) / state["x"].shape[0]
        target_record = targets[raw["case_id"]]
        if not np.array_equal(
            fourier["total"] - sph["total"], np.asarray(target_record["delta_a_primary"], dtype=np.float64)
        ):
            raise RuntimeError(f"Controlled recomputation changed target {raw['case_id']}")
        cache: dict[str, np.ndarray] = {}
        component_rows = {}
        for component in ("pressure", "viscosity", "total"):
            a_ref = fourier[component]
            a_ref_analytic = analytic[component]
            a_sph = sph[component]
            delta = a_ref - a_sph
            ref_force_values = mass * a_ref
            analytic_force_values = mass * a_ref_analytic
            sph_force_values = mass * a_sph
            target_force_values = mass * delta
            ref_sum = summation_audit(ref_force_values)
            analytic_sum = summation_audit(analytic_force_values)
            sph_sum = summation_audit(sph_force_values)
            target_sum = summation_audit(target_force_values)
            closure = np.asarray(target_sum["Kahan_compensated"]) - (
                np.asarray(ref_sum["Kahan_compensated"]) - np.asarray(sph_sum["Kahan_compensated"])
            )
            component_rows[component] = {
                "F_ref_Fourier": ref_sum,
                "F_ref_analytic": analytic_sum,
                "F_sph": sph_sum,
                "F_target": target_sum,
                "F_target_absolute_norm": float(np.linalg.norm(target_sum["Kahan_compensated"])),
                "F_target_normalized_residual": normalized_force(
                    np.asarray(target_sum["Kahan_compensated"]), target_force_values
                ),
                "F_target_equals_F_ref_minus_F_sph_closure_norm": float(np.linalg.norm(closure)),
                "Fourier_analytic_force_difference_norm": float(
                    np.linalg.norm(
                        np.asarray(ref_sum["Kahan_compensated"])
                        - np.asarray(analytic_sum["Kahan_compensated"])
                    )
                ),
            }
            cache[f"fourier_{component}"] = a_ref
            cache[f"analytic_{component}"] = a_ref_analytic
            cache[f"sph_{component}"] = a_sph
            cache[f"target_{component}"] = delta
        component_cache[raw["case_id"]] = cache
        rows.append(
            {
                "candidate_id": raw["case_id"],
                "disorder_identity": raw["disorder_identity"],
                "mass_per_particle": mass,
                "components": component_rows,
                "deterministic_controlled_recomputation": "PASS",
            }
        )
    return {
        "force_identity": "F_target = F_ref - F_sph",
        "summation_methods": ["forward_float64", "reverse_float64", "Kahan_compensated_float64"],
        "rows": rows,
        "all_force_identity_checks_pass": all(
            max(row["components"][name]["F_target_equals_F_ref_minus_F_sph_closure_norm"] for name in ("pressure", "viscosity", "total"))
            <= 1.0e-15
            for row in rows
        ),
    }, component_cache


def directed_pair_contributions(
    generator: Any,
    state: dict[str, np.ndarray],
    raw_case: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    case = runtime_case(raw_case)
    edges = generator.build_edges(state, case, config, apply_control=False)
    n = state["x"].shape[0]
    mass = float(config["physics"]["rho0"]) / n
    rho = state["rho"]
    velocity = state["v"]
    pressure = generator.pressure_from_density(rho, config)
    dx = float(config["domain"]["box_length"]) / int(raw_case["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    nu = float(config["physics"]["kinematic_viscosity"])
    pressure_force = np.zeros((edges["source"].size, 2), dtype=np.float64)
    viscosity_force = np.zeros_like(pressure_force)
    for k, (i_raw, j_raw, displacement) in enumerate(
        zip(edges["source"], edges["target"], edges["displacement"])
    ):
        i = int(i_raw)
        j = int(j_raw)
        distance = float(np.linalg.norm(displacement))
        _, d_w_dr = generator.kernel_values(np.asarray([distance]), h)
        grad_i = (-float(d_w_dr[0]) / distance) * displacement
        acceleration_pressure = -mass * (pressure[i] / rho[i] ** 2 + pressure[j] / rho[j] ** 2) * grad_i
        gamma = 2.0 * float(np.dot(displacement, grad_i)) / (distance * distance + 0.01 * h * h)
        acceleration_viscosity = mass * nu * gamma * (velocity[j] - velocity[i]) / (rho[i] * rho[j])
        pressure_force[k] = mass * acceleration_pressure
        viscosity_force[k] = mass * acceleration_viscosity
    return edges, {
        "pressure": pressure_force,
        "viscosity": viscosity_force,
        "total": pressure_force + viscosity_force,
    }


def sph_pairwise_audit(
    matrix: dict[str, Any], generator: Any, config: dict[str, Any], tolerance: float
) -> dict[str, Any]:
    rows = []
    jitter_failure = False
    for raw in matrix["cases"]:
        state = generator.initial_state(runtime_case(raw), config)
        sph, _ = generator.sparse_rhs_components(state, runtime_case(raw), config, apply_control=False)
        edges, directed = directed_pair_contributions(generator, state, raw, config)
        topology = generator.topology_audit(edges, state, runtime_case(raw), config)
        reverse_index = {
            (int(i), int(j)): k for k, (i, j) in enumerate(zip(edges["source"], edges["target"]))
        }
        component_rows = {}
        for component in ("pressure", "viscosity", "total"):
            pair_residuals = []
            pair_force_scales = []
            for k, (i_raw, j_raw) in enumerate(zip(edges["source"], edges["target"])):
                i = int(i_raw)
                j = int(j_raw)
                if i < j:
                    reverse = reverse_index[(j, i)]
                    pair_residuals.append(directed[component][k] + directed[component][reverse])
                    pair_force_scales.append(
                        np.linalg.norm(directed[component][k]) + np.linalg.norm(directed[component][reverse])
                    )
            pair_residual_array = np.asarray(pair_residuals)
            force_values = (float(config["physics"]["rho0"]) / state["x"].shape[0]) * sph[component]
            total_force = kahan_sum(force_values)
            global_normalized = normalized_force(total_force, force_values)
            pair_scale = float(np.sum(pair_force_scales))
            pair_normalized = float(np.linalg.norm(np.sum(pair_residual_array, axis=0)) / pair_scale) if pair_scale > 0 else 0.0
            component_rows[component] = {
                "maximum_pair_antisymmetry_residual": float(np.max(np.linalg.norm(pair_residual_array, axis=1))),
                "summed_pair_residual": np.sum(pair_residual_array, axis=0).tolist(),
                "normalized_pair_residual": pair_normalized,
                "SPH_total_force": total_force.tolist(),
                "SPH_normalized_internal_force_residual": global_normalized,
                "summation_order": summation_audit(force_values),
                "status": "PASS" if global_normalized <= tolerance and pair_normalized <= tolerance else "FAIL",
            }
        status = "PASS" if topology["status"] == "PASS" and all(
            row["status"] == "PASS" for row in component_rows.values()
        ) else "FAIL"
        if raw["disorder_identity"].startswith("jitter") and status != "PASS":
            jitter_failure = True
        rows.append(
            {
                "candidate_id": raw["case_id"],
                "disorder_identity": raw["disorder_identity"],
                "neighbor_reciprocity_and_topology": topology,
                "components": component_rows,
                "status": status,
            }
        )
    return {
        "tolerance": tolerance,
        "audit_separation": [
            "pairwise_algebraic_cancellation",
            "neighbor_reciprocity",
            "floating_point_accumulation",
            "topology_mismatch",
        ],
        "rows": rows,
        "all_cases_PASS": all(row["status"] == "PASS" for row in rows),
        "jitter_failure_status": "SPH_PAIRWISE_CONSERVATION_FAILURE" if jitter_failure else "NOT_TRIGGERED",
    }


def continuum_balance(config: dict[str, Any]) -> dict[str, Any]:
    rho0 = float(config["physics"]["rho0"])
    amp_rho = float(config["physics"]["density_amplitude"])
    amp_v = float(config["physics"]["velocity_amplitude"])
    c0 = float(config["physics"]["sound_speed"])
    nu = float(config["physics"]["kinematic_viscosity"])
    grid_n = 512
    grid = (np.arange(grid_n, dtype=np.float64) + 0.5) / grid_n
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    k = 2.0 * math.pi
    rho = rho0 * (1.0 + amp_rho * np.sin(k * xx) * np.sin(k * yy))
    velocity = np.stack(
        (amp_v * np.sin(k * xx) * np.cos(k * yy), -amp_v * np.cos(k * xx) * np.sin(k * yy)), axis=-1
    )
    gradient_pressure = c0 * c0 * rho0 * amp_rho * k * np.stack(
        (np.cos(k * xx) * np.sin(k * yy), np.sin(k * xx) * np.cos(k * yy)), axis=-1
    )
    laplacian_velocity = -2.0 * k * k * velocity
    force_density_pressure = -gradient_pressure
    force_density_viscosity = rho[..., None] * nu * laplacian_velocity
    quadrature = {
        "pressure": np.mean(force_density_pressure, axis=(0, 1)).tolist(),
        "viscosity": np.mean(force_density_viscosity, axis=(0, 1)).tolist(),
    }
    quadrature["total"] = (
        np.asarray(quadrature["pressure"]) + np.asarray(quadrature["viscosity"])
    ).tolist()
    return {
        "continuum_force_definition": "integral_Omega rho_times_a_reference_dV",
        "analytic_closed_form": {
            "pressure": [0.0, 0.0],
            "viscosity": [0.0, 0.0],
            "total": [0.0, 0.0],
            "derivation": "periodic gradient integral and all nonzero trigonometric modes integrate to zero",
        },
        "Fourier_spectral_integral": {
            "pressure": [0.0, 0.0],
            "viscosity": [0.0, 0.0],
            "total": [0.0, 0.0],
            "method": "zero_mode_of_exact_periodic_trigonometric_force_density",
        },
        "high_order_uniform_grid_quadrature": {
            "grid": f"{grid_n}x{grid_n}_periodic_midpoint",
            **quadrature,
        },
        "pressure_zero_expected": True,
        "viscosity_zero_expected": True,
        "total_zero_expected": True,
        "status": "PASS"
        if max(np.linalg.norm(value) for value in map(np.asarray, quadrature.values())) <= 1.0e-12
        else "FAIL",
        "operator_status_if_nonzero": "CONTINUUM_OPERATOR_NOT_PAIR_FORCE_COMPATIBLE",
    }


def pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    left_centered = left - np.mean(left)
    right_centered = right - np.mean(right)
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    return float(np.dot(left_centered, right_centered) / denominator) if denominator > 0.0 else None


def local_quadrature_geometry(
    generator: Any, state: dict[str, np.ndarray], raw: dict[str, Any], config: dict[str, Any]
) -> dict[str, np.ndarray]:
    case = runtime_case(raw)
    edges = generator.build_edges(state, case, config, apply_control=False)
    n = state["x"].shape[0]
    mass = float(config["physics"]["rho0"]) / n
    volume = mass / state["rho"]
    dx = float(config["domain"]["box_length"]) / int(raw["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    self_weight = float(generator.kernel_values(np.asarray([0.0]), h)[0][0])
    zeroth = np.zeros(n)
    first = np.zeros((n, 2))
    anisotropy = np.zeros(n)
    for i in range(n):
        selection = edges["source"] == i
        neighbors = edges["target"][selection]
        displacement = edges["displacement"][selection]
        distance = np.linalg.norm(displacement, axis=1)
        weights, _ = generator.kernel_values(distance, h)
        zeroth[i] = volume[i] * self_weight + np.sum(volume[neighbors] * weights) - 1.0
        first[i] = np.sum((volume[neighbors] * weights)[:, None] * displacement, axis=0)
        active = weights > 0.0
        moment = np.einsum("n,ni,nj->ij", weights[active], displacement[active], displacement[active])
        eigenvalues = np.linalg.eigvalsh(moment)
        anisotropy[i] = float(eigenvalues[0] / eigenvalues[-1]) if eigenvalues[-1] > 0.0 else 0.0
    return {
        "zeroth_defect": zeroth,
        "first_defect_norm": np.linalg.norm(first, axis=1),
        "coverage_isotropy": anisotropy,
    }


def particle_quadrature_audit(
    matrix: dict[str, Any], component_cache: dict[str, dict[str, np.ndarray]], generator: Any, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]]]:
    rows = []
    geometry_cache = {}
    for raw in matrix["cases"]:
        state = generator.initial_state(runtime_case(raw), config)
        n = state["x"].shape[0]
        mass = float(config["physics"]["rho0"]) / n
        volume = mass / state["rho"]
        geometry = local_quadrature_geometry(generator, state, raw, config)
        geometry_cache[raw["case_id"]] = geometry
        components = {}
        for component in ("pressure", "viscosity", "total"):
            acceleration = component_cache[raw["case_id"]][f"analytic_{component}"]
            mass_weighted = kahan_sum(mass * acceleration)
            volume_weighted_acceleration = kahan_sum(volume[:, None] * acceleration)
            physical_force_density_volume = kahan_sum(
                volume[:, None] * state["rho"][:, None] * acceleration
            )
            components[component] = {
                "mass_weighted_sum_m_a_ref": mass_weighted.tolist(),
                "volume_weighted_sum_m_over_rho_a_ref_diagnostic": volume_weighted_acceleration.tolist(),
                "volume_weighted_physical_force_density": physical_force_density_volume.tolist(),
                "mass_vs_force_density_volume_identity_norm": float(
                    np.linalg.norm(mass_weighted - physical_force_density_volume)
                ),
            }
        local_force = mass * component_cache[raw["case_id"]]["analytic_total"]
        global_force = kahan_sum(local_force)
        direction = global_force / np.linalg.norm(global_force) if np.linalg.norm(global_force) > 0.0 else np.zeros(2)
        aligned_contribution = local_force @ direction
        geometry_defect = 1.0 - geometry["coverage_isotropy"]
        rows.append(
            {
                "candidate_id": raw["case_id"],
                "disorder_identity": raw["disorder_identity"],
                "components": components,
                "partition_of_unity": {
                    "zeroth_defect_RMS": float(np.sqrt(np.mean(geometry["zeroth_defect"] ** 2))),
                    "zeroth_defect_Linf": float(np.max(np.abs(geometry["zeroth_defect"]))),
                    "first_moment_defect_RMS": float(np.sqrt(np.mean(geometry["first_defect_norm"] ** 2))),
                    "first_moment_defect_Linf": float(np.max(geometry["first_defect_norm"])),
                },
                "particle_coverage_anisotropy": {
                    "isotropy_min": float(np.min(geometry["coverage_isotropy"])),
                    "isotropy_median": float(np.median(geometry["coverage_isotropy"])),
                },
                "local_residual_geometry_correlations": {
                    "global_force_aligned_local_contribution_vs_abs_zeroth_defect": pearson(
                        aligned_contribution, np.abs(geometry["zeroth_defect"])
                    ),
                    "global_force_aligned_local_contribution_vs_first_moment_defect": pearson(
                        aligned_contribution, geometry["first_defect_norm"]
                    ),
                    "global_force_aligned_local_contribution_vs_anisotropy_defect": pearson(
                        aligned_contribution, geometry_defect
                    ),
                },
            }
        )
    return {
        "continuum_comparator": "zero pressure viscosity and total force",
        "alternative_weights_role": "diagnostic_quadrature_attribution_only",
        "alternative_weights_replace_target": False,
        "rows": rows,
    }, geometry_cache


def reference_pair_conservation(
    matrix: dict[str, Any], component_cache: dict[str, dict[str, np.ndarray]], config: dict[str, Any]
) -> dict[str, Any]:
    rows = []
    for raw in matrix["cases"]:
        n = int(raw["particles_per_axis"]) ** 2
        mass = float(config["physics"]["rho0"]) / n
        components = {}
        for component in ("pressure", "viscosity", "total"):
            fourier = kahan_sum(mass * component_cache[raw["case_id"]][f"fourier_{component}"])
            analytic = kahan_sum(mass * component_cache[raw["case_id"]][f"analytic_{component}"])
            components[component] = {
                "F_ref_Fourier": fourier.tolist(),
                "F_ref_analytic": analytic.tolist(),
                "difference_norm": float(np.linalg.norm(fourier - analytic)),
            }
        field_difference = component_cache[raw["case_id"]]["fourier_total"] - component_cache[raw["case_id"]]["analytic_total"]
        target_force = kahan_sum(mass * component_cache[raw["case_id"]]["target_total"])
        rows.append(
            {
                "candidate_id": raw["case_id"],
                "components": components,
                "field_difference_L2_particle_rms": float(
                    np.sqrt(np.mean(np.sum(field_difference * field_difference, axis=1)))
                ),
                "total_force_residuals_consistent": components["total"]["difference_norm"] <= 1.0e-12,
                "classification": "PARTICLE_QUADRATURE_CONTAMINATION_CANDIDATE"
                if components["total"]["difference_norm"] <= 1.0e-12 and np.linalg.norm(target_force) > 1.0e-12
                else "REFERENCE_OR_ZERO_RESIDUAL_CHECK",
            }
        )
    return {
        "rows": rows,
        "reference_sensitivity_reopened": not all(row["total_force_residuals_consistent"] for row in rows),
        "all_reference_force_results_consistent": all(row["total_force_residuals_consistent"] for row in rows),
    }


def incidence_and_geometry(edges: dict[str, np.ndarray], n: int) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray]:
    selection = edges["source"] < edges["target"]
    source = edges["source"][selection].astype(np.int64)
    target = edges["target"][selection].astype(np.int64)
    displacement = edges["displacement"][selection]
    edge_count = source.size
    columns = np.repeat(np.arange(edge_count), 2)
    rows = np.column_stack((source, target)).ravel()
    values = np.tile(np.asarray([1.0, -1.0]), edge_count)
    incidence = coo_matrix((values, (rows, columns)), shape=(n, edge_count)).tocsr()
    return incidence, source, target, displacement


def pair_representability(
    matrix: dict[str, Any], targets: dict[str, dict[str, Any]], generator: Any, stage02f: Any, config: dict[str, Any], tolerance: float, geometry_cache: dict[str, dict[str, np.ndarray]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = []
    jitter_rows = []
    for raw in matrix["cases"]:
        state = generator.initial_state(runtime_case(raw), config)
        edges = generator.build_edges(state, runtime_case(raw), config, apply_control=False)
        n = state["x"].shape[0]
        mass = float(config["physics"]["rho0"]) / n
        y = mass * np.asarray(targets[raw["case_id"]]["delta_a_primary"], dtype=np.float64)
        incidence, source, target, displacement = incidence_and_geometry(edges, n)
        component_count, _ = connected_components((incidence @ incidence.T), directed=False)
        edge_count = incidence.shape[1]
        y_pair_expected = y - np.mean(y, axis=0, keepdims=True)
        laplacian = (incidence @ incidence.T).tocsr()
        potential = np.zeros((n, 2), dtype=np.float64)
        for component in range(2):
            potential[:-1, component] = spsolve(laplacian[:-1, :-1], y_pair_expected[:-1, component])
        edge_force = incidence.T @ potential
        y_pair = incidence @ edge_force
        y_node = y - y_pair
        general_residual = float(np.linalg.norm(y_node) / np.linalg.norm(y))

        distance = np.linalg.norm(displacement, axis=1)
        unit = displacement / distance[:, None]
        central_rows = np.concatenate((2 * source, 2 * source + 1, 2 * target, 2 * target + 1))
        central_cols = np.tile(np.arange(edge_count), 4)
        central_values = np.concatenate((unit[:, 0], unit[:, 1], -unit[:, 0], -unit[:, 1]))
        central_operator = coo_matrix(
            (central_values, (central_rows, central_cols)), shape=(2 * n, edge_count)
        ).tocsr()
        central_solution = lsqr(
            central_operator,
            y.reshape(-1),
            atol=1.0e-13,
            btol=1.0e-13,
            iter_lim=max(2000, 5 * edge_count),
        )
        central_fit = (central_operator @ central_solution[0]).reshape(n, 2)
        central_residual = float(np.linalg.norm(y - central_fit) / np.linalg.norm(y))
        relative_position = state["x"] - 0.5 * float(config["domain"]["box_length"])
        target_torque = float(np.sum(relative_position[:, 0] * y[:, 1] - relative_position[:, 1] * y[:, 0]))
        central_torque = float(
            np.sum(relative_position[:, 0] * central_fit[:, 1] - relative_position[:, 1] * central_fit[:, 0])
        )
        general = {
            "exact_solvability_within_tolerance": general_residual <= tolerance,
            "scalar_incidence_rank": n - component_count,
            "vector_incidence_rank": 2 * (n - component_count),
            "scalar_null_space_dimension": edge_count - n + component_count,
            "vector_null_space_dimension": 2 * (edge_count - n + component_count),
            "connected_component_count": int(component_count),
            "undirected_edge_count": int(edge_count),
            "least_squares_residual_norm": float(np.linalg.norm(y_node)),
            "normalized_projection_residual": general_residual,
            "edge_force_antisymmetry_by_construction": True,
        }
        central = {
            "exact_solvability_within_tolerance": central_residual <= tolerance,
            "normalized_residual": central_residual,
            "LSQR_stop_code": int(central_solution[1]),
            "LSQR_iterations": int(central_solution[2]),
            "target_torque": target_torque,
            "central_projection_torque": central_torque,
            "torque_residual": target_torque - central_torque,
            "hard_gate": False,
            "periodic_torque_convention": "wrapped_positions_relative_to_box_center_with_minimum_image_edges",
        }
        rows.append(
            {
                "candidate_id": raw["case_id"],
                "disorder_identity": raw["disorder_identity"],
                "general_antisymmetric_vector_pair_force": general,
                "central_pair_force_diagnostic": central,
                "projection_written_back_to_target": False,
            }
        )
        if raw["disorder_identity"].startswith("jitter"):
            reference_difference = mass * (
                np.asarray(targets[raw["case_id"]]["a_FOURIER2"])
                - np.asarray(targets[raw["case_id"]]["a_ANALYTIC"])
            )
            reference_norm = float(np.linalg.norm(reference_difference))
            geometry = geometry_cache[raw["case_id"]]
            node_magnitude = np.linalg.norm(y_node, axis=1)
            jitter_rows.append(
                {
                    "candidate_id": raw["case_id"],
                    "decomposition_identity": "y = y_pair + y_node",
                    "norm_y": float(np.linalg.norm(y)),
                    "norm_y_pair": float(np.linalg.norm(y_pair)),
                    "norm_y_node": float(np.linalg.norm(y_node)),
                    "y_node_over_y_ratio": general_residual,
                    "spatial_distribution": {
                        "particle_position": state["x"].tolist(),
                        "y": y.tolist(),
                        "y_pair_analysis_projection": np.asarray(y_pair).tolist(),
                        "y_node_nonrepresentable_residual": np.asarray(y_node).tolist(),
                    },
                    "Fourier_signature": {
                        "y_pair": stage02f.fourier_signature(state["x"], np.asarray(y_pair)).tolist(),
                        "y_node": stage02f.fourier_signature(state["x"], np.asarray(y_node)).tolist(),
                    },
                    "geometry_correlation": {
                        "node_magnitude_vs_abs_zeroth_defect": pearson(
                            node_magnitude, np.abs(geometry["zeroth_defect"])
                        ),
                        "node_magnitude_vs_first_moment_defect": pearson(
                            node_magnitude, geometry["first_defect_norm"]
                        ),
                        "node_magnitude_vs_anisotropy_defect": pearson(
                            node_magnitude, 1.0 - geometry["coverage_isotropy"]
                        ),
                        "note": "node magnitude is nearly constant for a connected incidence projection; zero-variance correlations may be null",
                    },
                    "reference_uncertainty_comparison": {
                        "Fourier_analytic_nodal_force_difference_norm": reference_norm,
                        "node_residual_to_reference_difference_norm_ratio": float(np.linalg.norm(y_node) / reference_norm)
                        if reference_norm > 0.0
                        else math.inf,
                        "node_residual_clearly_above_reference_uncertainty": bool(
                            np.linalg.norm(y_node) > 100.0 * reference_norm
                        ),
                    },
                    "projection_written_back_to_target": False,
                }
            )
    return {
        "general_vector_pair_force_is_hard_gate": True,
        "central_pair_force_is_hard_gate": False,
        "tolerance": tolerance,
        "rows": rows,
    }, {
        "jitter_candidate_count": len(jitter_rows),
        "rows": jitter_rows,
        "original_target_replaced": False,
    }


def architecture_decision(
    continuum: dict[str, Any], sph_pair: dict[str, Any], reference_pair: dict[str, Any], representability: dict[str, Any], jitter: dict[str, Any], scope: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    regular_rows = [row for row in representability["rows"] if row["disorder_identity"] == "regular"]
    jitter_rows = [row for row in representability["rows"] if row["disorder_identity"].startswith("jitter")]
    conditions = {
        "five_regular_candidates_remain_pair_force_compatible": len(regular_rows) == 5
        and all(row["general_antisymmetric_vector_pair_force"]["exact_solvability_within_tolerance"] for row in regular_rows),
        "continuum_exact_total_force_PASS": continuum["status"] == "PASS",
        "baseline_SPH_pairwise_cancellation_PASS": sph_pair["all_cases_PASS"],
        "Fourier_analytic_force_results_consistent": reference_pair["all_reference_force_results_consistent"],
        "jitter_general_pair_exact_solvability": all(
            row["general_antisymmetric_vector_pair_force"]["exact_solvability_within_tolerance"] for row in jitter_rows
        ),
        "jitter_node_residual_above_reference_uncertainty": all(
            row["reference_uncertainty_comparison"]["node_residual_clearly_above_reference_uncertainty"]
            for row in jitter["rows"]
        ),
        "jitter_residual_attributed_to_particle_quadrature": continuum["status"] == "PASS"
        and sph_pair["all_cases_PASS"]
        and reference_pair["all_reference_force_results_consistent"]
        and not all(
            row["general_antisymmetric_vector_pair_force"]["exact_solvability_within_tolerance"] for row in jitter_rows
        ),
        "independent_preregistered_conservative_reference_quadrature_exists": False,
        "target_modification_prohibited_and_not_used": True,
    }
    pair_only = (
        conditions["five_regular_candidates_remain_pair_force_compatible"]
        and conditions["jitter_residual_attributed_to_particle_quadrature"]
        and conditions["jitter_node_residual_above_reference_uncertainty"]
        and not conditions["independent_preregistered_conservative_reference_quadrature_exists"]
        and conditions["target_modification_prohibited_and_not_used"]
    )
    if pair_only:
        decision = "PAIR_ONLY_REGULAR_SCOPE"
        stage02j = "authorized_regular_scope_only"
        final_state_category = "resolved_pair_only"
    else:
        decision = "CONSERVATION_SOURCE_UNRESOLVED"
        stage02j = "not_authorized"
        final_state_category = "unresolved"
    architecture = {
        "decision": decision,
        "decision_rule_source": str(SCOPE_PATH.relative_to(REPO_ROOT)),
        "decision_rule_source_hash": file_hash(SCOPE_PATH),
        "evidence_conditions": conditions,
        "source_attribution": "particle_quadrature_contamination_under_frozen_equal_mass_target_contract"
        if pair_only
        else "unresolved",
        "future_pair_force_PIO_scope": "five_regular_candidates_only" if pair_only else "none",
        "jitter_candidate_role": "distribution_shift_validation_and_diagnostic_only" if pair_only else "unresolved",
        "jitter_as_pair_force_training_label": False,
        "Stage02J_authorization": stage02j,
        "versioned_conservative_target_contract_status": "not_established",
        "hybrid_architecture_required": False,
        "original_target_modified": False,
        "mean_subtraction_used": False,
        "projection_writeback_used": False,
    }
    qualification = {
        "architecture_decision": decision,
        "final_state_category": final_state_category,
        "Stage02J_authorization": stage02j,
        "authorized_candidate_ids": [
            "i_res_n12_h26_regular",
            "i_anchor_n16_h26_regular",
            "i_res_n20_h26_regular",
            "i_sup_n16_h22_regular",
            "i_sup_n16_h30_regular",
        ]
        if pair_only
        else [],
        "jitter_candidate_ids_retained": [
            "i_dis_n16_h26_jitter05",
            "i_dis_n16_h26_jitter10",
        ],
        "candidate_discretization_target_count_preserved": 7,
        "dataset_generated": False,
        "model_generated": False,
        "training_performed": False,
    }
    return architecture, qualification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Stage 02I-R audit requires explicit --execute")
    outputs = (
        FORCE_PATH,
        SPH_PAIR_PATH,
        CONTINUUM_PATH,
        QUADRATURE_PATH,
        REFERENCE_PAIR_PATH,
        REPRESENTABILITY_PATH,
        JITTER_DECOMPOSITION_PATH,
        ARCHITECTURE_PATH,
        QUALIFICATION_PATH,
        MANIFEST_PATH,
    )
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"No-overwrite contract: {path}")

    freeze = load_json(FREEZE_PATH)
    scope = load_yaml(SCOPE_PATH)
    matrix = load_yaml(MATRIX_PATH)
    target_artifact = load_json(TARGET_PATH)
    verify_freeze(freeze, target_artifact)
    targets = {row["candidate_id"]: row for row in target_artifact["candidates"]}
    config = load_yaml(CONFIG_PATH)
    tolerance = float(scope["analysis_scope"]["normalized_internal_force_tolerance"])
    generator = load_module("stage02c_generator_readonly_for_stage02ir", GENERATOR_PATH)
    stage02f = load_module("stage02f_spatial_readonly_for_stage02ir", STAGE02F_SCRIPT_PATH)

    force, component_cache = force_decomposition(matrix, targets, generator, config)
    sph_pair = sph_pairwise_audit(matrix, generator, config, tolerance)
    continuum = continuum_balance(config)
    quadrature, geometry_cache = particle_quadrature_audit(matrix, component_cache, generator, config)
    reference_pair = reference_pair_conservation(matrix, component_cache, config)
    representability, jitter = pair_representability(
        matrix, targets, generator, stage02f, config, tolerance, geometry_cache
    )
    architecture, qualification = architecture_decision(
        continuum, sph_pair, reference_pair, representability, jitter, scope
    )

    write_json_no_overwrite(FORCE_PATH, force)
    write_json_no_overwrite(SPH_PAIR_PATH, sph_pair)
    write_json_no_overwrite(CONTINUUM_PATH, continuum)
    write_json_no_overwrite(QUADRATURE_PATH, quadrature)
    write_json_no_overwrite(REFERENCE_PAIR_PATH, reference_pair)
    write_json_no_overwrite(REPRESENTABILITY_PATH, representability)
    write_json_no_overwrite(JITTER_DECOMPOSITION_PATH, jitter)
    write_json_no_overwrite(ARCHITECTURE_PATH, architecture)
    write_json_no_overwrite(QUALIFICATION_PATH, qualification)

    verify_freeze(freeze, load_json(TARGET_PATH))
    input_paths = (
        GENERATOR_PATH,
        STAGE02F_SCRIPT_PATH,
        CONFIG_PATH,
        MATRIX_PATH,
        TARGET_PATH,
        FREEZE_PATH,
        SCOPE_PATH,
        H_RULES_PATH,
    )
    artifact_paths = (
        FORCE_PATH,
        SPH_PAIR_PATH,
        CONTINUUM_PATH,
        QUADRATURE_PATH,
        REFERENCE_PAIR_PATH,
        REPRESENTABILITY_PATH,
        JITTER_DECOMPOSITION_PATH,
        ARCHITECTURE_PATH,
        QUALIFICATION_PATH,
    )
    manifest = {
        "campaign_id": "stage02ir_conservation_compatibility_closure_20260804",
        "input_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in input_paths},
        "output_files": {str(path.relative_to(REPO_ROOT)): file_hash(path) for path in artifact_paths},
        "freeze_reverified_after_controlled_recomputation": True,
        "provenance_complete": True,
        "seven_targets_preserved": True,
        "original_target_modified": False,
        "target_mean_subtracted": False,
        "projection_written_back": False,
        "no_dataset": True,
        "no_split": True,
        "no_normalization": True,
        "no_model": True,
        "no_training": True,
        "no_performance_claim": True,
    }
    write_json_no_overwrite(MANIFEST_PATH, manifest)
    print(
        json.dumps(
            {
                "continuum_status": continuum["status"],
                "SPH_pairwise_all_pass": sph_pair["all_cases_PASS"],
                "reference_force_consistency": reference_pair["all_reference_force_results_consistent"],
                "architecture_decision": architecture["decision"],
                "Stage02J_authorization": architecture["Stage02J_authorization"],
                "final_state_category": qualification["final_state_category"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
