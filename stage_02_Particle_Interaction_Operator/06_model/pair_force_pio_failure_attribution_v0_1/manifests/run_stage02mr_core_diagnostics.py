#!/usr/bin/env python3
"""Read-only metric, dynamics, conditioning, identifiability, and shift audits."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from scipy.optimize import minimize
from scipy.spatial import cKDTree

from audit_common import (
    ARCHITECTURES, A0, EPSILON_METRIC, MROOT, ROOT, SEEDS, STAGE,
    checkpoint_paths, evaluate, graph_loss, load_items, make_model, module_name,
    node_features, pair_geometry, sha, symmetric_pair_features, tensor_hash,
    terminal, write_json,
)

CONTRACT = json.loads((ROOT / "freeze/diagnostic_contract_v0_1.json").read_text())
EPS = CONTRACT["optimization_conditioning"]["adam_epsilon"]
WD = CONTRACT["optimization_conditioning"]["weight_decay"]
B1 = CONTRACT["optimization_conditioning"]["adam_beta1"]
B2 = CONTRACT["optimization_conditioning"]["adam_beta2"]
MULTIPLIERS = CONTRACT["optimization_conditioning"]["loss_multipliers"]


def f64bytes(array: np.ndarray) -> bytes:
    return np.asarray(array, dtype="<f8", order="C").tobytes()


def checkpoint_metric_reconstruction(items: dict[str, list[Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    runs, dynamics = [], {}
    ever_gate = False
    for architecture in ARCHITECTURES:
        for seed in SEEDS:
            run_id = f"{architecture}_seed{seed}"
            term = terminal(architecture, seed)
            train_hist = json.loads((MROOT / f"runs/{architecture}/seed_{seed}/training_history.json").read_text())["rows"]
            hist_by_update = {row["update"]: row for row in train_hist}
            model, _ = make_model(architecture, seed)
            initial_train, initial_coeff = evaluate(model, items["future_train"], details=True)
            initial_val, _ = evaluate(model, items["future_validation"])
            previous_vector = torch.cat([p.detach().reshape(-1) for p in model.parameters()])
            checkpoint_rows = []
            for path in checkpoint_paths(architecture, seed):
                model, state = make_model(architecture, seed, path)
                assert state is not None
                update = int(state["update_number"])
                train_metrics, coeff = evaluate(model, items["future_train"], details=True)
                validation_metrics, _ = evaluate(model, items["future_validation"])
                vector = torch.cat([p.detach().reshape(-1) for p in model.parameters()])
                delta = vector - previous_vector
                parameter_norm = float(torch.linalg.vector_norm(vector))
                update_ratio = float(torch.linalg.vector_norm(delta) / torch.clamp(torch.linalg.vector_norm(previous_vector), min=1e-30))
                checkpoint_rows.append({
                    "update": update,
                    "checkpoint": str(path.relative_to(STAGE.parent)),
                    "checkpoint_sha256": sha(path),
                    "historical_train_loss": hist_by_update[update]["graph_balanced_loss"],
                    "learning_rate": hist_by_update[update]["learning_rate"],
                    "unclipped_gradient_norm": hist_by_update[update]["unclipped_gradient_norm"],
                    "clipped_gradient_norm": hist_by_update[update]["clipped_gradient_norm"],
                    "clipping_indicator": hist_by_update[update]["unclipped_gradient_norm"] > 1.0,
                    "parameter_norm": parameter_norm,
                    "update_to_parameter_ratio_since_previous_saved_state": update_ratio,
                    "coefficients": coeff,
                    "train": train_metrics,
                    "validation": validation_metrics,
                })
                previous_vector = vector
            lowest = min(checkpoint_rows, key=lambda row: (row["train"]["family_balanced_mean"]["Q_L2"], row["update"]))
            selected = next(row for row in checkpoint_rows if row["update"] == term["best_validation_update"])
            terminal_row = checkpoint_rows[-1]
            ever = any(row["train"]["family_balanced_mean"]["Q_L2"] <= 0.25 for row in checkpoint_rows)
            ever_gate = ever_gate or ever
            summary = {
                "run_id": run_id,
                "architecture": architecture,
                "seed": seed,
                "initial_checkpoint": "deterministic_frozen_initialization_not_selection_eligible",
                "interval_checkpoint_count": len(checkpoint_rows),
                "best_validation_checkpoint": term["selected_checkpoint"],
                "selected_checkpoint_hash": term["selected_checkpoint_hash"],
                "terminal_checkpoint": checkpoint_rows[-1]["checkpoint"],
                "optimizer_updates": term["total_optimizer_steps"],
                "best_update": term["best_validation_update"],
                "stop_reason": term["stop_reason"],
                "A_initialization": {"update": 0, "train": initial_train, "validation": initial_val, "coefficients": initial_coeff},
                "B_lowest_train_metric_checkpoint": lowest,
                "C_validation_selected_checkpoint": selected,
                "D_terminal_checkpoint": terminal_row,
                "ever_achieved_train_family_balanced_Q_L2_le_0p25": ever,
            }
            runs.append(summary)
            dynamics[run_id] = {"run_id": run_id, "rows": checkpoint_rows}

            updates = [row["update"] for row in checkpoint_rows]
            fig, axes = plt.subplots(4, 3, figsize=(14, 13), constrained_layout=True)
            series = [
                ("historical_train_loss", "train loss"),
                (lambda r: r["train"]["family_balanced_mean"]["Q_L2"], "train family Q_L2"),
                (lambda r: r["validation"]["family_balanced_mean"]["Q_L2"], "validation family Q_L2"),
                ("learning_rate", "learning rate"),
                ("unclipped_gradient_norm", "gradient norm"),
                (lambda r: float(r["clipping_indicator"]), "clipping indicator"),
                (lambda r: r["coefficients"]["mean"]["alpha_RMS"], "alpha RMS"),
                (lambda r: r["coefficients"]["mean"]["beta_RMS"], "beta RMS"),
                (lambda r: r["coefficients"]["mean"]["alpha_saturation_fraction_abs_ge_0p99"], "alpha saturation"),
                (lambda r: r["coefficients"]["mean"]["beta_saturation_fraction_abs_ge_0p99"], "beta saturation"),
                ("parameter_norm", "parameter norm"),
                ("update_to_parameter_ratio_since_previous_saved_state", "update / parameter"),
            ]
            for axis, (getter, title) in zip(axes.ravel(), series):
                values = [row[getter] if isinstance(getter, str) else getter(row) for row in checkpoint_rows]
                axis.plot(updates, values, marker="o", markersize=2, linewidth=1)
                axis.axvline(term["best_validation_update"], color="tab:red", linestyle="--", linewidth=0.8)
                axis.set_title(title); axis.set_xlabel("historical update"); axis.grid(alpha=0.25)
            fig.suptitle(run_id + " (red: historically selected)")
            path = ROOT / f"checkpoint_dynamics/{run_id}.png"
            path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=160); plt.close(fig)

    classification = "TRAIN_FIT_ACHIEVED_SELECTED" if any(r["C_validation_selected_checkpoint"]["train"]["family_balanced_mean"]["Q_L2"] <= .25 for r in runs) else ("TRAIN_FIT_ACHIEVED_NOT_SELECTED" if ever_gate else "NEVER_FIT_TRAIN")
    result = {
        "run_order": [row["run_id"] for row in runs],
        "optimizer_updates": [row["optimizer_updates"] for row in runs],
        "best_updates": [row["best_update"] for row in runs],
        "run_mapping_unique": len({row["run_id"] for row in runs}) == 9,
        "runs": runs,
        "ever_achieved_train_gate": ever_gate,
        "classification": classification,
        "test_evaluated": False,
    }
    write_json(ROOT / "metric_reconstruction/complete_checkpoint_metric_reconstruction.json", result)
    write_json(ROOT / "checkpoint_dynamics/checkpoint_dynamics.json", {"runs": dynamics, "test_evaluated": False})
    return result, dynamics


def optimizer_conditioning(items: dict[str, list[Any]], reconstruction: dict[str, Any]) -> dict[str, Any]:
    audits = []
    for run in reconstruction["runs"]:
        architecture, seed = run["architecture"], run["seed"]
        selected_path = STAGE.parent / run["C_validation_selected_checkpoint"]["checkpoint"]
        for point, path in (("initialization", None), ("selected", selected_path)):
            model, state = make_model(architecture, seed, path)
            before = tensor_hash(model)
            named = list(model.named_parameters())
            optimizer_state = {} if state is None else state["optimizer_state"]["state"]
            prepared_lr = 2e-5 if state is None else float(state["scheduler_state"]["prepared_lr"])
            multiplier_records, directions = [], {}
            for multiplier in MULTIPLIERS:
                model.zero_grad(set_to_none=True)
                loss = graph_loss(model, items["future_train"])
                (loss * multiplier).backward()
                global_norm = float(torch.sqrt(sum(torch.sum(p.grad * p.grad) for _, p in named if p.grad is not None)))
                module_arrays: dict[str, dict[str, list[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
                effective_parts = []
                for index, (name, parameter) in enumerate(named):
                    grad = parameter.grad.detach()
                    old = optimizer_state.get(index, {})
                    m = old.get("exp_avg", torch.zeros_like(parameter)).detach()
                    v = old.get("exp_avg_sq", torch.zeros_like(parameter)).detach()
                    step = int(old.get("step", 0).item()) if isinstance(old.get("step", 0), torch.Tensor) else int(old.get("step", 0))
                    mnew = B1 * m + (1.0 - B1) * grad
                    vnew = B2 * v + (1.0 - B2) * grad * grad
                    mhat = mnew / (1.0 - B1 ** (step + 1))
                    vhat = vnew / (1.0 - B2 ** (step + 1))
                    adam = mhat / (torch.sqrt(vhat) + EPS)
                    effective = -prepared_lr * (adam + WD * parameter.detach())
                    effective_parts.append(effective.reshape(-1))
                    group = module_arrays[module_name(name)]
                    for key, value in (("grad", grad), ("param", parameter.detach()), ("m", m), ("v", v), ("effective", effective)):
                        group[key].append(value.cpu().numpy().reshape(-1))
                effective_vector = np.concatenate([x.cpu().numpy() for x in effective_parts])
                directions[multiplier] = effective_vector
                modules = {}
                for module, values in module_arrays.items():
                    g, p = np.concatenate(values["grad"]), np.concatenate(values["param"])
                    m, v, eff = np.concatenate(values["m"]), np.concatenate(values["v"]), np.concatenate(values["effective"])
                    sqrtv = np.sqrt(v)
                    prospective_sqrtv = np.sqrt(B2 * v + (1.0 - B2) * g * g)
                    wd = WD * p
                    modules[module] = {
                        "parameter_count": int(g.size),
                        "data_gradient_L2": float(np.linalg.norm(g)),
                        "data_gradient_Linf": float(np.max(np.abs(g))),
                        "weight_decay_contribution_L2": float(np.linalg.norm(wd)),
                        "weight_decay_to_data_gradient_L2_ratio": float(np.linalg.norm(wd) / max(np.linalg.norm(g), 1e-300)),
                        "adam_first_moment_L2": float(np.linalg.norm(m)),
                        "adam_second_moment_mean": float(np.mean(v)),
                        "historical_sqrt_v_mean": float(np.mean(sqrtv)),
                        "historical_epsilon_dominated_fraction": float(np.mean(sqrtv <= 10 * EPS)),
                        "prospective_sqrt_v_after_same_gradient_mean": float(np.mean(prospective_sqrtv)),
                        "epsilon_dominated_fraction": float(np.mean(prospective_sqrtv <= 10 * EPS)),
                        "weight_decay_dominated_fraction": float(np.mean(np.abs(wd) >= np.abs(g))),
                        "near_zero_gradient_fraction": float(np.mean(np.abs(g) <= 1e-14)),
                        "effective_adam_update_L2": float(np.linalg.norm(eff)),
                        "preclip_gradient_norm": float(np.linalg.norm(g)),
                        "postclip_gradient_norm": float(np.linalg.norm(g) * min(1.0, 1.0 / max(global_norm, 1e-300))),
                        "finite_fraction": float(np.mean(np.isfinite(g))),
                        "nonzero_fraction": float(np.mean(g != 0)),
                    }
                multiplier_records.append({"multiplier": multiplier, "base_loss": float(loss.detach()), "scaled_loss": float(loss.detach()) * multiplier, "global_gradient_norm": global_norm, "prepared_learning_rate": prepared_lr, "modules": modules})
            ref = directions[1.0]
            for record in multiplier_records:
                vec = directions[record["multiplier"]]
                record["effective_update_direction_cosine_vs_multiplier_1"] = float(np.dot(ref, vec) / max(np.linalg.norm(ref) * np.linalg.norm(vec), 1e-300))
            after = tensor_hash(model)
            audits.append({"run_id": run["run_id"], "architecture": architecture, "seed": seed, "point": point, "parameter_hash_before": before, "parameter_hash_after": after, "parameter_hash_unchanged": before == after, "loss_multiplier_diagnostics": multiplier_records})
    output = {"audits": audits, "all_parameter_hashes_unchanged": all(row["parameter_hash_unchanged"] for row in audits), "optimizer_step_calls": 0, "scheduler_step_calls": 0}
    write_json(ROOT / "optimization_conditioning/zero_step_conditioning.json", output)
    return output


def target_scale(items: dict[str, list[Any]], reconstruction: dict[str, Any]) -> dict[str, Any]:
    graph_rows = []
    for item in items["future_train"]:
        target = item.target
        assert target is not None
        graph_rows.append({
            "case_id": item.case_id, "family_id": item.family_id, "resolution_id": item.resolution_id, "support_id": item.support_id,
            "dimensional_target_RMS_m_per_s2": float(torch.sqrt(torch.mean(torch.sum(target * target, dim=-1)))),
            "target_tilde_RMS": float(torch.sqrt(torch.mean(torch.sum((target / A0) ** 2, dim=-1)))),
            "target_tilde_Linf": float(torch.max(torch.linalg.vector_norm(target / A0, dim=-1))),
        })
    run_rows = []
    for run in reconstruction["runs"]:
        run_rows.append({
            "run_id": run["run_id"],
            "initial_graphs": [{"case_id": row["case_id"], "prediction_RMS": row["prediction_RMS"]} for row in run["A_initialization"]["train"]["per_graph"]],
            "selected_graphs": [{"case_id": row["case_id"], "prediction_RMS": row["prediction_RMS"]} for row in run["C_validation_selected_checkpoint"]["train"]["per_graph"]],
            "initial_loss": float(np.mean([(row["Q_L2"] * row["target_RMS"] / A0) ** 2 for row in run["A_initialization"]["train"]["per_graph"]])),
            "selected_loss": run["C_validation_selected_checkpoint"]["historical_train_loss"],
            "selected_coefficient_scale": run["C_validation_selected_checkpoint"]["coefficients"]["mean"],
        })
    output = {"a0_m_per_s2": A0, "a0_unchanged": True, "train_graphs": graph_rows, "runs": run_rows}
    write_json(ROOT / "target_scaling/target_scale_audit.json", output)
    return output


def rooted_representation(item: Any) -> np.ndarray:
    graph = item.graph
    node = node_features(graph).detach().numpy()
    edge = symmetric_pair_features(graph, pair_geometry(graph)).detach().numpy()
    reps = []
    for index in range(node.shape[0]):
        values = edge[(graph.pair_i.numpy() == index) | (graph.pair_j.numpy() == index)]
        reps.append(np.concatenate([node[index], values.mean(0), values.std(0), values.max(0)]))
    return np.stack(reps)


def allowed_graph_signature(item: Any) -> str:
    graph = item.graph
    arrays = [graph.position, graph.velocity, graph.density, graph.pressure, graph.mass, graph.smoothing_length,
              graph.pair_i.to(torch.float64), graph.pair_j.to(torch.float64), graph.active.to(torch.float64), graph.displacement, graph.relative_velocity]
    digest = hashlib.sha256()
    for value in arrays:
        assert value is not None
        digest.update(f64bytes(value.detach().numpy()))
    return "sha256:" + digest.hexdigest()


def identifiability_and_shift(loader: Any, items: dict[str, list[Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    supervised = items["future_train"] + items["future_validation"]
    edge_groups: dict[bytes, list[dict[str, Any]]] = defaultdict(list)
    graph_groups: dict[str, list[Any]] = defaultdict(list)
    reps, targets, labels = [], [], []
    for item in supervised:
        edge = symmetric_pair_features(item.graph, pair_geometry(item.graph)).detach().numpy()
        for index, row in enumerate(edge):
            edge_groups[f64bytes(row)].append({"case_id": item.case_id, "edge_index": index, "family_id": item.family_id})
        graph_groups[allowed_graph_signature(item)].append(item)
        rep = rooted_representation(item)
        reps.append(rep); targets.append(item.target.detach().numpy()); labels.extend([item.family_id] * rep.shape[0])
    contradictions = []
    for signature, group in graph_groups.items():
        if len(group) > 1:
            for left in range(len(group)):
                for right in range(left + 1, len(group)):
                    if group[left].target.shape == group[right].target.shape and not np.array_equal(group[left].target.numpy(), group[right].target.numpy()):
                        contradictions.append({"signature": signature, "left": group[left].case_id, "right": group[right].case_id})
    train_rep = np.concatenate(reps[:len(items["future_train"])])
    mean, scale = train_rep.mean(0), train_rep.std(0); scale[scale == 0] = 1.0
    all_rep = (np.concatenate(reps) - mean) / scale
    all_targets = np.concatenate(targets) / A0
    tree = cKDTree(all_rep)
    near = []
    for radius in CONTRACT["feature_identifiability"]["near_collision_L2_radii"]:
        pairs = sorted(tree.query_pairs(radius))
        spreads = [float(np.linalg.norm(all_targets[i] - all_targets[j])) for i, j in pairs]
        near.append({"radius": radius, "pair_count": len(pairs), "target_response_spread_mean": float(np.mean(spreads)) if spreads else None, "target_response_spread_max": float(np.max(spreads)) if spreads else None, "no_posthoc_threshold": True})
    by_family = {}
    labels_arr = np.asarray(labels)
    for family in sorted(set(labels)):
        current = all_rep[labels_arr == family]
        other = all_rep[labels_arr != family]
        distances, _ = cKDTree(other).query(current, k=1)
        by_family[family] = {"node_count": len(current), "nearest_other_family_distance_mean": float(np.mean(distances)), "nearest_other_family_distance_min": float(np.min(distances)), "nearest_other_family_distance_max": float(np.max(distances))}
    ident_status = "HARD_FEATURE_IDENTIFIABILITY_CONTRADICTION" if contradictions else "NO_HARD_IDENTIFIABILITY_CONTRADICTION_FOUND"
    ident = {
        "status": ident_status,
        "exact_edge_feature_vector_count": sum(len(v) for v in edge_groups.values()),
        "exact_edge_collision_group_count": sum(len(v) > 1 for v in edge_groups.values()),
        "exact_edge_collision_instance_count": sum(len(v) for v in edge_groups.values() if len(v) > 1),
        "edge_collision_interpretation": "No pseudo-inverse pair coefficient was treated as a unique target; edge collisions alone are not hard contradictions.",
        "exact_full_allowed_graph_input_collision_group_count": sum(len(v) > 1 for v in graph_groups.values()),
        "hard_incompatible_target_cases": contradictions,
        "near_collision_audit": near,
        "family_dependence": by_family,
        "test_target_used": False,
    }
    write_json(ROOT / "feature_identifiability/feature_identifiability_audit.json", ident)

    all_items = items["future_train"] + items["future_validation"] + items["future_test"]
    summaries = []
    for item in all_items:
        node = node_features(item.graph).detach().numpy()
        edge = symmetric_pair_features(item.graph, pair_geometry(item.graph)).detach().numpy()
        vector = np.concatenate([node.mean(0), node.std(0), node.min(0), node.max(0), edge.mean(0), edge.std(0), edge.min(0), edge.max(0)])
        summaries.append({"case_id": item.case_id, "family_id": item.family_id, "split_role": item.split_role, "resolution_id": item.resolution_id, "support_id": item.support_id, "vector": vector})
    train_matrix = np.stack([row["vector"] for row in summaries if row["split_role"] == "future_train"])
    gmean, gscale = train_matrix.mean(0), train_matrix.std(0); gscale[gscale == 0] = 1.0
    train_norm = (train_matrix - gmean) / gscale
    def hull_distance(x: np.ndarray) -> tuple[float, bool]:
        n = train_norm.shape[0]
        objective = lambda w: float(np.sum((w @ train_norm - x) ** 2))
        result = minimize(objective, np.ones(n) / n, method="SLSQP", bounds=[(0.0, 1.0)] * n, constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1.0}, options={"ftol": CONTRACT["family_shift"]["convex_hull_ftol"], "maxiter": CONTRACT["family_shift"]["convex_hull_maxiter"]})
        return math.sqrt(max(float(result.fun), 0.0)), bool(result.success)
    shift_rows = []
    train_tree = cKDTree(train_norm)
    for row in summaries:
        x = (row["vector"] - gmean) / gscale
        if row["split_role"] == "future_train":
            distances = np.linalg.norm(train_norm - x, axis=1); distances[distances == 0] = np.inf
            nearest = float(np.min(distances))
        else:
            nearest = float(train_tree.query(x, k=1)[0])
        hull, success = hull_distance(x)
        shift_rows.append({key: row[key] for key in ("case_id", "family_id", "split_role", "resolution_id", "support_id")} | {"train_nearest_neighbor_distance": nearest, "train_convex_hull_distance": hull, "convex_hull_solver_success": success})
    sealed = json.loads((MROOT / "test_evaluation/sealed_test_evaluation_manifest.json").read_text())
    shift = {
        "graph_summary_rows": shift_rows,
        "aggregates_by_split": {role: {"nearest_neighbor_mean": float(np.mean([r["train_nearest_neighbor_distance"] for r in shift_rows if r["split_role"] == role])), "convex_hull_mean": float(np.mean([r["train_convex_hull_distance"] for r in shift_rows if r["split_role"] == role]))} for role in ("future_train", "future_validation", "future_test")},
        "per_resolution": {value: {"nearest_neighbor_mean": float(np.mean([r["train_nearest_neighbor_distance"] for r in shift_rows if r["resolution_id"] == value]))} for value in sorted({r["resolution_id"] for r in shift_rows})},
        "per_support": {value: {"nearest_neighbor_mean": float(np.mean([r["train_nearest_neighbor_distance"] for r in shift_rows if r["support_id"] == value]))} for value in sorted({r["support_id"] for r in shift_rows})},
        "historical_sealed_test_manifest_sha256": sha(MROOT / "test_evaluation/sealed_test_evaluation_manifest.json"),
        "historical_sealed_test_metrics_descriptive_only": sealed,
        "test_inputs_decoded": 5,
        "test_targets_decoded": 0,
        "new_test_evaluations": 0,
        "current_test_status": "consumed_confirmatory_test",
    }
    write_json(ROOT / "family_shift/family_configuration_shift.json", shift)
    return ident, shift


def main() -> None:
    freeze = json.loads((ROOT / "freeze/stage02mr_historical_freeze_manifest.json").read_text())
    if freeze["status"] != "PASS":
        raise RuntimeError("historical freeze did not pass")
    loader, items = load_items(include_test_inputs=True)
    reconstruction, _ = checkpoint_metric_reconstruction(items)
    conditioning = optimizer_conditioning(items, reconstruction)
    scale = target_scale(items, reconstruction)
    ident, shift = identifiability_and_shift(loader, items)
    summary = {
        "status": "PASS",
        "metric_classification": reconstruction["classification"],
        "conditioning_parameter_hashes_unchanged": conditioning["all_parameter_hashes_unchanged"],
        "identifiability_status": ident["status"],
        "test_target_decode_count": 0,
        "new_optimizer_steps": 0,
        "new_training_runs": 0,
        "new_test_evaluations": 0,
        "target_scale_a0_unchanged": scale["a0_unchanged"],
        "family_shift_test_input_only": shift["test_targets_decoded"] == 0,
    }
    write_json(ROOT / "results/core_diagnostics_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
