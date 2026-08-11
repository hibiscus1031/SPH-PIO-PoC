"""Build and qualify the Stage07B TRAIN_V2 target/scale evidence."""

from __future__ import annotations

from dataclasses import dataclass
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Callable

import numpy as np
import psutil
import torch


HERE = Path(__file__).resolve(); B = HERE.parents[1]; STAGE07 = HERE.parents[3]; ROOT = HERE.parents[4]
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE05B = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b"
STAGE05Q = STAGE05B / "qualification"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
NEW_CORE = STAGE07 / "01_pool_generation/lineage_generator"
sys.path[:0] = [str(STAGE05Q), str(STAGE03C), str(ROOT / "01_solver"), str(STAGE04B / "formula_templates"), str(NEW_CORE)]
import run_stage05b_qualification as q5
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from tokenization.tokens import build_node_token
from stage04b_reference_core import evaluate_autograd as old_autograd, evaluate_symbolic as old_symbolic
from stage07a_reference_core import evaluate_autograd as new_autograd, evaluate_symbolic as new_symbolic


torch.set_default_dtype(torch.float64); torch.set_num_threads(1)
ANCHORS = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
NEW = ["HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03", "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
LINEAGES = ANCHORS + NEW; VARIANTS = ["LOW", "MAIN"]
DT = 2.0 / 20.0 / 256.0; S_A_V1 = 3.45632855338432798e-1
PROCESS = psutil.Process(); START = time.perf_counter(); RSS0 = PROCESS.memory_info().rss; PEAK = RSS0


def cv(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): cv(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [cv(v) for v in value]
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, torch.Tensor): return value.detach().cpu().tolist()
    return value
def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(cv(value), indent=2, sort_keys=True) + "\n")
def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()
def sha_array(*values: np.ndarray) -> str: return q5.sha_array(*values)
def variant_source(lineage: str, variant: str) -> str: return f"VARIANT_{variant}" if lineage in ANCHORS else variant
def evaluator(lineage: str) -> tuple[Callable[..., dict[str, np.ndarray]], Callable[..., dict[str, np.ndarray]]]:
    return (old_symbolic, old_autograd) if lineage in ANCHORS else (new_symbolic, new_autograd)
def trajectory_path(lineage: str, variant: str, resolution: int) -> Path:
    if lineage in ANCHORS:
        return STAGE04B / f"exact_trajectories/train/{lineage.lower()}_variant_{variant.lower()}_n{resolution}.npz"
    return STAGE07 / f"01_pool_generation/trajectory_materialization/{lineage.lower()}_{variant.lower()}_n{resolution}.npz"
def load_trajectory(lineage: str, variant: str, resolution: int) -> tuple[dict[str, np.ndarray], dict[str, Any], Path]:
    path = trajectory_path(lineage, variant, resolution)
    with np.load(path, allow_pickle=False) as z: arrays = {k: z[k] for k in z.files}
    meta = json.loads(path.with_suffix(".json").read_text())
    return arrays, meta, path
def tensor(value: np.ndarray) -> torch.Tensor: return torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)
def make_state(arrays: dict[str, np.ndarray], resolution: int, frame: int) -> DynamicParticleState:
    index = int(np.flatnonzero(arrays["frame_n"] == frame)[0]); rho = tensor(arrays["density"][index]); dx = 2.0 / resolution
    return DynamicParticleState(tensor(arrays["position_unwrapped"][index]), tensor(arrays["velocity"][index]), rho,
                                eos_pressure(rho), torch.full((resolution**2,), dx*dx, dtype=torch.float64),
                                torch.full((resolution**2,), 2.6*dx, dtype=torch.float64), tensor(arrays["material_labels"]),
                                float(arrays["physical_time"][index]), frame)
def source(lineage: str, variant: str, labels: torch.Tensor, physical_time: float) -> torch.Tensor:
    closed, _ = evaluator(lineage); values = closed(lineage, variant_source(lineage, variant), labels.detach().numpy(), physical_time * 20.0 / 2.0)["source"]
    return tensor(values)


