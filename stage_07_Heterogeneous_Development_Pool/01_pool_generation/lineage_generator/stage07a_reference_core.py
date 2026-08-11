"""Deterministic heterogeneous reference construction for Stage07A only.

No neural model, optimizer, training, normalization fit, rollout, checkpoint,
or performance-evaluation code is imported here.
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
POOL = HERE.parents[1]
STAGE07 = HERE.parents[2]
ROOT = HERE.parents[3]
CONTRACT_PATH = POOL / "contracts/heterogeneous_lineage_generator_v0_1.yaml"
ROLE_PATH = POOL / "role_assignment/preregistered_role_assignment.json"

L = 2.0
RHO0 = 1.0
CS = 20.0
NU = 0.02
SUPPORT_OVER_DX = 2.6
DOMAIN_MIN = np.asarray([-1.0, -1.0], dtype=np.float64)
DOMAIN_MAX = np.asarray([1.0, 1.0], dtype=np.float64)
VARIANT_SCALE = {"LOW": 0.75, "MAIN": 1.0}
LINEAGES = tuple(f"HET_S{s}_{i:02d}" for s in range(1, 5) for i in range(1, 4))

WAVEVECTORS = {
    1: [(1, 0), (1, 1)],
    2: [(1, 0), (0, 1), (2, 1)],
    3: [(1, 1), (1, -1), (0, 1)],
    4: [(1, 0), (0, 1), (1, 1), (2, -1)],
}
THETA_INTERVALS = {
    1: [(0.0, math.radians(10)), (math.radians(80), math.pi / 2)],
    2: [(math.radians(15), math.radians(35)), (math.radians(55), math.radians(75)), (math.radians(25), math.radians(65))],
    3: [(0.0, math.radians(30)), (math.radians(60), math.pi / 2), (math.radians(20), math.radians(70))],
    4: [(0.0, math.radians(20)), (math.radians(70), math.pi / 2), (math.radians(20), math.radians(50)), (math.radians(40), math.radians(70))],
}
TEMPORAL = {
    1: [("sin", 1, False), ("cos", 1, False)],
    2: [("sin", 1, False), ("cos", 1, False), ("sin", 2, False)],
    3: [("sin", 1, False), ("sin", 2, False), ("cos", 3, False)],
    4: [("sin", 2, True), ("cos", 2, True), ("sin", 1, False), ("cos", 3, False)],
}
ANISOTROPY = {1: [1.0, 1.0], 2: [1.0, 1.0, 1.0], 3: [1.0, 1.0, 1.0], 4: [1.0, 0.55, 0.8, 0.35]}


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def role_map() -> dict[str, str]:
    value = json.loads(ROLE_PATH.read_text(encoding="utf-8"))
    return {row["lineage_id"]: row["role"] for row in value["assignments"]}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def array_sha(*values: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in values:
        array = np.ascontiguousarray(value)
        digest.update(str(array.dtype).encode("ascii")); digest.update(b"\0")
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes()); digest.update(array.tobytes())
    return "sha256:" + digest.hexdigest()


def stratum_for(lineage_id: str) -> int:
    if lineage_id not in LINEAGES:
        raise KeyError(lineage_id)
    return int(lineage_id.split("_")[1][1:])


def _seed(lineage_id: str) -> bytes:
    return hashlib.sha256(("stage07a_heterogeneous_formula_v1" + lineage_id).encode("utf-8")).digest()


def _unit(seed: bytes, index: int) -> float:
    block = hashlib.sha256(seed + index.to_bytes(4, "big")).digest()
    return int.from_bytes(block[:8], "big") / 2**64


def parameter_record(lineage_id: str) -> dict[str, Any]:
    s = stratum_for(lineage_id)
    seed = _seed(lineage_id)
    count = len(WAVEVECTORS[s])
    amplitude_total = 0.006 + 0.004 * _unit(seed, 0)
    raw = np.asarray([(0.25 + 0.75 * _unit(seed, 1 + i)) * ANISOTROPY[s][i] for i in range(count)], dtype=np.float64)
    amplitudes = amplitude_total * raw / np.sum(raw)
    theta = [lo + (hi - lo) * _unit(seed, 16 + i) for i, (lo, hi) in enumerate(THETA_INTERVALS[s])]
    spatial_phase = [2.0 * math.pi * _unit(seed, 32 + i) for i in range(count)]
    temporal_phase = [0.0 if rotating else 2.0 * math.pi * _unit(seed, 48 + i) for i, (_kind, _freq, rotating) in enumerate(TEMPORAL[s])]
    if s == 3:
        # Deterministic, preregistered separation map; no result is consulted.
        for i in range(1, count):
            if abs(math.atan2(math.sin(temporal_phase[i] - temporal_phase[0]), math.cos(temporal_phase[i] - temporal_phase[0]))) < math.pi / 12:
                temporal_phase[i] = (temporal_phase[i] + math.pi / 3) % (2.0 * math.pi)
    modes = []
    for i, ((p, q), (kind, frequency, rotating)) in enumerate(zip(WAVEVECTORS[s], TEMPORAL[s])):
        modes.append({
            "mode_index": i, "p": p, "q": q, "A_main": float(amplitudes[i]),
            "theta": float(theta[i]), "phi": float(spatial_phase[i]), "temporal_kind": kind,
            "temporal_frequency_index": frequency, "psi": float(temporal_phase[i]),
            "rotating_quadrature_member": rotating,
        })
    return {
        "lineage_id": lineage_id, "stratum": f"H{s}", "seed_sha256": "sha256:" + seed.hex(),
        "amplitude_total_main": float(amplitude_total), "mode_count": count, "modes": modes,
        "mapping_algorithm": "sha256_counter_expansion_interval_map_v1",
    }


def parameters_for(lineage_id: str, variant: str) -> dict[str, Any]:
    if variant not in VARIANT_SCALE:
        raise KeyError(variant)
    base = parameter_record(lineage_id)
    scale = VARIANT_SCALE[variant]
    return {
        **base, "variant": variant, "variant_scale": scale,
        "amplitude_total": base["amplitude_total_main"] * scale,
        "modes": [{**mode, "A": mode["A_main"] * scale} for mode in base["modes"]],
    }


def formula_definition(lineage_id: str) -> dict[str, Any]:
    base = parameter_record(lineage_id)
    definition = {
        "lineage_id": lineage_id, "stratum": base["stratum"], "mode_count": base["mode_count"],
        "material_map": "x=(X,Y)+sum A_m(cos(theta_m)e_L+sin(theta_m)e_T)sin(p_m xi+q_m eta+phi_m)g_m(tau)",
        "wavevectors": [[row["p"], row["q"]] for row in base["modes"]],
        "generator_seed_sha256": base["seed_sha256"],
    }
    return {**definition, "formula_sha256": sha_bytes(canonical_bytes({**definition, "parameters": base}))}


def output_times() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame_n = np.arange(-3, 33, dtype=np.int64)
    tau = frame_n.astype(np.float64) / 256.0
    return frame_n, tau, tau * L / CS


def regular_material_layout(resolution: int) -> tuple[np.ndarray, float]:
    dx = L / resolution
    axis = -1.0 + (np.arange(resolution, dtype=np.float64) + 0.5) * dx
    xx, yy = np.meshgrid(axis, axis, indexing="ij")
    return np.stack((xx.ravel(), yy.ravel()), axis=1), dx


def wrap_positions(position: np.ndarray) -> np.ndarray:
    return np.remainder(position - DOMAIN_MIN, DOMAIN_MAX - DOMAIN_MIN) + DOMAIN_MIN


def minimum_image(displacement: np.ndarray) -> np.ndarray:
    return np.remainder(displacement + 0.5 * L, L) - 0.5 * L


def _sympy_primitive(lineage_id: str, variant: str) -> tuple[Any, ...]:
    params = parameters_for(lineage_id, variant)
    X, Y, tau = sp.symbols("X Y tau", real=True)
    xi, eta = sp.pi * X, sp.pi * Y
    dx, dy = sp.Integer(0), sp.Integer(0)
    for mode in params["modes"]:
        p, q = mode["p"], mode["q"]
        norm = sp.sqrt(p * p + q * q)
        theta = sp.Float(mode["theta"], 17)
        direction_x = sp.cos(theta) * p / norm + sp.sin(theta) * (-q) / norm
        direction_y = sp.cos(theta) * q / norm + sp.sin(theta) * p / norm
        phase = p * xi + q * eta + sp.Float(mode["phi"], 17)
        angle = sp.Integer(mode["temporal_frequency_index"]) * sp.pi * tau + sp.Float(mode["psi"], 17)
        temporal = sp.sin(angle) if mode["temporal_kind"] == "sin" else sp.cos(angle)
        amplitude = sp.Float(mode["A"], 17)
        dx += amplitude * direction_x * sp.sin(phase) * temporal
        dy += amplitude * direction_y * sp.sin(phase) * temporal
    return X, Y, tau, X + dx, Y + dy


@lru_cache(maxsize=24)
def symbolic_family(lineage_id: str, variant: str) -> dict[str, Any]:
    X, Y, tau, x, y = _sympy_primitive(lineage_id, variant)
    coordinates = (X, Y); mapping = (x, y)
    # SymPy differentiates only the primitive trigonometric map. Physical-field
    # tensor algebra is then evaluated explicitly in float64, avoiding symbolic
    # inverse-map expression explosion while remaining a closed-form/SymPy route.
    expressions: list[sp.Expr] = []
    expressions.extend(mapping)
    expressions.extend(sp.diff(mapping[c], coordinates[a]) for c in range(2) for a in range(2))
    expressions.extend(sp.diff(mapping[c], coordinates[a], coordinates[b]) for c in range(2) for a in range(2) for b in range(2))
    expressions.extend(sp.diff(mapping[c], tau) for c in range(2))
    expressions.extend(sp.diff(mapping[c], tau, 2) for c in range(2))
    expressions.extend(sp.diff(mapping[c], tau, coordinates[a]) for c in range(2) for a in range(2))
    expressions.extend(sp.diff(mapping[c], tau, coordinates[a], coordinates[b]) for c in range(2) for a in range(2) for b in range(2))
    return {"function": sp.lambdify((X, Y, tau), expressions, modules="numpy", cse=True)}


def evaluate_symbolic(lineage_id: str, variant: str, material: np.ndarray, tau: float | np.ndarray) -> dict[str, np.ndarray]:
    material = np.asarray(material, dtype=np.float64); count = len(material)
    times = np.asarray(tau, dtype=np.float64)
    if times.ndim == 0:
        times = np.full(count, float(times), dtype=np.float64)
    route = symbolic_family(lineage_id, variant)
    raw = route["function"](material[:, 0], material[:, 1], times)
    values = []
    for value in raw:
        array = np.asarray(value, dtype=np.float64)
        if array.ndim == 0:
            array = np.full(count, float(array), dtype=np.float64)
        values.append(np.broadcast_to(array, (count,)).copy())
    cursor = 0
    def take(size: int, shape: tuple[int, ...]) -> np.ndarray:
        nonlocal cursor
        result = np.stack(values[cursor:cursor + size], axis=-1).reshape((count, *shape)); cursor += size
        return result
    position = take(2, (2,)); F = take(4, (2, 2)); F_X = take(8, (2, 2, 2))
    position_tau = take(2, (2,)); position_tautau = take(2, (2,))
    position_tau_X = take(4, (2, 2)); position_tau_XX = take(8, (2, 2, 2))
    inverse = np.linalg.inv(F); J = np.linalg.det(F); density = RHO0 / J
    pressure = CS**2 * (density - RHO0); factor = CS / L
    velocity = position_tau * factor; acceleration = position_tautau * factor**2
    # dJ/ds = J tr(F^-1 dF/ds), for material coordinates and tau.
    J_X = J[:, None] * np.einsum("nAc,ncAB->nB", inverse, F_X)
    density_X = -RHO0 * J_X / J[:, None]**2
    pressure_X = CS**2 * density_X
    pressure_gradient = np.einsum("nA,nAa->na", pressure_X, inverse)
    velocity_X = position_tau_X * factor; velocity_XX = position_tau_XX * factor
    inverse_X = -np.einsum("nAc,ncDB,nDa->nBAa", inverse, F_X, inverse)
    velocity_laplacian = (
        np.einsum("nBa,ncAB,nAa->nc", inverse, velocity_XX, inverse)
        + np.einsum("nBa,ncA,nBAa->nc", inverse, velocity_X, inverse_X)
    )
    F_tau = position_tau_X
    J_tau = J * np.einsum("nAc,ncA->n", inverse, F_tau)
    material_density_rate = (-RHO0 * J_tau / J**2) * factor
    velocity_gradient = np.einsum("ncA,nAa->nca", velocity_X, inverse)
    velocity_divergence = velocity_gradient[:, 0, 0] + velocity_gradient[:, 1, 1]
    source = acceleration + pressure_gradient / density[:, None] - NU * velocity_laplacian
    continuity = material_density_rate + density * velocity_divergence
    momentum = acceleration - (-pressure_gradient / density[:, None] + NU * velocity_laplacian + source)
    path = position_tau * factor - velocity
    eos = pressure - CS**2 * (density - RHO0)
    return {"position": position, "F": F, "J": J, "density": density, "pressure": pressure,
            "velocity": velocity, "material_acceleration": acceleration, "pressure_gradient": pressure_gradient,
            "velocity_laplacian": velocity_laplacian, "source": source,
            "material_density_rate": material_density_rate, "velocity_divergence": velocity_divergence,
            "continuity_residual": continuity, "momentum_residual": momentum,
            "particle_path_residual": path, "eos_residual": eos}


def _torch_primitive(lineage_id: str, variant: str, material: torch.Tensor, tau: torch.Tensor) -> torch.Tensor:
    params = parameters_for(lineage_id, variant)
    X, Y = material[:, 0], material[:, 1]
    dx = torch.zeros_like(X); dy = torch.zeros_like(Y)
    for mode in params["modes"]:
        p, q = mode["p"], mode["q"]
        norm = math.sqrt(p * p + q * q); theta = mode["theta"]
        ex = math.cos(theta) * p / norm - math.sin(theta) * q / norm
        ey = math.cos(theta) * q / norm + math.sin(theta) * p / norm
        spatial = torch.sin(p * math.pi * X + q * math.pi * Y + mode["phi"])
        angle = mode["temporal_frequency_index"] * math.pi * tau + mode["psi"]
        temporal = torch.sin(angle) if mode["temporal_kind"] == "sin" else torch.cos(angle)
        dx = dx + mode["A"] * ex * spatial * temporal
        dy = dy + mode["A"] * ey * spatial * temporal
    return torch.stack((X + dx, Y + dy), dim=-1)


def evaluate_autograd(lineage_id: str, variant: str, material: np.ndarray, tau: np.ndarray) -> dict[str, np.ndarray]:
    X = torch.tensor(material, dtype=torch.float64, requires_grad=True)
    T = torch.tensor(tau, dtype=torch.float64, requires_grad=True)
    factor = CS / L

    def derivative(values: torch.Tensor, variable: torch.Tensor) -> torch.Tensor:
        return torch.autograd.grad(values, variable, torch.ones_like(values), create_graph=True, retain_graph=True)[0]

    position = _torch_primitive(lineage_id, variant, X, T)
    F = torch.stack([derivative(position[:, c], X) for c in range(2)], dim=1)
    J = torch.linalg.det(F); inverse = torch.linalg.inv(F); density = RHO0 / J
    pressure = CS**2 * (density - RHO0)
    velocity = torch.stack([derivative(position[:, c], T) for c in range(2)], dim=-1) * factor
    acceleration = torch.stack([derivative(velocity[:, c], T) for c in range(2)], dim=-1) * factor
    grad_X_pressure = derivative(pressure, X)
    pressure_gradient = torch.einsum("nA,nAa->na", grad_X_pressure, inverse)
    laplacians = []; gradients = []
    for c in range(2):
        grad_X_velocity = derivative(velocity[:, c], X)
        grad_x_velocity = torch.einsum("nA,nAa->na", grad_X_velocity, inverse); gradients.append(grad_x_velocity)
        laplacian = torch.zeros_like(T)
        for axis in range(2):
            grad_X_first = derivative(grad_x_velocity[:, axis], X)
            laplacian = laplacian + torch.einsum("nA,nA->n", grad_X_first, inverse[:, :, axis])
        laplacians.append(laplacian)
    velocity_laplacian = torch.stack(laplacians, dim=-1)
    velocity_gradient = torch.stack(gradients, dim=1)
    divergence = velocity_gradient[:, 0, 0] + velocity_gradient[:, 1, 1]
    density_rate = derivative(density, T) * factor
    source = acceleration + pressure_gradient / density[:, None] - NU * velocity_laplacian
    continuity = density_rate + density * divergence
    momentum = acceleration - (-pressure_gradient / density[:, None] + NU * velocity_laplacian + source)
    path = torch.stack([derivative(position[:, c], T) for c in range(2)], dim=-1) * factor - velocity
    eos = pressure - CS**2 * (density - RHO0)
    values = {"position": position, "F": F, "J": J, "density": density, "pressure": pressure,
              "velocity": velocity, "material_acceleration": acceleration, "pressure_gradient": pressure_gradient,
              "velocity_laplacian": velocity_laplacian, "source": source, "material_density_rate": density_rate,
              "velocity_divergence": divergence, "continuity_residual": continuity,
              "momentum_residual": momentum, "particle_path_residual": path, "eos_residual": eos}
    return {key: value.detach().numpy() for key, value in values.items()}


def audit_points(lineage_id: str, variant: str) -> tuple[np.ndarray, np.ndarray]:
    seed = int.from_bytes(hashlib.sha256(("stage07a_derivative_audit_v1" + lineage_id + variant).encode()).digest()[:8], "big")
    generator = np.random.default_rng(seed); count = 4096
    points = generator.uniform(-1.0, 1.0, size=(count, 2)).astype(np.float64)
    _, tau_grid, _ = output_times(); times = np.resize(tau_grid, count).copy()
    axis = np.asarray([-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, np.nextafter(1.0, -np.inf)])
    special = np.asarray([(x, y) for x in axis for y in axis], dtype=np.float64)
    points[:len(special)] = special; times[:len(tau_grid)] = tau_grid
    return points, times


def analytic_audit(lineage_id: str, variant: str) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    points, times = audit_points(lineage_id, variant)
    primary = evaluate_symbolic(lineage_id, variant, points, times)
    independent = evaluate_autograd(lineage_id, variant, points, times)
    keys = ["position", "F", "J", "density", "pressure", "velocity", "material_acceleration",
            "pressure_gradient", "velocity_laplacian", "source", "material_density_rate", "velocity_divergence"]
    disagreement = {}
    for key in keys:
        scale = max(1.0, float(np.max(np.abs(primary[key]))), float(np.max(np.abs(independent[key]))))
        disagreement[key] = float(np.max(np.abs(primary[key] - independent[key])) / scale)
    continuity_scale = np.maximum(1.0, np.abs(primary["material_density_rate"]) + np.abs(primary["density"] * primary["velocity_divergence"]))
    momentum_scale = np.maximum(1.0, np.linalg.norm(primary["material_acceleration"], axis=1) + np.linalg.norm(primary["pressure_gradient"] / primary["density"][:, None], axis=1) + NU * np.linalg.norm(primary["velocity_laplacian"], axis=1) + np.linalg.norm(primary["source"], axis=1))
    seam_points = points[:128].copy(); seam_times = times[:128]
    base = evaluate_symbolic(lineage_id, variant, seam_points, seam_times)
    sx = seam_points.copy(); sx[:, 0] += L
    sy = seam_points.copy(); sy[:, 1] += L
    xr = evaluate_symbolic(lineage_id, variant, sx, seam_times); yr = evaluate_symbolic(lineage_id, variant, sy, seam_times)
    periodic = max(float(np.max(np.abs((xr["position"] - base["position"]) - [L, 0.0]))),
                   float(np.max(np.abs((yr["position"] - base["position"]) - [0.0, L]))),
                   float(np.max(np.abs(xr["density"] - base["density"]))), float(np.max(np.abs(yr["density"] - base["density"]))),
                   float(np.max(np.abs(xr["velocity"] - base["velocity"]))), float(np.max(np.abs(yr["velocity"] - base["velocity"]))))
    metrics = {
        "lineage_id": lineage_id, "stratum": f"H{stratum_for(lineage_id)}", "variant": variant,
        "route_a": "closed_form_sympy", "route_b": "primitive_map_pytorch_float64_AD",
        "audit_point_count": len(points), "all_36_output_times_covered": set(output_times()[1]).issubset(set(times)),
        "minimum_J": float(np.min(primary["J"])), "minimum_rho": float(np.min(primary["density"])),
        "maximum_Mach": float(np.max(np.linalg.norm(primary["velocity"], axis=1)) / CS),
        "eos_max_absolute_residual": float(np.max(np.abs(primary["eos_residual"]))),
        "continuity_normalized_residual": float(np.max(np.abs(primary["continuity_residual"]) / continuity_scale)),
        "momentum_with_source_normalized_residual": float(np.max(np.linalg.norm(primary["momentum_residual"], axis=1) / momentum_scale)),
        "particle_path_residual": float(np.max(np.abs(primary["particle_path_residual"]))),
        "derivative_route_disagreement": disagreement, "derivative_route_disagreement_max": max(disagreement.values()),
        "periodic_residual": periodic,
        "finite": bool(all(np.isfinite(v).all() for v in primary.values()) and all(np.isfinite(v).all() for v in independent.values())),
        "formula_sha256": formula_definition(lineage_id)["formula_sha256"],
        "parameter_sha256": sha_bytes(canonical_bytes(parameters_for(lineage_id, variant))),
    }
    metrics["gates"] = {
        "eos": metrics["eos_max_absolute_residual"] <= 1e-12,
        "continuity": metrics["continuity_normalized_residual"] <= 1e-10,
        "momentum": metrics["momentum_with_source_normalized_residual"] <= 1e-10,
        "particle_path": metrics["particle_path_residual"] <= 1e-10,
        "derivative_disagreement": metrics["derivative_route_disagreement_max"] <= 1e-9,
        "minimum_J": metrics["minimum_J"] >= 0.95, "density": metrics["minimum_rho"] > 0.0,
        "Mach": metrics["maximum_Mach"] <= 0.05, "periodic": metrics["periodic_residual"] <= 1e-12,
        "finite": metrics["finite"], "time_coverage": metrics["all_36_output_times_covered"],
    }
    metrics["verdict"] = "PASS" if all(metrics["gates"].values()) else "FAIL"
    return metrics, primary


def graph_for_positions(positions: np.ndarray, support: float) -> dict[str, Any]:
    count = len(positions); pair_i, pair_j = np.triu_indices(count, k=1)
    distance = np.linalg.norm(minimum_image(positions[pair_i] - positions[pair_j]), axis=1)
    active = distance < support; unordered = np.stack((pair_i[active], pair_j[active]), axis=1).astype(np.int64)
    directed = np.concatenate((unordered, unordered[:, ::-1]), axis=0)
    if len(directed): directed = directed[np.lexsort((directed[:, 1], directed[:, 0]))]
    return {"unordered": unordered, "directed": directed, "graph_sha256": array_sha(directed),
            "edge_count_directed": int(len(directed)), "reciprocal": len(directed) == 2 * len(unordered),
            "duplicate_edge_count": int(len(directed) - len(np.unique(directed, axis=0)))}


def exact_frames(lineage_id: str, variant: str, resolution: int) -> dict[str, np.ndarray]:
    labels, dx = regular_material_layout(resolution); frame_n, tau, physical = output_times()
    fields = [evaluate_symbolic(lineage_id, variant, labels, value) for value in tau]
    unwrapped = np.stack([row["position"] for row in fields]); position = wrap_positions(unwrapped)
    arrays = {
        "frame_n": frame_n, "tau": tau, "physical_time": physical, "material_labels": labels,
        "position_unwrapped": unwrapped, "position": position,
        "velocity": np.stack([row["velocity"] for row in fields]), "density": np.stack([row["density"] for row in fields]),
        "pressure": np.stack([row["pressure"] for row in fields]),
        "material_acceleration": np.stack([row["material_acceleration"] for row in fields]),
        "external_source": np.stack([row["source"] for row in fields]), "jacobian": np.stack([row["J"] for row in fields]),
        "k1_origin_frame_n": np.asarray([[n - 3, n - 2, n - 1, n, n + 1] for n in range(32)], dtype=np.int64),
    }
    graphs = [graph_for_positions(frame, SUPPORT_OVER_DX * dx) for frame in position]
    arrays["graph_hashes"] = np.asarray([row["graph_sha256"] for row in graphs], dtype="U71")
    arrays["graph_edge_count"] = np.asarray([row["edge_count_directed"] for row in graphs], dtype=np.int64)
    arrays["state_hashes"] = np.asarray([array_sha(position[i], arrays["velocity"][i], arrays["density"][i], arrays["pressure"][i]) for i in range(36)], dtype="U71")
    return arrays


def positions_many(lineage_id: str, variant: str, labels: np.ndarray, tau: np.ndarray) -> np.ndarray:
    params = parameters_for(lineage_id, variant); tau = np.asarray(tau, dtype=np.float64)
    displacement = np.zeros((len(tau), len(labels), 2), dtype=np.float64)
    for mode in params["modes"]:
        p, q = mode["p"], mode["q"]; norm = math.sqrt(p * p + q * q); theta = mode["theta"]
        direction = np.asarray([math.cos(theta) * p / norm - math.sin(theta) * q / norm,
                                math.cos(theta) * q / norm + math.sin(theta) * p / norm])
        spatial = np.sin(p * math.pi * labels[:, 0] + q * math.pi * labels[:, 1] + mode["phi"])
        angle = mode["temporal_frequency_index"] * math.pi * tau + mode["psi"]
        temporal = np.sin(angle) if mode["temporal_kind"] == "sin" else np.cos(angle)
        displacement += mode["A"] * temporal[:, None, None] * spatial[None, :, None] * direction[None, None, :]
    return labels[None, :, :] + displacement


def topology_scan(lineage_id: str, variant: str, resolution: int) -> dict[str, Any]:
    labels, dx = regular_material_layout(resolution); support = SUPPORT_OVER_DX * dx
    pair_i, pair_j = np.triu_indices(len(labels), k=1)
    base_raw = labels[pair_i] - labels[pair_j]; base_distance = np.linalg.norm(minimum_image(base_raw), axis=1)
    perturbation_bound = 2.0 * parameters_for(lineage_id, variant)["amplitude_total"]
    selected = (np.abs(base_distance - support) <= 0.5 * dx) | (base_distance <= support + perturbation_bound)
    si, sj = pair_i[selected], pair_j[selected]
    excluded_lower = float(np.min(np.abs(base_distance[~selected] - support)) - perturbation_bound) if np.any(~selected) else math.inf
    times = np.linspace(-3.0 / 256.0, 32.0 / 256.0, 1025, dtype=np.float64)
    repeat_hashes = []; repeat_metrics = []
    for _repeat in range(3):
        sequence = hashlib.sha256(); previous_active = None; previous_shift = None
        events = switches = touches = 0; minimum_margin = math.inf
        positions = positions_many(lineage_id, variant, labels, times)
        for start in range(0, len(times), 64):
            raw = positions[start:start + 64, si] - positions[start:start + 64, sj]
            shift = np.floor((raw + 0.5 * L) / L).astype(np.int8)
            distance = np.linalg.norm(raw - shift * L, axis=2); active = distance < support
            margins = np.abs(distance - support); minimum_margin = min(minimum_margin, float(np.min(margins)))
            touches += int(np.count_nonzero(margins <= 16.0 * np.finfo(np.float64).eps * support))
            for k in range(len(active)):
                if previous_active is not None:
                    events += int(np.count_nonzero(active[k] != previous_active))
                    switches += int(np.count_nonzero(np.any(shift[k] != previous_shift, axis=1) & (active[k] | previous_active)))
                keys = np.stack((si[active[k]], sj[active[k]]), axis=1).astype(np.int32)
                sequence.update(keys.tobytes()); previous_active = active[k]; previous_shift = shift[k]
        repeat_hashes.append("sha256:" + sequence.hexdigest())
        repeat_metrics.append({"event_count": events, "minimum_image_switch_count": switches,
                               "cutoff_touch_count": touches, "minimum_absolute_cutoff_margin": minimum_margin})
    metric = repeat_metrics[0]; minimum_margin = min(metric["minimum_absolute_cutoff_margin"], excluded_lower)
    initial_graph = graph_for_positions(wrap_positions(positions_many(lineage_id, variant, labels, times[:1])[0]), support)
    gates = {"event_count": metric["event_count"] == 0, "minimum_image_switch": metric["minimum_image_switch_count"] == 0,
             "cutoff_touch": metric["cutoff_touch_count"] == 0, "margin": minimum_margin / dx >= 0.02,
             "repeat": len(set(repeat_hashes)) == 1 and repeat_metrics[1:] == repeat_metrics[:-1],
             "reciprocal": initial_graph["reciprocal"], "duplicate": initial_graph["duplicate_edge_count"] == 0}
    return {"lineage_id": lineage_id, "variant": variant, "resolution": resolution,
            "scan_time_sample_count": 1025, "deterministic_repeat_count": 3,
            "pair_count_total": int(len(pair_i)), "pair_count_scanned": int(len(si)),
            "dense_particle_N_by_N_allocation": False, "pair_distance_perturbation_bound": perturbation_bound,
            "excluded_margin_lower_bound": excluded_lower, **metric,
            "minimum_normalized_cutoff_margin": minimum_margin / dx, "reciprocal_failure_count": 0 if gates["reciprocal"] else 1,
            "duplicate_edge_count": initial_graph["duplicate_edge_count"], "repeat_sequence_hashes": repeat_hashes,
            "gates": gates, "verdict": "PASS" if all(gates.values()) else "FAIL"}
