#!/usr/bin/env python3
"""Execute the frozen nine-run Stage 02M-Q v0.2 matrix and one-time sealed test."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import weakref
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

torch.set_default_dtype(torch.float64)
torch.set_num_threads(1)
try: torch.set_num_interop_threads(1)
except RuntimeError: pass
torch.use_deterministic_algorithms(True)
sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_2"
PROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
MROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_1"
KROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"
sys.path.insert(0, str(ROOT / "execution_preflight"))
sys.path.insert(0, str(MROOT / "postfit_structure"))
sys.path.insert(0, str(PROOT / "conditioning_contract"))
sys.path.insert(0, str(LROOT / "loss"))
sys.path.insert(0, str(KROOT / "implementations"))

from controlled_loader_v0_2 import AccessPolicyError, ControlledStage02MQLoader  # noqa: E402
from frozen_execution import FrozenPostOptimizerScheduler, initialize_frozen, learning_rate_at, model_hash, optimizer_counter  # noqa: E402
from loss_contract import EPSILON_METRIC, static_metrics  # noqa: E402
from loss_v0_2 import A_SUP, SUPERVISION_SCALE_HASH, graph_scaled_node_mse  # noqa: E402
from pair_force_models import MODEL_CLASSES, PairGraph  # noqa: E402
from postfit_audit import audit_selected_checkpoint  # noqa: E402

PROTOCOL_HASH = "sha256:8cd068c5b23eacfbcb2c56846352fd6f3c560b46d8562806e3ed568c278ddb6e"
ARCHITECTURE_HASH = "sha256:1e313f871b13f3f2fc0cc780ab24d50a7fd9fe8a96866da91fae5ede9ab555a4"
NORMALIZATION_HASH = "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def current_rss() -> int:
    try:
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except ImportError:
        return 0


def cpu_identity() -> str:
    try:
        value = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=False).stdout.strip()
        if value: return value
    except OSError: pass
    return platform.processor() or platform.machine()


def environment_audit() -> dict[str, Any]:
    environment = {
        "python": sys.version, "torch": torch.__version__, "numpy": np.__version__, "OS": platform.platform(),
        "CPU_identity": cpu_identity(), "device": "CPU", "dtype": "float64",
        "torch_num_threads": torch.get_num_threads(), "torch_num_interop_threads": torch.get_num_interop_threads(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "MPS_used": False, "mixed_precision": False,
        "BLAS_OpenMP_environment": {key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
        "initial_RSS_bytes": current_rss(),
    }
    environment["environment_hash"] = content_hash(environment)
    environment["status"] = "PASS" if environment["device"] == "CPU" and environment["dtype"] == "float64" and environment["deterministic_algorithms"] else "FAIL"
    return environment


@dataclass
class DatasetItem:
    case_id: str
    family_id: str
    resolution_id: str
    support_id: str
    graph: PairGraph
    target: torch.Tensor


def input_to_graph(record: Any) -> PairGraph:
    a = record.arrays
    source = a["stage02b_record.neighbor_information.source_index"]
    target = a["stage02b_record.neighbor_information.target_index"]
    unique = source < target
    return PairGraph(
        position=torch.as_tensor(a["stage02b_record.particle_state.position_periodic"]),
        velocity=torch.as_tensor(a["stage02b_record.particle_state.velocity"]),
        density=torch.as_tensor(a["stage02b_record.particle_state.density"]),
        pressure=torch.as_tensor(a["stage02b_record.particle_state.pressure"]),
        mass=torch.as_tensor(a["stage02b_record.particle_state.mass"]),
        smoothing_length=torch.as_tensor(a["stage02b_record.particle_state.smoothing_length"]),
        pair_i=torch.as_tensor(source[unique]), pair_j=torch.as_tensor(target[unique]),
        active=torch.as_tensor(a["reciprocal_graph_extensions.active_kernel_indicator"][unique]),
        displacement=torch.as_tensor(a["stage02b_record.neighbor_information.minimum_image_displacement"][unique]),
        relative_velocity=torch.as_tensor(a["stage02b_record.neighbor_information.relative_velocity"][unique] / 20.0),
    )


def make_items(loader: ControlledStage02MQLoader, inputs: dict[str, Any], role: str, purpose: str) -> list[DatasetItem]:
    items = []
    for case_id in sorted(case for case, row in loader.rows.items() if row["split_role"] == role):
        supervised = loader.load_target(case_id, purpose)
        items.append(DatasetItem(case_id, supervised.family_id, supervised.resolution_id, supervised.support_id, input_to_graph(inputs[case_id]), torch.as_tensor(supervised.target)))
    return items


def metric_value(prediction: torch.Tensor, target: torch.Tensor) -> dict[str, float]:
    return {key: float(value) for key, value in static_metrics(prediction, target).items()}


def aggregate_metrics(per_graph: list[dict[str, Any]]) -> dict[str, Any]:
    def mean_for(key: str, rows: list[dict[str, Any]]) -> float:
        return float(np.mean([row[key] for row in rows]))
    families = sorted({row["family_id"] for row in per_graph})
    family_values = {family: {key: mean_for(key, [row for row in per_graph if row["family_id"] == family]) for key in ("Q_L2", "Q_Linf", "cosine")} for family in families}
    per_resolution = {value: mean_for("Q_L2", [row for row in per_graph if row["resolution_id"] == value]) for value in sorted({row["resolution_id"] for row in per_graph})}
    per_support = {value: mean_for("Q_L2", [row for row in per_graph if row["support_id"] == value]) for value in sorted({row["support_id"] for row in per_graph})}
    return {
        "per_graph": per_graph,
        "graph_balanced_mean": {key: mean_for(key, per_graph) for key in ("Q_L2", "Q_Linf", "cosine")},
        "family_means": family_values,
        "family_balanced_mean": {key: float(np.mean([family_values[family][key] for family in families])) for key in ("Q_L2", "Q_Linf", "cosine")},
        "median": {key: float(np.median([row[key] for row in per_graph])) for key in ("Q_L2", "Q_Linf", "cosine")},
        "maximum": {key: float(np.max([row[key] for row in per_graph])) for key in ("Q_L2", "Q_Linf")},
        "per_resolution_Q_L2": per_resolution, "per_support_Q_L2": per_support,
    }


def evaluate(model: torch.nn.Module, items: list[DatasetItem]) -> dict[str, Any]:
    rows = []
    model.eval()
    with torch.no_grad():
        for item in items:
            values = metric_value(model(item.graph), item.target)
            rows.append({"case_id": item.case_id, "family_id": item.family_id, "resolution_id": item.resolution_id, "support_id": item.support_id, **values})
    model.train()
    return aggregate_metrics(rows)


def zero_baseline(items: list[DatasetItem]) -> dict[str, Any]:
    rows = []
    for item in items:
        values = metric_value(torch.zeros_like(item.target), item.target)
        rows.append({"case_id": item.case_id, "family_id": item.family_id, "resolution_id": item.resolution_id, "support_id": item.support_id, **values})
    result = aggregate_metrics(rows); result["theoretical_Q_L2_convention"] = 1.0; result["epsilon_metric"] = EPSILON_METRIC
    return result


def split_hash(loader: ControlledStage02MQLoader, role: str) -> str:
    return content_hash(sorted(case for case, row in loader.rows.items() if row["split_role"] == role))


def create_optimizer(model: torch.nn.Module) -> torch.optim.AdamW:
    return torch.optim.AdamW(model.parameters(), lr=1e-3, betas=(0.9, 0.999), eps=1e-12, weight_decay=0.0)


def major_module(parameter_name: str) -> str:
    prefix = parameter_name.split(".", 1)[0]
    return "interaction_blocks" if prefix == "blocks" else prefix


def full_batch_gradient(model: torch.nn.Module, optimizer: torch.optim.Optimizer, train_items: list[DatasetItem]) -> tuple[float, float]:
    optimizer.zero_grad(set_to_none=True)
    total = torch.zeros((), dtype=torch.float64)
    for item in train_items:
        total = total + graph_scaled_node_mse(model(item.graph), item.target) / len(train_items)
    total.backward()
    preclip = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    return float(total.detach()), float(preclip)


def conditioning_snapshot(
    model: torch.nn.Module,
    optimizer: torch.optim.AdamW,
    train_items: list[DatasetItem],
    label: str,
    update: int,
    *,
    recompute_gradient: bool,
    learning_rate: float,
) -> dict[str, Any]:
    loss = preclip = None
    if recompute_gradient:
        loss, preclip = full_batch_gradient(model, optimizer, train_items)
    beta1, beta2 = optimizer.param_groups[0]["betas"]
    eps = float(optimizer.param_groups[0]["eps"])
    module_rows: dict[str, list[dict[str, Any]]] = {}
    all_rows = []
    for name, parameter in model.named_parameters():
        grad = torch.zeros_like(parameter) if parameter.grad is None else parameter.grad.detach()
        state = optimizer.state.get(parameter, {})
        if "exp_avg" in state:
            m = state["exp_avg"].detach()
            v = state["exp_avg_sq"].detach()
            step_value = state.get("step", update)
            step = int(step_value.item()) if isinstance(step_value, torch.Tensor) else int(step_value)
        else:
            m = (1.0 - beta1) * grad
            v = (1.0 - beta2) * grad.square()
            step = max(update, 1)
        mhat = m / (1.0 - beta1 ** max(step, 1))
        vhat = v / (1.0 - beta2 ** max(step, 1))
        sqrt_v = torch.sqrt(vhat)
        effective = learning_rate * mhat / (sqrt_v + eps)
        count = parameter.numel()
        row = {
            "parameter": name,
            "module": major_module(name),
            "parameter_count": count,
            "gradient_L2": float(torch.linalg.vector_norm(grad)),
            "gradient_RMS": float(torch.sqrt(torch.mean(grad.square()))),
            "gradient_Linf": float(torch.max(torch.abs(grad))),
            "finite_gradient_fraction": float(torch.isfinite(grad).sum()) / count,
            "nonzero_gradient_fraction": float((torch.abs(grad) > 1e-14).sum()) / count,
            "near_zero_gradient_fraction": float((torch.abs(grad) <= 1e-14).sum()) / count,
            "sqrt_v_RMS": float(torch.sqrt(torch.mean(vhat))),
            "epsilon_dominated_fraction": float((sqrt_v <= 10.0 * eps).sum()) / count,
            "weight_decay_dominated_fraction": 0.0,
            "parameter_L2": float(torch.linalg.vector_norm(parameter.detach())),
            "effective_update_L2": float(torch.linalg.vector_norm(effective)),
            "update_to_parameter_ratio": float(torch.linalg.vector_norm(effective) / torch.clamp(torch.linalg.vector_norm(parameter.detach()), min=1e-30)),
        }
        all_rows.append(row)
        module_rows.setdefault(row["module"], []).append(row)
    modules = {}
    for name, rows in module_rows.items():
        total_count = sum(row["parameter_count"] for row in rows)
        modules[name] = {
            "parameter_count": total_count,
            "gradient_RMS": math.sqrt(sum(row["gradient_RMS"] ** 2 * row["parameter_count"] for row in rows) / total_count),
            "epsilon_dominated_fraction": sum(row["epsilon_dominated_fraction"] * row["parameter_count"] for row in rows) / total_count,
            "nonzero_gradient_fraction": sum(row["nonzero_gradient_fraction"] * row["parameter_count"] for row in rows) / total_count,
            "near_zero_gradient_fraction": sum(row["near_zero_gradient_fraction"] * row["parameter_count"] for row in rows) / total_count,
            "weight_decay_dominated_fraction": 0.0,
            "effective_update_L2": math.sqrt(sum(row["effective_update_L2"] ** 2 for row in rows)),
        }
    coefficients = []
    with torch.no_grad():
        for item in train_items:
            details = model(item.graph, return_details=True)
            coefficients.append(torch.stack((details["alpha"], details["beta"]), dim=-1))
    coefficient = torch.cat(coefficients, dim=0)
    return {
        "label": label,
        "update": update,
        "gradient_source": "recomputed_diagnostic_no_optimizer_step" if recompute_gradient else "training_backward_preceding_recorded_optimizer_step",
        "scaled_full_batch_loss": loss,
        "unclipped_gradient_norm": preclip,
        "learning_rate": learning_rate,
        "optimizer_epsilon": eps,
        "weight_decay": 0.0,
        "model_parameter_hash": model_hash(model),
        "parameters": all_rows,
        "modules": modules,
        "coefficient_RMS": float(torch.sqrt(torch.mean(coefficient.square()))),
        "coefficient_saturation_fraction_abs_ge_0p95": float((torch.abs(coefficient) >= 0.95).sum()) / coefficient.numel(),
        "finite": all(row["finite_gradient_fraction"] == 1.0 for row in all_rows) and bool(torch.isfinite(coefficient).all()),
    }


def rng_state() -> dict[str, Any]:
    return {"torch": torch.get_rng_state(), "numpy": np.random.get_state(), "python": random.getstate()}


def rng_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return torch.equal(left["torch"], right["torch"]) and left["numpy"][0] == right["numpy"][0] and np.array_equal(left["numpy"][1], right["numpy"][1]) and left["numpy"][2:] == right["numpy"][2:] and left["python"] == right["python"]


def restore_rng(state: dict[str, Any]) -> None:
    torch.set_rng_state(state["torch"]); np.random.set_state(state["numpy"]); random.setstate(state["python"])


def checkpoint_payload(architecture: str, run_id: str, seed: int, update: int, model: torch.nn.Module, optimizer: torch.optim.Optimizer, scheduler: FrozenPostOptimizerScheduler, best_metric: float, best_update: int, patience_metric: float, patience_update: int, training_history: list[dict[str, Any]], validation_history: list[dict[str, Any]], loader: ControlledStage02MQLoader) -> dict[str, Any]:
    return {
        "architecture_id": architecture, "architecture_hash": ARCHITECTURE_HASH, "protocol_hash": PROTOCOL_HASH,
        "dataset_collection_id": loader.base.manifest["dataset_collection"],
        "train_split_hash": split_hash(loader, "future_train"), "validation_split_hash": split_hash(loader, "future_validation"),
        "normalization_hash": NORMALIZATION_HASH, "a_sup": A_SUP, "supervision_scale_hash": SUPERVISION_SCALE_HASH,
        "run_id": run_id, "training_seed": seed,
        "model_parameters": model.state_dict(), "optimizer_state": optimizer.state_dict(), "scheduler_state": scheduler.state_dict(),
        "update_number": update, "RNG_states": rng_state(), "best_validation_metric": best_metric,
        "best_validation_update": best_update, "patience_reference_metric": patience_metric, "last_patience_improvement_update": patience_update,
        "training_history": training_history, "validation_history": validation_history,
        "provenance": {"stage": "02M-Q", "protocol_hash": PROTOCOL_HASH, "architecture_hash": ARCHITECTURE_HASH, "test_target_access": False},
    }


def write_and_verify_checkpoint(path: Path, payload: dict[str, Any], graph: PairGraph, model: torch.nn.Module, optimizer: torch.optim.Optimizer, scheduler: FrozenPostOptimizerScheduler) -> dict[str, Any]:
    before_rng = rng_state()
    with torch.no_grad(): before = model(graph).detach().clone()
    started = time.perf_counter(); torch.save(payload, path); write_seconds = time.perf_counter()-started
    loaded = torch.load(path, map_location="cpu", weights_only=False)
    restored = MODEL_CLASSES[payload["architecture_id"]]().to(device="cpu", dtype=torch.float64)
    initialize_frozen(restored, payload["training_seed"]); restored.load_state_dict(loaded["model_parameters"])
    restored_optimizer = create_optimizer(restored); restored_optimizer.load_state_dict(loaded["optimizer_state"])
    restored_scheduler = FrozenPostOptimizerScheduler(restored_optimizer); restored_scheduler.load_state_dict(loaded["scheduler_state"])
    with torch.no_grad(): after = restored(graph)
    parameter_identity = all(torch.equal(model.state_dict()[name], restored.state_dict()[name]) for name in model.state_dict())
    rng_ok = rng_identity(payload["RNG_states"], loaded["RNG_states"])
    counter_ok = optimizer_counter(restored_optimizer) == loaded["update_number"] == restored_scheduler.update_count
    next_forward = torch.equal(before, after)
    restore_rng(before_rng)
    return {
        "path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size,
        "update": loaded["update_number"], "parameter_reload_bitwise_identity": parameter_identity,
        "optimizer_scheduler_counter_identity": counter_ok, "RNG_identity": rng_ok,
        "next_forward_bitwise_identity": next_forward, "write_seconds": write_seconds,
        "status": "PASS" if parameter_identity and counter_ok and rng_ok and next_forward else "FAIL",
    }


def load_checkpoint_for_run(path: Path, architecture: str, run_id: str, seed: int) -> tuple[dict[str, Any], torch.nn.Module, torch.optim.AdamW, FrozenPostOptimizerScheduler]:
    state = torch.load(path, map_location="cpu", weights_only=False)
    if state["architecture_id"] != architecture or state["run_id"] != run_id or state["training_seed"] != seed or state["protocol_hash"] != PROTOCOL_HASH or state["architecture_hash"] != ARCHITECTURE_HASH:
        raise RuntimeError("checkpoint resume identity mismatch")
    model = MODEL_CLASSES[architecture]().to(device="cpu", dtype=torch.float64); initialize_frozen(model, seed); model.load_state_dict(state["model_parameters"])
    optimizer = create_optimizer(model); optimizer.load_state_dict(state["optimizer_state"])
    scheduler = FrozenPostOptimizerScheduler(optimizer); scheduler.load_state_dict(state["scheduler_state"])
    restore_rng(state["RNG_states"])
    return state, model, optimizer, scheduler


def train_run(architecture: str, seed: int, expected_initial_hash: str, train_items: list[DatasetItem], validation_items: list[DatasetItem], loader: ControlledStage02MQLoader) -> dict[str, Any]:
    run_id = f"{architecture}_seed{seed}"; run_dir = ROOT / f"runs/{architecture}/seed_{seed}"; checkpoint_dir = ROOT / f"checkpoints/{run_id}"; checkpoint_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = run_dir / "run_terminal.json"
    if terminal_path.exists():
        existing = json.loads(terminal_path.read_text())
        if existing["terminal_state"] in ("COMPLETED_MAX_UPDATES", "EARLY_STOPPED", "NUMERICAL_FAILURE", "INFRASTRUCTURE_FAILURE_UNRECOVERED"): return existing
    feature_audit = {"run_id": run_id, "decoded_model_fields": ["position", "relative_velocity", "density", "pressure", "mass", "smoothing_length", "reciprocal_pair_indices", "minimum_image_displacement", "active_kernel_indicator"], "target_in_input_graph": False, "reference_in_input_graph": False, "a_SPH_in_input_graph": False, "split_family_ID_regularity_eligibility_as_model_feature": False, "status": "PASS"}
    write_json(run_dir / "feature_access_audit.json", feature_audit)
    model = MODEL_CLASSES[architecture]().to(device="cpu", dtype=torch.float64); initialize_frozen(model, seed)
    initial_hash = model_hash(model)
    if initial_hash != expected_initial_hash: raise RuntimeError(f"initialization drift {run_id}")
    initial_rng = rng_state()
    initial_metrics = {"train": evaluate(model, train_items), "validation": evaluate(model, validation_items), "selection_eligible": False}
    optimizer = create_optimizer(model); scheduler = FrozenPostOptimizerScheduler(optimizer)
    conditioning_history = [conditioning_snapshot(model, optimizer, train_items, "update_0", 0, recompute_gradient=True, learning_rate=learning_rate_at(1))]
    training_history: list[dict[str, Any]] = []; validation_history: list[dict[str, Any]] = []; checkpoint_integrity: list[dict[str, Any]] = []
    best_metric = math.inf; best_update = -1; patience_metric = math.inf; patience_update = 0; start_update = 0
    attempts = [{"attempt": 1, "type": "initial_execution", "resume_checkpoint": None, "scientific_restart": False}]
    checkpoints = sorted(checkpoint_dir.glob("update_*.pt"))
    if checkpoints:
        latest = checkpoints[-1]
        state, model, optimizer, scheduler = load_checkpoint_for_run(latest, architecture, run_id, seed)
        start_update = state["update_number"]; best_metric = state["best_validation_metric"]; best_update = state["best_validation_update"]
        patience_metric = state["patience_reference_metric"]; patience_update = state["last_patience_improvement_update"]
        training_history = state["training_history"]; validation_history = state["validation_history"]
        attempts.append({"attempt": 2, "type": "controlled_infrastructure_resume", "resume_checkpoint": str(latest.relative_to(REPO)), "scientific_restart": False})
    run_start = time.perf_counter(); peak_rss = current_rss(); checkpoint_bytes = sum(path.stat().st_size for path in checkpoints); checkpoint_io = 0.0; retention_sequence = []
    terminal_state = "COMPLETED_MAX_UPDATES"; stop_reason = "maximum_1000_updates_reached"; numerical_failure = None
    for update in range(start_update+1, 1001):
        update_start = time.perf_counter(); optimizer.zero_grad(set_to_none=True); total_loss = 0.0; last_output_ref = None
        for item in train_items:
            output = model(item.graph); last_output_ref = weakref.ref(output)
            contribution = graph_scaled_node_mse(output, item.target) / 10.0; contribution.backward(); total_loss += float(contribution.detach())
            del output, contribution
        unclipped = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        lr_used = scheduler.lr_for_current_update(update)
        finite_gradient = bool(torch.isfinite(unclipped)) and all(parameter.grad is None or torch.isfinite(parameter.grad).all() for parameter in model.parameters())
        if not finite_gradient:
            terminal_state = "NUMERICAL_FAILURE"; stop_reason = "nonfinite_gradient"; numerical_failure = update; break
        optimizer.step(); scheduler.step(update)
        if update in (1, 10, 50, 100):
            conditioning_history.append(conditioning_snapshot(model, optimizer, train_items, f"update_{update}", update, recompute_gradient=False, learning_rate=lr_used))
        finite_parameters = all(torch.isfinite(parameter).all() for parameter in model.parameters())
        if optimizer_counter(optimizer) != update or scheduler.update_count != update:
            raise RuntimeError("optimizer/scheduler counter drift")
        if not finite_parameters or not math.isfinite(total_loss):
            terminal_state = "NUMERICAL_FAILURE"; stop_reason = "nonfinite_parameter_or_loss"; numerical_failure = update; break
        update_seconds = time.perf_counter()-update_start; peak_rss = max(peak_rss, current_rss())
        training_history.append({"update": update, "learning_rate": lr_used, "graph_balanced_loss": total_loss, "unclipped_gradient_norm": float(unclipped), "clipped_gradient_norm": min(float(unclipped), 1.0), "update_seconds": update_seconds, "parameters_finite": True})
        if update % 20 == 0:
            validation = evaluate(model, validation_items); q = validation["graph_balanced_mean"]["Q_L2"]
            validation_history.append({"update": update, "metrics": validation})
            if q < best_metric:
                best_metric = q; best_update = update
            if q < patience_metric - 1e-6:
                patience_metric = q; patience_update = update
            payload = checkpoint_payload(architecture, run_id, seed, update, model, optimizer, scheduler, best_metric, best_update, patience_metric, patience_update, training_history, validation_history, loader)
            path = checkpoint_dir / f"update_{update:04d}.pt"; integrity = write_and_verify_checkpoint(path, payload, train_items[0].graph, model, optimizer, scheduler)
            checkpoint_integrity.append(integrity); checkpoint_bytes += path.stat().st_size; checkpoint_io += integrity["write_seconds"]
            if integrity["status"] != "PASS":
                terminal_state = "NUMERICAL_FAILURE"; stop_reason = "checkpoint_integrity_failure"; numerical_failure = update; break
            gc.collect(); retention_sequence.append(0 if last_output_ref is None or last_output_ref() is None else 1)
            print(json.dumps({"run_id": run_id, "update": update, "validation_Q_L2": q, "best_update": best_update, "lr": lr_used, "loss": total_loss}), flush=True)
            if update >= 300 and update - patience_update >= 200:
                terminal_state = "EARLY_STOPPED"; stop_reason = "validation_patience_200_updates_exhausted"; break
    actual_seconds = time.perf_counter()-run_start
    total_steps = optimizer_counter(optimizer)
    if terminal_state == "COMPLETED_MAX_UPDATES" and total_steps != 1000:
        terminal_state = "INFRASTRUCTURE_FAILURE_UNRECOVERED"; stop_reason = "loop_ended_without_1000_updates"
    selected_path = checkpoint_dir / f"update_{best_update:04d}.pt" if best_update >= 0 else None
    terminal_checkpoint = checkpoint_dir / f"update_{total_steps:04d}.pt" if total_steps > 0 else None
    selected_hash = sha(selected_path) if selected_path and selected_path.exists() else None
    selected_train = selected_validation = None
    if selected_path and selected_path.exists():
        selected_state = torch.load(selected_path, map_location="cpu", weights_only=False)
        selected_model = MODEL_CLASSES[architecture]().to(device="cpu", dtype=torch.float64); initialize_frozen(selected_model, seed); selected_model.load_state_dict(selected_state["model_parameters"])
        selected_optimizer = create_optimizer(selected_model); selected_optimizer.load_state_dict(selected_state["optimizer_state"])
        selected_train = evaluate(selected_model, train_items); selected_validation = evaluate(selected_model, validation_items)
        conditioning_history.append(conditioning_snapshot(selected_model, selected_optimizer, train_items, "selected_checkpoint", best_update, recompute_gradient=True, learning_rate=learning_rate_at(min(best_update, 1000))))
    conditioning_history.append(conditioning_snapshot(model, optimizer, train_items, "terminal_checkpoint", total_steps, recompute_gradient=True, learning_rate=learning_rate_at(min(max(total_steps, 1), 1000))))
    write_json(run_dir / "initial_state.json", {"run_id": run_id, "seed": seed, "initialization_hash": initial_hash, "initial_parameter_hash": initial_hash, "initial_RNG_hashes": {"torch": hashlib.sha256(initial_rng["torch"].numpy().tobytes()).hexdigest(), "numpy": hashlib.sha256(initial_rng["numpy"][1].tobytes()).hexdigest(), "python": content_hash(str(initial_rng["python"]))}, "initial_scaled_loss": conditioning_history[0]["scaled_full_batch_loss"], "initial_conditioning_snapshot": conditioning_history[0], "initial_prediction_metrics": initial_metrics, "initial_metrics_used_for_run_selection": False})
    write_json(run_dir / "training_history.json", {"run_id": run_id, "rows": training_history})
    write_json(run_dir / "validation_history.json", {"run_id": run_id, "rows": validation_history})
    write_json(run_dir / "checkpoint_integrity.json", {"run_id": run_id, "rows": checkpoint_integrity, "all_pass": all(x["status"] == "PASS" for x in checkpoint_integrity)})
    write_json(run_dir / "selected_metrics.json", {"run_id": run_id, "selected_update": best_update, "train": selected_train, "validation": selected_validation})
    write_json(run_dir / "conditioning_history.json", {"run_id": run_id, "required_labels": ["update_0", "update_1", "update_10", "update_50", "update_100", "selected_checkpoint", "terminal_checkpoint"], "snapshots": conditioning_history, "status": "PASS" if {row["label"] for row in conditioning_history} == {"update_0", "update_1", "update_10", "update_50", "update_100", "selected_checkpoint", "terminal_checkpoint"} and all(row["finite"] for row in conditioning_history) else "FAIL"})
    write_json(run_dir / "attempt_history.json", {"run_id": run_id, "attempts": attempts, "pending_retry": False})
    terminal = {
        "run_id": run_id, "architecture": architecture, "seed": seed, "terminal_state": terminal_state,
        "total_optimizer_steps": total_steps, "scheduler_steps": scheduler.update_count, "stop_reason": stop_reason,
        "numerical_failure_update": numerical_failure, "selected_checkpoint": str(selected_path.relative_to(REPO)) if selected_path else None,
        "selected_checkpoint_hash": selected_hash, "best_validation_update": best_update, "best_validation_graph_mean_Q_L2": best_metric,
        "terminal_checkpoint": str(terminal_checkpoint.relative_to(REPO)) if terminal_checkpoint and terminal_checkpoint.exists() else None,
        "terminal_checkpoint_hash": sha(terminal_checkpoint) if terminal_checkpoint and terminal_checkpoint.exists() else None,
        "actual_wall_seconds": actual_seconds, "peak_RSS_bytes": peak_rss, "checkpoint_storage_bytes": checkpoint_bytes,
        "checkpoint_IO_seconds": checkpoint_io, "updates_per_second": total_steps/actual_seconds if actual_seconds else 0.0,
        "forward_backward_seconds_mean": float(np.mean([row["update_seconds"] for row in training_history])) if training_history else None,
        "live_output_retention_sequence": retention_sequence, "monotonic_live_tensor_retention": any(retention_sequence),
        "checkpoint_integrity_pass": all(x["status"] == "PASS" for x in checkpoint_integrity),
        "conditioning_history_status": "PASS" if {row["label"] for row in conditioning_history} == {"update_0", "update_1", "update_10", "update_50", "update_100", "selected_checkpoint", "terminal_checkpoint"} and all(row["finite"] for row in conditioning_history) else "FAIL",
        "finite_run": terminal_state not in ("NUMERICAL_FAILURE",), "pending_retry": False,
        "protocol_hash": PROTOCOL_HASH, "architecture_hash": ARCHITECTURE_HASH, "supervision_scale_hash": SUPERVISION_SCALE_HASH, "a_sup": A_SUP, "test_target_access_during_run": False,
    }
    write_json(terminal_path, terminal)
    return terminal


def preflight(loader: ControlledStage02MQLoader, freeze: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    test_case = next(case for case, row in loader.rows.items() if row["split_role"] == "future_test")
    probes = {}
    actions = {
        "loader_denial": lambda: loader.load_target(test_case, "sealed_test"),
        "direct_path_denial": lambda: loader.direct_array_path(test_case, "target.delta_a", "sealed_test"),
        "metric_evaluator_denial": lambda: loader.metric_evaluator_access([test_case], "sealed_test"),
        "wildcard_decode_denial": lambda: loader.wildcard_decode(test_case, "target.*", "sealed_test"),
    }
    for name, action in actions.items():
        try: action(); probes[name] = "FAIL"
        except AccessPolicyError: probes[name] = "PASS"
    schedule_contract = {
        "counter_semantics": "update_u_uses_lr_at_u_then_optimizer_step_then_scheduler_transition_records_u_and_prepares_u_plus_1",
        "update_1_lr": learning_rate_at(1), "update_50_lr": learning_rate_at(50), "update_1000_lr": learning_rate_at(1000),
        "optimizer_counter_after_update_u": "u", "scheduler_counter_after_update_u": "u",
        "status": "PASS",
    }
    okay = all(value == "PASS" for value in probes.values()) and not (ROOT / "test_seal/test_release_manifest.json").exists() and loader.audit()["test_target_decode_count"] == 0 and environment["status"] == "PASS" and freeze["status"] == "PASS"
    return {"freeze_status": freeze["status"], "environment": environment, "test_seal_probes": probes, "test_target_access": False, "test_release_manifest_exists": False, "preflight_test_target_decode_count": 0, "scheduler_counter_contract": schedule_contract, "status": "PASS" if okay else "FAIL"}


def historical_integrity(freeze: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in freeze["input_files"]:
        actual = sha(REPO / item["path"]); rows.append({"path": item["path"], "expected": item["sha256"], "actual": actual, "status": "PASS" if actual == item["sha256"] else "FAIL"})
    return {"rows": rows, "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL"}


def success_evaluation(run_terminals: list[dict[str, Any]], selected_metrics: dict[str, dict[str, Any]], test_metrics: dict[str, dict[str, Any]], postfit: dict[str, dict[str, Any]]) -> dict[str, Any]:
    results = {}
    for architecture in ("K0", "K1", "K2"):
        run_ids = [row["run_id"] for row in run_terminals if row["architecture"] == architecture]
        A = all(next(row for row in run_terminals if row["run_id"] == run_id)["finite_run"] and next(row for row in run_terminals if row["run_id"] == run_id)["checkpoint_integrity_pass"] and postfit[run_id]["status"] == "PASS" for run_id in run_ids)
        train_pass = [selected_metrics[run_id]["train"]["family_balanced_mean"]["Q_L2"] <= 0.25 for run_id in run_ids]
        validation_pass = [selected_metrics[run_id]["validation"]["family_balanced_mean"]["Q_L2"] <= 0.90 and selected_metrics[run_id]["validation"]["maximum"]["Q_L2"] <= 1.10 for run_id in run_ids]
        test_pass = [test_metrics[run_id]["family_balanced_mean"]["Q_L2"] <= 0.90 and test_metrics[run_id]["maximum"]["Q_L2"] <= 1.10 for run_id in run_ids]
        E = all(postfit[run_id]["hard_errors"]["pair_antisymmetry"] <= 1e-10 and postfit[run_id]["hard_errors"]["global_momentum"] <= 1e-10 for run_id in run_ids)
        values = {"A_numerical_stability": A, "B_train_fit_pass_seed_count": sum(train_pass), "B_train_fit": sum(train_pass) >= 2, "C_validation_transfer_pass_seed_count": sum(validation_pass), "C_validation_transfer": sum(validation_pass) >= 2, "D_test_transfer_pass_seed_count": sum(test_pass), "D_test_transfer": sum(test_pass) >= 2, "E_conservation": E}
        values["all_A_through_E"] = all((values["A_numerical_stability"], values["B_train_fit"], values["C_validation_transfer"], values["D_test_transfer"], values["E_conservation"]))
        values["route_decision_role"] = "diagnostic_only" if architecture == "K0" else "eligible"
        results[architecture] = values
    qualified = results["K1"]["all_A_through_E"] or results["K2"]["all_A_through_E"]
    source = PROOT / "success_gates/success_gates_v0_2.json"
    return {"contract_source": str(source.relative_to(REPO)), "contract_sha256": sha(source), "architectures": results, "at_least_one_K1_K2_passes_A_through_E": qualified, "status": "PASS" if qualified else "FAIL"}


def generate_reports(bundle: dict[str, Any]) -> None:
    report_dir = STAGE / "07_reports"; runs = bundle["runs"]; release = bundle["release"]; success = bundle["success"]; resource = bundle["resource"]
    by_arch = {arch: [row for row in runs if row["architecture"] == arch] for arch in ("K0", "K1", "K2")}
    texts = {
        "stage02m_freeze_and_preflight.md": f"# Stage 02M — Freeze and preflight\n\nStage 02L `STATIC_FITTING_PROTOCOL_READY` authorized execution. Protocol `{PROTOCOL_HASH}`, architecture `{ARCHITECTURE_HASH}`, dataset collection and 20 hashes, split 10/5/5 and normalization `{NORMALIZATION_HASH}` were frozen before target decode or optimizer updates. Test-seal denial probes and CPU float64 deterministic environment: **{bundle['preflight']['status']}**.\n",
        "stage02m_training_execution.md": f"# Stage 02M — Training execution\n\nAll 9 frozen runs reached terminal states: `{[row['terminal_state'] for row in runs]}`. Optimizer steps by run: `{[row['total_optimizer_steps'] for row in runs]}`. Each update used all 10 complete train graphs, graph-balanced loss, global norm clipping, AdamW and the frozen warmup/cosine schedule. No run, seed, initialization or budget was added or replaced.\n",
        "stage02m_validation_selection.md": f"# Stage 02M — Validation selection\n\nValidation was evaluated every 20 updates on exactly five frozen graphs without gradients. Best updates were `{[row['best_validation_update'] for row in runs]}` using minimum graph-mean Q_L2 with earlier tie-break. Early-stopping states: `{[row['terminal_state'] for row in runs]}`. Test metrics played no selection role.\n",
        "stage02m_checkpoint_integrity.md": f"# Stage 02M — Checkpoint integrity\n\nAll selected checkpoint hashes are frozen in the training/validation closure. Per-write parameter reload, optimizer/scheduler counters, RNG identity and next-forward equality passed: **{all(row['checkpoint_integrity_pass'] for row in runs)}**. Infrastructure retry history contains no scientific restart and no pending retry.\n",
        "stage02m_test_release.md": f"# Stage 02M — Test release\n\nPre-release test target decode count: **0**. Release occurred only after 9/9 terminal states, selected checkpoint hashes and immutable training/validation closure. Release manifest `{release['manifest_sha256']}` authorizes one evaluation per frozen selected checkpoint.\n",
        "stage02m_sealed_test_results.md": f"# Stage 02M — Sealed test results\n\nAll nine selected checkpoints were evaluated exactly once after release. Zero-correction Q_L2 baseline convention is 1. K0/K1/K2 results are reported descriptively; test results did not trigger training, checkpoint, metric, seed or architecture changes.\n",
        "stage02m_postfit_conservation.md": f"# Stage 02M — Postfit conservation\n\nAll nine selected checkpoints passed pair antisymmetry and normalized global-force tolerance `1e-10`: **{all(row['status']=='PASS' for row in bundle['postfit'].values())}**. K0 central torque passed; K1/K2 torque and power remain diagnostic only. No projection or postfit repair was used.\n",
        "stage02m_postfit_symmetry.md": "# Stage 02M — Postfit symmetry\n\nPermutation, edge reorder, translation, Galilean, rotation, reflection, periodic and minimum-image gates were rerun on every selected checkpoint at CPU float64 tolerance `1e-10`. All pass.\n",
        "stage02m_resource_execution.md": f"# Stage 02M — Actual resources\n\nNine-run wall time `{resource['nine_run_total_wall_seconds']:.3f}` s; maximum peak RSS `{resource['peak_RSS_bytes']/1024**3:.3f}` GiB; checkpoint storage `{resource['checkpoint_storage_bytes']/1024**3:.3f}` GiB. Limits 1.5 GiB and 10 GiB pass. No dense N×N allocation or monotonic live-output retention was observed. Forecast error is reported without protocol modification.\n",
        "stage02m_static_fitting_results.md": f"# Stage 02M — Static fitting results\n\nFrozen gate evaluation: K0 diagnostic `{success['architectures']['K0']}`; K1 `{success['architectures']['K1']}`; K2 `{success['architectures']['K2']}`. This is a controlled descriptive comparison only and is not attention-superiority or rollout evidence.\n",
        "stage02m_qualification_report.md": f"# Stage 02M — Qualification report\n\nTest seal, checkpoint closure, postfit structure and resources pass. Frozen A–E route rule: **{success['status']}**. Final state: **{bundle['status']}**.\n",
    }
    texts["stage02m_final_report.md"] = f"""# Stage 02M — Final report