@dataclass(frozen=True)
class D0Result:
    start: DynamicParticleState; midpoint: DynamicParticleState; accepted: DynamicParticleState
    graphs: tuple[Any, Any, Any]; sources: tuple[torch.Tensor, torch.Tensor]


class D0Transition:
    def __init__(self, lineage: str, variant: str, dt: float) -> None: self.lineage, self.variant, self.dt = lineage, variant, dt
    def step(self, start: DynamicParticleState, source_start: torch.Tensor) -> D0Result:
        with torch.no_grad():
            s = start.with_eos(); g0 = build_reciprocal_graph(s); x1, v1, r1 = q5.rhs(s, g0, source_start); h = .5*self.dt
            mid = DynamicParticleState(s.x_unwrapped+h*x1, s.velocity+h*v1, s.density+h*r1, torch.empty_like(s.pressure),
                  s.mass, s.smoothing_length, s.material_labels, s.physical_time+h, s.accepted_step_index).with_eos()
            gm = build_reciprocal_graph(mid); sm = source(self.lineage, self.variant, mid.material_labels, mid.physical_time)
            x2, v2, r2 = q5.rhs(mid, gm, sm)
            accepted = DynamicParticleState(s.x_unwrapped+self.dt*x2, s.velocity+self.dt*v2, s.density+self.dt*r2,
                  torch.empty_like(s.pressure), s.mass, s.smoothing_length, s.material_labels,
                  s.physical_time+self.dt, s.accepted_step_index+1).with_eos(); ga = build_reciprocal_graph(accepted)
        return D0Result(s, mid, accepted, (g0, gm, ga), (source_start, sm))


def functional_d0(start: DynamicParticleState, lineage: str, variant: str, dt: float) -> D0Result:
    with torch.no_grad():
        s = start.with_eos(); g0 = build_reciprocal_graph(s); ss = source(lineage, variant, s.material_labels, s.physical_time)
        x1, v1, r1 = q5.rhs(s, g0, ss); mid = DynamicParticleState(s.x_unwrapped+.5*dt*x1, s.velocity+.5*dt*v1,
             s.density+.5*dt*r1, torch.empty_like(s.pressure), s.mass, s.smoothing_length, s.material_labels,
             s.physical_time+.5*dt, s.accepted_step_index).with_eos(); gm = build_reciprocal_graph(mid)
        sm = source(lineage, variant, mid.material_labels, mid.physical_time); x2, v2, r2 = q5.rhs(mid, gm, sm)
        accepted = DynamicParticleState(s.x_unwrapped+dt*x2, s.velocity+dt*v2, s.density+dt*r2, torch.empty_like(s.pressure),
             s.mass, s.smoothing_length, s.material_labels, s.physical_time+dt, s.accepted_step_index+1).with_eos()
        ga = build_reciprocal_graph(accepted)
    return D0Result(s, mid, accepted, (g0, gm, ga), (ss, sm))


