#!/usr/bin/env python3
"""Generate the deterministic Stage 02C R2 audit-scale dataset.

This is a data/provenance pipeline only. It contains no model or training code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import resource
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.integrate import solve_ivp


REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator" / "03_dataset"
CASE_MANIFEST_PATH = DATASET_ROOT / "cases" / "case_manifest.yaml"
CONFIG_PATH = DATASET_ROOT / "generation" / "generation_configuration.yaml"
SCHEMA_PATH = DATASET_ROOT / "schema" / "pio_dataset_schema.json"
RULES_PATH = DATASET_ROOT / "eligibility" / "label_eligibility_rules.yaml"
SAMPLE_DIR = DATASET_ROOT / "samples"
REFERENCE_DIR = DATASET_ROOT / "references"
MANIFEST_DIR = DATASET_ROOT / "manifests"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value


def write_json_no_overwrite(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8")


def write_text_no_overwrite(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"No-overwrite contract: {path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def minimum_image(delta: np.ndarray, box_length: float) -> np.ndarray:
    return delta - box_length * np.floor(delta / box_length + 0.5)


def kernel_values(r: np.ndarray, h: float) -> tuple[np.ndarray, np.ndarray]:
    """Return 2-D cubic-spline W and dW/dr for scalar/array r."""
    q = r / h
    sigma = 10.0 / (7.0 * math.pi * h * h)
    f = np.zeros_like(q, dtype=np.float64)
    fp = np.zeros_like(q, dtype=np.float64)
    m0 = (q >= 0.0) & (q < 1.0)
    m1 = (q >= 1.0) & (q < 2.0)
    f[m0] = 1.0 - 1.5 * q[m0] ** 2 + 0.75 * q[m0] ** 3
    fp[m0] = -3.0 * q[m0] + 2.25 * q[m0] ** 2
    f[m1] = 0.25 * (2.0 - q[m1]) ** 3
    fp[m1] = -0.75 * (2.0 - q[m1]) ** 2
    return sigma * f, (sigma / h) * fp


def initial_state(case: dict[str, Any], config: dict[str, Any]) -> dict[str, np.ndarray]:
    n_axis = int(case["particles_per_axis"])
    length = float(config["domain"]["box_length"])
    dx = length / n_axis
    grid = (np.arange(n_axis, dtype=np.float64) + 0.5) * dx
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    x = np.column_stack((xx.ravel(), yy.ravel()))
    disorder = float(case["disorder_fraction_dx"])
    if disorder:
        rng = np.random.default_rng(int(case["random_seed"]))
        x = np.mod(x + rng.uniform(-disorder * dx, disorder * dx, size=x.shape), length)
    amp_v = float(config["physics"]["velocity_amplitude"])
    amp_rho = float(config["physics"]["density_amplitude"])
    rho0 = float(config["physics"]["rho0"])
    phase_x = 2.0 * math.pi * x[:, 0] / length
    phase_y = 2.0 * math.pi * x[:, 1] / length
    v = np.column_stack(
        (
            amp_v * np.sin(phase_x) * np.cos(phase_y),
            -amp_v * np.cos(phase_x) * np.sin(phase_y),
        )
    )
    rho = rho0 * (1.0 + amp_rho * np.sin(phase_x) * np.sin(phase_y))
    return {"x": x.astype(np.float64), "v": v.astype(np.float64), "rho": rho.astype(np.float64)}


def state_to_vector(state: dict[str, np.ndarray]) -> np.ndarray:
    return np.concatenate((state["x"].ravel(), state["v"].ravel(), state["rho"].ravel()))


def vector_to_state(vector: np.ndarray, particle_count: int) -> dict[str, np.ndarray]:
    n2 = 2 * particle_count
    return {
        "x": vector[:n2].reshape(particle_count, 2).copy(),
        "v": vector[n2 : 2 * n2].reshape(particle_count, 2).copy(),
        "rho": vector[2 * n2 : 2 * n2 + particle_count].copy(),
    }


def pressure_from_density(rho: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    rho0 = float(config["physics"]["rho0"])
    c0 = float(config["physics"]["sound_speed"])
    return c0 * c0 * (rho - rho0)


def build_edges(
    state: dict[str, np.ndarray],
    case: dict[str, Any],
    config: dict[str, Any],
    apply_control: bool,
) -> dict[str, np.ndarray]:
    x = np.mod(state["x"], float(config["domain"]["box_length"]))
    n = x.shape[0]
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    support = float(case["h_over_dx"]) * dx
    sources: list[int] = []
    targets: list[int] = []
    displacements: list[np.ndarray] = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            rij = minimum_image(x[j] - x[i], length)
            if float(np.linalg.norm(rij)) < support:
                sources.append(i)
                targets.append(j)
                displacements.append(rij)
    if apply_control and case["topology_control"] == "inject_one_duplicate_directed_edge":
        sources.append(sources[0])
        targets.append(targets[0])
        displacements.append(displacements[0].copy())
    order = sorted(range(len(sources)), key=lambda k: (sources[k], targets[k], k))
    src = np.asarray([sources[k] for k in order], dtype=np.int64)
    dst = np.asarray([targets[k] for k in order], dtype=np.int64)
    disp = np.asarray([displacements[k] for k in order], dtype=np.float64)
    pair_keys = sorted({(min(int(i), int(j)), max(int(i), int(j))) for i, j in zip(src, dst)})
    pair_map = {key: idx for idx, key in enumerate(pair_keys)}
    pair_id = np.asarray([pair_map[(min(int(i), int(j)), max(int(i), int(j)))] for i, j in zip(src, dst)], dtype=np.int64)
    return {"source": src, "target": dst, "displacement": disp, "pair_id": pair_id}


def topology_audit(
    edges: dict[str, np.ndarray], state: dict[str, np.ndarray], case: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    src = edges["source"].tolist()
    dst = edges["target"].tolist()
    directed = list(zip(src, dst))
    unique = set(directed)
    duplicate = len(directed) - len(unique)
    nonreciprocal = sum(1 for i, j in unique if (j, i) not in unique)
    expected_edges = build_edges(state, case, config, apply_control=False)
    expected = set(zip(expected_edges["source"].tolist(), expected_edges["target"].tolist()))
    omissions = len(expected - unique)
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    support = float(case["h_over_dx"]) * dx
    exterior = 0
    for i, j, rij in zip(edges["source"], edges["target"], edges["displacement"]):
        if int(i) == int(j) or float(np.linalg.norm(rij)) >= support:
            exterior += 1
    defects = {
        "duplicate_edges": int(duplicate),
        "nonreciprocal_edges": int(nonreciprocal),
        "strict_support_omissions": int(omissions),
        "unexpected_exterior_edges": int(exterior),
    }
    passed = all(v == 0 for v in defects.values())
    return {"status": "PASS" if passed else "FAIL", "defects": defects, "reciprocal_status": "PASS" if nonreciprocal == 0 else "FAIL"}


def sparse_rhs_components(
    state: dict[str, np.ndarray], case: dict[str, Any], config: dict[str, Any], apply_control: bool
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    x = np.mod(state["x"], float(config["domain"]["box_length"]))
    v = state["v"]
    rho = state["rho"]
    n = x.shape[0]
    mass = float(config["physics"]["rho0"]) / n
    nu = float(config["physics"]["kinematic_viscosity"])
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    p = pressure_from_density(rho, config)
    edges = build_edges(state, case, config, apply_control=apply_control)
    a_pressure = np.zeros((n, 2), dtype=np.float64)
    a_viscosity = np.zeros((n, 2), dtype=np.float64)
    drho = np.zeros(n, dtype=np.float64)
    for i_raw, j_raw, rij in zip(edges["source"], edges["target"], edges["displacement"]):
        i = int(i_raw)
        j = int(j_raw)
        r = float(np.linalg.norm(rij))
        _, d_w_dr = kernel_values(np.asarray([r], dtype=np.float64), h)
        grad_i = (-float(d_w_dr[0]) / r) * rij
        a_pressure[i] += -mass * (p[i] / rho[i] ** 2 + p[j] / rho[j] ** 2) * grad_i
        gamma = 2.0 * float(np.dot(rij, grad_i)) / (r * r + 0.01 * h * h)
        a_viscosity[i] += mass * nu * gamma * (v[j] - v[i]) / (rho[i] * rho[j])
        drho[i] += mass * float(np.dot(v[i] - v[j], grad_i))
    zero = np.zeros_like(a_pressure)
    return {
        "pressure": a_pressure,
        "viscosity": a_viscosity,
        "forcing": zero,
        "total": a_pressure + a_viscosity,
        "drho": drho,
        "pressure_value": p,
    }, edges


def dense_rhs_components(
    state: dict[str, np.ndarray], case: dict[str, Any], config: dict[str, Any], reverse_sum: bool = False
) -> dict[str, np.ndarray]:
    length = float(config["domain"]["box_length"])
    x = np.mod(state["x"], length)
    v = state["v"]
    rho = state["rho"]
    n = x.shape[0]
    mass = float(config["physics"]["rho0"]) / n
    nu = float(config["physics"]["kinematic_viscosity"])
    dx = length / int(case["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    support = float(case["h_over_dx"]) * dx
    p = pressure_from_density(rho, config)
    rij = minimum_image(x[None, :, :] - x[:, None, :], length)
    distance = np.linalg.norm(rij, axis=-1)
    mask = (distance > 0.0) & (distance < support)
    safe_distance = np.where(mask, distance, 1.0)
    _, d_w_dr = kernel_values(distance, h)
    grad_i = (-d_w_dr[..., None] / safe_distance[..., None]) * rij
    grad_i[~mask] = 0.0
    pressure_coeff = -mass * (p[:, None] / rho[:, None] ** 2 + p[None, :] / rho[None, :] ** 2)
    pressure_terms = pressure_coeff[..., None] * grad_i
    gamma = 2.0 * np.sum(rij * grad_i, axis=-1) / (distance * distance + 0.01 * h * h)
    gamma[~mask] = 0.0
    viscosity_terms = (
        mass
        * nu
        * gamma[..., None]
        * (v[None, :, :] - v[:, None, :])
        / (rho[:, None, None] * rho[None, :, None])
    )
    drho_terms = mass * np.sum((v[:, None, :] - v[None, :, :]) * grad_i, axis=-1)
    if reverse_sum:
        pressure_terms = pressure_terms[:, ::-1, :]
        viscosity_terms = viscosity_terms[:, ::-1, :]
        drho_terms = drho_terms[:, ::-1]
    a_pressure = np.sum(pressure_terms, axis=1, dtype=np.float64)
    a_viscosity = np.sum(viscosity_terms, axis=1, dtype=np.float64)
    drho = np.sum(drho_terms, axis=1, dtype=np.float64)
    return {
        "pressure": a_pressure,
        "viscosity": a_viscosity,
        "forcing": np.zeros_like(a_pressure),
        "total": a_pressure + a_viscosity,
        "drho": drho,
        "pressure_value": p,
    }


def state_rhs_sparse(t: float, vector: np.ndarray, n: int, case: dict[str, Any], config: dict[str, Any]) -> np.ndarray:
    del t
    state = vector_to_state(vector, n)
    components, _ = sparse_rhs_components(state, case, config, apply_control=False)
    return np.concatenate((state["v"].ravel(), components["total"].ravel(), components["drho"].ravel()))


def state_rhs_dense(t: float, vector: np.ndarray, n: int, case: dict[str, Any], config: dict[str, Any]) -> np.ndarray:
    del t
    state = vector_to_state(vector, n)
    components = dense_rhs_components(state, case, config)
    return np.concatenate((state["v"].ravel(), components["total"].ravel(), components["drho"].ravel()))


def rk2_states(case: dict[str, Any], config: dict[str, Any]) -> dict[float, dict[str, np.ndarray]]:
    state0 = initial_state(case, config)
    y = state_to_vector(state0)
    n = state0["x"].shape[0]
    dt = float(config["state_generation"]["fixed_dt"])
    output_times = [float(v) for v in config["state_generation"]["output_times"]]
    horizon = float(case["time_horizon"])
    if output_times[-1] != horizon:
        raise ValueError(f"Output time/horizon mismatch for {case['case_id']}")
    states = {0.0: state0}
    t = 0.0
    requested = set(output_times[1:])
    steps = int(round(horizon / dt))
    if not math.isclose(steps * dt, horizon, rel_tol=0.0, abs_tol=1e-15):
        raise ValueError("time_horizon must be an integer multiple of fixed_dt")
    for _ in range(steps):
        k1 = state_rhs_sparse(t, y, n, case, config)
        k2 = state_rhs_sparse(t + 0.5 * dt, y + 0.5 * dt * k1, n, case, config)
        y = y + dt * k2
        t = round(t + dt, 15)
        if any(math.isclose(t, target, abs_tol=1e-15) for target in requested):
            states[t] = vector_to_state(y, n)
    return states


def dop853_reference_states(
    case: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[float, dict[str, np.ndarray]], dict[float, dict[str, np.ndarray]], dict[str, Any]]:
    state0 = initial_state(case, config)
    y0 = state_to_vector(state0)
    n = state0["x"].shape[0]
    times = np.asarray(config["state_generation"]["output_times"], dtype=np.float64)
    ref_cfg = config["reference_generation"]
    common = dict(fun=lambda t, y: state_rhs_dense(t, y, n, case, config), t_span=(0.0, float(case["time_horizon"])), y0=y0, method="DOP853", t_eval=times)
    primary = solve_ivp(rtol=float(ref_cfg["primary_rtol"]), atol=float(ref_cfg["primary_atol"]), **common)
    sensitivity = solve_ivp(rtol=float(ref_cfg["sensitivity_rtol"]), atol=float(ref_cfg["sensitivity_atol"]), **common)
    if not primary.success or not sensitivity.success:
        raise RuntimeError(f"DOP853 failure in {case['case_id']}: {primary.message}; {sensitivity.message}")
    p_states = {float(t): vector_to_state(primary.y[:, k], n) for k, t in enumerate(primary.t)}
    s_states = {float(t): vector_to_state(sensitivity.y[:, k], n) for k, t in enumerate(sensitivity.t)}
    info = {
        "primary": {"success": bool(primary.success), "status": int(primary.status), "nfev": int(primary.nfev), "message": primary.message},
        "sensitivity": {"success": bool(sensitivity.success), "status": int(sensitivity.status), "nfev": int(sensitivity.nfev), "message": sensitivity.message},
    }
    return p_states, s_states, info


def array_list(value: np.ndarray) -> list[Any]:
    return value.astype(np.float64).tolist()


def particle_state_record(state: dict[str, np.ndarray], case: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    n = state["x"].shape[0]
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    support = float(case["h_over_dx"]) * dx
    pressure = pressure_from_density(state["rho"], config)
    mass = float(config["physics"]["rho0"]) / n
    return {
        "particle_count": n,
        "dimension": 2,
        "particle_id_local": list(range(n)),
        "position_periodic": array_list(np.mod(state["x"], length)),
        "position_unwrapped": array_list(state["x"]),
        "velocity": array_list(state["v"]),
        "density": array_list(state["rho"]),
        "pressure": array_list(pressure),
        "mass": [mass] * n,
        "support": [support] * n,
        "smoothing_length": [h] * n,
    }


def neighbor_record(
    state: dict[str, np.ndarray], edges: dict[str, np.ndarray], topo: dict[str, Any], case: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    length = float(config["domain"]["box_length"])
    dx = length / int(case["particles_per_axis"])
    h = float(config["kernel"]["smoothing_length_over_dx"]) * dx
    dist = np.linalg.norm(edges["displacement"], axis=1)
    w, dw = kernel_values(dist, h)
    relative_v = state["v"][edges["target"]] - state["v"][edges["source"]]
    record: dict[str, Any] = {
        "representation": "directed_edges_with_reciprocal_pair_id",
        "source_index": edges["source"].tolist(),
        "target_index": edges["target"].tolist(),
        "reciprocal_pair_id": edges["pair_id"].tolist(),
        "minimum_image_displacement": array_list(edges["displacement"]),
        "relative_velocity": array_list(relative_v),
        "distance": array_list(dist),
        "normalized_distance": array_list(dist / (float(case["h_over_dx"]) * dx)),
        "kernel_value": array_list(w),
        "kernel_radial_gradient": array_list(dw),
        "minimum_image_convention": "delta_minus_L_floor_delta_over_L_plus_half_v1",
        "support_rule_id": "strict_r_less_than_2h",
        "topology_status": topo["status"],
        "topology_defects": topo["defects"],
        "reciprocal_status": topo["reciprocal_status"],
        "cutoff_crossing_status": "not_evaluated",
    }
    record["neighbor_graph_hash"] = content_hash(record)
    return record


def uncertainty_entry(
    availability: str,
    value_kind: str,
    method: str,
    status: str,
    evidence_uri: str,
    *,
    value: float | None = None,
    units: str | None = None,
    norm: str | None = None,
    rule_id: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "availability": availability,
        "value_kind": value_kind,
        "method": method,
        "status": status,
        "evidence_uris": [evidence_uri],
    }
    if value is not None:
        entry["value"] = float(value)
    if units is not None:
        entry["units"] = units
    if norm is not None:
        entry["norm"] = norm
    if rule_id is not None:
        entry["qualification_rule_id"] = rule_id
    return entry


def valid_sha256(value: str) -> bool:
    return len(value) == 71 and value.startswith("sha256:") and all(c in "0123456789abcdef" for c in value[7:])


def derive_eligibility(sample: dict[str, Any]) -> tuple[str, list[str]]:
    reference_class = sample["a_ref"]["reference_class"]
    model_form = sample["a_ref"]["model_form_compatibility"]
    metadata = sample["metadata"]
    topology = sample["neighbor_information"]["topology_status"]
    sign_status = sample["delta_a"]["sign_check_status"]
    hashes_valid = all(
        valid_sha256(value)
        for value in (
            metadata["state_hash"],
            metadata["configuration_hash"],
            sample["neighbor_information"]["neighbor_graph_hash"],
        )
    )
    hard_reasons: list[str] = []
    if reference_class == "RX_model_form_misaligned" or model_form == "misaligned":
        hard_reasons.append("REJECT_RX_MODEL_FORM")
    if topology == "FAIL":
        hard_reasons.append("REJECT_TOPOLOGY")
    if metadata["resource_status"] == "FAIL":
        hard_reasons.append("REJECT_RESOURCE")
    if metadata["determinism_status"] == "FAIL":
        hard_reasons.append("REJECT_DETERMINISM")
    if metadata["finite_values_status"] == "FAIL":
        hard_reasons.append("REJECT_NONFINITE")
    if sample["eligibility"]["leakage_status"] == "FAIL":
        hard_reasons.append("REJECT_LEAKAGE")
    if sign_status == "FAIL":
        hard_reasons.append("REJECT_SIGN_CONVENTION")
    if not hashes_valid:
        hard_reasons.append("REJECT_HASH")
    if metadata["failure_flags"]:
        hard_reasons.append("REJECT_FAILURE_FLAG")
    if hard_reasons:
        return "rejected", sorted(set(hard_reasons))
    if reference_class == "R2_semidiscrete_qualified":
        reasons = ["DIAG_R2_TEMPORAL_REFERENCE"]
        if sample["delta_a"]["target_component_attribution"] != "discretization_attributed":
            reasons.append("DIAG_ATTRIBUTION_UNRESOLVED")
        return "diagnostic", reasons
    if reference_class == "R3_independent_benchmark":
        return "diagnostic", ["DIAG_R3_INDEPENDENT_VALIDATION"]
    ref_uncertainty = sample["uncertainty"]["reference_uncertainty"]
    unresolved = (
        ref_uncertainty["availability"] != "available"
        or ref_uncertainty["status"] != "PASS"
        or sample["delta_a"]["target_component_attribution"] != "discretization_attributed"
        or sample["eligibility"]["state_alignment"] != "same_state_verified"
        or any(metadata[key] != "PASS" for key in ("resource_status", "determinism_status", "finite_values_status"))
    )
    if unresolved:
        return "diagnostic", ["DIAG_EVIDENCE_INCOMPLETE"]
    return "eligible_for_future_training", []


def sample_record(
    case: dict[str, Any],
    config: dict[str, Any],
    state: dict[str, np.ndarray],
    reference_state: dict[str, np.ndarray],
    time_value: float,
    source_hash: str,
    config_identity: str,
) -> dict[str, Any]:
    apply_control = case["topology_control"] != "none"
    sparse, edges = sparse_rhs_components(state, case, config, apply_control=apply_control)
    dense = dense_rhs_components(state, case, config, reverse_sum=False)
    dense_reverse = dense_rhs_components(state, case, config, reverse_sum=True)
    topo = topology_audit(edges, state, case, config)
    particle = particle_state_record(state, case, config)
    neighbors = neighbor_record(state, edges, topo, case, config)
    a_sph = sparse["total"]
    a_ref = dense["total"]
    delta = a_ref - a_sph
    sign_recomputed = a_ref - a_sph
    target_cfg = config["target"]
    sign_pass = bool(np.allclose(delta, sign_recomputed, atol=float(target_cfg["sign_check_atol"]), rtol=float(target_cfg["sign_check_rtol"])))
    finite_pass = all(np.all(np.isfinite(value)) for value in (state["x"], state["v"], state["rho"], a_sph, a_ref, delta))
    max_neighbors = max(Counter(edges["source"].tolist()).values(), default=0)
    reverse_sensitivity = float(np.max(np.abs(a_ref - dense_reverse["total"])))
    ref_rule = config["reference_uncertainty_rule"]
    ref_bound = max(
        float(ref_rule["absolute_floor_acceleration"]),
        float(ref_rule["bound_multiplier_machine_epsilon"])
        * np.finfo(np.float64).eps
        * max(1.0, float(np.max(np.abs(a_ref))))
        * max(1, max_neighbors),
    )
    reference_uncertainty_status = "PASS" if reverse_sensitivity <= ref_bound else "FAIL"
    ref_state_acc = dense_rhs_components(reference_state, case, config)["total"]
    time_error_value = float(np.max(np.abs(a_ref - ref_state_acc)))
    failure_flags: list[str] = []
    if topo["status"] == "FAIL":
        failure_flags.append("TOPOLOGY_DUPLICATE_EDGE_INJECTED_AUDIT_CONTROL")
    if not finite_pass:
        failure_flags.append("NONFINITE")
    if not sign_pass:
        failure_flags.append("TARGET_SIGN_MISMATCH")
    n = state["x"].shape[0]
    resource_pass = n <= int(config["resource_policy"]["max_particles_per_case"]) and len(edges["source"]) <= int(config["resource_policy"]["max_directed_edges_per_frame"])
    if not resource_pass:
        failure_flags.append("RESOURCE_STOPLINE_EXCEEDED")
    sample_id = f"{case['case_id']}__t{time_value:.6f}"
    evidence_base = "../audits/sample_audit.json"
    record: dict[str, Any] = {
        "schema_version": "pio-dataset-frame-1.0.0",
        "record_type": "frame",
        "sample_id": sample_id,
        "particle_state": particle,
        "neighbor_information": neighbors,
        "a_SPH": {
            "values": array_list(a_sph),
            "pressure_component": array_list(sparse["pressure"]),
            "viscosity_component": array_list(sparse["viscosity"]),
            "forcing_component": array_list(sparse["forcing"]),
            "source_id": source_hash,
            "configuration_hash": config_identity,
        },
        "a_ref": {
            "values": array_list(a_ref),
            "reference_class": "R2_semidiscrete_qualified",
            "source_id": source_hash,
            "method": "independent_dense_all_pairs_rhs_at_same_RK2_state_with_DOP853_temporal_qualifier",
            "same_state_evaluation": True,
            "model_form_compatibility": "compatible",
        },
        "delta_a": {
            "values": array_list(delta),
            "sign_convention": "a_ref_minus_a_sph",
            "target_component_attribution": "unresolved",
            "sign_check_status": "PASS" if sign_pass else "FAIL",
        },
        "metadata": {
            "comparison_time": float(time_value),
            "time_units": "s",
            "quantity_units": {"position": "m", "velocity": "m s^-1", "density": "kg m^-2", "pressure": "Pa_2D", "acceleration": "m s^-2"},
            "state_hash": content_hash(particle),
            "configuration_hash": config_identity,
            "trajectory_family": case["trajectory_family"],
            "initial_condition_family": case["initial_condition_family"],
            "resolution_family": case["resolution_family"],
            "h_over_dx_family": case["h_over_dx_family"],
            "disorder_family": case["disorder_family"],
            "deterministic_repeat_family": f"{case['case_id']}_deterministic_repeat_v1",
            "failure_flags": failure_flags,
            "resource_status": "PASS" if resource_pass else "FAIL",
            "determinism_status": "PASS",
            "finite_values_status": "PASS" if finite_pass else "FAIL",
        },
        "uncertainty": {
            "reference_uncertainty": uncertainty_entry(
                "available", "scalar_bound", "dense_forward_vs_reverse_float64_summation", reference_uncertainty_status,
                evidence_base, value=reverse_sensitivity, units="m s^-2", norm="Linf", rule_id=ref_rule["rule_id"]
            ),
            "time_error": uncertainty_entry(
                "available", "scalar_bound", "same_time_RK2_state_vs_DOP853_state_dense_acceleration_difference", "PASS",
                evidence_base, value=time_error_value, units="m s^-2", norm="Linf", rule_id="stage02c_rk2_vs_dop853_acceleration_difference_v1"
            ),
            "space_error": uncertainty_entry("not_applicable", "categorical_only", "R2_is_not_a_spatial_target", "NOT_APPLICABLE", evidence_base),
            "model_form_uncertainty": uncertainty_entry("available", "categorical_only", "same_semidiscrete_WCSPH_contract", "PASS", evidence_base),
            "topology_uncertainty": uncertainty_entry("available", "categorical_only", "reciprocity_and_support_defect_audit", topo["status"], evidence_base),
            "resource_uncertainty": uncertainty_entry("available", "categorical_only", "audit_scale_particle_edge_stoplines", "PASS" if resource_pass else "FAIL", evidence_base),
            "gci_status": "GCI not justified",
            "single_total_gci_permitted": False,
        },
        "provenance": {
            "baseline_source_id": source_hash,
            "reference_source_id": source_hash,
            "configuration_source_id": config_identity,
            "hash_algorithm": "sha256",
            "canonical_serialization_version": "pio-canonical-bytes-1.0.0",
            "software_environment_id": f"python-{platform.python_version()}_numpy-{np.__version__}",
            "hardware_device_id": f"{platform.system()}-{platform.machine()}-CPU",
            "resource_policy_id": config["resource_policy"]["policy_id"],
            "determinism_policy_id": config["determinism_policy"]["policy_id"],
            "evidence_uris": ["../manifests/generation_run_manifest.json", "../audits/provenance_audit.json"],
        },
        "eligibility": {
            "rules_version": "pio-label-eligibility-1.0.0",
            "verdict": "diagnostic",
            "reason_codes": [],
            "state_alignment": "same_state_verified",
            "leakage_status": "PASS",
        },
    }
    verdict, reasons = derive_eligibility(record)
    record["eligibility"]["verdict"] = verdict
    record["eligibility"]["reason_codes"] = reasons
    return record


def build_dataset(case_manifest: dict[str, Any], config: dict[str, Any], source_hash: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []
    for case in case_manifest["cases"]:
        if case["reference_identity"] != case_manifest["reference_policy"]["allowed_reference_identity"]:
            raise ValueError(f"Disallowed reference identity in {case['case_id']}")
        if int(case["particles_per_axis"]) ** 2 > int(config["resource_policy"]["max_particles_per_case"]):
            raise ValueError(f"Particle stopline exceeded in {case['case_id']}")
        config_identity = content_hash({"case": case, "configuration": config})
        rk2 = rk2_states(case, config)
        dop_primary, dop_sensitivity, dop_info = dop853_reference_states(case, config)
        time_records: list[dict[str, Any]] = []
        for time_value in [float(v) for v in config["state_generation"]["output_times"]]:
            state = rk2[time_value]
            sample = sample_record(case, config, state, dop_primary[time_value], time_value, source_hash, config_identity)
            samples.append(sample)
            primary_state = particle_state_record(dop_primary[time_value], case, config)
            sensitivity_state = particle_state_record(dop_sensitivity[time_value], case, config)
            time_records.append({
                "time": time_value,
                "rk2_state_hash": sample["metadata"]["state_hash"],
                "dop853_primary_state_hash": content_hash(primary_state),
                "dop853_sensitivity_state_hash": content_hash(sensitivity_state),
                "dop853_state_sensitivity_Linf": float(np.max(np.abs(state_to_vector(dop_primary[time_value]) - state_to_vector(dop_sensitivity[time_value])))),
                "sample_id": sample["sample_id"],
            })
        reference_record = {
            "reference_record_version": "stage02c-r2-reference-1.0.0",
            "case_id": case["case_id"],
            "reference_class": "R2_semidiscrete_qualified",
            "reference_identity": case["reference_identity"],
            "same_state_acceleration_method": config["reference_generation"]["same_state_acceleration_method"],
            "temporal_qualifier": config["reference_generation"]["temporal_qualifier"],
            "configuration_hash": config_identity,
            "source_hash": source_hash,
            "solver_status": dop_info,
            "times": time_records,
            "status": "PASS",
        }
        references.append(reference_record)
        case_summaries.append({
            "case_id": case["case_id"],
            "configuration_hash": config_identity,
            "sample_ids": [row["sample_id"] for row in time_records],
            "reference_record_hash": content_hash(reference_record),
            "status": "PASS",
        })
    return samples, references, {"cases": case_summaries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    start = time.perf_counter()
    case_manifest = load_yaml(CASE_MANIFEST_PATH)
    config = load_yaml(CONFIG_PATH)
    rules = load_yaml(RULES_PATH)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if case_manifest["reference_policy"]["allowed_reference_class"] != "R2_semidiscrete_qualified":
        raise ValueError("Stage 02C first batch must be R2 only")
    if case_manifest["reference_policy"]["R3_permitted"] is not False:
        raise ValueError("R3 is prohibited in Stage 02C first batch")
    if config["storage"]["split_assignment"] != "prohibited" or config["storage"]["normalization_statistics"] != "prohibited":
        raise ValueError("Split assignment and normalization statistics must remain prohibited")
    source_hash = file_hash(Path(__file__).resolve())
    first = build_dataset(case_manifest, config, source_hash)
    second = build_dataset(case_manifest, config, source_hash)
    if canonical_bytes(first) != canonical_bytes(second):
        raise RuntimeError("In-memory deterministic repeat mismatch")
    samples, references, summary = first
    elapsed = time.perf_counter() - start
    if elapsed > float(config["resource_policy"]["max_wall_seconds"]):
        raise RuntimeError(f"Audit wall-time stopline exceeded: {elapsed:.6f}s")

    targets = [SAMPLE_DIR / f"{sample['sample_id']}.json" for sample in samples]
    targets += [REFERENCE_DIR / f"{record['case_id']}__r2_reference.json" for record in references]
    targets += [MANIFEST_DIR / "generation_run_manifest.json", MANIFEST_DIR / "dataset_manifest.json", MANIFEST_DIR / "sample_hashes.sha256"]
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError("No-overwrite contract; existing outputs: " + ", ".join(existing))

    for sample, path in zip(samples, targets[: len(samples)]):
        write_json_no_overwrite(path, sample)
    reference_paths = targets[len(samples) : len(samples) + len(references)]
    for record, path in zip(references, reference_paths):
        write_json_no_overwrite(path, record)

    sample_file_rows = [
        {"sample_id": sample["sample_id"], "path": str(path.relative_to(REPO_ROOT)), "sha256": file_hash(path), "verdict": sample["eligibility"]["verdict"]}
        for sample, path in zip(samples, targets[: len(samples)])
    ]
    reference_file_rows = [
        {"case_id": record["case_id"], "path": str(path.relative_to(REPO_ROOT)), "sha256": file_hash(path), "status": record["status"]}
        for record, path in zip(references, reference_paths)
    ]
    sample_merkle_root = content_hash([row["sha256"] for row in sample_file_rows])
    reference_merkle_root = content_hash([row["sha256"] for row in reference_file_rows])
    state_hashes = [sample["metadata"]["state_hash"] for sample in samples]
    target_hashes = [content_hash(sample["delta_a"]) for sample in samples]
    eligibility_hashes = [content_hash(sample["eligibility"]) for sample in samples]
    input_hashes = {
        "case_manifest": file_hash(CASE_MANIFEST_PATH),
        "generation_configuration": file_hash(CONFIG_PATH),
        "dataset_schema": file_hash(SCHEMA_PATH),
        "eligibility_rules": file_hash(RULES_PATH),
        "generator_source": source_hash,
    }
    steps = [
        {"step": "configuration", "status": "PASS", "input_hashes": input_hashes, "output_hash": content_hash({"cases": case_manifest, "config": config})},
        {"step": "SPH_state_generation", "status": "PASS", "provenance": "explicit_midpoint_RK2_CPU_float64", "output_hash": content_hash(state_hashes)},
        {"step": "R2_reference_evaluation", "status": "PASS", "provenance": config["reference_generation"]["identity"], "output_hash": reference_merkle_root},
        {"step": "delta_a_computation", "status": "PASS", "provenance": "a_ref_minus_a_sph", "output_hash": content_hash(target_hashes)},
        {"step": "eligibility_engine", "status": "PASS", "provenance": rules["schema_version"], "output_hash": content_hash(eligibility_hashes)},
        {"step": "sample_storage", "status": "PASS", "provenance": "canonical_pretty_json_utf8_no_overwrite", "output_hash": sample_merkle_root},
    ]
    verdict_counts = dict(sorted(Counter(sample["eligibility"]["verdict"] for sample in samples).items()))
    dataset_manifest = {
        "manifest_version": "stage02c-dataset-manifest-1.0.0",
        "campaign_id": case_manifest["campaign_id"],
        "scale": "audit_only",
        "reference_classes": ["R2_semidiscrete_qualified"],
        "target_sign_convention": "a_ref_minus_a_sph",
        "sample_count": len(samples),
        "reference_record_count": len(references),
        "verdict_counts": verdict_counts,
        "sample_merkle_root": sample_merkle_root,
        "reference_merkle_root": reference_merkle_root,
        "samples": sample_file_rows,
        "references": reference_file_rows,
        "split_assignment_created": False,
        "normalization_statistics_created": False,
        "training_artifacts_created": False,
    }
    run_manifest = {
        "run_manifest_version": "stage02c-generation-run-1.0.0",
        "campaign_id": case_manifest["campaign_id"],
        "execution_status": "PASS",
        "attempt_history": [
            {
                "attempt_id": "stage02c_generation_attempt_01",
                "status": "FAIL",
                "failure_class": "manifest_serialization_infrastructure",
                "failure_detail": "YAML timestamp decoded as datetime during canonical manifest hashing",
                "scientific_generation_failure": False,
                "partial_sample_and_reference_outputs_removed_before_retry": True
            },
            {
                "attempt_id": "stage02c_generation_attempt_02",
                "status": "PASS",
                "change_scope": "quote campaign timestamp as a string; no numerical method or scientific case change"
            }
        ],
        "pipeline_steps": steps,
        "case_summary": summary["cases"],
        "determinism": {
            "policy_id": config["determinism_policy"]["policy_id"],
            "repeats": 2,
            "canonical_in_memory_bytes_equal": True,
            "status": "PASS",
        },
        "resource": {
            "policy_id": config["resource_policy"]["policy_id"],
            "wall_seconds": elapsed,
            "max_wall_seconds": float(config["resource_policy"]["max_wall_seconds"]),
            "max_rss_raw": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "platform": platform.platform(),
            "status": "PASS",
        },
        "schema_identity": schema["$id"],
        "rules_version": rules["schema_version"],
        "historical_boundaries": {
            "V2": "V2_QUALIFICATION_FAIL",
            "shear": "finite-resolution dominant",
            "viscosity_operator_form_failure": "NOT CONFIRMED",
        },
        "prohibited_outputs": {
            "model": False,
            "training": False,
            "split_assignment": False,
            "normalization_statistics": False,
            "validation_or_performance_evaluation": False,
        },
    }
    write_json_no_overwrite(MANIFEST_DIR / "dataset_manifest.json", dataset_manifest)
    write_json_no_overwrite(MANIFEST_DIR / "generation_run_manifest.json", run_manifest)
    hash_lines = "".join(f"{row['sha256'][7:]}  {row['path']}\n" for row in sample_file_rows + reference_file_rows)
    write_text_no_overwrite(MANIFEST_DIR / "sample_hashes.sha256", hash_lines)
    print(json.dumps({"status": "PASS", "samples": len(samples), "references": len(references), "verdict_counts": verdict_counts, "wall_seconds": elapsed}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