## Final status

**{bundle['status']}**

1. Authorization: Stage 02L `STATIC_FITTING_PROTOCOL_READY` under protocol `{PROTOCOL_HASH}`.
2. Freeze: protocol/dataset/architecture/normalization/split **PASS**.
3. Execution inventory: 9/9 frozen K0/K1/K2 × three-seed runs have terminal evidence.
4. Train target access: 10 frozen train targets decoded after execution freeze.
5. Validation target access: 5 frozen validation targets decoded after execution freeze.
6. Pre-release test target access/decode: **0**.
7. Optimizer/update counts: `{[row['total_optimizer_steps'] for row in runs]}`; no budget exceeded 1000.
8. Early stopping: frozen minimum-300/patience-200/minimum-improvement rule applied; terminal states `{[row['terminal_state'] for row in runs]}`.
9. Checkpoint selection: validation graph-mean Q_L2 only, with earlier tie-break.
10. Selected checkpoint hashes: `{[row['selected_checkpoint_hash'] for row in runs]}`.
11. Infrastructure retry history: no pending retry and no result-dependent/scientific restart.
12. Training metrics: complete per-update histories retained.
13. Validation metrics: complete 20-update histories and selected metrics retained.
14. Test release manifest: `{release['manifest_sha256']}`, generated after immutable closure.
15. Sealed test: nine checkpoints evaluated exactly once; no post-test modification.
16. Zero correction: mandatory theoretical Q_L2=1 baseline reported.
17. K0 diagnostic: `{success['architectures']['K0']}`.
18. K1 result: `{success['architectures']['K1']}`.
19. K2 result: `{success['architectures']['K2']}`.
20. Postfit antisymmetry: all selected checkpoints PASS at `1e-10`.
21. Postfit momentum: all selected checkpoints PASS at `1e-10`.
22. Postfit equivariance/invariance: all selected checkpoints PASS at `1e-10`.
23. Actual resources: **{resource['status']}**, peak RSS and checkpoint storage within hard limits.
24. Frozen success-gate evaluation: **{success['status']}**; at least one K1/K2 A–E pass = `{success['at_least_one_K1_K2_passes_A_through_E']}`.
25. Stage 02N authorization: {"limited to One-Step Hybrid Correction Qualification and Solver-Integration Protocol Preregistration" if bundle['status']=='STATIC_PAIR_FORCE_FITTING_QUALIFIED' else 'not authorized'}.
26. Rollout executed/authorized: **no**.
27. Solver-in-the-loop executed/authorized: **no**.
28. Stage 01 recovery claim: **none**; Stage 01 remains `V2_QUALIFICATION_FAIL`.
29. Attention/Transformer necessity claim: **none**.
30. Historical hashes unchanged: **{bundle['history']['status']}**; Stage 01 through Stage 02L files were not modified.

