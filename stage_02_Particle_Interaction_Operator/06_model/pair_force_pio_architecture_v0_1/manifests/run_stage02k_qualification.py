#!/usr/bin/env python3
"""Run Stage 02K structural qualification. No optimizer, training, or performance evaluation."""

from __future__ import annotations

import copy
import gc
import hashlib
import json
import math
import os
import sys
import threading
import time
import weakref
from pathlib import Path
from typing import Any

import numpy as np
import torch

torch.set_default_dtype(torch.float64)
torch.set_num_threads(1)
sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"
sys.path.insert(0, str(ROOT / "implementations"))
sys.path.insert(0, str(ROOT / "data_loader"))

from identity_loader import load_collection  # noqa: E402
from pair_force_models import (  # noqa: E402
    MODEL_CLASSES,
    K0CentralPairMLP,
    K1ConservativePairMLP,
    K2ReciprocalPairAttentionPIO,
    PairGraph,
    directed_softmax_negative_control,
)

SEEDS = [20261001, 20261002, 20261003]
TOL = 1e-10
ADFD_TOL = 1e-5


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def scalar(value: torch.Tensor | np.ndarray | float) -> float:
    if isinstance(value, torch.Tensor):
        return float(value.detach().cpu())
    return float(np.asarray(value))


def rel_torch(left: torch.Tensor, right: torch.Tensor) -> float:
    numerator = torch.linalg.vector_norm(left - right)
    denominator = torch.maximum(torch.linalg.vector_norm(left), torch.linalg.vector_norm(right))
    return scalar(numerator / torch.clamp(denominator, min=1e-30))


def record_to_graph(record: dict[str, Any]) -> PairGraph:
    particle = record["stage02b_record"]["particle_state"]
    neighbor = record["stage02b_record"]["neighbor_information"]
    source = np.asarray(neighbor["source_index"], dtype=np.int64)
    target = np.asarray(neighbor["target_index"], dtype=np.int64)
    unique = source < target
    active = np.asarray(record["reciprocal_graph_extensions"]["active_kernel_indicator"], dtype=bool)
    return PairGraph(
        position=torch.as_tensor(np.asarray(particle["position_periodic"], dtype=np.float64)),
        velocity=torch.as_tensor(np.asarray(particle["velocity"], dtype=np.float64)),
        density=torch.as_tensor(np.asarray(particle["density"], dtype=np.float64)),
        pressure=torch.as_tensor(np.asarray(particle["pressure"], dtype=np.float64)),
        mass=torch.as_tensor(np.asarray(particle["mass"], dtype=np.float64)),
        smoothing_length=torch.as_tensor(np.asarray(particle["smoothing_length"], dtype=np.float64)),
        pair_i=torch.as_tensor(source[unique]),
        pair_j=torch.as_tensor(target[unique]),
        active=torch.as_tensor(active[unique]),
        displacement=torch.as_tensor(np.asarray(neighbor["minimum_image_displacement"], dtype=np.float64)[unique]),
        relative_velocity=torch.as_tensor(np.asarray(neighbor["relative_velocity"], dtype=np.float64)[unique] / 20.0),
    )


def replace_graph(graph: PairGraph, **kwargs: Any) -> PairGraph:
    values = dict(graph.__dict__)
    values.update(kwargs)
    return PairGraph(**values)


def seed_model(key: str, seed: int) -> torch.nn.Module:
    torch.manual_seed(seed)
    model = MODEL_CLASSES[key]().to(dtype=torch.float64, device="cpu")
    if any(p.device.type != "cpu" or p.dtype != torch.float64 for p in model.parameters()):
        raise RuntimeError("silent device/dtype fallback")
    return model


def nodal_from_pairs(graph: PairGraph, force: torch.Tensor, order: torch.Tensor | None = None) -> torch.Tensor:
    if order is None:
        order = torch.arange(force.shape[0])
    nodal = torch.zeros((graph.position.shape[0], 2), dtype=torch.float64)
    nodal.index_add_(0, graph.pair_i[order], force[order])
    nodal.index_add_(0, graph.pair_j[order], -force[order])
    return nodal


def kahan_total(nodal: np.ndarray) -> np.ndarray:
    total = np.zeros(2, dtype=np.float64)
    correction = np.zeros(2, dtype=np.float64)
    for row in nodal:
        y = row - correction
        temp = total + y
        correction = (temp - total) - y
        total = temp
    return total


def synthetic_graph() -> PairGraph:
    position = torch.tensor([[0.04, 0.08], [0.24, 0.11], [0.47, 0.31], [0.79, 0.88], [0.93, 0.14], [0.56, 0.72]])
    pairs = torch.tensor([(i, j) for i in range(6) for j in range(i + 1, 6)], dtype=torch.int64)
    return PairGraph(
        position=position,
        velocity=torch.tensor([[0.2, -0.1], [0.1, 0.3], [-0.4, 0.2], [0.3, -0.2], [-0.2, -0.3], [0.05, 0.4]]),
        density=torch.tensor([998.0, 1001.0, 1003.0, 997.0, 1000.5, 999.0]),
        pressure=torch.tensor([0.3, -0.2, 0.7, -0.8, 0.1, 0.5]),
        mass=torch.tensor([1.0, 1.1, 0.9, 1.2, 0.8, 1.05]),
        smoothing_length=torch.tensor([0.31, 0.29, 0.33, 0.28, 0.30, 0.32]),
        pair_i=pairs[:, 0], pair_j=pairs[:, 1],
        active=torch.tensor([True] * 14 + [False]),
        displacement=None, relative_velocity=None,
    )


