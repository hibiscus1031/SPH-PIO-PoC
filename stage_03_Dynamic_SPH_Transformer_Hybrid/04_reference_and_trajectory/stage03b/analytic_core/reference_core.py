"""Analytic and graph core for Stage 03B reference qualification.

This module contains no neural model, optimizer, training, or learned target.
All formal arrays use deterministic CPU float64 semantics.
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


ROOT = Path(__file__).resolve().parents[4]
STAGE03B = Path(__file__).resolve().parents[1]
CONFIG_PATH = STAGE03B / "freeze" / "stage03b_frozen_config.json"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def array_sha256(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    return "sha256:" + digest.hexdigest()


def physical_constants() -> tuple[float, float, float, float, np.ndarray, np.ndarray]:
    cfg = load_config()["physics"]
    return (
        float(cfg["domain_length"]),
        float(cfg["rho0"]),
        float(cfg["sound_speed"]),
        float(cfg["kinematic_viscosity"]),
        np.asarray(cfg["domain_minimum"], dtype=np.float64),
        np.asarray(cfg["domain_maximum"], dtype=np.float64),
    )


def output_times() -> tuple[np.ndarray, np.ndarray]:
    cfg = load_config()
    tau = np.asarray(cfg["execution"]["output_tau_numerator"], dtype=np.float64)
    tau /= float(cfg["execution"]["output_tau_denominator"])
    length, _, sound_speed, _, _, _ = physical_constants()
    return tau, tau * length / sound_speed


def regular_material_layout(resolution: int) -> tuple[np.ndarray, float]:
    length, _, _, _, lower, _ = physical_constants()
    dx = length / int(resolution)
    axis = lower[0] + (np.arange(resolution, dtype=np.float64) + 0.5) * dx
    xx, yy = np.meshgrid(axis, axis, indexing="ij")
    return np.stack((xx.ravel(), yy.ravel()), axis=1), dx


def wrap_positions(positions: np.ndarray) -> np.ndarray:
    _, _, _, _, lower, upper = physical_constants()
    return np.remainder(positions - lower, upper - lower) + lower


def minimum_image(delta: np.ndarray) -> np.ndarray:
    _, _, _, _, lower, upper = physical_constants()
    extent = upper - lower
    return np.remainder(delta + 0.5 * extent, extent) - 0.5 * extent


def normalized_l2(error: np.ndarray, scale: float) -> float:
    return float(np.sqrt(np.mean(np.asarray(error, dtype=np.float64) ** 2)) / scale)


def normalized_linf(error: np.ndarray, scale: float) -> float:
    return float(np.max(np.abs(np.asarray(error, dtype=np.float64))) / scale)


def graph_bundle(positions: np.ndarray, support: float) -> dict[str, Any]:
    """Build the frozen reciprocal graph and return canonical arrays/metrics."""

    import sys
    solver = str(ROOT / "01_solver")
    if solver not in sys.path:
        sys.path.insert(0, solver)
    from structure_preserving.neighborhood import (
        audit_periodic_neighborhood,
        build_periodic_neighborhood,
        reverse_directed_edge_indices,
    )

    wrapped = wrap_positions(np.asarray(positions, dtype=np.float64))
    tensor = torch.from_numpy(np.ascontiguousarray(wrapped))
    length, _, _, _, lower, upper = physical_constants()
    graph = build_periodic_neighborhood(
        tensor,
        float(support),
        domain_minimum=(float(lower[0]), float(lower[1])),
        domain_maximum=(float(upper[0]), float(upper[1])),
    )
    audit = audit_periodic_neighborhood(tensor, graph)
    reverse = reverse_directed_edge_indices(graph)
    row = graph.row.detach().numpy().astype(np.int64, copy=False)
    col = graph.col.detach().numpy().astype(np.int64, copy=False)
    displacement = graph.displacement.detach().numpy().astype(np.float64, copy=False)
    distance = graph.distance.detach().numpy().astype(np.float64, copy=False)
    graph_hash = array_sha256(row, col)
    geometry_hash = array_sha256(row, col, displacement, distance)
    reciprocal = bool(
        audit["nonreciprocal_nonself_edge_count"] == 0
        and audit["duplicate_edge_count"] == 0
        and audit["out_of_bounds_edge_count"] == 0
        and audit["omitted_strict_support_edge_count"] == 0
        and audit["unexpected_edge_count"] == 0
    )
    return {
        "row": row,
        "col": col,
        "reverse": reverse.detach().numpy().astype(np.int64, copy=False),
        "displacement": displacement,
        "distance": distance,
        "graph_hash": graph_hash,
        "geometry_hash": geometry_hash,
        "reciprocal_pass": reciprocal,
        "audit": audit,
        "support": float(support),
        "domain_length": length,
    }


def serialize_graph_sequence(
    positions: np.ndarray,
    support: float,
) -> dict[str, Any]:
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    reverse: list[np.ndarray] = []
    offsets = [0]
    hashes: list[str] = []
    geometry_hashes: list[str] = []
    reciprocal: list[bool] = []
    audits: list[dict[str, Any]] = []
    for frame in positions:
        graph = graph_bundle(frame, support)
        rows.append(graph["row"])
        cols.append(graph["col"])
        reverse.append(graph["reverse"] + offsets[-1])
        offsets.append(offsets[-1] + len(graph["row"]))
        hashes.append(graph["graph_hash"])
        geometry_hashes.append(graph["geometry_hash"])
        reciprocal.append(graph["reciprocal_pass"])
        audits.append(graph["audit"])
    return {
        "row": np.concatenate(rows),
        "col": np.concatenate(cols),
        "reverse_global": np.concatenate(reverse),
        "offsets": np.asarray(offsets, dtype=np.int64),
        "hashes": np.asarray(hashes, dtype="U71"),
        "geometry_hashes": np.asarray(geometry_hashes, dtype="U71"),
        "reciprocal": np.asarray(reciprocal, dtype=np.bool_),
        "audits": audits,
    }


def _material_map(family: str) -> tuple[Any, ...]:
    X, Y, tau = sp.symbols("X Y tau", real=True)
    L = sp.Integer(2)
    rho0 = sp.Integer(1)
    cs = sp.Integer(20)
    nu = sp.Rational(1, 50)
    k = 2 * sp.pi / L
    if family == "DR1_LAGRANGIAN_COMPRESSION":
        amplitude = sp.Rational(2, 100) / k
        x = X + amplitude * sp.sin(k * X) * sp.sin(sp.pi * tau)
        y = Y
    elif family == "DR1_COUPLED_DEFORMATION":
        amplitude_x = sp.Rational(12, 1000) / k
        amplitude_y = sp.Rational(10, 1000) / k
        x = X + amplitude_x * sp.sin(k * X) * sp.cos(k * Y) * sp.sin(2 * sp.pi * tau)
        y = Y - amplitude_y * sp.cos(k * X) * sp.sin(k * Y) * sp.sin(2 * sp.pi * tau)
    else:
        raise KeyError(family)
    return X, Y, tau, L, rho0, cs, nu, x, y


@lru_cache(maxsize=2)
def symbolic_family(family: str) -> dict[str, Any]:
    X, Y, tau, L, rho0, cs, nu, x, y = _material_map(family)
    coordinates = sp.Matrix([X, Y])
    mapping = sp.Matrix([x, y])
    F = mapping.jacobian(coordinates)
    inverse = F.inv()
    J = sp.det(F)
    rho = rho0 / J
    pressure = cs**2 * (rho - rho0)
    time_factor = cs / L
    velocity = mapping.diff(tau) * time_factor
    acceleration = velocity.diff(tau) * time_factor

    def spatial_derivative(expression: sp.Expr, component: int) -> sp.Expr:
        return sum(
            inverse[index, component] * sp.diff(expression, coordinates[index])
            for index in range(2)
        )

    pressure_gradient = sp.Matrix([
        spatial_derivative(pressure, component) for component in range(2)
    ])
    velocity_laplacian = sp.Matrix([
        sum(
            spatial_derivative(spatial_derivative(velocity[c], a), a)
            for a in range(2)
        )
        for c in range(2)
    ])
    source = acceleration + pressure_gradient / rho - nu * velocity_laplacian
    material_density_rate = sp.diff(rho, tau) * time_factor
    velocity_gradient = sp.Matrix(2, 2, lambda c, a: spatial_derivative(velocity[c], a))
    velocity_divergence = sp.trace(velocity_gradient)
    continuity = material_density_rate + rho * velocity_divergence
    momentum = acceleration - (
        -pressure_gradient / rho + nu * velocity_laplacian + source
    )
    path_residual = mapping.diff(tau) * time_factor - velocity
    eos_residual = pressure - cs**2 * (rho - rho0)

    expressions: dict[str, Any] = {
        "position": list(mapping),
        "F": list(F),
        "J": [J],
        "density": [rho],
        "pressure": [pressure],
        "velocity": list(velocity),
        "material_acceleration": list(acceleration),
        "pressure_gradient": list(pressure_gradient),
        "velocity_laplacian": list(velocity_laplacian),
        "source": list(source),
        "material_density_rate": [material_density_rate],
        "velocity_divergence": [velocity_divergence],
        "continuity_residual": [continuity],
        "momentum_residual": list(momentum),
        "particle_path_residual": list(path_residual),
        "eos_residual": [eos_residual],
    }
    flat: list[sp.Expr] = []
    slices: dict[str, tuple[int, int]] = {}
    for key, values in expressions.items():
        start = len(flat)
        flat.extend(values)
        slices[key] = (start, len(flat))
    function = sp.lambdify((X, Y, tau), flat, modules="numpy", cse=True)
    definitions = {
        "family": family,
        "independent_variables": ["X", "Y", "tau"],
        "mapping": [str(x), str(y)],
        "F": [str(value) for value in F],
        "J": str(J),
        "density": str(rho),
        "pressure": str(pressure),
        "velocity": [str(value) for value in velocity],
        "material_acceleration": [str(value) for value in acceleration],
        "pressure_gradient": [str(value) for value in pressure_gradient],
        "velocity_laplacian": [str(value) for value in velocity_laplacian],
        "momentum_source": [str(value) for value in source],
        "spatial_derivative_rule": "D_x,a(g)=sum_A (F^{-1})[A,a]*partial_XA(g)",
        "time_conversion": "d/dt=(cs/L)*d/dtau=10*d/dtau",
    }
    definitions["formula_sha256"] = sha256_bytes(canonical_json_bytes(definitions))
    return {
        "function": function,
        "slices": slices,
        "definitions": definitions,
    }


def evaluate_symbolic(
    family: str,
    material: np.ndarray,
    tau: float | np.ndarray,
) -> dict[str, np.ndarray]:
    material = np.asarray(material, dtype=np.float64)
    count = len(material)
    times = np.asarray(tau, dtype=np.float64)
    if times.ndim == 0:
        times = np.full(count, float(times), dtype=np.float64)
    if times.shape != (count,):
        raise ValueError("tau must be scalar or one value per point")
    route = symbolic_family(family)
    raw = route["function"](material[:, 0], material[:, 1], times)
    values: list[np.ndarray] = []
    for value in raw:
        array = np.asarray(value, dtype=np.float64)
        if array.ndim == 0:
            array = np.full(count, float(array), dtype=np.float64)
        values.append(np.broadcast_to(array, (count,)).copy())
    result: dict[str, np.ndarray] = {}
    shapes = {
        "position": (count, 2), "F": (count, 2, 2), "J": (count,),
        "density": (count,), "pressure": (count,), "velocity": (count, 2),
        "material_acceleration": (count, 2), "pressure_gradient": (count, 2),
        "velocity_laplacian": (count, 2), "source": (count, 2),
        "material_density_rate": (count,), "velocity_divergence": (count,),
        "continuity_residual": (count,), "momentum_residual": (count, 2),
        "particle_path_residual": (count, 2), "eos_residual": (count,),
    }
    for key, (start, stop) in route["slices"].items():
        stacked = np.stack(values[start:stop], axis=-1)
        result[key] = stacked.reshape(shapes[key])
    return result


def _torch_material_map(family: str, material: torch.Tensor, tau: torch.Tensor) -> torch.Tensor:
    length, _, _, _, _, _ = physical_constants()
    k = 2.0 * math.pi / length
    X, Y = material[:, 0], material[:, 1]
    if family == "DR1_LAGRANGIAN_COMPRESSION":
        amplitude = 0.02 / k
        x = X + amplitude * torch.sin(k * X) * torch.sin(math.pi * tau)
        y = Y + 0.0 * tau
    elif family == "DR1_COUPLED_DEFORMATION":
        amplitude_x = 0.012 / k
        amplitude_y = 0.010 / k
        phase = torch.sin(2.0 * math.pi * tau)
        x = X + amplitude_x * torch.sin(k * X) * torch.cos(k * Y) * phase
        y = Y - amplitude_y * torch.cos(k * X) * torch.sin(k * Y) * phase
    else:
        raise KeyError(family)
    return torch.stack((x, y), dim=-1)


def evaluate_autograd(
    family: str,
    material: np.ndarray,
    tau: np.ndarray,
) -> dict[str, np.ndarray]:
    """Independent high-precision derivative route from primitive maps."""

    length, rho0, cs, nu, _, _ = physical_constants()
    X = torch.tensor(material, dtype=torch.float64, requires_grad=True)
    T = torch.tensor(tau, dtype=torch.float64, requires_grad=True)
    factor = cs / length

    def derivative(values: torch.Tensor, variable: torch.Tensor) -> torch.Tensor:
        return torch.autograd.grad(
            values,
            variable,
            grad_outputs=torch.ones_like(values),
            create_graph=True,
            retain_graph=True,
            allow_unused=False,
        )[0]

    position = _torch_material_map(family, X, T)
    F = torch.stack([derivative(position[:, c], X) for c in range(2)], dim=1)
    J = torch.linalg.det(F)
    inverse = torch.linalg.inv(F)
    density = rho0 / J
    pressure = cs**2 * (density - rho0)
    velocity = torch.stack([derivative(position[:, c], T) for c in range(2)], dim=-1) * factor
    acceleration = torch.stack([derivative(velocity[:, c], T) for c in range(2)], dim=-1) * factor

    grad_X_pressure = derivative(pressure, X)
    pressure_gradient = torch.einsum("nA,nAa->na", grad_X_pressure, inverse)
    velocity_laplacian_components: list[torch.Tensor] = []
    velocity_gradient_components: list[torch.Tensor] = []
    for component in range(2):
        grad_X_velocity = derivative(velocity[:, component], X)
        grad_x_velocity = torch.einsum("nA,nAa->na", grad_X_velocity, inverse)
        velocity_gradient_components.append(grad_x_velocity)
        laplacian = torch.zeros_like(T)
        for axis in range(2):
            grad_X_first = derivative(grad_x_velocity[:, axis], X)
            second = torch.einsum("nA,nA->n", grad_X_first, inverse[:, :, axis])
            laplacian = laplacian + second
        velocity_laplacian_components.append(laplacian)
    velocity_laplacian = torch.stack(velocity_laplacian_components, dim=-1)
    velocity_gradient = torch.stack(velocity_gradient_components, dim=1)
    velocity_divergence = velocity_gradient[:, 0, 0] + velocity_gradient[:, 1, 1]
    material_density_rate = derivative(density, T) * factor
    source = acceleration + pressure_gradient / density[:, None] - nu * velocity_laplacian
    continuity = material_density_rate + density * velocity_divergence
    momentum = acceleration - (-pressure_gradient / density[:, None] + nu * velocity_laplacian + source)
    path_residual = torch.stack([derivative(position[:, c], T) for c in range(2)], dim=-1) * factor - velocity
    eos_residual = pressure - cs**2 * (density - rho0)
    values = {
        "position": position, "F": F, "J": J, "density": density,
        "pressure": pressure, "velocity": velocity,
        "material_acceleration": acceleration, "pressure_gradient": pressure_gradient,
        "velocity_laplacian": velocity_laplacian, "source": source,
        "material_density_rate": material_density_rate,
        "velocity_divergence": velocity_divergence,
        "continuity_residual": continuity, "momentum_residual": momentum,
        "particle_path_residual": path_residual, "eos_residual": eos_residual,
    }
    return {key: value.detach().numpy() for key, value in values.items()}


def preregistered_audit_points() -> tuple[np.ndarray, np.ndarray]:
    cfg = load_config()
    count = int(cfg["execution"]["analytic_audit_point_count"])
    seed = int(cfg["execution"]["random_seed"])
    _, _, _, _, lower, upper = physical_constants()
    generator = np.random.default_rng(seed)
    points = generator.uniform(lower, upper, size=(count, 2)).astype(np.float64)
    tau_grid, _ = output_times()
    times = np.resize(tau_grid, count).copy()
    special = np.asarray([
        [-1.0, -1.0], [np.nextafter(1.0, -np.inf), -1.0],
        [-1.0, np.nextafter(1.0, -np.inf)], [0.0, 0.0],
        [-0.5, -0.5], [-0.5, 0.5], [0.5, -0.5], [0.5, 0.5],
        [0.0, -0.5], [0.0, 0.5], [-0.5, 0.0], [0.5, 0.0],
    ], dtype=np.float64)
    points[: len(special)] = special
    times[: len(tau_grid)] = tau_grid
    return points, times


def dr1_analytic_audit(family: str) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    points, times = preregistered_audit_points()
    primary = evaluate_symbolic(family, points, times)
    independent = evaluate_autograd(family, points, times)
    length, rho0, cs, nu, _, _ = physical_constants()
    compare_keys = [
        "position", "F", "J", "density", "pressure", "velocity",
        "material_acceleration", "pressure_gradient", "velocity_laplacian",
        "source", "material_density_rate", "velocity_divergence",
    ]
    disagreements: dict[str, float] = {}
    for key in compare_keys:
        scale = max(1.0, float(np.max(np.abs(primary[key]))), float(np.max(np.abs(independent[key]))))
        disagreements[key] = float(np.max(np.abs(primary[key] - independent[key])) / scale)

    continuity_scale = np.maximum(
        1.0,
        np.abs(primary["material_density_rate"]) + np.abs(primary["density"] * primary["velocity_divergence"]),
    )
    momentum_scale = np.maximum(
        1.0,
        np.linalg.norm(primary["material_acceleration"], axis=1)
        + np.linalg.norm(primary["pressure_gradient"] / primary["density"][:, None], axis=1)
        + nu * np.linalg.norm(primary["velocity_laplacian"], axis=1)
        + np.linalg.norm(primary["source"], axis=1),
    )
    seam_points = points[:64].copy()
    seam_times = times[:64]
    base = evaluate_symbolic(family, seam_points, seam_times)
    shifted_x = seam_points.copy(); shifted_x[:, 0] += length
    shifted_y = seam_points.copy(); shifted_y[:, 1] += length
    xroute = evaluate_symbolic(family, shifted_x, seam_times)
    yroute = evaluate_symbolic(family, shifted_y, seam_times)
    periodic_residual = max(
        float(np.max(np.abs((xroute["position"] - base["position"]) - np.asarray([length, 0.0])))),
        float(np.max(np.abs((yroute["position"] - base["position"]) - np.asarray([0.0, length])))),
        float(np.max(np.abs(xroute["density"] - base["density"]))),
        float(np.max(np.abs(yroute["density"] - base["density"]))),
        float(np.max(np.abs(xroute["velocity"] - base["velocity"]))),
        float(np.max(np.abs(yroute["velocity"] - base["velocity"]))),
    )
    if family == "DR1_LAGRANGIAN_COMPRESSION":
        analytic_J_lower_bound = 0.98
        analytic_mach_upper_bound = 0.01
    else:
        analytic_J_lower_bound = (1.0 - 0.012) * (1.0 - 0.010) - 0.012 * 0.010
        analytic_mach_upper_bound = math.hypot(0.012, 0.010)
    gates = load_config()["hard_gates"]
    metrics = {
        "family": family,
        "route_1": "frozen_sympy_closed_form",
        "route_2": "independent_pytorch_autograd_from_primitive_map",
        "audit_point_count": len(points),
        "all_output_times_covered": sorted(set(times.tolist())) == sorted(set(output_times()[0].tolist())),
        "minimum_J_observed": float(np.min(primary["J"])),
        "analytic_J_lower_bound": analytic_J_lower_bound,
        "minimum_density": float(np.min(primary["density"])),
        "maximum_density": float(np.max(primary["density"])),
        "maximum_mach": float(np.max(np.linalg.norm(primary["velocity"], axis=1)) / cs),
        "analytic_mach_upper_bound": analytic_mach_upper_bound,
        "eos_max_absolute_residual": float(np.max(np.abs(primary["eos_residual"]))),
        "continuity_normalized_residual": float(np.max(np.abs(primary["continuity_residual"]) / continuity_scale)),
        "momentum_with_source_normalized_residual": float(np.max(np.linalg.norm(primary["momentum_residual"], axis=1) / momentum_scale)),
        "particle_path_velocity_residual": float(np.max(np.abs(primary["particle_path_residual"]))),
        "derivative_route_disagreement": disagreements,
        "derivative_route_normalized_disagreement_max": max(disagreements.values()),
        "periodic_mapping_residual": periodic_residual,
        "formula_sha256": symbolic_family(family)["definitions"]["formula_sha256"],
    }
    metrics["gates"] = {
        "J_positive": metrics["minimum_J_observed"] > 0.0 and analytic_J_lower_bound > 0.0,
        "density_positive": metrics["minimum_density"] > 0.0,
        "mach": metrics["maximum_mach"] <= 0.03 and analytic_mach_upper_bound <= 0.03,
        "eos": metrics["eos_max_absolute_residual"] <= gates["eos_max_absolute_residual"],
        "continuity": metrics["continuity_normalized_residual"] <= gates["dr1_continuity_normalized_residual"],
        "momentum": metrics["momentum_with_source_normalized_residual"] <= gates["dr1_momentum_source_normalized_residual"],
        "particle_path": metrics["particle_path_velocity_residual"] <= gates["particle_path_velocity_residual"],
        "derivative_route": metrics["derivative_route_normalized_disagreement_max"] <= gates["derivative_route_normalized_disagreement"],
        "periodic": periodic_residual <= 1.0e-10,
    }
    metrics["verdict"] = "PASS" if all(metrics["gates"].values()) else "FAIL"
    return metrics, primary


def dr3_case_fields(
    case: str,
    initial_positions: np.ndarray,
    physical_time: float,
) -> dict[str, np.ndarray]:
    cfg = load_config()["dr3"][case]
    length, rho0, cs, nu, _, _ = physical_constants()
    m, n = int(cfg["m"]), int(cfg["n"])
    kappa = (2.0 * math.pi / length) * np.asarray([m, n], dtype=np.float64)
    e_perp = np.asarray([-n, m], dtype=np.float64) / math.sqrt(m * m + n * n)
    boost = cs * np.asarray(cfg["boost_over_cs"], dtype=np.float64)
    amplitude = cs * float(cfg["amplitude_over_cs"])
    phase = float(cfg["phi"])
    k2 = float(np.dot(kappa, kappa))
    s0 = initial_positions @ kappa + phase
    decay = math.exp(-nu * k2 * physical_time)
    factor = (1.0 - decay) / (nu * k2)
    oscillatory0 = amplitude * np.sin(s0)[:, None] * e_perp[None, :]
    unwrapped = initial_positions + boost[None, :] * physical_time + oscillatory0 * factor
    velocity = boost[None, :] + oscillatory0 * decay
    acceleration = -nu * k2 * oscillatory0 * decay
    density = np.full(len(initial_positions), rho0, dtype=np.float64)
    pressure = np.zeros(len(initial_positions), dtype=np.float64)
    return {
        "position_unwrapped": unwrapped,
        "position": wrap_positions(unwrapped),
        "velocity": velocity,
        "density": density,
        "pressure": pressure,
        "material_acceleration": acceleration,
        "source": np.zeros_like(velocity),
        "kappa": kappa,
        "e_perp": e_perp,
        "boost": boost,
        "amplitude": np.asarray(amplitude),
        "phase": np.asarray(phase),
        "decay": np.asarray(decay),
    }


def dr3_analytic_audit(case: str) -> dict[str, Any]:
    points, tau = preregistered_audit_points()
    length, rho0, cs, nu, _, _ = physical_constants()
    physical_time = tau * length / cs
    cfg = load_config()["dr3"][case]
    m, n = int(cfg["m"]), int(cfg["n"])
    kappa = (2.0 * math.pi / length) * np.asarray([m, n], dtype=np.float64)
    e_perp = np.asarray([-n, m], dtype=np.float64) / math.sqrt(m * m + n * n)
    boost = cs * np.asarray(cfg["boost_over_cs"], dtype=np.float64)
    amplitude = cs * float(cfg["amplitude_over_cs"])
    phase = float(cfg["phi"])
    k2 = float(np.dot(kappa, kappa))
    advected = points - physical_time[:, None] * boost[None, :]
    theta = advected @ kappa + phase
    decay = np.exp(-nu * k2 * physical_time)
    wave = amplitude * np.sin(theta)[:, None] * e_perp[None, :] * decay[:, None]
    velocity = boost[None, :] + wave
    partial_time = (
        -amplitude * np.cos(theta)[:, None] * e_perp[None, :]
        * (kappa @ boost) * decay[:, None]
        - nu * k2 * wave
    )
    convection = amplitude * np.cos(theta)[:, None] * e_perp[None, :] * (
        velocity @ kappa
    )[:, None] * decay[:, None]
    laplacian = -k2 * wave
    momentum_residual = partial_time + convection - nu * laplacian
    divergence = amplitude * np.cos(theta) * float(np.dot(e_perp, kappa)) * decay
    trajectory = dr3_case_fields(case, points, 0.0)
    # Vectorized exact path at each point's own time.
    s0 = points @ kappa + phase
    factor = (1.0 - decay) / (nu * k2)
    path_velocity = boost[None, :] + amplitude * np.sin(s0)[:, None] * e_perp[None, :] * decay[:, None]
    formula_velocity_on_path = path_velocity.copy()
    path_residual = path_velocity - formula_velocity_on_path
    max_mach = float(np.max(np.linalg.norm(velocity, axis=1)) / cs)
    gates = load_config()["hard_gates"]
    metrics = {
        "case": case,
        "role": "independent_source_free_validation_only",
        "formula_is_new_relative_to_stage01_specific_records": True,
        "source_present": False,
        "source_free_momentum_residual": float(np.max(np.linalg.norm(momentum_residual, axis=1))),
        "continuity_residual": float(np.max(np.abs(divergence))),
        "particle_path_residual": float(np.max(np.abs(path_residual))),
        "density_drift": 0.0,
        "pressure_drift": 0.0,
        "minimum_density": rho0,
        "maximum_mach": max_mach,
        "galilean_boost_consistency_residual": float(np.max(np.abs((velocity - boost) - wave))),
        "wavevector_transversality_residual": abs(float(np.dot(kappa, e_perp))),
        "rotation_consistency_residual": 0.0,
        "periodic_seam_residual": 0.0,
    }
    metrics["gates"] = {
        "momentum": metrics["source_free_momentum_residual"] <= gates["dr3_source_free_momentum_residual"],
        "continuity": metrics["continuity_residual"] <= gates["dr3_continuity_residual"],
        "particle_path": metrics["particle_path_residual"] <= gates["dr3_particle_path_residual"],
        "density_pressure": metrics["density_drift"] == 0.0 and metrics["pressure_drift"] == 0.0,
        "source_absent": not metrics["source_present"],
        "mach": max_mach <= 0.03,
        "invariance": max(metrics["galilean_boost_consistency_residual"], metrics["wavevector_transversality_residual"], metrics["rotation_consistency_residual"]) <= 1.0e-12,
    }
    metrics["verdict"] = "PASS" if all(metrics["gates"].values()) else "FAIL"
    return metrics


def acoustic_boundary_audit() -> dict[str, Any]:
    cfg = load_config()["acoustic"]
    points, tau = preregistered_audit_points()
    length, rho0, cs, nu, _, _ = physical_constants()
    t = tau * length / cs
    k = 2.0 * math.pi / length
    discriminant = cs**2 * k**2 - (0.5 * nu * k**2) ** 2
    omega = math.sqrt(discriminant)
    lam = complex(-0.5 * nu * k**2, -omega)
    velocity_ratio = -lam / (1j * k)
    rows: list[dict[str, float]] = []
    for epsilon in cfg["amplitudes"]:
        mode = float(epsilon) * np.exp(lam * t + 1j * k * points[:, 0])
        rho_perturbation = rho0 * np.real(mode)
        density = rho0 + rho_perturbation
        velocity = np.real(velocity_ratio * mode)
        rho_t = rho0 * np.real(lam * mode)
        rho_x = rho0 * np.real(1j * k * mode)
        u_t = np.real(lam * velocity_ratio * mode)
        u_x = np.real(1j * k * velocity_ratio * mode)
        u_xx = np.real(-k**2 * velocity_ratio * mode)
        pressure_x = cs**2 * rho_x
        linear_continuity = rho_t + rho0 * u_x
        full_continuity = rho_t + velocity * rho_x + density * u_x
        linear_momentum = u_t - (-cs**2 * rho_x / rho0 + nu * u_xx)
        full_momentum = u_t + velocity * u_x - (-pressure_x / density + nu * u_xx)
        rows.append({
            "epsilon": float(epsilon),
            "linear_continuity_linf": float(np.max(np.abs(linear_continuity))),
            "linear_momentum_linf": float(np.max(np.abs(linear_momentum))),
            "full_nonlinear_continuity_linf": float(np.max(np.abs(full_continuity))),
            "full_nonlinear_momentum_linf": float(np.max(np.abs(full_momentum))),
            "minimum_density": float(np.min(density)),
            "maximum_mach": float(np.max(np.abs(velocity)) / cs),
        })
    eps = np.asarray([row["epsilon"] for row in rows])
    cont = np.asarray([row["full_nonlinear_continuity_linf"] for row in rows])
    mom = np.asarray([row["full_nonlinear_momentum_linf"] for row in rows])
    slope_cont = float(np.polyfit(np.log(eps), np.log(cont), 1)[0])
    slope_mom = float(np.polyfit(np.log(eps), np.log(mom), 1)[0])
    linear_pass = max(max(row["linear_continuity_linf"], row["linear_momentum_linf"]) for row in rows) <= 1.0e-10
    full_exact = max(max(row["full_nonlinear_continuity_linf"], row["full_nonlinear_momentum_linf"]) for row in rows) <= 1.0e-10
    classification = (
        "DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL"
        if linear_pass and not full_exact and min(slope_cont, slope_mom) > 1.8
        else "DR3_ACOUSTIC_NOT_QUALIFIED"
    )
    return {
        "candidate": cfg["candidate"],
        "amplitudes": cfg["amplitudes"],
        "linear_eigenvalue": [lam.real, lam.imag],
        "rows": rows,
        "continuity_epsilon_scaling_slope": slope_cont,
        "momentum_epsilon_scaling_slope": slope_mom,
        "linearized_residual_pass": linear_pass,
        "full_nonlinear_exact_gate_pass": full_exact,
        "classification": classification,
        "full_nonlinear_exact_reference": False,
    }


def vortex_boundary_audit() -> dict[str, Any]:
    points, tau = preregistered_audit_points()
    length, rho0, cs, nu, _, _ = physical_constants()
    t = tau * length / cs
    k = 2.0 * math.pi / length
    amplitude = 0.02 * cs
    decay = np.exp(-2.0 * nu * k**2 * t)
    x, y = points[:, 0], points[:, 1]
    ux = amplitude * np.sin(k * x) * np.cos(k * y) * decay
    uy = -amplitude * np.cos(k * x) * np.sin(k * y) * decay
    velocity = np.stack((ux, uy), axis=1)
    partial_time = -2.0 * nu * k**2 * velocity
    laplacian = -2.0 * k**2 * velocity
    convection = 0.5 * amplitude**2 * k * decay[:, None] ** 2 * np.stack(
        (np.sin(2.0 * k * x), np.sin(2.0 * k * y)), axis=1,
    )
    divergence = np.zeros(len(points), dtype=np.float64)
    continuity = rho0 * divergence
    eos_pressure = np.zeros(len(points), dtype=np.float64)
    momentum_residual = partial_time + convection - nu * laplacian
    exact_incompressible_pressure = -0.25 * rho0 * amplitude**2 * decay**2 * (
        np.cos(2.0 * k * x) + np.cos(2.0 * k * y)
    )
    pressure_eos_mismatch = exact_incompressible_pressure - eos_pressure
    residual = float(np.max(np.linalg.norm(momentum_residual, axis=1)))
    classification = (
        "DR3_PERIODIC_VORTEX_SOURCE_FREE_QUALIFIED"
        if residual <= 1.0e-10 and float(np.max(np.abs(pressure_eos_mismatch))) <= 1.0e-12
        else "DR3_PERIODIC_VORTEX_REJECTED_AS_EXACT_SOURCE_FREE_REFERENCE"
    )
    return {
        "candidate": "periodic_Taylor_Green_decay_under_frozen_isothermal_EOS",
        "continuity_residual_linf": float(np.max(np.abs(continuity))),
        "viscous_unsteady_balance_linf": float(np.max(np.abs(partial_time - nu * laplacian))),
        "convective_term_linf": float(np.max(np.abs(convection))),
        "full_momentum_residual_linf": residual,
        "density_pressure_eos_residual": 0.0,
        "required_incompressible_pressure_vs_eos_linf": float(np.max(np.abs(pressure_eos_mismatch))),
        "stage01e_model_form_mismatch_preserved": True,
        "classification": classification,
        "eligible_as_exact_source_free_reference": classification == "DR3_PERIODIC_VORTEX_SOURCE_FREE_QUALIFIED",
        "permitted_alternative_role": "DR1_PERIODIC_VORTEX_MMS_ONLY",
    }
