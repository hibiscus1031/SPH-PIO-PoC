"""Execute one frozen Stage 07D formal TRAIN_V2 run."""

from __future__ import annotations

import gc
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE07D = HERE.parents[1]
STAGE07 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE07C = STAGE07 / "04_training_protocol/stage07c"
REPORTS = STAGE07 / "08_reports"
MANIFESTS = STAGE07 / "09_manifests"
EXPECTED_PROTOCOL = "sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb"
SCALE = 1.7254786448147168
SCALE_HASH = "sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b"
TARGET_MANIFEST_HASH = "sha256:9672352d3a9ee0798d86a52a92151167c3bb83ddb38e5eef1e31e491fa1d4198"
FRESH_VALIDATION_MANIFEST_HASH = "sha256:925852d9d3738b6168ae3fd4fb36d09432cf4361a595b38666356035d77b9bf5"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20700711, 20700712, 20700713)]
TRAIN_LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08",
                  "HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03",
                  "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
ANCHOR_LINEAGES = TRAIN_LINEAGES[:6]
NEW_TRAIN_LINEAGES = TRAIN_LINEAGES[6:]
VALIDATION_LINEAGES = ["HET_S1_01", "HET_S2_02", "HET_S3_03", "HET_S4_03"]
VARIANTS = ["LOW", "MAIN"]
VALIDATION_BASELINE = 2.0611476240379423
RSS_LIMIT = 1610612736
CHECKPOINT_LIMIT = 10737418240
PROCESS = psutil.Process()


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


QPATH = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/qualification/run_stage05c_arm.py"
Q = import_path("stage07d_stage05c", QPATH)
Q.S_A = SCALE


def convert(value: Any) -> Any:
    if isinstance(value, np.bool_): return bool(value)
    if isinstance(value, np.integer): return int(value)
    if isinstance(value, np.floating): return float(value)
    if isinstance(value, np.ndarray): return value.tolist()
    raise TypeError(type(value).__name__)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=convert).encode()


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, default=convert) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.rstrip() + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, default=convert) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def rng_payload() -> dict[str, Any]:
    return {"torch": torch.get_rng_state(), "numpy": np.random.get_state(), "python": random.getstate()}


def restore_rng(value: dict[str, Any]) -> None:
    torch.set_rng_state(value["torch"])
    np.random.set_state(value["numpy"])
    random.setstate(value["python"])


