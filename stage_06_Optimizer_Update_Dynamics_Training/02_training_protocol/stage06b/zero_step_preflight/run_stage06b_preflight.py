"""Execute nine zero-step forward/gradient/checkpoint preflights without update."""

from __future__ import annotations

import gc
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

HERE = Path(__file__).resolve(); STAGE06B = HERE.parents[1]; STAGE06 = HERE.parents[3]; ROOT = HERE.parents[4]


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None; sys.modules[name] = module; spec.loader.exec_module(module); return module


H = import_path("stage06b_harness", STAGE06B / "training_harness/stage06b_harness.py")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def rng_payload() -> dict[str, Any]:
    return {"torch": torch.get_rng_state(), "numpy": np.random.get_state(), "python": random.getstate()}


def restore_rng(value: dict[str, Any]) -> None:
    torch.set_rng_state(value["torch"]); np.random.set_state(value["numpy"]); random.setstate(value["python"])


def next_rng_identity() -> dict[str, Any]:
    return {"torch": torch.rand(4).tolist(), "numpy": np.random.random(4).tolist(), "python": [random.random() for _ in range(4)]}


def main() -> None:
    torch.set_num_threads(1); torch.set_default_dtype(torch.float64)
    process = psutil.Process(); rss_start = process.memory_info().rss; rss_peak = rss_start; started = time.perf_counter()
    protocol = json.loads((STAGE06B / "manifests/stage06b_protocol_manifest.json").read_text())
    runs = json.loads((STAGE06B / "model_seed_schedule/formal_model_seed_schedule.json").read_text())["runs"]
    validation_manifest = json.loads((STAGE06 / "09_manifests/stage06b_validation_manifest.json").read_text()); assert validation_manifest["pass"]
    train_cases, train_inventory = H.materialize_train_batch_zero(); validation_cases = H.load_validation_cases()
    rows = []; checkpoint_sizes = []
    counters = {"model_instances": 0, "optimizer_instances": 0, "scheduler_instances": 0, "train_forwards": 0,
                "validation_forwards": 0, "full_gradients": 0, "checkpoint_serializations": 0, "checkpoint_reloads": 0,
                "formal_optimizer_steps": 0, "formal_parameter_updates": 0, "formal_training_runs": 0,
                "sealed_test_evaluations": 0, "neural_rollouts": 0, "performance_evaluations": 0}
    for run in runs:
        arm, seed = run["arm"], run["formal_seed"]; run_id = run["run_id"]
        model, adapter = H.fresh(arm, seed, run["initial_parameter_sha256"]); counters["model_instances"] += 1
        model.train(); before = H.Q.parameter_hash(model); t0 = time.perf_counter()
        with sdpa_kernel(SDPBackend.MATH): train_loss = adapter(train_cases)
        train_seconds = time.perf_counter() - t0; counters["train_forwards"] += 1
        trace_safe = adapter.last_trace["safe"]; t0 = time.perf_counter(); train_loss.backward(); backward_seconds = time.perf_counter() - t0
        counters["full_gradients"] += 1
        grads = [p.grad for p in adapter.parameters()]
        gradient_finite = all(g is not None and torch.isfinite(g).all() for g in grads)
        gradient_norm = float(torch.sqrt(sum(g.detach().square().sum() for g in grads if g is not None)))
        after_backward = H.Q.parameter_hash(model); parameter_unchanged = before == after_backward
        opt = H.optimizer(adapter); sched = H.scheduler(opt); counters["optimizer_instances"] += 1; counters["scheduler_instances"] += 1
        optimizer_state_empty = len(opt.state_dict()["state"]) == 0
        scheduler_lr_update0 = float(opt.param_groups[0]["lr"])
        opt.zero_grad(set_to_none=True)
        model.eval(); t0 = time.perf_counter()
        with torch.no_grad(), sdpa_kernel(SDPBackend.MATH): validation_loss = adapter(validation_cases)
        validation_seconds = time.perf_counter() - t0; counters["validation_forwards"] += 1; validation_safe = adapter.last_trace["safe"]
        model.train(); checkpoint_rng = rng_payload()
        checkpoint = {"model": model.state_dict(), "optimizer": opt.state_dict(), "scheduler": sched.state_dict(), "RNG": checkpoint_rng,
                      "update": 0, "protocol_hash": protocol["protocol_sha256"], "run_identity": run["run_identity_sha256"]}
        buffer = io.BytesIO(); t0 = time.perf_counter(); torch.save(checkpoint, buffer); serialization_seconds = time.perf_counter()-t0
        payload = buffer.getvalue(); checkpoint_sizes.append(len(payload)); counters["checkpoint_serializations"] += 1
        restore_rng(checkpoint_rng)
        with sdpa_kernel(SDPBackend.MATH): original_next = float(adapter(train_cases).detach())
        original_rng = next_rng_identity()
        re_model, re_adapter = H.fresh(arm, seed, run["initial_parameter_sha256"]); counters["model_instances"] += 1
        re_opt = H.optimizer(re_adapter); re_sched = H.scheduler(re_opt); counters["optimizer_instances"] += 1; counters["scheduler_instances"] += 1
        t0 = time.perf_counter(); loaded = torch.load(io.BytesIO(payload), map_location="cpu", weights_only=False)
        re_model.load_state_dict(loaded["model"]); re_opt.load_state_dict(loaded["optimizer"]); re_sched.load_state_dict(loaded["scheduler"])
        restore_rng(loaded["RNG"]); reload_seconds = time.perf_counter()-t0; counters["checkpoint_reloads"] += 1
        re_model.train()
        with sdpa_kernel(SDPBackend.MATH): reloaded_next = float(re_adapter(train_cases).detach())
        reloaded_rng = next_rng_identity()
        equality = {"parameter_hash": H.Q.parameter_hash(re_model) == before, "next_train_forward_bitwise": original_next == reloaded_next,
                    "rng_next_draws_exact": original_rng == reloaded_rng, "optimizer_state_empty": len(re_opt.state_dict()["state"]) == 0,
                    "scheduler_state_exact": re_sched.state_dict() == sched.state_dict(), "protocol_hash": loaded["protocol_hash"] == protocol["protocol_sha256"],
                    "run_identity": loaded["run_identity"] == run["run_identity_sha256"], "update_zero": loaded["update"] == 0}
        sealed_denied = H.sealed_access_denied(); rss_peak = max(rss_peak, process.memory_info().rss)
        passed = bool(np.isfinite(float(train_loss.detach())) and np.isfinite(float(validation_loss)) and trace_safe and validation_safe and
                      gradient_finite and gradient_norm > 0 and parameter_unchanged and optimizer_state_empty and
                      abs(scheduler_lr_update0 - 1e-6) <= 1e-20 and all(equality.values()) and sealed_denied)
        rows.append({"run_id": run_id, "arm": arm, "formal_seed": seed, "initial_parameter_sha256": before,
                     "train_batch": "B00", "train_case_count": 48, "validation_case_count": 128,
                     "train_loss": float(train_loss.detach()), "validation_loss": float(validation_loss), "gradient_norm": gradient_norm,
                     "gradient_finite": gradient_finite, "train_trace_safe": trace_safe, "validation_trace_safe": validation_safe,
                     "parameter_unchanged": parameter_unchanged, "optimizer_state_created_at_zero_step": True,
                     "optimizer_state_empty_before_first_step": optimizer_state_empty, "scheduler_lr_at_update_0": scheduler_lr_update0,
                     "checkpoint_sha256": sha_bytes(payload), "checkpoint_bytes": len(payload), "checkpoint_equality": equality,
                     "sealed_access_denied": sealed_denied, "timing_seconds": {"train_forward": train_seconds, "backward": backward_seconds,
                       "validation_forward": validation_seconds, "serialization": serialization_seconds, "reload": reload_seconds}, "pass": passed})
        del model, adapter, opt, sched, checkpoint, payload, re_model, re_adapter, re_opt, re_sched, loaded; gc.collect()
    forbidden_zero = all(counters[k] == 0 for k in ("formal_optimizer_steps", "formal_parameter_updates", "formal_training_runs",
                                                     "sealed_test_evaluations", "neural_rollouts", "performance_evaluations"))
    gates = {"nine_runs": len(rows) == 9, "all_preflights": all(r["pass"] for r in rows), "forbidden_counts_zero": forbidden_zero,
             "protocol_unchanged": H.sha_file(ROOT / protocol["protocol_path"]) == protocol["protocol_sha256"],
             "validation_manifest_qualified": validation_manifest["pass"]}
    result = {"schema": "sph-pio-poc.stage06b.zero-step-preflight.v1", "protocol_sha256": protocol["protocol_sha256"],
              "run_count": len(rows), "rows": rows, "counters": counters, "gates": gates, "pass": all(gates.values()),
              "train_inventory": train_inventory, "validation_record_count": len(validation_cases),
              "rss_start_bytes": rss_start, "peak_rss_bytes": rss_peak, "peak_rss_delta_bytes": rss_peak-rss_start,
              "wall_time_seconds": time.perf_counter()-started, "checkpoint_bytes_max": max(checkpoint_sizes),
              "formal_training_performed": False, "optimizer_step_called": False}
    write_json(STAGE06B / "zero_step_preflight/zero_step_preflight_results.json", result)
    write_json(STAGE06B / "checkpoint_preflight/checkpoint_roundtrip_results.json",
               {"rows": [{k: r[k] for k in ("run_id", "checkpoint_sha256", "checkpoint_bytes", "checkpoint_equality", "pass")} for r in rows],
                "pass": all(r["pass"] for r in rows)})
    manifest = {"schema": "sph-pio-poc.stage06b.preflight-manifest.v1", "protocol_sha256": protocol["protocol_sha256"],
                "run_count": len(rows), "passed": sum(r["pass"] for r in rows), "counters": counters, "gates": gates,
                "peak_rss_bytes": rss_peak, "checkpoint_bytes_max": max(checkpoint_sizes), "pass": all(gates.values())}
    write_json(STAGE06 / "09_manifests/stage06b_preflight_manifest.json", manifest)
    write_json(STAGE06B / "manifests/stage06b_preflight_manifest.json", manifest)
    print(json.dumps({"runs": len(rows), "passed": sum(r["pass"] for r in rows), "counters": counters,
                      "peak_rss": rss_peak, "checkpoint_bytes_max": max(checkpoint_sizes), "pass": all(gates.values())}, sort_keys=True))


if __name__ == "__main__":
    main()