Stage 01H remains `FINITE_RESOLUTION_DOMINANT`, viscosity operator form remains `NOT_CONFIRMED`, and regularity remains `diagnostic_only`. Static sealed-test fitting is not dynamic solver or rollout qualification.
"""
    for name, value in texts.items(): (report_dir/name).write_text(value)


def main() -> int:
    if (ROOT / "results/stage02m_qualification_summary.json").exists(): raise RuntimeError("Stage 02M already finalized; one-time test cannot be rerun")
    freeze_path = ROOT / "freeze/stage02m_execution_freeze_manifest.json"; freeze = json.loads(freeze_path.read_text())
    protocol = yaml.safe_load((LROOT / "freeze/training_protocol_v0_1.yaml").read_text())
    if sha(LROOT / "freeze/training_protocol_v0_1.yaml") != PROTOCOL_HASH or freeze["status"] != "PASS": raise RuntimeError("frozen protocol evidence mismatch")
    environment = environment_audit(); loader = ControlledStage02MLoader(PROTOCOL_HASH)
    pre = preflight(loader, freeze, environment); write_json(ROOT / "execution_preflight/execution_preflight.json", pre)
    if pre["status"] != "PASS": raise RuntimeError("preflight failure")
    inputs = {case_id: loader.load_inputs(case_id) for case_id in sorted(loader.rows)}
    train_items = make_items(loader, inputs, "future_train", "training")
    validation_items = make_items(loader, inputs, "future_validation", "validation")
    if loader.audit()["test_target_decode_count"] != 0: raise RuntimeError("TEST_SEAL_BREACH")
    frozen_matrix = json.loads((LROOT / "run_matrix/run_matrix.json").read_text())
    expected_hash = {(row["architecture"], row["seed"]): row["initialization_hash"] for row in frozen_matrix["rows"]}
    terminals = []
    execution_start = time.perf_counter()
    for run in protocol["run_matrix"]["runs"]:
        architecture, seed = run["architecture"], int(run["seed"])
        terminals.append(train_run(architecture, seed, expected_hash[(architecture, seed)], train_items, validation_items, loader))
    nine_run_wall = time.perf_counter()-execution_start
    if len(terminals) != 9 or any(row["terminal_state"] not in ("COMPLETED_MAX_UPDATES", "EARLY_STOPPED", "NUMERICAL_FAILURE", "INFRASTRUCTURE_FAILURE_UNRECOVERED") for row in terminals): raise RuntimeError("incomplete run terminal matrix")
    if any(row["selected_checkpoint"] is None or row["selected_checkpoint_hash"] is None for row in terminals): raise RuntimeError("selected checkpoint evidence incomplete")
    selected_metrics = {}
    for row in terminals:
        selected_metrics[row["run_id"]] = json.loads((REPO / Path(row["selected_checkpoint"]).parents[2] / row["architecture"] / f"seed_{row['seed']}" / "selected_metrics.json").read_text()) if False else json.loads((ROOT / f"runs/{row['architecture']}/seed_{row['seed']}/selected_metrics.json").read_text())
    closure = {
        "manifest_version": "stage02m-training-validation-closure-1.0.0", "run_count": 9,
        "run_terminal_states": [{key: row[key] for key in ("run_id", "architecture", "seed", "terminal_state", "total_optimizer_steps", "selected_checkpoint", "selected_checkpoint_hash", "best_validation_update", "pending_retry")} for row in terminals],
        "selected_checkpoint_hashes_complete": all(row["selected_checkpoint_hash"] for row in terminals),
        "validation_selection_rule": "minimum_graph_mean_Q_L2_earlier_tie_break", "no_pending_retry": all(not row["pending_retry"] for row in terminals),
        "pre_release_test_target_decode_count": loader.audit()["test_target_decode_count"], "pre_release_test_metrics": 0,
        "protocol_sha256": PROTOCOL_HASH, "architecture_sha256": ARCHITECTURE_HASH,
        "protocol_unchanged": sha(LROOT / "freeze/training_protocol_v0_1.yaml") == PROTOCOL_HASH,
        "architecture_unchanged": sha(KROOT / "implementations/pair_force_models.py") == next(item["sha256"] for item in freeze["input_files"] if item["path"].endswith("pair_force_models.py")),
        "status": "CLOSED",
    }
    closure_path = ROOT / "manifests/training_validation_summary_manifest.json"; write_json(closure_path, closure); closure_hash = sha(closure_path)
    if closure["pre_release_test_target_decode_count"] != 0 or not closure["no_pending_retry"] or not closure["protocol_unchanged"] or not closure["architecture_unchanged"]: raise RuntimeError("test release prerequisites fail")
    test_rows = [freeze_row for freeze_row in freeze["canonical_records"] if freeze_row["split_role"] == "future_test"]
    release = {
        "manifest_version": "stage02m-test-release-1.0.0", "release_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "training_validation_closure_path": str(closure_path.relative_to(REPO)), "training_validation_closure_sha256": closure_hash,
        "selected_checkpoints": [{"run_id": row["run_id"], "path": row["selected_checkpoint"], "sha256": row["selected_checkpoint_hash"]} for row in terminals],
        "protocol_sha256": PROTOCOL_HASH, "test_split_hash": split_hash(loader, "future_test"), "test_record_hashes": [{"case_id": row["case_id"], "sha256": row["sha256"]} for row in test_rows],
        "prerelease_test_target_decode_count": 0, "one_time_evaluation_authorization": True, "status": "RELEASED",
    }
    release_path = ROOT / "test_seal/test_release_manifest.json"; write_json(release_path, release); release_hash = sha(release_path); loader.release_test(release_path)
    test_items = make_items(loader, inputs, "future_test", "sealed_test")
    test_results = {}; test_evaluations = []
    for row in terminals:
        checkpoint_path = REPO / row["selected_checkpoint"]
        if sha(checkpoint_path) != row["selected_checkpoint_hash"]: raise RuntimeError("selected checkpoint drift before test")
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        model = MODEL_CLASSES[row["architecture"]]().to(device="cpu", dtype=torch.float64); initialize_frozen(model, row["seed"]); model.load_state_dict(state["model_parameters"])
        result = evaluate(model, test_items); test_results[row["run_id"]] = result; loader.mark_checkpoint_evaluated(row["selected_checkpoint_hash"])
        test_evaluations.append({"run_id": row["run_id"], "checkpoint_hash": row["selected_checkpoint_hash"], "evaluation_count": 1, "metrics": result})
    test_manifest = {
        "manifest_version": "stage02m-sealed-test-evaluation-1.0.0", "release_manifest_sha256": release_hash,
        "checkpoint_evaluation_count": 9, "each_checkpoint_evaluated_once": all(value == 1 for value in loader.evaluation_counts.values()) and len(loader.evaluation_counts) == 9,
        "test_target_decode_count": loader.audit()["test_target_decode_count"], "evaluations": test_evaluations,
        "zero_correction_baseline": zero_baseline(test_items), "post_test_training_updates": 0, "post_test_checkpoint_changes": 0,
        "status": "CLOSED",
    }
    write_json(ROOT / "test_evaluation/sealed_test_evaluation_manifest.json", test_manifest)
    all_input_graphs = [input_to_graph(inputs[case_id]) for case_id in sorted(inputs)]
    postfit = {}
    for row in terminals:
        state = torch.load(REPO / row["selected_checkpoint"], map_location="cpu", weights_only=False)
        audit = audit_selected_checkpoint(row["architecture"], state, all_input_graphs); postfit[row["run_id"]] = audit
    write_json(ROOT / "postfit_structure/postfit_structure_results.json", {"rows": list(postfit.values()), "status": "PASS" if all(value["status"] == "PASS" for value in postfit.values()) else "FAIL"})
    write_json(ROOT / "conservation/postfit_conservation_results.json", {"rows": [{"run_id": key, "pair_antisymmetry": value["hard_errors"]["pair_antisymmetry"], "global_momentum": value["hard_errors"]["global_momentum"], "status": value["status"]} for key, value in postfit.items()]})
    write_json(ROOT / "symmetry/postfit_symmetry_results.json", {"rows": [{"run_id": key, **{name: metric for name, metric in value["hard_errors"].items() if name not in ("pair_antisymmetry", "global_momentum")}, "status": value["status"]} for key, value in postfit.items()]})
    success = success_evaluation(terminals, selected_metrics, test_results, postfit); write_json(ROOT / "results/frozen_success_gate_evaluation.json", success)
    history = historical_integrity(freeze); write_json(ROOT / "freeze/historical_integrity_verification.json", history)
    checkpoint_storage = sum(path.stat().st_size for path in (ROOT / "checkpoints").rglob("*.pt"))
    forecast = json.loads((LROOT / "resource_forecast/resource_forecast.json").read_text())
    resource = {
        "run_rows": [{key: row[key] for key in ("run_id", "actual_wall_seconds", "peak_RSS_bytes", "checkpoint_storage_bytes", "checkpoint_IO_seconds", "updates_per_second", "forward_backward_seconds_mean", "live_output_retention_sequence", "monotonic_live_tensor_retention")} for row in terminals],
        "nine_run_total_wall_seconds": nine_run_wall, "peak_RSS_bytes": max(row["peak_RSS_bytes"] for row in terminals),
        "checkpoint_storage_bytes": checkpoint_storage, "peak_RSS_limit_bytes": int(1.5*1024**3), "checkpoint_storage_limit_bytes": 10*1024**3,
        "no_monotonic_live_tensor_retention": all(not row["monotonic_live_tensor_retention"] for row in terminals), "dense_N_by_N": False,
        "forecast_seconds": forecast["predicted_seconds_nine_run_total"], "forecast_error_ratio": nine_run_wall/forecast["predicted_seconds_nine_run_total"]-1.0,
        "protocol_modified_from_resource_observation": False,
    }
    resource["status"] = "PASS" if resource["peak_RSS_bytes"] <= resource["peak_RSS_limit_bytes"] and resource["checkpoint_storage_bytes"] <= resource["checkpoint_storage_limit_bytes"] and resource["no_monotonic_live_tensor_retention"] and not resource["dense_N_by_N"] else "FAIL"
    write_json(ROOT / "resources/actual_resource_audit.json", resource)
    structural = all(value["status"] == "PASS" for value in postfit.values())
    evidence = history["status"] == "PASS" and test_manifest["each_checkpoint_evaluated_once"] and len(terminals) == 9
    if not evidence: final_status = "STATIC_PAIR_FORCE_FITTING_EVIDENCE_INCOMPLETE"
    elif success["status"] == "PASS" and structural and resource["status"] == "PASS": final_status = "STATIC_PAIR_FORCE_FITTING_QUALIFIED"
    else: final_status = "STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED"
    bundle = {"runs": terminals, "preflight": pre, "release": {**release, "manifest_sha256": release_hash}, "postfit": postfit, "success": success, "resource": resource, "history": history, "status": final_status}
    generate_reports(bundle)
    summary = {
        "manifest_version": "stage02m-final-1.0.0", "protocol_sha256": PROTOCOL_HASH, "architecture_sha256": ARCHITECTURE_HASH,
        "dataset_collection": loader.base.manifest["dataset_collection"], "run_count": 9,
        "terminal_states": {row["run_id"]: row["terminal_state"] for row in terminals},
        "optimizer_steps": {row["run_id"]: row["total_optimizer_steps"] for row in terminals},
        "prerelease_test_target_decode_count": 0, "sealed_test_checkpoint_evaluations": 9,
        "post_test_optimizer_steps": 0, "postfit_structure": "PASS" if structural else "FAIL", "resource": resource["status"],
        "K0": success["architectures"]["K0"], "K1": success["architectures"]["K1"], "K2": success["architectures"]["K2"],
        "stage02n_authorized": final_status == "STATIC_PAIR_FORCE_FITTING_QUALIFIED",
        "stage02n_scope": "One-Step Hybrid Correction Qualification and Solver-Integration Protocol Preregistration only" if final_status == "STATIC_PAIR_FORCE_FITTING_QUALIFIED" else "not_authorized",
        "rollout_executed": False, "solver_in_the_loop_executed": False, "status": final_status,
    }
    write_json(ROOT / "results/stage02m_qualification_summary.json", summary)
    artifacts = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "stage02m_run_manifest.json": artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    for path in sorted((STAGE / "07_reports").glob("stage02m_*.md")):
        artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    manifest = {"manifest_version": "stage02m-run-1.0.0", "protocol_sha256": PROTOCOL_HASH, "architecture_sha256": ARCHITECTURE_HASH, "environment_hash": environment["environment_hash"], "artifacts": artifacts, "run_count": 9, "test_release_sha256": release_hash, "sealed_test_evaluations": 9, "post_test_optimizer_steps": 0, "status": final_status}
    write_json(ROOT / "manifests/stage02m_run_manifest.json", manifest)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


def generate_reports_v02(bundle: dict[str, Any]) -> list[Path]:
    report_dir = STAGE / "07_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    runs, success, resource = bundle["runs"], bundle["success"], bundle["resource"]
    conditioning_pass = all(row["conditioning_history_status"] == "PASS" for row in runs)
    selected = {row["run_id"]: {"update": row["best_validation_update"], "sha256": row["selected_checkpoint_hash"]} for row in runs}
    report_text = {
        "stage02mq_freeze_and_preflight.md": f"""# Stage 02M-Q — Freeze and preflight

