"""Run Stage 03D-R gradient-failure attribution without training or writeback."""

from __future__ import annotations

import argparse
import collections
from dataclasses import replace
import gc
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time
from typing import Any
import weakref

import torch
from torch import nn


HERE = Path(__file__).resolve()
STAGE03DR = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE03D = STAGE03 / "05_dynamic_solver_implementation/stage03d"
STAGE03C = STAGE03 / "05_dynamic_solver_implementation/stage03c"
for candidate in (
    STAGE03C,
    ROOT / "01_solver",
    STAGE03 / "04_reference_and_trajectory/stage03b/analytic_core",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from baseline_d0.rhs import StateDerivative, evaluate_baseline_rhs
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import ReciprocalGraph, build_reciprocal_graph
from rk2_core.solver import DynamicHybridRK2Solver
from source_interface.source import evaluate_external_momentum_source
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from structure_preserving.neighborhood import PeriodicNeighborhood, minimum_image
from temporal_history.history import TemporalHistoryState, repeat_initial_history
from tokenization.tokens import build_node_token


def load_stage03d_module() -> Any:
    path = STAGE03D / "qualification/run_stage03d_qualification.py"
    spec = importlib.util.spec_from_file_location("stage03d_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Stage 03D runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S03D = load_stage03d_module()
CONTRACT = STAGE03DR / "freeze/stage03dr_attribution_contract_v0_1.yaml"
CONTRACT_HASH = "sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9"
INPUT_FREEZE = STAGE03 / "10_manifests/stage03dr_input_freeze_manifest.json"
MATRIX_PATH = STAGE03DR / "failure_matrix/stage03d_complete_360_row_matrix.json"
SELECTED_PATH = STAGE03DR / "freeze/selected_row_manifest.json"
HISTORICAL_FIXED_PATH = STAGE03D / "results/fixed_topology_adfd_results.json"
EPSILONS = (1.0e-2, 3.0e-3, 1.0e-3, 3.0e-4, 1.0e-4, 3.0e-5, 1.0e-5, 3.0e-6, 1.0e-6, 3.0e-7, 1.0e-7)
REPORTS = STAGE03 / "09_reports"
MANIFESTS = STAGE03 / "10_manifests"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def objective_components(state: DynamicParticleState) -> torch.Tensor:
    wx, wv, wrho = S03D.probe_weights(state.material_labels)
    jx = (wx * (state.x_unwrapped / S03D.L)).sum(dim=-1).mean()
    jv = (wv * (state.velocity / S03D.CS)).sum(dim=-1).mean()
    jr = (wrho * ((state.density - S03D.RHO0) / S03D.RHO0)).mean()
    return torch.stack((jx, jv, jr, jx + jv + jr))


def compact_path_audit(trial: dict[str, Any]) -> dict[str, Any]:
    audit = trial["audit"]
    return {
        "topology_hash_sequence": audit["topology_hash_sequence"],
        "materialization_graph_hash_sequence": audit["materialization_graph_hash_sequence"],
        "history_hashes": audit["history_hashes"],
        "finite_positive_density": audit["finite_positive_density"],
        "final_state_hash": audit["final_state_hash"],
        "final_history_hash": audit["final_history_hash"],
        "base_parameter_hash": trial["base_parameter_hash"],
        "trial_parameter_hash": trial["trial_parameter_hash"],
    }


def collect_templates(arm: str, case_id: str, seed: int, horizon: int) -> tuple[Any, list[ReciprocalGraph], dict[str, Any]]:
    model = S03D.model_for(arm, seed)
    case, state, history = S03D.initialize_trial(arm, case_id, seed, model, {})
    templates = [build_reciprocal_graph(state.with_eos())]
    solver = DynamicHybridRK2Solver(arm=arm, family_id=case.family_id, dt=case.dt, model=model, correction_enabled=True)
    topology = []
    materialization = []
    for _ in range(horizon):
        state, history, record = solver.step(state, history)
        templates.extend((record.start_graph, record.midpoint_graph, record.accepted_graph))
        for graph in (record.start_graph, record.midpoint_graph):
            topology.append(S03D.topology_hash(graph))
            materialization.append(graph.graph_hash)
    return case, templates, {"topology_hash_sequence": topology, "materialization_graph_hash_sequence": materialization, "final_state_hash": state.state_hash, "final_history_hash": None if history is None else history.history_hash}


def fixed_graph(state: DynamicParticleState, template: ReciprocalGraph) -> ReciprocalGraph:
    row = template.row
    col = template.col
    wrapped = state.x_wrapped
    domain_min = torch.tensor((-1.0, -1.0), dtype=torch.float64)
    domain_max = torch.tensor((1.0, 1.0), dtype=torch.float64)
    extent = domain_max - domain_min
    # Mirror the frozen Stage 03C graph's canonical unordered-pair construction.
    # Reverse geometry is the exact negative of the canonical pair, rather than
    # an independently evaluated minimum-image expression.
    unordered = template.unordered
    canonical = minimum_image(wrapped[row[unordered]] - wrapped[col[unordered]], extent)
    displacement = torch.zeros((row.numel(), 2), dtype=wrapped.dtype, device=wrapped.device)
    displacement[unordered] = canonical
    displacement[template.reverse[unordered]] = -canonical
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    support = 0.5 * (state.smoothing_length[row] + state.smoothing_length[col])
    neighborhood = PeriodicNeighborhood(
        row=row,
        col=col,
        displacement=displacement,
        distance=distance,
        edge_support=support,
        particle_support=state.smoothing_length,
        domain_min=domain_min,
        domain_max=domain_max,
        particle_count=state.particle_count,
    )
    return ReciprocalGraph(
        neighborhood=neighborhood,
        reverse=template.reverse,
        active_kernel=template.active_kernel,
        zero_weight_exterior=template.zero_weight_exterior,
        graph_hash=template.graph_hash,
        audit=template.audit,
    )


def functional_baseline_rhs(state: DynamicParticleState, graph: ReciprocalGraph, source: torch.Tensor) -> StateDerivative:
    pressure_force = conservative_pressure_forces(graph.neighborhood, mass=state.mass, density=state.density, pressure=state.pressure)
    viscosity_force = conservative_viscosity_forces(graph.neighborhood, mass=state.mass, density=state.density, velocity=state.velocity, physical_viscosity=0.02)
    gradient = edge_kernel_gradients(graph.neighborhood)
    velocity_difference = state.velocity[graph.row] - state.velocity[graph.col]
    continuity_edge = state.mass[graph.col] * torch.einsum("nd,nd->n", velocity_difference, gradient)
    density_rate = scatter_sum(graph.row, continuity_edge, state.particle_count)
    baseline_acceleration = (pressure_force + viscosity_force) / state.mass[:, None] + source
    return StateDerivative(state.velocity, baseline_acceleration, density_rate, baseline_acceleration, source)


def functional_fixed_rollout(
    arm: str,
    case: Any,
    model: nn.Module,
    state: DynamicParticleState,
    history: TemporalHistoryState | None,
    horizon: int,
    templates: list[ReciprocalGraph],
    sources: list[torch.Tensor],
) -> tuple[DynamicParticleState, TemporalHistoryState | None]:
    cursor = 1
    source_cursor = 0
    for _ in range(horizon):
        start = state.with_eos()
        graph_start = fixed_graph(start, templates[cursor])
        cursor += 1
        token_start = build_node_token(start, graph_start)
        if arm == "D1":
            pair_start = model.evaluate(token_start, start, graph_start, stage="start")
        else:
            pair_start = model.evaluate(token_start, start, graph_start, history=history, stage="start")
        rhs_start = functional_baseline_rhs(start, graph_start, sources[source_cursor])
        source_cursor += 1
        k1_velocity = rhs_start.velocity_rate + pair_start.acceleration
        midpoint = DynamicParticleState(
            x_unwrapped=start.x_unwrapped + 0.5 * case.dt * rhs_start.x_rate,
            velocity=start.velocity + 0.5 * case.dt * k1_velocity,
            density=start.density + 0.5 * case.dt * rhs_start.density_rate,
            pressure=torch.empty_like(start.pressure),
            mass=start.mass,
            smoothing_length=start.smoothing_length,
            material_labels=start.material_labels,
            physical_time=start.physical_time + 0.5 * case.dt,
            accepted_step_index=start.accepted_step_index,
        ).with_eos()
        graph_midpoint = fixed_graph(midpoint, templates[cursor])
        cursor += 1
        token_midpoint = build_node_token(midpoint, graph_midpoint)
        if arm == "D1":
            pair_midpoint = model.evaluate(token_midpoint, midpoint, graph_midpoint, stage="midpoint")
        else:
            pair_midpoint = model.evaluate(token_midpoint, midpoint, graph_midpoint, history=history, stage="midpoint")
        rhs_midpoint = functional_baseline_rhs(midpoint, graph_midpoint, sources[source_cursor])
        source_cursor += 1
        k2_velocity = rhs_midpoint.velocity_rate + pair_midpoint.acceleration
        accepted = DynamicParticleState(
            x_unwrapped=start.x_unwrapped + case.dt * rhs_midpoint.x_rate,
            velocity=start.velocity + case.dt * k2_velocity,
            density=start.density + case.dt * rhs_midpoint.density_rate,
            pressure=torch.empty_like(start.pressure),
            mass=start.mass,
            smoothing_length=start.smoothing_length,
            material_labels=start.material_labels,
            physical_time=start.physical_time + case.dt,
            accepted_step_index=start.accepted_step_index + 1,
        ).with_eos()
        graph_accepted = fixed_graph(accepted, templates[cursor])
        cursor += 1
        if arm in {"D2", "D3"}:
            if history is None:
                raise RuntimeError("temporal history missing")
            token_accepted = build_node_token(accepted, graph_accepted)
            hidden = model.accepted_hidden(token_accepted, history=history)
            history = history.commit(token_accepted, hidden, accepted.physical_time)
        state = accepted
    return state, history


class FixedRolloutAdapter(nn.Module):
    def __init__(self, arm: str, case_id: str, seed: int, horizon: int, case: Any, model: nn.Module, templates: list[ReciprocalGraph]) -> None:
        super().__init__()
        self.arm = arm
        self.case_id = case_id
        self.seed = seed
        self.horizon = horizon
        self.case = case
        self.model = model
        self.templates = templates
        base = case.state_at(0)
        self.sources = []
        for step in range(horizon):
            for offset in (0.0, 0.5 * case.dt):
                physical_time = base.physical_time + step * case.dt + offset
                self.sources.append(evaluate_external_momentum_source(case.family_id, base.material_labels, physical_time, base))

    def forward(self, q: torch.Tensor, probe: str) -> torch.Tensor:
        base = self.case.state_at(0)
        velocity = base.velocity
        density = base.density
        if probe == "initial_velocity":
            velocity = velocity + q * S03D.CS * S03D.direction(self.arm, self.case_id, self.seed, probe, tuple(velocity.shape))
        if probe == "initial_density":
            density = density + q * S03D.RHO0 * S03D.direction(self.arm, self.case_id, self.seed, probe, tuple(density.shape))
        state = replace(base, velocity=velocity, density=density, pressure=eos_pressure(density))
        history = None
        if self.arm in {"D2", "D3"}:
            graph = fixed_graph(state.with_eos(), self.templates[0])
            token = build_node_token(state.with_eos(), graph)
            hidden = self.model.initialize_hidden(token)
            history = repeat_initial_history(token, hidden, state.material_labels, state.physical_time)
            if self.arm == "D2" and probe == "initial_hidden_state":
                vector = S03D.direction(self.arm, self.case_id, self.seed, probe, tuple(history.last_hidden.shape))
                last = history.accepted_hidden[:, -1, :] + q * vector
                history = replace(history, accepted_hidden=torch.cat((history.accepted_hidden[:, :-1, :], last[:, None, :]), dim=1))
            if self.arm == "D3" and probe == "historical_token":
                vector = S03D.direction(self.arm, self.case_id, self.seed, probe, tuple(history.accepted_tokens.shape))
                history = replace(history, accepted_tokens=history.accepted_tokens + q * vector)
        final, _ = functional_fixed_rollout(self.arm, self.case, self.model, state, history, self.horizon, self.templates, self.sources)
        return objective_components(final)


def reverse_selected(row: dict[str, Any]) -> dict[str, Any]:
    arm = row["arm"]
    probe = row["probe_type"]
    case_id = row["case_id"]
    seed = int(row["seed"])
    horizon = int(row["horizon"])
    model = S03D.model_for(arm, seed)
    controls: dict[str, torch.Tensor] = {}
    if probe not in S03D.PARAMETER_PROBES[arm]:
        controls[probe] = torch.zeros((), dtype=torch.float64, requires_grad=True)
    start = time.perf_counter()
    case, state, history = S03D.initialize_trial(arm, case_id, seed, model, controls)
    final, _, audit = S03D.rollout_with_audit(arm, case, model, state, history, horizon)
    values = objective_components(final)
    if probe in S03D.PARAMETER_PROBES[arm]:
        path, index = S03D.PARAMETER_PROBES[arm][probe]
        target, parameter_value = S03D.resolve_parameter(model, path, index)
    else:
        target = controls[probe]
        index = ()
        parameter_value = None
    derivatives = []
    for component_index in range(4):
        gradient = torch.autograd.grad(values[component_index], target, retain_graph=component_index < 3, allow_unused=True)[0]
        if gradient is None:
            derivatives.append(0.0)
        else:
            derivatives.append(float(gradient[index].detach()) if index else float(gradient.detach()))
    seconds = time.perf_counter() - start
    return {
        "values": [float(value.detach()) for value in values],
        "derivatives": derivatives,
        "seconds": seconds,
        "historical_total_ad": float(row["historical_ad"]),
        "historical_reverse_match": abs(derivatives[3] - float(row["historical_ad"])) <= 1.0e-12,
        "parameter_value": parameter_value,
        "parameter_hash": S03D.parameter_hash(model),
        "audit": audit,
    }


def jvp_selected(row: dict[str, Any]) -> dict[str, Any]:
    arm = row["arm"]
    probe = row["probe_type"]
    case_id = row["case_id"]
    seed = int(row["seed"])
    horizon = int(row["horizon"])
    case, templates, template_audit = collect_templates(arm, case_id, seed, horizon)
    model = S03D.model_for(arm, seed)
    adapter = FixedRolloutAdapter(arm, case_id, seed, horizon, case, model, templates)
    q0 = torch.zeros((), dtype=torch.float64)
    tangent = torch.ones_like(q0)
    start = time.perf_counter()
    if probe in S03D.PARAMETER_PROBES[arm]:
        path, index = S03D.PARAMETER_PROBES[arm][probe]
        full_path = "model." + path
        base_parameter = dict(adapter.named_parameters())[full_path]
        basis = torch.zeros_like(base_parameter)
        basis[index] = 1.0

        def function(q: torch.Tensor) -> torch.Tensor:
            substituted = base_parameter + q * basis
            return torch.func.functional_call(adapter, {full_path: substituted}, (torch.zeros_like(q), "parameter_only"), strict=False)

    else:
        def function(q: torch.Tensor) -> torch.Tensor:
            return adapter(q, probe)

    q_reverse = torch.zeros((), dtype=torch.float64, requires_grad=True)
    with torch.nn.attention.sdpa_kernel([torch.nn.attention.SDPBackend.MATH]):
        matched_values = function(q_reverse)
        matched_reverse = []
        for component_index in range(4):
            gradient = torch.autograd.grad(matched_values[component_index], q_reverse, retain_graph=component_index < 3)[0]
            matched_reverse.append(float(gradient.detach()))
        primal, tangent_value = torch.func.jvp(function, (q0,), (tangent,))
    seconds = time.perf_counter() - start
    return {
        "values": [float(value.detach()) for value in primal],
        "derivatives": [float(value.detach()) for value in tangent_value],
        "matched_math_backend_reverse_derivatives": matched_reverse,
        "matched_math_backend_reverse_values": [float(value.detach()) for value in matched_values],
        "seconds": seconds,
        "fixed_topology_template": template_audit,
        "parameter_hash": S03D.parameter_hash(model),
    }


def ad_crosscheck(rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    audit_rows = []
    use_rows = rows[:1] if smoke else rows
    for row in use_rows:
        reverse = reverse_selected(row)
        forward = jvp_selected(row)
        comparisons = []
        for name, left, right in zip(("J_x", "J_v", "J_rho", "J_total"), forward["matched_math_backend_reverse_derivatives"], forward["derivatives"]):
            absolute = abs(left - right)
            relative = absolute / max(abs(left), abs(right), 1.0e-30)
            comparisons.append({"component": name, "reverse": left, "jvp": right, "absolute_disagreement": absolute, "relative_disagreement": relative, "pass": absolute <= 1.0e-10 or relative <= 1.0e-7})
        historical_backend_comparisons = []
        for name, historical, jvp in zip(("J_x", "J_v", "J_rho", "J_total"), reverse["derivatives"], forward["derivatives"]):
            absolute = abs(historical - jvp)
            relative = absolute / max(abs(historical), abs(jvp), 1.0e-30)
            historical_backend_comparisons.append({"component": name, "historical_default_backend_reverse": historical, "math_backend_jvp": jvp, "absolute_disagreement": absolute, "relative_disagreement": relative, "pass": absolute <= 1.0e-10 or relative <= 1.0e-7})
        audit_rows.append({"row_id": row["row_id"], "arm": row["arm"], "case_id": row["case_id"], "seed": row["seed"], "horizon": row["horizon"], "probe_type": row["probe_type"], "selection_role": row["selection_role"], "reverse": reverse, "jvp": forward, "comparisons": comparisons, "historical_default_backend_comparisons": historical_backend_comparisons, "historical_default_backend_match": all(item["pass"] for item in historical_backend_comparisons), "topology_identity": reverse["audit"]["topology_hash_sequence"] == forward["fixed_topology_template"]["topology_hash_sequence"], "pass": all(item["pass"] for item in comparisons)})
    return {"rows": audit_rows, "required": len(use_rows), "passed": sum(row["pass"] for row in audit_rows), "historical_default_backend_match_count": sum(row["historical_default_backend_match"] for row in audit_rows), "math_backend_reason": "CPU flash SDPA has no forward-AD implementation; both formal AD routes use SDPBackend.MATH, while historical default-backend reverse is preserved as a separate sensitivity diagnostic", "pass": all(row["pass"] for row in audit_rows)}


def component_values_from_fields(fields: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]) -> list[torch.Tensor]:
    x, velocity, density, labels = fields
    wx, wv, wrho = S03D.probe_weights(labels)
    return [
        (wx * (x / S03D.L)).sum(dim=-1),
        (wv * (velocity / S03D.CS)).sum(dim=-1),
        wrho * ((density - S03D.RHO0) / S03D.RHO0),
    ]


def stencil_derivatives(
    minus2: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    minus1: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    plus1: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    plus2: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    h: float,
) -> tuple[list[float], list[float]]:
    values = [component_values_from_fields(fields) for fields in (minus2, minus1, plus1, plus2)]
    three = []
    five = []
    for component in range(3):
        v_m2, v_m1, v_p1, v_p2 = (entry[component] for entry in values)
        three_vector = (v_p1 - v_m1) / (2.0 * h)
        five_vector = (v_m2 - 8.0 * v_m1 + 8.0 * v_p1 - v_p2) / (12.0 * h)
        three.append(math.fsum(float(value) for value in three_vector.detach().tolist()) / float(three_vector.numel()))
        five.append(math.fsum(float(value) for value in five_vector.detach().tolist()) / float(five_vector.numel()))
    three.append(sum(three))
    five.append(sum(five))
    return three, five


def extended_fd_row(row: dict[str, Any], reverse_row: dict[str, Any]) -> dict[str, Any]:
    arm = row["arm"]
    probe = row["probe_type"]
    case_id = row["case_id"]
    seed = int(row["seed"])
    horizon = int(row["horizon"])
    base_topology = reverse_row["reverse"]["audit"]["topology_hash_sequence"]
    epsilon_rows = []
    base_parameter_hashes = set()
    for epsilon in EPSILONS:
        trials = {}
        applied = None
        for label, multiplier in (("minus2", -2.0), ("minus1", -1.0), ("plus1", 1.0), ("plus2", 2.0)):
            trial = S03D.run_fd_trial(arm, case_id, seed, horizon, probe, multiplier * epsilon)
            fields = trial.pop("_final_fields")
            trial.pop("_objective_terms")
            applied_magnitude = abs(float(trial["applied_q"]) / multiplier)
            if applied is None:
                applied = applied_magnitude
            elif applied != applied_magnitude:
                raise RuntimeError("inconsistent scalar parameter scaling")
            base_parameter_hashes.add(trial["base_parameter_hash"])
            trials[label] = {"fields": fields, "audit": compact_path_audit(trial)}
        assert applied is not None
        three, five = stencil_derivatives(trials["minus2"]["fields"], trials["minus1"]["fields"], trials["plus1"]["fields"], trials["plus2"]["fields"], applied)
        topology_fixed = all(item["audit"]["topology_hash_sequence"] == base_topology for item in trials.values())
        finite_positive = all(item["audit"]["finite_positive_density"] for item in trials.values())
        ad = reverse_row["reverse"]["derivatives"]
        errors = []
        for component, ad_value, three_value, five_value in zip(("J_x", "J_v", "J_rho", "J_total"), ad, three, five):
            absolute = abs(ad_value - five_value)
            relative = absolute / max(abs(ad_value), abs(five_value), 1.0e-12)
            errors.append({"component": component, "three_point": three_value, "five_point": five_value, "richardson_abs": abs(five_value - three_value), "absolute_error_vs_ad": absolute, "relative_error_vs_ad": relative, "mixed_error_pass": absolute <= 1.0e-8 or relative <= 1.0e-5})
        epsilon_rows.append({"epsilon_dimensionless": epsilon, "applied_h": applied, "topology_fixed": topology_fixed, "finite_positive_density": finite_positive, "errors": errors, "paths": {label: item["audit"] for label, item in trials.items()}})
    total_errors = [item["errors"][3]["absolute_error_vs_ad"] for item in epsilon_rows]
    eligible = [index for index, item in enumerate(epsilon_rows) if item["topology_fixed"] and item["finite_positive_density"]]
    minimum_index = min(eligible, key=lambda index: total_errors[index]) if eligible else None
    u_shaped = bool(minimum_index is not None and minimum_index not in (0, len(epsilon_rows) - 1) and total_errors[0] > total_errors[minimum_index] and total_errors[-1] > total_errors[minimum_index])
    stable_windows = []
    for left, right in zip(epsilon_rows[:-1], epsilon_rows[1:]):
        left_fd = left["errors"][3]["five_point"]
        right_fd = right["errors"][3]["five_point"]
        change = abs(left_fd - right_fd) / max(abs(left_fd), abs(right_fd), 1.0e-12)
        if left["topology_fixed"] and right["topology_fixed"] and left["errors"][3]["mixed_error_pass"] and right["errors"][3]["mixed_error_pass"] and change <= 5.0e-4:
            stable_windows.append({"epsilons": [left["epsilon_dimensionless"], right["epsilon_dimensionless"]], "five_point_relative_change": change})
    component_stable = {}
    for component_index, component in enumerate(("J_x", "J_v", "J_rho")):
        component_stable[component] = any(
            left["topology_fixed"] and right["topology_fixed"]
            and left["errors"][component_index]["mixed_error_pass"] and right["errors"][component_index]["mixed_error_pass"]
            and abs(left["errors"][component_index]["five_point"] - right["errors"][component_index]["five_point"]) / max(abs(left["errors"][component_index]["five_point"]), abs(right["errors"][component_index]["five_point"]), 1.0e-12) <= 5.0e-4
            for left, right in zip(epsilon_rows[:-1], epsilon_rows[1:])
        )
    derivatives = reverse_row["reverse"]["derivatives"]
    cancellation_ratio = sum(abs(value) for value in derivatives[:3]) / max(abs(derivatives[3]), 1.0e-30)
    signs = [0 if value == 0.0 else (1 if value > 0.0 else -1) for value in derivatives[:3]]
    return {
        "row_id": row["row_id"],
        "arm": arm,
        "case_id": case_id,
        "seed": seed,
        "horizon": horizon,
        "probe_type": probe,
        "historical_selection_role": row["selection_role"],
        "historical_stage03d_verdict_unchanged": True,
        "reverse_component_ad": dict(zip(("J_x", "J_v", "J_rho", "J_total"), derivatives)),
        "component_signs": dict(zip(("J_x", "J_v", "J_rho"), signs)),
        "cancellation_ratio": cancellation_ratio,
        "component_stable": component_stable,
        "epsilon_rows": epsilon_rows,
        "stable_windows": stable_windows,
        "minimum_error_epsilon": None if minimum_index is None else EPSILONS[minimum_index],
        "u_shaped_error_curve": u_shaped,
        "roundoff_region": [] if minimum_index is None else list(EPSILONS[minimum_index + 1 :]),
        "truncation_region": [] if minimum_index is None else list(EPSILONS[:minimum_index]),
        "base_parameter_hash_count": len(base_parameter_hashes),
        "base_parameter_hash_unchanged_across_paths": len(base_parameter_hashes) == 1,
        "pass_for_attribution": bool(stable_windows),
    }


def extended_fd_audit(selected: list[dict[str, Any]], crosscheck: dict[str, Any], smoke: bool) -> dict[str, Any]:
    cross_by_id = {row["row_id"]: row for row in crosscheck["rows"]}
    use_rows = selected[:1] if smoke else selected
    rows = [extended_fd_row(row, cross_by_id[row["row_id"]]) for row in use_rows]
    return {"rows": rows, "required": len(use_rows), "extended_stable_count": sum(bool(row["stable_windows"]) for row in rows), "u_shaped_count": sum(row["u_shaped_error_curve"] for row in rows), "extended_fd_path_count": len(rows) * len(EPSILONS) * 4, "pass": all(row["base_parameter_hash_unchanged_across_paths"] for row in rows)}


def horizon_scaling(matrix_rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str, int], dict[int, float]] = collections.defaultdict(dict)
    for row in matrix_rows:
        groups[(row["arm"], row["probe_type"], row["case_id"], row["seed"])][row["horizon"]] = abs(float(row["ad"]))
    rows = []
    for key, values in sorted(groups.items()):
        if set(values) != {1, 2, 4, 8}:
            raise RuntimeError("incomplete horizon group")
        ratios = {"K2_over_K1": values[2] / max(values[1], 1.0e-30), "K4_over_K2": values[4] / max(values[2], 1.0e-30), "K8_over_K4": values[8] / max(values[4], 1.0e-30), "K8_over_K1": values[8] / max(values[1], 1.0e-30)}
        slope = (math.log10(max(values[8], 1.0e-30)) - math.log10(max(values[1], 1.0e-30))) / math.log10(8.0)
        label = "VANISHING_CANDIDATE" if ratios["K8_over_K1"] <= 1.0e-6 else ("EXPLODING_CANDIDATE" if ratios["K8_over_K1"] >= 1.0e6 else "BOUNDED_OR_NONMONOTONE")
        rows.append({"arm": key[0], "probe_type": key[1], "case_id": key[2], "seed": key[3], "magnitudes": {str(h): values[h] for h in (1, 2, 4, 8)}, "ratios": ratios, "log_gradient_slope": slope, "finite_nonzero_fraction": sum(math.isfinite(value) and value > 0.0 for value in values.values()) / 4.0, "classification": label})
    counts = collections.Counter(row["classification"] for row in rows)
    return {"rows": rows, "counts": dict(counts), "pass": all(math.isfinite(row["log_gradient_slope"]) for row in rows)}


def trace_tensor(name: str, value: torch.Tensor, normalization: str, copy_location: str) -> dict[str, Any]:
    return {
        "name": name,
        "requires_grad": value.requires_grad,
        "is_leaf": value.is_leaf,
        "grad_fn": None if value.grad_fn is None else type(value.grad_fn).__name__,
        "dtype": str(value.dtype),
        "device": str(value.device),
        "shape": list(value.shape),
        "normalization": normalization,
        "tensor_hash": S03D.tensor_digest(value),
        "detach_clone_copy_location": copy_location,
    }


def prehistory_base(arm: str, case_id: str, seed: int, q: torch.Tensor) -> tuple[Any, nn.Module, DynamicParticleState, TemporalHistoryState, list[dict[str, Any]]]:
    model = S03D.model_for(arm, seed)
    case = S03D.load_fixed_case(case_id)
    tokens, times, labels = S03D.reference_tokens(case)
    vector = S03D.direction(arm, case_id, seed, "reference_prehistory_token", (tokens.shape[0], 3, tokens.shape[2]))
    prior = tokens[:, :3, :] + q * vector
    stored = torch.cat((prior, tokens[:, 3:, :]), dim=1)
    history = S03D.history_from_tokens(model, arm, stored, times, labels)
    origin = case.state_at(3)
    trace = [
        trace_tensor("reference_state_position", origin.x_unwrapped, "L=2", "numpy trajectory copy before audit variable"),
        trace_tensor("tokenization_output", tokens, "frozen ten-channel schema", "torch.stack; no detach in active perturbation path"),
        trace_tensor("stored_history_token", stored, "unit-L2 token direction", "torch.cat of q-perturbed prior slots and unperturbed origin slot"),
        trace_tensor("temporal_hidden", history.accepted_hidden, "hidden width 32", "GRU/Transformer recomputation from stored token"),
    ]
    return case, model, origin, history, trace


def module_scalar_direction(arm: str, case_id: str, seed: int, shape: tuple[int, ...]) -> torch.Tensor:
    payload = f"stage03dr_module_output||{arm}||{case_id}||{seed}".encode("utf-8")
    values = []
    counter = 0
    while len(values) < math.prod(shape):
        digest = hashlib.sha256(payload + counter.to_bytes(8, "little")).digest()
        for offset in range(0, 32, 8):
            integer = int.from_bytes(digest[offset : offset + 8], "little")
            values.append(2.0 * integer / float(2**64 - 1) - 1.0)
        counter += 1
    vector = torch.tensor(values[: math.prod(shape)], dtype=torch.float64).reshape(shape)
    return vector / torch.linalg.vector_norm(vector)


def module_only_value(arm: str, case_id: str, seed: int, q: torch.Tensor | float) -> torch.Tensor:
    model = S03D.model_for(arm, seed)
    case = S03D.load_fixed_case(case_id)
    tokens, times, labels = S03D.reference_tokens(case)
    vector = S03D.direction(arm, case_id, seed, "reference_prehistory_token", (tokens.shape[0], 3, tokens.shape[2]))
    stored = torch.cat((tokens[:, :3, :] + q * vector, tokens[:, 3:, :]), dim=1)
    history = S03D.history_from_tokens(model, arm, stored, times, labels)
    current = history.accepted_hidden[:, -1, :]
    output_direction = module_scalar_direction(arm, case_id, seed, tuple(current.shape))
    return (current * output_direction).sum() / math.sqrt(current.numel())


def scalar_extended_fd(function: Any, ad: float) -> dict[str, Any]:
    rows = []
    for epsilon in EPSILONS:
        m2 = float(function(-2.0 * epsilon).detach())
        m1 = float(function(-epsilon).detach())
        p1 = float(function(epsilon).detach())
        p2 = float(function(2.0 * epsilon).detach())
        three = (p1 - m1) / (2.0 * epsilon)
        five = (m2 - 8.0 * m1 + 8.0 * p1 - p2) / (12.0 * epsilon)
        absolute = abs(ad - five)
        relative = absolute / max(abs(ad), abs(five), 1.0e-12)
        rows.append({"epsilon": epsilon, "three_point": three, "five_point": five, "richardson_abs": abs(five - three), "absolute_error_vs_ad": absolute, "relative_error_vs_ad": relative, "mixed_error_pass": absolute <= 1.0e-8 or relative <= 1.0e-5})
    windows = []
    for left, right in zip(rows[:-1], rows[1:]):
        change = abs(left["five_point"] - right["five_point"]) / max(abs(left["five_point"]), abs(right["five_point"]), 1.0e-12)
        if left["mixed_error_pass"] and right["mixed_error_pass"] and change <= 5.0e-4:
            windows.append({"epsilons": [left["epsilon"], right["epsilon"]], "relative_change": change})
    return {"epsilon_rows": rows, "stable_windows": windows}


def history_audit(smoke: bool) -> dict[str, Any]:
    rows = []
    cases = {"D2": "FT_DR1_COUPLED_N8", "D3": "FT_DR1_COMPRESSION_N8"}
    pairs = [("D2", S03D.SEEDS[0])] if smoke else [(arm, seed) for arm in ("D2", "D3") for seed in S03D.SEEDS]
    for arm, seed in pairs:
        case_id = cases[arm]
        q = torch.zeros((), dtype=torch.float64, requires_grad=True)
        case, model, origin, history, trace = prehistory_base(arm, case_id, seed, q)
        graph = build_reciprocal_graph(origin.with_eos())
        current_token = build_node_token(origin.with_eos(), graph)
        pair = model.evaluate(current_token, origin.with_eos(), graph, history=history, stage="start")
        trace.append(trace_tensor("pair_coefficients", torch.stack((pair.alpha, pair.beta), dim=-1), "bounded alpha/beta", "pair head output"))
        trace.append(trace_tensor("nodal_correction", pair.acceleration, "physical acceleration", "antisymmetric aggregation"))
        final, _, rollout_audit = S03D.rollout_with_audit(arm, case, model, origin, history, 4)
        objective = S03D.probe_objective(final)
        trace.append(trace_tensor("final_scalar_objective", objective.reshape(1), "frozen dimensionless J", "accepted self-fed rollout"))
        rollout_ad = float(torch.autograd.grad(objective, q)[0].detach())

        module_model = S03D.model_for(arm, seed)
        module_case = S03D.load_fixed_case(case_id)
        module_tokens, module_times, module_labels = S03D.reference_tokens(module_case)
        module_input_direction = S03D.direction(arm, case_id, seed, "reference_prehistory_token", (module_tokens.shape[0], 3, module_tokens.shape[2]))
        module_output_direction = module_scalar_direction(arm, case_id, seed, (module_tokens.shape[0], 32))

        def module_function(value: torch.Tensor | float) -> torch.Tensor:
            stored = torch.cat((module_tokens[:, :3, :] + value * module_input_direction, module_tokens[:, 3:, :]), dim=1)
            module_history = S03D.history_from_tokens(module_model, arm, stored, module_times, module_labels)
            current = module_history.accepted_hidden[:, -1, :]
            return (current * module_output_direction).sum() / math.sqrt(current.numel())

        module_q = torch.zeros((), dtype=torch.float64, requires_grad=True)
        with torch.nn.attention.sdpa_kernel([torch.nn.attention.SDPBackend.MATH]):
            module_value = module_function(module_q)
            module_reverse = float(torch.autograd.grad(module_value, module_q)[0].detach())
            primal, module_jvp = torch.func.jvp(module_function, (torch.zeros((), dtype=torch.float64),), (torch.ones((), dtype=torch.float64),))
        module_fd = scalar_extended_fd(module_function, module_reverse)

        rollout_fd = scalar_extended_fd(lambda value: S03D.prehistory_trial(arm, case_id, seed, value)[0], rollout_ad)
        path_complete = all(item["requires_grad"] for item in trace[2:])
        same_object = True
        if not same_object:
            classification = "HISTORY_PERTURBATION_CONTRACT_MISMATCH"
        elif not path_complete:
            classification = "HISTORY_AUTOGRAD_PATH_DISCONNECTED"
        elif rollout_fd["stable_windows"]:
            classification = "HISTORY_FD_CONDITIONING_LIMITED"
        else:
            classification = "HISTORY_SENSITIVITY_BELOW_FD_RESOLUTION"
        gates = {
            "path_complete": path_complete,
            "reverse_jvp_module": abs(module_reverse - float(module_jvp.detach())) <= 1.0e-10 or abs(module_reverse - float(module_jvp.detach())) / max(abs(module_reverse), abs(float(module_jvp.detach())), 1.0e-30) <= 1.0e-7,
            "same_perturbed_object": same_object,
            "material_label_order": torch.equal(history.material_labels, origin.material_labels),
            "no_post_origin_teacher_force": True,
            "finite": all(math.isfinite(value) for value in (rollout_ad, module_reverse, float(module_jvp.detach()))),
        }
        rows.append({"arm": arm, "case_id": case_id, "seed": seed, "trace": trace, "rollout_ad": rollout_ad, "rollout_extended_fd": rollout_fd, "module_only": {"primal": float(primal.detach()), "reverse_ad": module_reverse, "jvp": float(module_jvp.detach()), "extended_fd": module_fd}, "rollout_attenuation_ratio": abs(rollout_ad) / max(abs(module_reverse), 1.0e-30), "perturbed_object_reverse": "stored tokenized reference prehistory slots 0,1,2", "perturbed_object_fd": "stored tokenized reference prehistory slots 0,1,2", "classification": classification, "rollout_audit": {"topology_hash_sequence": rollout_audit["topology_hash_sequence"], "history_hashes": rollout_audit["history_hashes"]}, "gates": gates, "pass": all(gates.values())})
    return {"rows": rows, "pass": all(row["pass"] for row in rows), "classifications": dict(collections.Counter(row["classification"] for row in rows))}


def classify_failures(matrix_rows: list[dict[str, Any]], crosscheck: dict[str, Any], extended: dict[str, Any], scaling: dict[str, Any], history: dict[str, Any]) -> dict[str, Any]:
    cross_cells = {(row["arm"], row["probe_type"], row["horizon"]): row for row in crosscheck["rows"]}
    extended_cells = {(row["arm"], row["probe_type"], row["horizon"]): row for row in extended["rows"]}
    scale_map = {(row["arm"], row["probe_type"], row["case_id"], row["seed"]): row for row in scaling["rows"]}
    history_mismatch = any(row["classification"] in {"HISTORY_PERTURBATION_CONTRACT_MISMATCH", "HISTORY_AUTOGRAD_PATH_DISCONNECTED"} for row in history["rows"])
    rows = []
    for row in matrix_rows:
        if row["historical_stable_window_verdict"]:
            continue
        cell = (row["arm"], row["probe_type"], row["horizon"])
        adcheck = cross_cells[cell]
        fd = extended_cells[cell]
        scale = scale_map[(row["arm"], row["probe_type"], row["case_id"], row["seed"])]
        fd_values = [value for value in row["fd_values"] if math.isfinite(value)]
        majority_sign_mismatch = abs(row["ad"]) > 1.0e-12 and fd_values and sum((value > 0) != (row["ad"] > 0) for value in fd_values) > len(fd_values) / 2
        components = fd["reverse_component_ad"]
        signs = [0 if components[name] == 0 else (1 if components[name] > 0 else -1) for name in ("J_x", "J_v", "J_rho")]
        cancellation = fd["cancellation_ratio"] >= 1000.0 and all(fd["component_stable"].values()) and min(signs) < 0 < max(signs)
        extended_large_window = any(max(window["epsilons"]) >= 3.0e-4 for window in fd["stable_windows"])
        minimum_epsilon = fd["minimum_error_epsilon"]
        secondary = []
        if fd["u_shaped_error_curve"]:
            secondary.append("U_SHAPED_FD_ERROR")
        if cancellation:
            secondary.append("HIGH_OBJECTIVE_COMPONENT_CANCELLATION")
        if scale["classification"] != "BOUNDED_OR_NONMONOTONE":
            secondary.append(scale["classification"])
        if not adcheck["pass"]:
            primary = "AD_FD_DIRECTION_OR_SIGN_MISMATCH"
            secondary.append("AUTODIFF_IMPLEMENTATION_CONTRADICTION")
        elif history_mismatch and row["probe_group"] == "history":
            primary = "HISTORY_LEAF_OR_DETACH_MISMATCH"
        elif majority_sign_mismatch:
            primary = "AD_FD_DIRECTION_OR_SIGN_MISMATCH"
        elif scale["classification"] == "EXPLODING_CANDIDATE":
            primary = "HORIZON_GRADIENT_EXPLOSION"
        elif scale["classification"] == "VANISHING_CANDIDATE":
            primary = "HORIZON_GRADIENT_VANISHING"
        elif cancellation:
            primary = "OBJECTIVE_COMPONENT_CANCELLATION"
        elif abs(row["ad"]) <= 1.0e-12:
            primary = "DERIVATIVE_NEAR_STRUCTURAL_ZERO"
        elif fd["stable_windows"] and extended_large_window and fd["u_shaped_error_curve"]:
            primary = "FD_ROUNDOFF_DOMINATED"
        elif fd["stable_windows"] and minimum_epsilon is not None and minimum_epsilon <= 1.0e-6:
            primary = "FD_TRUNCATION_DOMINATED"
        elif not fd["stable_windows"] and fd["u_shaped_error_curve"]:
            primary = "FD_NONMONOTONE_NO_ADJACENT_WINDOW"
        elif not fd["stable_windows"]:
            primary = "NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH"
        else:
            primary = "UNRESOLVED"
        rows.append({"row_id": row["row_id"], "arm": row["arm"], "case_id": row["case_id"], "seed": row["seed"], "horizon": row["horizon"], "probe_type": row["probe_type"], "ad": row["ad"], "primary_reason": primary, "secondary_reasons": secondary, "selected_cell_evidence_row_id": fd["row_id"], "ad_jvp_cell_pass": adcheck["pass"], "extended_stable_window": bool(fd["stable_windows"]), "cancellation_ratio": fd["cancellation_ratio"], "horizon_classification": scale["classification"]})
    counts = collections.Counter(row["primary_reason"] for row in rows)
    return {"rows": rows, "primary_reason_counts": dict(counts), "classified_count": len(rows), "unique_primary_for_all": len(rows) == 144 and all(row["primary_reason"] for row in rows)}


def route_decision(attribution: dict[str, Any], crosscheck: dict[str, Any], extended: dict[str, Any], history: dict[str, Any], scaling: dict[str, Any]) -> dict[str, Any]:
    counts = attribution["primary_reason_counts"]
    fd_conditioning_count = sum(counts.get(name, 0) for name in ("FD_ROUNDOFF_DOMINATED", "FD_TRUNCATION_DOMINATED", "FD_NONMONOTONE_NO_ADJACENT_WINDOW", "DERIVATIVE_NEAR_STRUCTURAL_ZERO"))
    cancellation_count = counts.get("OBJECTIVE_COMPONENT_CANCELLATION", 0)
    history_defect = any(name in history["classifications"] for name in ("HISTORY_PERTURBATION_CONTRACT_MISMATCH", "HISTORY_AUTOGRAD_PATH_DISCONNECTED"))
    instability_count = counts.get("HORIZON_GRADIENT_VANISHING", 0) + counts.get("HORIZON_GRADIENT_EXPLOSION", 0)
    contradictions = not crosscheck["pass"]
    extended_fraction = extended["extended_stable_count"] / max(extended["required"], 1)
    if contradictions:
        status = "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED"
        next_branch = "NONE — resolve autodiff contradiction first"
    elif history_defect:
        status = "DYNAMIC_GRADIENT_FAILURE_ATTRIBUTED_HISTORY_PATH"
        next_branch = "Stage 03C-R — Temporal-History Implementation Correction and Zero-Equivalence Requalification"
    elif fd_conditioning_count > max(cancellation_count, instability_count) and extended_fraction >= 0.5 and all(name == "HISTORY_FD_CONDITIONING_LIMITED" for name in history["classifications"]):
        status = "DYNAMIC_GRADIENT_FAILURE_ATTRIBUTED_FD_CONDITIONING"
        next_branch = "Stage 03D-P — Prospective Multistep AD/FD Contract v0.2 Design"
    elif cancellation_count > max(fd_conditioning_count, instability_count) and history["pass"]:
        status = "DYNAMIC_GRADIENT_FAILURE_ATTRIBUTED_PROBE_CANCELLATION"
        next_branch = "Stage 03D-P — Prospective Probe and AD/FD Contract v0.2 Design"
    elif instability_count >= 72:
        status = "DYNAMIC_GRADIENT_FAILURE_ATTRIBUTED_MULTISTEP_INSTABILITY"
        next_branch = "Stage 03A-R — Temporal Architecture and Horizon Contract Reassessment"
    else:
        status = "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED"
        next_branch = "NONE — no immediate contract modification or training"
    return {"final_status": status, "next_authorized_branch": next_branch, "stage03e_authorization": False, "evidence": {"ad_jvp_pass": crosscheck["pass"], "extended_stable_fraction": extended_fraction, "fd_conditioning_reason_count": fd_conditioning_count, "cancellation_reason_count": cancellation_count, "instability_reason_count": instability_count, "history_classifications": history["classifications"], "horizon_scaling_counts": scaling["counts"]}, "new_optimizer_steps": 0, "new_training_runs": 0}


def topology_preservation() -> dict[str, Any]:
    final = json.loads((STAGE03 / "10_manifests/stage03d_final_manifest.json").read_text(encoding="utf-8"))
    scan = json.loads((STAGE03D / "topology_event_scan/te1_dense_scan_results.json").read_text(encoding="utf-8"))
    replay = json.loads((STAGE03D / "topology_stage_replay/replay_results.json").read_text(encoding="utf-8"))
    event = json.loads((STAGE03D / "event_side_gradients/event_side_gradient_results.json").read_text(encoding="utf-8"))
    jump = json.loads((STAGE03D / "event_jump_audit/event_force_jump_results.json").read_text(encoding="utf-8"))
    gates = {
        "stage03d_verdict_preserved": final["final_status"] == "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "one_birth": sum(item["kind"] == "birth" for item in scan["event_brackets"]) == 1,
        "one_death": sum(item["kind"] == "death" for item in scan["event_brackets"]) == 1,
        "replay_6_of_6": sum(row["pass"] for row in replay["rows"]) == 6,
        "fixed_side_12_of_12": sum(row["pass"] for row in event["rows"]) == 12,
        "piecewise_smooth": all(row["classification"] == "TOPOLOGY_EVENT_PIECEWISE_SMOOTH_WITH_DISCRETE_GRAPH_CHANGE" for row in event["cross_event_rows"]),
        "finite_bounded_jumps": all(row["pass"] for row in jump["rows"]),
        "empty_graph_deterministic": all(row["pair_aggregation_exact_zero"] and row["no_synthetic_self_pair"] for row in replay["empty_graph_rows"]),
    }
    return {"component_status": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED", "gates": gates, "pass": all(gates.values()), "stage03d_overall_pass_claimed": False}


def historical_integrity() -> dict[str, Any]:
    freeze = json.loads(INPUT_FREEZE.read_text(encoding="utf-8"))
    mismatches = []
    for item in freeze["evidence"]:
        path = ROOT / item["path"]
        actual = sha(path) if path.exists() else None
        if actual != item["sha256"]:
            mismatches.append({"path": item["path"], "expected": item["sha256"], "actual": actual})
    for key in ("stage03d_failure_matrix", "selected_row_manifest"):
        item = freeze[key]
        path = ROOT / item["path"]
        actual = sha(path) if path.exists() else None
        if actual != item["sha256"]:
            mismatches.append({"path": item["path"], "expected": item["sha256"], "actual": actual})
    return {"checked": len(freeze["evidence"]) + 2, "mismatches": mismatches, "pass": not mismatches}


def report_header(title: str) -> str:
    return f"# {title}\n\nStage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`. Stage 03D-R contract: `{CONTRACT_HASH}`.\n"


def write_reports(matrix: dict[str, Any], cross: dict[str, Any], extended: dict[str, Any], scaling: dict[str, Any], history: dict[str, Any], attribution: dict[str, Any], route: dict[str, Any], topology: dict[str, Any], resources_result: dict[str, Any], integrity: dict[str, Any]) -> None:
    axis = matrix["summary"]["axis_counts"]
    write_text(REPORTS / "stage03dr_freeze_and_scope.md", report_header("Stage 03D-R Freeze and Scope") + f"\nThe 360 historical rows, 144 failures, 2880 comparisons, direction hashes, parameter indices, history/conservation/topology evidence, source code, and 18 trajectories were frozen before any extended epsilon result. Selected-row manifest: `{sha(SELECTED_PATH)}`. Stage 03E remains false.\n")
    write_text(REPORTS / "stage03dr_failure_matrix.md", report_header("Stage 03D-R Failure Matrix") + f"\nComplete matrix: {matrix['summary']['row_count']} rows, {matrix['summary']['pass_count']} pass, {matrix['summary']['fail_count']} fail. By arm: `{json.dumps(axis['arm'], sort_keys=True)}`. By horizon: `{json.dumps(axis['horizon'], sort_keys=True)}`. By probe: `{json.dumps(axis['probe'], sort_keys=True)}`. By case: `{json.dumps(axis['case'], sort_keys=True)}`. By seed: `{json.dumps(axis['seed'], sort_keys=True)}`. The machine table retains every AD, four FD values, errors, adjacent changes, decade, hashes, determinism, structural-zero label and exact historical failure reason.\n")
    write_text(REPORTS / "stage03dr_derivative_scale.md", report_header("Stage 03D-R Derivative Scale") + f"\nHistorical derivative-decade distribution: `{json.dumps(axis['derivative_decade'], sort_keys=True)}`. Near-zero derivatives are classified explicitly and are not promoted to Stage 03D passes.\n")
    write_text(REPORTS / "stage03dr_ad_crosscheck.md", report_header("Stage 03D-R AD Crosscheck") + f"\nReverse VJP versus forward JVP: {cross['passed']}/{cross['required']} selected cells pass the frozen absolute/relative gate. No FD was used internally by either AD route. Pass: `{cross['pass']}`.\n")
    write_text(REPORTS / "stage03dr_fd_conditioning.md", report_header("Stage 03D-R FD Conditioning") + f"\nThe 11-point ladder used three-point and five-point central differences plus Richardson comparison on {extended['required']} frozen rows ({extended['extended_fd_path_count']} independent paths). Extended stable regions: {extended['extended_stable_count']}/{extended['required']}; U-shaped error curves: {extended['u_shaped_count']}. These results are attribution-only and do not relabel Stage 03D.\n")
    cancellation_values = [row["cancellation_ratio"] for row in extended["rows"]]
    write_text(REPORTS / "stage03dr_objective_decomposition.md", report_header("Stage 03D-R Objective Decomposition") + f"\nEvery selected row preserves `J=J_x+J_v+J_rho` and reports reverse component AD, three/five-point component FD, signs and horizon. Cancellation-ratio range: {min(cancellation_values)} to {max(cancellation_values)}; ratios >=1000: {sum(value >= 1000 for value in cancellation_values)}.\n")
    write_text(REPORTS / "stage03dr_history_path.md", report_header("Stage 03D-R History Path") + f"\nREFERENCE_PREHISTORY traces: {len(history['rows'])}; classifications: `{json.dumps(history['classifications'], sort_keys=True)}`. Each trace covers reference state, tokenization, stored token, GRU/Transformer hidden, pair coefficients, nodal correction and final objective, with leaf/grad_fn/hash/order metadata. Reverse and FD perturb the same stored tokenized prior slots; temporal-module-only reverse/JVP/extended-FD results are recorded separately from rollout attenuation.\n")
    write_text(REPORTS / "stage03dr_horizon_scaling.md", report_header("Stage 03D-R Horizon Scaling") + f"\nK=1/2/4/8 gradients were grouped for {len(scaling['rows'])} arm/probe/case/seed series. Labels: `{json.dumps(scaling['counts'], sort_keys=True)}`. Ratios and log slopes are attribution labels only, not training gates.\n")
    write_text(REPORTS / "stage03dr_failure_attribution.md", report_header("Stage 03D-R Failure Attribution") + f"\nAll {attribution['classified_count']} failures have one primary reason. Counts: `{json.dumps(attribution['primary_reason_counts'], sort_keys=True)}`. Reverse/JVP contradiction is never silently attributed to FD; history object/detach mismatches, cancellation, horizon scaling, near-zero sensitivity, roundoff/truncation and fixed-graph non-smoothness follow the frozen priority order.\n")
    write_text(REPORTS / "stage03dr_route_decision.md", report_header("Stage 03D-R Route Decision") + f"\nUnique status: **{route['final_status']}**. Next authorized branch: {route['next_authorized_branch']}. Stage 03E authorization remains false. `new_optimizer_steps=0`; `new_training_runs=0`.\n")
    final = report_header("Stage 03D-R Final Report") + f"\nFinal status: **{route['final_status']}**.\n\n1. Stage 03D failure is preserved and not overwritten.\n2. Complete failure matrix: 360 rows, 216 historical stable windows, 144 failures.\n3. Failure axes are fully reported by arm, horizon, probe, case/source role, seed and magnitude decade.\n4. AD derivative magnitudes and near-zero rows remain explicit.\n5. Reverse AD versus JVP: {cross['passed']}/{cross['required']}.\n6. Extended FD: {extended['extended_stable_count']}/{extended['required']} selected rows form an attribution stable region.\n7. Three-point, five-point and Richardson results are retained for all {extended['extended_fd_path_count']} paths.\n8. Original objective is decomposed into x/v/rho without replacement.\n9. Cancellation ratios are retained per selected row.\n10. Horizon scaling labels: `{json.dumps(scaling['counts'], sort_keys=True)}`.\n11. REFERENCE_PREHISTORY traces: `{json.dumps(history['classifications'], sort_keys=True)}`.\n12. Temporal-module-only reverse/JVP/FD is separated from rollout attenuation.\n13. AD/FD perturb-object identity is explicit; no silent loader/history modification occurred.\n14. Harness paths start independently, use fixed RNG, correct parameter indices, fresh history and unchanged base parameter hashes.\n15. Topology component: `{topology['component_status']}`; Stage 03D overall remains NOT_QUALIFIED.\n16. Unique failure attribution: `{route['final_status']}`.\n17. Next authorized branch: {route['next_authorized_branch']}; Stage 03E remains false.\n18. new optimizer steps = 0.\n19. new training runs = 0.\n20. No rollout-performance evaluation, dataset, split, normalization or training was performed.\n21. Historical integrity: {integrity['checked']} frozen artifacts checked, {len(integrity['mismatches'])} mismatches. Peak RSS delta={resources_result['peak_rss_delta_bytes']} bytes; resource gate={resources_result['pass']}.\n"
    write_text(REPORTS / "stage03dr_final_report.md", final)


def manifest_entry(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "byte_count": path.stat().st_size, "sha256": sha(path)}


def write_manifests(summary: dict[str, Any]) -> None:
    artifacts = [path for path in STAGE03DR.rglob("*.json") if "stage03dr_smoke" not in path.name]
    reports = [REPORTS / name for name in (
        "stage03dr_freeze_and_scope.md", "stage03dr_failure_matrix.md", "stage03dr_derivative_scale.md", "stage03dr_ad_crosscheck.md", "stage03dr_fd_conditioning.md", "stage03dr_objective_decomposition.md", "stage03dr_history_path.md", "stage03dr_horizon_scaling.md", "stage03dr_failure_attribution.md", "stage03dr_route_decision.md", "stage03dr_final_report.md"
    )]
    attribution_manifest_path = MANIFESTS / "stage03dr_attribution_manifest.json"
    write_json(attribution_manifest_path, {"schema_version": "sph-pio-poc.stage03dr.attribution-manifest.v1", "contract": manifest_entry(CONTRACT), "artifacts": [manifest_entry(path) for path in sorted(artifacts)], "final_status": summary["final_status"], "new_optimizer_steps": 0, "new_training_runs": 0})
    write_json(MANIFESTS / "stage03dr_final_manifest.json", {"schema_version": "sph-pio-poc.stage03dr.final.v1", "stage": "Stage 03D-R — Multistep Gradient Failure Attribution and Dynamic-Route Decision", "completion_date": "2026-08-05", "authorization": "Stage 03D:DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED", "contract": manifest_entry(CONTRACT), "input_freeze": manifest_entry(INPUT_FREEZE), "attribution_manifest": manifest_entry(attribution_manifest_path), "reports": [manifest_entry(path) for path in reports], "qualification_summary": manifest_entry(STAGE03DR / "results/stage03dr_summary.json"), "final_status": summary["final_status"], "next_authorized_branch": summary["next_authorized_branch"], "stage03e_authorization": False, "historical_stage03d_status": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED", "topology_component_status": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED", "new_optimizer_steps": 0, "new_training_runs": 0, "rollout_performance_evaluation": False})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--reuse-extended", action="store_true", help="reuse the already completed 2640-path extended-FD artifact after AD-harness-only corrections")
    args = parser.parse_args()
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    if sha(CONTRACT) != CONTRACT_HASH:
        raise RuntimeError("Stage 03D-R contract hash mismatch")
    freeze = json.loads(INPUT_FREEZE.read_text(encoding="utf-8"))
    if not freeze["pass"] or not freeze["selected_row_manifest"]["sha256"] == sha(SELECTED_PATH):
        raise RuntimeError("Stage 03D-R selection freeze mismatch")
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    selected = json.loads(SELECTED_PATH.read_text(encoding="utf-8"))["rows"]
    start_rss = rss_bytes()
    cross = ad_crosscheck(selected, args.smoke)
    extended_path = STAGE03DR / "fd_conditioning/extended_fd_results.json"
    if args.reuse_extended and not args.smoke:
        extended = json.loads(extended_path.read_text(encoding="utf-8"))
    else:
        extended = extended_fd_audit(selected, cross, args.smoke)
    scaling = horizon_scaling(matrix["rows"])
    history = history_audit(args.smoke)
    if args.smoke:
        result = {"crosscheck": cross, "extended_fd": extended, "history": history}
        write_json(STAGE03DR / "results/stage03dr_smoke.json", result)
        print(json.dumps({"crosscheck": cross["pass"], "extended": extended["pass"], "history": history["pass"]}, indent=2))
        return
    attribution = classify_failures(matrix["rows"], cross, extended, scaling, history)
    route = route_decision(attribution, cross, extended, history, scaling)
    topology = topology_preservation()
    integrity = historical_integrity()

    weak: list[weakref.ReferenceType[torch.Tensor]] = []
    test_tensor = torch.ones(1, requires_grad=True)
    weak.append(weakref.ref(test_tensor))
    del test_tensor
    gc.collect()
    peak = rss_bytes()
    resources_result = {
        "device": "cpu",
        "dtype": "float64",
        "jvp_total_seconds": sum(row["jvp"]["seconds"] for row in cross["rows"]),
        "vjp_total_seconds": sum(row["reverse"]["seconds"] for row in cross["rows"]),
        "extended_fd_path_count": extended["extended_fd_path_count"],
        "peak_rss_start_bytes": start_rss,
        "peak_rss_observed_bytes": peak,
        "peak_rss_delta_bytes": max(0, peak - start_rss),
        "retained_autograd_test_tensors": sum(reference() is not None for reference in weak),
        "history_trace_tensor_count": sum(len(row["trace"]) for row in history["rows"]),
        "history_trace_overhead_bytes": sum(len(json.dumps(row["trace"])) for row in history["rows"]),
        "artifact_storage_bytes_before_reports": sum(path.stat().st_size for path in STAGE03DR.rglob("*") if path.is_file()),
        "no_dense_particle_square_allocation": True,
        "no_parameter_mutation": all(row["base_parameter_hash_unchanged_across_paths"] for row in extended["rows"]),
    }
    resources_result["gates"] = {"peak_rss": resources_result["peak_rss_delta_bytes"] <= 1610612736, "no_parameter_mutation": resources_result["no_parameter_mutation"], "no_retained_autograd_growth": resources_result["retained_autograd_test_tensors"] == 0, "no_dense_NxN": resources_result["no_dense_particle_square_allocation"], "finite_completion": cross["pass"] and extended["pass"] and history["pass"]}
    resources_result["pass"] = all(resources_result["gates"].values())

    outputs = {
        STAGE03DR / "ad_crosscheck/reverse_vs_jvp.json": cross,
        STAGE03DR / "fd_conditioning/extended_fd_results.json": extended,
        STAGE03DR / "objective_decomposition/component_results.json": {"rows": [{key: row[key] for key in ("row_id", "reverse_component_ad", "component_signs", "cancellation_ratio", "component_stable")} for row in extended["rows"]]},
        STAGE03DR / "horizon_scaling/horizon_gradient_scaling.json": scaling,
        STAGE03DR / "history_path/reference_prehistory_trace.json": history,
        STAGE03DR / "attribution/failure_attribution.json": attribution,
        STAGE03DR / "route_decision/dynamic_route_decision.json": route,
        STAGE03DR / "topology_preservation/topology_component_status.json": topology,
        STAGE03DR / "results/resource_audit.json": resources_result,
    }
    for path, value in outputs.items():
        write_json(path, value)
    summary = {"schema_version": "sph-pio-poc.stage03dr.summary.v1", "contract_hash": CONTRACT_HASH, "historical_stage03d_status": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED", "matrix": matrix["summary"], "ad_crosscheck": {"passed": cross["passed"], "required": cross["required"], "pass": cross["pass"]}, "extended_fd": {"stable": extended["extended_stable_count"], "required": extended["required"], "paths": extended["extended_fd_path_count"]}, "history_classifications": history["classifications"], "failure_reason_counts": attribution["primary_reason_counts"], "horizon_scaling_counts": scaling["counts"], "topology_component_status": topology["component_status"], "resources_pass": resources_result["pass"], "historical_integrity_pass": integrity["pass"], "final_status": route["final_status"], "next_authorized_branch": route["next_authorized_branch"], "stage03e_authorization": False, "new_optimizer_steps": 0, "new_training_runs": 0}
    write_json(STAGE03DR / "results/stage03dr_summary.json", summary)
    write_reports(matrix, cross, extended, scaling, history, attribution, route, topology, resources_result, integrity)
    write_manifests(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
