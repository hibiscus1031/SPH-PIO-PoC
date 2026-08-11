"""Run one Stage07B arm/seed over 14 lineage and one global context."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve(); B = HERE.parents[1]; STAGE07 = HERE.parents[3]; ROOT = HERE.parents[4]
STAGE06Q = ROOT / "stage_06_Optimizer_Update_Dynamics_Training/01_update_map_qualification/qualification"
sys.path.insert(0, str(STAGE06Q)); import run_stage06a_seed as s
q = s.q
SEEDS = [20700701, 20700702, 20700703]
ANCHORS = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
NEW = ["HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03", "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
LINEAGES = ANCHORS + NEW; LR = 1e-5; PROCESS = psutil.Process()


def fd_evaluate_values_no_grad(adapter: q.DefectAdapter, cases: list[q.Case], values: tuple[torch.Tensor, ...],
                               names: list[str], rng_seed: int) -> tuple[float, dict[str, Any]]:
    """Evaluate parameter-space FD endpoints without constructing autograd graphs.

    FD endpoints require scalar losses and safety/topology traces only. Keeping
    autograd enabled here is mathematically inert but materially inflates D3's
    peak RSS on the 112-record global batch.
    """
    torch.manual_seed(rng_seed)
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
        loss = q.functional_call(adapter, dict(zip(names, values)), (cases,), strict=True)
    return float(loss.detach()), json.loads(json.dumps(adapter.last_trace))


q.evaluate_values = fd_evaluate_values_no_grad


def write_json(path: Path, value: Any) -> None:
    def cv(x: Any) -> Any:
        if isinstance(x, np.generic): return x.item()
        if isinstance(x, np.ndarray): return x.tolist()
        raise TypeError(type(x).__name__)
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, indent=2, sort_keys=True, default=cv) + "\n")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()


def load_cases() -> dict[str, q.Case]:
    manifest = json.loads((B / "update_contexts/cached_case_manifest.json").read_text()); assert manifest["pass"] and manifest["case_count"] == 224
    result = {}
    for row in manifest["cases"]:
        path = ROOT / row["path"]; assert sha_file(path) == row["sha256"]
        with np.load(path, allow_pickle=False) as z: a = {k: z[k] for k in z.files}
        result[row["record_id"]] = q.Case(row["record_id"], row["lineage"], row["variant"], row["origin"],
            torch.from_numpy(a["frames"]).to(torch.int64), q.tensor(a["physical_times"]), q.tensor(a["x"]),
            q.tensor(a["velocity"]), q.tensor(a["density"]), q.tensor(a["material_labels"]), q.tensor(a["mass"]),
            q.tensor(a["smoothing"]), q.tensor(a["history_tokens"]), q.tensor(a["source_start"]),
            q.tensor(a["source_midpoint"]), q.tensor(a["v0_accepted"]), q.tensor(a["a_cons"]))
    return result


def lineage_batch(lineage: str, cases: dict[str, q.Case], plan: dict[str, Any]) -> list[q.Case]:
    rows = []
    for item in plan["selection"]:
        if item["lineage"] == lineage:
            rows.extend(cases[f"{lineage}_{item['variant']}_N8_O{o:02d}"] for o in item["origins"])
    assert len(rows) == 16; return rows


def global_batch(cases: dict[str, q.Case], plan: dict[str, Any]) -> list[q.Case]:
    rows = []
    for lineage in LINEAGES:
        for item in plan["selection"]:
            if item["lineage"] == lineage:
                rows.extend(cases[f"{lineage}_{item['variant']}_N8_O{o:02d}"] for o in item["global_origins"])
    assert len(rows) == 112; return rows


def gradient_vector(arm: str, seed: int, expected: str, cases: list[q.Case]) -> tuple[np.ndarray, dict[str, Any]]:
    model, adapter = s.fresh(arm, seed, expected); params = tuple(p for _, p in adapter.named_parameters())
    with sdpa_kernel(SDPBackend.MATH): loss1 = adapter(cases)
    grad1 = tuple(g.detach().clone() for g in torch.autograd.grad(loss1, params, allow_unused=False)); trace1 = json.loads(json.dumps(adapter.last_trace))
    with sdpa_kernel(SDPBackend.MATH): loss2 = adapter(cases)
    grad2 = tuple(g.detach().clone() for g in torch.autograd.grad(loss2, params, allow_unused=False)); trace2 = json.loads(json.dumps(adapter.last_trace))
    vector1 = torch.cat([g.reshape(-1) for g in grad1]); vector2 = torch.cat([g.reshape(-1) for g in grad2])
    row = {"L_repeats": [float(loss1.detach()), float(loss2.detach())], "loss_repeat_exact": float(loss1.detach()) == float(loss2.detach()),
           "gradient_sha256_repeats": [s.tensor_digest(grad1), s.tensor_digest(grad2)],
           "gradient_repeat_exact": torch.equal(vector1, vector2), "gradient_L2": float(torch.linalg.vector_norm(vector1)),
           "finite": bool(torch.isfinite(vector1).all()), "graph_repeat_exact": trace1["graph_hashes"] == trace2["graph_hashes"],
           "safe": trace1["safe"] and trace2["safe"]}
    result = vector1.detach().numpy().copy(); del loss1, loss2, grad1, grad2, vector1, vector2, params, adapter, model; gc.collect(); return result, row


def streamed_global_gradient(adapter: q.DefectAdapter, cases: list[q.Case],
                             params: tuple[torch.Tensor, ...]) -> tuple[float, tuple[torch.Tensor, ...], dict[str, Any]]:
    """Evaluate the frozen global mean gradient one record at a time.

    The adapter's batch loss is the arithmetic mean of independent record
    losses.  Accumulating detached per-record gradients therefore computes the
    same derivative while avoiding retention of 112 complete D3 attention
    graphs at once.
    """
    accum = [torch.zeros_like(parameter) for parameter in params]
    losses: list[float] = []
    traces: list[dict[str, Any]] = []
    for case in cases:
        with sdpa_kernel(SDPBackend.MATH):
            loss = adapter([case])
        gradients = torch.autograd.grad(loss, params, allow_unused=False)
        for total, gradient in zip(accum, gradients):
            total.add_(gradient.detach())
        losses.append(float(loss.detach()))
        traces.extend(json.loads(json.dumps(adapter.last_trace))["cases"])
        del loss, gradients
    divisor = float(len(cases))
    mean_gradient = tuple(total.div_(divisor) for total in accum)
    combined = {
        "cases": traces,
        "topology": [item for trace in traces for item in trace["topology"]],
        "graph_hashes": [item for trace in traces for item in trace["graph_hashes"]],
        "safe": all(trace["finite"] and trace["density_min"] > 0 and trace["force_residual_max"] <= 1e-10
                    and trace["midpoint_commit_count"] == 0
                    and trace["history_commit_count"] == (0 if adapter.arm == "D1" else 1) for trace in traces),
    }
    return float(math.fsum(losses) / divisor), mean_gradient, combined


def streamed_global_reverse_jvp(adapter: q.DefectAdapter, cases: list[q.Case],
                                params: tuple[torch.Tensor, ...], names: list[str],
                                direction: tuple[torch.Tensor, ...],
                                gradient: tuple[torch.Tensor, ...]) -> dict[str, Any]:
    """Check reverse/JVP identity without constructing a full-global JVP graph."""
    reverse = float(sum((g * d).sum() for g, d in zip(gradient, direction)))
    tangents: list[float] = []
    for case in cases:
        def fn(*values: torch.Tensor) -> torch.Tensor:
            with sdpa_kernel(SDPBackend.MATH):
                return q.functional_call(adapter, dict(zip(names, values)), ([case],), strict=True)
        with sdpa_kernel(SDPBackend.MATH):
            _, tangent = torch.autograd.functional.jvp(fn, params, direction, create_graph=False, strict=True)
        tangents.append(float(tangent.detach()))
        del tangent
    jvp = float(math.fsum(tangents) / len(tangents))
    absolute = abs(reverse - jvp)
    near_zero = abs(reverse) < 1e-12 and abs(jvp) < 1e-12
    relative = absolute / max(abs(reverse), abs(jvp), 1e-30)
    passed = absolute <= (1e-12 if near_zero else 1e-10) or (not near_zero and relative <= 1e-7)
    return {"reverse": reverse, "jvp": jvp, "abs_difference": absolute,
            "relative_difference": relative, "near_zero": near_zero, "pass": passed,
            "streamed_global_identity": True}


def streamed_diagnostic_probe(adapter: q.DefectAdapter, cases: list[q.Case], params: tuple[torch.Tensor, ...],
                              names: list[str], gradient: tuple[torch.Tensor, ...],
                              direction: tuple[torch.Tensor, ...], scale: float,
                              base_trace: dict[str, Any], rng_seed: int) -> dict[str, Any]:
    original = q.reverse_jvp
    q.reverse_jvp = lambda a, c, p, n, d, g: streamed_global_reverse_jvp(a, c, p, n, d, g)
    try:
        return s.diagnostic_probe(adapter, cases, params, names, gradient, direction, scale, base_trace, rng_seed)
    finally:
        q.reverse_jvp = original


def coordinate_global(arm: str, seed: int, expected: str, cases: list[q.Case], groups: list[dict[str, Any]], plan: list[dict[str, Any]], probe_index: int | None = None) -> dict[str, Any]:
    model, adapter = s.fresh(arm, seed, expected); params = tuple(p for _, p in adapter.named_parameters()); names = [n for n, _ in adapter.named_parameters()]
    loss_value, gradient, base_trace = streamed_global_gradient(adapter, cases, params); probes = []
    for gi, group in enumerate(groups):
        context = next(r for r in plan if r["arm"] == arm and r["seed"] == seed and r["group"] == group["group"])
        items = [("coordinate", x) for x in context["coordinates"]] + [("block", x) for x in context["blocks"]]
        if probe_index is not None: items = [items[probe_index]]
        for pi, (kind, probe) in enumerate(items):
            if kind == "coordinate":
                indices = [probe["group_flat_index"]]; weights = [1.]
                scale = max(1., abs(float(q.group_vector(params, names, group)[indices[0]].detach())))
            else:
                indices = probe["indices"]; weights = (np.asarray(probe["rademacher_signs"], dtype=float)/math.sqrt(len(indices))).tolist()
                gv = q.group_vector(params, names, group); scale = max(1., float(torch.sqrt(gv[indices].detach().square().mean())))
            direction = q.group_direction(params, names, group, indices, weights)
            row = streamed_diagnostic_probe(adapter, cases, params, names, gradient, direction, scale, base_trace,
                                            seed+gi*100000+pi*1000)
            row.update({"arm": arm, "seed": seed, "context": "GLOBAL", "group": group["group"], "kind": kind,
                        "selection": probe, "perturbation_scale": scale}); probes.append(row)
    forbidden = {"REVERSE_JVP_MAPPING_CONTRADICTION", "SIGN_CONTRADICTION", "NONDETERMINISTIC", "SAFETY_FAILURE"}
    result = {"arm": arm, "seed": seed, "context": "GLOBAL", "probes": probes, "probe_count": len(probes),
              "FD_WINDOW_MISSING_count": sum(r["classification"] == "FD_WINDOW_MISSING" for r in probes),
              "hard_failure_count": sum(r["classification"] in forbidden for r in probes),
              "complete_coordinate_block_FD_qualified": False, "pass": not any(r["classification"] in forbidden for r in probes)}
    result["streamed_global_loss"] = loss_value
    result["streamed_record_count"] = len(cases)
    del gradient, params, adapter, model; gc.collect(); return result


def cosine_diagnostics(arm: str, seed: int, vectors: dict[str, np.ndarray]) -> dict[str, Any]:
    matrix = np.zeros((14, 14)); norms = {k: np.linalg.norm(v) for k, v in vectors.items()}
    for i, left in enumerate(LINEAGES):
        for j, right in enumerate(LINEAGES): matrix[i, j] = float(np.dot(vectors[left], vectors[right])/max(norms[left]*norms[right], 1e-300))
    off = matrix[~np.eye(14, dtype=bool)]; global_v = vectors["GLOBAL"]; global_norm = norms["GLOBAL"]
    to_global = {f: float(np.dot(vectors[f], global_v)/max(norms[f]*global_norm, 1e-300)) for f in LINEAGES}
    def pair_values(predicate: Any) -> list[float]:
        return [matrix[i, j] for i in range(14) for j in range(i+1, 14) if predicate(LINEAGES[i], LINEAGES[j])]
    anchor_new = pair_values(lambda a, b: (a in ANCHORS) != (b in ANCHORS))
    within = pair_values(lambda a, b: a in NEW and b in NEW and a.split("_")[1] == b.split("_")[1])
    cross = pair_values(lambda a, b: a in NEW and b in NEW and a.split("_")[1] != b.split("_")[1])
    lcdf08 = [float(matrix[LINEAGES.index("LCDF_08"), LINEAGES.index(f)]) for f in NEW]
    return {"arm": arm, "seed": seed, "lineages": LINEAGES, "cosine_matrix": matrix,
            "mean_off_diagonal_cosine": float(np.mean(off)), "negative_cosine_fraction": float(np.mean(off < 0)),
            "minimum_cosine": float(np.min(off)), "cosine_to_global_gradient": to_global,
            "anchor_vs_new_mean": float(np.mean(anchor_new)), "within_stratum_mean": float(np.mean(within)),
            "cross_stratum_mean": float(np.mean(cross)), "LCDF_08_vs_new": lcdf08,
            "LCDF_08_vs_new_mean": float(np.mean(lcdf08)), "role": "POSTHOC_DEVELOPMENT_DIAGNOSTIC_ONLY", "hard_gate": False}


def coordinate_group_probe(arm: str, seed: int, group_name: str, probe_index: int | None = None) -> None:
    torch.set_num_threads(1); started = time.perf_counter(); rss0 = PROCESS.memory_info().rss
    target = json.loads((B / "results/target_scale_result.json").read_text()); q.S_A = target["s_a_v2"]
    cases = load_cases(); context_plan = json.loads((B / "update_contexts/preregistered_update_contexts.json").read_text())
    selected = global_batch(cases, context_plan)
    all_groups = json.loads((B / "gradient_identity/parameter_groups.json").read_text())["groups"][arm]
    groups = [g for g in all_groups if g["group"] == group_name]
    if len(groups) != 1: raise ValueError(group_name)
    plan = json.loads((B / "coordinate_boundary/preregistered_diagnostic_plan.json").read_text())["contexts"]
    identities = json.loads((B / "model_seeds/preregistered_model_identities.json").read_text())["models"]
    expected = next(r["complete_parameter_sha256"] for r in identities if r["arm"] == arm and r["seed"] == seed)
    result = coordinate_global(arm, seed, expected, selected, groups, plan, probe_index)
    peak = max(PROCESS.memory_info().rss, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    result.update({"isolated_group_process": True, "group": group_name, "rss_start_bytes": rss0, "peak_rss_bytes": peak,
                   "peak_rss_delta_bytes": peak-rss0, "peak_rss_pass": peak-rss0 <= 1610612736,
                   "qualification_models_destroyed": True, "wall_time_seconds": time.perf_counter()-started})
    result["pass"] = result["pass"] and result["peak_rss_pass"]
    suffix = "group" if probe_index is None else f"probe{probe_index}"
    result["probe_index"] = probe_index
    write_json(B / f"coordinate_boundary/{arm}_{seed}_{group_name}_{suffix}_isolated.json", result)
    print(json.dumps({"arm": arm, "seed": seed, "group": group_name, "probe_index": probe_index, "pass": result["pass"],
                      "peak_delta": result["peak_rss_delta_bytes"], "wall": result["wall_time_seconds"]}), flush=True)


def run(arm: str, seed: int, only_context: str | None = None, skip_coordinate: bool = False) -> None:
    torch.set_num_threads(1); started = time.perf_counter(); rss0 = PROCESS.memory_info().rss; peak = rss0; retention = []
    freeze = json.loads((B / "freeze/stage07b_input_freeze_record.json").read_text()); assert sha_file(ROOT/freeze["contract_path"]) == freeze["contract_sha256"]
    target = json.loads((B / "results/target_scale_result.json").read_text()); assert target["target_scale_pass"]
    q.S_A = target["s_a_v2"]
    cases = load_cases(); context_plan = json.loads((B / "update_contexts/preregistered_update_contexts.json").read_text())
    groups = json.loads((B / "gradient_identity/parameter_groups.json").read_text())["groups"][arm]
    probe_plan = json.loads((B / "coordinate_boundary/preregistered_diagnostic_plan.json").read_text())["contexts"]
    identities = json.loads((B / "model_seeds/preregistered_model_identities.json").read_text())["models"]
    expected = next(r["complete_parameter_sha256"] for r in identities if r["arm"] == arm and r["seed"] == seed)
    outdir = B / f"results/optimizer/{arm.lower()}/{seed}"; summaries = []; vectors = {}; optimizer_steps = optimizer_instances = graph_rebuilds = 0
    contexts = [(f, lineage_batch(f, cases, context_plan)) for f in LINEAGES] + [("GLOBAL", global_batch(cases, context_plan))]
    if only_context is not None:
        contexts = [row for row in contexts if row[0] == only_context]
        if len(contexts) != 1: raise ValueError(only_context)
    for index, (context, selected) in enumerate(contexts):
        vector, gradient_identity = gradient_vector(arm, seed, expected, selected); vectors[context] = vector
        one = s.one_step_lr(arm, seed, expected, selected, LR, groups)
        micro = s.micro_update(arm, seed, expected, selected, LR)
        actual = s.actual_update_fd(arm, seed, expected, selected, LR, context != "GLOBAL")
        coordinate = coordinate_global(arm, seed, expected, selected, groups, probe_plan) if context == "GLOBAL" and not skip_coordinate else None
        context_pass = gradient_identity["finite"] and gradient_identity["gradient_repeat_exact"] and one["pass"] and micro["pass"] and actual["pass"] and (coordinate is None or coordinate["pass"])
        result = {"arm": arm, "seed": seed, "context": context, "batch_size": len(selected), "batch_record_ids": [c.record_id for c in selected],
                  "scale_v2": target["s_a_v2"], "scale_v2_hash": target["scale_v2_hash"], "formal_requalification_lr": LR,
                  "gradient_identity": gradient_identity, "one_step_actual_AdamW": one, "actual_update_FD": actual,
                  "micro_update_2_4": micro, "coordinate_block_boundary": coordinate,
                  "structure_safety": None if context == "GLOBAL" else actual["structure_audit"],
                  "qualification_optimizer_instances": one["qualification_optimizer_instances"] + micro["qualification_optimizer_instances"] + actual["qualification_optimizer_instances"],
                  "qualification_optimizer_steps": one["qualification_optimizer_steps"] + micro["qualification_optimizer_steps"] + actual["qualification_optimizer_steps"],
                  "training_runs": 0, "saved_training_checkpoints": 0, "fresh_validation_evaluations": 0,
                  "consumed_validation_evaluations": 0, "sealed_test_evaluations": 0, "pass": bool(context_pass)}
        write_json(outdir / f"{arm}_{seed}_{context}.json", result)
        summaries.append({"context": context, "pass": result["pass"], "gradient": gradient_identity["finite"] and gradient_identity["gradient_repeat_exact"],
                          "one_step": one["pass"], "actual_FD": actual["pass"], "micro": micro["pass"],
                          "structure": None if context == "GLOBAL" else actual["structure_audit"]["pass"],
                          "coordinate": None if coordinate is None else coordinate["pass"]})
        optimizer_instances += result["qualification_optimizer_instances"]; optimizer_steps += result["qualification_optimizer_steps"]
        # Conservative accounting based on adapter traces; no particle N x N allocation is used.
        graph_rebuilds += len(selected) * (3*40 + (8 if context != "GLOBAL" else 0))
        gc.collect(); peak = max(peak, PROCESS.memory_info().rss, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss); retention.append(PROCESS.memory_info().rss)
        print(json.dumps({"arm": arm, "seed": seed, "context": context, "pass": result["pass"], "elapsed": time.perf_counter()-started}), flush=True)
    if only_context is not None:
        monotonic = False
        probe = {"arm": arm, "seed": seed, "context": only_context, "same_frozen_context_replay": True,
                 "scientific_result_pass": summaries[0]["pass"], "coordinate_diagnostic_in_separate_group_processes": skip_coordinate,
                 "rss_start_bytes": rss0, "peak_rss_bytes": peak,
                 "peak_rss_delta_bytes": peak-rss0, "peak_rss_delta_gate_bytes": 1610612736,
                 "peak_rss_pass": peak-rss0 <= 1610612736, "retention_rss_samples": retention,
                 "retained_autograd_monotonic_growth": monotonic, "qualification_models_destroyed": True,
                 "pass": summaries[0]["pass"] and peak-rss0 <= 1610612736}
        write_json(B / f"resources/{arm}_{seed}_{only_context}_isolated_resource_probe.json", probe)
        print(json.dumps(probe), flush=True); return
    diagnostic = cosine_diagnostics(arm, seed, vectors); write_json(B / f"lineage_gradient_diagnostics/{arm}_{seed}_cosines.json", diagnostic)
    monotonic = len(retention) > 2 and all(retention[i+1] > retention[i] for i in range(len(retention)-1)) and retention[-1]-retention[0] > 64*1024**2
    lineage_count = sum(r["pass"] for r in summaries if r["context"] != "GLOBAL"); global_pass = next(r["pass"] for r in summaries if r["context"] == "GLOBAL")
    summary = {"arm": arm, "seed": seed, "contexts": summaries, "lineage_pass_count": lineage_count, "global_pass": global_pass,
               "pass": lineage_count == 14 and global_pass, "qualification_optimizer_instances": optimizer_instances,
               "qualification_optimizer_steps": optimizer_steps, "formal_optimizer_context_count": 15,
               "graph_rebuild_count_estimate": graph_rebuilds, "rss_start_bytes": rss0, "peak_rss_bytes": peak,
               "peak_rss_delta_bytes": peak-rss0, "retention_rss_samples": retention, "retained_autograd_monotonic_growth": monotonic,
               "optimizer_state_memory_peak_upper_bound_bytes": 2*next(r["parameter_count"] for r in identities if r["arm"] == arm and r["seed"] == seed)*8,
               "wall_time_seconds": time.perf_counter()-started, "dense_particle_N_by_N_allocation": False,
               "qualification_models_destroyed": True, "qualification_weights_saved": 0, "saved_training_checkpoints": 0,
               "training_runs": 0, "fresh_validation_evaluations": 0, "consumed_validation_evaluations": 0, "sealed_test_evaluations": 0}
    summary["resource_pass"] = summary["peak_rss_delta_bytes"] <= 1610612736 and not monotonic and summary["qualification_models_destroyed"]
    summary["pass"] = summary["pass"] and summary["resource_pass"]
    write_json(B / f"qualification/{arm.lower()}_{seed}_optimizer_summary.json", summary)
    print(json.dumps({"arm": arm, "seed": seed, "pass": summary["pass"], "lineages": lineage_count, "global": global_pass,
                      "optimizer_steps": optimizer_steps, "wall": summary["wall_time_seconds"]}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--arm", choices=["D1", "D2", "D3"], required=True); p.add_argument("--seed", type=int, choices=SEEDS, required=True)
    p.add_argument("--only-context", choices=[*LINEAGES, "GLOBAL"]); p.add_argument("--skip-coordinate", action="store_true")
    p.add_argument("--coordinate-group"); p.add_argument("--probe-index", type=int, choices=[0,1,2,3]); a = p.parse_args()
    if a.coordinate_group: coordinate_group_probe(a.arm, a.seed, a.coordinate_group, a.probe_index)
    else: run(a.arm, a.seed, a.only_context, a.skip_coordinate)
