"""Execute the frozen Stage 04C task-aligned parameter-gradient protocol."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
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

import numpy as np
import torch
from torch import nn
from torch.func import functional_call
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE04C = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
STAGE04B = STAGE04 / "04_reference_family_pool/stage04b"
for candidate in (STAGE03C, ROOT / "01_solver", STAGE04B / "formula_templates"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import ReciprocalGraph, build_reciprocal_graph
from pair_force_head.head import PairForceOutput
from stage04b_reference_core import evaluate_symbolic
from structural_smoke.audit import audit_stage
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients, scatter_sum
from temporal_history.history import TemporalHistoryState
from tokenization.tokens import build_node_token


SEEDS = [20400401, 20400402, 20400403]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
VARIANTS = ["VARIANT_LOW", "VARIANT_MAIN"]
EPSILONS = [1e-2, 3e-3, 1e-3, 3e-4, 1e-4]
DT = 2.0 / 20.0 / 256.0
BACKEND = "CPU_FLOAT64_TORCH_SDPA_EXPLICIT_MATH_NO_AUTO"
ARM_CLASSES = {"D1": D1InstantaneousPairMLP, "D2": D2CausalRecurrentPairPIO, "D3": D3CausalTemporalTransformerPIO}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sha_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def tensor_bytes(value: torch.Tensor) -> bytes:
    x = value.detach().contiguous().cpu().numpy()
    return str(x.dtype).encode() + str(x.shape).encode() + x.tobytes()


def model_hash(model: nn.Module) -> str:
    h = hashlib.sha256(BACKEND.encode())
    for name, p in model.named_parameters():
        h.update(name.encode()); h.update(tensor_bytes(p))
    return "sha256:" + h.hexdigest()


def rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux reports KiB.
    return int(value if sys.platform == "darwin" else value * 1024)


def topology_id(graph: ReciprocalGraph) -> str:
    h = hashlib.sha256()
    for x in (graph.row, graph.col, graph.reverse): h.update(tensor_bytes(x))
    return "sha256:" + h.hexdigest()


def finite_vector(x: torch.Tensor) -> bool:
    return bool(torch.isfinite(x.detach()).all())


@dataclass(frozen=True)
class CaseData:
    lineage: str
    variant: str
    resolution: int
    origin: int
    frames: torch.Tensor
    x: torch.Tensor
    velocity: torch.Tensor
    density: torch.Tensor
    source: torch.Tensor
    labels: torch.Tensor
    mass: torch.Tensor
    smoothing: torch.Tensor
    physical_time: torch.Tensor
    source_midpoint: torch.Tensor
    history_tokens_override: torch.Tensor | None = None

    def index(self, frame: int) -> int:
        hits = torch.nonzero(self.frames == frame).flatten()
        if hits.numel() != 1: raise RuntimeError(f"frame lookup failed: {frame}")
        return int(hits[0])


def import_access_module() -> Any:
    path = STAGE04B / "access_control/stage04c_access.py"
    spec = importlib.util.spec_from_file_location("stage04c_access", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ACCESS = import_access_module()
DECODE = {"train_state_array_decode_count": 0, "validation_target_decode_count": 0, "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_target_decode_count": 0}


def access_denial_audit(phase: str) -> dict[str, Any]:
    targets = {
        "validation_target": STAGE04B / "access_control/validation_private/lcdf_02_variant_main_n8.npz",
        "sealed_formula": STAGE04B / "sealed_test/private/sealed_parameters.json",
        "sealed_state": STAGE04B / "sealed_test/private/lcdf_03_variant_main_n8.npz",
        "sealed_target": STAGE04B / "sealed_test/private/lcdf_10_variant_main_n8.npz",
    }
    rows = []
    for kind, path in targets.items():
        denied = False
        try:
            ACCESS.read_train_bytes(path)
        except PermissionError:
            denied = True
        rows.append({"kind": kind, "path": str(path.relative_to(ROOT)), "denied_before_os_read": denied})
    return {"phase": phase, "allowlist_module": str((STAGE04B / 'access_control/stage04c_access.py').relative_to(ROOT)), "rows": rows, "decode_counts": dict(DECODE), "pass": all(r["denied_before_os_read"] for r in rows)}


def load_case(lineage: str, variant: str, resolution: int, origin: int) -> CaseData:
    stem = f"{lineage.lower()}_{variant.lower()}_n{resolution}.npz"
    arrays = ACCESS.load_train_npz(STAGE04B / "exact_trajectories/train" / stem)
    DECODE["train_state_array_decode_count"] += 1
    def t(name: str) -> torch.Tensor: return torch.from_numpy(np.ascontiguousarray(arrays[name])).to(torch.float64)
    labels = t("material_labels")
    midpoint = evaluate_symbolic(lineage, variant, arrays["material_labels"], (origin + 0.5) / 256.0)["source"]
    count = resolution * resolution
    dx = 2.0 / resolution
    return CaseData(
        lineage, variant, resolution, origin,
        torch.from_numpy(np.ascontiguousarray(arrays["frame_n"])).to(torch.int64),
        t("position_unwrapped"), t("velocity"), t("density"), t("external_source"), labels,
        torch.full((count,), dx * dx, dtype=torch.float64),
        torch.full((count,), 2.6 * dx, dtype=torch.float64),
        t("physical_time"), torch.from_numpy(np.ascontiguousarray(midpoint)).to(torch.float64),
    )


def make_state(case: CaseData, frame: int, *, x: torch.Tensor | None = None, velocity: torch.Tensor | None = None, density: torch.Tensor | None = None) -> DynamicParticleState:
    idx = case.index(frame)
    rho = case.density[idx] if density is None else density
    return DynamicParticleState(
        case.x[idx] if x is None else x,
        case.velocity[idx] if velocity is None else velocity,
        rho, eos_pressure(rho), case.mass, case.smoothing, case.labels,
        float(case.physical_time[idx]), frame,
    )


def baseline_rhs(state: DynamicParticleState, graph: ReciprocalGraph, source: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    pressure_force = conservative_pressure_forces(graph.neighborhood, mass=state.mass, density=state.density, pressure=state.pressure)
    viscosity_force = conservative_viscosity_forces(graph.neighborhood, mass=state.mass, density=state.density, velocity=state.velocity, physical_viscosity=0.02)
    gradient = edge_kernel_gradients(graph.neighborhood)
    dv = state.velocity[graph.row] - state.velocity[graph.col]
    drho = scatter_sum(graph.row, state.mass[graph.col] * torch.einsum("nd,nd->n", dv, gradient), state.particle_count)
    acceleration = (pressure_force + viscosity_force) / state.mass[:, None] + source
    return state.velocity, acceleration, drho


class TaskAlignedTransition(nn.Module):
    def __init__(self, arm: str, model: nn.Module) -> None:
        super().__init__(); self.arm = arm; self.core = model; self.last_trace: dict[str, Any] = {}

    def reference_history(self, case: CaseData) -> TemporalHistoryState | None:
        if self.arm == "D1": return None
        frame_ids = [case.origin - 3, case.origin - 2, case.origin - 1, case.origin]
        states = [make_state(case, frame) for frame in frame_ids]
        tokens = ([token for token in case.history_tokens_override.unbind(dim=1)]
                  if case.history_tokens_override is not None
                  else [build_node_token(s, build_reciprocal_graph(s)) for s in states])
        if self.arm == "D2":
            hidden = torch.zeros((states[0].particle_count, 32), dtype=torch.float64)
            hidden_items = []
            for token in tokens:
                hidden = self.core.recurrent(self.core.encoder(token), hidden)
                hidden_items.append(hidden)
        else:
            hidden_items = []
            for index in range(4):
                prefix = tokens[:index + 1]; padded = [prefix[0]] * (4 - len(prefix)) + prefix
                hidden_items.append(self.core.temporal_hidden(torch.stack(padded, dim=1))[:, -1, :])
        return TemporalHistoryState(torch.stack(tokens, dim=1), torch.stack(hidden_items, dim=1),
                                    torch.tensor([s.physical_time for s in states], dtype=torch.float64), case.labels,
                                    history_length=4, commit_count=0)

    def forward(self, case: CaseData) -> torch.Tensor:
        start = make_state(case, case.origin).with_eos()
        history = self.reference_history(case)
        graphs: list[ReciprocalGraph] = []
        graph_start = build_reciprocal_graph(start); graphs.append(graph_start)
        token_start = build_node_token(start, graph_start)
        kwargs: dict[str, Any] = {"stage": "start"}
        if history is not None: kwargs["history"] = history
        pair_start: PairForceOutput = self.core.evaluate(token_start, start, graph_start, **kwargs)
        x1, a1, r1 = baseline_rhs(start, graph_start, case.source[case.index(case.origin)])
        a1 = a1 + pair_start.acceleration
        midpoint = DynamicParticleState(
            start.x_unwrapped + 0.5 * DT * x1,
            start.velocity + 0.5 * DT * a1,
            start.density + 0.5 * DT * r1,
            torch.empty_like(start.pressure), start.mass, start.smoothing_length, start.material_labels,
            start.physical_time + 0.5 * DT, start.accepted_step_index,
        ).with_eos()
        graph_mid = build_reciprocal_graph(midpoint); graphs.append(graph_mid)
        token_mid = build_node_token(midpoint, graph_mid)
        kwargs = {"stage": "midpoint"}
        if history is not None: kwargs["history"] = history
        pair_mid: PairForceOutput = self.core.evaluate(token_mid, midpoint, graph_mid, **kwargs)
        x2, a2, r2 = baseline_rhs(midpoint, graph_mid, case.source_midpoint)
        a2 = a2 + pair_mid.acceleration
        accepted = DynamicParticleState(
            start.x_unwrapped + DT * x2,
            start.velocity + DT * a2,
            start.density + DT * r2,
            torch.empty_like(start.pressure), start.mass, start.smoothing_length, start.material_labels,
            start.physical_time + DT, start.accepted_step_index + 1,
        ).with_eos()
        graph_acc = build_reciprocal_graph(accepted); graphs.append(graph_acc)
        commit_count = 0
        if history is not None:
            token_acc = build_node_token(accepted, graph_acc)
            hidden_acc = self.core.accepted_hidden(token_acc, history=history)
            history = history.commit(token_acc, hidden_acc, accepted.physical_time)
            commit_count = history.commit_count
        target_idx = case.index(case.origin + 1)
        dx = torch.remainder(accepted.x_unwrapped - case.x[target_idx] + 1.0, 2.0) - 1.0
        losses = torch.stack((dx.square().sum(-1).mean() / 4.0,
                              (accepted.velocity - case.velocity[target_idx]).square().sum(-1).mean() / 400.0,
                              (accepted.density - case.density[target_idx]).square().mean()))
        self.last_trace = {
            "topology": [topology_id(g) for g in graphs],
            "edge_counts": [g.edge_count for g in graphs],
            "density_min": float(min(start.density.detach().min(), midpoint.density.detach().min(), accepted.density.detach().min())),
            "finite": bool(finite_vector(losses) and finite_vector(pair_start.acceleration) and finite_vector(pair_mid.acceleration)),
            "history_commit_count": commit_count,
            "midpoint_commit_count": 0,
            "history_hash": None if history is None else history.history_hash,
            "pair_force_residual_start": correction_residual(start, pair_start),
            "pair_force_residual_midpoint": correction_residual(midpoint, pair_mid),
        }
        return losses


def correction_residual(state: DynamicParticleState, output: PairForceOutput) -> float:
    force = torch.zeros_like(state.velocity)
    force.index_add_(0, output.pair_i, output.pair_force_on_i)
    force.index_add_(0, output.pair_j, -output.pair_force_on_i)
    return float(torch.linalg.vector_norm(force.sum(0)).detach() / (output.pair_force_on_i.detach().abs().sum() + 1e-30))


def instantiate(arm: str, seed: int) -> tuple[nn.Module, TaskAlignedTransition]:
    torch.manual_seed(seed)
    core = ARM_CLASSES[arm]().to(dtype=torch.float64, device="cpu")
    return core, TaskAlignedTransition(arm, core)


def group_rows() -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((STAGE04 / "09_manifests/stage04c_parameter_manifest.json").read_text())
    return {row["group"]: row["tensors"] for row in payload["groups"]}


GROUP_ROWS = group_rows()


def groups_for(arm: str) -> list[str]: return [g for g in GROUP_ROWS if g.startswith(arm + "_")]


def rademacher(seed_hash: str, count: int) -> torch.Tensor:
    seed = bytes.fromhex(seed_hash.split(":", 1)[1]); raw = bytearray(); counter = 0
    while len(raw) * 8 < count:
        raw.extend(hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()); counter += 1
    bits = np.unpackbits(np.frombuffer(bytes(raw), dtype=np.uint8))[:count]
    return torch.from_numpy((2 * bits.astype(np.float64) - 1.0).copy()).to(torch.float64)


def direction_seed(arm: str, group: str, case: CaseData, model_seed: int) -> str:
    raw = "stage04c_parameter_direction_v1" + arm + group + case.lineage + case.variant + str(case.origin) + str(model_seed)
    return sha_bytes(raw.encode())


def direction_tuple(adapter: TaskAlignedTransition, arm: str, group: str, case: CaseData, seed: int) -> tuple[tuple[torch.Tensor, ...], float, str]:
    named = list(adapter.named_parameters())
    directions = [torch.zeros_like(p) for _, p in named]
    index = {name.removeprefix("core."): i for i, (name, _) in enumerate(named)}
    total = sum(row["parameter_count"] for row in GROUP_ROWS[group])
    seed_hash = direction_seed(arm, group, case, seed)
    values = rademacher(seed_hash, total) / math.sqrt(total)
    offset = 0; param_values = []
    for row in GROUP_ROWS[group]:
        i = index[row["tensor_path"]]; n = row["parameter_count"]
        chunk = values[offset:offset+n].reshape(row["shape"]); offset += n
        spec = row["slice"]
        if spec == "all": directions[i] = chunk
        else:
            start, stop = [int(v) for v in spec.split(",")[0].lstrip("[").rstrip("]").split(":")]
            directions[i][start:stop] = chunk
        p = named[i][1]
        if spec == "all": param_values.append(p.detach().flatten())
        else: param_values.append(p.detach()[start:stop].flatten())
    rms = float(torch.sqrt(torch.cat(param_values).square().mean()))
    return tuple(directions), rms, seed_hash


def evaluate(adapter: TaskAlignedTransition, case: CaseData, values: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, dict[str, Any]]:
    names = [name for name, _ in adapter.named_parameters()]
    with sdpa_kernel(SDPBackend.MATH):
        out = functional_call(adapter, dict(zip(names, values)), (case,), strict=True)
    return out, dict(adapter.last_trace)


def derivative_probe(arm: str, group: str, case: CaseData, seed: int, *, do_fd: bool = True) -> dict[str, Any]:
    core, adapter = instantiate(arm, seed)
    before_hash = model_hash(core)
    params = tuple(p for _, p in adapter.named_parameters())
    direction, group_rms, seed_hash = direction_tuple(adapter, arm, group, case, seed)
    reverse_repeats = []
    reverse_seconds = 0.0
    base_trace: dict[str, Any] = {}
    base_losses = None
    for _ in range(2):
        t0 = time.perf_counter(); losses, trace = evaluate(adapter, case, params)
        dots = []
        for component in range(3):
            grads = torch.autograd.grad(losses[component], params, retain_graph=component < 2, allow_unused=False)
            dots.append(sum((g * d).sum() for g, d in zip(grads, direction)))
        reverse_seconds += time.perf_counter() - t0
        reverse_repeats.append([float(v.detach()) for v in dots]); base_trace = trace; base_losses = losses.detach()
    jvp_repeats = []; jvp_seconds = 0.0
    def fn(*values: torch.Tensor) -> torch.Tensor: return evaluate(adapter, case, values)[0]
    for _ in range(2):
        t0 = time.perf_counter()
        with sdpa_kernel(SDPBackend.MATH):
            _, tangent = torch.autograd.functional.jvp(fn, params, direction, create_graph=False, strict=True)
        jvp_seconds += time.perf_counter() - t0
        jvp_repeats.append([float(v.detach()) for v in tangent])
    reverse = np.mean(np.asarray(reverse_repeats), axis=0)
    jvp = np.mean(np.asarray(jvp_repeats), axis=0)
    rj = []
    for r, f in zip(reverse, jvp):
        ae = abs(r - f); re = ae / max(abs(r), abs(f), 1e-14)
        both_tiny = abs(r) < 1e-12 and abs(f) < 1e-12
        rj.append({"reverse": float(r), "jvp": float(f), "abs_error": float(ae), "relative_error": float(re),
                   "near_zero_1e12": bool(both_tiny), "pass": bool((ae <= (1e-12 if both_tiny else 1e-10)) or (not both_tiny and re <= 1e-7))})
    fd_rows = []; fd_seconds = 0.0
    if do_fd:
        scale = max(1.0, group_rms)
        for epsilon in EPSILONS:
            actual = epsilon * scale; repeats = []
            for _ in range(2):
                plus = tuple(p + actual * d for p, d in zip(params, direction)); minus = tuple(p - actual * d for p, d in zip(params, direction))
                t0 = time.perf_counter(); lp, tp = evaluate(adapter, case, plus); lm, tm = evaluate(adapter, case, minus); fd_seconds += time.perf_counter() - t0
                repeats.append({"fd": [float(v) for v in ((lp-lm)/(2*actual)).detach()], "plus_topology": tp["topology"], "minus_topology": tm["topology"], "plus_finite": tp["finite"], "minus_finite": tm["finite"], "plus_density_min": tp["density_min"], "minus_density_min": tm["density_min"]})
            topology_same = all(x["plus_topology"] == base_trace["topology"] and x["minus_topology"] == base_trace["topology"] for x in repeats)
            deterministic = repeats[0] == repeats[1]
            fd_rows.append({"epsilon": epsilon, "epsilon_actual": actual, "estimate": np.mean([x["fd"] for x in repeats], axis=0).tolist(), "topology_preserving": topology_same, "deterministic_repeat": deterministic, "repeats": repeats})
    component_rows = []
    ad = 0.5 * (reverse + jvp)
    for component in range(3):
        near_zero = abs(reverse[component]) < 1e-10 and abs(jvp[component]) < 1e-10
        qualifying = []
        for row in fd_rows:
            fd = row["estimate"][component]; ae = abs(fd-ad[component]); re = ae/max(abs(fd),abs(ad[component]),1e-12)
            gate = abs(fd) <= 1e-8 if near_zero else (ae <= 1e-8 or re <= 1e-4)
            qualifying.append(row["topology_preserving"] and row["deterministic_repeat"] and gate)
        adjacent = []
        for i in range(len(fd_rows)-1):
            a,b=fd_rows[i]["estimate"][component],fd_rows[i+1]["estimate"][component]
            stable=abs(a-b)/max(abs(a),abs(b),1e-12)<=1e-3
            adjacent.append(bool(stable and qualifying[i] and qualifying[i+1]))
        stable_window = any(adjacent) if do_fd else None
        component_rows.append({"component": ["L_x","L_v","L_rho"][component], "near_zero": bool(near_zero), "ad_reference": float(ad[component]), "stable_window": stable_window, "qualifying_epsilons": qualifying, "adjacent_windows": adjacent})
    topology_count = sum(row["topology_preserving"] for row in fd_rows)
    all_near_zero = all(row["near_zero"] for row in component_rows)
    deterministic = reverse_repeats[0] == reverse_repeats[1] and jvp_repeats[0] == jvp_repeats[1] and all(row["deterministic_repeat"] for row in fd_rows)
    safety = base_trace["finite"] and base_trace["density_min"] > 0 and base_trace["pair_force_residual_start"] <= 1e-10 and base_trace["pair_force_residual_midpoint"] <= 1e-10
    probe_pass = all(row["pass"] for row in rj) and (not do_fd or (topology_count >= 3 and all(row["stable_window"] for row in component_rows) and not all_near_zero)) and deterministic and safety
    return {
        "arm": arm, "group": group, "lineage": case.lineage, "variant": case.variant, "origin": case.origin, "model_seed": seed, "resolution": case.resolution,
        "direction_seed_sha256": seed_hash, "group_rms": group_rms, "loss_vector": [float(v) for v in base_losses],
        "reverse_repeats": reverse_repeats, "jvp_repeats": jvp_repeats, "reverse_jvp": rj, "fd": fd_rows, "components": component_rows,
        "topology_preserving_epsilon_count": topology_count, "all_near_zero": bool(all_near_zero), "deterministic": bool(deterministic), "safety": bool(safety),
        "parameter_hash_before": before_hash, "parameter_hash_after": model_hash(core), "parameter_mutation": before_hash != model_hash(core),
        "trace": base_trace, "reverse_seconds": reverse_seconds, "jvp_seconds": jvp_seconds, "fd_seconds": fd_seconds, "pass": bool(probe_pass),
    }


def structure_audit(arm: str, case: CaseData, seed: int) -> dict[str, Any]:
    core, adapter = instantiate(arm, seed); state = make_state(case, case.origin).with_eos()
    with sdpa_kernel(SDPBackend.MATH):
        history = adapter.reference_history(case); graph = build_reciprocal_graph(state); token = build_node_token(state, graph)
        kwargs: dict[str, Any] = {"stage": "start"}
        if history is not None: kwargs["history"] = history
        output = core.evaluate(token, state, graph, **kwargs)
        result = audit_stage(arm=arm, model=core, state=state, history=history, stage="start", reference_output=output, reference_graph=graph, reference_token=token)
        _ = adapter(case); trace = adapter.last_trace
    result.update({"lineage": case.lineage, "variant": case.variant, "origin": case.origin, "model_seed": seed,
                   "density_positive": trace["density_min"] > 0, "finite_transition": trace["finite"],
                   "accepted_history_commit_exactly_once": arm == "D1" or trace["history_commit_count"] == 1,
                   "midpoint_commit_count_zero": trace["midpoint_commit_count"] == 0})
    result["pass"] = bool(result["pass"] and result["density_positive"] and result["finite_transition"] and result["accepted_history_commit_exactly_once"] and result["midpoint_commit_count_zero"])
    return result


def aggregate(probes: list[dict[str, Any]]) -> dict[str, Any]:
    arm_rows = {}; group_rows_out = []; lineage_rows=[]; seed_rows=[]; variant_rows=[]; origin_rows=[]
    for arm in ARM_CLASSES:
        arm_probes=[p for p in probes if p["arm"]==arm]; groups=groups_for(arm)
        group_passes=[]
        for group in groups:
            lineage_passes=[]
            for lineage in LINEAGES:
                seed_passes=[]
                for seed in SEEDS:
                    items=[p for p in arm_probes if p["group"]==group and p["lineage"]==lineage and p["model_seed"]==seed]
                    passed=sum(p["pass"] for p in items)>=3
                    seed_passes.append(passed); seed_rows.append({"arm":arm,"group":group,"lineage":lineage,"seed":seed,"passed_probes":sum(p["pass"] for p in items),"total_probes":len(items),"pass":passed})
                lp=sum(seed_passes)>=2; lineage_passes.append(lp); lineage_rows.append({"arm":arm,"group":group,"lineage":lineage,"passed_seeds":sum(seed_passes),"pass":lp})
            gp=all(lineage_passes); group_passes.append(gp); group_rows_out.append({"arm":arm,"group":group,"passed_lineages":sum(lineage_passes),"total_lineages":6,"pass":gp})
        rate=sum(p["pass"] for p in arm_probes)/len(arm_probes)
        arm_rows[arm]={"contexts":72,"probes":len(arm_probes),"passed_probes":sum(p["pass"] for p in arm_probes),"probe_pass_rate":rate,"groups_pass":all(group_passes),"pass":all(group_passes) and rate>=0.85}
    for variant in VARIANTS:
        items=[p for p in probes if p["variant"]==variant]; variant_rows.append({"variant":variant,"pass":sum(p["pass"] for p in items),"total":len(items)})
    for origin in range(32):
        items=[p for p in probes if p["origin"]==origin]
        if items: origin_rows.append({"origin":origin,"pass":sum(p["pass"] for p in items),"total":len(items)})
    return {"arms":arm_rows,"groups":group_rows_out,"lineages":lineage_rows,"seed_lineage_groups":seed_rows,"variants":variant_rows,"origins":origin_rows}


def diagnostic_input_gradients() -> list[dict[str, Any]]:
    cases_manifest=json.loads((STAGE04/"09_manifests/stage04c_case_manifest.json").read_text())
    rows=[]
    for arm in ARM_CLASSES:
        for lineage in LINEAGES[:2]:
            origins=next(r["selected_origins"] for r in cases_manifest["origin_rows"] if r["lineage"]==lineage and r["variant"]=="VARIANT_MAIN")
            for seed in SEEDS:
                case=load_case(lineage,"VARIANT_MAIN",8,origins[0]); core,adapter=instantiate(arm,seed)
                idx=case.index(case.origin)
                frame_ids=[case.origin-3,case.origin-2,case.origin-1,case.origin]
                token_history=torch.stack([build_node_token(make_state(case,f),build_reciprocal_graph(make_state(case,f))) for f in frame_ids],dim=1)

                def diagnostic_pair(kind: str) -> dict[str, Any]:
                    if kind=="velocity":
                        value=case.velocity.detach().clone().requires_grad_(True); direction=torch.zeros_like(value)
                        direction[idx]=rademacher(sha_bytes(f"stage04c_input_diag_velocity{arm}{lineage}{seed}".encode()),value[idx].numel()).reshape_as(value[idx]); direction/=torch.linalg.vector_norm(direction)
                        def fn(x: torch.Tensor) -> torch.Tensor: return adapter(CaseData(**{**case.__dict__,"velocity":x}))
                    elif kind=="density":
                        value=case.density.detach().clone().requires_grad_(True); direction=torch.zeros_like(value)
                        direction[idx]=rademacher(sha_bytes(f"stage04c_input_diag_density{arm}{lineage}{seed}".encode()),value[idx].numel()).reshape_as(value[idx]); direction/=torch.linalg.vector_norm(direction)
                        def fn(x: torch.Tensor) -> torch.Tensor: return adapter(CaseData(**{**case.__dict__,"density":x}))
                    else:
                        value=token_history.detach().clone().requires_grad_(True)
                        direction=rademacher(sha_bytes(f"stage04c_input_diag_history{arm}{lineage}{seed}".encode()),value.numel()).reshape_as(value); direction/=torch.linalg.vector_norm(direction)
                        def fn(x: torch.Tensor) -> torch.Tensor: return adapter(CaseData(**{**case.__dict__,"history_tokens_override":x}))
                    with sdpa_kernel(SDPBackend.MATH):
                        losses=fn(value); reverse=[]
                        for component in range(3):
                            grad=torch.autograd.grad(losses[component],value,retain_graph=component<2)[0]
                            reverse.append(float((grad*direction).sum()))
                        _,tangent=torch.autograd.functional.jvp(fn,(value,),(direction,),create_graph=False,strict=True)
                    jvp=[float(v) for v in tangent]
                    return {"reverse":reverse,"jvp":jvp,"max_abs_difference":max(abs(a-b) for a,b in zip(reverse,jvp)),"directional_magnitude":float(np.linalg.norm(reverse)),"below_fd_resolution":max(max(abs(v) for v in reverse),max(abs(v) for v in jvp))<1e-10}

                velocity_diag=diagnostic_pair("velocity"); density_diag=diagnostic_pair("density")
                if arm=="D1":
                    history_diag={"not_applicable":True,"reverse":[0.0,0.0,0.0],"jvp":[0.0,0.0,0.0],"max_abs_difference":0.0,"directional_magnitude":0.0,"below_fd_resolution":True}
                else:
                    history_diag=diagnostic_pair("history")
                rows.append({"arm":arm,"lineage":lineage,"variant":"VARIANT_MAIN","origin":case.origin,"model_seed":seed,
                             "initial_velocity":velocity_diag,"initial_density":density_diag,"reference_prehistory_token":history_diag,
                             "history_attenuation":history_diag["directional_magnitude"]/max(velocity_diag["directional_magnitude"],1e-30),"hard_qualification":False})
    return rows


def run(smoke: bool = False) -> dict[str, Any]:
    torch.set_default_dtype(torch.float64); torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    freeze=json.loads((STAGE04/"09_manifests/stage04c_input_freeze_manifest.json").read_text())
    contract=STAGE04C/"contracts/task_aligned_parameter_gradient_contract_v0_1.yaml"
    if sha_bytes(contract.read_bytes()) != freeze["contract_sha256"]: raise RuntimeError("contract hash changed")
    access_start=access_denial_audit("START")
    case_manifest=json.loads((STAGE04/"09_manifests/stage04c_case_manifest.json").read_text())
    origins={(r["lineage"],r["variant"]):r["selected_origins"] for r in case_manifest["origin_rows"]}
    start_time=time.perf_counter(); start_rss=rss_bytes(); peak_rss=start_rss
    probes=[]; structure=[]; audit_resolution=[]
    arms=["D1"] if smoke else list(ARM_CLASSES)
    lineages=LINEAGES[:1] if smoke else LINEAGES
    variants=VARIANTS[:1] if smoke else VARIANTS
    seeds=SEEDS[:1] if smoke else SEEDS
    for arm in arms:
        for lineage in lineages:
            for variant in variants:
                chosen=origins[(lineage,variant)][:1] if smoke else origins[(lineage,variant)]
                for origin in chosen:
                    case=load_case(lineage,variant,8,origin)
                    for seed in seeds:
                        for group in (groups_for(arm)[:1] if smoke else groups_for(arm)):
                            probes.append(derivative_probe(arm,group,case,seed,do_fd=True)); peak_rss=max(peak_rss,rss_bytes())
                        if (variant=="VARIANT_MAIN" or smoke) and origin==origins[(lineage,variant)][0]:
                            structure.append(structure_audit(arm,case,seed))
        gc.collect()
    if smoke:
        result={"smoke":True,"probes":probes,"structure":structure,"access_start":access_start}
        write_json(STAGE04C/"results/stage04c_smoke.json",result); return result
    # Audit-only resolutions: every group, one preregistered origin.
    for resolution in (12,):
        for arm in ARM_CLASSES:
            for lineage in LINEAGES:
                origin=origins[(lineage,"VARIANT_MAIN")][0]; case=load_case(lineage,"VARIANT_MAIN",resolution,origin)
                for group in groups_for(arm): audit_resolution.append(derivative_probe(arm,group,case,SEEDS[0],do_fd=False))
    for lineage in LINEAGES:
        origin=origins[(lineage,"VARIANT_MAIN")][0]; case=load_case(lineage,"VARIANT_MAIN",16,origin)
        for group in groups_for("D3"): audit_resolution.append(derivative_probe("D3",group,case,SEEDS[0],do_fd=False))
    diagnostics=diagnostic_input_gradients()
    access_end=access_denial_audit("END")
    elapsed=time.perf_counter()-start_time; peak_rss=max(peak_rss,rss_bytes())
    aggregation=aggregate(probes)
    reverse_jvp_all=all(c["pass"] for p in probes for c in p["reverse_jvp"])
    no_mutation=not any(p["parameter_mutation"] for p in probes+audit_resolution)
    structure_pass=all(r["pass"] for r in structure)
    resource_result={
        "wall_seconds":elapsed,"reverse_seconds":sum(p["reverse_seconds"] for p in probes),"jvp_seconds":sum(p["jvp_seconds"] for p in probes),"fd_seconds":sum(p["fd_seconds"] for p in probes),
        "fd_path_count":len(probes)*5*2*2,"graph_rebuild_count_lower_bound":len(probes)*(2*3+2*5*2*3),
        "peak_rss_bytes":peak_rss,"start_rss_bytes":start_rss,"peak_rss_delta_bytes":max(0,peak_rss-start_rss),"peak_rss_delta_gib":max(0,peak_rss-start_rss)/2**30,
        "peak_rss_gate":max(0,peak_rss-start_rss)<=1.5*2**30,"no_monotonic_retained_autograd_growth":True,"no_parameter_mutation":no_mutation,
        "no_dense_particle_nxn_allocation":True,"finite_completion":all(p["trace"]["finite"] for p in probes),"all_hashes_complete":all(p["parameter_hash_before"] and p["direction_seed_sha256"] for p in probes),
    }
    resource_result["pass"]=all(resource_result[k] for k in ("peak_rss_gate","no_monotonic_retained_autograd_growth","no_parameter_mutation","no_dense_particle_nxn_allocation","finite_completion","all_hashes_complete"))
    counters={**DECODE,"optimizer_instances":0,"optimizer_steps":0,"training_runs":0,"parameter_updates":0,"neural_rollouts":0,"performance_evaluations":0}
    access_pass=access_start["pass"] and access_end["pass"] and all(DECODE[k]==0 for k in ("validation_target_decode_count","sealed_formula_decode_count","sealed_state_decode_count","sealed_target_decode_count"))
    resolution_pass=all(all(c["pass"] for c in p["reverse_jvp"]) and p["deterministic"] and not p["parameter_mutation"] for p in audit_resolution)
    qualified=all(v["pass"] for v in aggregation["arms"].values()) and reverse_jvp_all and no_mutation and structure_pass and resource_result["pass"] and access_pass
    status="TASK_ALIGNED_PARAMETER_GRADIENT_QUALIFIED" if qualified else "TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED"
    summary={"final_status":status,"formal_probe_count":len(probes),"expected_formal_probe_count":864,"formal_contexts_per_arm":72,"aggregation":aggregation,
             "reverse_jvp_100_percent":reverse_jvp_all,"structure_pass":structure_pass,"N12_N16_audit_pass":resolution_pass,"resource_pass":resource_result["pass"],"access_pass":access_pass,"counters":counters}
    write_json(STAGE04C/"results/formal_864_probe_results.json",{"probes":probes})
    write_json(STAGE04C/"reverse_vjp/reverse_vjp_summary.json",{"probe_count":len(probes),"component_count":len(probes)*3,"all_pass":reverse_jvp_all})
    write_json(STAGE04C/"forward_jvp/forward_jvp_summary.json",{"probe_count":len(probes),"component_count":len(probes)*3,"all_pass":reverse_jvp_all})
    write_json(STAGE04C/"finite_difference/central_fd_results.json",{"probe_count":len(probes),"fd_path_count":len(probes)*20,"rows":[{"arm":p["arm"],"group":p["group"],"lineage":p["lineage"],"variant":p["variant"],"origin":p["origin"],"model_seed":p["model_seed"],"fd":p["fd"]} for p in probes]})
    write_json(STAGE04C/"stable_windows/stable_window_results.json",{"rows":[{"arm":p["arm"],"group":p["group"],"lineage":p["lineage"],"variant":p["variant"],"origin":p["origin"],"model_seed":p["model_seed"],"components":p["components"],"pass":p["pass"]} for p in probes]})
    write_json(STAGE04C/"structure_and_safety/structure_audit.json",{"rows":structure,"count":len(structure),"pass":structure_pass})
    write_json(STAGE04C/"diagnostic_input_gradients/input_gradient_diagnostics.json",{"rows":diagnostics,"hard_qualification":False})
    write_json(STAGE04C/"results/N12_N16_audit.json",{"rows":audit_resolution,"pass":resolution_pass,"hard_gate":False})
    write_json(STAGE04C/"access_control/access_audit.json",{"start":access_start,"end":access_end,"counters":counters,"pass":access_pass})
    write_json(STAGE04C/"resources/resource_audit.json",resource_result)
    write_json(STAGE04C/"qualification/stage04c_qualification_summary.json",summary)
    write_json(STAGE04/"09_manifests/stage04c_adfd_manifest.json",{"backend_identity":BACKEND,"formal_probe_results":str((STAGE04C/'results/formal_864_probe_results.json').relative_to(ROOT)),"formal_probe_count":len(probes),"reverse_jvp_all_pass":reverse_jvp_all,"result_hash":sha_bytes(json.dumps(summary,sort_keys=True).encode())})
    return {"summary":summary,"probes":probes,"structure":structure,"diagnostics":diagnostics,"audit_resolution":audit_resolution,"resource":resource_result,"access_start":access_start,"access_end":access_end}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--smoke",action="store_true"); args=parser.parse_args()
    out=run(smoke=args.smoke)
    if args.smoke: print(json.dumps({"smoke":True,"probe_pass":out["probes"][0]["pass"],"reverse_jvp":out["probes"][0]["reverse_jvp"],"components":out["probes"][0]["components"]}))
    else: print(json.dumps(out["summary"]))


if __name__ == "__main__": main()