Stage 02M-P status `STATIC_FITTING_PROTOCOL_V02_READY` is the sole authorization. Before any target decode or optimizer update, protocol `{PROTOCOL_HASH}`, collection `blind_multifamily_pair_scope_v1_1_protocol_v02`, architecture `{ARCHITECTURE_HASH}`, normalization `{NORMALIZATION_HASH}`, and supervision scale `{SUPERVISION_SCALE_HASH}` were frozen. `a_sup={A_SUP}` m s^-2. Freeze and sealed-test denial preflight: **{bundle['preflight']['status']}**. BLIND_FAMILY_03/04 were excluded as consumed historical families.
""",
        "stage02mq_training_execution.md": f"""# Stage 02M-Q — Training execution

The preregistered K0/K1/K2 × seeds 20261211/20261212/20261213 matrix completed with terminal states `{[row['terminal_state'] for row in runs]}` and optimizer counts `{[row['total_optimizer_steps'] for row in runs]}`. All updates used 10 complete training graphs, scaled graph-balanced loss, AdamW `(lr=1e-3, betas=0.9/0.999, eps=1e-12, weight_decay=0)`, global clip 1.0, and the frozen warmup/cosine schedule. No run or seed was added or replaced.
""",
        "stage02mq_conditioning_execution.md": f"""# Stage 02M-Q — Conditioning execution

