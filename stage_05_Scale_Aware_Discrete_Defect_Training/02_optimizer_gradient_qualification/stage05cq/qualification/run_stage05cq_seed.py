"""Run one Stage 05C-Q arm/seed over all blind N8 formal contexts."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE05CQ = HERE.parents[1]
ROOT = HERE.parents[4]
STAGE05C = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c"
sys.path.insert(0, str(STAGE05C / "qualification"))
import run_stage05c_arm as q


SEEDS = [20500521, 20500522, 20500523]
RADII = [3e-7, 1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3]
PROCESS = psutil.Process()


def write_json(path: Path, value: Any) -> None:
    def convert(item: Any) -> Any:
        if isinstance(item, np.bool_): return bool(item)
        if isinstance(item, np.integer): return int(item)
        if isinstance(item, np.floating): return float(item)
        raise TypeError(type(item).__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=convert) + "\n", encoding="utf-8")


def load_cases() -> dict[str, q.Case]:
    manifest = json.loads((STAGE05CQ / "blind_origin_selection/cached_blind_batch_manifest.json").read_text())
    assert manifest["pass"] and manifest["case_count"] == 48
    result = {}
    for row in manifest["cases"]:
        with np.load(ROOT / row["path"], allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        result[row["record_id"]] = q.Case(
            row["record_id"], row["lineage"], row["variant"], row["origin"],
            torch.from_numpy(arrays["frames"]).to(torch.int64), q.tensor(arrays["physical_times"]),
            q.tensor(arrays["x"]), q.tensor(arrays["velocity"]), q.tensor(arrays["density"]),
            q.tensor(arrays["material_labels"]), q.tensor(arrays["mass"]), q.tensor(arrays["smoothing"]),
            q.tensor(arrays["history_tokens"]), q.tensor(arrays["source_start"]), q.tensor(arrays["source_midpoint"]),
            q.tensor(arrays["v0_accepted"]), q.tensor(arrays["a_cons"]),
        )
    return result


def batch_for(lineage: str, cases: dict[str, q.Case], origins: dict[str, Any]) -> list[q.Case]:
    rows = []
    for item in origins["selection"]:
        if item["lineage"] == lineage:
            rows.extend(cases[f"{lineage}_{item['variant']}_N8_O{origin:02d}"] for origin in item["origins"])
    assert len(rows) == 8
    return rows


def global_batch(cases: dict[str, q.Case], origins: dict[str, Any]) -> list[q.Case]:
    return [case for lineage in q.LINEAGES for case in batch_for(lineage, cases, origins)]


def group_direction_from_gradient(grads: tuple[torch.Tensor, ...], params: tuple[torch.Tensor, ...], names: list[str], group: dict[str, Any]) -> tuple[tuple[torch.Tensor, ...], float, float]:
    vector = q.group_vector(grads, names, group)
    norm = float(torch.linalg.vector_norm(vector))
    directions = [torch.zeros_like(parameter) for parameter in params]
    index = {name.removeprefix("core."): position for position, name in enumerate(names)}
    for entry in group["entries"]:
        position = index[entry["tensor_path"]]
        if "slice_dim0" in entry:
            start, end = entry["slice_dim0"]
            directions[position][start:end] = grads[position][start:end] / max(norm, 1e-30)
        else:
            directions[position] = grads[position] / max(norm, 1e-30)
    theta = q.group_vector(params, names, group)
    theta_ref = max(float(torch.linalg.vector_norm(theta.detach())), math.sqrt(theta.numel()) * 1e-3)
    return tuple(directions), norm, theta_ref


def trace_hash(trace: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(trace["graph_hashes"], separators=(",", ":")).encode()).hexdigest()


def extended_fd(adapter: q.DefectAdapter, cases: list[q.Case], params: tuple[torch.Tensor, ...], names: list[str],
                direction: tuple[torch.Tensor, ...], scale: float, ad: float, near_zero: bool,
                base_topology: list[str], seed: int) -> dict[str, Any]:
    rows = []
    before = q.parameter_hash(adapter.core)
    for radius_index, radius in enumerate(RADII):
        h = radius * scale
        evaluations: dict[str, list[float]] = {"plus_h": [], "minus_h": [], "plus_2h": [], "minus_2h": []}
        trace_rows: dict[str, list[dict[str, Any]]] = {key: [] for key in evaluations}
        for repeat in range(2):
            for label, multiplier in (("plus_h", 1.), ("minus_h", -1.), ("plus_2h", 2.), ("minus_2h", -2.)):
                values = tuple(parameter + multiplier * h * delta for parameter, delta in zip(params, direction))
                loss, trace = q.evaluate_values(adapter, cases, values, names, seed + radius_index * 100 + repeat * 10 + len(trace_rows[label]))
                evaluations[label].append(loss); trace_rows[label].append(trace)
        d3_repeats = [(evaluations["plus_h"][repeat] - evaluations["minus_h"][repeat]) / (2 * h) for repeat in range(2)]
        d5_repeats = [(-evaluations["plus_2h"][repeat] + 8 * evaluations["plus_h"][repeat]
                       - 8 * evaluations["minus_h"][repeat] + evaluations["minus_2h"][repeat]) / (12 * h) for repeat in range(2)]
        d3 = float(np.mean(d3_repeats)); d5 = float(np.mean(d5_repeats))
        d3_abs = abs(d3 - ad); d5_abs = abs(d5 - ad)
        d3_rel = d3_abs / max(abs(d3), abs(ad), 1e-30); d5_rel = d5_abs / max(abs(d5), abs(ad), 1e-30)
        deterministic = all(evaluations[key][0] == evaluations[key][1]
                            and trace_rows[key][0]["graph_hashes"] == trace_rows[key][1]["graph_hashes"] for key in evaluations)
        topology = all(trace["topology"] == base_topology for key in trace_rows for trace in trace_rows[key])
        safe = all(trace["safe"] for key in trace_rows for trace in trace_rows[key])
        restored = q.parameter_hash(adapter.core) == before
        rows.append({
            "radius": radius, "arc_length": h, "loss_repeats": evaluations,
            "three_point_repeats": d3_repeats, "five_point_repeats": d5_repeats,
            "three_point": d3, "five_point": d5,
            "three_point_AD_abs": d3_abs, "three_point_AD_rel": d3_rel,
            "five_point_AD_abs": d5_abs, "five_point_AD_rel": d5_rel,
            "three_point_AD_pass": d3_abs <= 1e-8 or d3_rel <= 1e-4,
            "five_point_AD_pass": d5_abs <= 1e-8 or d5_rel <= 1e-4,
            "deterministic": deterministic, "topology_unchanged": topology, "safe": safe,
            "parameter_bitwise_restored": restored,
            "graph_sequence_hashes": {key: [trace_hash(trace) for trace in trace_rows[key]] for key in trace_rows},
        })
    pairs = []
    for index in range(len(rows) - 1):
        large, small = rows[index + 1], rows[index]
        if large["radius"] < small["radius"]:
            large, small = small, large
        ratio = large["arc_length"] / small["arc_length"]
        richardson = (ratio ** 4 * small["five_point"] - large["five_point"]) / (ratio ** 4 - 1)
        if near_zero:
            estimator_pass = abs(large["five_point"]) <= 1e-8 and abs(small["five_point"]) <= 1e-8
            change = abs(large["five_point"] - small["five_point"])
            rich_difference = abs(richardson - small["five_point"])
            stability_pass = True
            rich_pass = rich_difference <= 1e-8
        else:
            estimator_pass = (large["five_point_AD_pass"] or large["three_point_AD_pass"]) and (small["five_point_AD_pass"] or small["three_point_AD_pass"])
            large_est = large["five_point"] if large["five_point_AD_pass"] else large["three_point"]
            small_est = small["five_point"] if small["five_point_AD_pass"] else small["three_point"]
            change = abs(large_est - small_est) / max(abs(large_est), abs(small_est), 1e-30)
            rich_difference = abs(richardson - small_est) / max(abs(richardson), abs(small_est), 1e-30)
            stability_pass = change <= 1e-3
            rich_pass = rich_difference <= 1e-3
        base = all(row[gate] for row in (large, small) for gate in ("deterministic", "topology_unchanged", "safe", "parameter_bitwise_restored"))
        pairs.append({"indices": [index, index + 1], "richardson": richardson, "adjacent_variation": change,
                      "richardson_relative_difference": rich_difference, "estimator_pass": estimator_pass,
                      "adjacent_stability_pass": stability_pass, "richardson_pass": rich_pass,
                      "pass": base and estimator_pass and stability_pass and rich_pass})
    return {"radii": rows, "adjacent_pairs": pairs, "stable": any(pair["pass"] for pair in pairs),
            "near_zero_consistent": near_zero and any(pair["pass"] for pair in pairs),
            "parameter_hash_before": before, "parameter_hash_after": q.parameter_hash(adapter.core),
            "evaluation_path_count": len(RADII) * 8}


def classify_probe(reverse_jvp: dict[str, Any], fd: dict[str, Any]) -> str:
    if not reverse_jvp["pass"]: return "SIGN_OR_MAPPING_CONTRADICTION"
    if any(not row["topology_unchanged"] for row in fd["radii"]): return "TOPOLOGY_CHANGED"
    if any(not row["deterministic"] for row in fd["radii"]): return "NONDETERMINISTIC"
    if any(not row["safe"] for row in fd["radii"]): return "SAFETY_FAIL"
    if reverse_jvp["near_zero"] and fd["near_zero_consistent"]: return "NEAR_ZERO_CONSISTENT"
    if fd["stable"]: return "PASS"
    return "FD_WINDOW_MISSING"


def run(arm: str, seed: int) -> None:
    torch.set_num_threads(1)
    started = time.perf_counter(); rss_start = PROCESS.memory_info().rss; peak = rss_start
    cases = load_cases()
    origins = json.loads((STAGE05CQ / "blind_origin_selection/preregistered_blind_origins.json").read_text())
    groups = json.loads((STAGE05CQ / "parameter_groups/preregistered_parameter_groups.json").read_text())["groups"][arm]
    plan = json.loads((STAGE05CQ / "coordinate_block_sampling/preregistered_blind_probe_plan.json").read_text())["contexts"]
    identities = json.loads((STAGE05CQ / "blind_model_seeds/preregistered_blind_model_identities.json").read_text())["models"]
    torch.manual_seed(seed); model = q.ARMS[arm]().to(dtype=torch.float64, device="cpu"); model.eval()
    expected = next(row for row in identities if row["arm"] == arm and row["seed"] == seed)
    assert q.parameter_hash(model) == expected["complete_parameter_sha256"]
    adapter = q.DefectAdapter(arm, model)
    params = tuple(parameter for _, parameter in adapter.named_parameters()); names = [name for name, _ in adapter.named_parameters()]
    outdir = STAGE05CQ / f"results/{arm.lower()}"; outdir.mkdir(parents=True, exist_ok=True)
    context_summaries = []; backward_count = jvp_count = fd_paths = local_forwards = restore_checks = 0
    for lineage in q.LINEAGES:
        selected = batch_for(lineage, cases, origins); before = q.parameter_hash(model)
        losses, grads, traces = q.full_gradient(adapter, selected); backward_count += 2
        stats = [q.group_stats(grads[0], grads[1], params, names, group) for group in groups]
        local = q.local_descent(adapter, selected, params, names, grads[0], losses, traces[0], seed + q.LINEAGES.index(lineage) * 10000)
        local_forwards += 12; restore_checks += 6
        with sdpa_kernel(SDPBackend.MATH):
            state, history, output, graph, token = adapter.start_audit(selected[0])
            structure = q.audit_stage(arm=arm, model=model, state=state, history=history, stage="start",
                                      reference_output=output, reference_graph=graph, reference_token=token)
        optimizer_rows = []; blind_rows = []; group_contexts = []
        for group_index, group in enumerate(groups):
            gradient_direction, gradient_norm, theta_ref = group_direction_from_gradient(grads[0], params, names, group)
            optimizer_jvp = q.reverse_jvp(adapter, selected, params, names, gradient_direction, grads[0]); jvp_count += 1
            optimizer_fd = extended_fd(adapter, selected, params, names, gradient_direction, theta_ref,
                                       optimizer_jvp["reverse"], optimizer_jvp["near_zero"], traces[0]["topology"],
                                       seed + group_index * 1000000 + q.LINEAGES.index(lineage) * 10000)
            fd_paths += optimizer_fd["evaluation_path_count"]; restore_checks += len(RADII)
            optimizer_rows.append({"arm": arm, "seed": seed, "lineage": lineage, "group": group["group"],
                                   "gradient_L2": gradient_norm, "theta_ref": theta_ref, "reverse_jvp": optimizer_jvp,
                                   "finite_difference": optimizer_fd,
                                   "pass": optimizer_jvp["pass"] and optimizer_fd["stable"]})
            probe_context = next(row for row in plan if row["arm"] == arm and row["group"] == group["group"] and row["lineage"] == lineage and row["seed"] == seed)
            directions = [("coordinate", row) for row in probe_context["coordinates"]] + [("block", row) for row in probe_context["blocks"]]
            for probe_index, (kind, probe) in enumerate(directions):
                if kind == "coordinate":
                    indices = [probe["group_flat_index"]]; weights = [1.]
                    scale = max(1., abs(float(q.group_vector(params, names, group)[indices[0]].detach())))
                else:
                    indices = probe["indices"]; weights = (np.asarray(probe["rademacher_signs"], dtype=float) / math.sqrt(len(indices))).tolist()
                    vector = q.group_vector(params, names, group)
                    scale = max(1., float(torch.sqrt(vector[indices].detach().square().mean())))
                direction = q.group_direction(params, names, group, indices, weights)
                reverse = q.reverse_jvp(adapter, selected, params, names, direction, grads[0]); jvp_count += 1
                fd = extended_fd(adapter, selected, params, names, direction, scale, reverse["reverse"], reverse["near_zero"],
                                 traces[0]["topology"], seed + group_index * 1000000 + probe_index * 100000 + q.LINEAGES.index(lineage) * 1000)
                fd_paths += fd["evaluation_path_count"]; restore_checks += len(RADII)
                classification = classify_probe(reverse, fd)
                blind_rows.append({"arm": arm, "seed": seed, "lineage": lineage, "group": group["group"], "kind": kind,
                                   "selection": probe, "perturbation_scale": scale, "reverse_jvp": reverse,
                                   "finite_difference": fd, "classification": classification,
                                   "stable_nonzero": classification == "PASS" and not reverse["near_zero"],
                                   "pass_or_consistent": classification in {"PASS", "NEAR_ZERO_CONSISTENT"}})
            group_probe_rows = [row for row in blind_rows if row["group"] == group["group"]]
            valid = sum(row["pass_or_consistent"] for row in group_probe_rows)
            forbidden = any(row["classification"] in {"SIGN_OR_MAPPING_CONTRADICTION", "NONDETERMINISTIC", "SAFETY_FAIL"} for row in group_probe_rows)
            stat = next(row for row in stats if row["group"] == group["group"])
            optimizer_pass = optimizer_rows[-1]["pass"]
            group_contexts.append({"group": group["group"], "full_gradient": stat, "optimizer_path_pass": optimizer_pass,
                                   "blind_probe_pass_or_consistent_count": valid, "blind_probe_count": len(group_probe_rows),
                                   "stable_nonzero_count": sum(row["stable_nonzero"] for row in group_probe_rows),
                                   "forbidden_classification": forbidden,
                                   "pass": stat["active"] and optimizer_pass and valid >= 7 and any(row["stable_nonzero"] for row in group_probe_rows) and not forbidden})
        after = q.parameter_hash(model)
        result = {"arm": arm, "seed": seed, "lineage": lineage, "batch_record_ids": [case.record_id for case in selected],
                  "loss_repeats": losses, "loss_repeat_exact": losses[0] == losses[1], "full_gradient_groups": stats,
                  "optimizer_paths": optimizer_rows, "blind_probes": blind_rows, "group_contexts": group_contexts,
                  "local_descent": local, "structure": structure, "parameter_hash_before": before, "parameter_hash_after": after,
                  "parameter_unchanged": before == after,
                  "pass": all(row["pass"] for row in group_contexts) and local["window"] and structure["pass"] and before == after}
        write_json(outdir / f"{arm}_{seed}_{lineage}.json", result)
        context_summaries.append({"lineage": lineage, "pass": result["pass"], "local": local["window"], "structure": structure["pass"],
                                  "groups": {row["group"]: row["pass"] for row in group_contexts}})
        peak = max(peak, PROCESS.memory_info().rss)
        del losses, grads, traces, optimizer_rows, blind_rows; gc.collect()
        print(json.dumps({"arm": arm, "seed": seed, "lineage": lineage, "pass": result["pass"], "elapsed": time.perf_counter() - started}), flush=True)
    selected = global_batch(cases, origins)
    losses, grads, traces = q.full_gradient(adapter, selected); backward_count += 2
    local = q.local_descent(adapter, selected, params, names, grads[0], losses, traces[0], seed + 900000)
    local_forwards += 12; restore_checks += 6
    global_result = {"arm": arm, "seed": seed, "batch_size": 48, "loss_repeats": losses,
                     "gradient_L2": float(torch.sqrt(sum(gradient.square().sum() for gradient in grads[0]))),
                     "local_descent": local, "parameter_unchanged": q.parameter_hash(model) == expected["complete_parameter_sha256"],
                     "pass": local["window"] and q.parameter_hash(model) == expected["complete_parameter_sha256"]}
    write_json(outdir / f"{arm}_{seed}_GLOBAL.json", global_result)
    summary = {"arm": arm, "seed": seed, "contexts": context_summaries, "lineage_context_count": len(context_summaries),
               "lineage_context_pass_count": sum(row["pass"] for row in context_summaries), "global_pass": global_result["pass"],
               "full_gradient_backward_count": backward_count, "reverse_jvp_count": jvp_count, "FD_path_count": fd_paths,
               "local_descent_forward_count": local_forwards, "parameter_restoration_checks": restore_checks,
               "adapter_forward_count": adapter.forward_count, "graph_rebuild_count": adapter.graph_rebuild_count,
               "rss_start_bytes": rss_start, "peak_rss_bytes": peak, "peak_rss_delta_bytes": peak - rss_start,
               "wall_time_seconds": time.perf_counter() - started,
               "optimizer_instances": 0, "optimizer_steps": 0, "persistent_parameter_updates": 0,
               "training_runs": 0, "neural_rollouts": 0, "performance_evaluations": 0,
               "pass": all(row["pass"] for row in context_summaries) and global_result["pass"]}
    write_json(STAGE05CQ / f"qualification/{arm.lower()}_{seed}_summary.json", summary)
    print(json.dumps({"arm": arm, "seed": seed, "pass": summary["pass"], "wall": summary["wall_time_seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--arm", choices=["D1", "D2", "D3"], required=True)
    parser.add_argument("--seed", type=int, choices=SEEDS, required=True); args = parser.parse_args()
    run(args.arm, args.seed)