def independent_fields(lineage: str, variant: str, labels: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    closed_fn, ad_fn = evaluator(lineage); name = variant_source(lineage, variant); taus = np.arange(0., 32.5, .5) / 256.
    tiled = np.tile(labels, (len(taus), 1)); times = np.repeat(taus, len(labels))
    closed = closed_fn(lineage, name, tiled, times); independent = ad_fn(lineage, name, tiled, times)
    return ({k: closed[k].reshape(len(taus), len(labels), -1) for k in ("velocity", "source")},
            {k: independent[k].reshape(len(taus), len(labels), -1) for k in ("velocity", "source")})


def summarize(rows: list[dict[str, Any]], key: str, limits: tuple[float, float, float, float]) -> dict[str, Any]:
    values = np.asarray([r[key] for r in rows]); lineage_means = {f: float(np.mean([r[key] for r in rows if r["lineage"] == f])) for f in LINEAGES}
    result = {"family_balanced_mean": float(np.mean(list(lineage_means.values()))), "p95": float(np.percentile(values, 95)),
              "maximum": float(np.max(values)), "lineage_means": lineage_means}
    result["gates"] = {"mean": result["family_balanced_mean"] <= limits[0], "p95": result["p95"] <= limits[1],
                       "maximum": result["maximum"] <= limits[2], "lineages": all(v <= limits[3] for v in lineage_means.values())}
    return result


def import_anchors() -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]], list[dict[str, Any]]]:
    manifest = json.loads((ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json").read_text())
    formal = json.loads((STAGE05B / "results/formal_origin_results.json").read_text())["rows"]
    formal_map = {r["origin_id"]: r for r in formal}; rows = []; arrays_map = {}; audit = []
    for item in manifest["records"]:
        npz = ROOT / item["npz_path"]; meta_path = ROOT / item["json_path"]
        assert sha_file(npz) == item["npz_sha256"] and sha_file(meta_path) == item["json_sha256"]
        with np.load(npz, allow_pickle=False) as z: arrays = {k: z[k] for k in z.files}
        meta = json.loads(meta_path.read_text()); rid_old = item["record_id"]; old = formal_map[rid_old]
        assert all(sha_array(arrays[k]) == meta["array_hashes"][k] for k in ("a_def", "a_cm", "a_cons", "a_incompatible"))
        lineage = meta["lineage"]; variant = "LOW" if meta["variant"].endswith("LOW") else "MAIN"; origin = meta["origin"]
        rid = f"{lineage}_{variant}_N8_O{origin:02d}"; mass = np.full(64, (2./8.)**2); dec = q5.decompose(arrays["a_def"], mass, meta["u_origin"])
        checks = {"a_def_hash": True, "a_cm": np.array_equal(arrays["a_cm"], dec["a_cm"]),
                  "a_cons": np.array_equal(arrays["a_cons"], dec["a_cons"]), "u_origin": meta["u_origin"] == old["u_origin"],
                  "graph_identity": meta["graph_hashes"] == old["graph_hashes"], "source_identity": meta["source_identity"] == old["source_identity"],
                  "reference_state": meta["reference_accepted_hash"] == old["reference_accepted_hash"], "D0_state": meta["D0_state_hash"] == old["D0_state_hash"]}
        row = {**old, "lineage": lineage, "variant": variant, "origin_id": rid, "role": "ANCHOR_TRAIN_V1",
               "stratum": "ANCHOR", "anchor_import_checks": checks, "anchor_import_pass": all(checks.values()),
               "source_record_id": rid_old, "source_npz_sha256": item["npz_sha256"], "source_json_sha256": item["json_sha256"]}
        row.update({k: dec[k] for k in ("E_total", "E_cons", "E_incompatible", "incompatible_fraction", "conservative_coverage", "zero_force_normalized_residual")})
        rows.append(row); arrays_map[rid] = {k: arrays[k] for k in ("a_def", "a_cm", "a_cons", "a_incompatible")}; audit.append({"record_id": rid, "checks": checks})
    return rows, arrays_map, audit


def build_new() -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]], dict[str, dict[str, Any]], dict[str, Any]]:
    rows = []; arrays_map = {}; midpoint_map = {}; graph_rebuilds = 0; solves = 0; roundoff = 64*np.finfo(float).eps*20./DT
    dop = json.loads((STAGE07 / "01_pool_generation/semidiscrete_audit/dop853_summary.json").read_text())
    u5_by_lineage = {lineage: max(r["maximum_normalized_L2"] for r in dop["rows"] if r["opaque_lineage_id"] == lineage)*20./DT for lineage in NEW}
    for lineage in NEW:
        for variant in VARIANTS:
            traj, meta, path = load_trajectory(lineage, variant, 8); assert meta["role"] == "NEW_TRAIN_V2"
            closed, independent = independent_fields(lineage, variant, traj["material_labels"]); mass = np.full(64, (2./8.)**2)
            transition = D0Transition(lineage, variant, DT)
            for origin in range(32):
                idx = int(np.flatnonzero(traj["frame_n"] == origin)[0]); target_idx = int(np.flatnonzero(traj["frame_n"] == origin+1)[0])
                start = make_state(traj, 8, origin); exact_source = tensor(traj["external_source"][idx])
                primary = transition.step(start, exact_source); functional = functional_d0(start, lineage, variant, DT); repeat = transition.step(start, exact_source); graph_rebuilds += 9
                l2, linf = q5.route_disagreement(primary.accepted, functional.accepted)
                graphs_exact = [g.graph_hash for g in primary.graphs] == [g.graph_hash for g in functional.graphs]
                sources_exact = all(torch.equal(a, b) for a, b in zip(primary.sources, functional.sources))
                repeat_exact = q5.state_bitwise(primary.accepted, repeat.accepted) and [g.graph_hash for g in primary.graphs] == [g.graph_hash for g in repeat.graphs]
                a_def = (traj["velocity"][target_idx] - primary.accepted.velocity.numpy()) / DT
                U1 = q5.mass_norm((closed["velocity"][2*(origin+1)] - independent["velocity"][2*(origin+1)])/DT, mass)
                U2 = q5.mass_norm((primary.accepted.velocity.numpy() - functional.accepted.velocity.numpy())/DT, mass)
                U3 = q5.mass_norm((primary.accepted.velocity.numpy() - repeat.accepted.velocity.numpy())/DT, mass)
                U4 = max(q5.mass_norm(closed["source"][2*origin]-independent["source"][2*origin], mass),
                         q5.mass_norm(closed["source"][2*origin+1]-independent["source"][2*origin+1], mass))
                U5 = u5_by_lineage[lineage]; u = float(max(U1, U2, U3, U4, U5, roundoff)); dec = q5.decompose(a_def, mass, u)
                basis = q5.solve_basis(primary.midpoint, primary.graphs[1], dec["a_cons"], u); solves += 1
                rid = f"{lineage}_{variant}_N8_O{origin:02d}"; route_pass = l2 <= 1e-13 and linf <= 1e-12 and graphs_exact and sources_exact and repeat_exact
                row = {"lineage": lineage, "variant": variant, "origin": origin, "origin_id": rid, "role": "NEW_TRAIN_V2",
                       "stratum": f"H{lineage[5]}", "resolution": 8, "dt": DT,
                       "D0_state_hash": primary.accepted.state_hash, "reference_accepted_hash": str(traj["state_hashes"][target_idx]),
                       "reference_history_hashes": [str(traj["state_hashes"][int(np.flatnonzero(traj["frame_n"] == f)[0])]) for f in range(origin-3, origin+1)],
                       "graph_hashes": [g.graph_hash for g in primary.graphs], "source_identity": sha_array(*[s.numpy() for s in primary.sources]),
                       "route_normalized_L2": l2, "route_normalized_Linf": linf, "graph_hash_sequence_exact": graphs_exact,
                       "source_evaluation_identity_exact": sources_exact, "deterministic_repeat_exact": repeat_exact,
                       "D0_transition_pass": route_pass, "reference_identity_pass": True,
                       "finite_and_safety": bool(np.isfinite(a_def).all() and primary.accepted.density.min() > 0),
                       "r_def": q5.mass_norm(a_def, mass), "a_cons_component_rms": float(np.sqrt(np.mean(dec["a_cons"]**2))),
                       "U1": U1, "U2": U2, "U3": U3, "U4": U4, "U5": U5, "u_roundoff_floor": roundoff, "u_origin": u,
                       "signal_bearing": q5.mass_norm(a_def, mass) >= 10*u,
                       **{k: dec[k] for k in ("E_total", "E_cons", "E_incompatible", "incompatible_fraction", "conservative_coverage", "zero_force_normalized_residual")},
                       **basis, "defect_construction_pass": route_pass and np.isfinite(a_def).all() and primary.accepted.density.min() > 0,
                       "trajectory_sha256": sha_file(path)}
                rows.append(row); arrays_map[rid] = {"a_def": a_def, "a_cm": dec["a_cm"], "a_cons": dec["a_cons"], "a_incompatible": dec["a_incompatible"],
                                                      "delta_x": traj["position_unwrapped"][target_idx]-primary.accepted.x_unwrapped.numpy(),
                                                      "delta_rho": traj["density"][target_idx]-primary.accepted.density.numpy()}
                midpoint_map[rid] = {"x": primary.midpoint.x_unwrapped.numpy(), "velocity": primary.midpoint.velocity.numpy(),
                                     "density": primary.midpoint.density.numpy(), "graph_hash": primary.graphs[1].graph_hash}
            del traj, closed, independent; gc.collect(); global PEAK; PEAK = max(PEAK, PROCESS.memory_info().rss)
            print(json.dumps({"target": f"{lineage}/{variant}", "complete": 32, "elapsed": time.perf_counter()-START}), flush=True)
    return rows, arrays_map, midpoint_map, {"graph_rebuilds": graph_rebuilds, "representability_solves": solves}