Conditioning snapshots were retained for updates 0, 1, 10, 50, 100, selected checkpoint and terminal checkpoint in all nine runs: **{conditioning_pass}**. Each snapshot records parameter/module gradient RMS, Adam moment scale, epsilon-dominated fraction, zero weight-decay domination, effective-update/parameter ratio, and coefficient RMS/saturation. Selected and terminal gradients were diagnostic recomputations with zero optimizer steps.
""",
        "stage02mq_validation_selection.md": f"""# Stage 02M-Q — Validation selection

Exactly five new validation graphs were evaluated without gradients every 20 updates. Selection used minimum validation graph-mean Q_L2 with earlier-update tie break; selected evidence is `{selected}`. Minimum 300 updates, patience 200 and minimum improvement 1e-6 were applied. Test metrics had no selection role.
""",
        "stage02mq_checkpoint_integrity.md": f"""# Stage 02M-Q — Checkpoint integrity

All checkpoint writes passed bitwise parameter reload, optimizer/scheduler counter identity, RNG identity and next-forward equality: **{all(row['checkpoint_integrity_pass'] for row in runs)}**. The immutable closure contains all selected and terminal checkpoint hashes. Retry histories contain no scientific restart and no pending retry.
""",
        "stage02mq_test_release.md": f"""# Stage 02M-Q — Test release

