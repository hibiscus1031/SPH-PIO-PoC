"""Diagnostic-only N12/N16 Stage 05C gradient and local-descent checks."""

from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE05C = HERE.parents[1]
ROOT = HERE.parents[4]
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE05C / "qualification"), str(STAGE03C), str(ROOT / "01_solver"), str(STAGE04B / "formula_templates")]

import run_stage05c_arm as q
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from stage04b_reference_core import CS, L, RHO0, SUPPORT_OVER_DX, evaluate_symbolic
from tokenization.tokens import build_node_token


PROCESS = psutil.Process()
SEED = 20500501
ARMS = ("D1", "D2", "D3")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def import_access() -> Any:
    path = STAGE05C / "access_control/stage05c_train_access.py"
    spec = importlib.util.spec_from_file_location("stage05c_diag_access", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ACCESS = import_access()


def tensor(value: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)


def make_state(arrays: dict[str, np.ndarray], resolution: int, frame: int) -> DynamicParticleState:
    hits = np.flatnonzero(arrays["frame_n"] == frame)
    if len(hits) != 1:
        raise RuntimeError(f"missing diagnostic frame {frame}")
    index = int(hits[0])
    rho = tensor(arrays["density"][index])
    dx = L / resolution
    return DynamicParticleState(
        tensor(arrays["position_unwrapped"][index]),
        tensor(arrays["velocity"][index]),
        rho,
        eos_pressure(rho),
        torch.full((resolution * resolution,), RHO0 * dx * dx, dtype=torch.float64),
        torch.full((resolution * resolution,), SUPPORT_OVER_DX * dx, dtype=torch.float64),
        tensor(arrays["material_labels"]),
        float(arrays["physical_time"][index]),
        frame,
    )


def make_case(lineage: str, resolution: int, origin: int, decode: dict[str, int]) -> tuple[q.Case, dict[str, Any]]:
    stem = f"{lineage.lower()}_variant_main_n{resolution}"
    npz_path = STAGE04B / f"exact_trajectories/train/{stem}.npz"
    json_path = npz_path.with_suffix(".json")
    arrays = ACCESS.load_npz(npz_path)
    metadata = ACCESS.load_json(json_path)
    decode["diagnostic_train_trajectory_npz_decode_count"] += 1
    decode["diagnostic_train_trajectory_json_decode_count"] += 1
    if metadata["role"] != "TRAIN_LINEAGE":
        raise RuntimeError("diagnostic trajectory is not TRAIN")

    frames = list(range(origin - 3, origin + 1))
    states = [make_state(arrays, resolution, frame) for frame in frames]
    start = states[-1].with_eos()
    start_index = int(np.flatnonzero(arrays["frame_n"] == origin)[0])
    target_index = int(np.flatnonzero(arrays["frame_n"] == origin + 1)[0])
    source_start = tensor(arrays["external_source"][start_index])
    source_mid = tensor(evaluate_symbolic(lineage, "VARIANT_MAIN", arrays["material_labels"], (origin + 0.5) / 256.0)["source"])

    with torch.no_grad():
        g0 = build_reciprocal_graph(start)
        x1, a1, r1 = q.rhs(start, g0, source_start)
        midpoint = DynamicParticleState(
            start.x_unwrapped + 0.5 * q.DT * x1,
            start.velocity + 0.5 * q.DT * a1,
            start.density + 0.5 * q.DT * r1,
            torch.empty_like(start.pressure),
            start.mass,
            start.smoothing_length,
            start.material_labels,
            start.physical_time + 0.5 * q.DT,
            start.accepted_step_index,
        ).with_eos()
        gm = build_reciprocal_graph(midpoint)
        x2, a2, r2 = q.rhs(midpoint, gm, source_mid)
        accepted = DynamicParticleState(
            start.x_unwrapped + q.DT * x2,
            start.velocity + q.DT * a2,
            start.density + q.DT * r2,
            torch.empty_like(start.pressure),
            start.mass,
            start.smoothing_length,
            start.material_labels,
            start.physical_time + q.DT,
            start.accepted_step_index + 1,
        ).with_eos()

    reference_velocity = tensor(arrays["velocity"][target_index])
    a_def = (reference_velocity - accepted.velocity) / q.DT
    center_of_mass = (start.mass[:, None] * a_def).sum(0) / start.mass.sum()
    a_cons = a_def - center_of_mass
    history_tokens = torch.stack([build_node_token(state, build_reciprocal_graph(state)) for state in states], dim=1)
    case = q.Case(
        f"{lineage}_VARIANT_MAIN_N{resolution}_O{origin:02d}",
        lineage,
        "VARIANT_MAIN",
        origin,
        torch.tensor(frames, dtype=torch.int64),
        torch.tensor([state.physical_time for state in states], dtype=torch.float64),
        torch.stack([state.x_unwrapped for state in states]),
        torch.stack([state.velocity for state in states]),
        torch.stack([state.density for state in states]),
        tensor(arrays["material_labels"]),
        start.mass,
        start.smoothing_length,
        history_tokens,
        source_start,
        source_mid,
        accepted.velocity,
        a_cons,
    )
    provenance = {
        "npz_path": str(npz_path.relative_to(ROOT)),
        "json_path": str(json_path.relative_to(ROOT)),
        "npz_sha256": sha_file(npz_path),
        "json_sha256": sha_file(json_path),
        "target_component_rms": float(torch.sqrt(a_cons.square().mean())),
        "zero_correction_loss_using_N8_s_a": float((a_cons / q.S_A).square().mean()),
        "center_of_mass_residual": float(torch.linalg.vector_norm((start.mass[:, None] * a_cons).sum(0))),
    }
    return case, provenance


def diagnostic_direction(grads: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    norm = torch.sqrt(sum(grad.square().sum() for grad in grads))
    return tuple(-grad / max(float(norm), 1.0e-30) for grad in grads)


def run_context(arm: str, resolution: int, case: q.Case, model: torch.nn.Module) -> dict[str, Any]:
    adapter = q.DefectAdapter(arm, model)
    params = tuple(parameter for _, parameter in adapter.named_parameters())
    names = [name for name, _ in adapter.named_parameters()]
    before = q.parameter_hash(model)
    losses, grads, traces = q.full_gradient(adapter, [case])
    flat = torch.cat([gradient.reshape(-1) for gradient in grads[0]])
    finite_backward = bool(torch.isfinite(flat).all())
    direction = diagnostic_direction(grads[0])
    jvp = None
    if resolution == 12:
        jvp = q.reverse_jvp(adapter, [case], params, names, direction, grads[0])
    descent = q.local_descent(adapter, [case], params, names, grads[0], losses, traces[0], SEED + resolution * 1000 + q.LINEAGES.index(case.lineage) * 100)
    after = q.parameter_hash(model)
    result = {
        "arm": arm,
        "resolution": resolution,
        "seed": SEED,
        "lineage": case.lineage,
        "variant": case.variant,
        "origin": case.origin,
        "record_id": case.record_id,
        "uses_N8_s_a": True,
        "s_a": q.S_A,
        "loss_repeats": losses,
        "loss_repeat_exact": losses[0] == losses[1],
        "finite_backward": finite_backward,
        "gradient_L2": float(torch.linalg.vector_norm(flat)),
        "gradient_RMS": float(torch.sqrt(flat.square().mean())),
        "gradient_Linf": float(flat.abs().max()),
        "gradient_exact_nonzero_count": int((flat != 0).sum()),
        "reverse_jvp": jvp,
        "local_descent": descent,
        "parameter_hash_before": before,
        "parameter_hash_after": after,
        "parameter_unchanged": before == after,
        "diagnostic_pass": finite_backward and (jvp is None or jvp["pass"]) and descent["window"] and before == after,
        "affects_N8_qualification": False,
        "forward_count": adapter.forward_count,
        "graph_rebuild_count": adapter.graph_rebuild_count,
    }
    del adapter, params, grads, traces, flat
    gc.collect()
    return result


def main() -> None:
    torch.set_num_threads(1)
    started = time.perf_counter()
    rss_start = PROCESS.memory_info().rss
    peak_rss = rss_start
    batches = json.loads((STAGE05C / "batch_selection/preregistered_batches.json").read_text())
    identities = json.loads((STAGE05C / "model_instantiation/preregistered_model_identities.json").read_text())["models"]
    selected = {(row["resolution"], row["lineage"]): row for row in batches["resolution_diagnostics"]}
    decode = {
        "diagnostic_train_trajectory_npz_decode_count": 0,
        "diagnostic_train_trajectory_json_decode_count": 0,
        "validation_state_decode_count": 0,
        "validation_target_decode_count": 0,
        "sealed_formula_decode_count": 0,
        "sealed_state_decode_count": 0,
        "sealed_source_decode_count": 0,
        "sealed_target_decode_count": 0,
        "sealed_origin_decode_count": 0,
    }
    cases: dict[tuple[int, str], q.Case] = {}
    provenance: dict[tuple[int, str], dict[str, Any]] = {}
    for resolution in (12, 16):
        for lineage in q.LINEAGES:
            row = selected[(resolution, lineage)]
            case, prov = make_case(lineage, resolution, row["origin"], decode)
            cases[(resolution, lineage)] = case
            provenance[(resolution, lineage)] = {**prov, "selection_key": row["key"]}

    rows = []
    model_instances = 0
    for arm in ARMS:
        torch.manual_seed(SEED)
        model = q.ARMS[arm]().to(dtype=torch.float64, device="cpu")
        model.eval()
        model_instances += 1
        expected = next(row for row in identities if row["arm"] == arm and row["seed"] == SEED)
        if q.parameter_hash(model) != expected["complete_parameter_sha256"]:
            raise RuntimeError(f"diagnostic model identity mismatch: {arm}")
        resolutions = (12, 16) if arm == "D3" else (12,)
        for resolution in resolutions:
            for lineage in q.LINEAGES:
                with sdpa_kernel(SDPBackend.MATH):
                    result = run_context(arm, resolution, cases[(resolution, lineage)], model)
                result["input_provenance"] = provenance[(resolution, lineage)]
                rows.append(result)
                peak_rss = max(peak_rss, PROCESS.memory_info().rss)
                print(json.dumps({"arm": arm, "resolution": resolution, "lineage": lineage, "pass": result["diagnostic_pass"]}), flush=True)
        del model
        gc.collect()

    summary = {
        "schema": "sph-pio-poc.stage05c.resolution-diagnostics.v1",
        "role": "DIAGNOSTIC_ONLY",
        "affects_N8_qualification": False,
        "modifies_s_a": False,
        "resolution_generalization_claim": False,
        "spatial_convergence_claim": False,
        "N8_s_a": q.S_A,
        "seed": SEED,
        "row_count": len(rows),
        "N12_row_count": sum(row["resolution"] == 12 for row in rows),
        "N16_row_count": sum(row["resolution"] == 16 for row in rows),
        "finite_backward_count": sum(row["finite_backward"] for row in rows),
        "N12_reverse_jvp_pass_count": sum(row["resolution"] == 12 and row["reverse_jvp"]["pass"] for row in rows),
        "local_descent_window_count": sum(row["local_descent"]["window"] for row in rows),
        "parameter_restoration_count": sum(row["parameter_unchanged"] for row in rows),
        "diagnostic_pass_count": sum(row["diagnostic_pass"] for row in rows),
        "model_instances": model_instances,
        "full_gradient_backward_count": len(rows) * 2,
        "reverse_jvp_count": sum(row["resolution"] == 12 for row in rows),
        "local_descent_forward_count": len(rows) * 12,
        "graph_rebuild_count": sum(row["graph_rebuild_count"] for row in rows),
        "decode_counts": decode,
        "wall_time_seconds": time.perf_counter() - started,
        "rss_start_bytes": rss_start,
        "peak_rss_bytes": peak_rss,
        "peak_rss_delta_bytes": peak_rss - rss_start,
        "optimizer_instances": 0,
        "optimizer_steps": 0,
        "persistent_parameter_updates": 0,
        "training_runs": 0,
        "neural_rollouts": 0,
        "performance_evaluations": 0,
        "pass": len(rows) == 24 and all(row["diagnostic_pass"] for row in rows),
        "rows": rows,
    }
    write_json(STAGE05C / "resolution_diagnostics/resolution_diagnostics.json", summary)
    print(json.dumps({"rows": len(rows), "pass": summary["pass"], "wall": summary["wall_time_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
