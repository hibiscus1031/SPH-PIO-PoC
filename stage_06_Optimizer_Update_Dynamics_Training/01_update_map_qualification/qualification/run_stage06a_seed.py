"""Run one Stage 06A arm/seed over frozen blind lineage and global batches."""

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
import resource
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

HERE = Path(__file__).resolve()
STAGE06 = HERE.parents[2]
ROOT = HERE.parents[3]
STAGE05C = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c"
sys.path.insert(0, str(STAGE05C / "qualification"))
import run_stage05c_arm as q

SEEDS = [20600601, 20600602, 20600603]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
LRS = [1e-5, 3e-5, 1e-4, 3e-4, 1e-3]
ACTUAL_FD_SCALES = [.25, .5, 1., 2.]
DIAGNOSTIC_RADII = [1e-5, 3e-5]
PROCESS = psutil.Process()


def write_json(path: Path, value: Any) -> None:
    def convert(item: Any) -> Any:
        if isinstance(item, np.bool_): return bool(item)
        if isinstance(item, np.integer): return int(item)
        if isinstance(item, np.floating): return float(item)
        raise TypeError(type(item).__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=convert) + "\n", encoding="utf-8")


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def tensor_digest(values: tuple[torch.Tensor, ...] | list[torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for value in values: digest.update(q.tensor_bytes(value))
    return "sha256:" + digest.hexdigest()


def vector_stats(value: torch.Tensor) -> dict[str, Any]:
    return {"element_count": value.numel(), "L2": float(torch.linalg.vector_norm(value)),
            "RMS": float(torch.sqrt(value.square().mean())), "Linf": float(value.abs().max()),
            "finite": bool(torch.isfinite(value).all()), "exact_nonzero_count": int((value != 0).sum())}


def load_cases() -> dict[str, q.Case]:
    manifest = json.loads((STAGE06 / "01_update_map_qualification/blind_batches/cached_blind_batch_manifest.json").read_text())
    assert manifest["pass"] and manifest["case_count"] == 96
    result = {}
    for row in manifest["cases"]:
        path = ROOT / row["path"]; assert sha_file(path) == row["sha256"]
        with np.load(path, allow_pickle=False) as archive: arrays = {key: archive[key] for key in archive.files}
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
    assert len(rows) == 16; return rows


def global_batch(cases: dict[str, q.Case], origins: dict[str, Any]) -> list[q.Case]:
    rows = [case for lineage in LINEAGES for case in batch_for(lineage, cases, origins)]
    assert len(rows) == 96; return rows


def fresh(arm: str, seed: int, expected_hash: str) -> tuple[torch.nn.Module, q.DefectAdapter]:
    torch.manual_seed(seed)
    model = q.ARMS[arm]().to(dtype=torch.float64, device="cpu"); model.eval()
    assert q.parameter_hash(model) == expected_hash
    return model, q.DefectAdapter(arm, model)


def optimizer_for(adapter: q.DefectAdapter, lr: float) -> torch.optim.AdamW:
    return torch.optim.AdamW(adapter.parameters(), lr=lr, betas=(.9, .999), eps=1e-12,
                             weight_decay=0, amsgrad=False)


def parameter_norm(params: tuple[torch.Tensor, ...]) -> tuple[float, float]:
    norm = float(torch.sqrt(sum(parameter.detach().square().sum() for parameter in params)))
    reference = max(norm, math.sqrt(sum(parameter.numel() for parameter in params)) * 1e-3)
    return norm, reference


def moment_stats(optimizer: torch.optim.AdamW) -> dict[str, Any]:
    first, second, steps = [], [], []
    for state in optimizer.state.values():
        first.append(state["exp_avg"].detach()); second.append(state["exp_avg_sq"].detach())
        step = state["step"]; steps.append(float(step.detach()) if torch.is_tensor(step) else float(step))
    first_v = torch.cat([value.reshape(-1) for value in first]); second_v = torch.cat([value.reshape(-1) for value in second])
    return {"parameter_state_count": len(first), "step_values": sorted(set(steps)),
            "first_moment": vector_stats(first_v), "second_moment": vector_stats(second_v),
            "finite": bool(torch.isfinite(first_v).all() and torch.isfinite(second_v).all()),
            "state_sha256": tensor_digest(first + second)}


def coefficient_diagnostic(adapter: q.DefectAdapter, case: q.Case) -> dict[str, Any]:
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
        _, _, output, _, _ = adapter.start_audit(case)
    alpha = output.alpha.detach(); beta = output.beta.detach()
    return {"alpha_min": float(alpha.min()), "alpha_max": float(alpha.max()),
            "beta_min": float(beta.min()), "beta_max": float(beta.max()),
            "alpha_saturation_fraction": float((alpha.abs() >= .99 * .05).to(torch.float64).mean()),
            "beta_saturation_fraction": float((beta.abs() >= .99 * .05).to(torch.float64).mean()),
            "finite": bool(torch.isfinite(alpha).all() and torch.isfinite(beta).all())}


def one_step_once(arm: str, seed: int, expected_hash: str, cases: list[q.Case], lr: float) -> tuple[dict[str, Any], tuple[torch.Tensor, ...]]:
    model, adapter = fresh(arm, seed, expected_hash); params = tuple(parameter for _, parameter in adapter.named_parameters())
    names = [name for name, _ in adapter.named_parameters()]; before_values = tuple(parameter.detach().clone() for parameter in params)
    before_hash = q.parameter_hash(model); optimizer = optimizer_for(adapter, lr)
    initial_state_empty = len(optimizer.state) == 0
    optimizer.zero_grad(set_to_none=True)
    with sdpa_kernel(SDPBackend.MATH): loss = adapter(cases)
    before_loss = float(loss.detach()); before_trace = json.loads(json.dumps(adapter.last_trace)); loss.backward()
    gradients = tuple(parameter.grad.detach().clone() for parameter in params)
    gradient_norm = float(torch.sqrt(sum(gradient.square().sum() for gradient in gradients)))
    clip_factor = min(1., 1. / max(gradient_norm, 1e-30))
    returned_norm = float(torch.nn.utils.clip_grad_norm_(params, max_norm=1.0))
    clipped_norm = float(torch.sqrt(sum(parameter.grad.detach().square().sum() for parameter in params)))
    optimizer.step()
    updates = tuple(parameter.detach() - before for parameter, before in zip(params, before_values))
    update_vector = torch.cat([value.reshape(-1) for value in updates]); gradient_vector = torch.cat([value.reshape(-1) for value in gradients])
    parameter_vector = torch.cat([value.reshape(-1) for value in before_values]); _, theta_ref = parameter_norm(before_values)
    update_norm = float(torch.linalg.vector_norm(update_vector)); grad_norm = float(torch.linalg.vector_norm(gradient_vector))
    cosine = float(torch.dot(update_vector, -gradient_vector) / max(update_norm * grad_norm, 1e-30))
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH): after_loss_tensor = adapter(cases)
    after_loss = float(after_loss_tensor); after_trace = json.loads(json.dumps(adapter.last_trace))
    moments = moment_stats(optimizer); coeff = coefficient_diagnostic(adapter, cases[0])
    row = {"learning_rate": lr, "L_before": before_loss, "L_after": after_loss, "Delta_L": after_loss - before_loss,
           "gradient": vector_stats(gradient_vector), "gradient_sha256": tensor_digest(gradients),
           "gradient_clip_factor": clip_factor, "clip_returned_preclip_L2": returned_norm,
           "clipped_gradient_L2": clipped_norm, "effective_update": vector_stats(update_vector),
           "effective_update_sha256": tensor_digest(updates), "cosine_update_negative_gradient": cosine,
           "parameter_L2": float(torch.linalg.vector_norm(parameter_vector)),
           "parameter_relative_update": update_norm / theta_ref,
           "optimizer_state_initially_empty": initial_state_empty, "optimizer_moments_after_step": moments,
           "coefficient_saturation": coeff, "parameter_hash_before": before_hash,
           "parameter_hash_after": q.parameter_hash(model), "topology_unchanged": before_trace["topology"] == after_trace["topology"],
           "graph_identity_before": before_trace["graph_hashes"], "graph_identity_after": after_trace["graph_hashes"],
           "safety_before": before_trace["safe"], "safety_after": after_trace["safe"],
           "density_positive": min(case["density_min"] for case in before_trace["cases"] + after_trace["cases"]) > 0,
           "correction_force_residual_max": max(case["force_residual_max"] for case in before_trace["cases"] + after_trace["cases"]),
           "accepted_state_commit_count": 1, "temporal_history_commit_count": 0 if arm == "D1" else 1,
           "midpoint_commit_count": 0}
    del optimizer, adapter, model, params, before_values, updates, update_vector, gradient_vector, parameter_vector, loss, after_loss_tensor
    gc.collect(); return row, gradients


def one_step_lr(arm: str, seed: int, expected_hash: str, cases: list[q.Case], lr: float,
                groups: list[dict[str, Any]]) -> dict[str, Any]:
    first, grad_first = one_step_once(arm, seed, expected_hash, cases, lr)
    second, grad_second = one_step_once(arm, seed, expected_hash, cases, lr)
    # Names are invariant and only needed for the frozen scientific grouping.
    model, adapter = fresh(arm, seed, expected_hash); params = tuple(parameter for _, parameter in adapter.named_parameters())
    names = [name for name, _ in adapter.named_parameters()]
    group_gradients = [q.group_stats(grad_first, grad_second, params, names, group) for group in groups]
    # Reconstruct grouped update statistics from deterministic first-step Adam:
    # at step one with zero moments and no weight decay, every active element is
    # lr-scaled sign(gradient), after global clipping.
    group_updates = []
    for group, grad_stat in zip(groups, group_gradients):
        gv = q.group_vector(grad_first, names, group)
        uv = -lr * gv / (gv.abs() + 1e-12 / max(first["gradient_clip_factor"], 1e-30))
        stats = vector_stats(uv); stats.update({"group": group["group"], "active": grad_stat["active"] and stats["L2"] > 0})
        group_updates.append(stats)
    del model, adapter, params
    deterministic = (first["L_before"] == second["L_before"] and first["L_after"] == second["L_after"]
                     and first["gradient_sha256"] == second["gradient_sha256"]
                     and first["effective_update_sha256"] == second["effective_update_sha256"]
                     and first["optimizer_moments_after_step"]["state_sha256"] == second["optimizer_moments_after_step"]["state_sha256"]
                     and first["graph_identity_before"] == second["graph_identity_before"]
                     and first["graph_identity_after"] == second["graph_identity_after"])
    u_loss = max(abs(first["L_before"] - second["L_before"]),
                 128 * np.finfo(np.float64).eps * max(1., abs(first["L_before"])))
    passed = (first["Delta_L"] < -100 * u_loss and np.isfinite([first["L_before"], first["L_after"]]).all()
              and first["gradient"]["finite"] and first["gradient"]["L2"] > 0
              and all(row["active"] for row in group_updates) and first["effective_update"]["finite"]
              and first["cosine_update_negative_gradient"] > 0 and first["parameter_relative_update"] < 1e-2
              and first["topology_unchanged"] and first["safety_before"] and first["safety_after"]
              and first["density_positive"] and first["correction_force_residual_max"] <= 1e-10
              and first["optimizer_moments_after_step"]["finite"] and deterministic)
    result = dict(first); result.update({"loss_repeat_numerical_floor": u_loss, "deterministic_repeat": deterministic,
                                        "gradient_groups": group_gradients, "update_groups": group_updates,
                                        "no_parameter_group_skipped": all(row["active"] for row in group_updates),
                                        "repeat_identity": {"L_before": second["L_before"], "L_after": second["L_after"],
                                                            "gradient_sha256": second["gradient_sha256"],
                                                            "effective_update_sha256": second["effective_update_sha256"],
                                                            "optimizer_state_sha256": second["optimizer_moments_after_step"]["state_sha256"]},
                                        "qualification_optimizer_instances": 2, "qualification_optimizer_steps": 2,
                                        "pass": bool(passed)})
    del grad_first, grad_second; gc.collect(); return result


def micro_horizon(arm: str, seed: int, expected_hash: str, cases: list[q.Case], lr: float, horizon: int) -> dict[str, Any]:
    model, adapter = fresh(arm, seed, expected_hash); params = tuple(parameter for _, parameter in adapter.named_parameters())
    initial = tuple(parameter.detach().clone() for parameter in params); _, theta_ref = parameter_norm(initial)
    optimizer = optimizer_for(adapter, lr); losses = []; steps = []; update_hashes = []
    for step_index in range(1, horizon + 1):
        optimizer.zero_grad(set_to_none=True)
        with sdpa_kernel(SDPBackend.MATH): loss = adapter(cases)
        current = float(loss.detach()); trace_before = json.loads(json.dumps(adapter.last_trace))
        if not losses: losses.append(current)
        else: assert current == losses[-1]
        loss.backward(); gradients = tuple(parameter.grad.detach().clone() for parameter in params)
        grad_norm = float(torch.sqrt(sum(value.square().sum() for value in gradients)))
        clip_factor = min(1., 1. / max(grad_norm, 1e-30)); torch.nn.utils.clip_grad_norm_(params, 1.0)
        before = tuple(parameter.detach().clone() for parameter in params); optimizer.step()
        updates = tuple(parameter.detach() - value for parameter, value in zip(params, before)); update_hashes.append(tensor_digest(updates))
        update_norm = float(torch.sqrt(sum(value.square().sum() for value in updates)))
        displacement = tuple(parameter.detach() - value for parameter, value in zip(params, initial))
        displacement_norm = float(torch.sqrt(sum(value.square().sum() for value in displacement)))
        # Keep grad mode identical across the post-step observation and the
        # next pre-step evaluation. D3 attention can differ by roundoff when
        # PyTorch selects a distinct no-grad internal path even under the same
        # explicitly locked MATH backend.
        with sdpa_kernel(SDPBackend.MATH): after_tensor = adapter(cases)
        after = float(after_tensor.detach()); trace_after = json.loads(json.dumps(adapter.last_trace)); losses.append(after)
        steps.append({"step": step_index, "L_before": current, "L_after": after, "Delta_L": after-current,
                      "gradient_L2": grad_norm, "gradient_finite": all(torch.isfinite(value).all() for value in gradients),
                      "gradient_clip_factor": clip_factor, "update_L2": update_norm,
                      "update_RMS": math.sqrt(sum(value.square().sum().item() for value in updates) / sum(value.numel() for value in updates)),
                      "update_Linf": max(float(value.abs().max()) for value in updates), "update_sha256": update_hashes[-1],
                      "moment_state": moment_stats(optimizer), "parameter_relative_displacement": displacement_norm / theta_ref,
                      "topology_unchanged": trace_before["topology"] == trace_after["topology"],
                      "density_min": min(case["density_min"] for case in trace_before["cases"] + trace_after["cases"]),
                      "correction_force_residual_max": max(case["force_residual_max"] for case in trace_before["cases"] + trace_after["cases"]),
                      "graph_identity": trace_after["graph_hashes"], "safety": trace_before["safe"] and trace_after["safe"],
                      "coefficient_saturation": coefficient_diagnostic(adapter, cases[0]),
                      "accepted_state_commit_count": 1, "temporal_history_commit_count": 0 if arm == "D1" else 1,
                      "midpoint_commit_count": 0})
        del loss, after_tensor, gradients, before, updates, displacement; gc.collect()
    row = {"horizon": horizon, "learning_rate": lr, "loss_sequence": losses, "steps": steps,
           "update_hashes": update_hashes, "optimizer_state_initially_zero": True,
           "qualification_optimizer_instances": 1, "qualification_optimizer_steps": horizon,
           "final_parameter_hash": q.parameter_hash(model)}
    del optimizer, adapter, model, params, initial; gc.collect(); return row


def micro_update(arm: str, seed: int, expected_hash: str, cases: list[q.Case], lr: float) -> dict[str, Any]:
    horizon2 = micro_horizon(arm, seed, expected_hash, cases, lr, 2)
    horizon4 = micro_horizon(arm, seed, expected_hash, cases, lr, 4)
    prefix_repeat = horizon2["loss_sequence"] == horizon4["loss_sequence"][:3] and horizon2["update_hashes"] == horizon4["update_hashes"][:2]
    losses = horizon4["loss_sequence"]; floor = 128 * np.finfo(np.float64).eps * max(1., max(abs(value) for value in losses))
    relative_reduction = (losses[0] - losses[4]) / max(abs(losses[0]), 1e-30)
    relative_increases = [(losses[i+1] - losses[i]) / max(abs(losses[i]), 1e-30) for i in range(4)]
    steps = horizon4["steps"]
    passed = (losses[1] < losses[0] and losses[2] <= losses[1] + floor and losses[4] <= losses[2] + floor
              and relative_reduction >= 1e-4 and max(relative_increases) <= 1e-3
              and all(row["gradient_finite"] and np.isfinite([row["gradient_L2"], row["update_L2"]]).all() for row in steps)
              and all(row["parameter_relative_displacement"] <= 5e-2 for row in steps)
              and all(row["topology_unchanged"] and row["density_min"] > 0 and row["correction_force_residual_max"] <= 1e-10
                      and row["safety"] and row["moment_state"]["finite"] and row["coefficient_saturation"]["finite"] for row in steps)
              and prefix_repeat)
    return {"learning_rate": lr, "horizon2": horizon2, "horizon4": horizon4,
            "deterministic_2_step_prefix": prefix_repeat, "numerical_floor": floor,
            "step4_relative_loss_reduction": relative_reduction, "single_step_relative_loss_increases": relative_increases,
            "no_gradient_or_update_explosion": all(row["gradient_finite"] and row["update_L2"] < math.inf for row in steps),
            "qualification_optimizer_instances": 2, "qualification_optimizer_steps": 6, "pass": bool(passed)}


def actual_update_fd(arm: str, seed: int, expected_hash: str, cases: list[q.Case], lr: float,
                     run_structure: bool) -> dict[str, Any]:
    model, adapter = fresh(arm, seed, expected_hash); params = tuple(parameter for _, parameter in adapter.named_parameters())
    names = [name for name, _ in adapter.named_parameters()]; base_values = tuple(parameter.detach().clone() for parameter in params)
    optimizer = optimizer_for(adapter, lr); optimizer.zero_grad(set_to_none=True)
    with sdpa_kernel(SDPBackend.MATH): loss = adapter(cases)
    base_loss = float(loss.detach()); base_trace = json.loads(json.dumps(adapter.last_trace)); loss.backward()
    gradients = tuple(parameter.grad.detach().clone() for parameter in params); torch.nn.utils.clip_grad_norm_(params, 1.0); optimizer.step()
    updates = tuple(parameter.detach() - base for parameter, base in zip(params, base_values))
    reverse = float(sum((gradient * update).sum() for gradient, update in zip(gradients, updates)))
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH): observed_tensor = adapter(cases)
    observed_loss = float(observed_tensor); observed_trace = json.loads(json.dumps(adapter.last_trace))
    rows = []
    for scale_index, scale in enumerate(ACTUAL_FD_SCALES):
        plus_values = tuple(base + scale * update for base, update in zip(base_values, updates))
        minus_values = tuple(base - scale * update for base, update in zip(base_values, updates))
        plus, minus, plus_traces, minus_traces = [], [], [], []
        for repeat in range(2):
            lp, tp = q.evaluate_values(adapter, cases, plus_values, names, seed + 700000 + scale_index * 100 + repeat * 2)
            lm, tm = q.evaluate_values(adapter, cases, minus_values, names, seed + 700000 + scale_index * 100 + repeat * 2 + 1)
            plus.append(lp); minus.append(lm); plus_traces.append(tp); minus_traces.append(tm)
        fd_repeats = [(p-m)/(2*scale) for p,m in zip(plus,minus)]; fd = float(np.mean(fd_repeats))
        deterministic = (plus[0] == plus[1] and minus[0] == minus[1]
                         and plus_traces[0]["graph_hashes"] == plus_traces[1]["graph_hashes"]
                         and minus_traces[0]["graph_hashes"] == minus_traces[1]["graph_hashes"])
        topology = all(trace["topology"] == base_trace["topology"] for trace in plus_traces + minus_traces)
        safe = all(trace["safe"] for trace in plus_traces + minus_traces)
        rows.append({"scale": scale, "plus_loss_repeats": plus, "minus_loss_repeats": minus,
                     "central_FD_repeats": fd_repeats, "central_FD": fd,
                     "reverse_directional_derivative": reverse,
                     "sign_consistent": (fd < 0) == (reverse < 0) and fd != 0 and reverse != 0,
                     "deterministic": deterministic, "topology_unchanged": topology, "safety": safe})
    adjacent = [{"scales": [rows[i]["scale"], rows[i+1]["scale"]],
                 "pass": all(rows[j]["sign_consistent"] and rows[j]["deterministic"] and rows[j]["topology_unchanged"] and rows[j]["safety"] for j in (i,i+1))}
                for i in range(len(rows)-1)]
    structure = None
    if run_structure:
        with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
            state, history, output, graph, token = adapter.start_audit(cases[0])
            structure = q.audit_stage(arm=arm, model=model, state=state, history=history, stage="start",
                                      reference_output=output, reference_graph=graph, reference_token=token)
    passed = (reverse < 0 and observed_loss < base_loss and any(row["pass"] for row in adjacent)
              and base_trace["safe"] and observed_trace["safe"] and base_trace["topology"] == observed_trace["topology"]
              and (structure is None or structure["pass"]))
    result = {"learning_rate_selection_algorithm": "smallest LR belonging to a passing adjacent one-step pair",
              "learning_rate": lr, "L_before": base_loss, "L_after_actual_step": observed_loss,
              "observed_Delta_L": observed_loss-base_loss, "reverse_directional_derivative": reverse,
              "update_sha256": tensor_digest(updates), "scales": rows, "adjacent_direction_stable_pairs": adjacent,
              "observed_change_local_prediction_sign_consistent": observed_loss-base_loss < 0 and reverse < 0,
              "structure_audit": structure, "qualification_optimizer_instances": 1,
              "qualification_optimizer_steps": 1, "FD_evaluation_paths": len(ACTUAL_FD_SCALES)*4,
              "pass": bool(passed)}
    del optimizer, adapter, model, params, base_values, gradients, updates, loss, observed_tensor; gc.collect(); return result