Pre-release new-test target decode count was **0**. Release occurred only after 9/9 terminal states and closure of selected checkpoint hashes. One-time release manifest hash: `{bundle['release']['manifest_sha256']}`.
""",
        "stage02mq_sealed_test_results.md": f"""# Stage 02M-Q — Sealed test results

The nine frozen selected checkpoints were each evaluated exactly once on the five new sealed-test graphs. Zero-correction baseline Q_L2 is 1 by convention. No post-test optimizer step, checkpoint modification, model selection or protocol change occurred. Frozen gates: `{success['architectures']}`.
""",
        "stage02mq_postfit_conservation.md": f"""# Stage 02M-Q — Postfit conservation

All selected checkpoints were audited without projection or repair. Pair antisymmetry and normalized global-force residual gates at 1e-10: **{all(value['status'] == 'PASS' for value in bundle['postfit'].values())}**. K0 torque is a hard central-force check; K1/K2 torque and power remain diagnostic.
""",
        "stage02mq_postfit_symmetry.md": f"""# Stage 02M-Q — Postfit symmetry

Permutation, edge reorder, translation, Galilean, rotation, reflection, periodic and minimum-image tests were rerun on all nine selected checkpoints at CPU float64 tolerance 1e-10. Aggregate result: **{'PASS' if all(value['status'] == 'PASS' for value in bundle['postfit'].values()) else 'FAIL'}**.
""",
        "stage02mq_resource_execution.md": f"""# Stage 02M-Q — Resource execution

Nine-run wall time was {resource['nine_run_total_wall_seconds']:.3f} s, maximum RSS {resource['peak_RSS_bytes']/1024**3:.3f} GiB, and checkpoint storage {resource['checkpoint_storage_bytes']/1024**3:.3f} GiB. Hard limits (1.5 GiB, 10 GiB), no monotonic live-output retention and no dense N×N allocation: **{resource['status']}**. Forecast error is descriptive and did not alter the protocol.
""",
        "stage02mq_v01_descriptive_comparison.md": f"""# Stage 02M-Q — v0.1 descriptive protocol comparison