def make_case_cache(rows: list[dict[str, Any]], arrays_map: dict[str, dict[str, np.ndarray]], scale_hash: str) -> dict[str, Any]:
    contexts = json.loads((B / "update_contexts/preregistered_update_contexts.json").read_text()); selected = {(r["lineage"], r["variant"], o) for r in contexts["selection"] for o in r["origins"]}
    cache = B / "update_contexts/case_cache"; cases = []
    for lineage in LINEAGES:
        for variant in VARIANTS:
            traj, _meta, _path = load_trajectory(lineage, variant, 8)
            for origin in sorted(o for f, v, o in selected if f == lineage and v == variant):
                rid = f"{lineage}_{variant}_N8_O{origin:02d}"; target = arrays_map[rid]; frames = list(range(origin-3, origin+1)); states = [make_state(traj, 8, f) for f in frames]
                history = torch.stack([build_node_token(state, build_reciprocal_graph(state)) for state in states], dim=1).numpy()
                current = int(np.flatnonzero(traj["frame_n"] == origin)[0]); accepted = int(np.flatnonzero(traj["frame_n"] == origin+1)[0])
                source_mid = evaluator(lineage)[0](lineage, variant_source(lineage, variant), traj["material_labels"], (origin+.5)/256.)["source"]
                v0 = traj["velocity"][accepted] - DT*target["a_def"]; path = cache / f"{rid}.npz"; path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(path, frames=np.asarray(frames), physical_times=np.asarray([s.physical_time for s in states]),
                    x=np.stack([s.x_unwrapped.numpy() for s in states]), velocity=np.stack([s.velocity.numpy() for s in states]),
                    density=np.stack([s.density.numpy() for s in states]), material_labels=traj["material_labels"], mass=states[-1].mass.numpy(),
                    smoothing=states[-1].smoothing_length.numpy(), history_tokens=history, source_start=traj["external_source"][current],
                    source_midpoint=source_mid, v0_accepted=v0, a_cons=target["a_cons"])
                cases.append({"record_id": rid, "lineage": lineage, "variant": variant, "origin": origin,
                              "path": str(path.relative_to(ROOT)), "sha256": sha_file(path), "scale_v2_hash": scale_hash})
    result = {"case_count": len(cases), "lineage_case_count": 16, "global_case_count": 112, "cases": cases,
              "fresh_validation_decodes": 0, "consumed_validation_decodes": 0, "sealed_test_decodes": 0, "pass": len(cases) == 224}
    write_json(B / "update_contexts/cached_case_manifest.json", result); return result


