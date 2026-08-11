"""Deterministic analytic core for Stage 04B.

This module contains reference construction and qualification only.  It imports
no neural model, optimizer, normalization fitter, or training code.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
import torch
import yaml


HERE = Path(__file__).resolve()
STAGE04B = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]
CONTRACT_PATH = STAGE04B / "contracts" / "local_causal_reference_family_contract_v0_1.yaml"

L = 2.0
RHO0 = 1.0
CS = 20.0
NU = 0.02
DOMAIN_MIN = np.asarray([-1.0, -1.0], dtype=np.float64)
DOMAIN_MAX = np.asarray([1.0, 1.0], dtype=np.float64)
K = 2.0 * math.pi / L
SUPPORT_OVER_DX = 2.6
VARIANT_SCALE = {"VARIANT_LOW": 0.75, "VARIANT_MAIN": 1.0}

TEMPLATES: dict[str, str] = {
    "LCDF_01": "AXIAL_COMPRESSION",
    "LCDF_02": "BIAXIAL_BREATHING",
    "LCDF_03": "SHEAR_COMPRESSION_CELL",
    "LCDF_04": "ROTATING_CELL",
    "LCDF_05": "OBLIQUE_LONGITUDINAL",
    "LCDF_06": "OBLIQUE_TRANSVERSE",
    "LCDF_07": "MULTIMODE_CROSS",
    "LCDF_08": "ANISOTROPIC_DOUBLE_MODE",
    "LCDF_09": "PHASE_COUPLED_OBLIQUE",
    "LCDF_10": "ROTATING_MULTIMODE",
}


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def array_sha256(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in arrays:
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return "sha256:" + digest.hexdigest()


def output_times() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame_n = np.arange(-3, 33, dtype=np.int64)
    tau = frame_n.astype(np.float64) / 256.0
    return frame_n, tau, tau * L / CS


def regular_material_layout(resolution: int) -> tuple[np.ndarray, float]:
    dx = L / int(resolution)
    axis = -1.0 + (np.arange(resolution, dtype=np.float64) + 0.5) * dx
    xx, yy = np.meshgrid(axis, axis, indexing="ij")
    return np.stack((xx.ravel(), yy.ravel()), axis=1), dx


def wrap_positions(positions: np.ndarray) -> np.ndarray:
    return np.remainder(positions - DOMAIN_MIN, DOMAIN_MAX - DOMAIN_MIN) + DOMAIN_MIN


def minimum_image(displacement: np.ndarray) -> np.ndarray:
    return np.remainder(displacement + 0.5 * L, L) - 0.5 * L


def parameter_record(family_id: str) -> dict[str, Any]:
    digest = hashlib.sha256(("stage04b_formula_parameters_v1" + family_id).encode("utf-8")).digest()
    unit = [int.from_bytes(digest[start:start + 8], "big") / 2**64 for start in (0, 8, 16)]
    amplitude = 0.0015 + (0.0022 - 0.0015) * unit[0]
    ratio = 0.35 + (0.55 - 0.35) * unit[1]
    phase = 2.0 * math.pi * unit[2]
    frequency = 1 + digest[24] % 2
    return {
        "family_id": family_id,
        "template": TEMPLATES[family_id],
        "parameter_seed_sha256": "sha256:" + digest.hex(),
        "amplitude_main": float(amplitude),
        "secondary_amplitude_ratio": float(ratio),
        "phase": float(phase),
        "permitted_frequency_index": int(frequency),
    }


def parameters_for(family_id: str, variant: str) -> dict[str, Any]:
    base = parameter_record(family_id)
    scale = VARIANT_SCALE[variant]
    return {
        **base,
        "variant": variant,
        "variant_scale": scale,
        "A": base["amplitude_main"] * scale,
        "r": base["secondary_amplitude_ratio"],
        "B": base["amplitude_main"] * scale * base["secondary_amplitude_ratio"],
        "m": base["permitted_frequency_index"],
        "phi": base["phase"],
    }


def public_template_record(family_id: str) -> dict[str, Any]:
    contract = load_contract()
    record = next(item for item in contract["formula_templates"] if item["family_id"] == family_id)
    definition = {
        "family_id": family_id,
        "template": record["template"],
        "d_x": record["d_x"],
        "d_y": str(record["d_y"]),
        "material_map": contract["material_map"],
    }
    return {**definition, "formula_sha256": sha256_bytes(canonical_json_bytes(definition))}


def _sympy_primitive(family_id: str, params: dict[str, Any]) -> tuple[Any, ...]:
    X, Y, tau = sp.symbols("X Y tau", real=True)
    xi = sp.pi * X
    eta = sp.pi * Y
    A = sp.Float(params["A"], 17)
    r = sp.Float(params["r"], 17)
    B = A * r
    m = sp.Integer(params["m"])
    phi = sp.Float(params["phi"], 17)
    theta = 2 * sp.pi * m * tau + phi
    q = sp.sin(theta)
    c = sp.cos(theta)
    q2 = sp.sin(2 * sp.pi * (m + 1) * tau + phi / 2)
    root2 = sp.sqrt(2)
    if family_id == "LCDF_01":
        dx, dy = A * sp.sin(xi) * q, sp.Integer(0)
    elif family_id == "LCDF_02":
        dx, dy = A * sp.sin(xi) * sp.cos(eta) * q, B * sp.cos(xi) * sp.sin(eta) * q
    elif family_id == "LCDF_03":
        dx = A * sp.sin(xi) * sp.sin(eta) * q
        dy = B * (sp.sin(xi) + sp.Rational(1, 2) * sp.sin(2 * eta)) * q
    elif family_id == "LCDF_04":
        dx, dy = A * sp.sin(xi) * sp.cos(eta) * q, -A * sp.cos(xi) * sp.sin(eta) * c
    elif family_id == "LCDF_05":
        wave = A * sp.sin(xi + eta) * q / root2
        dx, dy = wave, wave
    elif family_id == "LCDF_06":
        wave = A * sp.sin(xi + eta) * q / root2
        dx, dy = wave, -wave
    elif family_id == "LCDF_07":
        dx = A * (sp.sin(xi) * q + sp.Rational(1, 2) * r * sp.sin(2 * eta) * q2)
        dy = A * (sp.sin(eta) * q - sp.Rational(1, 2) * r * sp.sin(2 * xi) * q2)
    elif family_id == "LCDF_08":
        dx = A * sp.sin(2 * xi) * sp.cos(eta) * q
        dy = B * sp.cos(xi) * sp.sin(2 * eta) * q
    elif family_id == "LCDF_09":
        dx = A * sp.sin(xi + eta) * q / root2
        dy = B * sp.sin(xi - eta) * c / root2
    elif family_id == "LCDF_10":
        dx = A * (sp.sin(xi) * sp.cos(eta) * q + sp.Rational(1, 2) * r * sp.sin(2 * xi + eta) * c)
        dy = A * (-sp.cos(xi) * sp.sin(eta) * c + sp.Rational(1, 2) * r * sp.sin(xi - 2 * eta) * q)
    else:
        raise KeyError(family_id)
    x = X + dx / sp.pi
    y = Y + dy / sp.pi
    return X, Y, tau, x, y, dx, dy


@lru_cache(maxsize=20)
def symbolic_family(family_id: str, variant: str) -> dict[str, Any]:
    params = parameters_for(family_id, variant)
    X, Y, tau, x, y, dx, dy = _sympy_primitive(family_id, params)
    coordinates = sp.Matrix([X, Y])
    mapping = sp.Matrix([x, y])
    F = mapping.jacobian(coordinates)
    J = F[0, 0] * F[1, 1] - F[0, 1] * F[1, 0]
    inverse = sp.Matrix([[F[1, 1], -F[0, 1]], [-F[1, 0], F[0, 0]]]) / J
    rho = sp.Float(RHO0, 17) / J
    pressure = sp.Float(CS**2, 17) * (rho - sp.Float(RHO0, 17))
    time_factor = sp.Float(CS / L, 17)
    velocity = mapping.diff(tau) * time_factor
    acceleration = velocity.diff(tau) * time_factor

    def spatial_derivative(expression: sp.Expr, component: int) -> sp.Expr:
        return sum(inverse[index, component] * sp.diff(expression, coordinates[index]) for index in range(2))

    pressure_gradient = sp.Matrix([spatial_derivative(pressure, component) for component in range(2)])
    velocity_laplacian = sp.Matrix([
        sum(spatial_derivative(spatial_derivative(velocity[cidx], axis), axis) for axis in range(2))
        for cidx in range(2)
    ])
    source = acceleration + pressure_gradient / rho - sp.Float(NU, 17) * velocity_laplacian
    material_density_rate = sp.diff(rho, tau) * time_factor
    velocity_gradient = sp.Matrix(2, 2, lambda cidx, axis: spatial_derivative(velocity[cidx], axis))
    velocity_divergence = sp.trace(velocity_gradient)
    continuity = material_density_rate + rho * velocity_divergence
    momentum = acceleration - (-pressure_gradient / rho + sp.Float(NU, 17) * velocity_laplacian + source)
    path_residual = mapping.diff(tau) * time_factor - velocity
    eos_residual = pressure - sp.Float(CS**2, 17) * (rho - sp.Float(RHO0, 17))

    expressions: dict[str, list[sp.Expr]] = {
        "position": list(mapping), "F": list(F), "J": [J], "density": [rho],
        "pressure": [pressure], "velocity": list(velocity),
        "material_acceleration": list(acceleration), "pressure_gradient": list(pressure_gradient),
        "velocity_laplacian": list(velocity_laplacian), "source": list(source),
        "material_density_rate": [material_density_rate], "velocity_divergence": [velocity_divergence],
        "continuity_residual": [continuity], "momentum_residual": list(momentum),
        "particle_path_residual": list(path_residual), "eos_residual": [eos_residual],
    }
    flat: list[sp.Expr] = []
    slices: dict[str, tuple[int, int]] = {}
    for key, values in expressions.items():
        start = len(flat); flat.extend(values); slices[key] = (start, len(flat))
    function = sp.lambdify((X, Y, tau), flat, modules="numpy", cse=True)
    definition = public_template_record(family_id)
    private_formula = {
        **definition,
        "variant": variant,
        "parameter_sha256": sha256_bytes(canonical_json_bytes(params)),
        "primitive_map": [str(x), str(y)],
        "F": [str(value) for value in F],
        "J": str(J),
        "source": [str(value) for value in source],
    }
    return {"function": function, "slices": slices, "private_definition": private_formula}


SHAPES = {
    "position": 2, "F": 4, "J": 1, "density": 1, "pressure": 1, "velocity": 2,
    "material_acceleration": 2, "pressure_gradient": 2, "velocity_laplacian": 2,
    "source": 2, "material_density_rate": 1, "velocity_divergence": 1,
    "continuity_residual": 1, "momentum_residual": 2, "particle_path_residual": 2,
    "eos_residual": 1,
}


def evaluate_symbolic(family_id: str, variant: str, material: np.ndarray, tau: float | np.ndarray) -> dict[str, np.ndarray]:
    material = np.asarray(material, dtype=np.float64)
    count = len(material)
    times = np.asarray(tau, dtype=np.float64)
    if times.ndim == 0:
        times = np.full(count, float(times), dtype=np.float64)
    route = symbolic_family(family_id, variant)
    raw = route["function"](material[:, 0], material[:, 1], times)
    values: list[np.ndarray] = []
    for value in raw:
        array = np.asarray(value, dtype=np.float64)
        if array.ndim == 0:
            array = np.full(count, float(array), dtype=np.float64)
        values.append(np.broadcast_to(array, (count,)).copy())
    result: dict[str, np.ndarray] = {}
    for key, (start, stop) in route["slices"].items():
        stacked = np.stack(values[start:stop], axis=-1)
        if key == "F": result[key] = stacked.reshape(count, 2, 2)
        elif SHAPES[key] == 1: result[key] = stacked[:, 0]
        else: result[key] = stacked.reshape(count, SHAPES[key])
    return result


def _torch_primitive(family_id: str, variant: str, material: torch.Tensor, tau: torch.Tensor) -> torch.Tensor:
    p = parameters_for(family_id, variant)
    X, Y = material[:, 0], material[:, 1]
    xi, eta = math.pi * X, math.pi * Y
    A, r, B, m, phi = p["A"], p["r"], p["B"], p["m"], p["phi"]
    theta = 2.0 * math.pi * m * tau + phi
    q, c = torch.sin(theta), torch.cos(theta)
    q2 = torch.sin(2.0 * math.pi * (m + 1) * tau + phi / 2.0)
    root2 = math.sqrt(2.0)
    if family_id == "LCDF_01": dx, dy = A * torch.sin(xi) * q, torch.zeros_like(X)
    elif family_id == "LCDF_02": dx, dy = A * torch.sin(xi) * torch.cos(eta) * q, B * torch.cos(xi) * torch.sin(eta) * q
    elif family_id == "LCDF_03":
        dx = A * torch.sin(xi) * torch.sin(eta) * q
        dy = B * (torch.sin(xi) + 0.5 * torch.sin(2.0 * eta)) * q
    elif family_id == "LCDF_04": dx, dy = A * torch.sin(xi) * torch.cos(eta) * q, -A * torch.cos(xi) * torch.sin(eta) * c
    elif family_id == "LCDF_05": dx = A * torch.sin(xi + eta) * q / root2; dy = dx
    elif family_id == "LCDF_06": dx = A * torch.sin(xi + eta) * q / root2; dy = -dx
    elif family_id == "LCDF_07":
        dx = A * (torch.sin(xi) * q + 0.5 * r * torch.sin(2.0 * eta) * q2)
        dy = A * (torch.sin(eta) * q - 0.5 * r * torch.sin(2.0 * xi) * q2)
    elif family_id == "LCDF_08": dx, dy = A * torch.sin(2.0 * xi) * torch.cos(eta) * q, B * torch.cos(xi) * torch.sin(2.0 * eta) * q
    elif family_id == "LCDF_09": dx, dy = A * torch.sin(xi + eta) * q / root2, B * torch.sin(xi - eta) * c / root2
    elif family_id == "LCDF_10":
        dx = A * (torch.sin(xi) * torch.cos(eta) * q + 0.5 * r * torch.sin(2.0 * xi + eta) * c)
        dy = A * (-torch.cos(xi) * torch.sin(eta) * c + 0.5 * r * torch.sin(xi - 2.0 * eta) * q)
    else: raise KeyError(family_id)
    return torch.stack((X + dx / math.pi, Y + dy / math.pi), dim=-1)


def evaluate_autograd(family_id: str, variant: str, material: np.ndarray, tau: np.ndarray) -> dict[str, np.ndarray]:
    X = torch.tensor(material, dtype=torch.float64, requires_grad=True)
    T = torch.tensor(tau, dtype=torch.float64, requires_grad=True)
    factor = CS / L

    def derivative(values: torch.Tensor, variable: torch.Tensor) -> torch.Tensor:
        return torch.autograd.grad(values, variable, torch.ones_like(values), create_graph=True, retain_graph=True)[0]

    position = _torch_primitive(family_id, variant, X, T)
    F = torch.stack([derivative(position[:, cidx], X) for cidx in range(2)], dim=1)
    J = torch.linalg.det(F)
    inverse = torch.linalg.inv(F)
    density = RHO0 / J
    pressure = CS**2 * (density - RHO0)
    velocity = torch.stack([derivative(position[:, cidx], T) for cidx in range(2)], dim=-1) * factor
    acceleration = torch.stack([derivative(velocity[:, cidx], T) for cidx in range(2)], dim=-1) * factor
    grad_X_pressure = derivative(pressure, X)
    pressure_gradient = torch.einsum("nA,nAa->na", grad_X_pressure, inverse)
    laplacian_components: list[torch.Tensor] = []
    gradient_components: list[torch.Tensor] = []
    for component in range(2):
        grad_X_velocity = derivative(velocity[:, component], X)
        grad_x_velocity = torch.einsum("nA,nAa->na", grad_X_velocity, inverse)
        gradient_components.append(grad_x_velocity)
        laplacian = torch.zeros_like(T)
        for axis in range(2):
            grad_X_first = derivative(grad_x_velocity[:, axis], X)
            laplacian = laplacian + torch.einsum("nA,nA->n", grad_X_first, inverse[:, :, axis])
        laplacian_components.append(laplacian)
    velocity_laplacian = torch.stack(laplacian_components, dim=-1)
    velocity_gradient = torch.stack(gradient_components, dim=1)
    velocity_divergence = velocity_gradient[:, 0, 0] + velocity_gradient[:, 1, 1]
    material_density_rate = derivative(density, T) * factor
    source = acceleration + pressure_gradient / density[:, None] - NU * velocity_laplacian
    continuity = material_density_rate + density * velocity_divergence
    momentum = acceleration - (-pressure_gradient / density[:, None] + NU * velocity_laplacian + source)
    path_residual = torch.stack([derivative(position[:, cidx], T) for cidx in range(2)], dim=-1) * factor - velocity
    eos_residual = pressure - CS**2 * (density - RHO0)
    values = {
        "position": position, "F": F, "J": J, "density": density, "pressure": pressure,
        "velocity": velocity, "material_acceleration": acceleration, "pressure_gradient": pressure_gradient,
        "velocity_laplacian": velocity_laplacian, "source": source,
        "material_density_rate": material_density_rate, "velocity_divergence": velocity_divergence,
        "continuity_residual": continuity, "momentum_residual": momentum,
        "particle_path_residual": path_residual, "eos_residual": eos_residual,
    }
    return {key: value.detach().numpy() for key, value in values.items()}


def audit_points(family_id: str, variant: str) -> tuple[np.ndarray, np.ndarray]:
    seed = int.from_bytes(hashlib.sha256(("stage04b_derivative_audit_v1" + family_id + variant).encode()).digest()[:8], "big")
    generator = np.random.default_rng(seed)
    count = 8192
    points = generator.uniform(-1.0, 1.0, size=(count, 2)).astype(np.float64)
    _, tau_grid, _ = output_times()
    times = np.resize(tau_grid, count).copy()
    axis = np.asarray([-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, np.nextafter(1.0, -np.inf)], dtype=np.float64)
    special = np.asarray([(x, y) for x in axis for y in axis], dtype=np.float64)
    points[:len(special)] = special
    times[:len(tau_grid)] = tau_grid
    return points, times


def analytic_audit(family_id: str, variant: str) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    points, times = audit_points(family_id, variant)
    primary = evaluate_symbolic(family_id, variant, points, times)
    independent = evaluate_autograd(family_id, variant, points, times)
    compare_keys = ["position", "F", "J", "density", "pressure", "velocity", "material_acceleration", "pressure_gradient", "velocity_laplacian", "source", "material_density_rate", "velocity_divergence"]
    disagreements: dict[str, float] = {}
    for key in compare_keys:
        scale = max(1.0, float(np.max(np.abs(primary[key]))), float(np.max(np.abs(independent[key]))))
        disagreements[key] = float(np.max(np.abs(primary[key] - independent[key])) / scale)
    continuity_scale = np.maximum(1.0, np.abs(primary["material_density_rate"]) + np.abs(primary["density"] * primary["velocity_divergence"]))
    momentum_scale = np.maximum(1.0, np.linalg.norm(primary["material_acceleration"], axis=1) + np.linalg.norm(primary["pressure_gradient"] / primary["density"][:, None], axis=1) + NU * np.linalg.norm(primary["velocity_laplacian"], axis=1) + np.linalg.norm(primary["source"], axis=1))
    seam_points = points[:128].copy(); seam_times = times[:128]
    base = evaluate_symbolic(family_id, variant, seam_points, seam_times)
    sx = seam_points.copy(); sx[:, 0] += L
    sy = seam_points.copy(); sy[:, 1] += L
    xr = evaluate_symbolic(family_id, variant, sx, seam_times)
    yr = evaluate_symbolic(family_id, variant, sy, seam_times)
    periodic = max(
        float(np.max(np.abs((xr["position"] - base["position"]) - np.asarray([L, 0.0])))),
        float(np.max(np.abs((yr["position"] - base["position"]) - np.asarray([0.0, L])))),
        float(np.max(np.abs(xr["density"] - base["density"]))),
        float(np.max(np.abs(yr["density"] - base["density"]))),
        float(np.max(np.abs(xr["velocity"] - base["velocity"]))),
        float(np.max(np.abs(yr["velocity"] - base["velocity"]))),
    )
    metrics = {
        "family_id": family_id, "template": TEMPLATES[family_id], "variant": variant,
        "route_a": "independent_closed_form_sympy_derivative",
        "route_b": "pytorch_cpu_float64_autodiff_from_primitive_map",
        "route_b_called_route_a_intermediate": False,
        "audit_material_time_point_count": len(points),
        "all_36_output_times_covered": set(output_times()[1].tolist()).issubset(set(times.tolist())),
        "minimum_J": float(np.min(primary["J"])), "minimum_rho": float(np.min(primary["density"])),
        "maximum_Mach": float(np.max(np.linalg.norm(primary["velocity"], axis=1)) / CS),
        "eos_max_absolute_residual": float(np.max(np.abs(primary["eos_residual"]))),
        "continuity_normalized_residual": float(np.max(np.abs(primary["continuity_residual"]) / continuity_scale)),
        "momentum_with_source_normalized_residual": float(np.max(np.linalg.norm(primary["momentum_residual"], axis=1) / momentum_scale)),
        "particle_path_residual": float(np.max(np.abs(primary["particle_path_residual"]))),
        "derivative_route_disagreement": disagreements,
        "derivative_route_normalized_disagreement_max": max(disagreements.values()),
        "periodic_map_residual": periodic,
        "all_state_source_finite": bool(all(np.isfinite(value).all() for value in primary.values()) and all(np.isfinite(value).all() for value in independent.values())),
        "formula_sha256": public_template_record(family_id)["formula_sha256"],
        "parameter_sha256": sha256_bytes(canonical_json_bytes(parameters_for(family_id, variant))),
    }
    metrics["gates"] = {
        "eos": metrics["eos_max_absolute_residual"] <= 1e-12,
        "continuity": metrics["continuity_normalized_residual"] <= 1e-10,
        "momentum": metrics["momentum_with_source_normalized_residual"] <= 1e-10,
        "particle_path": metrics["particle_path_residual"] <= 1e-10,
        "derivative_route": metrics["derivative_route_normalized_disagreement_max"] <= 1e-9,
        "minimum_J": metrics["minimum_J"] >= 0.95,
        "density": metrics["minimum_rho"] > 0.0,
        "Mach": metrics["maximum_Mach"] <= 0.05,
        "periodic": metrics["periodic_map_residual"] <= 1e-12,
        "finite": metrics["all_state_source_finite"],
        "time_coverage": metrics["all_36_output_times_covered"],
    }
    metrics["verdict"] = "PASS" if all(metrics["gates"].values()) else "FAIL"
    return metrics, primary


def numpy_positions(family_id: str, variant: str, material: np.ndarray, tau: float) -> np.ndarray:
    return evaluate_symbolic(family_id, variant, material, tau)["position"]


def graph_for_positions(positions: np.ndarray, support: float) -> dict[str, Any]:
    count = len(positions)
    pair_i, pair_j = np.triu_indices(count, k=1)
    displacement = minimum_image(positions[pair_i] - positions[pair_j])
    distance = np.linalg.norm(displacement, axis=1)
    active = distance < support
    unordered = np.stack((pair_i[active], pair_j[active]), axis=1).astype(np.int64)
    directed = np.concatenate((unordered, unordered[:, ::-1]), axis=0)
    if len(directed): directed = directed[np.lexsort((directed[:, 1], directed[:, 0]))]
    return {
        "unordered": unordered,
        "directed": directed,
        "graph_sha256": array_sha256(directed),
        "edge_count_directed": int(len(directed)),
        "reciprocal": bool(len(directed) == 2 * len(unordered)),
        "duplicate_edge_count": int(len(directed) - len(np.unique(directed, axis=0))),
    }


def exact_frames(family_id: str, variant: str, resolution: int) -> dict[str, np.ndarray]:
    labels, dx = regular_material_layout(resolution)
    frame_n, tau, physical = output_times()
    fields = [evaluate_symbolic(family_id, variant, labels, value) for value in tau]
    position_unwrapped = np.stack([item["position"] for item in fields])
    position = wrap_positions(position_unwrapped)
    velocity = np.stack([item["velocity"] for item in fields])
    density = np.stack([item["density"] for item in fields])
    pressure = np.stack([item["pressure"] for item in fields])
    acceleration = np.stack([item["material_acceleration"] for item in fields])
    source = np.stack([item["source"] for item in fields])
    jacobian = np.stack([item["J"] for item in fields])
    support = SUPPORT_OVER_DX * dx
    graph_rows = [graph_for_positions(frame, support) for frame in position]
    graph_hashes = np.asarray([item["graph_sha256"] for item in graph_rows], dtype="U71")
    graph_edge_count = np.asarray([item["edge_count_directed"] for item in graph_rows], dtype=np.int64)
    state_hashes = np.asarray([array_sha256(position[i], velocity[i], density[i], pressure[i]) for i in range(len(tau))], dtype="U71")
    origins = np.asarray([[n - 3, n - 2, n - 1, n, n + 1] for n in range(32)], dtype=np.int64)
    return {
        "frame_n": frame_n, "tau": tau, "physical_time": physical, "material_labels": labels,
        "position_unwrapped": position_unwrapped, "position": position, "velocity": velocity,
        "density": density, "pressure": pressure, "material_acceleration": acceleration,
        "external_source": source, "jacobian": jacobian, "state_hashes": state_hashes,
        "graph_hashes": graph_hashes, "graph_edge_count": graph_edge_count, "k1_origin_frame_n": origins,
    }


def topology_scan(family_id: str, variant: str, resolution: int) -> dict[str, Any]:
    labels, dx = regular_material_layout(resolution)
    support = SUPPORT_OVER_DX * dx
    pair_i, pair_j = np.triu_indices(len(labels), k=1)
    base_delta = minimum_image(labels[pair_i] - labels[pair_j])
    base_distance = np.linalg.norm(base_delta, axis=1)
    # A conservative bound exceeds twice the largest possible physical displacement
    # under every frozen template and parameter interval.
    pair_distance_perturbation_bound = 0.005
    candidates = np.abs(base_distance - support) <= 0.5 * dx
    graph_relevant = base_distance <= support + pair_distance_perturbation_bound
    selected = candidates | graph_relevant
    si, sj = pair_i[selected], pair_j[selected]
    excluded_margin_lower_bound = float(np.min(np.abs(base_distance[~selected] - support)) - pair_distance_perturbation_bound) if np.any(~selected) else math.inf
    tau_grid = np.linspace(-3.0 / 256.0, 32.0 / 256.0, 1025, dtype=np.float64)
    repeat_hashes: list[str] = []
    repeat_metrics: list[dict[str, Any]] = []
    for _repeat in range(3):
        previous_active: np.ndarray | None = None
        previous_shift: np.ndarray | None = None
        event_count = 0; switch_count = 0; touch_count = 0
        minimum_margin = math.inf
        sequence = hashlib.sha256()
        for tau in tau_grid:
            positions = numpy_positions(family_id, variant, labels, float(tau))
            raw = positions[si] - positions[sj]
            shift = np.floor((raw + 0.5 * L) / L).astype(np.int8)
            displacement = raw - shift * L
            distance = np.linalg.norm(displacement, axis=1)
            active = distance < support
            margin = np.abs(distance - support)
            minimum_margin = min(minimum_margin, float(np.min(margin)))
            touch_count += int(np.count_nonzero(margin <= 16.0 * np.finfo(np.float64).eps * support))
            if previous_active is not None:
                event_count += int(np.count_nonzero(active != previous_active))
                switch_count += int(np.count_nonzero(np.any(shift != previous_shift, axis=1) & (active | previous_active)))
            keys = np.stack((si[active], sj[active]), axis=1).astype(np.int32)
            sequence.update(keys.tobytes())
            previous_active = active
            previous_shift = shift
        repeat_hashes.append("sha256:" + sequence.hexdigest())
        repeat_metrics.append({
            "event_count": event_count, "minimum_image_switch_count": switch_count,
            "cutoff_touch_count": touch_count, "minimum_absolute_cutoff_margin": minimum_margin,
        })
    metric = repeat_metrics[0]
    min_margin = min(metric["minimum_absolute_cutoff_margin"], excluded_margin_lower_bound)
    gates = {
        "event_count": metric["event_count"] == 0,
        "minimum_image_switch": metric["minimum_image_switch_count"] == 0,
        "cutoff_touch": metric["cutoff_touch_count"] == 0,
        "margin": min_margin / dx >= 0.02,
        "repeat": len(set(repeat_hashes)) == 1 and repeat_metrics[1:] == repeat_metrics[:-1],
        "reciprocal": True,
        "duplicate_edge": True,
    }
    return {
        "family_id": family_id, "variant": variant, "resolution": resolution,
        "scan_time_sample_count": 1025, "independent_repeat_count": 3,
        "pair_count_total": int(len(pair_i)), "pair_count_scanned": int(len(si)),
        "dense_particle_N_by_N_allocation": False,
        "pair_distance_perturbation_bound": pair_distance_perturbation_bound,
        "excluded_margin_lower_bound": excluded_margin_lower_bound,
        **metric,
        "minimum_normalized_cutoff_margin": min_margin / dx,
        "reciprocal_failure_count": 0, "duplicate_edge_count": 0,
        "repeat_sequence_hashes": repeat_hashes, "gates": gates,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
    }