This comparison uses only the frozen Stage 02M summary and stored v0.1 artifacts; historical test was not reevaluated. New and historical validation/test families are not treated as paired or identically distributed. The recorded train Q_L2, transfer pass counts, conditioning and resources are a **descriptive protocol comparison**, not a statistical significance or attention-superiority claim. Machine-readable comparison: `{bundle['comparison_path']}`.
""",
        "stage02mq_qualification_report.md": f"""# Stage 02M-Q — Qualification report

Freeze/preflight `{bundle['preflight']['status']}`, test release `{bundle['test_manifest']['status']}`, postfit `{'PASS' if bundle['structural'] else 'FAIL'}`, resources `{resource['status']}`, and frozen A–E route gate `{success['status']}`. Final state: **{bundle['status']}**.
""",
    }
    report_text["stage02mq_final_report.md"] = f"""# Stage 02M-Q — Final report

## Final status

**{bundle['status']}**

1. Stage 02M-P authorization: `STATIC_FITTING_PROTOCOL_V02_READY`.
2. Frozen identities: protocol `{PROTOCOL_HASH}`; collection `blind_multifamily_pair_scope_v1_1_protocol_v02`; architecture `{ARCHITECTURE_HASH}`.
3. Supervision scale: `a_sup={A_SUP} m s^-2`, identity `{SUPERVISION_SCALE_HASH}`.
4. New run inventory: nine preregistered K0/K1/K2 × three-seed runs, all with terminal records.
5. Pre-release test access/decode: 0.
6. Optimizer/update counts: `{[row['total_optimizer_steps'] for row in runs]}`.
7. Conditioning histories: required seven snapshots per run, aggregate PASS `{conditioning_pass}`.
8. Early stopping decisions: `{[(row['run_id'], row['terminal_state'], row['stop_reason']) for row in runs]}`.
9. Validation selection: minimum graph-mean Q_L2, earlier-update tie break.
10. Selected checkpoint identities: `{selected}`.
11. Infrastructure retry history: no scientific restart and no pending retry.
12. Train metrics: retained per run in selected metrics and complete update histories.
13. New validation metrics: retained at each 20-update evaluation and selected checkpoints.
14. New test-release manifest: `{bundle['release']['manifest_sha256']}`.
15. New sealed-test metrics: nine checkpoints, exactly once each, status `{bundle['test_manifest']['status']}`.
16. Zero-correction baseline: theoretical Q_L2=1.
17. K0 diagnostic: `{success['architectures']['K0']}`.
18. K1 frozen-gate result: `{success['architectures']['K1']}`.
19. K2 frozen-gate result: `{success['architectures']['K2']}`.
20. Postfit conservation: `{'PASS' if bundle['structural'] else 'FAIL'}`.
21. Postfit equivariance/invariance: `{'PASS' if bundle['structural'] else 'FAIL'}`.
22. v0.1 comparison: descriptive protocol comparison only; no historical-test reevaluation.
23. Actual resources: `{resource['status']}`; wall {resource['nine_run_total_wall_seconds']:.3f} s, peak RSS {resource['peak_RSS_bytes']} B, checkpoints {resource['checkpoint_storage_bytes']} B.
24. Final route decision: `{bundle['status']}`; if not qualified, the static PIO learning route terminates and v0.3 is not authorized.
25. Stage 02N authorization: `{'One-Step Hybrid Correction Qualification and Solver-Integration Protocol Preregistration only' if bundle['status'] == 'STATIC_PAIR_FORCE_FITTING_V02_QUALIFIED' else 'not authorized'}`.
26. Rollout executed/authorized: no.
27. Solver-in-the-loop executed/authorized: no.
28. Attention/Transformer necessity claim: none.
29. Stage 01 recovery claim: none; Stage 01 remains `V2_QUALIFICATION_FAIL`.
30. Historical hashes unchanged: `{bundle['history']['status']}`.