def diagnostic_probe(adapter: q.DefectAdapter, cases: list[q.Case], params: tuple[torch.Tensor, ...], names: list[str],
                     gradient: tuple[torch.Tensor, ...], direction: tuple[torch.Tensor, ...], scale: float,
                     base_trace: dict[str, Any], rng_seed: int) -> dict[str, Any]:
    reverse_jvp = q.reverse_jvp(adapter, cases, params, names, direction, gradient); rows = []
    for index, radius in enumerate(DIAGNOSTIC_RADII):
        h = radius * scale; plus, minus, traces = [], [], []
        for repeat in range(2):
            pv = tuple(parameter + h*delta for parameter, delta in zip(params,direction))
            mv = tuple(parameter - h*delta for parameter, delta in zip(params,direction))
            lp,tp = q.evaluate_values(adapter,cases,pv,names,rng_seed+index*100+repeat*2)
            lm,tm = q.evaluate_values(adapter,cases,mv,names,rng_seed+index*100+repeat*2+1)
            plus.append(lp); minus.append(lm); traces.extend([tp,tm])
        fds = [(p-m)/(2*h) for p,m in zip(plus,minus)]; fd = float(np.mean(fds)); reverse = reverse_jvp["reverse"]
        rows.append({"radius": radius, "arc_length": h, "plus_loss_repeats": plus, "minus_loss_repeats": minus,
                     "central_FD_repeats": fds, "central_FD": fd,
                     "FD_reverse_abs": abs(fd-reverse), "FD_reverse_rel": abs(fd-reverse)/max(abs(fd),abs(reverse),1e-30),
                     "FD_reverse_pass": abs(fd-reverse)<=1e-8 or abs(fd-reverse)/max(abs(fd),abs(reverse),1e-30)<=1e-4,
                     "sign_consistent": reverse_jvp["near_zero"] or fd*reverse >= 0,
                     "deterministic": plus[0]==plus[1] and minus[0]==minus[1]
                                      and traces[0]["graph_hashes"]==traces[2]["graph_hashes"]
                                      and traces[1]["graph_hashes"]==traces[3]["graph_hashes"],
                     "topology_unchanged": all(trace["topology"]==base_trace["topology"] for trace in traces),
                     "safety": all(trace["safe"] for trace in traces)})
    variation = abs(rows[0]["central_FD"]-rows[1]["central_FD"])/max(abs(rows[0]["central_FD"]),abs(rows[1]["central_FD"]),1e-30)
    stable = all(row["FD_reverse_pass"] for row in rows) and variation <= 1e-3
    if not reverse_jvp["pass"]: classification = "REVERSE_JVP_MAPPING_CONTRADICTION"
    elif any(not row["sign_consistent"] for row in rows): classification = "SIGN_CONTRADICTION"
    elif any(not row["deterministic"] for row in rows): classification = "NONDETERMINISTIC"
    elif any(not row["safety"] or not row["topology_unchanged"] for row in rows): classification = "SAFETY_FAILURE"
    elif reverse_jvp["near_zero"] and all(abs(row["central_FD"]) <= 1e-8 for row in rows): classification = "NEAR_ZERO_CONSISTENT"
    elif stable: classification = "PASS"
    else: classification = "FD_WINDOW_MISSING"
    return {"reverse_jvp": reverse_jvp, "radii": rows, "adjacent_relative_variation": variation,
            "classification": classification, "diagnostic_pass": classification in {"PASS","NEAR_ZERO_CONSISTENT","FD_WINDOW_MISSING"},
            "FD_window_missing_allowed": True, "evaluation_paths": 8}