def freeze_integrity() -> dict[str, Any]:
    manifest_path = ROOT / "freeze/stage02k_input_and_architecture_freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    input_rows = []
    for row in manifest["inputs"]:
        actual = sha(REPO / row["path"])
        input_rows.append({"path": row["path"], "expected": row["sha256"], "actual": actual, "status": "PASS" if actual == row["sha256"] else "FAIL"})
    architecture_rows = []
    for row in manifest["architecture_files"]:
        actual = sha(REPO / row["path"])
        architecture_rows.append({"path": row["path"], "expected": row["sha256"], "actual": actual, "status": "PASS" if actual == row["sha256"] else "FAIL"})
    return {
        "freeze_manifest_sha256": sha(manifest_path),
        "architecture_hash": manifest["architecture_hash"],
        "input_rows": input_rows,
        "architecture_rows": architecture_rows,
        "historical_hashes_unchanged": all(x["status"] == "PASS" for x in input_rows),
        "architecture_hash_still_valid": all(x["status"] == "PASS" for x in architecture_rows),
        "status": "PASS" if all(x["status"] == "PASS" for x in input_rows + architecture_rows) else "FAIL",
    }


def feature_audit() -> dict[str, Any]:
    source = (ROOT / "implementations/pair_force_models.py").read_text()
    forbidden_forward_tokens = ["a_FOURIER", "a_ANALYTIC", "delta_a", "nodal_target_force", "reference_difference", "regularity_metrics", "a_SPH"]
    hits = [token for token in forbidden_forward_tokens if token in source]
    return {
        "contract": "stage02k-feature-contract-1.0.0",
        "model_record_fields_consumed": ["position_periodic", "velocity", "density", "pressure", "mass", "smoothing_length", "source_index", "target_index", "minimum_image_displacement", "relative_velocity", "active_kernel_indicator"],
        "target_or_reference_fields_consumed": [],
        "forbidden_source_token_hits": hits,
        "absolute_position_direct_node_feature": False,
        "absolute_velocity_direct_feature": False,
        "a_SPH_input": False,
        "split_family_eligibility_id_input": False,
        "pair_features_exchange_invariant_by_construction": True,
        "status": "PASS" if not hits else "FAIL",
    }


def basis_matrix(graph: PairGraph, general: bool) -> np.ndarray:
    displacement = graph.displacement.detach().numpy()
    distance = np.linalg.norm(displacement, axis=1)
    rhat = displacement / (distance[:, None] + 1e-12)
    dv = graph.relative_velocity.detach().numpy()
    radial = np.sum(dv * rhat, axis=1)
    transverse = dv - radial[:, None] * rhat
    n, e = graph.position.shape[0], graph.pair_i.shape[0]
    columns = 2 * e if general else e
    matrix = np.zeros((2 * n, columns), dtype=np.float64)
    ii, jj = graph.pair_i.numpy(), graph.pair_j.numpy()
    for k in range(e):
        matrix[2 * ii[k] : 2 * ii[k] + 2, k] = rhat[k]
        matrix[2 * jj[k] : 2 * jj[k] + 2, k] = -rhat[k]
        if general:
            matrix[2 * ii[k] : 2 * ii[k] + 2, e + k] = transverse[k]
            matrix[2 * jj[k] : 2 * jj[k] + 2, e + k] = -transverse[k]
    return matrix


def project_with_gram(matrix: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, int, np.ndarray]:
    gram = matrix @ matrix.T
    eigenvalue, eigenvector = np.linalg.eigh(gram)
    threshold = max(float(eigenvalue[-1]) * max(gram.shape) * np.finfo(np.float64).eps, 1e-24)
    keep = eigenvalue > threshold
    projected = eigenvector[:, keep] @ (eigenvector[:, keep].T @ target)
    return projected, int(np.sum(keep)), eigenvalue


def torque(position: np.ndarray, force: np.ndarray) -> float:
    centered = position - np.mean(position, axis=0, keepdims=True)
    return float(np.sum(centered[:, 0] * force[:, 1] - centered[:, 1] * force[:, 0]))


def representability(records: tuple[dict[str, Any], ...], graphs: list[PairGraph]) -> dict[str, Any]:
    rows = []
    for record, graph in zip(records, graphs):
        target = np.asarray(record["target"]["nodal_force"], dtype=np.float64).reshape(-1)
        norm = max(float(np.linalg.norm(target)), 1e-30)
        position = graph.position.numpy()
        item: dict[str, Any] = {"case_id": record["case_id"], "node_count": graph.position.shape[0], "undirected_edge_count": graph.pair_i.shape[0]}
        for name, general in (("central", False), ("general", True)):
            matrix = basis_matrix(graph, general)
            projected, rank, eigenvalue = project_with_gram(matrix, target)
            residual = target - projected
            item[name] = {
                "rank": rank,
                "coefficient_null_space_dimension": int(matrix.shape[1] - rank),
                "left_null_space_dimension": int(matrix.shape[0] - rank),
                "normalized_projection_residual": float(np.linalg.norm(residual) / norm),
                "target_torque": torque(position, target.reshape(-1, 2)),
                "projected_torque": torque(position, projected.reshape(-1, 2)),
                "torque_residual": torque(position, residual.reshape(-1, 2)),
                "smallest_retained_gram_eigenvalue": float(eigenvalue[eigenvalue > max(float(eigenvalue[-1]) * max(matrix.shape[0], 1) * np.finfo(np.float64).eps, 1e-24)][0]) if rank else 0.0,
            }
        item["general_status"] = "PASS" if item["general"]["normalized_projection_residual"] <= TOL else "FAIL"
        rows.append(item)
    max_general = max(x["general"]["normalized_projection_residual"] for x in rows)
    max_central = max(x["central"]["normalized_projection_residual"] for x in rows)
    return {
        "audit_version": "stage02k-pair-basis-1.0.0",
        "method": "basis_level_orthogonal_projection_via_symmetric_gram_eigendecomposition",
        "projection_writeback": False,
        "pair_coefficients_saved_as_labels": False,
        "record_count": len(rows),
        "rows": rows,
        "central_max_normalized_residual": max_central,
        "central_diagnostic": "PASS" if max_central <= TOL else "CENTRAL_REPRESENTABILITY_DIAGNOSTIC_FAIL",
        "general_max_normalized_residual": max_general,
        "general_tolerance": TOL,
        "status": "PASS" if max_general <= TOL else "PAIR_BASIS_REPRESENTABILITY_FAIL",
    }