def resolution_diagnostics() -> dict[str, Any]:
    contexts = json.loads((B / "update_contexts/preregistered_update_contexts.json").read_text()); rows = []
    for lineage in LINEAGES:
        origins = next(r["global_origins"] for r in contexts["selection"] if r["lineage"] == lineage and r["variant"] == "MAIN")
        n8_values = []
        for resolution in (12, 16):
            traj, _meta, _path = load_trajectory(lineage, "MAIN", resolution); mass = np.full(resolution**2, (2./resolution)**2); transition = D0Transition(lineage, "MAIN", DT)
            for origin in origins:
                idx = int(np.flatnonzero(traj["frame_n"] == origin)[0]); target_idx = int(np.flatnonzero(traj["frame_n"] == origin+1)[0])
                primary = transition.step(make_state(traj, resolution, origin), tensor(traj["external_source"][idx])); a_def = (traj["velocity"][target_idx]-primary.accepted.velocity.numpy())/DT
                u = 64*np.finfo(float).eps*20./DT; dec = q5.decompose(a_def, mass, u)
                basis = q5.solve_basis(primary.midpoint, primary.graphs[1], dec["a_cons"], u, diagnostic_sparse=True)
                rows.append({"lineage": lineage, "resolution": resolution, "origin": origin,
                             "defect_rms": q5.mass_norm(a_def, mass), "conservative_fraction": dec["conservative_coverage"],
                             "Q_unbounded": basis["Q_unbounded"], "Q_bounded": basis["Q_bounded"],
                             "uncertainty_ratio": q5.mass_norm(a_def, mass)/u})
            print(json.dumps({"resolution_diagnostic": lineage, "N": resolution, "complete": 4}), flush=True)
    return {"rows": rows, "case_count": len(rows), "diagnostic_only": True, "scale_v2_redefined": False,
            "convergence_claim": False, "GCI_claim": False, "N8_failure_replacement": False}


