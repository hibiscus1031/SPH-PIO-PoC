"""Frozen Stage 06B/06C harness primitives; Stage 06B calls no optimizer step."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch

HERE = Path(__file__).resolve(); STAGE06B = HERE.parents[1]; STAGE06 = HERE.parents[3]; ROOT = HERE.parents[4]
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE05B = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver"), str(STAGE04B / "formula_templates")]
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from stage04b_reference_core import CS, L, RHO0, SUPPORT_OVER_DX, evaluate_symbolic
from tokenization.tokens import build_node_token


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None; sys.modules[name] = module; spec.loader.exec_module(module); return module


Q = import_path("stage06b_stage05c_model", ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/qualification/run_stage05c_arm.py")
ACCESS = import_path("stage06b_harness_access", STAGE06B / "access_control/stage06b_access.py")
LR = 1.0e-5


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def tensor(value: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)


def case_from_npz(record_id: str, lineage: str, variant: str, origin: int, path: Path) -> Q.Case:
    with np.load(path, allow_pickle=False) as z: a = {k: z[k] for k in z.files}
    return Q.Case(record_id, lineage, variant, origin, torch.from_numpy(a["frames"]).to(torch.int64), tensor(a["physical_times"]),
        tensor(a["x"]), tensor(a["velocity"]), tensor(a["density"]), tensor(a["material_labels"]), tensor(a["mass"]), tensor(a["smoothing"]),
        tensor(a["history_tokens"]), tensor(a["source_start"]), tensor(a["source_midpoint"]), tensor(a["v0_accepted"]), tensor(a["a_cons"]))


def make_state(arrays: dict[str, np.ndarray], frame: int) -> DynamicParticleState:
    idx = int(np.flatnonzero(arrays["frame_n"] == frame)[0]); dx = L / 8; rho = tensor(arrays["density"][idx])
    return DynamicParticleState(tensor(arrays["position_unwrapped"][idx]), tensor(arrays["velocity"][idx]), rho, eos_pressure(rho),
        torch.full((64,), RHO0*dx*dx, dtype=torch.float64), torch.full((64,), SUPPORT_OVER_DX*dx, dtype=torch.float64),
        tensor(arrays["material_labels"]), float(arrays["physical_time"][idx]), frame)


def materialize_train_batch_zero() -> tuple[list[Q.Case], dict[str, Any]]:
    schedule = json.loads((STAGE06B / "train_batch_schedule/formal_train_batch_schedule.json").read_text())
    records = schedule["base_batches"][0]["records"]; target_manifest = json.loads((ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json").read_text())
    entries = {row["record_id"]: row for row in target_manifest["records"]}; grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in records: grouped.setdefault((row["lineage"], row["variant"]), []).append(row)
    out = []; inventory = []; cache_dir = STAGE06B / "training_harness/train_batch_zero_cache"; cache_dir.mkdir(parents=True, exist_ok=True)
    for (lineage, variant), group in grouped.items():
        stem = f"{lineage.lower()}_{variant.lower()}_n8"
        arrays = ACCESS.load_npz("zero_step_preflight", STAGE04B / f"exact_trajectories/train/{stem}.npz")
        metadata = ACCESS.load_json("zero_step_preflight", STAGE04B / f"exact_trajectories/train/{stem}.json")
        assert metadata["role"] == "TRAIN_LINEAGE"
        for row in group:
            record_id = row["record_id"]; entry = entries[record_id]
            target = ACCESS.load_npz("zero_step_preflight", ROOT / entry["npz_path"])
            target_meta = ACCESS.load_json("zero_step_preflight", ROOT / entry["json_path"])
            assert sha_file(ROOT / entry["npz_path"]) == entry["npz_sha256"] and target_meta["qualification_verdict"] == "QUALIFIED_STAGE05B"
            origin = row["origin"]; frames = list(range(origin-3, origin+1)); states = [make_state(arrays, f) for f in frames]
            tokens = torch.stack([build_node_token(s, build_reciprocal_graph(s)) for s in states], dim=1).numpy()
            idx = int(np.flatnonzero(arrays["frame_n"] == origin)[0]); nxt = int(np.flatnonzero(arrays["frame_n"] == origin+1)[0])
            source_mid = evaluate_symbolic(lineage, variant, arrays["material_labels"], (origin+.5)/256.)["source"]
            v0 = arrays["velocity"][nxt] - (L/CS/256.) * target["a_def"]
            path = cache_dir / f"{record_id}.npz"
            np.savez_compressed(path, frames=np.asarray(frames), physical_times=np.asarray([s.physical_time for s in states]),
                x=np.stack([s.x_unwrapped.numpy() for s in states]), velocity=np.stack([s.velocity.numpy() for s in states]),
                density=np.stack([s.density.numpy() for s in states]), material_labels=arrays["material_labels"], mass=states[-1].mass.numpy(),
                smoothing=states[-1].smoothing_length.numpy(), history_tokens=tokens, source_start=arrays["external_source"][idx],
                source_midpoint=source_mid, v0_accepted=v0, a_cons=target["a_cons"], y_def=target["y_def"])
            out.append(case_from_npz(record_id, lineage, variant, origin, path))
            inventory.append({"record_id": record_id, "path": str(path.relative_to(ROOT)), "sha256": sha_file(path)})
    assert len(out) == 48
    return out, {"base_batch_id": "B00", "case_count": 48, "cases": inventory, "access_counts": dict(ACCESS.COUNTS)}


def load_validation_cases() -> list[Q.Case]:
    manifest = json.loads((STAGE06 / "09_manifests/stage06b_validation_manifest.json").read_text()); assert manifest["pass"] and manifest["record_count"] == 128
    result = []
    for row in manifest["records"]:
        path = ROOT / row["case_cache_path"]; assert sha_file(path) == row["case_cache_sha256"]
        parts = row["record_id"].split("_"); lineage = "_".join(parts[:2]); variant = "_".join(parts[2:4]); origin = int(parts[-1][1:])
        result.append(case_from_npz(row["record_id"], lineage, variant, origin, path))
    return result


def fresh(arm: str, seed: int, expected_hash: str) -> tuple[torch.nn.Module, Q.DefectAdapter]:
    # Frozen identities were preregistered from PyTorch's default float32
    # initializer, followed by an explicit float64 conversion.
    prior = torch.get_default_dtype(); torch.set_default_dtype(torch.float32)
    try:
        torch.manual_seed(seed); model = Q.ARMS[arm]().to(dtype=torch.float64, device="cpu")
    finally:
        torch.set_default_dtype(prior)
    assert Q.parameter_hash(model) == expected_hash
    return model, Q.DefectAdapter(arm, model)


def optimizer(adapter: Q.DefectAdapter) -> torch.optim.AdamW:
    return torch.optim.AdamW(adapter.parameters(), lr=LR, betas=(.9, .999), eps=1e-12, weight_decay=0, amsgrad=False)


def scheduler(opt: torch.optim.Optimizer) -> torch.optim.lr_scheduler.LambdaLR:
    values = json.loads((STAGE06B / "optimizer_schedule/formal_scheduler_values.json").read_text())["rows"]
    factors = [row["factor"] for row in values]
    return torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=lambda update: factors[min(update, 1500)])


def sealed_access_denied(actor: str = "zero_step_preflight") -> bool:
    path = STAGE04B / "sealed_test/private/lcdf_03_variant_main_n8.npz"
    try: ACCESS.read_for_actor(actor, path)
    except (PermissionError, OSError): return True
    return False