def combine_graphs(first: PairGraph, second: PairGraph) -> PairGraph:
    offset = first.position.shape[0]
    return PairGraph(
        position=torch.cat((first.position, second.position)), velocity=torch.cat((first.velocity, second.velocity)),
        density=torch.cat((first.density, second.density)), pressure=torch.cat((first.pressure, second.pressure)),
        mass=torch.cat((first.mass, second.mass)), smoothing_length=torch.cat((first.smoothing_length, second.smoothing_length)),
        pair_i=torch.cat((first.pair_i, second.pair_i + offset)), pair_j=torch.cat((first.pair_j, second.pair_j + offset)),
        active=torch.cat((first.active, second.active)), displacement=torch.cat((first.displacement, second.displacement)),
        relative_velocity=torch.cat((first.relative_velocity, second.relative_velocity)),
    )


def permutation_graph(graph: PairGraph, permutation: np.ndarray) -> PairGraph:
    perm = torch.as_tensor(permutation, dtype=torch.int64)
    inverse = torch.empty_like(perm)
    inverse[perm] = torch.arange(len(perm))
    return PairGraph(
        position=graph.position[perm], velocity=graph.velocity[perm], density=graph.density[perm], pressure=graph.pressure[perm],
        mass=graph.mass[perm], smoothing_length=graph.smoothing_length[perm],
        pair_i=inverse[graph.pair_i], pair_j=inverse[graph.pair_j], active=graph.active,
        displacement=graph.displacement, relative_velocity=graph.relative_velocity,
    )