def rng_digest(value: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(value["torch"].numpy().tobytes())
    h.update(repr(value["numpy"]).encode())
    h.update(repr(value["python"]).encode())
    return "sha256:" + h.hexdigest()


def nested_equal(left: Any, right: Any) -> bool:
    if torch.is_tensor(left) and torch.is_tensor(right): return torch.equal(left, right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(nested_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(nested_equal(a, b) for a, b in zip(left, right))
    return left == right


def directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def optimizer_finite(optimizer: torch.optim.Optimizer) -> bool:
    return all(not torch.is_tensor(value) or bool(torch.isfinite(value).all())
               for state in optimizer.state.values() for value in state.values())


def parameter_norm(parameters: list[torch.Tensor]) -> float:
    return float(torch.sqrt(sum(item.detach().square().sum() for item in parameters)))


def module_hashes(model: torch.nn.Module) -> dict[str, str]:
    result = {}
    for module_name, module in model.named_modules():
        digest = hashlib.sha256()
        count = 0
        for name, value in module.named_parameters(recurse=False):
            digest.update(name.encode())
            digest.update(Q.tensor_bytes(value))
            count += 1
        if count:
            result[module_name or "<root>"] = "sha256:" + digest.hexdigest()
    return result


def optimizer_memory_bytes(optimizer: torch.optim.Optimizer) -> int:
    return sum(value.numel() * value.element_size() for state in optimizer.state.values()
               for value in state.values() if torch.is_tensor(value))


def optimizer_moment_stats(optimizer: torch.optim.Optimizer) -> dict[str, Any]:
    exp_avg = [state["exp_avg"] for state in optimizer.state.values() if "exp_avg" in state]
    exp_avg_sq = [state["exp_avg_sq"] for state in optimizer.state.values() if "exp_avg_sq" in state]
    steps = [int(state["step"].item()) for state in optimizer.state.values() if "step" in state]
    return {"parameter_state_count": len(optimizer.state), "step_min": min(steps), "step_max": max(steps),
            "exp_avg_L2": float(torch.sqrt(sum(x.square().sum() for x in exp_avg))),
            "exp_avg_sq_L2": float(torch.sqrt(sum(x.square().sum() for x in exp_avg_sq)))}


def fresh(arm: str, seed: int, expected: str) -> tuple[torch.nn.Module, Any]:
    prior = torch.get_default_dtype(); torch.set_default_dtype(torch.float32)
    try:
        torch.manual_seed(seed); model = Q.ARMS[arm]().to(dtype=torch.float64, device="cpu")
    finally:
        torch.set_default_dtype(prior)
    if Q.parameter_hash(model) != expected: raise RuntimeError("fresh initialization parameter identity mismatch")
    return model, Q.DefectAdapter(arm, model)


def make_optimizer(adapter: Any) -> torch.optim.AdamW:
    return torch.optim.AdamW(adapter.parameters(), lr=1e-5, betas=(.9, .999), eps=1e-12, weight_decay=0, amsgrad=False)


def make_scheduler(optimizer: torch.optim.Optimizer) -> torch.optim.lr_scheduler.LambdaLR:
    values = json.loads((STAGE07C / "optimizer_schedule/formal_scheduler_values.json").read_text())
    factors = [row["factor"] for row in values["rows"]]
    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda update: factors[min(update, 1500)])


def sealed_denial() -> bool:
    audit = json.loads((STAGE07C / "sealed_test_preflight/original_sealed_test_denial.json").read_text())
    return bool(audit["pass"] and all(value == 0 for value in audit["decode_counts"].values()))


def verify_historical() -> dict[str, Any]:
    freeze = json.loads((MANIFESTS / "stage07c_input_freeze_manifest.json").read_text())
    groups = {"historical_inputs": freeze["historical_inputs"], "stage07c_artifacts": list(freeze["artifacts"].values())}
    changed = []
    for group, rows in groups.items():
        for row in rows:
            path = ROOT / row["path"]
            if not path.is_file() or sha_file(path) != row["sha256"]:
                changed.append({"group": group, "path": row["path"]})
    return {"counts": {key: len(value) for key, value in groups.items()}, "changed": changed, "pass": not changed}


def case_from_row(row: dict[str, Any]) -> Any:
    path = ROOT / row["path"]
    if sha_file(path) != row["sha256"] or row["scale_v2_hash"] != SCALE_HASH: raise RuntimeError(f"case identity mismatch: {row['record_id']}")
    with np.load(path, allow_pickle=False) as archive: a = {key: archive[key] for key in archive.files}
    tensor = lambda value: torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)
    return Q.Case(row["record_id"], row["lineage"], row["variant"], row["origin"], torch.from_numpy(a["frames"]).to(torch.int64),
        tensor(a["physical_times"]), tensor(a["x"]), tensor(a["velocity"]), tensor(a["density"]), tensor(a["material_labels"]),
        tensor(a["mass"]), tensor(a["smoothing"]), tensor(a["history_tokens"]), tensor(a["source_start"]),
        tensor(a["source_midpoint"]), tensor(a["v0_accepted"]), tensor(a["a_cons"]))


def load_case_sets() -> tuple[dict[str, Any], list[Any], dict[str, Any]]:
    schedule = json.loads((STAGE07C / "train_v2_batch_schedule/formal_train_v2_batch_schedule.json").read_text())
    tm = json.loads((STAGE07C / "train_v2_batch_schedule/train_case_cache_manifest.json").read_text())
    vm = json.loads((STAGE07C / "validation_target_construction/validation_case_cache_manifest.json").read_text())
    if not schedule["pass"] or schedule["record_count"] != 896 or tm["case_count"] != 896: raise RuntimeError("TRAIN_V2 inventory is not 896/896")
    if vm["case_count"] != 256: raise RuntimeError("FRESH_VALIDATION_V2 inventory is not 256/256")
    cases = {row["record_id"]: case_from_row(row) for row in tm["cases"]}; validation = [case_from_row(row) for row in vm["cases"]]
    if {c.lineage for c in cases.values()} != set(TRAIN_LINEAGES): raise RuntimeError("TRAIN lineage mismatch")
    if {c.lineage for c in validation} != set(VALIDATION_LINEAGES): raise RuntimeError("fresh validation lineage mismatch")
    batches = {row["base_batch_id"]: [cases[item["record_id"]] for item in row["records"]] for row in schedule["base_batches"]}
    if len(batches) != 8 or any(len(batch) != 112 for batch in batches.values()): raise RuntimeError("8x112 batch mismatch")
    return cases, validation, {"schedule": schedule, "batches": batches,
        "manifest": {"record_count": 896, "validation_record_count": 256, "pass": True}}


def predict_case(adapter: Any, case: Any) -> dict[str, Any]:
    start = case.state(3).with_eos()
    history = adapter.history(case)
    g0 = Q.build_reciprocal_graph(start)
    t0 = Q.build_node_token(start, g0)
    kwargs: dict[str, Any] = {"stage": "start"}
    if history is not None: kwargs["history"] = history
    p0 = adapter.core.evaluate(t0, start, g0, **kwargs)
    x1, a1, r1 = Q.rhs(start, g0, case.source_start)
    a1 = a1 + p0.acceleration
    mid = Q.DynamicParticleState(
        start.x_unwrapped + .5 * Q.DT * x1, start.velocity + .5 * Q.DT * a1,
        start.density + .5 * Q.DT * r1, torch.empty_like(start.pressure), start.mass,
        start.smoothing_length, start.material_labels, start.physical_time + .5 * Q.DT,
        start.accepted_step_index,
    ).with_eos()
    gm = Q.build_reciprocal_graph(mid)
    tm = Q.build_node_token(mid, gm)
    kwargs = {"stage": "midpoint"}
    if history is not None: kwargs["history"] = history
    pm = adapter.core.evaluate(tm, mid, gm, **kwargs)
    x2, a2, r2 = Q.rhs(mid, gm, case.source_mid)
    a2 = a2 + pm.acceleration
    accepted = Q.DynamicParticleState(
        start.x_unwrapped + Q.DT * x2, start.velocity + Q.DT * a2,
        start.density + Q.DT * r2, torch.empty_like(start.pressure), start.mass,
        start.smoothing_length, start.material_labels, start.physical_time + Q.DT,
        start.accepted_step_index + 1,
    ).with_eos()
    ga = Q.build_reciprocal_graph(accepted)
    commit_count = 0
    if history is not None:
        token = Q.build_node_token(accepted, ga)
        hidden = adapter.core.accepted_hidden(token, history=history)
        history = history.commit(token, hidden, accepted.physical_time)
        commit_count = history.commit_count
    aeff = (accepted.velocity - case.v0) / Q.DT
    loss = ((aeff - case.target) / Q.S_A).square().mean()
    acceleration_error = aeff - case.target
    coefficients = torch.cat((p0.alpha.reshape(-1), p0.beta.reshape(-1), pm.alpha.reshape(-1), pm.beta.reshape(-1)))
    hidden = torch.cat((p0.particle_hidden.reshape(-1), pm.particle_hidden.reshape(-1)))
    finite = bool(torch.isfinite(loss) and torch.isfinite(coefficients).all() and torch.isfinite(p0.particle_hidden).all()
                  and torch.isfinite(pm.particle_hidden).all() and torch.isfinite(accepted.velocity).all()
                  and torch.isfinite(accepted.density).all())
    residual = max(Q.force_residual(start, p0), Q.force_residual(mid, pm))
    return {
        "record_id": case.record_id, "lineage": case.lineage, "variant": case.variant, "origin": case.origin,
        "loss": float(loss), "acceleration_error_sq_sum": float(acceleration_error.square().sum()),
        "zero_acceleration_sq_sum": float(case.target.square().sum()), "acceleration_count": acceleration_error.numel(),
        "density_min": float(torch.stack((start.density.min(), mid.density.min(), accepted.density.min())).min()),
        "coefficient_sq_sum": float(coefficients.square().sum()), "coefficient_count": coefficients.numel(),
        "coefficient_saturated": int((coefficients.abs() >= .99 * .05).sum()),
        "hidden_sq_sum": float(hidden.square().sum()), "hidden_count": hidden.numel(), "hidden_abs_max": float(hidden.abs().max()),
        "correction_force_residual": residual, "history_commit_count": commit_count, "midpoint_commit_count": 0,
        "finite": finite,
    }


def summarize_rows(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    def q_for(selected: list[dict[str, Any]]) -> float:
        return math.sqrt(sum(row["loss"] for row in selected) / len(selected))
    lineages = TRAIN_LINEAGES if role == "TRAIN" else VALIDATION_LINEAGES
    max_row = max(rows, key=lambda row: (math.sqrt(row["loss"]), row["record_id"]))
    acceleration_sum = sum(row["acceleration_error_sq_sum"] for row in rows); acceleration_count = sum(row["acceleration_count"] for row in rows)
    zero_sum = sum(row["zero_acceleration_sq_sum"] for row in rows)
    coeff_sum = sum(row["coefficient_sq_sum"] for row in rows); coeff_count = sum(row["coefficient_count"] for row in rows)
    hidden_sum = sum(row["hidden_sq_sum"] for row in rows); hidden_count = sum(row["hidden_count"] for row in rows)
    raw_by_lineage = {lineage: math.sqrt(sum(row["acceleration_error_sq_sum"] for row in rows if row["lineage"] == lineage) /
                                         sum(row["acceleration_count"] for row in rows if row["lineage"] == lineage)) for lineage in lineages}
    zero_by_lineage = {lineage: math.sqrt(sum(row["zero_acceleration_sq_sum"] for row in rows if row["lineage"] == lineage) /
                                          sum(row["acceleration_count"] for row in rows if row["lineage"] == lineage)) for lineage in lineages}
    origin_q = {lineage: sorted(math.sqrt(row["loss"]) for row in rows if row["lineage"] == lineage) for lineage in lineages}
    per_lineage_q = {lineage: q_for([row for row in rows if row["lineage"] == lineage]) for lineage in lineages}
    return {
        "role": role, "record_count": len(rows), "global_balanced_L_def": sum(row["loss"] for row in rows) / len(rows),
        "global_balanced_Q_def": q_for(rows),
        "per_lineage_Q_def": per_lineage_q,
        "per_variant_Q_def": {variant: q_for([row for row in rows if row["variant"] == variant]) for variant in VARIANTS},
        "maximum_origin": {"record_id": max_row["record_id"], "Q_def": math.sqrt(max_row["loss"])},
        "raw_acceleration_RMSE": math.sqrt(acceleration_sum / acceleration_count),
        "zero_correction_raw_acceleration_RMSE": math.sqrt(zero_sum / acceleration_count),
        "relative_reduction_vs_zero": 1.0 - math.sqrt(acceleration_sum / acceleration_count) / math.sqrt(zero_sum / acceleration_count),
        "per_lineage_raw_acceleration_RMSE": raw_by_lineage,
        "per_lineage_zero_RMSE": zero_by_lineage,
        "per_lineage_relative_reduction": {lineage: 1.0 - raw_by_lineage[lineage] / zero_by_lineage[lineage] for lineage in lineages},
        "per_lineage_origin_Q": {lineage: {"median": float(np.median(values)), "p90": float(np.quantile(values, .9)), "max": max(values)} for lineage, values in origin_q.items()},
        "anchor_mean_Q_def": float(np.mean([per_lineage_q[x] for x in ANCHOR_LINEAGES])) if role == "TRAIN" else None,
        "new_TRAIN_mean_Q_def": float(np.mean([per_lineage_q[x] for x in NEW_TRAIN_LINEAGES])) if role == "TRAIN" else None,
        "LCDF_08_Q_def": per_lineage_q.get("LCDF_08"),
        "coefficient_RMS": math.sqrt(coeff_sum / coeff_count),
        "coefficient_saturation_fraction": sum(row["coefficient_saturated"] for row in rows) / coeff_count,
        "hidden_RMS": math.sqrt(hidden_sum / hidden_count), "hidden_abs_max": max(row["hidden_abs_max"] for row in rows),
        "correction_force_residual_max": max(row["correction_force_residual"] for row in rows),
        "density_min": min(row["density_min"] for row in rows),
        "finite": all(row["finite"] for row in rows),
        "history_semantics": all(row["midpoint_commit_count"] == 0 and row["history_commit_count"] in (0, 1) for row in rows),
        "safe": all(row["finite"] and row["density_min"] > 0 and row["correction_force_residual"] <= 1e-10 for row in rows),
    }


def evaluate(adapter: Any, cases: list[Any], role: str) -> dict[str, Any]:
    saved_rng = rng_payload()
    prior_mode = adapter.core.training
    adapter.core.eval()
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
        rows = [predict_case(adapter, case) for case in cases]
    adapter.core.train(prior_mode)
    restore_rng(saved_rng)
    return summarize_rows(rows, role)


def checkpoint_path(run_id: str, update: int) -> Path:
    return STAGE07D / "checkpoints" / f"{run_id}_update{update:04d}.pt"


def exact_next_forward(adapter: Any, cases: list[Any]) -> float:
    mode = adapter.core.training
    adapter.core.train()
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH): value = float(adapter(cases))
    adapter.core.train(mode)
    return value


def save_and_verify_checkpoint(run: dict[str, Any], model: Any, adapter: Any, optimizer: Any, scheduler: Any,
                               update: int, batch_state: dict[str, Any], train_metrics: dict[str, Any],
                               validation_metrics: dict[str, Any], next_cases: list[Any]) -> dict[str, Any]:
    path = checkpoint_path(run["run_id"], update)
    checkpoint_rng = rng_payload()
    parameter_sha = Q.parameter_hash(model)
    payload = {
        "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
        "RNG": checkpoint_rng, "update": update, "protocol_hash": EXPECTED_PROTOCOL, "run_id": run["run_id"],
        "run_identity": run["run_identity_sha256"], "architecture_hash": run["architecture_sha256"],
        "parameter_hash": parameter_sha, "batch_order_state": batch_state, "TRAIN_metrics": train_metrics,
        "fresh_validation_metrics": validation_metrics, "backend": "CPU_FLOAT64_SDPBackend.MATH",
        "scale_hash": SCALE_HASH, "target_manifest_hash": TARGET_MANIFEST_HASH,
        "fresh_validation_manifest_hash": FRESH_VALIDATION_MANIFEST_HASH,
    }
    tmp = path.with_suffix(".pt.tmp")
    torch.save(payload, tmp)
    os.replace(tmp, path)
    file_sha = sha_file(path)
    restore_rng(checkpoint_rng)
    original_next = exact_next_forward(adapter, next_cases)
    restore_rng(checkpoint_rng)
    re_model, re_adapter = fresh(run["arm"], run["formal_seed"], run["initial_parameter_sha256"])
    re_optimizer = make_optimizer(re_adapter)
    re_scheduler = make_scheduler(re_optimizer)
    loaded = torch.load(path, map_location="cpu", weights_only=False)
    re_model.load_state_dict(loaded["model"])
    re_optimizer.load_state_dict(loaded["optimizer"])
    re_scheduler.load_state_dict(loaded["scheduler"])
    restore_rng(loaded["RNG"])
    reloaded_next = exact_next_forward(re_adapter, next_cases)
    equality = {
        "file_hash": sha_file(path) == file_sha,
        "parameter_hash": Q.parameter_hash(re_model) == parameter_sha == loaded["parameter_hash"],
        "model_state_bitwise": nested_equal(model.state_dict(), re_model.state_dict()),
        "optimizer_state_exact": nested_equal(optimizer.state_dict(), re_optimizer.state_dict()),
        "scheduler_state_exact": nested_equal(scheduler.state_dict(), re_scheduler.state_dict()),
        "rng_identity": rng_digest(checkpoint_rng) == rng_digest(loaded["RNG"]),
        "next_forward_bitwise": original_next == reloaded_next,
        "protocol_identity": loaded["protocol_hash"] == EXPECTED_PROTOCOL,
        "run_identity": loaded["run_id"] == run["run_id"] and loaded["run_identity"] == run["run_identity_sha256"],
        "architecture_identity": loaded["architecture_hash"] == run["architecture_sha256"],
        "backend_identity": loaded["backend"] == "CPU_FLOAT64_SDPBackend.MATH",
        "update_identity": loaded["update"] == update,
        "batch_order_identity": loaded["batch_order_state"] == batch_state,
        "scale_identity": loaded["scale_hash"] == SCALE_HASH,
        "target_manifest_identity": loaded["target_manifest_hash"] == TARGET_MANIFEST_HASH,
        "fresh_validation_manifest_identity": loaded["fresh_validation_manifest_hash"] == FRESH_VALIDATION_MANIFEST_HASH,
    }
    restore_rng(checkpoint_rng)
    row = {"run_id": run["run_id"], "update": update, "path": str(path.relative_to(ROOT)),
           "checkpoint_sha256": file_sha, "parameter_sha256": parameter_sha, "bytes": path.stat().st_size,
           "equality": equality, "pass": all(equality.values())}
    write_json(STAGE07D / "checkpoint_integrity" / f"{run['run_id']}_update{update:04d}.json", row)
    if not row["pass"]: raise RuntimeError(f"checkpoint/reload mismatch at {run['run_id']} update {update}")
    del re_model, re_adapter, re_optimizer, re_scheduler, loaded
    gc.collect()
    return row


def load_checkpoint_for_run(run: dict[str, Any], path: Path) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    model, adapter = fresh(run["arm"], run["formal_seed"], run["initial_parameter_sha256"])
    optimizer = make_optimizer(adapter); scheduler = make_scheduler(optimizer)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload["protocol_hash"] != EXPECTED_PROTOCOL or payload["run_id"] != run["run_id"] or payload["run_identity"] != run["run_identity_sha256"]:
        raise RuntimeError("resume checkpoint identity mismatch")
    model.load_state_dict(payload["model"]); optimizer.load_state_dict(payload["optimizer"]); scheduler.load_state_dict(payload["scheduler"])
    restore_rng(payload["RNG"])
    if Q.parameter_hash(model) != payload["parameter_hash"]: raise RuntimeError("resume parameter hash mismatch")
    return model, adapter, optimizer, scheduler, payload


def structural_audit(run: dict[str, Any], model: Any, adapter: Any, case: Any, checkpoint_integrity: bool) -> dict[str, Any]:
    model.eval()
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
        state, history, output, graph, token = adapter.start_audit(case)
        start_audit = Q.audit_stage(arm=run["arm"], model=model, state=state, history=history, stage="start",
                                      reference_output=output, reference_graph=graph, reference_token=token)
        x1, a1, r1 = Q.rhs(state, graph, case.source_start); a1 = a1 + output.acceleration
        midpoint = Q.DynamicParticleState(
            state.x_unwrapped + .5 * Q.DT * x1, state.velocity + .5 * Q.DT * a1,
            state.density + .5 * Q.DT * r1, torch.empty_like(state.pressure), state.mass,
            state.smoothing_length, state.material_labels, state.physical_time + .5 * Q.DT,
            state.accepted_step_index,
        ).with_eos()
        mid_graph = Q.build_reciprocal_graph(midpoint); mid_token = Q.build_node_token(midpoint, mid_graph)
        kwargs: dict[str, Any] = {"stage": "midpoint"}
        if history is not None: kwargs["history"] = history
        mid_output = model.evaluate(mid_token, midpoint, mid_graph, **kwargs)
        midpoint_audit = Q.audit_stage(arm=run["arm"], model=model, state=midpoint, history=history, stage="midpoint",
                                         reference_output=mid_output, reference_graph=mid_graph, reference_token=mid_token)
        _, trace = adapter.one(case)
    history_pass = trace["midpoint_commit_count"] == 0 and trace["history_commit_count"] == (0 if run["arm"] == "D1" else 1)
    gates = {"start": start_audit["pass"], "midpoint": midpoint_audit["pass"], "accepted_history_commit": history_pass,
             "midpoint_not_committed": trace["midpoint_commit_count"] == 0, "checkpoint_reload_identity": checkpoint_integrity}
    return {"run_id": run["run_id"], "start": start_audit, "midpoint": midpoint_audit,
            "history": {"history_commit_count": trace["history_commit_count"], "midpoint_commit_count": trace["midpoint_commit_count"]},
            "gates": gates, "pass": all(gates.values())}


def selected_audit(run: dict[str, Any], selected_path: Path, all_train: list[Any],
                   validation_cases: list[Any], checkpoint_ok: bool) -> dict[str, Any]:
    model, adapter, optimizer, scheduler, payload = load_checkpoint_for_run(run, selected_path)
    train_first = evaluate(adapter, all_train, "TRAIN")
    validation_first = evaluate(adapter, validation_cases, "VALIDATION")
    train_second = evaluate(adapter, all_train, "TRAIN")
    validation_second = evaluate(adapter, validation_cases, "VALIDATION")
    deterministic = canonical(train_first) == canonical(train_second) and canonical(validation_first) == canonical(validation_second)
    structure = structural_audit(run, model, adapter, all_train[0], checkpoint_ok)
    gates = {
        "A_numerical_safety": train_first["safe"] and validation_first["safe"] and deterministic,
        "B_train_fit": train_first["global_balanced_Q_def"] <= .50,
        "C_validation_transfer": validation_first["global_balanced_Q_def"] <= .90,
        "D_HET_S1_01": validation_first["per_lineage_Q_def"]["HET_S1_01"] <= 1.0,
        "D_HET_S2_02": validation_first["per_lineage_Q_def"]["HET_S2_02"] <= 1.0,
        "D_HET_S3_03": validation_first["per_lineage_Q_def"]["HET_S3_03"] <= 1.0,
        "D_HET_S4_03": validation_first["per_lineage_Q_def"]["HET_S4_03"] <= 1.0,
        "E_structure": structure["pass"],
    }
    result = {"run_id": run["run_id"], "selected_update": payload["update"], "selected_checkpoint": str(selected_path.relative_to(ROOT)),
              "selected_checkpoint_sha256": sha_file(selected_path), "parameter_sha256": payload["parameter_hash"],
              "TRAIN": train_first, "VALIDATION": validation_first, "deterministic_repeat": deterministic,
              "structure": structure, "frozen_gates_A_E": gates, "seed_pass": all(gates.values()),
              "validation_zero_baseline": VALIDATION_BASELINE,
              "Delta_Q_val": validation_first["global_balanced_Q_def"] - VALIDATION_BASELINE,
              "relative_validation_reduction": 1.0 - validation_first["global_balanced_Q_def"] / VALIDATION_BASELINE,
              "baseline_diagnostic": "validation improvement" if validation_first["global_balanced_Q_def"] < VALIDATION_BASELINE else
                                     "frozen transfer gate PASS, but no improvement over zero correction baseline" if gates["C_validation_transfer"] else
                                     "frozen transfer gate FAIL and no improvement over zero correction baseline"}
    write_json(STAGE07D / "postfit_structure" / f"{run['run_id']}.json", structure)
    write_json(STAGE07D / "determinism" / f"{run['run_id']}.json", {"run_id": run["run_id"], "repeat_exact": deterministic,
               "train_first_sha256": sha_bytes(canonical(train_first)), "train_second_sha256": sha_bytes(canonical(train_second)),
               "validation_first_sha256": sha_bytes(canonical(validation_first)), "validation_second_sha256": sha_bytes(canonical(validation_second))})
    del model, adapter, optimizer, scheduler, payload
    gc.collect()
    return result


def run_one(run: dict[str, Any], run_index: int, all_train: list[Any],
            validation_cases: list[Any], schedule_data: dict[str, Any],
            campaign_peak: int) -> tuple[dict[str, Any], int]:
    run_id = run["run_id"]
    run_dir = STAGE07D / "runs" / run_id
    train_history_path = STAGE07D / "training_histories" / f"{run_id}.jsonl"
    validation_history_path = STAGE07D / "validation_histories" / f"{run_id}.jsonl"
    summary_path = run_dir / "run_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        return summary, max(campaign_peak, summary["peak_rss_bytes"])
    if train_history_path.exists() or validation_history_path.exists():
        raise RuntimeError(f"partial run requires explicit checkpoint resume: {run_id}")
    start_denied = sealed_denial()
    start_access = {"run_id": run_id, "phase": "start", "sealed_access_denied": start_denied,
                    "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
                    "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0, "sealed_test_evaluations": 0}
    write_json(STAGE07D / "access_control" / f"{run_id}_start.json", start_access)
    if not start_denied: raise RuntimeError("sealed denial failed")
    random.seed(run["formal_seed"]); np.random.seed(run["formal_seed"])
    model, adapter = fresh(run["arm"], run["formal_seed"], run["initial_parameter_sha256"])
    optimizer = make_optimizer(adapter); scheduler = make_scheduler(optimizer)
    updates = [row for row in schedule_data["schedule"]["update_schedule"] if row["run_id"] == run_id]
    batches = schedule_data["batches"]
    initial_hash = Q.parameter_hash(model)
    started = time.perf_counter(); peak_rss = PROCESS.memory_info().rss; graph_start = adapter.graph_rebuild_count
    train0 = evaluate(adapter, all_train, "TRAIN")
    val0 = evaluate(adapter, validation_cases, "VALIDATION")
    update0 = {"run_id": run_id, "update": 0, "initial_parameter_sha256": initial_hash,
               "model_parameter_sha256": initial_hash, "module_parameter_hashes": module_hashes(model),
               "architecture_sha256": run["architecture_sha256"], "seed": run["formal_seed"],
               "protocol_sha256": EXPECTED_PROTOCOL, "backend": "CPU_FLOAT64_SDPBackend.MATH", "TRAIN": train0,
               "VALIDATION": val0, "RNG_sha256": rng_digest(rng_payload()), "eligible_for_selection": False}
    write_json(run_dir / "update_0000.json", update0)
    append_jsonl(validation_history_path, {"update": 0, "TRAIN": train0, "VALIDATION": val0, "eligible_for_selection": False})
    first_row = updates[0]; first_batch = batches[first_row["base_batch_id"]]
    checkpoint_rows = [save_and_verify_checkpoint(run, model, adapter, optimizer, scheduler, 0,
                       {"completed_update": 0, "next_update": 1, "next_base_batch_id": first_row["base_batch_id"]}, train0, val0, first_batch)]
    update0["update_0_checkpoint"] = {key: checkpoint_rows[0][key] for key in
                                      ("path", "checkpoint_sha256", "parameter_sha256", "bytes", "pass")}
    write_json(run_dir / "update_0000.json", update0)
    best_q = math.inf; best_update = None; best_checkpoint = None
    patience_best = math.inf; patience_anchor = 320
    ledger = sha_bytes(canonical({"run_id": run_id, "update": 0, "parameter_hash": initial_hash}))
    terminal_reason = "MAX_UPDATES"
    terminal_update = 0
    for row in updates:
        update = row["update"]; batch_id = row["base_batch_id"]; cases = batches[batch_id]
        batch_spec = next(item for item in schedule_data["schedule"]["base_batches"] if item["base_batch_id"] == batch_id)
        model.train(); optimizer.zero_grad(set_to_none=True)
        before = [parameter.detach().clone() for parameter in adapter.parameters()]
        lr_used = float(optimizer.param_groups[0]["lr"])
        with sdpa_kernel(SDPBackend.MATH): loss = adapter(cases)
        loss_value = float(loss.detach())
        if not math.isfinite(loss_value) or not adapter.last_trace["safe"]:
            raise RuntimeError(f"FORMAL_RUN_NUMERICAL_FAILURE {run_id} update {update}: unsafe forward")
        loss.backward()
        parameters = list(adapter.parameters())
        gradients = [parameter.grad for parameter in parameters]
        if any(gradient is None or not bool(torch.isfinite(gradient).all()) for gradient in gradients):
            raise RuntimeError(f"FORMAL_RUN_NUMERICAL_FAILURE {run_id} update {update}: nonfinite gradient")
        gradient_norm = float(torch.sqrt(sum(gradient.detach().square().sum() for gradient in gradients if gradient is not None)))
        clip_factor = min(1.0, 1.0 / max(gradient_norm, 1e-30))
        returned_norm = float(torch.nn.utils.clip_grad_norm_(parameters, 1.0))
        optimizer.step()
        scheduler.step()
        if not optimizer_finite(optimizer) or any(not bool(torch.isfinite(parameter).all()) for parameter in parameters):
            raise RuntimeError(f"FORMAL_RUN_NUMERICAL_FAILURE {run_id} update {update}: optimizer corruption")
        update_norm = float(torch.sqrt(sum((parameter.detach() - prior).square().sum() for parameter, prior in zip(parameters, before))))
        parameter_l2 = parameter_norm(parameters)
        parameter_sha = Q.parameter_hash(model)
        ledger = sha_bytes(canonical({"previous": ledger, "update": update, "batch_id": batch_id, "parameter_sha256": parameter_sha}))
        history_row = {
            "run_id": run_id, "update": update, "epoch": row["epoch"], "base_batch_id": batch_id,
            "record_ids": [item["record_id"] for item in batch_spec["records"]],
            "lineage_variant_origins": [{key: item[key] for key in ("lineage", "variant", "origin")} for item in batch_spec["records"]],
            "batch_order_sha256": batch_spec["record_ids_sha256"], "L_def": loss_value, "Q_def": math.sqrt(loss_value),
            "gradient_norm": gradient_norm, "clip_factor": clip_factor, "clip_returned_preclip_norm": returned_norm,
            "learning_rate_used": lr_used, "learning_rate_after_scheduler": float(optimizer.param_groups[0]["lr"]),
            "parameter_norm": parameter_l2, "update_norm": update_norm, "parameter_sha256": parameter_sha,
            "optimizer_moments": optimizer_moment_stats(optimizer), "rng_ledger_sha256": ledger, "finite": True,
        }
        append_jsonl(train_history_path, history_row)
        del loss, gradients, before
        terminal_update = update
        peak_rss = max(peak_rss, PROCESS.memory_info().rss); campaign_peak = max(campaign_peak, peak_rss)
        if peak_rss > RSS_LIMIT: raise RuntimeError(f"resource RSS gate exceeded in {run_id}")
        if update % 20 == 0:
            train_metrics = evaluate(adapter, all_train, "TRAIN")
            validation_metrics = evaluate(adapter, validation_cases, "VALIDATION")
            eval_row = {"run_id": run_id, "update": update, "TRAIN": train_metrics, "VALIDATION": validation_metrics,
                        "eligible_for_selection": update >= 320, "optimizer_unchanged_during_evaluation": True,
                        "scheduler_unchanged_during_evaluation": True, "RNG_restored": True}
            append_jsonl(validation_history_path, eval_row)
            next_index = min(update, len(updates) - 1)
            next_row = updates[next_index]
            checkpoint = save_and_verify_checkpoint(run, model, adapter, optimizer, scheduler, update,
                {"completed_update": update, "next_update": update + 1 if update < 1500 else None,
                 "next_base_batch_id": next_row["base_batch_id"] if update < 1500 else None},
                train_metrics, validation_metrics, batches[next_row["base_batch_id"]])
            checkpoint_rows.append(checkpoint)
            q_val = validation_metrics["global_balanced_Q_def"]
            if update >= 320 and q_val < best_q:
                best_q = q_val; best_update = update; best_checkpoint = checkpoint_path(run_id, update)
            if update == 320:
                patience_best = q_val; patience_anchor = update
            elif update > 320 and q_val < patience_best - 1e-5:
                patience_best = q_val; patience_anchor = update
            if update >= 320 and update - patience_anchor >= 300:
                terminal_reason = "EARLY_STOPPED"
                break
            print(json.dumps({"event": "evaluation", "run_id": run_id, "update": update,
                              "train_Q": train_metrics["global_balanced_Q_def"], "validation_Q": q_val,
                              "best_update": best_update, "peak_rss": peak_rss}, sort_keys=True), flush=True)
        gc.collect()
    if best_checkpoint is None or best_update is None:
        raise RuntimeError(f"no selectable checkpoint for {run_id}")
    selected_path = STAGE07D / "checkpoint_selection" / f"{run_id}_selected.pt"
    shutil.copy2(best_checkpoint, selected_path)
    selected_sha = sha_file(selected_path)
    selected_integrity = next(row for row in checkpoint_rows if row["update"] == best_update)
    audit = selected_audit(run, selected_path, all_train, validation_cases, selected_integrity["pass"])
    end_denied = sealed_denial()
    end_access = {"run_id": run_id, "phase": "end", "sealed_access_denied": end_denied,
                  "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
                  "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0, "sealed_test_evaluations": 0}
    write_json(STAGE07D / "access_control" / f"{run_id}_end.json", end_access)
    if not end_denied: raise RuntimeError("sealed denial failed at run end")
    checkpoint_storage = directory_bytes(STAGE07D / "checkpoints") + directory_bytes(STAGE07D / "checkpoint_selection")
    if checkpoint_storage > CHECKPOINT_LIMIT: raise RuntimeError("checkpoint storage gate exceeded")
    summary = {
        "run_id": run_id, "arm": run["arm"], "formal_seed": run["formal_seed"], "terminal_reason": terminal_reason,
        "terminal_update": terminal_update, "selected_update": best_update, "selected_checkpoint": str(selected_path.relative_to(ROOT)),
        "selected_checkpoint_sha256": selected_sha, "selected_parameter_sha256": audit["parameter_sha256"],
        "minimum_validation_Q_def": best_q, "selected_metrics": audit, "update_count": terminal_update,
        "optimizer_step_count": terminal_update, "formal_parameter_update_count": terminal_update,
        "wall_time_seconds": time.perf_counter() - started, "peak_rss_bytes": peak_rss,
        "checkpoint_storage_bytes_campaign": checkpoint_storage, "optimizer_memory_bytes": optimizer_memory_bytes(optimizer),
        "graph_rebuilds": adapter.graph_rebuild_count - graph_start,
        "validation_evaluation_count": terminal_update // 20 + 3,
        "checkpoint_count": len(checkpoint_rows), "checkpoint_integrity_pass": all(row["pass"] for row in checkpoint_rows),
        "sealed_decode_counts": {"sealed_formula_decode_count": 0, "sealed_state_decode_count": 0,
                                 "sealed_source_decode_count": 0, "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0},
        "sealed_test_evaluations": 0, "retry_resume_history": [], "formal_run_terminal": True,
        "seed_pass": audit["seed_pass"],
    }
    write_json(summary_path, summary)
    write_json(STAGE07D / "checkpoint_selection" / f"{run_id}_selection.json", {
        "run_id": run_id, "selection_metric": "FRESH_VALIDATION_V2.global_balanced_Q_def_v2", "minimum_selectable_update": 320,
        "tie_break": "earlier_update", "selected_update": best_update, "selected_Q_def": best_q,
        "selected_checkpoint": str(selected_path.relative_to(ROOT)), "selected_checkpoint_sha256": selected_sha,
        "sealed_test_participated": False,
    })
    print(json.dumps({"event": "run_terminal", "run_id": run_id, "terminal_reason": terminal_reason,
                      "terminal_update": terminal_update, "selected_update": best_update, "seed_pass": audit["seed_pass"]}, sort_keys=True), flush=True)
    del model, adapter, optimizer, scheduler
    gc.collect()
    return summary, campaign_peak


def main(run_id: str) -> None:
    torch.set_num_threads(1)
    torch.set_default_dtype(torch.float64)
    if run_id not in RUN_IDS: raise SystemExit("unauthorized run identity")
    freeze = json.loads((STAGE07D / "freeze/stage07d_input_freeze_record.json").read_text())
    if not freeze["pass"] or freeze["protocol_sha256"] != EXPECTED_PROTOCOL: raise SystemExit("Stage07D freeze is not ready")
    protocol_manifest = json.loads((STAGE07C / "manifests/stage07c_protocol_manifest.json").read_text())
    if sha_file(ROOT / protocol_manifest["protocol_path"]) != EXPECTED_PROTOCOL: raise SystemExit("protocol identity changed")
    if not verify_historical()["pass"]: raise SystemExit("historical identity changed")
    cases, validation_cases, schedule_data = load_case_sets()
    all_train = [cases[row["record_id"]] for row in schedule_data["schedule"]["assignments"]]
    runs = json.loads((STAGE07C / "model_seed_schedule/formal_model_seed_schedule.json").read_text())["runs"]
    if [row["run_id"] for row in runs] != RUN_IDS: raise RuntimeError("run inventory order mismatch")
    run = next(row for row in runs if row["run_id"] == run_id)
    if run["protocol_sha256"] != EXPECTED_PROTOCOL or run["scale_hash"] != SCALE_HASH or run["target_manifest_sha256"] != TARGET_MANIFEST_HASH:
        raise RuntimeError("run frozen identity mismatch")
    try:
        summary, _ = run_one(run, RUN_IDS.index(run_id), all_train, validation_cases, schedule_data, PROCESS.memory_info().rss)
    except Exception as exc:
        history = STAGE07D / "training_histories" / f"{run_id}.jsonl"
        steps = len(history.read_text().splitlines()) if history.exists() else 0
        failure = {"schema": "sph-pio-poc.stage07d.run-failure.v1", "run_id": run_id,
            "terminal_reason": "FORMAL_RUN_NUMERICAL_FAILURE" if "FORMAL_RUN_NUMERICAL_FAILURE" in str(exc) else "FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE",
            "error": f"{type(exc).__name__}: {exc}", "optimizer_step_count": steps,
            "retry_or_replacement": False, "sealed_test_evaluations": 0,
            "sealed_decode_counts": {"formula": 0, "state": 0, "source": 0, "target": 0, "origin": 0}}
        write_json(STAGE07D / "runs" / run_id / "run_failure.json", failure)
        write_json(STAGE07D / "access_control" / f"{run_id}_failure_end.json", failure)
        raise
    print(json.dumps({"event": "run_process_terminal", "run_id": run_id, "terminal_update": summary["terminal_update"],
                      "selected_update": summary["selected_update"], "seed_pass": summary["seed_pass"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", choices=RUN_IDS, required=True)
    main(parser.parse_args().run_id)