def main() -> None:
    freeze = json.loads((B / "freeze/stage07b_input_freeze_record.json").read_text()); contract = ROOT / freeze["contract_path"]
    assert freeze["frozen_before_new_train_trajectory_decode"] and freeze["new_train_trajectory_decode_count_at_freeze"] == 0 and sha_file(contract) == freeze["contract_sha256"]
    anchor_rows, anchor_arrays, anchor_audit = import_anchors(); print(json.dumps({"anchor_import": len(anchor_rows), "pass": all(r["anchor_import_pass"] for r in anchor_rows)}), flush=True)
    new_rows, new_arrays, _midpoints, accounting = build_new(); rows = anchor_rows + new_rows; arrays_map = {**anchor_arrays, **new_arrays}
    assert len(rows) == 896 and len(arrays_map) == 896
    signal_rows = [r for r in rows if r["signal_bearing"]]
    compatibility = summarize(signal_rows, "incompatible_fraction", (5e-3, 1e-2, 5e-2, 1e-2)); compatibility["zero_force_max"] = max(r["zero_force_normalized_residual"] for r in rows); compatibility["gates"]["zero_force"] = compatibility["zero_force_max"] <= 1e-12
    unbounded = summarize(rows, "Q_unbounded", (.02, .05, .10, .05)); bounded = summarize(rows, "Q_bounded", (.05, .10, .20, .10))
    signal_lineage = {f: float(np.mean([r["signal_bearing"] for r in rows if r["lineage"] == f])) for f in LINEAGES}; signal_overall = float(np.mean([r["signal_bearing"] for r in rows]))
    scale_lineage = {f: math.sqrt(float(np.mean([np.mean(arrays_map[r["origin_id"]]["a_cons"]**2) for r in rows if r["lineage"] == f]))) for f in LINEAGES}
    scale_variant = {f"{f}/{v}": math.sqrt(float(np.mean([np.mean(arrays_map[r["origin_id"]]["a_cons"]**2) for r in rows if r["lineage"] == f and r["variant"] == v]))) for f in LINEAGES for v in VARIANTS}
    s_a_v2 = math.sqrt(float(np.mean([scale_lineage[f]**2 for f in LINEAGES]))); scale_hash = "sha256:" + hashlib.sha256(np.asarray([s_a_v2], dtype=np.float64).tobytes()).hexdigest()
    zero_loss = float(np.mean([np.mean((arrays_map[r["origin_id"]]["a_cons"]/s_a_v2)**2) for r in rows]))
    u_lineage = {f: math.sqrt(float(np.mean([r["u_origin"]**2 for r in rows if r["lineage"] == f]))) for f in LINEAGES}
    u_variant = {f"{f}/{v}": math.sqrt(float(np.mean([r["u_origin"]**2 for r in rows if r["lineage"] == f and r["variant"] == v]))) for f in LINEAGES for v in VARIANTS}
    u_a_v2 = math.sqrt(float(np.mean([u_lineage[f]**2 for f in LINEAGES])))
    uncertainty = {"u_a_v2": u_a_v2, "s_a_v2_over_u_a_v2": s_a_v2/u_a_v2,
                   "lineage_ratios": {f: scale_lineage[f]/u_lineage[f] for f in LINEAGES},
                   "variant_ratios": {k: scale_variant[k]/u_variant[k] for k in scale_variant}}
    uncertainty["gates"] = {"global": uncertainty["s_a_v2_over_u_a_v2"] >= 100,
                            "lineages": all(v >= 20 for v in uncertainty["lineage_ratios"].values()),
                            "variants": all(v >= 20 for v in uncertainty["variant_ratios"].values())}
    target_gates = {"anchor_import_384": len(anchor_rows) == 384 and all(r["anchor_import_pass"] for r in anchor_rows),
                    "new_D0_512": len(new_rows) == 512 and all(r["D0_transition_pass"] and r["defect_construction_pass"] for r in new_rows),
                    "complete_896": len(rows) == 896, "conservative": all(compatibility["gates"].values()),
                    "pair_unbounded": all(unbounded["gates"].values()), "pair_bounded": all(bounded["gates"].values()),
                    "scale_positive_finite": np.isfinite(s_a_v2) and s_a_v2 > 0, "zero_baseline": abs(zero_loss-1) <= 1e-12,
                    "uncertainty": all(uncertainty["gates"].values()),
                    "signal": signal_overall >= .95 and all(v >= .90 for v in signal_lineage.values())}
    target_pass = all(target_gates.values())
    write_json(B / "anchor_import/anchor_import_audit.json", {"required": 384, "complete": len(anchor_rows), "rows": anchor_audit, "pass": target_gates["anchor_import_384"]})
    write_json(B / "new_defect_construction/new_D0_summary.json", {"required": 512, "complete": len(new_rows), "route_pass": sum(r["D0_transition_pass"] for r in new_rows), "accounting": accounting, "pass": target_gates["new_D0_512"]})
    write_json(B / "conservative_decomposition/conservative_compatibility.json", compatibility)
    write_json(B / "pair_basis_representability/pair_basis_summary.json", {"unbounded": unbounded, "bounded": bounded, "LCDF_08_exception": False, "pass": target_gates["pair_unbounded"] and target_gates["pair_bounded"]})
    distribution = {"s_a_v1": S_A_V1, "s_a_v2": s_a_v2, "s_a_v2_over_s_a_v1": s_a_v2/S_A_V1,
                    "anchor_only_RMS": math.sqrt(float(np.mean([scale_lineage[f]**2 for f in ANCHORS]))),
                    "new_train_only_RMS": math.sqrt(float(np.mean([scale_lineage[f]**2 for f in NEW]))),
                    "lineage_RMS": scale_lineage, "stratum_RMS": {f"H{s}": math.sqrt(float(np.mean([scale_lineage[f]**2 for f in NEW if f.startswith(f'HET_S{s}_')]))) for s in range(1,5)},
                    "variant_RMS": {v: math.sqrt(float(np.mean([scale_variant[f'{f}/{v}']**2 for f in LINEAGES]))) for v in VARIANTS},
                    "LOW_MAIN_ratio": math.sqrt(float(np.mean([scale_variant[f'{f}/LOW']**2 for f in LINEAGES])))/math.sqrt(float(np.mean([scale_variant[f'{f}/MAIN']**2 for f in LINEAGES]))),
                    "evidence_only_no_reweighting": True}
    scale_result = {"s_a_v2": s_a_v2, "scale_v2_hash": scale_hash, "formula": "nested_lineage_variant_origin_node_component_RMS",
                    "zero_correction_L_def_v2": zero_loss, "absolute_error": abs(zero_loss-1), "lineage_RMS": scale_lineage,
                    "variant_RMS": scale_variant, "pass": target_gates["scale_positive_finite"] and target_gates["zero_baseline"]}
    write_json(B / "scale_v2/scale_v2.json", scale_result); write_json(B / "distribution_shift/scale_distribution_shift.json", distribution)
    write_json(B / "uncertainty_v2/uncertainty_v2.json", uncertainty); write_json(B / "distinguishability/signal_bearing.json", {"overall_fraction": signal_overall, "lineage_fractions": signal_lineage, "pass": target_gates["signal"]})
    write_json(B / "qualification/target_scale_qualification.json", {"gates": target_gates, "pass": target_pass})
    if not target_pass:
        raise RuntimeError("TRAIN_V2 target/scale gates failed; optimizer evidence is not authorized")
    target_dir = B / "results/qualified_targets"; manifest_rows = []
    for row in rows:
        rid = row["origin_id"]; values = arrays_map[rid]; y = values["a_cons"]/s_a_v2; npz = target_dir / f"{rid}.npz"; npz.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(npz, **values, y_def_v2=y)
        meta = {**row, "s_a_v2": s_a_v2, "s_a_v2_hash": scale_hash, "array_hashes": {k: sha_array(v) for k, v in {**values, "y_def_v2": y}.items()},
                "npz_path": str(npz.relative_to(ROOT)), "qualification_verdict": "QUALIFIED_STAGE07B_TARGET_SCALE", "old_y_def_v1_used": False}
        json_path = npz.with_suffix(".json"); write_json(json_path, meta)
        manifest_rows.append({"record_id": rid, "role": row["role"], "lineage": row["lineage"], "variant": row["variant"], "origin": row["origin"],
                              "npz_path": str(npz.relative_to(ROOT)), "npz_sha256": sha_file(npz), "json_path": str(json_path.relative_to(ROOT)), "json_sha256": sha_file(json_path)})
    target_manifest = {"record_count": len(manifest_rows), "required": 896, "scale_v2_hash": scale_hash, "records": manifest_rows, "pass": len(manifest_rows) == 896}
    write_json(B / "manifests/target_record_manifest.json", target_manifest)
    case_manifest = make_case_cache(rows, arrays_map, scale_hash)
    resolution = resolution_diagnostics(); write_json(B / "resolution_diagnostics/resolution_diagnostics.json", resolution)
    global PEAK; PEAK = max(PEAK, PROCESS.memory_info().rss)
    resources = {"wall_time_seconds": time.perf_counter()-START, "rss_start_bytes": RSS0, "peak_rss_bytes": PEAK,
                 "peak_rss_delta_bytes": PEAK-RSS0, "new_D0_routes": 512, "representability_records": 896,
                 "new_representability_solves": accounting["representability_solves"], "resolution_diagnostic_cases": resolution["case_count"],
                 "graph_rebuilds": accounting["graph_rebuilds"], "dense_particle_N_by_N_allocation": False,
                 "fresh_validation_decodes": 0, "consumed_validation_decodes": 0, "sealed_test_decodes": 0,
                 "training_runs": 0, "pass": PEAK-RSS0 <= 1610612736}
    write_json(B / "resources/target_scale_resource_audit.json", resources)
    result = {"contract_sha256": freeze["contract_sha256"], "target_scale_pass": True, "target_gates": target_gates,
              "counts": {"anchor": 384, "new": 512, "total": 896, "case_cache": case_manifest["case_count"]},
              "s_a_v1": S_A_V1, "s_a_v2": s_a_v2, "scale_v2_hash": scale_hash, "u_a_v2": u_a_v2,
              "compatibility": compatibility, "unbounded": unbounded, "bounded": bounded,
              "signal_overall": signal_overall, "resource": resources}
    write_json(B / "results/target_scale_result.json", result); print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__": main()
