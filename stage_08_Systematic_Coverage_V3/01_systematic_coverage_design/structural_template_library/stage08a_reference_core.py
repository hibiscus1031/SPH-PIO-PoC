"""Deterministic Stage08A reference physics and coverage descriptors.

This module has no neural-model, optimizer, checkpoint, or training imports.
Candidate identities are a pure function of the frozen contract and unscrambled
Sobol index.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.stats import qmc
import torch
import yaml


HERE = Path(__file__).resolve()
DESIGN = HERE.parents[1]
STAGE08 = HERE.parents[2]
ROOT = HERE.parents[3]
CONTRACT_PATH = DESIGN / "contracts/systematic_coverage_v3_contract_v0_1.yaml"

L = 2.0
RHO0 = 1.0
CS = 20.0
NU = 0.02
SUPPORT_OVER_DX = 2.6
DOMAIN_MIN = np.asarray([-1.0, -1.0], dtype=np.float64)
DOMAIN_MAX = np.asarray([1.0, 1.0], dtype=np.float64)
VARIANT_SCALE = {"LOW": 0.75, "MAIN": 1.0}


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


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


def template_records() -> dict[str, dict[str, Any]]:
    return load_contract()["structural_templates"]


def _sobol_points() -> np.ndarray:
    return qmc.Sobol(d=8, scramble=False).random_base2(m=9).astype(np.float64)


SOBOL_POINTS = _sobol_points()


def candidate_specs(bank: str) -> list[tuple[str, str, int]]:
    templates = sorted(template_records())
    rows: list[tuple[str, str, int]] = []
    if bank == "TRAIN":
        for template_index, template in enumerate(templates):
            for local in range(8):
                index = template_index * 8 + local
                rows.append((f"SV3_{template}_S{index:03d}", template, index))
    elif bank == "VALIDATION":
        for template_index, template in enumerate(templates):
            for local in range(4):
                index = 256 + template_index * 4 + local
                rows.append((f"SV3V_{template}_S{index:03d}", template, index))
    else:
        raise KeyError(bank)
    return rows


def _phase_dispersion(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(1.0 - abs(np.mean(np.exp(1j * np.asarray(values, dtype=np.float64)))))


def parameter_record(candidate_id: str, template: str | None = None, sobol_index: int | None = None) -> dict[str, Any]:
    if template is None or sobol_index is None:
        found = [row for bank in ("TRAIN", "VALIDATION") for row in candidate_specs(bank) if row[0] == candidate_id]
        if len(found) != 1:
            raise KeyError(candidate_id)
        _cid, template, sobol_index = found[0]
    spec = template_records()[template]
    point = SOBOL_POINTS[int(sobol_index)]
    count = len(spec["wavevectors"])
    total = 0.004 + 0.008 * float(point[0])
    lt = 0.10 + 0.80 * float(point[1])
    anisotropy = 1.0 + 2.0 * float(point[2])
    temporal_base = 2.0 * math.pi * float(point[3])
    spatial_base = 2.0 * math.pi * float(point[4])
    simplex = np.asarray([point[5], point[6], point[7], (point[5] + point[6] + 0.5) % 1.0], dtype=np.float64)[:count]
    ordering = np.argsort(simplex, kind="stable")
    exponents = np.linspace(-0.5, 0.5, count)
    weights = np.empty(count, dtype=np.float64); weights[ordering] = anisotropy ** exponents
    weights *= 0.75 + 0.5 * simplex
    weights /= np.sum(weights)
    target_theta = math.acos(math.sqrt(lt))
    modes = []
    for mode_index, ((p, q), (kind, frequency)) in enumerate(zip(spec["wavevectors"], spec["temporal"])):
        offset = (mode_index - 0.5 * (count - 1)) * (0.08 + 0.08 * float(point[6]))
        theta = float(np.clip(target_theta + offset, 0.0, 0.5 * math.pi))
        phi = float((spatial_base + mode_index * math.pi * (math.sqrt(5.0) - 1.0)) % (2.0 * math.pi))
        psi = float((temporal_base + mode_index * math.pi * (math.sqrt(3.0) - 1.0)) % (2.0 * math.pi))
        modes.append({"mode_index": mode_index, "p": int(p), "q": int(q), "temporal_kind": str(kind),
                      "temporal_frequency_index": int(frequency), "A_main": float(total * weights[mode_index]),
                      "theta": theta, "phi": phi, "psi": psi})
    rotating_fraction = float(point[7]) if spec["macro_group"] == "rotating_anisotropic" else 0.0
    value = {"candidate_id": candidate_id, "template": template, "macro_group": spec["macro_group"],
             "sobol_index": int(sobol_index), "sobol_dimension": 8, "sobol_scramble": False,
             "sobol_point": point.tolist(), "total_amplitude_main": total, "LT_mixing_input": lt,
             "anisotropy_input": anisotropy, "rotation_fraction": rotating_fraction, "modes": modes,
             "generator": "systematic_coverage_v3_sobol_v1"}
    value["parameter_sha256"] = sha_bytes(canonical_bytes(value))
    return value


def parameters_for(candidate_id: str, variant: str) -> dict[str, Any]:
    if variant not in VARIANT_SCALE:
        raise KeyError(variant)
    base = parameter_record(candidate_id); scale = VARIANT_SCALE[variant]
    return {**base, "variant": variant, "variant_scale": scale,
            "total_amplitude": base["total_amplitude_main"] * scale,
            "modes": [{**mode, "A": mode["A_main"] * scale} for mode in base["modes"]]}


def formula_definition(candidate_id: str) -> dict[str, Any]:
    base = parameter_record(candidate_id)
    definition = {"candidate_id": candidate_id, "template": base["template"], "macro_group": base["macro_group"],
                  "mode_count": len(base["modes"]), "wavevectors": [[m["p"], m["q"]] for m in base["modes"]],
                  "material_map": "sum (A/max(1,|k|))*(cos(theta)eL+sin(theta)eT)*sin(k*pi*X+phi)*g(tau)",
                  "sobol_index": base["sobol_index"]}
    definition["formula_sha256"] = sha_bytes(canonical_bytes({**definition, "parameters": base}))
    return definition


def evaluate(candidate_id: str, variant: str, material: np.ndarray, tau: float | np.ndarray) -> dict[str, np.ndarray]:
    params = parameters_for(candidate_id, variant)
    material = np.asarray(material, dtype=np.float64); count = len(material)
    times = np.asarray(tau, dtype=np.float64)
    if times.ndim == 0:
        times = np.full(count, float(times), dtype=np.float64)
    position = material.copy(); F = np.broadcast_to(np.eye(2), (count, 2, 2)).copy()
    F_X = np.zeros((count, 2, 2, 2), dtype=np.float64)
    position_tau = np.zeros((count, 2), dtype=np.float64); position_tautau = np.zeros_like(position_tau)
    position_tau_X = np.zeros((count, 2, 2), dtype=np.float64)
    position_tau_XX = np.zeros((count, 2, 2, 2), dtype=np.float64)
    for mode in params["modes"]:
        p, q = mode["p"], mode["q"]; norm = math.hypot(p, q)
        eL = np.asarray([p, q], dtype=np.float64) / norm; eT = np.asarray([-q, p], dtype=np.float64) / norm
        direction = math.cos(mode["theta"]) * eL + math.sin(mode["theta"]) * eT
        k = math.pi * np.asarray([p, q], dtype=np.float64); amplitude = mode["A"] / max(1.0, norm)
        spatial_angle = material @ k + mode["phi"]; spatial_sin = np.sin(spatial_angle); spatial_cos = np.cos(spatial_angle)
        omega = mode["temporal_frequency_index"] * math.pi; temporal_angle = omega * times + mode["psi"]
        if mode["temporal_kind"] == "sin":
            g = np.sin(temporal_angle); gp = omega * np.cos(temporal_angle); gpp = -omega**2 * g
        else:
            g = np.cos(temporal_angle); gp = -omega * np.sin(temporal_angle); gpp = -omega**2 * g
        position += amplitude * spatial_sin[:, None] * g[:, None] * direction
        F += amplitude * np.einsum("c,a,n,n->nca", direction, k, spatial_cos, g)
        F_X += -amplitude * np.einsum("c,a,b,n,n->ncab", direction, k, k, spatial_sin, g)
        position_tau += amplitude * spatial_sin[:, None] * gp[:, None] * direction
        position_tautau += amplitude * spatial_sin[:, None] * gpp[:, None] * direction
        position_tau_X += amplitude * np.einsum("c,a,n,n->nca", direction, k, spatial_cos, gp)
        position_tau_XX += -amplitude * np.einsum("c,a,b,n,n->ncab", direction, k, k, spatial_sin, gp)
    inverse = np.linalg.inv(F); J = np.linalg.det(F); density = RHO0 / J; pressure = CS**2 * (density - RHO0)
    factor = CS / L; velocity = position_tau * factor; acceleration = position_tautau * factor**2
    J_X = J[:, None] * np.einsum("nAc,ncAB->nB", inverse, F_X)
    density_X = -RHO0 * J_X / J[:, None]**2; pressure_X = CS**2 * density_X
    pressure_gradient = np.einsum("nA,nAa->na", pressure_X, inverse)
    velocity_X = position_tau_X * factor; velocity_XX = position_tau_XX * factor
    inverse_X = -np.einsum("nAc,ncDB,nDa->nBAa", inverse, F_X, inverse)
    velocity_laplacian = np.einsum("nBa,ncAB,nAa->nc", inverse, velocity_XX, inverse) + np.einsum("nBa,ncA,nBAa->nc", inverse, velocity_X, inverse_X)
    F_tau = position_tau_X; J_tau = J * np.einsum("nAc,ncA->n", inverse, F_tau)
    density_rate = (-RHO0 * J_tau / J**2) * factor
    velocity_gradient = np.einsum("ncA,nAa->nca", velocity_X, inverse)
    divergence = velocity_gradient[:, 0, 0] + velocity_gradient[:, 1, 1]
    source = acceleration + pressure_gradient / density[:, None] - NU * velocity_laplacian
    continuity = density_rate + density * divergence
    momentum = acceleration - (-pressure_gradient / density[:, None] + NU * velocity_laplacian + source)
    return {"position": position, "F": F, "J": J, "density": density, "pressure": pressure, "velocity": velocity,
            "material_acceleration": acceleration, "pressure_gradient": pressure_gradient,
            "velocity_laplacian": velocity_laplacian, "source": source, "material_density_rate": density_rate,
            "velocity_divergence": divergence, "continuity_residual": continuity, "momentum_residual": momentum,
            "particle_path_residual": position_tau * factor - velocity,
            "eos_residual": pressure - CS**2 * (density - RHO0)}


def evaluate_autograd(candidate_id: str, variant: str, material: np.ndarray, tau: np.ndarray) -> dict[str, np.ndarray]:
    params = parameters_for(candidate_id, variant)
    X = torch.tensor(material, dtype=torch.float64, requires_grad=True)
    T = torch.tensor(tau, dtype=torch.float64, requires_grad=True)
    position = X.clone()
    for mode in params["modes"]:
        p, q = mode["p"], mode["q"]; norm = math.hypot(p, q)
        eL = torch.tensor([p / norm, q / norm], dtype=torch.float64); eT = torch.tensor([-q / norm, p / norm], dtype=torch.float64)
        direction = math.cos(mode["theta"]) * eL + math.sin(mode["theta"]) * eT
        spatial = torch.sin(math.pi * (p * X[:, 0] + q * X[:, 1]) + mode["phi"])
        angle = mode["temporal_frequency_index"] * math.pi * T + mode["psi"]
        temporal = torch.sin(angle) if mode["temporal_kind"] == "sin" else torch.cos(angle)
        position = position + (mode["A"] / max(1.0, norm)) * spatial[:, None] * temporal[:, None] * direction
    def derivative(values: torch.Tensor, variable: torch.Tensor) -> torch.Tensor:
        return torch.autograd.grad(values, variable, torch.ones_like(values), create_graph=True, retain_graph=True)[0]
    factor = CS / L
    F = torch.stack([derivative(position[:, c], X) for c in range(2)], dim=1)
    J = torch.linalg.det(F); inverse = torch.linalg.inv(F); density = RHO0 / J; pressure = CS**2 * (density - RHO0)
    velocity = torch.stack([derivative(position[:, c], T) for c in range(2)], dim=-1) * factor
    acceleration = torch.stack([derivative(velocity[:, c], T) for c in range(2)], dim=-1) * factor
    pressure_gradient = torch.einsum("nA,nAa->na", derivative(pressure, X), inverse)
    gradients = []; laplacians = []
    for c in range(2):
        grad_X = derivative(velocity[:, c], X); grad_x = torch.einsum("nA,nAa->na", grad_X, inverse); gradients.append(grad_x)
        lap = torch.zeros_like(T)
        for axis in range(2):
            lap += torch.einsum("nA,nA->n", derivative(grad_x[:, axis], X), inverse[:, :, axis])
        laplacians.append(lap)
    velocity_laplacian = torch.stack(laplacians, dim=-1); vg = torch.stack(gradients, dim=1)
    divergence = vg[:, 0, 0] + vg[:, 1, 1]; density_rate = derivative(density, T) * factor
    source = acceleration + pressure_gradient / density[:, None] - NU * velocity_laplacian
    values = {"position": position, "F": F, "J": J, "density": density, "pressure": pressure, "velocity": velocity,
              "material_acceleration": acceleration, "pressure_gradient": pressure_gradient,
              "velocity_laplacian": velocity_laplacian, "source": source, "material_density_rate": density_rate,
              "velocity_divergence": divergence}
    return {key: value.detach().numpy() for key, value in values.items()}


def audit_points(candidate_id: str, variant: str, count: int) -> tuple[np.ndarray, np.ndarray]:
    digest = hashlib.sha256(("stage08a_audit_v1" + candidate_id + variant).encode()).digest()
    generator = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    points = generator.uniform(-1.0, 1.0, size=(count, 2)).astype(np.float64)
    _, grid, _ = output_times(); times = np.resize(grid, count).copy()
    return points, times


def analytic_audit(candidate_id: str, variant: str, *, independent: bool, point_count: int) -> dict[str, Any]:
    points, times = audit_points(candidate_id, variant, point_count); primary = evaluate(candidate_id, variant, points, times)
    disagreement: dict[str, float] = {}
    if independent:
        other = evaluate_autograd(candidate_id, variant, points, times)
        for key in other:
            scale = max(1.0, float(np.max(np.abs(primary[key]))), float(np.max(np.abs(other[key]))))
            disagreement[key] = float(np.max(np.abs(primary[key] - other[key])) / scale)
    continuity_scale = np.maximum(1.0, np.abs(primary["material_density_rate"]) + np.abs(primary["density"] * primary["velocity_divergence"]))
    momentum_scale = np.maximum(1.0, np.linalg.norm(primary["material_acceleration"], axis=1) + np.linalg.norm(primary["pressure_gradient"] / primary["density"][:, None], axis=1) + NU * np.linalg.norm(primary["velocity_laplacian"], axis=1) + np.linalg.norm(primary["source"], axis=1))
    seam = points[:128].copy(); seam_t = times[:128]; base = evaluate(candidate_id, variant, seam, seam_t)
    sx = seam.copy(); sx[:, 0] += L; sy = seam.copy(); sy[:, 1] += L
    xr = evaluate(candidate_id, variant, sx, seam_t); yr = evaluate(candidate_id, variant, sy, seam_t)
    periodic = max(float(np.max(np.abs((xr["position"] - base["position"]) - [L, 0.0]))),
                   float(np.max(np.abs((yr["position"] - base["position"]) - [0.0, L]))),
                   float(np.max(np.abs(xr["density"] - base["density"]))), float(np.max(np.abs(yr["density"] - base["density"]))))
    metrics = {"candidate_id": candidate_id, "variant": variant, "audit_point_count": point_count,
               "minimum_J": float(np.min(primary["J"])), "minimum_rho": float(np.min(primary["density"])),
               "maximum_Mach": float(np.max(np.linalg.norm(primary["velocity"], axis=1)) / CS),
               "eos_max_absolute_residual": float(np.max(np.abs(primary["eos_residual"]))),
               "continuity_normalized_residual": float(np.max(np.abs(primary["continuity_residual"]) / continuity_scale)),
               "momentum_with_source_normalized_residual": float(np.max(np.linalg.norm(primary["momentum_residual"], axis=1) / momentum_scale)),
               "particle_path_residual": float(np.max(np.abs(primary["particle_path_residual"]))),
               "derivative_route_disagreement": disagreement,
               "derivative_route_disagreement_max": max(disagreement.values(), default=0.0), "periodic_residual": periodic,
               "finite": bool(all(np.isfinite(value).all() for value in primary.values())),
               "formula_sha256": formula_definition(candidate_id)["formula_sha256"]}
    gates = {"eos": metrics["eos_max_absolute_residual"] <= 1e-12,
             "continuity": metrics["continuity_normalized_residual"] <= 1e-10,
             "momentum": metrics["momentum_with_source_normalized_residual"] <= 1e-10,
             "particle_path": metrics["particle_path_residual"] <= 1e-10,
             "derivative_disagreement": (not independent) or metrics["derivative_route_disagreement_max"] <= 1e-9,
             "minimum_J": metrics["minimum_J"] >= 0.95, "density": metrics["minimum_rho"] > 0.0,
             "Mach": metrics["maximum_Mach"] <= 0.05, "periodic": periodic <= 1e-12, "finite": metrics["finite"]}
    metrics["gates"] = gates; metrics["verdict"] = "PASS" if all(gates.values()) else "FAIL"
    return metrics


def graph_for_positions(positions: np.ndarray, support: float) -> dict[str, Any]:
    count = len(positions); pair_i, pair_j = np.triu_indices(count, k=1)
    distance = np.linalg.norm(minimum_image(positions[pair_i] - positions[pair_j]), axis=1)
    active = distance < support; unordered = np.stack((pair_i[active], pair_j[active]), axis=1).astype(np.int64)
    directed = np.concatenate((unordered, unordered[:, ::-1]), axis=0)
    if len(directed): directed = directed[np.lexsort((directed[:, 1], directed[:, 0]))]
    return {"unordered": unordered, "directed": directed, "graph_sha256": array_sha(directed),
            "edge_count_directed": int(len(directed)), "reciprocal": len(directed) == 2 * len(unordered),
            "duplicate_edge_count": int(len(directed) - len(np.unique(directed, axis=0)))}


def exact_frames(candidate_id: str, variant: str, resolution: int) -> dict[str, np.ndarray]:
    labels, dx = regular_material_layout(resolution); frame_n, tau, physical = output_times()
    fields = [evaluate(candidate_id, variant, labels, value) for value in tau]
    unwrapped = np.stack([row["position"] for row in fields]); position = wrap_positions(unwrapped)
    arrays = {"frame_n": frame_n, "tau": tau, "physical_time": physical, "material_labels": labels,
              "position_unwrapped": unwrapped, "position": position,
              "velocity": np.stack([row["velocity"] for row in fields]),
              "density": np.stack([row["density"] for row in fields]),
              "pressure": np.stack([row["pressure"] for row in fields]),
              "material_acceleration": np.stack([row["material_acceleration"] for row in fields]),
              "external_source": np.stack([row["source"] for row in fields]),
              "jacobian": np.stack([row["J"] for row in fields]),
              "k1_origin_frame_n": np.asarray([[n - 3, n - 2, n - 1, n, n + 1] for n in range(32)], dtype=np.int64)}
    graphs = [graph_for_positions(frame, SUPPORT_OVER_DX * dx) for frame in position]
    arrays["graph_hashes"] = np.asarray([row["graph_sha256"] for row in graphs], dtype="U71")
    arrays["graph_edge_count"] = np.asarray([row["edge_count_directed"] for row in graphs], dtype=np.int64)
    arrays["state_hashes"] = np.asarray([array_sha(position[i], arrays["velocity"][i], arrays["density"][i], arrays["pressure"][i]) for i in range(36)], dtype="U71")
    return arrays


def positions_many(candidate_id: str, variant: str, labels: np.ndarray, tau: np.ndarray) -> np.ndarray:
    params = parameters_for(candidate_id, variant); tau = np.asarray(tau, dtype=np.float64)
    displacement = np.zeros((len(tau), len(labels), 2), dtype=np.float64)
    for mode in params["modes"]:
        p, q = mode["p"], mode["q"]; norm = math.hypot(p, q)
        direction = math.cos(mode["theta"]) * np.asarray([p, q]) / norm + math.sin(mode["theta"]) * np.asarray([-q, p]) / norm
        spatial = np.sin(math.pi * (p * labels[:, 0] + q * labels[:, 1]) + mode["phi"])
        angle = mode["temporal_frequency_index"] * math.pi * tau + mode["psi"]
        temporal = np.sin(angle) if mode["temporal_kind"] == "sin" else np.cos(angle)
        displacement += (mode["A"] / max(1.0, norm)) * temporal[:, None, None] * spatial[None, :, None] * direction
    return labels[None, :, :] + displacement


def topology_scan(candidate_id: str, variant: str, resolution: int) -> dict[str, Any]:
    labels, dx = regular_material_layout(resolution); support = SUPPORT_OVER_DX * dx
    pair_i, pair_j = np.triu_indices(len(labels), k=1)
    base_raw = labels[pair_i] - labels[pair_j]; base_distance = np.linalg.norm(minimum_image(base_raw), axis=1)
    perturbation_bound = 2.0 * parameters_for(candidate_id, variant)["total_amplitude"]
    selected = (np.abs(base_distance - support) <= 0.5 * dx) | (base_distance <= support + perturbation_bound)
    si, sj = pair_i[selected], pair_j[selected]
    excluded_lower = float(np.min(np.abs(base_distance[~selected] - support)) - perturbation_bound) if np.any(~selected) else math.inf
    times = np.linspace(-3.0 / 256.0, 32.0 / 256.0, 1025, dtype=np.float64)
    repeat_hashes = []; repeat_metrics = []
    positions = positions_many(candidate_id, variant, labels, times)
    for _repeat in range(3):
        sequence = hashlib.sha256(); previous_active = None; previous_shift = None
        events = switches = touches = 0; minimum_margin = math.inf
        for start in range(0, len(times), 64):
            raw = positions[start:start + 64, si] - positions[start:start + 64, sj]
            shift = np.floor((raw + 0.5 * L) / L).astype(np.int8); distance = np.linalg.norm(raw - shift * L, axis=2)
            active = distance < support; margins = np.abs(distance - support); minimum_margin = min(minimum_margin, float(np.min(margins)))
            touches += int(np.count_nonzero(margins <= 16.0 * np.finfo(np.float64).eps * support))
            for k in range(len(active)):
                if previous_active is not None:
                    events += int(np.count_nonzero(active[k] != previous_active))
                    switches += int(np.count_nonzero(np.any(shift[k] != previous_shift, axis=1) & (active[k] | previous_active)))
                sequence.update(np.stack((si[active[k]], sj[active[k]]), axis=1).astype(np.int32).tobytes())
                previous_active = active[k]; previous_shift = shift[k]
        repeat_hashes.append("sha256:" + sequence.hexdigest())
        repeat_metrics.append({"event_count": events, "minimum_image_switch_count": switches,
                               "cutoff_touch_count": touches, "minimum_absolute_cutoff_margin": minimum_margin})
    metric = repeat_metrics[0]; minimum_margin = min(metric["minimum_absolute_cutoff_margin"], excluded_lower)
    graph = graph_for_positions(wrap_positions(positions[0]), support)
    gates = {"event_count": metric["event_count"] == 0, "minimum_image_switch": metric["minimum_image_switch_count"] == 0,
             "cutoff_touch": metric["cutoff_touch_count"] == 0, "margin": minimum_margin / dx >= 0.02,
             "repeat": len(set(repeat_hashes)) == 1 and repeat_metrics[1:] == repeat_metrics[:-1],
             "reciprocal": graph["reciprocal"], "duplicate": graph["duplicate_edge_count"] == 0}
    return {"candidate_id": candidate_id, "variant": variant, "resolution": resolution, "scan_time_sample_count": 1025,
            "deterministic_repeat_count": 3, "pair_count_total": int(len(pair_i)), "pair_count_scanned": int(len(si)),
            **metric, "minimum_normalized_cutoff_margin": minimum_margin / dx,
            "repeat_sequence_hashes": repeat_hashes, "gates": gates, "verdict": "PASS" if all(gates.values()) else "FAIL"}


def primitive_descriptor(record: dict[str, Any]) -> dict[str, Any]:
    modes = record["modes"]; amplitudes = np.asarray([m.get("A_main", m.get("A", 0.0)) for m in modes])
    wavevectors = [(int(m["p"]), int(m["q"])) for m in modes]; angles = np.unwrap(np.asarray([math.atan2(q, p) for p, q in wavevectors]))
    longitudinal = float(np.sum(amplitudes * np.cos([m["theta"] for m in modes])**2) / np.sum(amplitudes))
    transverse = 1.0 - longitudinal
    return {"mode_count": len(modes), "total_amplitude": float(np.sum(amplitudes)),
            "wavevector_set_identity": [f"{p}:{q}" for p, q in sorted(set(wavevectors))],
            "max_wavevector_norm": float(max(math.hypot(p, q) for p, q in wavevectors)),
            "wavevector_angle_dispersion": float(np.std(angles)) if len(angles) > 1 else 0.0,
            "temporal_frequency_count": len(set(m["temporal_frequency_index"] for m in modes)),
            "max_temporal_frequency": max(m["temporal_frequency_index"] for m in modes),
            "temporal_phase_dispersion": _phase_dispersion([m["psi"] for m in modes]),
            "longitudinal_fraction": longitudinal, "transverse_fraction": transverse,
            "LT_mixing_index": 2.0 * min(longitudinal, transverse),
            "anisotropy_ratio": float(np.max(amplitudes) / max(np.min(amplitudes), 1e-15)),
            "rotating_mode_fraction": float(record.get("rotation_fraction", 0.0))}


NUMERIC_DESCRIPTOR_KEYS = (
    "mode_count", "total_amplitude", "max_wavevector_norm", "wavevector_angle_dispersion",
    "temporal_frequency_count", "max_temporal_frequency", "temporal_phase_dispersion", "longitudinal_fraction",
    "transverse_fraction", "LT_mixing_index", "anisotropy_ratio", "rotating_mode_fraction", "source_rms",
    "source_p95", "velocity_rms", "acceleration_rms", "density_variation_rms", "Mach_max", "min_J",
    "graph_degree_mean", "graph_degree_std", "normalized_topology_margin", "raw_a_def_rms", "raw_a_cons_rms",
    "component_covariance_eigenvalue_1", "component_covariance_eigenvalue_2", "spatial_spectral_centroid",
    "spatial_spectral_spread", "temporal_defect_variation", "conservative_fraction",
    "oracle_bounded_coefficient_rms", "oracle_bounded_coefficient_p95", "oracle_alpha_rms", "oracle_beta_rms",
    "bounded_head_margin", "Q_bounded")


def graph_degree_stats(position: np.ndarray, resolution: int) -> tuple[float, float]:
    graph = graph_for_positions(position, SUPPORT_OVER_DX * L / resolution); degrees = np.zeros(len(position), dtype=np.int64)
    if len(graph["directed"]): np.add.at(degrees, graph["directed"][:, 0], 1)
    return float(np.mean(degrees)), float(np.std(degrees))


def physical_descriptor(arrays: dict[str, np.ndarray], topology: dict[str, Any], resolution: int = 8) -> dict[str, float]:
    source = arrays["external_source"]; velocity = arrays["velocity"]; acceleration = arrays["material_acceleration"]
    density = arrays["density"]; degree_mean, degree_std = graph_degree_stats(arrays["position"][3], resolution)
    return {"source_rms": float(np.sqrt(np.mean(source**2))), "source_p95": float(np.percentile(np.abs(source), 95)),
            "velocity_rms": float(np.sqrt(np.mean(velocity**2))), "acceleration_rms": float(np.sqrt(np.mean(acceleration**2))),
            "density_variation_rms": float(np.sqrt(np.mean((density - RHO0)**2))),
            "Mach_max": float(np.max(np.linalg.norm(velocity, axis=-1)) / CS), "min_J": float(np.min(arrays["jacobian"])),
            "graph_degree_mean": degree_mean, "graph_degree_std": degree_std,
            "normalized_topology_margin": float(topology["minimum_normalized_cutoff_margin"])}


def spatial_spectrum_metrics(targets: np.ndarray, resolution: int) -> tuple[float, float]:
    k = np.fft.fftfreq(resolution) * resolution; kx, ky = np.meshgrid(k, k, indexing="ij"); radius = np.sqrt(kx**2 + ky**2)
    energy = np.zeros_like(radius)
    for target in targets:
        grid = target.reshape(resolution, resolution, 2)
        energy += np.abs(np.fft.fft2(grid[:, :, 0]))**2 + np.abs(np.fft.fft2(grid[:, :, 1]))**2
    total = float(np.sum(energy)) + 1e-30; centroid = float(np.sum(radius * energy) / total)
    spread = float(np.sqrt(np.sum((radius - centroid)**2 * energy) / total))
    return centroid, spread


def defect_oracle_descriptor(arrays: dict[str, np.ndarray], rhs_factory: Callable[[], Any], resolution: int = 8) -> tuple[dict[str, float], np.ndarray]:
    rhs = rhs_factory(); dt = L / CS / 256.0; raw = []; cons = []; alpha = []; beta = []; bounded_all = []; q_values = []
    for n in range(32):
        start = n + 3; nxt = start + 1
        state = rhs.pack(arrays["position_unwrapped"][start], arrays["velocity"][start], arrays["density"][start])
        k1 = rhs(float(arrays["physical_time"][start]), state); midpoint = state + 0.5 * dt * k1
        k2 = rhs(float(arrays["physical_time"][start] + 0.5 * dt), midpoint); accepted = state + dt * k2
        mid_position, mid_velocity, _ = rhs.unpack(midpoint); _, accepted_velocity, _ = rhs.unpack(accepted)
        a_def = (arrays["velocity"][nxt] - accepted_velocity) / dt; a_cons = a_def - np.mean(a_def, axis=0, keepdims=True)
        raw.append(a_def); cons.append(a_cons)
        graph = graph_for_positions(wrap_positions(mid_position), SUPPORT_OVER_DX * L / resolution); pairs = graph["unordered"]
        mass = RHO0 * (L / resolution)**2; count = resolution * resolution; edge_count = len(pairs)
        if edge_count == 0:
            q_values.append(1.0); continue
        displacement = minimum_image(mid_position[pairs[:, 0]] - mid_position[pairs[:, 1]])
        distance = np.linalg.norm(displacement, axis=1); rhat = displacement / (distance[:, None] + 2e-12)
        dv = (mid_velocity[pairs[:, 1]] - mid_velocity[pairs[:, 0]]) / CS
        radial = np.sum(dv * rhat, axis=1); transverse = dv - radial[:, None] * rhat
        B = np.zeros((2 * count, 2 * edge_count), dtype=np.float64); f0 = mass * CS**2 / L; bound = 0.05
        for edge, (i, j) in enumerate(pairs):
            for offset, vector in ((0, bound * f0 * rhat[edge]), (edge_count, bound * f0 * transverse[edge])):
                B[2*i:2*i+2, edge+offset] = vector / mass; B[2*j:2*j+2, edge+offset] = -vector / mass
        b = a_cons.ravel(); coefficient = B.T @ (np.linalg.pinv(B @ B.T, rcond=1e-12, hermitian=True) @ b)
        bounded = np.clip(coefficient, -1.0, 1.0); residual = (B @ bounded).reshape(a_cons.shape) - a_cons
        denominator = max(float(np.sqrt(np.mean(a_cons**2))), 1e-12)
        alpha.extend(bounded[:edge_count]); beta.extend(bounded[edge_count:]); bounded_all.extend(bounded)
        q_values.append(float(np.sqrt(np.mean(residual**2)) / denominator))
    raw_a = np.stack(raw); cons_a = np.stack(cons); covariance = np.cov(cons_a.reshape(-1, 2), rowvar=False)
    eig = np.sort(np.linalg.eigvalsh(covariance))[::-1]; centroid, spread = spatial_spectrum_metrics(cons_a, resolution)
    bounded_array = np.asarray(bounded_all, dtype=np.float64); alpha_array = np.asarray(alpha); beta_array = np.asarray(beta)
    raw_energy = float(np.mean(raw_a**2)); cons_energy = float(np.mean(cons_a**2))
    desc = {"raw_a_def_rms": float(np.sqrt(raw_energy)), "raw_a_cons_rms": float(np.sqrt(cons_energy)),
            "component_covariance_eigenvalue_1": float(eig[0]), "component_covariance_eigenvalue_2": float(eig[1]),
            "spatial_spectral_centroid": centroid, "spatial_spectral_spread": spread,
            "temporal_defect_variation": float(np.sqrt(np.mean(np.diff(cons_a, axis=0)**2)) / max(np.sqrt(cons_energy), 1e-12)),
            "conservative_fraction": cons_energy / max(raw_energy, 1e-24),
            "oracle_bounded_coefficient_rms": float(np.sqrt(np.mean(bounded_array**2))) if len(bounded_array) else 0.0,
            "oracle_bounded_coefficient_p95": float(np.percentile(np.abs(bounded_array), 95)) if len(bounded_array) else 0.0,
            "oracle_alpha_rms": float(np.sqrt(np.mean(alpha_array**2))) if len(alpha_array) else 0.0,
            "oracle_beta_rms": float(np.sqrt(np.mean(beta_array**2))) if len(beta_array) else 0.0,
            "bounded_head_margin": float(1.0 - np.max(np.abs(bounded_array))) if len(bounded_array) else 1.0,
            "Q_bounded": float(np.mean(q_values))}
    return desc, cons_a.reshape(-1).astype(np.float64)


def normalization(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = np.asarray([[row[key] for key in NUMERIC_DESCRIPTOR_KEYS] for row in rows], dtype=np.float64)
    median = np.median(matrix, axis=0); mad = np.median(np.abs(matrix - median), axis=0)
    floor = np.maximum(1e-12, 0.01 * np.maximum(np.abs(median), 1.0)); scale = np.maximum(1.4826 * mad, floor)
    return {"keys": list(NUMERIC_DESCRIPTOR_KEYS), "median": median.tolist(), "MAD": mad.tolist(),
            "frozen_floor": floor.tolist(), "scale": scale.tolist(), "evidence_count": len(rows)}


def descriptor_distance(left: dict[str, Any], right: dict[str, Any], norm: dict[str, Any]) -> float:
    center = np.asarray(norm["median"]); scale = np.asarray(norm["scale"])
    a = (np.asarray([left[key] for key in NUMERIC_DESCRIPTOR_KEYS]) - center) / scale
    b = (np.asarray([right[key] for key in NUMERIC_DESCRIPTOR_KEYS]) - center) / scale
    sa, sb = set(left["wavevector_set_identity"]), set(right["wavevector_set_identity"])
    structural = 1.0 - len(sa & sb) / max(len(sa | sb), 1)
    return float(np.sqrt((np.sum((a - b)**2) + structural**2) / (len(a) + 1)))