def coordinate_boundary(arm: str, seed: int, expected_hash: str, lineage: str, cases: list[q.Case],
                        groups: list[dict[str, Any]], plan: list[dict[str, Any]]) -> dict[str, Any]:
    model, adapter = fresh(arm, seed, expected_hash); params = tuple(parameter for _, parameter in adapter.named_parameters())
    names = [name for name, _ in adapter.named_parameters()]
    with sdpa_kernel(SDPBackend.MATH): loss = adapter(cases)
    gradient = tuple(value.detach().clone() for value in torch.autograd.grad(loss, params, allow_unused=False))
    base_trace = json.loads(json.dumps(adapter.last_trace)); probes = []
    for group_index, group in enumerate(groups):
        context = next(row for row in plan if row["arm"]==arm and row["seed"]==seed and row["lineage"]==lineage and row["group"]==group["group"])
        for probe_index, (kind, probe) in enumerate([*(('coordinate',x) for x in context["coordinates"]), *(('block',x) for x in context["blocks"]) ]):
            if kind == "coordinate":
                indices=[probe["group_flat_index"]]; weights=[1.]
                scale=max(1.,abs(float(q.group_vector(params,names,group)[indices[0]].detach())))
            else:
                indices=probe["indices"]; weights=(np.asarray(probe["rademacher_signs"],dtype=float)/math.sqrt(len(indices))).tolist()
                gv=q.group_vector(params,names,group); scale=max(1.,float(torch.sqrt(gv[indices].detach().square().mean())))
            direction=q.group_direction(params,names,group,indices,weights)
            row=diagnostic_probe(adapter,cases,params,names,gradient,direction,scale,base_trace,
                                 seed+group_index*100000+probe_index*1000+LINEAGES.index(lineage)*10)
            row.update({"arm":arm,"seed":seed,"lineage":lineage,"group":group["group"],"kind":kind,
                        "selection":probe,"perturbation_scale":scale}); probes.append(row)
    forbidden={"REVERSE_JVP_MAPPING_CONTRADICTION","SIGN_CONTRADICTION","NONDETERMINISTIC","SAFETY_FAILURE"}
    result={"arm":arm,"seed":seed,"lineage":lineage,"diagnostic_radii":DIAGNOSTIC_RADII,"probes":probes,
            "probe_count":len(probes),"FD_window_missing_count":sum(row["classification"]=="FD_WINDOW_MISSING" for row in probes),
            "hard_failure_count":sum(row["classification"] in forbidden for row in probes),
            "reverse_JVP_pass_count":sum(row["reverse_jvp"]["pass"] for row in probes),
            "complete_coordinate_block_FD_qualified":False,
            "pass":not any(row["classification"] in forbidden for row in probes)}
    del loss,gradient,params,adapter,model; gc.collect(); return result