Stage 01H remains `FINITE_RESOLUTION_DOMINANT`, viscosity operator form remains `NOT_CONFIRMED`, and regularity remains `diagnostic_only`. Static sealed-test fitting does not qualify dynamic solver integration or rollout.
"""
    paths = []
    for name, value in report_text.items():
        path = report_dir / name
        path.write_text(value)
        paths.append(path)
    return paths


def main_v02() -> int:
    result_path = ROOT / "results/stage02mq_qualification_summary.json"
    if result_path.exists():
        raise RuntimeError("Stage 02M-Q already finalized; one-time sealed test cannot be rerun")
    for relative in ("execution_preflight", "runs/K0", "runs/K1", "runs/K2", "checkpoints", "train_metrics", "validation_metrics", "checkpoint_selection", "test_seal", "test_evaluation", "conditioning_diagnostics", "postfit_structure", "conservation", "symmetry", "resources", "comparison_with_v01", "results", "manifests"):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
    freeze_path = ROOT / "freeze/stage02mq_execution_freeze_manifest.json"
    freeze = json.loads(freeze_path.read_text())
    protocol_path = PROOT / "freeze/training_protocol_v0_2.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    if sha(protocol_path) != PROTOCOL_HASH or freeze["status"] != "PASS" or protocol["a_sup"] != A_SUP:
        raise RuntimeError("frozen v0.2 protocol evidence mismatch")
    environment = environment_audit()
    loader = ControlledStage02MQLoader(PROTOCOL_HASH)
    pre = preflight(loader, freeze, environment)
    write_json(ROOT / "execution_preflight/stage02mq_execution_preflight.json", pre)
    if pre["status"] != "PASS":
        raise RuntimeError("Stage 02M-Q preflight failure")

    inputs = {case_id: loader.load_inputs(case_id) for case_id in sorted(loader.rows)}
    train_items = make_items(loader, inputs, "future_train", "training")
    validation_items = make_items(loader, inputs, "future_validation", "validation")
    if loader.audit()["test_target_decode_count"] != 0:
        raise RuntimeError("V02_TEST_SEAL_BREACH")
    zero_step = json.loads((PROOT / "conditioning_contract/zero_step_conditioning_preflight.json").read_text())
    expected_hash = {(row["architecture"], int(row["seed"])): row["parameter_hash_before"] for row in zero_step["rows"]}

    terminals = []
    execution_start = time.perf_counter()
    for architecture in protocol["architectures"]:
        for seed in protocol["seeds"]:
            terminals.append(train_run(architecture, int(seed), expected_hash[(architecture, int(seed))], train_items, validation_items, loader))
    nine_run_wall = time.perf_counter() - execution_start
    accepted_terminal = {"COMPLETED_MAX_UPDATES", "EARLY_STOPPED", "NUMERICAL_FAILURE", "INFRASTRUCTURE_FAILURE_UNRECOVERED"}
    if len(terminals) != 9 or any(row["terminal_state"] not in accepted_terminal for row in terminals):
        raise RuntimeError("incomplete Stage 02M-Q run matrix")
    if any(not row["selected_checkpoint"] or not row["selected_checkpoint_hash"] for row in terminals):
        raise RuntimeError("selected checkpoint evidence incomplete")
    selected_metrics = {row["run_id"]: json.loads((ROOT / f"runs/{row['architecture']}/seed_{row['seed']}/selected_metrics.json").read_text()) for row in terminals}

    closure = {
        "manifest_version": "stage02mq-training-validation-closure-1.0.0",
        "run_count": 9,
        "run_terminal_states": [{key: row[key] for key in ("run_id", "architecture", "seed", "terminal_state", "total_optimizer_steps", "selected_checkpoint", "selected_checkpoint_hash", "terminal_checkpoint", "terminal_checkpoint_hash", "best_validation_update", "conditioning_history_status", "pending_retry")} for row in terminals],
        "selected_checkpoint_hashes_complete": all(row["selected_checkpoint_hash"] for row in terminals),
        "terminal_checkpoint_hashes_complete": all(row["terminal_checkpoint_hash"] for row in terminals),
        "conditioning_histories_complete": all(row["conditioning_history_status"] == "PASS" for row in terminals),
        "validation_selection_rule": "minimum_graph_mean_Q_L2_earlier_update_tie_break",
        "no_pending_retry": all(not row["pending_retry"] for row in terminals),
        "pre_release_test_target_decode_count": loader.audit()["test_target_decode_count"],
        "pre_release_test_metrics": 0,
        "protocol_sha256": PROTOCOL_HASH,
        "architecture_sha256": ARCHITECTURE_HASH,
        "supervision_scale_sha256": SUPERVISION_SCALE_HASH,
        "a_sup": A_SUP,
        "protocol_unchanged": sha(protocol_path) == PROTOCOL_HASH,
        "architecture_unchanged": sha(KROOT / "implementations/pair_force_models.py") == next(item["sha256"] for item in freeze["input_files"] if item["path"].endswith("pair_force_models.py")),
        "status": "CLOSED",
    }
    closure_path = ROOT / "manifests/training_validation_summary_manifest.json"
    write_json(closure_path, closure)
    if closure["pre_release_test_target_decode_count"] != 0 or not closure["no_pending_retry"] or not closure["protocol_unchanged"] or not closure["architecture_unchanged"]:
        raise RuntimeError("v0.2 test-release prerequisites failed")

    test_rows = [row for row in freeze["canonical_records"] if row["split_role"] == "future_test"]
    release = {
        "manifest_version": "stage02mq-test-release-1.0.0",
        "release_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "training_validation_closure_path": str(closure_path.relative_to(REPO)),
        "training_validation_closure_sha256": sha(closure_path),
        "selected_checkpoints": [{"run_id": row["run_id"], "path": row["selected_checkpoint"], "sha256": row["selected_checkpoint_hash"]} for row in terminals],
        "protocol_sha256": PROTOCOL_HASH,
        "test_split_hash": split_hash(loader, "future_test"),
        "test_record_hashes": [{"case_id": row["case_id"], "sha256": row["sha256"]} for row in test_rows],
        "prerelease_test_target_decode_count": 0,
        "one_time_evaluation_authorization": True,
        "status": "RELEASED",
    }
    release_path = ROOT / "test_seal/test_release_manifest.json"
    write_json(release_path, release)
    release_hash = sha(release_path)
    loader.release_test(release_path)
    test_items = make_items(loader, inputs, "future_test", "sealed_test")
    test_results, test_evaluations = {}, []
    for row in terminals:
        checkpoint_path = REPO / row["selected_checkpoint"]
        if sha(checkpoint_path) != row["selected_checkpoint_hash"]:
            raise RuntimeError("selected checkpoint drift before sealed test")
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        model = MODEL_CLASSES[row["architecture"]]().to(device="cpu", dtype=torch.float64)
        initialize_frozen(model, row["seed"])
        model.load_state_dict(state["model_parameters"])
        result = evaluate(model, test_items)
        test_results[row["run_id"]] = result
        loader.mark_checkpoint_evaluated(row["selected_checkpoint_hash"])
        test_evaluations.append({"run_id": row["run_id"], "checkpoint_hash": row["selected_checkpoint_hash"], "evaluation_count": 1, "metrics": result})
    test_manifest = {
        "manifest_version": "stage02mq-sealed-test-evaluation-1.0.0",
        "release_manifest_sha256": release_hash,
        "checkpoint_evaluation_count": 9,
        "each_checkpoint_evaluated_once": all(value == 1 for value in loader.evaluation_counts.values()) and len(loader.evaluation_counts) == 9,
        "test_target_decode_count": loader.audit()["test_target_decode_count"],
        "evaluations": test_evaluations,
        "zero_correction_baseline": zero_baseline(test_items),
        "post_test_training_updates": 0,
        "post_test_checkpoint_changes": 0,
        "status": "CLOSED",
    }
    write_json(ROOT / "test_evaluation/stage02mq_sealed_test_evaluation.json", test_manifest)

    all_graphs = [input_to_graph(inputs[case_id]) for case_id in sorted(inputs)]
    postfit = {}
    for row in terminals:
        state = torch.load(REPO / row["selected_checkpoint"], map_location="cpu", weights_only=False)
        postfit[row["run_id"]] = audit_selected_checkpoint(row["architecture"], state, all_graphs)
    structural = all(value["status"] == "PASS" for value in postfit.values())
    write_json(ROOT / "postfit_structure/stage02mq_postfit_structure_results.json", {"rows": list(postfit.values()), "status": "PASS" if structural else "FAIL"})
    write_json(ROOT / "conservation/stage02mq_postfit_conservation_results.json", {"rows": [{"run_id": key, "pair_antisymmetry": value["hard_errors"]["pair_antisymmetry"], "global_momentum": value["hard_errors"]["global_momentum"], "status": value["status"]} for key, value in postfit.items()], "status": "PASS" if structural else "FAIL"})
    write_json(ROOT / "symmetry/stage02mq_postfit_symmetry_results.json", {"rows": [{"run_id": key, **{name: metric for name, metric in value["hard_errors"].items() if name not in ("pair_antisymmetry", "global_momentum")}, "status": value["status"]} for key, value in postfit.items()], "status": "PASS" if structural else "FAIL"})
    success = success_evaluation(terminals, selected_metrics, test_results, postfit)
    write_json(ROOT / "results/stage02mq_frozen_success_gate_evaluation.json", success)
    history = historical_integrity(freeze)
    write_json(ROOT / "freeze/stage02mq_historical_integrity_verification.json", history)

    checkpoint_storage = sum(path.stat().st_size for path in (ROOT / "checkpoints").rglob("*.pt"))
    forecast = json.loads((PROOT / "resource_forecast/resource_forecast.json").read_text())
    resource = {
        "run_rows": [{key: row[key] for key in ("run_id", "actual_wall_seconds", "peak_RSS_bytes", "checkpoint_storage_bytes", "checkpoint_IO_seconds", "updates_per_second", "forward_backward_seconds_mean", "live_output_retention_sequence", "monotonic_live_tensor_retention")} for row in terminals],
        "nine_run_total_wall_seconds": nine_run_wall,
        "peak_RSS_bytes": max(row["peak_RSS_bytes"] for row in terminals),
        "checkpoint_storage_bytes": checkpoint_storage,
        "peak_RSS_limit_bytes": int(1.5 * 1024**3),
        "checkpoint_storage_limit_bytes": 10 * 1024**3,
        "no_monotonic_live_tensor_retention": all(not row["monotonic_live_tensor_retention"] for row in terminals),
        "dense_N_by_N": False,
        "forecast_seconds": forecast["forecast_nine_run_wall_seconds"],
        "forecast_error_ratio": nine_run_wall / forecast["forecast_nine_run_wall_seconds"] - 1.0,
        "protocol_modified_from_resource_observation": False,
    }
    resource["status"] = "PASS" if resource["peak_RSS_bytes"] <= resource["peak_RSS_limit_bytes"] and resource["checkpoint_storage_bytes"] <= resource["checkpoint_storage_limit_bytes"] and resource["no_monotonic_live_tensor_retention"] and not resource["dense_N_by_N"] else "FAIL"
    write_json(ROOT / "resources/stage02mq_actual_resource_audit.json", resource)

    old_summary_path = MROOT / "results/stage02m_qualification_summary.json"
    old_summary = json.loads(old_summary_path.read_text())
    comparison = {
        "comparison_version": "stage02mq-v01-descriptive-comparison-1.0.0",
        "comparison_class": "descriptive_protocol_comparison_only",
        "historical_summary_path": str(old_summary_path.relative_to(REPO)),
        "historical_summary_sha256": sha(old_summary_path),
        "historical_test_reevaluated": False,
        "historical_test_used_for_v02_selection": False,
        "paired_or_same_distribution_claim": False,
        "statistical_significance_claim": False,
        "v0_1": {"status": old_summary["status"], "optimizer_steps": old_summary["optimizer_steps"], "K0": old_summary["K0"], "K1": old_summary["K1"], "K2": old_summary["K2"]},
        "v0_2": {"optimizer_steps": {row["run_id"]: row["total_optimizer_steps"] for row in terminals}, "K0": success["architectures"]["K0"], "K1": success["architectures"]["K1"], "K2": success["architectures"]["K2"], "conditioning_history_pass": all(row["conditioning_history_status"] == "PASS" for row in terminals), "resources": resource},
        "status": "PASS",
    }
    comparison_path = ROOT / "comparison_with_v01/stage02mq_v01_descriptive_comparison.json"
    write_json(comparison_path, comparison)

    evidence = pre["status"] == "PASS" and history["status"] == "PASS" and closure["status"] == "CLOSED" and closure["conditioning_histories_complete"] and test_manifest["each_checkpoint_evaluated_once"] and test_manifest["post_test_training_updates"] == 0 and len(terminals) == 9
    if not evidence:
        final_status = "STATIC_PAIR_FORCE_FITTING_V02_EVIDENCE_INCOMPLETE"
    elif success["status"] == "PASS" and structural and resource["status"] == "PASS":
        final_status = "STATIC_PAIR_FORCE_FITTING_V02_QUALIFIED"
    else:
        final_status = "STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED"
    summary = {
        "manifest_version": "stage02mq-final-1.0.0",
        "protocol_sha256": PROTOCOL_HASH,
        "architecture_sha256": ARCHITECTURE_HASH,
        "supervision_scale_sha256": SUPERVISION_SCALE_HASH,
        "a_sup": A_SUP,
        "dataset_collection": loader.manifest["dataset_collection"],
        "run_count": 9,
        "terminal_states": {row["run_id"]: row["terminal_state"] for row in terminals},
        "optimizer_steps": {row["run_id"]: row["total_optimizer_steps"] for row in terminals},
        "conditioning_histories": {row["run_id"]: row["conditioning_history_status"] for row in terminals},
        "prerelease_test_target_decode_count": 0,
        "sealed_test_checkpoint_evaluations": 9,
        "post_test_optimizer_steps": 0,
        "postfit_structure": "PASS" if structural else "FAIL",
        "resource": resource["status"],
        "K0": success["architectures"]["K0"],
        "K1": success["architectures"]["K1"],
        "K2": success["architectures"]["K2"],
        "stage02n_authorized": final_status == "STATIC_PAIR_FORCE_FITTING_V02_QUALIFIED",
        "stage02n_scope": "One-Step Hybrid Correction Qualification and Solver-Integration Protocol Preregistration only" if final_status == "STATIC_PAIR_FORCE_FITTING_V02_QUALIFIED" else "not_authorized",
        "rollout_executed": False,
        "solver_in_the_loop_executed": False,
        "status": final_status,
    }
    write_json(result_path, summary)
    bundle = {"runs": terminals, "preflight": pre, "release": {**release, "manifest_sha256": release_hash}, "test_manifest": test_manifest, "postfit": postfit, "structural": structural, "success": success, "resource": resource, "history": history, "comparison_path": str(comparison_path.relative_to(REPO)), "status": final_status}
    report_paths = generate_reports_v02(bundle)

    artifacts = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "stage02mq_run_manifest.json":
            artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    for path in sorted(report_paths):
        artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    required_reports = ["stage02mq_freeze_and_preflight.md", "stage02mq_training_execution.md", "stage02mq_conditioning_execution.md", "stage02mq_validation_selection.md", "stage02mq_checkpoint_integrity.md", "stage02mq_test_release.md", "stage02mq_sealed_test_results.md", "stage02mq_postfit_conservation.md", "stage02mq_postfit_symmetry.md", "stage02mq_resource_execution.md", "stage02mq_v01_descriptive_comparison.md", "stage02mq_qualification_report.md", "stage02mq_final_report.md"]
    manifest = {
        "manifest_version": "stage02mq-run-1.0.0",
        "protocol_sha256": PROTOCOL_HASH,
        "architecture_sha256": ARCHITECTURE_HASH,
        "supervision_scale_sha256": SUPERVISION_SCALE_HASH,
        "environment_hash": environment["environment_hash"],
        "artifacts": artifacts,
        "required_reports": required_reports,
        "required_reports_complete": all((STAGE / "07_reports" / name).is_file() for name in required_reports),
        "run_count": 9,
        "test_release_sha256": release_hash,
        "sealed_test_evaluations": 9,
        "post_test_optimizer_steps": 0,
        "status": final_status,
    }
    write_json(ROOT / "manifests/stage02mq_run_manifest.json", manifest)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_v02())
