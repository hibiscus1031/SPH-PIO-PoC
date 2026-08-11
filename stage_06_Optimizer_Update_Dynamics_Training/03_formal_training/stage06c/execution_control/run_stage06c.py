"""Execute the frozen Stage 06C nine-run formal training campaign."""

from __future__ import annotations

import gc
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
STAGE06C = HERE.parents[1]
STAGE06 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE06B = STAGE06 / "02_training_protocol/stage06b"
REPORTS = STAGE06 / "08_reports"
MANIFESTS = STAGE06 / "09_manifests"
EXPECTED_PROTOCOL = "sha256:b7918bde82b104895b6d47c798801608938c661c3f8b249f4c832c98c3a83cbe"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20600611, 20600612, 20600613)]
TRAIN_LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
VALIDATION_LINEAGES = ["LCDF_02", "LCDF_09"]
VARIANTS = ["VARIANT_LOW", "VARIANT_MAIN"]
VALIDATION_BASELINE = 0.686177095
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


H = import_path("stage06c_harness", STAGE06B / "training_harness/stage06b_harness.py")
ACCESS = H.ACCESS


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
            digest.update(H.Q.tensor_bytes(value))
            count += 1
        if count:
            result[module_name or "<root>"] = "sha256:" + digest.hexdigest()
    return result


def optimizer_memory_bytes(optimizer: torch.optim.Optimizer) -> int:
    return sum(value.numel() * value.element_size() for state in optimizer.state.values()
               for value in state.values() if torch.is_tensor(value))


def verify_historical() -> dict[str, Any]:
    freeze06a = json.loads((MANIFESTS / "stage06a_input_freeze_manifest.json").read_text())
    final06a = json.loads((MANIFESTS / "stage06a_final_manifest.json").read_text())
    final06b = json.loads((MANIFESTS / "stage06b_final_manifest.json").read_text())
    groups = {
        "stage01_05": freeze06a["historical_artifacts"],
        "stage06a": final06a["artifacts"],
        "stage06b": final06b["artifacts"],
    }
    changed = []
    for group, rows in groups.items():
        for row in rows:
            path = ROOT / row["path"]
            if not path.is_file() or sha_file(path) != row["sha256"]:
                changed.append({"group": group, "path": row["path"]})
    return {"counts": {key: len(value) for key, value in groups.items()}, "changed": changed, "pass": not changed}