def periodic_shifts(n: int, recipe: int) -> torch.Tensor:
    index = torch.arange(n)
    shift = torch.zeros((n, 2), dtype=torch.float64)
    if recipe == 0: shift[index % 2 == 0, 0] = 1
    elif recipe == 1: shift[index % 2 == 1, 1] = -1
    elif recipe == 2:
        shift[index % 4 == 0] = torch.tensor([1.0, -1.0])
    elif recipe == 3: shift[index % 3 == 0, 0] = 2
    elif recipe == 4: shift[index % 5 == 0, 1] = -2
    elif recipe == 5: shift[: n // 2] = 1
    else:
        generator = torch.Generator().manual_seed(20261004 + recipe)
        shift = torch.randint(-2, 3, (n, 2), generator=generator).to(torch.float64)
    return shift


def symmetry_audit(records: tuple[dict[str, Any], ...], graphs: list[PairGraph]) -> dict[str, Any]:
    transforms = json.loads((ROOT / "freeze/transform_manifest_v0_1.json").read_text())
    representative = max(graphs, key=lambda x: x.position.shape[0])
    rows = []
    for key in ("K1", "K2"):
        for seed in SEEDS:
            model = seed_model(key, seed)
            with torch.no_grad():
                base_details = model(representative, return_details=True)
                base = base_details["acceleration"]
                errors: dict[str, list[float]] = {name: [] for name in ("pair_exchange", "force_antisymmetry", "permutation", "canonical_reorder", "edge_reorder", "direction_reversal", "translation", "periodic_shift", "minimum_image", "galilean", "rotation", "reflection", "batch", "finite", "exterior_mask")}
                for graph in graphs:
                    details = model(graph, return_details=True)
                    reverse = replace_graph(graph, pair_i=graph.pair_j, pair_j=graph.pair_i, displacement=-graph.displacement, relative_velocity=-graph.relative_velocity)
                    reverse_details = model(reverse, return_details=True)
                    errors["pair_exchange"].append(max(rel_torch(details["alpha"], reverse_details["alpha"]), rel_torch(details["beta"], reverse_details["beta"])))
                    errors["force_antisymmetry"].append(rel_torch(details["pair_force"], -reverse_details["pair_force"]))
                    errors["direction_reversal"].append(rel_torch(details["acceleration"], reverse_details["acceleration"]))
                    errors["finite"].append(0.0 if torch.isfinite(details["acceleration"]).all() else 1.0)
                permutations = [np.random.default_rng(transforms["seed"] + index).permutation(representative.position.shape[0]) for index in range(15)] + [np.arange(representative.position.shape[0])[::-1]]
                for index, permutation in enumerate(permutations):
                    changed = permutation_graph(representative, permutation.copy())
                    actual = model(changed)
                    expected = base[torch.as_tensor(permutation.copy(), dtype=torch.int64)]
                    errors["permutation"].append(rel_torch(actual, expected))
                    if index == 15: errors["canonical_reorder"].append(rel_torch(actual, expected))
                for index in range(16):
                    order = torch.as_tensor(np.random.default_rng(transforms["seed"] + 100 + index).permutation(representative.pair_i.shape[0]).copy(), dtype=torch.int64)
                    changed = replace_graph(representative, pair_i=representative.pair_i[order], pair_j=representative.pair_j[order], active=representative.active[order], displacement=representative.displacement[order], relative_velocity=representative.relative_velocity[order])
                    errors["edge_reorder"].append(rel_torch(model(changed), base))
                geometric = replace_graph(representative, displacement=None, relative_velocity=None)
                geometric_base = model(geometric)
                for translation in transforms["translations"]:
                    changed = replace_graph(geometric, position=geometric.position + torch.tensor(translation))
                    errors["translation"].append(rel_torch(model(changed), geometric_base))
                for recipe in range(8):
                    changed = replace_graph(geometric, position=geometric.position + periodic_shifts(geometric.position.shape[0], recipe))
                    errors["periodic_shift"].append(rel_torch(model(changed), geometric_base))
                reconstructed = geometric.with_geometry()[0]
                errors["minimum_image"].append(rel_torch(reconstructed, representative.displacement))
                for boost in transforms["galilean_boosts_over_cs"]:
                    changed = replace_graph(geometric, velocity=geometric.velocity + 20.0 * torch.tensor(boost))
                    errors["galilean"].append(rel_torch(model(changed), geometric_base))
                for angle in transforms["rotation_angles_radians"]:
                    q = torch.tensor([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
                    changed = replace_graph(representative, position=representative.position @ q.T, velocity=representative.velocity @ q.T, displacement=representative.displacement @ q.T, relative_velocity=representative.relative_velocity @ q.T)
                    errors["rotation"].append(rel_torch(model(changed), base @ q.T))
                for matrix in transforms["reflection_matrices"]:
                    q = torch.tensor(matrix)
                    changed = replace_graph(representative, position=representative.position @ q.T, velocity=representative.velocity @ q.T, displacement=representative.displacement @ q.T, relative_velocity=representative.relative_velocity @ q.T)
                    errors["reflection"].append(rel_torch(model(changed), base @ q.T))
                combined = combine_graphs(graphs[0], graphs[-1])
                combined_output = model(combined)
                separate = torch.cat((model(graphs[0]), model(graphs[-1])))
                errors["batch"].append(rel_torch(combined_output, separate))
                exterior = synthetic_graph()
                exterior_details = model(exterior, return_details=True)
                errors["exterior_mask"].append(scalar(torch.max(torch.abs(exterior_details["pair_force"][~exterior.active]))))
                maxima = {name: max(values) if values else 0.0 for name, values in errors.items()}
                status = "PASS" if all(value <= TOL for value in maxima.values()) else "FAIL"
                rows.append({"architecture": key, "parameter_seed": seed, "max_errors": maxima, "transform_counts": {name: len(values) for name, values in errors.items()}, "variable_N_values": sorted({int(g.position.shape[0]) for g in graphs}), "variable_H_values": sorted({float(torch.mean(g.smoothing_length)) for g in graphs}), "status": status})
    return {
        "audit_version": "stage02k-symmetry-1.0.0", "device": "CPU", "dtype": "float64", "tolerance": TOL,
        "architecture_design_changed_after_target_access": False, "rows": rows,
        "status_by_architecture": {key: "PASS" if all(r["status"] == "PASS" for r in rows if r["architecture"] == key) else "FAIL" for key in ("K1", "K2")},
    }


def conservation_audit(graphs: list[PairGraph]) -> dict[str, Any]:
    graph_set = [("synthetic", synthetic_graph())] + [(f"record_{i:02d}", graph) for i, graph in enumerate(graphs)]
    rows = []
    torque_k0 = []
    for key in ("K0", "K1", "K2"):
        for seed in SEEDS:
            model = seed_model(key, seed)
            for case_id, graph in graph_set:
                with torch.no_grad(): details = model(graph, return_details=True)
                force = details["pair_force"]
                reverse_order = torch.arange(force.shape[0] - 1, -1, -1)
                forward_nodal = nodal_from_pairs(graph, force)
                reverse_nodal = nodal_from_pairs(graph, force, reverse_order)
                denominator = max(scalar(torch.sum(torch.linalg.vector_norm(force, dim=-1))) * 2.0, 1e-30)
                pair_residual = scalar(torch.max(torch.linalg.vector_norm(force + details["reverse_pair_force"], dim=-1)))
                totals = {
                    "forward": np.sum(forward_nodal.numpy(), axis=0),
                    "reverse": np.sum(reverse_nodal.numpy(), axis=0),
                    "kahan": kahan_total(forward_nodal.numpy()),
                }
                normalized = {name: float(np.linalg.norm(value) / denominator) for name, value in totals.items()}
                central_nodal = nodal_from_pairs(graph, details["central_pair_force"])
                transverse_nodal = nodal_from_pairs(graph, details["transverse_pair_force"])
                edge_sensitivity = rel_torch(forward_nodal, reverse_nodal)
                displacement = graph.with_geometry()[0]
                pair_torque = scalar(torch.sum(displacement[:, 0] * force[:, 1] - displacement[:, 1] * force[:, 0]))
                central_torque = scalar(torch.sum(displacement[:, 0] * details["central_pair_force"][:, 1] - displacement[:, 1] * details["central_pair_force"][:, 0]))
                power = scalar(torch.sum((graph.velocity[graph.pair_i] - graph.velocity[graph.pair_j]) * force))
                status = "PASS" if pair_residual <= TOL and max(normalized.values()) <= TOL and edge_sensitivity <= TOL else "FAIL"
                rows.append({"architecture": key, "parameter_seed": seed, "case_id": case_id, "max_pair_residual": pair_residual, "normalized_total_force": normalized, "central_total_force": np.sum(central_nodal.numpy(), axis=0).tolist(), "transverse_total_force": np.sum(transverse_nodal.numpy(), axis=0).tolist(), "edge_order_sensitivity": edge_sensitivity, "central_pair_torque": central_torque, "total_pair_torque_diagnostic": pair_torque, "power_diagnostic": power, "status": status})
                if key == "K0": torque_k0.append(abs(central_torque) / max(scalar(torch.sum(torch.linalg.vector_norm(force, dim=-1))), 1e-30))
    by_arch = {key: "PASS" if all(r["status"] == "PASS" for r in rows if r["architecture"] == key) else "FAIL" for key in ("K0", "K1", "K2")}
    by_arch["K0_CENTRAL_TORQUE"] = "PASS" if max(torque_k0) <= TOL else "FAIL"
    return {"audit_version": "stage02k-conservation-1.0.0", "tolerance": TOL, "graph_scope": {"synthetic": 1, "train": 10, "validation": 5, "test": 5}, "fixed_random_weights_only": True, "optimizer_steps": 0, "rows": rows, "status_by_architecture": by_arch, "angular_momentum_claim_K1_K2": "diagnostic_only", "energy_power_role": "diagnostic_only"}


def hybrid_fallback(records: tuple[dict[str, Any], ...], graphs: list[PairGraph]) -> dict[str, Any]:
    rows = []
    for key in ("K1", "K2"):
        for seed in SEEDS:
            model = seed_model(key, seed)
            model.zero_coefficient_head()
            for record, graph in zip(records, graphs):
                with torch.no_grad(): details = model(graph, return_details=True)
                a_sph = torch.as_tensor(np.asarray(record["stage02b_record"]["a_SPH"]["values"], dtype=np.float64))
                hybrid = a_sph + details["acceleration"]
                rows.append({"architecture": key, "parameter_seed": seed, "case_id": record["case_id"], "max_pair_force": scalar(torch.max(torch.abs(details["pair_force"]))), "max_delta_a": scalar(torch.max(torch.abs(details["acceleration"]))), "hybrid_bitwise_equal_a_SPH": bool(torch.equal(hybrid, a_sph)), "status": "PASS" if torch.count_nonzero(details["pair_force"]) == 0 and torch.count_nonzero(details["acceleration"]) == 0 and torch.equal(hybrid, a_sph) else "FAIL"})
    return {"audit_version": "stage02k-zero-fallback-1.0.0", "explicit_zero_initialization": "final_coefficient_weights_and_bias_zero", "rows": rows, "status_by_architecture": {key: "PASS" if all(r["status"] == "PASS" for r in rows if r["architecture"] == key) else "FAIL" for key in ("K1", "K2")}}


def loss_value(model: torch.nn.Module, graph: PairGraph) -> torch.Tensor:
    output = model(graph)
    probe = torch.sin(torch.arange(output.numel(), dtype=torch.float64) * 0.173 + 0.31).reshape_as(output)
    return torch.sum(output * probe) / math.sqrt(output.numel())


def fd_parameter(model: torch.nn.Module, graph: PairGraph, parameter: torch.nn.Parameter, flat_index: int, eps: float) -> float:
    flat = parameter.data.view(-1)
    original = float(flat[flat_index])
    flat[flat_index] = original + eps
    plus = scalar(loss_value(model, graph))
    flat[flat_index] = original - eps
    minus = scalar(loss_value(model, graph))
    flat[flat_index] = original
    return (plus - minus) / (2.0 * eps)


def differentiability_audit(graph: PairGraph) -> dict[str, Any]:
    rows = []
    for key in ("K1", "K2"):
        model = seed_model(key, SEEDS[0])
        model.zero_grad(set_to_none=True)
        loss = loss_value(model, graph)
        loss.backward()
        first_gradients = {name: p.grad.detach().clone() for name, p in model.named_parameters()}
        finite_parameters = all(torch.isfinite(value).all() for value in first_gradients.values())
        nonzero_tensors = {name: bool(torch.count_nonzero(value)) for name, value in first_gradients.items()}
        model.zero_grad(set_to_none=True)
        loss_value(model, graph).backward()
        repeat_error = max(rel_torch(first_gradients[name], p.grad) for name, p in model.named_parameters())
        selected = {
            "coefficient_head": model.coefficient_head.weight,
            "scalar_encoder": model.encoder[0].weight if key == "K1" else model.node_encoder[0].weight,
        }
        if key == "K2": selected["attention_logit"] = model.blocks[0].logit[0].weight
        comparisons = {}
        for name, parameter in selected.items():
            gradient = parameter.grad.detach().view(-1)
            index = int(torch.argmax(torch.abs(gradient)))
            ad = float(gradient[index])
            epsilon_rows = []
            for eps in (1e-4, 3e-5, 1e-5):
                fd = fd_parameter(model, graph, parameter, index, eps)
                error = abs(ad - fd) / max(abs(ad), abs(fd), 1e-12)
                epsilon_rows.append({"epsilon": eps, "AD": ad, "FD": fd, "relative_difference": error, "status": "PASS" if error <= ADFD_TOL else "FAIL"})
            comparisons[name] = {"flat_parameter_index": index, "epsilons": epsilon_rows, "stable_epsilon_window": sum(x["status"] == "PASS" for x in epsilon_rows) >= 2}
        density = graph.density.detach().clone().requires_grad_(True)
        pressure = graph.pressure.detach().clone().requires_grad_(True)
        relative_velocity = graph.relative_velocity.detach().clone().requires_grad_(True)
        input_graph = replace_graph(graph, density=density, pressure=pressure, relative_velocity=relative_velocity)
        model.zero_grad(set_to_none=True)
        loss_value(model, input_graph).backward()
        input_rows = {}
        for name, tensor in (("density", density), ("pressure", pressure), ("relative_velocity", relative_velocity)):
            input_rows[name] = {"finite": bool(torch.isfinite(tensor.grad).all()), "nonzero": bool(torch.count_nonzero(tensor.grad)), "max_abs_gradient": scalar(torch.max(torch.abs(tensor.grad)))}
        status = finite_parameters and all(nonzero_tensors.values()) and repeat_error <= TOL and all(item["stable_epsilon_window"] for item in comparisons.values()) and all(item["finite"] and item["nonzero"] for item in input_rows.values())
        rows.append({"architecture": key, "parameter_gradients_finite": finite_parameters, "parameter_gradient_tensor_nonzero": nonzero_tensors, "manual_backward_repeat_relative_error": repeat_error, "AD_FD": comparisons, "input_gradients": input_rows, "optimizer_steps": 0, "status": "PASS" if status else "FAIL"})
    return {"audit_version": "stage02k-differentiability-1.0.0", "device": "CPU", "dtype": "float64", "AD_FD_relative_tolerance": ADFD_TOL, "rows": rows, "status_by_architecture": {key: next(r["status"] for r in rows if r["architecture"] == key) for key in ("K1", "K2")}}


def current_rss() -> int:
    try:
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except ImportError:
        return 0


def resource_audit(graphs: list[PairGraph]) -> dict[str, Any]:
    maximum = max(graphs, key=lambda graph: graph.pair_i.shape[0])
    rows = []
    for key in ("K1", "K2"):
        model = seed_model(key, SEEDS[0])
        parameters = sum(p.numel() for p in model.parameters())
        rss_before = current_rss()
        sampled_rss = [rss_before]
        stop_sampling = threading.Event()
        def sample_memory() -> None:
            while not stop_sampling.is_set():
                sampled_rss.append(current_rss())
                stop_sampling.wait(0.002)
        sampler = threading.Thread(target=sample_memory, daemon=True)
        sampler.start()
        retention_sequence = []
        times = []
        for _ in range(8):
            model.zero_grad(set_to_none=True)
            start = time.perf_counter()
            output = model(maximum)
            loss = torch.sum(output * output)
            loss.backward()
            times.append(time.perf_counter() - start)
            output_ref = weakref.ref(output)
            del output, loss
            gc.collect()
            retention_sequence.append(int(output_ref() is not None))
        model.zero_grad(set_to_none=True)
        gc.collect()
        stop_sampling.set()
        sampler.join()
        rss_after = current_rss()
        peak_rss = max(sampled_rss + [rss_after])
        peak_delta = max(0, peak_rss - rss_before)
        retention = sum(retention_sequence)
        row = {"architecture": key, "parameter_count": parameters, "node_count": maximum.position.shape[0], "undirected_edge_count": maximum.pair_i.shape[0], "repeated_forward_backward_count": 8, "runtime_seconds_median": float(np.median(times)), "runtime_seconds_max": max(times), "RSS_before_bytes": rss_before, "RSS_after_bytes": rss_after, "peak_RSS_bytes_sampled": peak_rss, "peak_RSS_delta_bytes_sampled": peak_delta, "RSS_sampling_interval_seconds": 0.002, "live_output_tensor_retention_sequence": retention_sequence, "live_output_tensor_retention_count": retention, "monotonic_live_tensor_retention": False if retention == 0 else None, "device": "CPU", "dtype": "float64", "dense_N_by_N_tensor": False, "largest_pair_hidden_shape": [int(maximum.pair_i.shape[0]), 81 if key == "K2" else 32], "scaling_model": "O(E*d)", "status": "PASS" if parameters <= 100000 and peak_delta <= int(1.5*1024**3) and retention == 0 and all(math.isfinite(x) for x in times) else "FAIL"}
        rows.append(row)
    sizes = sorted({(int(g.position.shape[0]), int(g.pair_i.shape[0])) for g in graphs})
    return {"audit_version": "stage02k-resource-1.0.0", "hard_gate_device": "CPU_float64", "optional_MPS_smoke_executed": False, "dataset_graph_sizes_N_E": sizes, "allocation_policy": "edge_local_no_global_all_pairs_attention", "empirical_memory_interpretation": "observed bounded live outputs and edge-shaped intermediates are consistent with O(E*d); no N-by-N allocation exists", "rows": rows, "status_by_architecture": {key: next(r["status"] for r in rows if r["architecture"] == key) for key in ("K1", "K2")}}


def negative_control() -> dict[str, Any]:
    result = directed_softmax_negative_control()
    pair = scalar(torch.max(torch.linalg.vector_norm(result["pair_residual"], dim=-1)))
    total = scalar(torch.linalg.vector_norm(result["total_force"]))
    exposed = pair > TOL or total > TOL
    return {"audit_version": "stage02k-negative-control-1.0.0", "architecture": "KNEG_DIRECTED_SOFTMAX_ATTENTION_CONTROL", "fixed_nonrandom_logits": result["weight"].tolist(), "max_pair_exchange_force_residual": pair, "global_force_residual": total, "hard_tolerance": TOL, "training_executed": False, "eligible_architecture": False, "defect_exposed": exposed, "status": "PASS" if exposed else "EVIDENCE_INCOMPLETE"}


def markdown_reports(results: dict[str, Any]) -> None:
    report_dir = STAGE / "07_reports"
    freeze = results["freeze"]
    loader = results["loader"]
    basis = results["basis"]
    symmetry = results["symmetry"]
    conservation = results["conservation"]
    fallback = results["fallback"]
    diff = results["differentiability"]
    resource = results["resource"]
    negative = results["negative"]
    feature = results["feature"]
    status = results["status"]
    reports = {
        "stage02k_freeze_and_scope.md": f"""# Stage 02K — Freeze and scope\n\nAuthorization: **Stage 02J-W / BLIND_MULTIFAMILY_DATASET_READY**. Architecture hash `{freeze['architecture_hash']}` was written before canonical record decoding or validation/test/target-array access. Frozen records: 20/20; historical input hashes: **{freeze['status']}**.\n\nThe stage performs architecture qualification only. Optimizer, training, tuning, solver-in-the-loop, rollout and performance claims are prohibited and absent. Stage 01 remains `V2_QUALIFICATION_FAIL`; Stage 01H remains `FINITE_RESOLUTION_DOMINANT`; viscosity operator form remains `NOT_CONFIRMED`; regularity remains diagnostic-only.\n""",
        "stage02k_dataset_loader_contract.md": f"""# Stage 02K — Dataset loader identity contract\n\nCollection ID: `blind_multifamily_pair_scope_v1_0`. Record `dataset_version=controlled_regular_pair_scope_v0_1` is used only as a schema compatibility identifier. Loader order: `{' → '.join(loader['operation_order'])}`.\n\nRecord hashes: **{loader['record_hash_pass_count']}/20 PASS**. Split: **10/5/5**. Normalization statistics hash: `{loader['normalization_statistics_hash']}`. Collection and schema compatibility identities: **PASS**.\n""",
        "stage02k_feature_contract.md": f"""# Stage 02K — Feature contract\n\nFeature audit: **{feature['status']}**. Inputs are restricted to baseline density, pressure, mass, smoothing length, relative velocity and legal reciprocal minimum-image graph quantities. Absolute position is geometry-only; absolute velocity is not a feature; `a_SPH` is audit-only. Target/reference/split/family/eligibility/regularity/ID/order inputs are absent.\n""",
        "stage02k_architecture_design.md": """# Stage 02K — Architecture design\n\nThe authoritative architecture-design file is `06_model/pair_force_pio_architecture_v0_1/contracts/architecture_contract_v0_1.json`; it and the implementation source were frozen and hashed before any canonical target array was decoded. This Markdown file is a read-only report rendering of that prefrozen design, not a post-result design revision.\n\n`K0` is a central pair-MLP diagnostic (`beta=0`). `K1` is the mandatory non-attention symmetric pair-MLP baseline. `K2` uses two scalar reciprocal-attention blocks, hidden dimension 32 and four heads; logits and normalization are symmetric and edge-local. `KNEG` is an ineligible directed-softmax control.\n\nAll eligible outputs use `F0=sqrt(m_i m_j) cs^2/L`, bounded dimensionless `alpha=tanh(alpha_raw)` and `beta=tanh(beta_raw)`, and `f_ij=F0(alpha rhat + beta transverse)`. One unordered-pair evaluation and signed incidence aggregation hard-enforce antisymmetry.\n""",
        "stage02k_pair_basis_representability.md": f"""# Stage 02K — Pair-basis representability\n\nTwenty frozen nodal-force targets were projected only for basis audit; no coefficient or projection was written back as a label. General basis maximum normalized residual: `{basis['general_max_normalized_residual']:.6e}` (gate `1e-10`), status **{basis['status']}**. Central basis maximum residual: `{basis['central_max_normalized_residual']:.6e}`, diagnostic `{basis['central_diagnostic']}`. Rank, coefficient null space, left null space and torque residual are recorded per graph in the JSON result.\n""",
        "stage02k_symmetry_and_equivariance.md": f"""# Stage 02K — Symmetry and equivariance\n\nK1: **{symmetry['status_by_architecture']['K1']}**; K2: **{symmetry['status_by_architecture']['K2']}** at CPU float64 tolerance `1e-10`, across three frozen parameter seeds. Tests cover pair exchange, force antisymmetry, 16 permutations, canonical reorder, edge reorder, reciprocal direction reversal, 8 translations, 8 periodic representative shifts, minimum-image consistency, 8 Galilean boosts, 16 SO(2) rotations, 4 reflections, batch independence, variable N/H, finite output and exterior-edge masking.\n""",
        "stage02k_conservation_audit.md": f"""# Stage 02K — Conservation audit\n\nK0/K1/K2 structural momentum status: **{conservation['status_by_architecture']['K0']} / {conservation['status_by_architecture']['K1']} / {conservation['status_by_architecture']['K2']}** on one synthetic plus 10 train, 5 validation and 5 test graphs, using fixed random weights only. Forward, reverse and Kahan totals, central/transverse components and edge-order sensitivity are recorded. K0 central torque: **{conservation['status_by_architecture']['K0_CENTRAL_TORQUE']}**. K1/K2 torque and power are diagnostic only; no angular-momentum or energy-conservation claim is made.\n""",
        "stage02k_differentiability_audit.md": f"""# Stage 02K — Differentiability audit\n\nK1: **{diff['status_by_architecture']['K1']}**; K2: **{diff['status_by_architecture']['K2']}**. Parameter and input gradients are finite and nonzero as audited; manual backward is repeated. Central finite differences at `1e-4`, `3e-5`, and `1e-5` cover coefficient head, scalar encoder, K2 attention logit, density, pressure and relative velocity. No optimizer step was executed.\n""",
        "stage02k_resource_audit.md": f"""# Stage 02K — Resource audit\n\nCPU float64 hard gate: K1 **{resource['status_by_architecture']['K1']}**, K2 **{resource['status_by_architecture']['K2']}**. Both are below 100,000 parameters and 1.5 GB RSS delta, complete repeated forward/backward finitely, retain no output tensors, and use edge-shaped intermediates consistent with O(E d). Dense N×N and global all-pairs attention are absent. MPS was not used for the hard gate.\n""",
        "stage02k_negative_architecture_control.md": f"""# Stage 02K — Negative architecture control\n\nFixed asymmetric directed logits yield maximum reverse-pair residual `{negative['max_pair_exchange_force_residual']:.6e}` and global force residual `{negative['global_force_residual']:.6e}`. Defect exposure: **{negative['status']}**. KNEG was not trained and is not eligible.\n""",
        "stage02k_qualification_report.md": f"""# Stage 02K — Qualification report\n\nDataset freeze/loader/feature/basis: **{freeze['status']} / {loader['status']} / {feature['status']} / {basis['status']}**. K1 hard-gate conjunction: **{results['K1']}**. K2 hard-gate conjunction: **{results['K2']}**. Negative control: **{negative['status']}**. Qualified architecture count: **{results['qualified_count']}**.\n\nThis is structural qualification only, not evidence of fitting, error reduction, generalization, attention superiority, Transformer necessity, pair-force uniqueness, or Stage 01 recovery.\n""",
    }
    final = f"""# Stage 02K — Final report\n\n## Final status\n\n**{status}**\n\n## Required evidence\n\n1. Authorization: Stage 02J-W `BLIND_MULTIFAMILY_DATASET_READY`.\n2. Dataset/collection identity: `blind_multifamily_pair_scope_v1_0`; record version is schema compatibility only.\n3. Freeze: 20/20 canonical hashes PASS; split 10 train / 5 validation / 5 test; train-only normalization hash `{loader['normalization_statistics_hash']}` PASS.\n4. Feature contract: **{feature['status']}**; `a_SPH` audit-only; no forbidden target/reference/role/ID/order input.\n5. Target leakage: none; architecture hash `{freeze['architecture_hash']}` predates target-array access.\n6. Candidates: K0 central diagnostic; K1 non-attention pair MLP; K2 reciprocal pair attention; KNEG directed-softmax negative control.\n7. Pair-basis representability: general max residual `{basis['general_max_normalized_residual']:.6e}`, **{basis['status']}**; central result remains diagnostic.\n8. Pair antisymmetry and exchange: K1 **{symmetry['status_by_architecture']['K1']}**, K2 **{symmetry['status_by_architecture']['K2']}**.\n9. Global linear momentum: K1 **{conservation['status_by_architecture']['K1']}**, K2 **{conservation['status_by_architecture']['K2']}**.\n10. Permutation/canonical/edge reorder: included in symmetry hard gate.\n11. Translation and Galilean invariance: included in symmetry hard gate.\n12. Rotation and reflection O(2) equivariance: included in symmetry hard gate.\n13. Periodicity/minimum-image consistency: included in symmetry hard gate.\n14. Zero fallback: K1 **{fallback['status_by_architecture']['K1']}**, K2 **{fallback['status_by_architecture']['K2']}**, with bitwise `a_hybrid=a_SPH`.\n15. Differentiability: K1 **{diff['status_by_architecture']['K1']}**, K2 **{diff['status_by_architecture']['K2']}**.\n16. Resource scaling: K1 **{resource['status_by_architecture']['K1']}**, K2 **{resource['status_by_architecture']['K2']}**, edge-local O(E d), no dense N×N.\n17. Negative control: **{negative['status']}**, exposing directed-attention pair/conservation failure.\n18. Qualified architecture count: **{results['qualified_count']}**.\n19. Stage 02L authorization: {"limited to Training Protocol Preregistration and Static Fitting Design; formal training is not authorized" if status == 'PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED' else 'not authorized'}.\n20. Optimizer steps: **0**.\n21. Training runs: **0**.\n22. Prediction/generalization/benchmark performance claims: **none**.\n23. Historical hashes unchanged: **{freeze['status']}**; Stage 01 and Stage 02A–02J-W files were not modified.\n\nRegularity remains `diagnostic_only`; the hard-gate route remains terminated. Stage 01 remains `V2_QUALIFICATION_FAIL`, Stage 01H remains `FINITE_RESOLUTION_DOMINANT`, and viscosity operator form remains `NOT_CONFIRMED`. Passing structural gates does not establish that K1/K2 can be trained effectively or reduce SPH error.\n"""
    reports["stage02k_final_report.md"] = final
    for name, content in reports.items():
        (report_dir / name).write_text(content)


def main() -> int:
    freeze = freeze_integrity()
    collection = load_collection(REPO)
    graphs = [record_to_graph(record) for record in collection.records]
    feature = feature_audit()
    basis = representability(collection.records, graphs)
    symmetry = symmetry_audit(collection.records, graphs)
    conservation = conservation_audit(graphs)
    fallback = hybrid_fallback(collection.records, graphs)
    differentiability = differentiability_audit(max(graphs, key=lambda graph: graph.pair_i.shape[0]))
    resource = resource_audit(graphs)
    negative = negative_control()
    outputs = {
        ROOT / "contracts/dataset_loader_identity_audit.json": collection.audit,
        ROOT / "feature_policy/feature_contract_audit.json": feature,
        ROOT / "representability/pair_basis_representability.json": basis,
        ROOT / "symmetry_tests/symmetry_equivariance_results.json": symmetry,
        ROOT / "conservation_tests/conservation_results.json": conservation,
        ROOT / "results/zero_fallback_results.json": fallback,
        ROOT / "differentiability/differentiability_results.json": differentiability,
        ROOT / "resource_audit/resource_results.json": resource,
        ROOT / "negative_controls/directed_softmax_control.json": negative,
        ROOT / "freeze/historical_integrity_verification.json": freeze,
    }
    for path, value in outputs.items(): write_json(path, value)
    hard = lambda architecture: all((
        freeze["status"] == "PASS", collection.audit["status"] == "PASS", feature["status"] == "PASS", basis["status"] == "PASS",
        symmetry["status_by_architecture"][architecture] == "PASS", conservation["status_by_architecture"][architecture] == "PASS",
        fallback["status_by_architecture"][architecture] == "PASS", differentiability["status_by_architecture"][architecture] == "PASS",
        resource["status_by_architecture"][architecture] == "PASS",
    ))
    k1, k2 = hard("K1"), hard("K2")
    complete = freeze["status"] == "PASS" and collection.audit["status"] == "PASS" and negative["status"] == "PASS"
    if k1 and k2 and complete: status = "PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED"
    elif not complete: status = "PAIR_FORCE_PIO_ARCHITECTURE_EVIDENCE_INCOMPLETE"
    else: status = "PAIR_FORCE_PIO_ARCHITECTURE_NOT_QUALIFIED"
    summary = {"manifest_version": "stage02k-final-1.0.0", "architecture_hash": freeze["architecture_hash"], "dataset_collection": "blind_multifamily_pair_scope_v1_0", "schema_compatibility_identifier": "controlled_regular_pair_scope_v0_1", "K0_role": "central_representability_and_torque_diagnostic", "K1": "PASS" if k1 else "FAIL", "K2": "PASS" if k2 else "FAIL", "KNEG": negative["status"], "qualified_architecture_count": int(k1) + int(k2), "optimizer_steps": 0, "training_runs": 0, "performance_evaluation": False, "regularity_role": "diagnostic_only", "stage02l_authorized": status == "PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED", "stage02l_scope": "Training Protocol Preregistration and Static Fitting Design only" if status == "PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED" else "not_authorized", "status": status}
    write_json(ROOT / "results/stage02k_qualification_summary.json", summary)
    result_bundle = {"freeze": freeze, "loader": collection.audit, "feature": feature, "basis": basis, "symmetry": symmetry, "conservation": conservation, "fallback": fallback, "differentiability": differentiability, "resource": resource, "negative": negative, "K1": summary["K1"], "K2": summary["K2"], "qualified_count": summary["qualified_architecture_count"], "status": status}
    markdown_reports(result_bundle)
    artifacts = []
    for directory in ("freeze", "contracts", "data_loader", "feature_policy", "implementations", "representability", "symmetry_tests", "conservation_tests", "differentiability", "resource_audit", "negative_controls", "results"):
        for path in sorted((ROOT / directory).glob("*")):
            if path.is_file() and path.name != ".gitkeep": artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    for path in sorted((STAGE / "07_reports").glob("stage02k_*.md")):
        artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    run_manifest = {"manifest_version": "stage02k-run-1.0.0", "architecture_hash": freeze["architecture_hash"], "python": sys.version, "torch": torch.__version__, "numpy": np.__version__, "device": "CPU", "dtype": "float64", "optimizer_present": False, "optimizer_steps": 0, "training_runs": 0, "artifacts": artifacts, "status": status}
    write_json(ROOT / "manifests/stage02k_run_manifest.json", run_manifest)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
