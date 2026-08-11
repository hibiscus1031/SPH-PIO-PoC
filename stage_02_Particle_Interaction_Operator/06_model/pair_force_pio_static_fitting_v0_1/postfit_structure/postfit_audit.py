"""Postfit hard structural re-audit for frozen selected checkpoints."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch

from pair_force_models import MODEL_CLASSES, PairGraph

TOLERANCE = 1e-10


def replace_graph(graph: PairGraph, **kwargs: Any) -> PairGraph:
    values = dict(graph.__dict__); values.update(kwargs); return PairGraph(**values)


def relative(left: torch.Tensor, right: torch.Tensor) -> float:
    numerator = torch.linalg.vector_norm(left-right)
    denominator = torch.maximum(torch.linalg.vector_norm(left), torch.linalg.vector_norm(right))
    return float(numerator / torch.clamp(denominator, min=1e-30))


def permutation_graph(graph: PairGraph, permutation: np.ndarray) -> PairGraph:
    perm = torch.as_tensor(permutation.copy(), dtype=torch.int64)
    inverse = torch.empty_like(perm); inverse[perm] = torch.arange(len(perm))
    return PairGraph(
        position=graph.position[perm], velocity=graph.velocity[perm], density=graph.density[perm], pressure=graph.pressure[perm],
        mass=graph.mass[perm], smoothing_length=graph.smoothing_length[perm], pair_i=inverse[graph.pair_i], pair_j=inverse[graph.pair_j],
        active=graph.active, displacement=graph.displacement, relative_velocity=graph.relative_velocity,
    )


def audit_selected_checkpoint(architecture: str, state: dict[str, Any], graphs: list[PairGraph]) -> dict[str, Any]:
    model = MODEL_CLASSES[architecture]().to(device="cpu", dtype=torch.float64)
    model.load_state_dict(state["model_parameters"]); model.eval()
    parameter_finite = all(torch.isfinite(parameter).all() for parameter in model.parameters())
    pair_residuals, force_residuals, torques, powers, saturations = [], [], [], [], []
    with torch.no_grad():
        for graph in graphs:
            details = model(graph, return_details=True)
            force = details["pair_force"]
            pair_scale = max(float(torch.max(torch.linalg.vector_norm(force, dim=-1))), 1e-30)
            pair_residuals.append(float(torch.max(torch.linalg.vector_norm(force + details["reverse_pair_force"], dim=-1))) / pair_scale)
            denominator = max(2.0 * float(torch.sum(torch.linalg.vector_norm(force, dim=-1))), 1e-30)
            force_residuals.append(float(torch.linalg.vector_norm(torch.sum(details["nodal_force"], dim=0))) / denominator)
            displacement = graph.with_geometry()[0]
            torques.append(float(torch.abs(torch.sum(displacement[:, 0]*force[:, 1]-displacement[:, 1]*force[:, 0]))) / max(float(torch.sum(torch.linalg.vector_norm(force, dim=-1))), 1e-30))
            powers.append(float(torch.sum((graph.velocity[graph.pair_i]-graph.velocity[graph.pair_j])*force)))
            saturation = torch.cat((torch.abs(details["alpha"]), torch.abs(details["beta"])))
            saturations.append(float(torch.mean((saturation >= 0.99).to(torch.float64))))
        representative = max(graphs, key=lambda graph: graph.position.shape[0])
        base = model(representative)
        rng = np.random.default_rng(20261301)
        permutation_errors = []
        for index in range(4):
            permutation = np.random.default_rng(20261301+index).permutation(representative.position.shape[0])
            actual = model(permutation_graph(representative, permutation))
            permutation_errors.append(relative(actual, base[torch.as_tensor(permutation.copy())]))
        edge_errors = []
        for index in range(4):
            order = torch.as_tensor(np.random.default_rng(20261401+index).permutation(representative.pair_i.shape[0]).copy(), dtype=torch.int64)
            changed = replace_graph(representative, pair_i=representative.pair_i[order], pair_j=representative.pair_j[order], active=representative.active[order], displacement=representative.displacement[order], relative_velocity=representative.relative_velocity[order])
            edge_errors.append(relative(model(changed), base))
        geometric = replace_graph(representative, displacement=None, relative_velocity=None)
        geometric_base = model(geometric)
        translation_errors = []
        for value in ([0.137, -0.219], [1.125, 0.375]):
            translation_errors.append(relative(model(replace_graph(geometric, position=geometric.position+torch.tensor(value))), geometric_base))
        boost_errors = []
        for value in ([0.031, -0.047], [0.503, -0.409]):
            boost_errors.append(relative(model(replace_graph(geometric, velocity=geometric.velocity+20.0*torch.tensor(value))), geometric_base))
        rotation_errors = []
        for angle in (0.331, 1.237, 2.719, 5.617):
            q = torch.tensor([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
            changed = replace_graph(representative, position=representative.position@q.T, velocity=representative.velocity@q.T, displacement=representative.displacement@q.T, relative_velocity=representative.relative_velocity@q.T)
            rotation_errors.append(relative(model(changed), base@q.T))
        reflection_errors = []
        for q in (torch.tensor([[1.0,0.0],[0.0,-1.0]]), torch.tensor([[0.0,1.0],[1.0,0.0]])):
            changed = replace_graph(representative, position=representative.position@q.T, velocity=representative.velocity@q.T, displacement=representative.displacement@q.T, relative_velocity=representative.relative_velocity@q.T)
            reflection_errors.append(relative(model(changed), base@q.T))
        periodic_errors = []
        for stride in (2, 5):
            shift = torch.zeros_like(geometric.position); shift[torch.arange(shift.shape[0])%stride==0, 0] = 1.0; shift[torch.arange(shift.shape[0])%(stride+1)==0, 1] = -1.0
            periodic_errors.append(relative(model(replace_graph(geometric, position=geometric.position+shift)), geometric_base))
        minimum_image_error = relative(geometric.with_geometry()[0], representative.displacement)
        reverse = replace_graph(representative, pair_i=representative.pair_j, pair_j=representative.pair_i, displacement=-representative.displacement, relative_velocity=-representative.relative_velocity)
        reverse_details = model(reverse, return_details=True)
        base_details = model(representative, return_details=True)
        antisymmetry_error = relative(base_details["pair_force"], -reverse_details["pair_force"])
        output_finite = all(torch.isfinite(model(graph)).all() for graph in graphs)
    hard_values = {
        "pair_antisymmetry": max(max(pair_residuals), antisymmetry_error),
        "global_momentum": max(force_residuals),
        "permutation": max(permutation_errors), "edge_reorder": max(edge_errors),
        "translation": max(translation_errors), "galilean": max(boost_errors),
        "rotation": max(rotation_errors), "reflection": max(reflection_errors),
        "periodic": max(periodic_errors), "minimum_image": minimum_image_error,
    }
    hard_pass = parameter_finite and output_finite and all(value <= TOLERANCE for value in hard_values.values())
    if architecture == "K0": hard_pass = hard_pass and max(torques) <= TOLERANCE
    return {
        "architecture": architecture, "run_id": state["run_id"], "selected_update": state["update_number"],
        "hard_tolerance": TOLERANCE, "hard_errors": hard_values,
        "finite_parameters": bool(parameter_finite), "finite_outputs": bool(output_finite),
        "central_torque_hard_error" if architecture == "K0" else "torque_diagnostic_max": max(torques),
        "power_diagnostic_max_abs": max(abs(value) for value in powers),
        "coefficient_saturation_fraction_max": max(saturations),
        "projection_or_postfit_repair_used": False,
        "status": "PASS" if hard_pass else "FAIL",
    }