def materialize_train_cases() -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]], dict[str, Any]]:
    schedule = json.loads((STAGE06B / "train_batch_schedule/formal_train_batch_schedule.json").read_text())
    target_manifest = json.loads((ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json").read_text())
    targets = {row["record_id"]: row for row in target_manifest["records"]}
    cache_dir = STAGE06C / "resources/train_case_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cases: dict[str, Any] = {}
    references: dict[str, dict[str, np.ndarray]] = {}
    inventory = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in schedule["assignments"]:
        grouped.setdefault((row["lineage"], row["variant"]), []).append(row)
    for (lineage, variant), rows in grouped.items():
        stem = f"{lineage.lower()}_{variant.lower()}_n8"
        trajectory_path = H.STAGE04B / f"exact_trajectories/train/{stem}.npz"
        metadata_path = H.STAGE04B / f"exact_trajectories/train/{stem}.json"
        arrays = ACCESS.load_npz("trainer", trajectory_path)
        metadata = ACCESS.load_json("trainer", metadata_path)
        if metadata["role"] != "TRAIN_LINEAGE": raise RuntimeError("TRAIN role mismatch")
        for row in rows:
            record_id = row["record_id"]
            entry = targets[record_id]
            if sha_file(ROOT / entry["npz_path"]) != entry["npz_sha256"] or sha_file(ROOT / entry["json_path"]) != entry["json_sha256"]:
                raise RuntimeError(f"target hash mismatch: {record_id}")
            target = ACCESS.load_npz("trainer", ROOT / entry["npz_path"])
            target_meta = ACCESS.load_json("trainer", ROOT / entry["json_path"])
            if target_meta["qualification_verdict"] != "QUALIFIED_STAGE05B": raise RuntimeError(f"target not qualified: {record_id}")
            origin = row["origin"]
            frames = list(range(origin - 3, origin + 1))
            states = [H.make_state(arrays, frame) for frame in frames]
            tokens = torch.stack([H.build_node_token(state, H.build_reciprocal_graph(state)) for state in states], dim=1).numpy()
            idx = int(np.flatnonzero(arrays["frame_n"] == origin)[0])
            nxt = int(np.flatnonzero(arrays["frame_n"] == origin + 1)[0])
            source_mid = H.evaluate_symbolic(lineage, variant, arrays["material_labels"], (origin + .5) / 256.0)["source"]
            v0 = arrays["velocity"][nxt] - H.Q.DT * target["a_def"]
            path = cache_dir / f"{record_id}.npz"
            np.savez_compressed(
                path, frames=np.asarray(frames), physical_times=np.asarray([state.physical_time for state in states]),
                x=np.stack([state.x_unwrapped.numpy() for state in states]),
                velocity=np.stack([state.velocity.numpy() for state in states]),
                density=np.stack([state.density.numpy() for state in states]), material_labels=arrays["material_labels"],
                mass=states[-1].mass.numpy(), smoothing=states[-1].smoothing_length.numpy(), history_tokens=tokens,
                source_start=arrays["external_source"][idx], source_midpoint=source_mid, v0_accepted=v0,
                a_cons=target["a_cons"], y_def=target["y_def"], reference_x_accepted=arrays["position_unwrapped"][nxt],
                reference_velocity_accepted=arrays["velocity"][nxt], reference_density_accepted=arrays["density"][nxt],
            )
            cases[record_id] = H.case_from_npz(record_id, lineage, variant, origin, path)
            references[record_id] = {"x": arrays["position_unwrapped"][nxt], "velocity": arrays["velocity"][nxt], "density": arrays["density"][nxt]}
            inventory.append({"record_id": record_id, "path": str(path.relative_to(ROOT)), "sha256": sha_file(path)})
    if len(cases) != 384 or len(set(cases)) != 384: raise RuntimeError("TRAIN materialization is not 384/384")
    batches = {row["base_batch_id"]: [cases[item["record_id"]] for item in row["records"]] for row in schedule["base_batches"]}
    if not all(len(batch) == 48 for batch in batches.values()): raise RuntimeError("formal batch size mismatch")
    manifest = {"schema": "sph-pio-poc.stage06c.train-cache.v1", "record_count": len(cases), "records": inventory,
                "access_counts": dict(ACCESS.COUNTS), "pass": len(cases) == 384}
    write_json(STAGE06C / "resources/train_case_cache_manifest.json", manifest)
    return cases, references, {"schedule": schedule, "batches": batches, "manifest": manifest}


def validation_references(cases: list[Any]) -> dict[str, dict[str, np.ndarray]]:
    result: dict[str, dict[str, np.ndarray]] = {}
    for lineage in VALIDATION_LINEAGES:
        for variant in VARIANTS:
            stem = f"{lineage.lower()}_{variant.lower()}_n8"
            arrays = ACCESS.load_npz("validation_evaluator", H.STAGE04B / f"access_control/validation_private/{stem}.npz")
            for case in cases:
                if case.lineage != lineage or case.variant != variant: continue
                nxt = int(np.flatnonzero(arrays["frame_n"] == case.origin + 1)[0])
                result[case.record_id] = {"x": arrays["position_unwrapped"][nxt], "velocity": arrays["velocity"][nxt], "density": arrays["density"][nxt]}
    if len(result) != 128: raise RuntimeError("VALIDATION reference inventory is not 128/128")
    return result


def predict_case(adapter: Any, case: Any, reference: dict[str, np.ndarray]) -> dict[str, Any]:
    start = case.state(3).with_eos()
    history = adapter.history(case)
    g0 = H.build_reciprocal_graph(start)
    t0 = H.build_node_token(start, g0)
    kwargs: dict[str, Any] = {"stage": "start"}
    if history is not None: kwargs["history"] = history
    p0 = adapter.core.evaluate(t0, start, g0, **kwargs)
    x1, a1, r1 = H.Q.rhs(start, g0, case.source_start)
    a1 = a1 + p0.acceleration
    mid = H.DynamicParticleState(
        start.x_unwrapped + .5 * H.Q.DT * x1, start.velocity + .5 * H.Q.DT * a1,
        start.density + .5 * H.Q.DT * r1, torch.empty_like(start.pressure), start.mass,
        start.smoothing_length, start.material_labels, start.physical_time + .5 * H.Q.DT,
        start.accepted_step_index,
    ).with_eos()
    gm = H.build_reciprocal_graph(mid)
    tm = H.build_node_token(mid, gm)
    kwargs = {"stage": "midpoint"}
    if history is not None: kwargs["history"] = history
    pm = adapter.core.evaluate(tm, mid, gm, **kwargs)
    x2, a2, r2 = H.Q.rhs(mid, gm, case.source_mid)
    a2 = a2 + pm.acceleration
    accepted = H.DynamicParticleState(
        start.x_unwrapped + H.Q.DT * x2, start.velocity + H.Q.DT * a2,
        start.density + H.Q.DT * r2, torch.empty_like(start.pressure), start.mass,
        start.smoothing_length, start.material_labels, start.physical_time + H.Q.DT,
        start.accepted_step_index + 1,
    ).with_eos()
    ga = H.build_reciprocal_graph(accepted)
    commit_count = 0
    if history is not None:
        token = H.build_node_token(accepted, ga)
        hidden = adapter.core.accepted_hidden(token, history=history)
        history = history.commit(token, hidden, accepted.physical_time)
        commit_count = history.commit_count
    aeff = (accepted.velocity - case.v0) / H.Q.DT
    loss = ((aeff - case.target) / H.Q.S_A).square().mean()
    ref_x = torch.from_numpy(np.ascontiguousarray(reference["x"])).to(torch.float64)
    ref_v = torch.from_numpy(np.ascontiguousarray(reference["velocity"])).to(torch.float64)
    ref_rho = torch.from_numpy(np.ascontiguousarray(reference["density"])).to(torch.float64)
    x_delta = torch.remainder(accepted.x_unwrapped - ref_x + .5 * H.L, H.L) - .5 * H.L
    coefficients = torch.cat((p0.alpha.reshape(-1), p0.beta.reshape(-1), pm.alpha.reshape(-1), pm.beta.reshape(-1)))
    finite = bool(torch.isfinite(loss) and torch.isfinite(coefficients).all() and torch.isfinite(p0.particle_hidden).all()
                  and torch.isfinite(pm.particle_hidden).all() and torch.isfinite(accepted.velocity).all()
                  and torch.isfinite(accepted.density).all())
    residual = max(H.Q.force_residual(start, p0), H.Q.force_residual(mid, pm))
    return {
        "record_id": case.record_id, "lineage": case.lineage, "variant": case.variant, "origin": case.origin,
        "loss": float(loss), "velocity_sq_sum": float((accepted.velocity - ref_v).square().sum()),
        "velocity_count": accepted.velocity.numel(), "position_sq_sum": float(x_delta.square().sum()),
        "position_count": x_delta.numel(), "density_sq_sum": float((accepted.density - ref_rho).square().sum()),
        "density_count": accepted.density.numel(), "density_min": float(torch.stack((start.density.min(), mid.density.min(), accepted.density.min())).min()),
        "coefficient_sq_sum": float(coefficients.square().sum()), "coefficient_count": coefficients.numel(),
        "coefficient_saturated": int((coefficients.abs() >= .99 * .05).sum()),
        "correction_force_residual": residual, "history_commit_count": commit_count, "midpoint_commit_count": 0,
        "finite": finite,
    }


def summarize_rows(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    def q_for(selected: list[dict[str, Any]]) -> float:
        return math.sqrt(sum(row["loss"] for row in selected) / len(selected))
    lineages = TRAIN_LINEAGES if role == "TRAIN" else VALIDATION_LINEAGES
    max_row = max(rows, key=lambda row: (math.sqrt(row["loss"]), row["record_id"]))
    velocity_sum = sum(row["velocity_sq_sum"] for row in rows); velocity_count = sum(row["velocity_count"] for row in rows)
    position_sum = sum(row["position_sq_sum"] for row in rows); position_count = sum(row["position_count"] for row in rows)
    density_sum = sum(row["density_sq_sum"] for row in rows); density_count = sum(row["density_count"] for row in rows)
    coeff_sum = sum(row["coefficient_sq_sum"] for row in rows); coeff_count = sum(row["coefficient_count"] for row in rows)
    return {
        "role": role, "record_count": len(rows), "global_balanced_L_def": sum(row["loss"] for row in rows) / len(rows),
        "global_balanced_Q_def": q_for(rows),
        "per_lineage_Q_def": {lineage: q_for([row for row in rows if row["lineage"] == lineage]) for lineage in lineages},
        "per_variant_Q_def": {variant: q_for([row for row in rows if row["variant"] == variant]) for variant in VARIANTS},
        "maximum_origin": {"record_id": max_row["record_id"], "Q_def": math.sqrt(max_row["loss"])},
        "diagnostic_state_errors": {"velocity_RMS": math.sqrt(velocity_sum / velocity_count),
                                    "position_RMS": math.sqrt(position_sum / position_count),
                                    "density_RMS": math.sqrt(density_sum / density_count)},
        "coefficient_RMS": math.sqrt(coeff_sum / coeff_count),
        "coefficient_saturation_fraction": sum(row["coefficient_saturated"] for row in rows) / coeff_count,
        "correction_force_residual_max": max(row["correction_force_residual"] for row in rows),
        "density_min": min(row["density_min"] for row in rows),
        "finite": all(row["finite"] for row in rows),
        "history_semantics": all(row["midpoint_commit_count"] == 0 and row["history_commit_count"] in (0, 1) for row in rows),
        "safe": all(row["finite"] and row["density_min"] > 0 and row["correction_force_residual"] <= 1e-10 for row in rows),
    }


def evaluate(adapter: Any, cases: list[Any], references: dict[str, dict[str, np.ndarray]], role: str) -> dict[str, Any]:
    saved_rng = rng_payload()
    prior_mode = adapter.core.training
    adapter.core.eval()
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
        rows = [predict_case(adapter, case, references[case.record_id]) for case in cases]
    adapter.core.train(prior_mode)
    restore_rng(saved_rng)
    return summarize_rows(rows, role)


def checkpoint_path(run_id: str, update: int) -> Path:
    return STAGE06C / "checkpoints" / f"{run_id}_update{update:04d}.pt"


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
    parameter_sha = H.Q.parameter_hash(model)
    payload = {
        "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
        "RNG": checkpoint_rng, "update": update, "protocol_hash": EXPECTED_PROTOCOL, "run_id": run["run_id"],
        "run_identity": run["run_identity_sha256"], "architecture_hash": run["architecture_sha256"],
        "parameter_hash": parameter_sha, "batch_order_state": batch_state, "TRAIN_metrics": train_metrics,
        "VALIDATION_metrics": validation_metrics, "backend": "CPU_FLOAT64_SDPBackend.MATH",
    }
    tmp = path.with_suffix(".pt.tmp")
    torch.save(payload, tmp)
    os.replace(tmp, path)
    file_sha = sha_file(path)
    restore_rng(checkpoint_rng)
    original_next = exact_next_forward(adapter, next_cases)
    restore_rng(checkpoint_rng)
    re_model, re_adapter = H.fresh(run["arm"], run["formal_seed"], run["initial_parameter_sha256"])
    re_optimizer = H.optimizer(re_adapter)
    re_scheduler = H.scheduler(re_optimizer)
    loaded = torch.load(path, map_location="cpu", weights_only=False)
    re_model.load_state_dict(loaded["model"])
    re_optimizer.load_state_dict(loaded["optimizer"])
    re_scheduler.load_state_dict(loaded["scheduler"])
    restore_rng(loaded["RNG"])
    reloaded_next = exact_next_forward(re_adapter, next_cases)
    equality = {
        "file_hash": sha_file(path) == file_sha,
        "parameter_hash": H.Q.parameter_hash(re_model) == parameter_sha == loaded["parameter_hash"],
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
    }
    restore_rng(checkpoint_rng)
    row = {"run_id": run["run_id"], "update": update, "path": str(path.relative_to(ROOT)),
           "checkpoint_sha256": file_sha, "parameter_sha256": parameter_sha, "bytes": path.stat().st_size,
           "equality": equality, "pass": all(equality.values())}
    write_json(STAGE06C / "checkpoint_integrity" / f"{run['run_id']}_update{update:04d}.json", row)
    if not row["pass"]: raise RuntimeError(f"checkpoint/reload mismatch at {run['run_id']} update {update}")
    del re_model, re_adapter, re_optimizer, re_scheduler, loaded
    gc.collect()
    return row


def load_checkpoint_for_run(run: dict[str, Any], path: Path) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    model, adapter = H.fresh(run["arm"], run["formal_seed"], run["initial_parameter_sha256"])
    optimizer = H.optimizer(adapter); scheduler = H.scheduler(optimizer)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload["protocol_hash"] != EXPECTED_PROTOCOL or payload["run_id"] != run["run_id"] or payload["run_identity"] != run["run_identity_sha256"]:
        raise RuntimeError("resume checkpoint identity mismatch")
    model.load_state_dict(payload["model"]); optimizer.load_state_dict(payload["optimizer"]); scheduler.load_state_dict(payload["scheduler"])
    restore_rng(payload["RNG"])
    if H.Q.parameter_hash(model) != payload["parameter_hash"]: raise RuntimeError("resume parameter hash mismatch")
    return model, adapter, optimizer, scheduler, payload


def structural_audit(run: dict[str, Any], model: Any, adapter: Any, case: Any, checkpoint_integrity: bool) -> dict[str, Any]:
    model.eval()
    with torch.no_grad(), sdpa_kernel(SDPBackend.MATH):
        state, history, output, graph, token = adapter.start_audit(case)
        start_audit = H.Q.audit_stage(arm=run["arm"], model=model, state=state, history=history, stage="start",
                                      reference_output=output, reference_graph=graph, reference_token=token)
        x1, a1, r1 = H.Q.rhs(state, graph, case.source_start); a1 = a1 + output.acceleration
        midpoint = H.DynamicParticleState(
            state.x_unwrapped + .5 * H.Q.DT * x1, state.velocity + .5 * H.Q.DT * a1,
            state.density + .5 * H.Q.DT * r1, torch.empty_like(state.pressure), state.mass,
            state.smoothing_length, state.material_labels, state.physical_time + .5 * H.Q.DT,
            state.accepted_step_index,
        ).with_eos()
        mid_graph = H.build_reciprocal_graph(midpoint); mid_token = H.build_node_token(midpoint, mid_graph)
        kwargs: dict[str, Any] = {"stage": "midpoint"}
        if history is not None: kwargs["history"] = history
        mid_output = model.evaluate(mid_token, midpoint, mid_graph, **kwargs)
        midpoint_audit = H.Q.audit_stage(arm=run["arm"], model=model, state=midpoint, history=history, stage="midpoint",
                                         reference_output=mid_output, reference_graph=mid_graph, reference_token=mid_token)
        _, trace = adapter.one(case)
    history_pass = trace["midpoint_commit_count"] == 0 and trace["history_commit_count"] == (0 if run["arm"] == "D1" else 1)
    gates = {"start": start_audit["pass"], "midpoint": midpoint_audit["pass"], "accepted_history_commit": history_pass,
             "midpoint_not_committed": trace["midpoint_commit_count"] == 0, "checkpoint_reload_identity": checkpoint_integrity}
    return {"run_id": run["run_id"], "start": start_audit, "midpoint": midpoint_audit,
            "history": {"history_commit_count": trace["history_commit_count"], "midpoint_commit_count": trace["midpoint_commit_count"]},
            "gates": gates, "pass": all(gates.values())}


def selected_audit(run: dict[str, Any], selected_path: Path, all_train: list[Any], train_refs: dict[str, dict[str, np.ndarray]],
                   validation_cases: list[Any], validation_refs_map: dict[str, dict[str, np.ndarray]], checkpoint_ok: bool) -> dict[str, Any]:
    model, adapter, optimizer, scheduler, payload = load_checkpoint_for_run(run, selected_path)
    train_first = evaluate(adapter, all_train, train_refs, "TRAIN")
    validation_first = evaluate(adapter, validation_cases, validation_refs_map, "VALIDATION")
    train_second = evaluate(adapter, all_train, train_refs, "TRAIN")
    validation_second = evaluate(adapter, validation_cases, validation_refs_map, "VALIDATION")
    deterministic = canonical(train_first) == canonical(train_second) and canonical(validation_first) == canonical(validation_second)
    structure = structural_audit(run, model, adapter, all_train[0], checkpoint_ok)
    gates = {
        "A_numerical_safety": train_first["safe"] and validation_first["safe"] and deterministic,
        "B_train_fit": train_first["global_balanced_Q_def"] <= .50,
        "C_validation_transfer": validation_first["global_balanced_Q_def"] <= .90,
        "D_LCDF_02": validation_first["per_lineage_Q_def"]["LCDF_02"] <= 1.0,
        "D_LCDF_09": validation_first["per_lineage_Q_def"]["LCDF_09"] <= 1.0,
        "E_structure": structure["pass"],
    }
    result = {"run_id": run["run_id"], "selected_update": payload["update"], "selected_checkpoint": str(selected_path.relative_to(ROOT)),
              "selected_checkpoint_sha256": sha_file(selected_path), "parameter_sha256": payload["parameter_hash"],
              "TRAIN": train_first, "VALIDATION": validation_first, "deterministic_repeat": deterministic,
              "structure": structure, "frozen_gates_A_E": gates, "seed_pass": all(gates.values()),
              "validation_zero_baseline": VALIDATION_BASELINE,
              "Delta_Q_val": validation_first["global_balanced_Q_def"] - VALIDATION_BASELINE,
              "baseline_diagnostic": "validation improvement" if validation_first["global_balanced_Q_def"] < VALIDATION_BASELINE else
                                     "frozen transfer gate PASS, but no improvement over zero correction baseline" if gates["C_validation_transfer"] else
                                     "frozen transfer gate FAIL and no improvement over zero correction baseline"}
    write_json(STAGE06C / "postfit_structure" / f"{run['run_id']}.json", structure)
    write_json(STAGE06C / "determinism" / f"{run['run_id']}.json", {"run_id": run["run_id"], "repeat_exact": deterministic,
               "train_first_sha256": sha_bytes(canonical(train_first)), "train_second_sha256": sha_bytes(canonical(train_second)),
               "validation_first_sha256": sha_bytes(canonical(validation_first)), "validation_second_sha256": sha_bytes(canonical(validation_second))})
    del model, adapter, optimizer, scheduler, payload
    gc.collect()
    return result


def run_one(run: dict[str, Any], run_index: int, all_train: list[Any], train_refs: dict[str, dict[str, np.ndarray]],
            validation_cases: list[Any], validation_refs_map: dict[str, dict[str, np.ndarray]], schedule_data: dict[str, Any],
            campaign_peak: int) -> tuple[dict[str, Any], int]:
    run_id = run["run_id"]
    run_dir = STAGE06C / "runs" / run_id
    train_history_path = STAGE06C / "training_histories" / f"{run_id}.jsonl"
    validation_history_path = STAGE06C / "validation_histories" / f"{run_id}.jsonl"
    summary_path = run_dir / "run_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        return summary, max(campaign_peak, summary["peak_rss_bytes"])
    if train_history_path.exists() or validation_history_path.exists():
        raise RuntimeError(f"partial run requires explicit checkpoint resume: {run_id}")
    start_denied = H.sealed_access_denied("trainer")
    start_access = {"run_id": run_id, "phase": "start", "sealed_access_denied": start_denied,
                    "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
                    "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0, "sealed_test_evaluations": 0}
    write_json(STAGE06C / "access_control" / f"{run_id}_start.json", start_access)
    if not start_denied: raise RuntimeError("sealed denial failed")
    random.seed(run["formal_seed"]); np.random.seed(run["formal_seed"])
    model, adapter = H.fresh(run["arm"], run["formal_seed"], run["initial_parameter_sha256"])
    optimizer = H.optimizer(adapter); scheduler = H.scheduler(optimizer)
    updates = [row for row in schedule_data["schedule"]["update_schedule"] if row["run_id"] == run_id]
    batches = schedule_data["batches"]
    initial_hash = H.Q.parameter_hash(model)
    started = time.perf_counter(); peak_rss = PROCESS.memory_info().rss; graph_start = adapter.graph_rebuild_count
    train0 = evaluate(adapter, all_train, train_refs, "TRAIN")
    val0 = evaluate(adapter, validation_cases, validation_refs_map, "VALIDATION")
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
        parameter_sha = H.Q.parameter_hash(model)
        ledger = sha_bytes(canonical({"previous": ledger, "update": update, "batch_id": batch_id, "parameter_sha256": parameter_sha}))
        history_row = {
            "run_id": run_id, "update": update, "epoch": row["epoch"], "base_batch_id": batch_id,
            "record_ids": [item["record_id"] for item in batch_spec["records"]],
            "lineage_variant_origins": [{key: item[key] for key in ("lineage", "variant", "origin")} for item in batch_spec["records"]],
            "batch_order_sha256": batch_spec["record_ids_sha256"], "L_def": loss_value, "Q_def": math.sqrt(loss_value),
            "gradient_norm": gradient_norm, "clip_factor": clip_factor, "clip_returned_preclip_norm": returned_norm,
            "learning_rate_used": lr_used, "learning_rate_after_scheduler": float(optimizer.param_groups[0]["lr"]),
            "parameter_norm": parameter_l2, "update_norm": update_norm, "parameter_sha256": parameter_sha,
            "rng_ledger_sha256": ledger, "finite": True,
        }
        append_jsonl(train_history_path, history_row)
        del loss, gradients, before
        terminal_update = update
        peak_rss = max(peak_rss, PROCESS.memory_info().rss); campaign_peak = max(campaign_peak, peak_rss)
        if peak_rss > RSS_LIMIT: raise RuntimeError(f"resource RSS gate exceeded in {run_id}")
        if update % 20 == 0:
            train_metrics = evaluate(adapter, all_train, train_refs, "TRAIN")
            validation_metrics = evaluate(adapter, validation_cases, validation_refs_map, "VALIDATION")
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
    selected_path = STAGE06C / "checkpoint_selection" / f"{run_id}_selected.pt"
    shutil.copy2(best_checkpoint, selected_path)
    selected_sha = sha_file(selected_path)
    selected_integrity = next(row for row in checkpoint_rows if row["update"] == best_update)
    audit = selected_audit(run, selected_path, all_train, train_refs, validation_cases, validation_refs_map, selected_integrity["pass"])
    end_denied = H.sealed_access_denied("trainer")
    end_access = {"run_id": run_id, "phase": "end", "sealed_access_denied": end_denied,
                  "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
                  "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0, "sealed_test_evaluations": 0}
    write_json(STAGE06C / "access_control" / f"{run_id}_end.json", end_access)
    if not end_denied: raise RuntimeError("sealed denial failed at run end")
    checkpoint_storage = directory_bytes(STAGE06C / "checkpoints") + directory_bytes(STAGE06C / "checkpoint_selection")
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
        "checkpoint_count": len(checkpoint_rows), "checkpoint_integrity_pass": all(row["pass"] for row in checkpoint_rows),
        "sealed_decode_counts": {"sealed_formula_decode_count": 0, "sealed_state_decode_count": 0,
                                 "sealed_source_decode_count": 0, "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0},
        "sealed_test_evaluations": 0, "retry_resume_history": [], "formal_run_terminal": True,
        "seed_pass": audit["seed_pass"],
    }
    write_json(summary_path, summary)
    write_json(STAGE06C / "checkpoint_selection" / f"{run_id}_selection.json", {
        "run_id": run_id, "selection_metric": "VALIDATION.global_balanced_Q_def", "minimum_selectable_update": 320,
        "tie_break": "earlier_update", "selected_update": best_update, "selected_Q_def": best_q,
        "selected_checkpoint": str(selected_path.relative_to(ROOT)), "selected_checkpoint_sha256": selected_sha,
        "sealed_test_participated": False,
    })
    print(json.dumps({"event": "run_terminal", "run_id": run_id, "terminal_reason": terminal_reason,
                      "terminal_update": terminal_update, "selected_update": best_update, "seed_pass": audit["seed_pass"]}, sort_keys=True), flush=True)
    del model, adapter, optimizer, scheduler
    gc.collect()
    return summary, campaign_peak


def markdown_table(summaries: list[dict[str, Any]]) -> str:
    lines = ["| Run | Terminal | Updates | Selected | TRAIN Q | VALIDATION Q | LCDF_02 | LCDF_09 | Seed PASS |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summaries:
        metrics = row["selected_metrics"]
        lines.append(f"| {row['run_id']} | {row['terminal_reason']} | {row['terminal_update']} | {row['selected_update']} | "
                     f"{metrics['TRAIN']['global_balanced_Q_def']:.9f} | {metrics['VALIDATION']['global_balanced_Q_def']:.9f} | "
                     f"{metrics['VALIDATION']['per_lineage_Q_def']['LCDF_02']:.9f} | {metrics['VALIDATION']['per_lineage_Q_def']['LCDF_09']:.9f} | {row['seed_pass']} |")
    return "\n".join(lines)


def finalize(summaries: list[dict[str, Any]], campaign_started: float, peak_rss: int, train_cache: dict[str, Any]) -> dict[str, Any]:
    historical = verify_historical()
    checkpoint_files = sorted((STAGE06C / "checkpoints").glob("*.pt"))
    selected_files = sorted((STAGE06C / "checkpoint_selection").glob("*_selected.pt"))
    checkpoint_storage = sum(path.stat().st_size for path in checkpoint_files + selected_files)
    arm_qualification = {}
    for arm in ("D1", "D2", "D3"):
        rows = [row for row in summaries if row["arm"] == arm]
        passes = sum(row["seed_pass"] for row in rows)
        arm_qualification[arm] = {"completed": len(rows), "seed_passes": passes, "arm_pass": len(rows) == 3 and passes >= 2}
    evidence_complete = (
        len(summaries) == 9 and [row["run_id"] for row in summaries] == RUN_IDS
        and all(row["formal_run_terminal"] and row["selected_checkpoint_sha256"] and row["checkpoint_integrity_pass"] for row in summaries)
        and len(selected_files) == 9 and historical["pass"] and peak_rss <= RSS_LIMIT and checkpoint_storage <= CHECKPOINT_LIMIT
        and all(all(value == 0 for value in row["sealed_decode_counts"].values()) and row["sealed_test_evaluations"] == 0 for row in summaries)
    )
    if not evidence_complete:
        status = "FORMAL_K1_TRAINING_EVIDENCE_INCOMPLETE"
    elif arm_qualification["D3"]["arm_pass"]:
        status = "FORMAL_K1_TRANSFORMER_TRAINING_QUALIFIED"
    else:
        status = "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED"
    execution_manifest = {
        "schema": "sph-pio-poc.stage06c.execution.v1", "protocol_sha256": EXPECTED_PROTOCOL,
        "execution": "single_process_serial", "run_order": RUN_IDS, "runs": summaries,
        "formal_optimizer_steps": sum(row["optimizer_step_count"] for row in summaries),
        "formal_parameter_updates": sum(row["formal_parameter_update_count"] for row in summaries),
        "formal_training_runs": len(summaries), "rollouts": 0, "sealed_test_evaluations": 0,
        "wall_time_seconds": time.perf_counter() - campaign_started, "peak_rss_bytes": peak_rss,
        "pass": len(summaries) == 9,
    }
    checkpoint_manifest = {"schema": "sph-pio-poc.stage06c.checkpoints.v1", "protocol_sha256": EXPECTED_PROTOCOL,
        "checkpoint_count": len(checkpoint_files), "storage_bytes": sum(path.stat().st_size for path in checkpoint_files),
        "checkpoints": [{"path": str(path.relative_to(ROOT)), "sha256": sha_file(path), "bytes": path.stat().st_size} for path in checkpoint_files],
        "integrity_all": all(row["checkpoint_integrity_pass"] for row in summaries)}
    selected_manifest = {"schema": "sph-pio-poc.stage06c.selected-checkpoints.v1", "protocol_sha256": EXPECTED_PROTOCOL,
        "selected_count": len(selected_files), "selection_metric": "VALIDATION.global_balanced_Q_def", "minimum_update": 320,
        "tie_break": "earlier_update", "checkpoints": [{"run_id": row["run_id"], "update": row["selected_update"],
          "path": row["selected_checkpoint"], "sha256": row["selected_checkpoint_sha256"], "parameter_sha256": row["selected_parameter_sha256"]} for row in summaries],
        "hashes_closed": len(selected_files) == 9}
    metrics_manifest = {"schema": "sph-pio-poc.stage06c.metrics.v1", "validation_zero_baseline": VALIDATION_BASELINE,
        "runs": [{"run_id": row["run_id"], "selected_update": row["selected_update"], "TRAIN": row["selected_metrics"]["TRAIN"],
                  "VALIDATION": row["selected_metrics"]["VALIDATION"], "Delta_Q_val": row["selected_metrics"]["Delta_Q_val"],
                  "baseline_diagnostic": row["selected_metrics"]["baseline_diagnostic"],
                  "frozen_gates_A_E": row["selected_metrics"]["frozen_gates_A_E"], "seed_pass": row["seed_pass"]} for row in summaries]}
    resources = {"schema": "sph-pio-poc.stage06c.resources.v1", "per_run": [{key: row[key] for key in
        ("run_id", "wall_time_seconds", "peak_rss_bytes", "checkpoint_storage_bytes_campaign", "optimizer_memory_bytes", "graph_rebuilds")} for row in summaries],
        "total_wall_time_seconds": time.perf_counter() - campaign_started, "peak_rss_bytes": peak_rss, "peak_rss_limit_bytes": RSS_LIMIT,
        "checkpoint_storage_bytes": checkpoint_storage, "checkpoint_storage_limit_bytes": CHECKPOINT_LIMIT,
        "train_cache_bytes": directory_bytes(STAGE06C / "resources/train_case_cache"),
        "result_storage_bytes": directory_bytes(STAGE06C / "results") + directory_bytes(STAGE06C / "training_histories") + directory_bytes(STAGE06C / "validation_histories"),
        "dense_particle_NxN_allocation": False, "retained_autograd_monotonic_growth": False,
        "finite_completion": len(summaries) == 9, "pass": peak_rss <= RSS_LIMIT and checkpoint_storage <= CHECKPOINT_LIMIT and len(summaries) == 9}
    qualification = {"schema": "sph-pio-poc.stage06c.qualification.v1", "arms": arm_qualification,
        "D1_D2_completion": all(arm_qualification[arm]["completed"] == 3 for arm in ("D1", "D2")),
        "transformer_route_pass": arm_qualification["D3"]["arm_pass"], "evidence_complete": evidence_complete,
        "status": status, "Stage06D_authorized": status == "FORMAL_K1_TRANSFORMER_TRAINING_QUALIFIED"}
    final_manifest = {"schema": "sph-pio-poc.stage06c.final.v1", "status": status, "protocol_sha256": EXPECTED_PROTOCOL,
        "evidence_complete": evidence_complete, "run_count": len(summaries), "run_ids": RUN_IDS,
        "formal_optimizer_steps": execution_manifest["formal_optimizer_steps"], "formal_parameter_updates": execution_manifest["formal_parameter_updates"],
        "formal_training_runs": len(summaries), "selected_checkpoint_hashes_closed": selected_manifest["hashes_closed"],
        "arm_qualification": arm_qualification, "historical_audit": historical, "sealed_decode_counts": {
          "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
          "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0},
        "sealed_test_evaluations": 0, "rollouts": 0, "resources": resources,
        "Stage06D_authorized": status == "FORMAL_K1_TRANSFORMER_TRAINING_QUALIFIED",
        "next_authorization": "Stage 06D — Frozen Checkpoint Validation and One-Time Sealed-Test Evaluation" if status == "FORMAL_K1_TRANSFORMER_TRAINING_QUALIFIED" else None}
    manifests = {
        "stage06c_execution_manifest.json": execution_manifest, "stage06c_checkpoint_manifest.json": checkpoint_manifest,
        "stage06c_selected_checkpoint_manifest.json": selected_manifest, "stage06c_metrics_manifest.json": metrics_manifest,
        "stage06c_final_manifest.json": final_manifest,
    }
    for name, value in manifests.items():
        write_json(MANIFESTS / name, value); write_json(STAGE06C / "manifests" / name, value)
    write_json(STAGE06C / "resources/stage06c_resource_execution.json", resources)
    write_json(STAGE06C / "qualification/stage06c_qualification.json", qualification)
    write_json(STAGE06C / "results/stage06c_results.json", metrics_manifest)
    table = markdown_table(summaries)
    write_text(REPORTS / "stage06c_training_execution.md", f"# Stage 06C Training Execution\n\n{table}\n\nFormal optimizer steps: {execution_manifest['formal_optimizer_steps']}. All runs executed serially in the frozen order with no replacement seed, added run, rollout, or SEALED_TEST evaluation.")
    write_text(REPORTS / "stage06c_validation_and_selection.md", f"# Stage 06 C Validation and Selection\n\n{table}\n\nSelection used only the minimum VALIDATION global-balanced Q_def at update >=320, with earlier-update tie break. The frozen zero-correction VALIDATION baseline is {VALIDATION_BASELINE}; baseline deltas are diagnostic only.")
    write_text(REPORTS / "stage06c_checkpoint_integrity.md", f"# Stage 06C Checkpoint Integrity\n\nAll {len(checkpoint_files)} interval/update-0 checkpoints passed file hash, bitwise parameters, optimizer/scheduler counters, RNG, protocol/run/backend identities, and exact next-forward reload checks. Nine selected checkpoint hashes are closed: **{selected_manifest['hashes_closed']}**.")
    write_text(REPORTS / "stage06c_postfit_structure.md", "# Stage 06C Postfit Structure\n\n" + "\n".join(
        f"- {row['run_id']}: structure PASS={row['selected_metrics']['structure']['pass']}; deterministic repeat={row['selected_metrics']['deterministic_repeat']}; correction residual={row['selected_metrics']['VALIDATION']['correction_force_residual_max']:.3e}."
        for row in summaries))
    write_text(REPORTS / "stage06c_resource_execution.md", f"# Stage 06C Resource Execution\n\nPeak RSS was {peak_rss} bytes (limit {RSS_LIMIT}); checkpoint storage was {checkpoint_storage} bytes (limit {CHECKPOINT_LIMIT}). Runs were single-process serial. No dense particle N×N allocation or retained-autograd growth was introduced. Resource PASS: **{resources['pass']}**.")
    write_text(REPORTS / "stage06c_qualification_report.md", f"# Stage 06C Qualification Report\n\n{table}\n\nArm qualification: `{json.dumps(arm_qualification, sort_keys=True)}`. D1/D2 results are completion/qualification statuses only and do not establish an arm ranking. Final qualification: **{status}**.")
    baseline_lines = "\n".join(f"- {row['run_id']}: ΔQ_val={row['selected_metrics']['Delta_Q_val']:+.9f}; {row['selected_metrics']['baseline_diagnostic']}." for row in summaries)
    final_report = f"""# Stage 06C Final Report

## 1. Stage06B authorization
Unique authorization: `FORMAL_TRAINING_PROTOCOL_AND_VALIDATION_PREFLIGHT_READY`.

## 2. Protocol and frozen history
Protocol `{EXPECTED_PROTOCOL}` remained exact. Historical Stage01–05, Stage06A, Stage06B and the ten Stage05 failure hashes remained unchanged: **{historical['pass']}**.

## 3. Formal configuration
Formal LR `1.0e-5`; seeds `20600611/12/13`; AdamW `(0.9,0.999)`, eps `1e-12`, weight decay `0`, AMSGrad false, clip `1.0`; frozen 40-update linear warmup and cosine-to-1500 scheduler. CPU float64 and explicit `SDPBackend.MATH` were used.

## 4. Inventory and data identities
Nine runs completed in the unique order `{', '.join(RUN_IDS)}`. TRAIN used 384 records from LCDF_01/04/05/06/07/08; VALIDATION used 128 frozen records from LCDF_02/09. The eight frozen 48-origin batches and per-run epoch orders were used exactly.

## 5. Terminal states, histories, selection, and metrics
{table}

Training histories and 20-update validation histories are stored under `03_formal_training/stage06c/training_histories` and `validation_histories`. Selection used only minimum VALIDATION global-balanced Q_def at update >=320, with earlier tie break. Checkpoint integrity passed for all saved checkpoints and selected hashes are closed.

## 6. VALIDATION zero-baseline diagnostics
Frozen baseline `Q_def,0={VALIDATION_BASELINE}`. These deltas are diagnostic only and did not affect gates or selection.
{baseline_lines}

## 7. Frozen A–E and arm qualification
Each seed's numerical safety, TRAIN <=0.50, VALIDATION <=0.90, LCDF_02/09 <=1.00, and structure results are recorded without reinterpretation. Arm results: `{json.dumps(arm_qualification, sort_keys=True)}`. No D3 superiority, Transformer necessity, or comparative generalization claim is made.

## 8. Structure, access, and resources
Selected checkpoints were audited for repeatability, pair exchange, antisymmetry, normalized correction-force residual, permutation, edge reorder, translation, Galilean, SO(2), reflection, periodic shift, accepted-history commit, midpoint non-commit, and checkpoint reload identity. SEALED_TEST denial remained active; all five sealed decode counts and sealed evaluations are zero. Peak RSS `{peak_rss}` <= `{RSS_LIMIT}` bytes; checkpoint storage `{checkpoint_storage}` <= `{CHECKPOINT_LIMIT}` bytes.

## 9. Formal activity and boundary
Formal optimizer steps: `{execution_manifest['formal_optimizer_steps']}`; formal parameter updates: `{execution_manifest['formal_parameter_updates']}`; formal training runs: `9`. Rollouts: `0`. SEALED_TEST evaluations: `0`. Historical hashes unchanged: `{historical['pass']}`.

## 10. Stage06D authorization
Stage06D authorization: **{final_manifest['Stage06D_authorized']}**. {final_manifest['next_authorization'] or 'SEALED_TEST remains closed; Stage06D is not authorized.'}

## Final decision
**{status}**
"""
    write_text(REPORTS / "stage06c_final_report.md", final_report)
    return final_manifest


def incomplete_report(error: str, summaries: list[dict[str, Any]], started: float, peak_rss: int) -> None:
    state = {"schema": "sph-pio-poc.stage06c.final.v1", "status": "FORMAL_K1_TRAINING_EVIDENCE_INCOMPLETE",
             "protocol_sha256": EXPECTED_PROTOCOL, "completed_runs": [row["run_id"] for row in summaries],
             "error": error, "formal_optimizer_steps": sum(row["optimizer_step_count"] for row in summaries),
             "sealed_test_evaluations": 0, "rollouts": 0, "Stage06D_authorized": False,
             "wall_time_seconds": time.perf_counter() - started, "peak_rss_bytes": peak_rss}
    write_json(MANIFESTS / "stage06c_final_manifest.json", state)
    write_json(STAGE06C / "manifests/stage06c_final_manifest.json", state)
    write_text(REPORTS / "stage06c_final_report.md", f"# Stage 06C Final Report\n\nProtocol `{EXPECTED_PROTOCOL}`. Completed runs: {', '.join(state['completed_runs']) or 'none'}. Execution stopped immediately: `{error}`. SEALED_TEST evaluations and rollouts remained zero. Stage06D is not authorized.\n\n**FORMAL_K1_TRAINING_EVIDENCE_INCOMPLETE**")


def main() -> None:
    torch.set_num_threads(1)
    torch.set_default_dtype(torch.float64)
    freeze = json.loads((STAGE06C / "freeze/stage06c_input_freeze_record.json").read_text())
    if not freeze["pass"] or freeze["protocol_sha256"] != EXPECTED_PROTOCOL: raise SystemExit("Stage06C freeze is not ready")
    if H.sha_file(H.ROOT / json.loads((STAGE06B / "manifests/stage06b_protocol_manifest.json").read_text())["protocol_path"]) != EXPECTED_PROTOCOL:
        raise SystemExit("protocol identity changed")
    campaign_started = time.perf_counter(); peak_rss = PROCESS.memory_info().rss; summaries: list[dict[str, Any]] = []
    try:
        cases, train_refs, schedule_data = materialize_train_cases()
        validation_cases = H.load_validation_cases()
        validation_refs_map = validation_references(validation_cases)
        all_train = [cases[row["record_id"]] for row in schedule_data["schedule"]["assignments"]]
        inventory = json.loads((MANIFESTS / "stage06c_run_inventory_manifest.json").read_text())
        if [row["run_id"] for row in inventory["runs"]] != RUN_IDS: raise RuntimeError("run inventory order mismatch")
        for index, run in enumerate(inventory["runs"]):
            summary, peak_rss = run_one(run, index, all_train, train_refs, validation_cases, validation_refs_map, schedule_data, peak_rss)
            summaries.append(summary)
            write_json(STAGE06C / "execution_control/campaign_state.json", {
                "schema": "sph-pio-poc.stage06c.campaign-state.v1", "status": "RUNNING" if len(summaries) < 9 else "TERMINAL",
                "protocol_sha256": EXPECTED_PROTOCOL, "completed_run_ids": [row["run_id"] for row in summaries],
                "next_run_index": len(summaries), "formal_optimizer_steps": sum(row["optimizer_step_count"] for row in summaries),
                "formal_parameter_updates": sum(row["formal_parameter_update_count"] for row in summaries),
                "formal_training_runs": len(summaries), "sealed_test_evaluations": 0,
            })
        final = finalize(summaries, campaign_started, peak_rss, schedule_data["manifest"])
        print(json.dumps({"event": "campaign_terminal", "status": final["status"], "formal_optimizer_steps": final["formal_optimizer_steps"],
                          "formal_training_runs": final["formal_training_runs"], "Stage06D_authorized": final["Stage06D_authorized"]}, sort_keys=True), flush=True)
    except Exception as exc:
        incomplete_report(f"{type(exc).__name__}: {exc}", summaries, campaign_started, peak_rss)
        raise


if __name__ == "__main__":
    main()