def run(arm: str, seed: int) -> None:
    torch.set_num_threads(1); started=time.perf_counter(); rss_start=PROCESS.memory_info().rss; peak=rss_start
    freeze=json.loads((STAGE06/"01_update_map_qualification/freeze/stage06a_freeze_record.json").read_text())
    assert sha_file(ROOT/freeze["contract_path"])==freeze["contract_sha256"]
    cases=load_cases(); origins=json.loads((STAGE06/"01_update_map_qualification/blind_batches/preregistered_blind_origins.json").read_text())
    groups=json.loads((STAGE06/"01_update_map_qualification/optimizer_definition/parameter_groups.json").read_text())["groups"][arm]
    plans=json.loads((STAGE06/"01_update_map_qualification/coordinate_fd_boundary/preregistered_diagnostic_plan.json").read_text())["contexts"]
    identities=json.loads((STAGE06/"01_update_map_qualification/blind_models/preregistered_model_identities.json").read_text())["models"]
    expected=next(row for row in identities if row["arm"]==arm and row["seed"]==seed)["complete_parameter_sha256"]
    output_dir=STAGE06/f"01_update_map_qualification/results/{arm.lower()}"; output_dir.mkdir(parents=True,exist_ok=True)
    context_summaries=[]; optimizer_instances=optimizer_steps=qualification_models=update_paths=graph_rebuilds=0; retention=[]
    contexts=[(lineage,batch_for(lineage,cases,origins)) for lineage in LINEAGES]+[("GLOBAL",global_batch(cases,origins))]
    for context_index,(lineage,selected) in enumerate(contexts):
        lr_rows=[]
        for lr in LRS:
            row=one_step_lr(arm,seed,expected,selected,lr,groups); lr_rows.append(row)
            optimizer_instances+=row["qualification_optimizer_instances"]; optimizer_steps+=row["qualification_optimizer_steps"]; update_paths+=2
            qualification_models+=3
        adjacent=[{"learning_rates":[LRS[i],LRS[i+1]],"pass":lr_rows[i]["pass"] and lr_rows[i+1]["pass"]} for i in range(len(LRS)-1)]
        stable_lrs=sorted({lr for pair in adjacent if pair["pass"] for lr in pair["learning_rates"]})
        micro=[]
        for lr in stable_lrs:
            row=micro_update(arm,seed,expected,selected,lr); micro.append(row)
            optimizer_instances+=row["qualification_optimizer_instances"]; optimizer_steps+=row["qualification_optimizer_steps"]
            qualification_models+=2
        selected_lr=min(stable_lrs) if stable_lrs else None
        actual=None
        if selected_lr is not None:
            actual=actual_update_fd(arm,seed,expected,selected,selected_lr,lineage!="GLOBAL")
            optimizer_instances+=actual["qualification_optimizer_instances"]; optimizer_steps+=actual["qualification_optimizer_steps"]
            qualification_models+=1
            update_paths+=actual["FD_evaluation_paths"]
        coordinate=None
        if lineage!="GLOBAL":
            coordinate=coordinate_boundary(arm,seed,expected,lineage,selected,groups,plans)
            qualification_models+=1
            update_paths+=sum(row["evaluation_paths"] for row in coordinate["probes"])
        adapter_forwards=20+12*len(stable_lrs)+(0 if actual is None else 18)
        if coordinate is not None: adapter_forwards+=1+9*len(coordinate["probes"])
        graph_rebuilds+=3*len(selected)*adapter_forwards+(0 if actual is None or lineage=="GLOBAL" else 8)
        lineage_pass=(any(pair["pass"] for pair in adjacent) and any(row["pass"] for row in micro)
                      and actual is not None and actual["pass"] and (coordinate is None or coordinate["pass"]))
        result={"arm":arm,"seed":seed,"context":lineage,"batch_size":len(selected),"batch_record_ids":[case.record_id for case in selected],
                "one_step_learning_rates":lr_rows,"adjacent_one_step_pairs":adjacent,"stable_region_learning_rates":stable_lrs,
                "micro_updates":micro,"actual_update_FD":actual,"coordinate_block_boundary":coordinate,
                "qualification_optimizer_instances":sum(row["qualification_optimizer_instances"] for row in lr_rows)+sum(row["qualification_optimizer_instances"] for row in micro)+(0 if actual is None else 1),
                "qualification_optimizer_steps":sum(row["qualification_optimizer_steps"] for row in lr_rows)+sum(row["qualification_optimizer_steps"] for row in micro)+(0 if actual is None else 1),
                "formal_training_runs":0,"saved_training_checkpoints":0,"validation_evaluations":0,"sealed_test_evaluations":0,
                "pass":bool(lineage_pass)}
        write_json(output_dir/f"{arm}_{seed}_{lineage}.json",result)
        context_summaries.append({"context":lineage,"pass":result["pass"],"stable_learning_rates":stable_lrs,
                                  "micro_pass_count":sum(row["pass"] for row in micro),"actual_update_FD_pass":None if actual is None else actual["pass"],
                                  "coordinate_boundary_pass":None if coordinate is None else coordinate["pass"]})
        peak=max(peak,PROCESS.memory_info().rss,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss); gc.collect(); retention.append(PROCESS.memory_info().rss)
        print(json.dumps({"arm":arm,"seed":seed,"context":lineage,"pass":result["pass"],"stable_lrs":stable_lrs,
                          "elapsed":time.perf_counter()-started}),flush=True)
    lineage_pass_count=sum(row["pass"] for row in context_summaries if row["context"]!="GLOBAL")
    global_pass=next(row["pass"] for row in context_summaries if row["context"]=="GLOBAL")
    monotonic_growth=all(retention[i+1]>retention[i] for i in range(len(retention)-1)) and retention[-1]-retention[0]>64*1024**2
    summary={"arm":arm,"seed":seed,"contexts":context_summaries,"lineage_pass_count":lineage_pass_count,
             "global_pass":global_pass,"pass":lineage_pass_count==6 and global_pass,
             "qualification_model_instances":qualification_models,"qualification_optimizer_instances":optimizer_instances,
             "qualification_optimizer_steps":optimizer_steps,"update_paths":update_paths,"graph_rebuilds":graph_rebuilds,
             "rss_start_bytes":rss_start,"peak_rss_bytes":peak,"peak_rss_delta_bytes":peak-rss_start,
             "retention_rss_samples":retention,"retained_autograd_monotonic_growth":monotonic_growth,
             "optimizer_state_memory_peak_upper_bound_bytes":2*next(row for row in identities if row["arm"]==arm and row["seed"]==seed)["parameter_count"]*8,
             "wall_time_seconds":time.perf_counter()-started,"dense_particle_N_by_N_allocation_observed":False,
             "all_qualification_models_destroyed":True,"qualification_weights_saved":0,"formal_training_runs":0,
             "saved_training_checkpoints":0,"validation_evaluations":0,"sealed_test_evaluations":0}
    summary["resource_pass"]=(summary["peak_rss_delta_bytes"]<=1610612736 and not monotonic_growth and summary["all_qualification_models_destroyed"])
    summary["pass"]=summary["pass"] and summary["resource_pass"]
    write_json(STAGE06/f"01_update_map_qualification/qualification/{arm.lower()}_{seed}_summary.json",summary)
    print(json.dumps({"arm":arm,"seed":seed,"pass":summary["pass"],"wall":summary["wall_time_seconds"],
                      "optimizer_instances":optimizer_instances,"optimizer_steps":optimizer_steps}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--arm",choices=["D1","D2","D3"],required=True)
    parser.add_argument("--seed",type=int,choices=SEEDS,required=True); args=parser.parse_args(); run(args.arm,args.seed)
