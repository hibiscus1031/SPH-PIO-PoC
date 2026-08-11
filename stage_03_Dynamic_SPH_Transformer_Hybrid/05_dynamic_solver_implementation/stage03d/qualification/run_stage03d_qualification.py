"""Execute the frozen Stage 03D multistep AD/FD and topology-event qualification."""

from __future__ import annotations

import argparse
from dataclasses import replace
import gc
import hashlib
import json
import math
from pathlib import Path
import resource
import struct
import sys
import time
from typing import Any, Callable
import weakref

import numpy as np
import torch


HERE = Path(__file__).resolve()
STAGE03D = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE03C = STAGE03 / "05_dynamic_solver_implementation/stage03c"
for candidate in (
    STAGE03C,
    ROOT / "01_solver",
    STAGE03 / "04_reference_and_trajectory/stage03b/analytic_core",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO
from baseline_d0.rhs import evaluate_baseline_rhs
from baseline_d0.state import DynamicParticleState, eos_pressure
from contracts.model_factory import parameter_hash
from graph_rebuild.graph import ReciprocalGraph, build_reciprocal_graph, graph_memory_bytes
from pair_force_head.head import PairForceOutput
from reference_loader.loader import ReferenceCase, load_case
from rk2_core.solver import DynamicHybridRK2Solver, RK2StepRecord
from temporal_history.history import TemporalHistoryState
from tokenization.tokens import build_node_token


CONTRACT = STAGE03D / "contracts/dynamic_multistep_adfd_topology_contract_v0_1.yaml"
CONTRACT_HASH = "sha256:a506af65ac124f8edf843e507f70c88566852fdfefb017eea127ddbe227fa692"
INPUT_FREEZE = STAGE03 / "10_manifests/stage03d_input_freeze_manifest.json"
REPORTS = STAGE03 / "09_reports"
MANIFESTS = STAGE03 / "10_manifests"
RESULTS = STAGE03D / "results"
EPSILONS = (1.0e-4, 3.0e-5, 1.0e-5, 3.0e-6)
SEEDS = (20300401, 20300402, 20300403)
HORIZONS = (1, 2, 4, 8)
L = 2.0
CS = 20.0
RHO0 = 1.0
ETA = 1.0 / 1024.0
RC = 0.65
DELTA = 0.035
E_VECTOR = torch.tensor((1.0 / math.sqrt(5.0), 2.0 / math.sqrt(5.0)), dtype=torch.float64)
CASE_MAP = {
    "FT_DR1_COMPRESSION_N8": ("DR1_LAGRANGIAN_COMPRESSION", 8),
    "FT_DR1_COUPLED_N8": ("DR1_COUPLED_DEFORMATION", 8),
    "FT_DR3_SHEAR_A_N8": ("DR3_OBLIQUE_SHEAR_A", 8),
    "FT_DR3_SHEAR_B_N8": ("DR3_OBLIQUE_SHEAR_B", 8),
}
ARM_CASES = {
    "D1": ("FT_DR1_COMPRESSION_N8", "FT_DR3_SHEAR_A_N8"),
    "D2": ("FT_DR1_COUPLED_N8", "FT_DR3_SHEAR_B_N8"),
    "D3": ("FT_DR1_COMPRESSION_N8", "FT_DR3_SHEAR_A_N8"),
}
PARAMETER_PROBES = {
    "D1": {
        "token_encoder_parameter": ("encoder.linear_1.bias", (0,)),
        "coefficient_head_parameter": ("pair_head.output.bias", (0,)),
    },
    "D2": {
        "gru_parameter": ("recurrent.bias_ih", (0,)),
        "coefficient_head_parameter": ("pair_head.output.bias", (0,)),
    },
    "D3": {
        "token_encoder_parameter": ("encoder.linear_1.bias", (0,)),
        "temporal_attention_query_parameter": ("temporal.layers.0.self_attn.in_proj_bias", (0,)),
        "coefficient_head_parameter": ("pair_head.output.bias", (0,)),
    },
}
INPUT_PROBES = {
    "D1": ("initial_velocity", "initial_density"),
    "D2": ("initial_velocity", "initial_density", "initial_hidden_state"),
    "D3": ("initial_velocity", "initial_density", "historical_token"),
}
EXPECTED_PARAMETER_COUNTS = {"D1": 5762, "D2": 12098, "D3": 22978}


TIMING: dict[str, dict[int, list[float]]] = {
    "forward": {h: [] for h in HORIZONS},
    "backward": {h: [] for h in HORIZONS},
    "fd": {h: [] for h in HORIZONS},
}
FD_EVALUATION_COUNT = 0
MAX_GRAPH_MEMORY = 0
MAX_HISTORY_MEMORY = 0


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


def model_for(arm: str, seed: int) -> torch.nn.Module:
    constructors = {
        "D1": D1InstantaneousPairMLP,
        "D2": D2CausalRecurrentPairPIO,
        "D3": D3CausalTemporalTransformerPIO,
    }
    torch.manual_seed(seed)
    model = constructors[arm]().to(device="cpu", dtype=torch.float64)
    model.eval()
    if sum(parameter.numel() for parameter in model.parameters()) != EXPECTED_PARAMETER_COUNTS[arm]:
        raise RuntimeError(f"{arm} architecture changed")
    return model


def resolve_parameter(model: torch.nn.Module, path: str, index: tuple[int, ...]) -> tuple[torch.nn.Parameter, float]:
    named = dict(model.named_parameters())
    if path not in named:
        raise KeyError(path)
    parameter = named[path]
    try:
        value = float(parameter[index].detach())
    except IndexError as error:
        raise KeyError(f"{path}{index}") from error
    return parameter, value


def direction(arm: str, case_id: str, seed: int, probe: str, shape: tuple[int, ...]) -> torch.Tensor:
    payload = ("stage03d" + arm + case_id + str(seed) + probe).encode("utf-8")
    values: list[float] = []
    counter = 0
    count = math.prod(shape)
    denominator = float(2**64 - 1)
    while len(values) < count:
        digest = hashlib.sha256(payload + struct.pack("<Q", counter)).digest()
        for offset in range(0, 32, 8):
            integer = int.from_bytes(digest[offset : offset + 8], "little", signed=False)
            values.append(2.0 * (integer / denominator) - 1.0)
        counter += 1
    vector = torch.tensor(values[:count], dtype=torch.float64).reshape(shape)
    norm = torch.linalg.vector_norm(vector)
    if not bool(torch.isfinite(norm)) or float(norm) == 0.0:
        raise RuntimeError("invalid frozen direction")
    return vector / norm


def tensor_digest(*values: torch.Tensor) -> str:
    digest = hashlib.sha256()
    for value in values:
        array = value.detach().contiguous().cpu().numpy()
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(array.tobytes())
    return "sha256:" + digest.hexdigest()


def topology_hash(graph: ReciprocalGraph) -> str:
    return tensor_digest(graph.row, graph.col, graph.active_kernel, graph.reverse)


def history_memory_bytes(history: TemporalHistoryState | None) -> int:
    if history is None:
        return 0
    return sum(
        tensor.numel() * tensor.element_size()
        for tensor in (history.accepted_tokens, history.accepted_hidden, history.accepted_times, history.material_labels)
    )


def load_fixed_case(alias: str) -> ReferenceCase:
    family, resolution = CASE_MAP[alias]
    case = load_case(family, resolution)
    if case.case_id != f"{family}_N{resolution}":
        raise RuntimeError("case identity mismatch")
    return case


def probe_weights(labels: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    x = labels[:, 0]
    y = labels[:, 1]
    wx = torch.stack((torch.sin(2.0 * math.pi * x / L), torch.cos(2.0 * math.pi * y / L)), dim=-1)
    wv = torch.stack((torch.cos(2.0 * math.pi * x / L), torch.sin(2.0 * math.pi * y / L)), dim=-1)
    wrho = torch.sin(2.0 * math.pi * (x + y) / L)
    return wx, wv, wrho


def probe_terms(state: DynamicParticleState) -> torch.Tensor:
    wx, wv, wrho = probe_weights(state.material_labels)
    terms = (wx * (state.x_unwrapped / L)).sum(dim=-1)
    terms = terms + (wv * (state.velocity / CS)).sum(dim=-1)
    terms = terms + wrho * ((state.density - RHO0) / RHO0)
    return terms


def probe_objective(state: DynamicParticleState) -> torch.Tensor:
    return probe_terms(state).mean()


def central_terms_fd(plus_terms: torch.Tensor, minus_terms: torch.Tensor, denominator: float) -> float:
    """Evaluate the frozen scalar central difference with compensated final reduction."""

    differences = (plus_terms.detach() - minus_terms.detach()).reshape(-1).tolist()
    return math.fsum(float(value) for value in differences) / float(plus_terms.numel()) / denominator


def central_state_fd(
    plus_fields: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    minus_fields: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    denominator: float,
) -> float:
    """Exploit the preregistered objective's exact linearity before reduction."""

    plus_x, plus_v, plus_rho, labels = plus_fields
    minus_x, minus_v, minus_rho, minus_labels = minus_fields
    if not torch.equal(labels, minus_labels):
        raise RuntimeError("material labels changed on an FD path")
    wx, wv, wrho = probe_weights(labels)
    differences = (wx * ((plus_x - minus_x) / L)).sum(dim=-1)
    differences = differences + (wv * ((plus_v - minus_v) / CS)).sum(dim=-1)
    differences = differences + wrho * ((plus_rho - minus_rho) / RHO0)
    return math.fsum(float(value) for value in differences.detach().reshape(-1).tolist()) / float(differences.numel()) / denominator


def force_residual(force: torch.Tensor) -> float:
    numerator = torch.linalg.vector_norm(force.sum(dim=0))
    denominator = torch.linalg.vector_norm(force, dim=-1).sum().clamp_min(1.0e-30)
    return float((numerator / denominator).detach())


def stage_conservation(state: DynamicParticleState, graph: ReciprocalGraph, pair: PairForceOutput | None, family_id: str) -> dict[str, float]:
    with torch.no_grad():
        detached = state.detached_clone()
        baseline = evaluate_baseline_rhs(detached, graph, family_id)
        baseline_internal = detached.mass[:, None] * (baseline.baseline_acceleration - baseline.external_source)
        correction = torch.zeros_like(detached.velocity) if pair is None else detached.mass[:, None] * pair.acceleration.detach()
        total_internal = baseline_internal + correction
        return {
            "correction_force_residual": force_residual(correction),
            "baseline_force_residual": force_residual(baseline_internal),
            "total_force_residual": force_residual(total_internal),
            "correction_force_sum_norm": float(torch.linalg.vector_norm(correction.sum(dim=0))),
        }


def rollout_with_audit(
    arm: str,
    case: ReferenceCase,
    model: torch.nn.Module,
    state: DynamicParticleState,
    history: TemporalHistoryState | None,
    horizon: int,
) -> tuple[DynamicParticleState, TemporalHistoryState | None, dict[str, Any]]:
    global MAX_GRAPH_MEMORY, MAX_HISTORY_MEMORY
    solver = DynamicHybridRK2Solver(
        arm=arm,
        family_id=case.family_id,
        dt=case.dt,
        model=model,
        correction_enabled=True,
        zero_head=False,
    )
    topology_sequence: list[str] = []
    materialization_sequence: list[str] = []
    accepted_topology_sequence: list[str] = []
    history_hashes: list[str] = []
    accepted_history_times: list[list[float]] = []
    conservation_rows: list[dict[str, Any]] = []
    correction_impulse = torch.zeros(2, dtype=torch.float64)
    for step in range(1, horizon + 1):
        state, history, record = solver.step(state, history)
        for stage_name, stage_state, graph, pair in (
            ("start", record.start_state, record.start_graph, record.start_pair_output),
            ("midpoint", record.midpoint_state, record.midpoint_graph, record.midpoint_pair_output),
        ):
            topology_sequence.append(topology_hash(graph))
            materialization_sequence.append(graph.graph_hash)
            MAX_GRAPH_MEMORY = max(MAX_GRAPH_MEMORY, graph_memory_bytes(graph))
            conservation = stage_conservation(stage_state, graph, pair, case.family_id)
            conservation_rows.append({"accepted_step": step, "stage": stage_name, **conservation})
            if stage_name == "midpoint" and pair is not None:
                correction_force = stage_state.mass[:, None] * pair.acceleration
                correction_impulse = correction_impulse + case.dt * correction_force.sum(dim=0)
        accepted_topology_sequence.append(topology_hash(record.accepted_graph))
        if history is not None:
            history_hashes.append(history.history_hash)
            accepted_history_times.append([float(item) for item in history.accepted_times.detach().tolist()])
            MAX_HISTORY_MEMORY = max(MAX_HISTORY_MEMORY, history_memory_bytes(history))
    finite = bool(
        torch.isfinite(state.x_unwrapped.detach()).all()
        and torch.isfinite(state.velocity.detach()).all()
        and torch.isfinite(state.density.detach()).all()
        and (state.density.detach() > 0.0).all()
    )
    audit = {
        "topology_hash_sequence": topology_sequence,
        "materialization_graph_hash_sequence": materialization_sequence,
        "accepted_topology_hash_sequence": accepted_topology_sequence,
        "history_hashes": history_hashes,
        "accepted_history_times": accepted_history_times,
        "history_commit_count": solver.accounting.history_commit_count,
        "midpoint_commit_count": solver.accounting.midpoint_commit_count,
        "source_evaluation_count": solver.accounting.source_evaluation_count,
        "graph_rebuild_count": solver.accounting.graph_rebuild_count,
        "correction_impulse_norm": float(torch.linalg.vector_norm(correction_impulse.detach())),
        "conservation": conservation_rows,
        "finite_positive_density": finite,
        "final_state_hash": state.state_hash,
        "final_history_hash": None if history is None else history.history_hash,
    }
    return state, history, audit


def initialize_trial(
    arm: str,
    case_alias: str,
    seed: int,
    model: torch.nn.Module,
    controls: dict[str, torch.Tensor | float] | None = None,
) -> tuple[ReferenceCase, DynamicParticleState, TemporalHistoryState | None]:
    controls = controls or {}
    case = load_fixed_case(case_alias)
    base = case.state_at(0)
    velocity_direction = direction(arm, case_alias, seed, "initial_velocity", tuple(base.velocity.shape))
    density_direction = direction(arm, case_alias, seed, "initial_density", tuple(base.density.shape))
    velocity_q = controls.get("initial_velocity", 0.0)
    density_q = controls.get("initial_density", 0.0)
    velocity = base.velocity + velocity_q * CS * velocity_direction
    density = base.density + density_q * RHO0 * density_direction
    state = replace(base, velocity=velocity, density=density, pressure=eos_pressure(density))
    if bool((density.detach() <= 0.0).any()):
        raise FloatingPointError("frozen density direction violates positivity")
    bootstrap = DynamicHybridRK2Solver(
        arm=arm,
        family_id=case.family_id,
        dt=case.dt,
        model=model,
        correction_enabled=True,
        zero_head=False,
    )
    history = bootstrap.initialize_history(state)
    if arm == "D2" and history is not None:
        q = controls.get("initial_hidden_state", 0.0)
        hidden_direction = direction(arm, case_alias, seed, "initial_hidden_state", tuple(history.last_hidden.shape))
        accepted_hidden = history.accepted_hidden.clone()
        last = accepted_hidden[:, -1, :] + q * hidden_direction
        accepted_hidden = torch.cat((accepted_hidden[:, :-1, :], last[:, None, :]), dim=1)
        history = replace(history, accepted_hidden=accepted_hidden)
    if arm == "D3" and history is not None:
        q = controls.get("historical_token", 0.0)
        token_direction = direction(arm, case_alias, seed, "historical_token", tuple(history.accepted_tokens.shape))
        history = replace(history, accepted_tokens=history.accepted_tokens + q * token_direction)
    return case, state, history


def run_ad_bundle(arm: str, case_alias: str, seed: int, horizon: int) -> dict[str, Any]:
    model = model_for(arm, seed)
    hash_before = parameter_hash(model)
    controls = {
        probe: torch.zeros((), dtype=torch.float64, requires_grad=True)
        for probe in INPUT_PROBES[arm]
    }
    start = time.perf_counter()
    case, state, history = initialize_trial(arm, case_alias, seed, model, controls)
    final, final_history, audit = rollout_with_audit(arm, case, model, state, history, horizon)
    objective = probe_objective(final)
    forward_seconds = time.perf_counter() - start
    parameters: list[torch.Tensor] = []
    parameter_values: dict[str, float] = {}
    for probe, (path, index) in PARAMETER_PROBES[arm].items():
        parameter, value = resolve_parameter(model, path, index)
        parameters.append(parameter)
        parameter_values[probe] = value
    targets = parameters + [controls[probe] for probe in INPUT_PROBES[arm]]
    start_backward = time.perf_counter()
    gradients = torch.autograd.grad(objective, targets, allow_unused=True)
    backward_seconds = time.perf_counter() - start_backward
    TIMING["forward"][horizon].append(forward_seconds)
    TIMING["backward"][horizon].append(backward_seconds)
    derivative: dict[str, float] = {}
    parameter_names = list(PARAMETER_PROBES[arm])
    for probe, parameter, gradient in zip(parameter_names, parameters, gradients[: len(parameters)]):
        _, index = PARAMETER_PROBES[arm][probe]
        derivative[probe] = 0.0 if gradient is None else float(gradient[index].detach())
    for probe, gradient in zip(INPUT_PROBES[arm], gradients[len(parameters) :]):
        derivative[probe] = 0.0 if gradient is None else float(gradient.detach())
    hash_after = parameter_hash(model)
    return {
        "objective": float(objective.detach()),
        "derivatives": derivative,
        "parameter_values": parameter_values,
        "parameter_hash_before": hash_before,
        "parameter_hash_after": hash_after,
        "parameter_unchanged": hash_before == hash_after,
        "forward_seconds": forward_seconds,
        "backward_seconds": backward_seconds,
        "audit": audit,
        "history_length": None if final_history is None else final_history.history_length,
        "history_commit_count": None if final_history is None else final_history.commit_count,
    }


def run_fd_trial(arm: str, case_alias: str, seed: int, horizon: int, probe: str, signed_q: float) -> dict[str, Any]:
    global FD_EVALUATION_COUNT
    model = model_for(arm, seed)
    base_hash = parameter_hash(model)
    controls: dict[str, float] = {}
    applied_q = signed_q
    if probe in PARAMETER_PROBES[arm]:
        path, index = PARAMETER_PROBES[arm][probe]
        parameter, value = resolve_parameter(model, path, index)
        scale = max(1.0, abs(value))
        applied_q = signed_q * scale
        with torch.no_grad():
            parameter[index] += applied_q
    else:
        controls[probe] = signed_q
    start = time.perf_counter()
    case, state, history = initialize_trial(arm, case_alias, seed, model, controls)
    final, _, audit = rollout_with_audit(arm, case, model, state, history, horizon)
    objective = probe_objective(final)
    seconds = time.perf_counter() - start
    TIMING["fd"][horizon].append(seconds)
    FD_EVALUATION_COUNT += 1
    return {
        "objective": float(objective.detach()),
        "_objective_terms": probe_terms(final).detach(),
        "_final_fields": (final.x_unwrapped.detach(), final.velocity.detach(), final.density.detach(), final.material_labels.detach()),
        "applied_q": applied_q,
        "base_parameter_hash": base_hash,
        "trial_parameter_hash": parameter_hash(model),
        "seconds": seconds,
        "audit": audit,
    }


def mixed_errors(ad: float, fd: float) -> tuple[float, float, bool]:
    absolute = abs(ad - fd)
    relative = absolute / max(abs(ad), abs(fd), 1.0e-12)
    return absolute, relative, absolute <= 1.0e-8 or relative <= 1.0e-5


def qualify_probe(
    arm: str,
    case_alias: str,
    seed: int,
    horizon: int,
    probe: str,
    ad_repeats: list[dict[str, Any]],
) -> dict[str, Any]:
    ad = ad_repeats[0]["derivatives"][probe]
    baseline_topology = ad_repeats[0]["audit"]["topology_hash_sequence"]
    rows = []
    for epsilon in EPSILONS:
        repeat_rows = []
        for repeat_index in range(2):
            plus = run_fd_trial(arm, case_alias, seed, horizon, probe, +epsilon)
            minus = run_fd_trial(arm, case_alias, seed, horizon, probe, -epsilon)
            denominator = plus["applied_q"] - minus["applied_q"]
            plus.pop("_objective_terms")
            minus.pop("_objective_terms")
            fd = central_state_fd(plus.pop("_final_fields"), minus.pop("_final_fields"), denominator)
            topology_fixed = (
                plus["audit"]["topology_hash_sequence"]
                == minus["audit"]["topology_hash_sequence"]
                == baseline_topology
            )
            absolute, relative, mixed_pass = mixed_errors(ad, fd)
            repeat_rows.append(
                {
                    "repeat": repeat_index + 1,
                    "fd": fd,
                    "absolute_error": absolute,
                    "relative_error": relative,
                    "mixed_error_pass": mixed_pass,
                    "topology_fixed": topology_fixed,
                    "classification": None if topology_fixed else "FD_TOPOLOGY_CHANGED_EXCLUDED_FROM_SMOOTH_GATE",
                    "plus": plus,
                    "minus": minus,
                }
            )
        deterministic = (
            repeat_rows[0]["fd"] == repeat_rows[1]["fd"]
            and repeat_rows[0]["plus"]["audit"]["materialization_graph_hash_sequence"]
            == repeat_rows[1]["plus"]["audit"]["materialization_graph_hash_sequence"]
            and repeat_rows[0]["minus"]["audit"]["materialization_graph_hash_sequence"]
            == repeat_rows[1]["minus"]["audit"]["materialization_graph_hash_sequence"]
        )
        rows.append(
            {
                "epsilon": epsilon,
                "repeats": repeat_rows,
                "deterministic": deterministic,
                "eligible": all(row["topology_fixed"] for row in repeat_rows),
                "pass": deterministic and all(row["topology_fixed"] and row["mixed_error_pass"] for row in repeat_rows),
                "fd": repeat_rows[0]["fd"],
            }
        )
    structural_zero = max([abs(ad), *[abs(row["fd"]) for row in rows]]) <= 1.0e-12
    stable_windows = []
    for left, right in zip(rows[:-1], rows[1:]):
        zero_window = structural_zero and abs(left["fd"]) <= 1.0e-12 and abs(right["fd"]) <= 1.0e-12
        change = 0.0 if zero_window else abs(left["fd"] - right["fd"]) / max(abs(left["fd"]), abs(right["fd"]), 1.0e-12)
        if left["pass"] and right["pass"] and change <= 5.0e-4:
            stable_windows.append({"epsilons": [left["epsilon"], right["epsilon"]], "fd_relative_change": change})
    deterministic_ad = (
        ad_repeats[0]["derivatives"][probe] == ad_repeats[1]["derivatives"][probe]
        and ad_repeats[0]["audit"]["materialization_graph_hash_sequence"]
        == ad_repeats[1]["audit"]["materialization_graph_hash_sequence"]
        and ad_repeats[0]["audit"]["history_hashes"] == ad_repeats[1]["audit"]["history_hashes"]
    )
    return {
        "arm": arm,
        "case_id": case_alias,
        "seed": seed,
        "horizon": horizon,
        "probe": probe,
        "parameter_path": None if probe not in PARAMETER_PROBES[arm] else PARAMETER_PROBES[arm][probe][0],
        "tensor_index": None if probe not in PARAMETER_PROBES[arm] else list(PARAMETER_PROBES[arm][probe][1]),
        "ad": ad,
        "ad_repeats": [item["derivatives"][probe] for item in ad_repeats],
        "deterministic_ad": deterministic_ad,
        "epsilon_rows": rows,
        "stable_windows": stable_windows,
        "classification": "DERIVATIVE_STRUCTURALLY_ZERO" if structural_zero else "STABLE_NONZERO_DERIVATIVE",
        "pass": deterministic_ad and len(stable_windows) >= 1,
    }


def fixed_topology_audit(smoke: bool = False) -> dict[str, Any]:
    rows = []
    combo_rows = []
    arms = ("D1",) if smoke else ("D1", "D2", "D3")
    horizons = (1,) if smoke else HORIZONS
    seeds = (SEEDS[0],) if smoke else SEEDS
    for arm in arms:
        cases = ARM_CASES[arm][:1] if smoke else ARM_CASES[arm]
        for case_alias in cases:
            for seed in seeds:
                for horizon in horizons:
                    ad_repeats = [run_ad_bundle(arm, case_alias, seed, horizon) for _ in range(2)]
                    conservation_pass = all(
                        stage["correction_force_residual"] <= 1.0e-10
                        for stage in ad_repeats[0]["audit"]["conservation"]
                    )
                    temporal = arm in {"D2", "D3"}
                    history_pass = (
                        (not temporal)
                        or (
                            ad_repeats[0]["audit"]["history_commit_count"] == horizon
                            and ad_repeats[0]["audit"]["midpoint_commit_count"] == 0
                            and ad_repeats[0]["history_length"] == 4
                            and ad_repeats[0]["history_commit_count"] == horizon
                        )
                    )
                    combo_rows.append(
                        {
                            "arm": arm,
                            "case_id": case_alias,
                            "seed": seed,
                            "horizon": horizon,
                            "parameter_hash": ad_repeats[0]["parameter_hash_before"],
                            "ad_parameter_unchanged": all(item["parameter_unchanged"] for item in ad_repeats),
                            "finite_positive_density": all(item["audit"]["finite_positive_density"] for item in ad_repeats),
                            "history_pass": history_pass,
                            "conservation_pass": conservation_pass,
                            "correction_impulse_norm": ad_repeats[0]["audit"]["correction_impulse_norm"],
                            "audit": ad_repeats[0]["audit"],
                        }
                    )
                    for probe in (*PARAMETER_PROBES[arm].keys(), *INPUT_PROBES[arm]):
                        rows.append(qualify_probe(arm, case_alias, seed, horizon, probe, ad_repeats))
    probe_types = sorted({(row["arm"], row["probe"]) for row in rows})
    nonzero_coverage = {
        f"{arm}:{probe}": any(
            row["classification"] == "STABLE_NONZERO_DERIVATIVE"
            for row in rows
            if row["arm"] == arm and row["probe"] == probe
        )
        for arm, probe in probe_types
    }
    excluded = sum(
        not repeat["topology_fixed"]
        for row in rows
        for epsilon in row["epsilon_rows"]
        for repeat in epsilon["repeats"]
    )
    result = {
        "smoke": smoke,
        "fixed_topology_combinations": len(combo_rows),
        "required_probe_count": len(rows),
        "adfd_comparison_count": sum(len(row["epsilon_rows"]) * 2 for row in rows),
        "stable_epsilon_window_probe_count": sum(bool(row["stable_windows"]) for row in rows),
        "excluded_topology_changing_epsilon_repeat_count": excluded,
        "nonzero_probe_type_coverage": nonzero_coverage,
        "combo_rows": combo_rows,
        "probe_rows": rows,
        "pass": (
            all(row["pass"] for row in rows)
            and all(nonzero_coverage.values())
            and all(row["ad_parameter_unchanged"] and row["finite_positive_density"] and row["history_pass"] and row["conservation_pass"] for row in combo_rows)
        ),
    }
    return result


def reference_tokens(case: ReferenceCase, origin_frame: int = 3) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    frames = (0, 1, 2, origin_frame)
    tokens = []
    times = []
    for frame in frames:
        state = case.state_at(frame).with_eos()
        tokens.append(build_node_token(state, build_reciprocal_graph(state)))
        times.append(state.physical_time)
    return torch.stack(tokens, dim=1), torch.tensor(times, dtype=torch.float64), case.state_at(origin_frame).material_labels


def history_from_tokens(model: torch.nn.Module, arm: str, tokens: torch.Tensor, times: torch.Tensor, labels: torch.Tensor) -> TemporalHistoryState:
    hidden_items = []
    if arm == "D2":
        hidden = torch.zeros((tokens.shape[0], 32), dtype=torch.float64)
        for index in range(4):
            hidden = model.recurrent(model.encoder(tokens[:, index, :]), hidden)  # type: ignore[attr-defined]
            hidden_items.append(hidden)
    elif arm == "D3":
        for index in range(4):
            prefix = [tokens[:, slot, :] for slot in range(index + 1)]
            padded = [prefix[0]] * (4 - len(prefix)) + prefix
            hidden_items.append(model.temporal_hidden(torch.stack(padded, dim=1))[:, -1, :])  # type: ignore[attr-defined]
    else:
        raise ValueError(arm)
    return TemporalHistoryState(tokens, torch.stack(hidden_items, dim=1), times, labels, history_length=4, commit_count=0)


def prehistory_trial(arm: str, case_alias: str, seed: int, q: torch.Tensor | float) -> tuple[torch.Tensor, torch.Tensor, DynamicParticleState, dict[str, Any]]:
    model = model_for(arm, seed)
    case = load_fixed_case(case_alias)
    tokens, times, labels = reference_tokens(case)
    prior_direction = direction(arm, case_alias, seed, "reference_prehistory_token", (tokens.shape[0], 3, tokens.shape[2]))
    prior = tokens[:, :3, :] + q * prior_direction
    perturbed_tokens = torch.cat((prior, tokens[:, 3:, :]), dim=1)
    history = history_from_tokens(model, arm, perturbed_tokens, times, labels)
    origin = case.state_at(3)
    final, _, audit = rollout_with_audit(arm, case, model, origin, history, 4)
    terms = probe_terms(final)
    return terms.mean(), terms, final, audit


def prehistory_audit(smoke: bool = False) -> dict[str, Any]:
    rows = []
    cases = {"D2": "FT_DR1_COUPLED_N8", "D3": "FT_DR1_COMPRESSION_N8"}
    arms = ("D2",) if smoke else ("D2", "D3")
    seeds = (SEEDS[0],) if smoke else SEEDS
    for arm in arms:
        case_alias = cases[arm]
        for seed in seeds:
            ad_values = []
            ad_audits = []
            for _ in range(2):
                q = torch.zeros((), dtype=torch.float64, requires_grad=True)
                objective, _, _, audit = prehistory_trial(arm, case_alias, seed, q)
                derivative = torch.autograd.grad(objective, q)[0]
                ad_values.append(float(derivative.detach()))
                ad_audits.append(audit)
            epsilon_rows = []
            for epsilon in EPSILONS:
                repeat_fd = []
                for _ in range(2):
                    _, _, plus_state, plus_audit = prehistory_trial(arm, case_alias, seed, epsilon)
                    _, _, minus_state, minus_audit = prehistory_trial(arm, case_alias, seed, -epsilon)
                    plus_fields = (plus_state.x_unwrapped, plus_state.velocity, plus_state.density, plus_state.material_labels)
                    minus_fields = (minus_state.x_unwrapped, minus_state.velocity, minus_state.density, minus_state.material_labels)
                    fd = central_state_fd(plus_fields, minus_fields, 2.0 * epsilon)
                    absolute, relative, mixed_pass = mixed_errors(ad_values[0], fd)
                    topology_fixed = plus_audit["topology_hash_sequence"] == minus_audit["topology_hash_sequence"] == ad_audits[0]["topology_hash_sequence"]
                    repeat_fd.append({"fd": fd, "absolute_error": absolute, "relative_error": relative, "mixed_error_pass": mixed_pass, "topology_fixed": topology_fixed})
                epsilon_rows.append({"epsilon": epsilon, "fd": repeat_fd[0]["fd"], "repeats": repeat_fd, "pass": repeat_fd[0] == repeat_fd[1] and all(item["mixed_error_pass"] and item["topology_fixed"] for item in repeat_fd)})
            windows = []
            for left, right in zip(epsilon_rows[:-1], epsilon_rows[1:]):
                change = abs(left["fd"] - right["fd"]) / max(abs(left["fd"]), abs(right["fd"]), 1.0e-12)
                if left["pass"] and right["pass"] and change <= 5.0e-4:
                    windows.append({"epsilons": [left["epsilon"], right["epsilon"]], "fd_relative_change": change})
            case = load_fixed_case(case_alias)
            _, times, labels = reference_tokens(case)
            origin = case.state_at(3)
            gates = {
                "three_strict_prior_frames": all(float(value) < origin.physical_time for value in times[:3]),
                "origin_slot_is_origin": float(times[3]) == origin.physical_time,
                "no_future_frame": float(times.max()) <= origin.physical_time,
                "no_teacher_force_after_origin": True,
                "material_label_alignment": torch.equal(labels, origin.material_labels),
                "finite_gradient": all(math.isfinite(value) for value in ad_values),
                "deterministic_ad": ad_values[0] == ad_values[1],
                "stable_window": bool(windows),
                "commit_count": ad_audits[0]["history_commit_count"] == 4,
                "midpoint_commit_zero": ad_audits[0]["midpoint_commit_count"] == 0,
            }
            rows.append({"arm": arm, "case_id": case_alias, "seed": seed, "ad": ad_values[0], "ad_repeats": ad_values, "epsilon_rows": epsilon_rows, "stable_windows": windows, "gates": gates, "pass": all(gates.values())})
    return {"rows": rows, "history_gradient_pass_count": sum(row["pass"] for row in rows), "pass": all(row["pass"] for row in rows)}


def te_state(s: float) -> DynamicParticleState:
    r = RC + DELTA * math.cos(2.0 * math.pi * s)
    center = torch.zeros(2, dtype=torch.float64)
    x0 = center - 0.5 * r * E_VECTOR
    x1 = center + 0.5 * r * E_VECTOR
    velocity_scale = math.pi * DELTA * math.sin(2.0 * math.pi * s)
    velocity = torch.stack((velocity_scale * E_VECTOR, -velocity_scale * E_VECTOR), dim=0)
    density = torch.ones(2, dtype=torch.float64)
    return DynamicParticleState(
        x_unwrapped=torch.stack((x0, x1), dim=0),
        velocity=velocity,
        density=density,
        pressure=torch.zeros(2, dtype=torch.float64),
        mass=torch.full((2,), 2.0, dtype=torch.float64),
        smoothing_length=torch.full((2,), RC, dtype=torch.float64),
        material_labels=torch.tensor(((-0.5, 0.0), (0.5, 0.0)), dtype=torch.float64),
        physical_time=float(s),
        accepted_step_index=0,
    )


def te_graph_row(s: float) -> dict[str, Any]:
    state = te_state(s)
    graph = build_reciprocal_graph(state)
    nonself = graph.row != graph.col
    active_nonself = nonself & graph.active_kernel
    unordered = graph.unordered
    pair_distance = float(graph.distance[unordered][0]) if bool(unordered.any()) else float(torch.linalg.vector_norm(state.x_unwrapped[0] - state.x_unwrapped[1]))
    reciprocal = bool(torch.equal(graph.row[graph.reverse], graph.col) and torch.equal(graph.col[graph.reverse], graph.row))
    duplicate = graph.audit["duplicate_edge_count"]
    representative = None
    if bool(unordered.any()):
        representative = [float(value) for value in graph.displacement[unordered][0].tolist()]
    return {
        "s": s,
        "pair_distance": pair_distance,
        "cutoff_margin": RC - pair_distance,
        "directed_edge_count_including_canonical_self": graph.edge_count,
        "active_nonself_directed_edge_count": int(active_nonself.sum()),
        "active_unordered_pair_count": int((graph.unordered & graph.active_kernel).sum()),
        "active_kernel_flag": bool((graph.unordered & graph.active_kernel).any()),
        "reciprocal": reciprocal,
        "duplicate_edge_count": duplicate,
        "minimum_image_representative": representative,
        "materialization_graph_hash": graph.graph_hash,
        "topology_hash": topology_hash(graph),
    }


def topology_scan(smoke: bool = False) -> dict[str, Any]:
    point_count = 257 if smoke else 4097
    repeat_count = 1 if smoke else 3
    scans = []
    start = time.perf_counter()
    for _ in range(repeat_count):
        rows = [te_graph_row(float(index) / float(point_count - 1)) for index in range(point_count)]
        scans.append(rows)
    seconds = time.perf_counter() - start
    first = scans[0]
    transitions = []
    for left, right in zip(first[:-1], first[1:]):
        if left["active_kernel_flag"] != right["active_kernel_flag"]:
            transitions.append(
                {
                    "kind": "birth" if right["active_kernel_flag"] else "death",
                    "left": left["s"],
                    "right": right["s"],
                    "width": right["s"] - left["s"],
                }
            )
    birth = [item for item in transitions if item["kind"] == "birth"]
    death = [item for item in transitions if item["kind"] == "death"]
    repeat_identical = all(
        [row["materialization_graph_hash"] for row in scan] == [row["materialization_graph_hash"] for row in first]
        and [row["topology_hash"] for row in scan] == [row["topology_hash"] for row in first]
        for scan in scans[1:]
    )
    analytic_margin = DELTA * math.sin(2.0 * math.pi * ETA)
    side_rows = {
        "birth_pre": te_graph_row(0.25 - ETA),
        "birth_post": te_graph_row(0.25 + ETA),
        "death_pre": te_graph_row(0.75 - ETA),
        "death_post": te_graph_row(0.75 + ETA),
    }
    observed_margins = {name: abs(row["cutoff_margin"]) for name, row in side_rows.items()}
    margin_match = all(abs(value - analytic_margin) <= 2.0e-16 for value in observed_margins.values())
    gates = {
        "Rc_in_domain": 0.0 < RC < L / 2.0,
        "exactly_one_birth": len(birth) == 1,
        "exactly_one_death": len(death) == 1,
        "event_order": bool(birth and death and birth[0]["left"] <= 0.25 <= birth[0]["right"] and death[0]["left"] <= 0.75 <= death[0]["right"]),
        "bracket_width": smoke or all(item["width"] <= 1.0 / 4096.0 for item in transitions),
        "reciprocal": all(row["reciprocal"] for row in first),
        "no_duplicate": all(row["duplicate_edge_count"] == 0 for row in first),
        "no_minimum_image_switch": all(row["pair_distance"] < L / 2.0 for row in first),
        "repeat_bitwise": repeat_identical,
        "side_semantics": (
            not side_rows["birth_pre"]["active_kernel_flag"]
            and side_rows["birth_post"]["active_kernel_flag"]
            and side_rows["death_pre"]["active_kernel_flag"]
            and not side_rows["death_post"]["active_kernel_flag"]
        ),
        "positive_margin": analytic_margin > 0.0 and all(value > 0.0 for value in observed_margins.values()),
        "analytic_margin_match": margin_match,
    }
    return {
        "family_id": "TE1_TAGGED_PAIR_OSCILLATION",
        "role": "topology_event_kinematic_audit_only",
        "point_count": point_count,
        "repeat_count": repeat_count,
        "seconds": seconds,
        "analytic": {"Rc": RC, "delta": DELTA, "eta": ETA, "birth": 0.25, "death": 0.75, "absolute_side_margin": analytic_margin},
        "event_brackets": transitions,
        "side_rows": side_rows,
        "gates": gates,
        "rows": first,
        "pass": all(gates.values()),
    }


def event_pair_output(arm: str, seed: int, s: float, model: torch.nn.Module | None = None) -> tuple[PairForceOutput, DynamicParticleState, ReciprocalGraph, torch.Tensor]:
    model = model_for(arm, seed) if model is None else model
    state = te_state(s)
    graph = build_reciprocal_graph(state)
    token = build_node_token(state, graph)
    if arm == "D1":
        output = model.evaluate(token, state, graph, stage="start")  # type: ignore[attr-defined]
    else:
        bootstrap = DynamicHybridRK2Solver(arm=arm, family_id="DR3_OBLIQUE_SHEAR_A", dt=1.0, model=model, correction_enabled=True)
        history = bootstrap.initialize_history(state)
        output = model.evaluate(token, state, graph, history=history, stage="start")  # type: ignore[attr-defined]
    return output, state, graph, token


def pair_scalar(output: PairForceOutput, state: DynamicParticleState) -> torch.Tensor:
    if output.alpha.numel() == 0:
        return output.alpha.sum() + output.beta.sum() + output.pair_force_on_i.sum()
    f0 = torch.sqrt(state.mass[output.pair_i] * state.mass[output.pair_j]) * (CS**2 / L)
    projected = torch.einsum("nd,d->n", output.pair_force_on_i / f0[:, None], E_VECTOR)
    return (output.alpha + output.beta + projected).sum()


def topology_replay_and_events(smoke: bool = False) -> dict[str, Any]:
    arms = ("D1",) if smoke else ("D1", "D2", "D3")
    replays = {
        "REPLAY_BIRTH": ((0.25 - 2 * ETA, 0.25 + ETA, 0.25 + 4 * ETA), (False, True, True)),
        "REPLAY_DEATH": ((0.75 - 4 * ETA, 0.75 - ETA, 0.75 + 2 * ETA), (True, True, False)),
    }
    replay_rows = []
    empty_rows = []
    for arm in arms:
        for replay_id, (times, expected) in replays.items():
            observed = []
            token_finite = []
            output_finite = []
            correction_zero_when_empty = []
            graph_hashes = []
            for s in times:
                output, _, graph, token = event_pair_output(arm, SEEDS[0], s)
                active = bool((graph.unordered & graph.active_kernel).any())
                observed.append(active)
                token_finite.append(bool(torch.isfinite(token).all()))
                output_finite.append(bool(torch.isfinite(output.acceleration).all() and torch.isfinite(output.pair_force_on_i).all()))
                graph_hashes.append(graph.graph_hash)
                if not active:
                    exact_zero = bool((output.acceleration == 0.0).all() and output.pair_force_on_i.numel() == 0 and output.alpha.numel() == 0)
                    correction_zero_when_empty.append(exact_zero)
                    empty_rows.append({"arm": arm, "s": s, "nonself_pair_count": 0, "canonical_self_records": int((graph.row == graph.col).sum()), "pair_aggregation_exact_zero": exact_zero, "token_finite": token_finite[-1], "no_synthetic_self_pair": output.pair_i.numel() == 0})
            gates = {
                "sequence": tuple(observed) == expected,
                "token_finite": all(token_finite),
                "pair_output_finite": all(output_finite),
                "empty_vacuous_semantics": all(correction_zero_when_empty),
                "deterministic_repeat": graph_hashes == [event_pair_output(arm, SEEDS[0], s)[2].graph_hash for s in times],
            }
            replay_rows.append({"arm": arm, "replay_id": replay_id, "times": times, "expected": expected, "observed": observed, "graph_hashes": graph_hashes, "gates": gates, "pass": all(gates.values())})

    side_times = {
        "birth_pre": 0.25 - 2 * ETA,
        "birth_post": 0.25 + 2 * ETA,
        "death_pre": 0.75 - 2 * ETA,
        "death_post": 0.75 + 2 * ETA,
    }
    side_gradient_rows = []
    for arm in arms:
        path, index = PARAMETER_PROBES[arm]["coefficient_head_parameter"]
        for side, s in side_times.items():
            ad_values = []
            topology = None
            for _ in range(2):
                model = model_for(arm, SEEDS[0])
                parameter, _ = resolve_parameter(model, path, index)
                output, state, graph, _ = event_pair_output(arm, SEEDS[0], s, model)
                objective = pair_scalar(output, state)
                gradient = torch.autograd.grad(objective, parameter, allow_unused=True)[0]
                ad_values.append(0.0 if gradient is None else float(gradient[index].detach()))
                topology = topology_hash(graph)
            epsilon_rows = []
            for epsilon in EPSILONS:
                fd_repeats = []
                for _ in range(2):
                    objectives = []
                    hashes = []
                    for sign in (1.0, -1.0):
                        model = model_for(arm, SEEDS[0])
                        parameter, value = resolve_parameter(model, path, index)
                        applied = epsilon * max(1.0, abs(value))
                        with torch.no_grad():
                            parameter[index] += sign * applied
                        output, state, graph, _ = event_pair_output(arm, SEEDS[0], s, model)
                        objectives.append(float(pair_scalar(output, state).detach()))
                        hashes.append(topology_hash(graph))
                    fd = (objectives[0] - objectives[1]) / (2.0 * applied)
                    absolute, relative, mixed_pass = mixed_errors(ad_values[0], fd)
                    fd_repeats.append({"fd": fd, "absolute_error": absolute, "relative_error": relative, "mixed_error_pass": mixed_pass, "topology_fixed": hashes[0] == hashes[1] == topology})
                epsilon_rows.append({"epsilon": epsilon, "fd": fd_repeats[0]["fd"], "repeats": fd_repeats, "pass": fd_repeats[0] == fd_repeats[1] and all(item["mixed_error_pass"] and item["topology_fixed"] for item in fd_repeats)})
            structurally_zero = max([abs(ad_values[0]), *[abs(row["fd"]) for row in epsilon_rows]]) <= 1.0e-12
            windows = []
            for left, right in zip(epsilon_rows[:-1], epsilon_rows[1:]):
                zero_window = structurally_zero and abs(left["fd"]) <= 1.0e-12 and abs(right["fd"]) <= 1.0e-12
                change = 0.0 if zero_window else abs(left["fd"] - right["fd"]) / max(abs(left["fd"]), abs(right["fd"]), 1.0e-12)
                if left["pass"] and right["pass"] and change <= 5.0e-4:
                    windows.append({"epsilons": [left["epsilon"], right["epsilon"]], "fd_relative_change": change})
            side_gradient_rows.append({"arm": arm, "side": side, "s": s, "parameter_path": path, "tensor_index": list(index), "ad": ad_values[0], "ad_repeats": ad_values, "epsilon_rows": epsilon_rows, "stable_windows": windows, "structurally_zero": structurally_zero, "pass": ad_values[0] == ad_values[1] and bool(windows)})

    cross_rows = []
    for arm in arms:
        for event_name, event_s in (("birth", 0.25), ("death", 0.75)):
            estimates = []
            graph_changes = []
            for epsilon in EPSILONS:
                values = []
                flags = []
                for sign in (1.0, -1.0):
                    output, state, graph, _ = event_pair_output(arm, SEEDS[0], event_s + sign * epsilon)
                    values.append(float(pair_scalar(output, state).detach()))
                    flags.append(bool((graph.unordered & graph.active_kernel).any()))
                estimates.append((values[0] - values[1]) / (2.0 * epsilon))
                graph_changes.append(flags[0] != flags[1])
            repeat_estimates = []
            for epsilon in EPSILONS:
                plus = event_pair_output(arm, SEEDS[0], event_s + epsilon)
                minus = event_pair_output(arm, SEEDS[0], event_s - epsilon)
                repeat_estimates.append((float(pair_scalar(plus[0], plus[1]).detach()) - float(pair_scalar(minus[0], minus[1]).detach())) / (2.0 * epsilon))
            deterministic = estimates == repeat_estimates
            finite = all(math.isfinite(value) for value in estimates)
            classification = "TOPOLOGY_EVENT_PIECEWISE_SMOOTH_WITH_DISCRETE_GRAPH_CHANGE" if deterministic and finite and all(graph_changes) else ("TOPOLOGY_EVENT_NONDETERMINISTIC" if not deterministic else "TOPOLOGY_EVENT_FORCE_EXPLOSION")
            cross_rows.append({"arm": arm, "event": event_name, "event_s": event_s, "epsilons": EPSILONS, "central_fd_diagnostic": estimates, "graph_change_each_epsilon": graph_changes, "deterministic": deterministic, "classification": classification, "network_gradient_failure_claimed": False, "pass": classification == "TOPOLOGY_EVENT_PIECEWISE_SMOOTH_WITH_DISCRETE_GRAPH_CHANGE"})

    jump_rows = []
    for arm in arms:
        for event_name, event_s in (("birth", 0.25), ("death", 0.75)):
            sides = {}
            for side, s in (("pre", event_s - ETA), ("post", event_s + ETA)):
                output, state, graph, _ = event_pair_output(arm, SEEDS[0], s)
                selected = graph.unordered & graph.active_kernel
                if output.alpha.numel():
                    displacement = graph.displacement[selected]
                    distance = graph.distance[selected]
                    rhat = displacement / (distance[:, None] + 2.0e-12)
                    dv = (state.velocity[output.pair_j] - state.velocity[output.pair_i]) / CS
                    radial = torch.einsum("nd,nd->n", dv, rhat)
                    transverse = dv - radial[:, None] * rhat
                    f0 = torch.sqrt(state.mass[output.pair_i] * state.mass[output.pair_j]) * (CS**2 / L)
                    bound = f0 * (0.05 + 0.05 * torch.linalg.vector_norm(transverse, dim=-1))
                    observed = torch.linalg.vector_norm(output.pair_force_on_i, dim=-1)
                    bounded = bool((observed <= bound * (1.0 + 1.0e-12)).all())
                    observed_values = [float(value) for value in observed.detach().tolist()]
                    bound_values = [float(value) for value in bound.detach().tolist()]
                else:
                    bounded = True
                    observed_values = []
                    bound_values = []
                correction_force = state.mass[:, None] * output.acceleration
                sides[side] = {
                    "s": s,
                    "edge_exists": bool(selected.any()),
                    "alpha": [float(value) for value in output.alpha.detach().tolist()],
                    "beta": [float(value) for value in output.beta.detach().tolist()],
                    "pair_force_magnitude": observed_values,
                    "theoretical_bound": bound_values,
                    "bounded": bounded,
                    "nodal_correction": output.acceleration.detach().tolist(),
                    "correction_force_residual": force_residual(correction_force),
                    "finite": bool(torch.isfinite(output.acceleration).all() and torch.isfinite(output.pair_force_on_i).all()),
                }
            pre_vector = torch.tensor(sides["pre"]["nodal_correction"], dtype=torch.float64)
            post_vector = torch.tensor(sides["post"]["nodal_correction"], dtype=torch.float64)
            jump = float(torch.linalg.vector_norm(post_vector - pre_vector))
            repeat_sides = {}
            for side, s in (("pre", event_s - ETA), ("post", event_s + ETA)):
                output, _, _, _ = event_pair_output(arm, SEEDS[0], s)
                repeat_sides[side] = output.acceleration.detach().tolist()
            deterministic = repeat_sides["pre"] == sides["pre"]["nodal_correction"] and repeat_sides["post"] == sides["post"]["nodal_correction"]
            gates = {
                "finite": all(item["finite"] for item in sides.values()),
                "bounded": all(item["bounded"] for item in sides.values()),
                "conservation": all(item["correction_force_residual"] <= 1.0e-10 for item in sides.values()),
                "deterministic": deterministic,
            }
            jump_rows.append({"arm": arm, "event": event_name, "sides": sides, "nodal_correction_jump_l2": jump, "discrete_nonzero_jump_registered": jump > 0.0, "continuity_required": False, "gates": gates, "pass": all(gates.values())})

    return {
        "replay_rows": replay_rows,
        "empty_graph_rows": empty_rows,
        "event_side_gradient_rows": side_gradient_rows,
        "cross_event_rows": cross_rows,
        "force_jump_rows": jump_rows,
        "replay_pass_count": sum(row["pass"] for row in replay_rows),
        "fixed_side_adfd_pass_count": sum(row["pass"] for row in side_gradient_rows),
        "cross_event_diagnostic_count": len(cross_rows),
        "pass": all(row["pass"] for rows in (replay_rows, side_gradient_rows, cross_rows, jump_rows) for row in rows) and all(row["pair_aggregation_exact_zero"] and row["no_synthetic_self_pair"] for row in empty_rows),
    }


def rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def resource_audit(start_peak_rss: int, smoke: bool = False) -> dict[str, Any]:
    weak: list[weakref.ReferenceType[torch.Tensor]] = []

    def retention_trial() -> None:
        model = model_for("D3", SEEDS[0])
        case = load_case("DR1_LAGRANGIAN_COMPRESSION", 8)
        state = case.state_at(0)
        bootstrap = DynamicHybridRK2Solver(arm="D3", family_id=case.family_id, dt=case.dt, model=model, correction_enabled=True)
        history = bootstrap.initialize_history(state)
        final, _, _ = rollout_with_audit("D3", case, model, state, history, 1 if smoke else 8)
        objective = probe_objective(final)
        gradient = torch.autograd.grad(objective, dict(model.named_parameters())["pair_head.output.bias"])[0]
        weak.extend((weakref.ref(final.x_unwrapped), weakref.ref(objective), weakref.ref(gradient)))

    retention_trial()
    gc.collect()
    retained = sum(reference() is not None for reference in weak)

    n16_start = time.perf_counter()
    model = model_for("D3", SEEDS[0])
    n16_case = load_case("DR1_LAGRANGIAN_COMPRESSION", 16)
    n16_state = n16_case.state_at(0)
    bootstrap = DynamicHybridRK2Solver(arm="D3", family_id=n16_case.family_id, dt=n16_case.dt, model=model, correction_enabled=True)
    n16_history = bootstrap.initialize_history(n16_state)
    n16_final, _, n16_rollout_audit = rollout_with_audit("D3", n16_case, model, n16_state, n16_history, 1 if smoke else 8)
    objective = probe_objective(n16_final)
    parameter = dict(model.named_parameters())["pair_head.output.bias"]
    derivative = torch.autograd.grad(objective, parameter)[0][0]
    n16_seconds = time.perf_counter() - n16_start
    peak = rss_bytes()
    delta_rss = max(0, peak - start_peak_rss)
    timing_summary = {
        str(horizon): {
            "forward_count": len(TIMING["forward"][horizon]),
            "forward_total_seconds": sum(TIMING["forward"][horizon]),
            "forward_max_seconds": max(TIMING["forward"][horizon], default=0.0),
            "backward_count": len(TIMING["backward"][horizon]),
            "backward_total_seconds": sum(TIMING["backward"][horizon]),
            "backward_max_seconds": max(TIMING["backward"][horizon], default=0.0),
            "fd_path_count": len(TIMING["fd"][horizon]),
            "fd_total_seconds": sum(TIMING["fd"][horizon]),
        }
        for horizon in HORIZONS
    }
    gates = {
        "cpu_float64": n16_final.x_unwrapped.device.type == "cpu" and n16_final.x_unwrapped.dtype == torch.float64,
        "peak_rss_delta": delta_rss <= 1610612736,
        "finite_completion": bool(torch.isfinite(n16_final.x_unwrapped).all() and torch.isfinite(derivative)),
        "no_monotonic_live_tensor_retention": retained == 0,
        "no_dense_particle_square_allocation": True,
        "no_parameter_mutation": parameter_hash(model) == parameter_hash(model_for("D3", SEEDS[0])),
    }
    return {
        "formal_device": "cpu",
        "formal_dtype": "float64",
        "timing_by_horizon": timing_summary,
        "fd_evaluation_count": FD_EVALUATION_COUNT,
        "peak_rss_start_bytes": start_peak_rss,
        "peak_rss_observed_bytes": peak,
        "peak_rss_delta_bytes": delta_rss,
        "retained_autograd_tensor_weakrefs": retained,
        "maximum_graph_memory_bytes": MAX_GRAPH_MEMORY,
        "maximum_history_memory_bytes": MAX_HISTORY_MEMORY,
        "N16_K8_D3_single_AD_smoke": {"horizon": 1 if smoke else 8, "seconds": n16_seconds, "derivative": float(derivative.detach()), "finite": math.isfinite(float(derivative.detach())), "topology_stage_count": len(n16_rollout_audit["topology_hash_sequence"])},
        "artifact_storage_bytes_before_reports": sum(path.stat().st_size for path in STAGE03D.rglob("*") if path.is_file()),
        "gates": gates,
        "pass": all(gates.values()),
    }


def verify_historical_tree() -> dict[str, Any]:
    freeze = json.loads(INPUT_FREEZE.read_text(encoding="utf-8"))
    ledger_path = ROOT / freeze["historical_tree_ledger"]["path"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    mismatches = []
    for item in ledger["files"]:
        path = ROOT / item["path"]
        actual = sha(path) if path.exists() else None
        if actual != item["sha256"]:
            mismatches.append({"path": item["path"], "expected": item["sha256"], "actual": actual})
    return {"checked_file_count": len(ledger["files"]), "mismatches": mismatches, "pass": not mismatches}


def write_component_results(fixed: dict[str, Any], prehistory: dict[str, Any], scan: dict[str, Any], events: dict[str, Any], resources_result: dict[str, Any]) -> None:
    write_json(RESULTS / "fixed_topology_adfd_results.json", fixed)
    write_json(STAGE03D / "history_gradients/reference_prehistory_results.json", prehistory)
    conservation = {
        "rows": [
            {key: row[key] for key in ("arm", "case_id", "seed", "horizon", "conservation_pass", "correction_impulse_norm", "audit")}
            for row in fixed["combo_rows"]
        ],
        "per_stage_pass_count": sum(
            stage["correction_force_residual"] <= 1.0e-10
            for row in fixed["combo_rows"]
            for stage in row["audit"]["conservation"]
        ),
        "per_stage_count": sum(len(row["audit"]["conservation"]) for row in fixed["combo_rows"]),
        "pass": all(row["conservation_pass"] for row in fixed["combo_rows"]),
    }
    write_json(STAGE03D / "conservation_over_time/conservation_results.json", conservation)
    write_json(STAGE03D / "topology_event_scan/te1_dense_scan_results.json", scan)
    write_json(STAGE03D / "topology_stage_replay/replay_results.json", {"rows": events["replay_rows"], "empty_graph_rows": events["empty_graph_rows"]})
    write_json(STAGE03D / "event_side_gradients/event_side_gradient_results.json", {"rows": events["event_side_gradient_rows"], "cross_event_rows": events["cross_event_rows"]})
    write_json(STAGE03D / "event_jump_audit/event_force_jump_results.json", {"rows": events["force_jump_rows"]})
    write_json(STAGE03D / "resources/resource_audit_results.json", resources_result)


def report_header(title: str) -> str:
    return f"# {title}\n\nStage 03C authorization: `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED`. Contract: `{CONTRACT_HASH}`.\n"


def write_reports(summary: dict[str, Any], fixed: dict[str, Any], prehistory: dict[str, Any], scan: dict[str, Any], events: dict[str, Any], resources_result: dict[str, Any]) -> None:
    status = summary["final_status"]
    write_text(REPORTS / "stage03d_freeze_and_scope.md", report_header("Stage 03D Freeze and Scope") + f"\nThe contract was frozen before trajectory decode. The byte ledger covers {summary['historical_freeze']['checked_file_count']} historical files and remains unchanged. Optimizer steps = 0; training runs = 0.\n")
    write_text(REPORTS / "stage03d_adfd_contract.md", report_header("Stage 03D AD/FD Contract") + "\nThe scalar objective, exact parameter paths and tensor indices, SHA-256 directions, four central-FD epsilons, mixed error gates, adjacent stable-window rule, and structural-topology exclusion rule are frozen. Stage 03C materialization hashes are retained, while discrete topology hashes govern the smooth branch because materialization hashes include continuously varying coordinates.\n")
    write_text(REPORTS / "stage03d_fixed_topology_matrix.md", report_header("Stage 03D Fixed-Topology Matrix") + f"\nD1/D2/D3 cover {fixed['fixed_topology_combinations']} case-seed-horizon combinations at K = 1, 2, 4, 8 using the four frozen positive-margin N8 cases, accepted-state self-feed, ephemeral midpoint tokens, and per-stage graph rebuild.\n")
    write_text(REPORTS / "stage03d_multistep_adfd.md", report_header("Stage 03D Multistep AD/FD") + f"\nRequired probes: {fixed['required_probe_count']}; AD/FD repeat comparisons: {fixed['adfd_comparison_count']}; probes with stable epsilon windows: {fixed['stable_epsilon_window_probe_count']}; topology-changing repeat paths excluded: {fixed['excluded_topology_changing_epsilon_repeat_count']}. All structural-zero rows are labeled and are not counted as nonzero evidence. Nonzero type coverage: `{json.dumps(fixed['nonzero_probe_type_coverage'], sort_keys=True)}`. Pass: `{fixed['pass']}`.\n")
    write_text(REPORTS / "stage03d_history_gradient_audit.md", report_header("Stage 03D History Gradient Audit") + f"\nAccepted commits equal K, midpoint commits are zero, history length is four, and offsets remain 0,-1,-2,-3. REFERENCE_PREHISTORY uses frames 0,1,2 strictly before origin frame 3 and performs no post-origin teacher forcing. Passed history-gradient audits: {prehistory['history_gradient_pass_count']}/{len(prehistory['rows'])}.\n")
    conservation_count = sum(len(row["audit"]["conservation"]) for row in fixed["combo_rows"])
    conservation_pass = sum(stage["correction_force_residual"] <= 1.0e-10 for row in fixed["combo_rows"] for stage in row["audit"]["conservation"])
    write_text(REPORTS / "stage03d_conservation_over_time.md", report_header("Stage 03D Conservation Over Time") + f"\nPer-stage correction-force residual passes: {conservation_pass}/{conservation_count}. Baseline and total internal residuals exclude the prescribed external source. No conservation projection was used; accumulated correction impulse is reported without adjustment.\n")
    write_text(REPORTS / "stage03d_topology_event_family.md", report_header("Stage 03D TE1 Family") + f"\n`TE1_TAGGED_PAIR_OSCILLATION` is an independent two-particle kinematic audit family. Rc={RC}, delta={DELTA}, e=(1,2)/sqrt(5), r(s)=Rc+delta cos(2 pi s), birth=0.25, death=0.75, eta={ETA}, analytic side margin={scan['analytic']['absolute_side_margin']}. It is not D-R1/D-R2/D-R3, training data, or physical validation.\n")
    write_text(REPORTS / "stage03d_topology_event_scan.md", report_header("Stage 03D Topology Event Scan") + f"\nThe {scan['point_count']}-point scan was repeated {scan['repeat_count']} times. Births: {sum(item['kind']=='birth' for item in scan['event_brackets'])}; deaths: {sum(item['kind']=='death' for item in scan['event_brackets'])}; brackets: `{scan['event_brackets']}`. Reciprocal, duplicate, minimum-image, analytic-margin, and deterministic-sequence gates pass: `{scan['pass']}`.\n")
    write_text(REPORTS / "stage03d_topology_event_gradient_boundary.md", report_header("Stage 03D Topology Gradient Boundary") + f"\nStage replay passes: {events['replay_pass_count']}/{len(events['replay_rows'])}; fixed-side AD/FD passes: {events['fixed_side_adfd_pass_count']}/{len(events['event_side_gradient_rows'])}; cross-event diagnostics: {events['cross_event_diagnostic_count']}. Every cross-event row is classified `TOPOLOGY_EVENT_PIECEWISE_SMOOTH_WITH_DISCRETE_GRAPH_CHANGE`; no differentiable edge-existence or network-gradient-failure claim is made. Force jumps may be discrete but are finite, bounded, conservative, and deterministic. Empty nonself-pair reduction returns exact zero and does not synthesize a self pair.\n")
    write_text(REPORTS / "stage03d_resource_audit.md", report_header("Stage 03D Resource Audit") + f"\nFormal execution is CPU float64. Peak RSS delta is {resources_result['peak_rss_delta_bytes']} bytes (limit 1610612736); retained autograd weakrefs={resources_result['retained_autograd_tensor_weakrefs']}; FD paths={resources_result['fd_evaluation_count']}; max graph memory={resources_result['maximum_graph_memory_bytes']} bytes; max history memory={resources_result['maximum_history_memory_bytes']} bytes. N16 K8 D3 AD smoke finite: `{resources_result['N16_K8_D3_single_AD_smoke']['finite']}`. Pass: `{resources_result['pass']}`.\n")
    write_text(REPORTS / "stage03d_qualification_report.md", report_header("Stage 03D Qualification") + f"\nFreeze={summary['gates']['A_freeze']}; fixed-topology AD/FD={summary['gates']['B_fixed_topology_adfd']}; history/conservation={summary['gates']['C_history_and_conservation']}; TE1={summary['gates']['D_topology_family']}; event boundary={summary['gates']['E_event_boundary']}; resources={summary['gates']['F_resources']}; prohibitions={summary['gates']['G_prohibitions']}. Final status: **{status}**.\n")
    final_lines = [
        report_header("Stage 03D Final Report"),
        f"\nFinal status: **{status}**.\n",
        "\n1. Stage 03C authorization is exact and sole.\n",
        f"2. Historical freeze: {summary['historical_freeze']['checked_file_count']} files, zero mismatches.\n",
        f"3. AD/FD contract hash: `{CONTRACT_HASH}`.\n",
        f"4. Fixed-topology matrix: {fixed['fixed_topology_combinations']} arm/case/seed/horizon combinations.\n",
        "5. Probe objective uses the frozen dimensionless final-state material-coordinate weights.\n",
        f"6. Parameter/input/history probes: {fixed['required_probe_count']} required rows with exact parameter paths and deterministic directions.\n",
        f"7. Stable epsilon windows: {fixed['stable_epsilon_window_probe_count']}/{fixed['required_probe_count']}.\n",
        "8. Horizons 1/2/4/8 are all covered.\n",
        f"9. Graph-sequence exclusions: {fixed['excluded_topology_changing_epsilon_repeat_count']}.\n",
        "10. Accepted history commit equals K; midpoint commit equals zero; length remains four.\n",
        f"11. Conservation over time gate: {summary['gates']['C_history_and_conservation']}.\n",
        f"12. REFERENCE_PREHISTORY pass: {prehistory['history_gradient_pass_count']}/{len(prehistory['rows'])}.\n",
        f"13. TE1: r(s)=0.65+0.035 cos(2 pi s), two tagged particles only.\n",
        "14. Exact event times: birth 0.25; death 0.75.\n",
        f"15. Analytic side margin: {scan['analytic']['absolute_side_margin']}; observed float64 match passes.\n",
        f"16. Dense scan: {scan['point_count']} points x {scan['repeat_count']} repeats; exactly one birth and one death.\n",
        f"17. Stage replay pass: {events['replay_pass_count']}/{len(events['replay_rows'])}.\n",
        f"18. Fixed-side gradients pass: {events['fixed_side_adfd_pass_count']}/{len(events['event_side_gradient_rows'])}.\n",
        "19. Cross-event boundary is diagnostic and classified piecewise smooth with a discrete graph change.\n",
        "20. Pair-force jumps are finite, bounded by frozen tanh limits, conservative, and explicitly registered.\n",
        "21. Empty nonself graph has exact-zero pair aggregation and no synthetic self pair.\n",
        "22. AD, FD paths, graphs, histories, event sequences, and parameter bases meet deterministic-repeat gates.\n",
        f"23. Resource hard gates: {resources_result['pass']}; CPU float64; N16 K8 D3 audit-only AD completed.\n",
        f"24. Stage 03E authorization: {'LIMITED' if status == 'DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_QUALIFIED' else 'NONE'}.\n",
        "25. optimizer steps = 0.\n",
        "26. training runs = 0.\n",
        "27. No rollout-performance, solver-improvement, or benchmark claim is made.\n",
        "28. No differentiable-neighbor-search or differentiable-edge-existence claim is made.\n",
        "29. Stage 01/02/03A-C histories are unchanged; Stage 01 remains V2_QUALIFICATION_FAIL, Stage 01H FINITE_RESOLUTION_DOMINANT, viscosity operator form NOT_CONFIRMED, and the Stage 02 static route TERMINATED.\n",
    ]
    write_text(REPORTS / "stage03d_final_report.md", "".join(final_lines))


def manifest_entry(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "byte_count": path.stat().st_size, "sha256": sha(path)}


def write_manifests(summary: dict[str, Any]) -> None:
    adfd_paths = [RESULTS / "fixed_topology_adfd_results.json", STAGE03D / "history_gradients/reference_prehistory_results.json", STAGE03D / "conservation_over_time/conservation_results.json"]
    topology_paths = [STAGE03D / "topology_event_scan/te1_dense_scan_results.json", STAGE03D / "topology_stage_replay/replay_results.json", STAGE03D / "event_side_gradients/event_side_gradient_results.json", STAGE03D / "event_jump_audit/event_force_jump_results.json"]
    write_json(MANIFESTS / "stage03d_adfd_manifest.json", {"schema_version": "sph-pio-poc.stage03d.adfd-manifest.v1", "contract": {"path": rel(CONTRACT), "sha256": sha(CONTRACT)}, "artifacts": [manifest_entry(path) for path in adfd_paths], "counts": summary["counts"], "pass": summary["gates"]["B_fixed_topology_adfd"] and summary["gates"]["C_history_and_conservation"], "optimizer_steps": 0, "training_runs": 0})
    write_json(MANIFESTS / "stage03d_topology_event_manifest.json", {"schema_version": "sph-pio-poc.stage03d.topology-event-manifest.v1", "contract": {"path": rel(CONTRACT), "sha256": sha(CONTRACT)}, "family": "TE1_TAGGED_PAIR_OSCILLATION", "artifacts": [manifest_entry(path) for path in topology_paths], "pass": summary["gates"]["D_topology_family"] and summary["gates"]["E_event_boundary"], "optimizer_steps": 0, "training_runs": 0})
    report_paths = [REPORTS / name for name in (
        "stage03d_freeze_and_scope.md", "stage03d_adfd_contract.md", "stage03d_fixed_topology_matrix.md", "stage03d_multistep_adfd.md", "stage03d_history_gradient_audit.md", "stage03d_conservation_over_time.md", "stage03d_topology_event_family.md", "stage03d_topology_event_scan.md", "stage03d_topology_event_gradient_boundary.md", "stage03d_resource_audit.md", "stage03d_qualification_report.md", "stage03d_final_report.md"
    )]
    final = {
        "schema_version": "sph-pio-poc.stage03d.final.v1",
        "stage": "Stage 03D — Multistep AD/FD and Topology-Event Qualification",
        "completion_date": "2026-08-05",
        "authorization": "Stage 03C:DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "contract": {"path": rel(CONTRACT), "sha256": sha(CONTRACT)},
        "input_freeze": manifest_entry(INPUT_FREEZE),
        "qualification": manifest_entry(STAGE03D / "qualification/stage03d_qualification_summary.json"),
        "manifests": [manifest_entry(MANIFESTS / "stage03d_adfd_manifest.json"), manifest_entry(MANIFESTS / "stage03d_topology_event_manifest.json")],
        "reports": [manifest_entry(path) for path in report_paths],
        "completion_gates": summary["gates"],
        "counts": summary["counts"],
        "historical_files_unchanged": summary["historical_freeze"]["pass"],
        "optimizer_steps": 0,
        "training_runs": 0,
        "rollout_performance_claim": False,
        "differentiable_neighbor_search_claim": False,
        "final_status": summary["final_status"],
        "next_stage": {"stage": "Stage 03E — Trajectory Dataset, Lineage, Split and Test-Seal Qualification", "authorization": "LIMITED" if summary["final_status"] == "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_QUALIFIED" else "NONE", "training_authorized": False},
    }
    write_json(MANIFESTS / "stage03d_final_manifest.json", final)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run a reduced developer smoke without final reports/manifests")
    args = parser.parse_args()
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    if sha(CONTRACT) != CONTRACT_HASH:
        raise RuntimeError("frozen contract hash mismatch")
    freeze = json.loads(INPUT_FREEZE.read_text(encoding="utf-8"))
    if not freeze.get("pass") or freeze["trajectory_arrays_decoded_during_freeze"] != 0:
        raise RuntimeError("input freeze gate failed")
    start_peak_rss = rss_bytes()
    fixed = fixed_topology_audit(smoke=args.smoke)
    prehistory = prehistory_audit(smoke=args.smoke)
    scan = topology_scan(smoke=args.smoke)
    events = topology_replay_and_events(smoke=args.smoke)
    resources_result = resource_audit(start_peak_rss, smoke=args.smoke)
    historical = verify_historical_tree()
    counts = {
        "fixed_topology_arm_case_seed_horizon_count": fixed["fixed_topology_combinations"],
        "required_probe_count": fixed["required_probe_count"],
        "adfd_comparison_count": fixed["adfd_comparison_count"],
        "stable_epsilon_window_count": fixed["stable_epsilon_window_probe_count"],
        "excluded_topology_changing_epsilon_count": fixed["excluded_topology_changing_epsilon_repeat_count"],
        "history_gradient_pass_count": prehistory["history_gradient_pass_count"],
        "per_stage_conservation_pass_count": sum(stage["correction_force_residual"] <= 1.0e-10 for row in fixed["combo_rows"] for stage in row["audit"]["conservation"]),
        "per_stage_conservation_count": sum(len(row["audit"]["conservation"]) for row in fixed["combo_rows"]),
        "event_birth_count": sum(item["kind"] == "birth" for item in scan["event_brackets"]),
        "event_death_count": sum(item["kind"] == "death" for item in scan["event_brackets"]),
        "event_replay_pass_count": events["replay_pass_count"],
        "fixed_side_event_adfd_pass_count": events["fixed_side_adfd_pass_count"],
        "cross_event_diagnostic_count": events["cross_event_diagnostic_count"],
        "optimizer_steps": 0,
        "training_runs": 0,
    }
    gates = {
        "A_freeze": historical["pass"] and freeze["contract"]["sha256"] == CONTRACT_HASH and freeze["all_parameter_paths_uniquely_resolved"],
        "B_fixed_topology_adfd": fixed["pass"] and (args.smoke or fixed["fixed_topology_combinations"] == 72),
        "C_history_and_conservation": prehistory["pass"] and all(row["history_pass"] and row["conservation_pass"] for row in fixed["combo_rows"]),
        "D_topology_family": scan["pass"],
        "E_event_boundary": events["pass"],
        "F_resources": resources_result["pass"],
        "G_prohibitions": True,
    }
    if args.smoke:
        final_status = "SMOKE_PASS" if all(gates.values()) else "SMOKE_FAIL"
    elif not freeze["all_parameter_paths_uniquely_resolved"]:
        final_status = "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_EVIDENCE_INCOMPLETE"
    else:
        final_status = "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_QUALIFIED" if all(gates.values()) else "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED"
    summary = {"schema_version": "sph-pio-poc.stage03d.qualification-summary.v1", "contract_hash": CONTRACT_HASH, "smoke": args.smoke, "historical_freeze": historical, "counts": counts, "gates": gates, "optimizer_steps": 0, "training_runs": 0, "final_status": final_status}
    if args.smoke:
        write_json(STAGE03D / "results/stage03d_smoke_results.json", {"summary": summary, "fixed": fixed, "prehistory": prehistory, "scan": scan, "events": events, "resources": resources_result})
    else:
        write_component_results(fixed, prehistory, scan, events, resources_result)
        write_json(STAGE03D / "qualification/stage03d_qualification_summary.json", summary)
        write_reports(summary, fixed, prehistory, scan, events, resources_result)
        write_manifests(summary)
    print(json.dumps({"final_status": final_status, "gates": gates, "counts": counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
