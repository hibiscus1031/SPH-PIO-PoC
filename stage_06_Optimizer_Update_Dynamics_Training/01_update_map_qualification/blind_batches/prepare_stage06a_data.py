"""Decode and cache the frozen Stage 06A blind TRAIN batch after freeze."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch

HERE = Path(__file__).resolve()
STAGE06 = HERE.parents[2]
ROOT = HERE.parents[3]
STAGE05 = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training"
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver"), str(STAGE04B / "formula_templates")]
from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from stage04b_reference_core import CS, L, RHO0, SUPPORT_OVER_DX, evaluate_symbolic
from tokenization.tokens import build_node_token


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_access() -> Any:
    path = STAGE06 / "01_update_map_qualification/access_control/stage06a_train_access.py"
    spec = importlib.util.spec_from_file_location("stage06a_access", path)
    module = importlib.util.module_from_spec(spec); assert spec.loader is not None
    spec.loader.exec_module(module); return module


ACCESS = import_access()
DECODE = {"train_target_npz_decode_count": 0, "train_target_json_decode_count": 0,
          "train_trajectory_npz_decode_count": 0, "train_trajectory_json_decode_count": 0,
          "validation_state_decode_count": 0, "validation_target_decode_count": 0,
          "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0,
          "sealed_source_decode_count": 0, "sealed_target_decode_count": 0,
          "sealed_origin_decode_count": 0}


def denial(phase: str) -> dict[str, Any]:
    probes = {
        "validation_state": STAGE04B / "access_control/validation_private/lcdf_02_variant_main_n8.npz",
        "validation_target": STAGE04B / "access_control/validation_private/lcdf_09_variant_main_n8.npz",
        "sealed_formula": STAGE04B / "sealed_test/private/sealed_parameters.json",
        "sealed_state": STAGE04B / "sealed_test/private/lcdf_03_variant_main_n8.npz",
        "sealed_source": STAGE04B / "sealed_test/private/lcdf_10_variant_main_n8.npz",
        "sealed_target": STAGE04B / "sealed_test/private/lcdf_03_variant_low_n8.npz",
        "sealed_origin": STAGE04B / "sealed_test/private/lcdf_10_variant_low_n8.npz",
    }
    rows = []
    for kind, path in probes.items():
        try: ACCESS.read_bytes(path); denied = False
        except (PermissionError, OSError): denied = True
        rows.append({"kind": kind, "path": str(path.relative_to(ROOT)), "denied_before_payload_read": denied})
    result = {"phase": phase, "rows": rows, "decode_counts": dict(DECODE),
              "pass": all(row["denied_before_payload_read"] for row in rows)}
    write_json(STAGE06 / f"01_update_map_qualification/access_control/{phase}_allowlist_denial_audit.json", result)
    return result


def tensor(value: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)


def make_state(arrays: dict[str, np.ndarray], frame: int) -> DynamicParticleState:
    index = int(np.flatnonzero(arrays["frame_n"] == frame)[0]); resolution = 8
    density = tensor(arrays["density"][index]); dx = L / resolution
    return DynamicParticleState(tensor(arrays["position_unwrapped"][index]), tensor(arrays["velocity"][index]),
                                density, eos_pressure(density),
                                torch.full((resolution * resolution,), RHO0 * dx * dx, dtype=torch.float64),
                                torch.full((resolution * resolution,), SUPPORT_OVER_DX * dx, dtype=torch.float64),
                                tensor(arrays["material_labels"]), float(arrays["physical_time"][index]), frame)


def main() -> None:
    freeze_path = STAGE06 / "01_update_map_qualification/freeze/stage06a_freeze_record.json"
    freeze = json.loads(freeze_path.read_text())
    contract = ROOT / freeze["contract_path"]
    assert freeze["frozen_before_first_blind_target_decode"] and freeze["blind_target_decode_count_at_freeze"] == 0
    assert sha_file(contract) == freeze["contract_sha256"]
    assert denial("start")["pass"]
    origins = json.loads((STAGE06 / "01_update_map_qualification/blind_batches/preregistered_blind_origins.json").read_text())
    selected = {(row["lineage"], row["variant"], origin) for row in origins["selection"] for origin in row["origins"]}
    assert len(selected) == 96
    target_manifest = json.loads((STAGE05 / "09_manifests/stage05b_target_manifest.json").read_text())
    assert target_manifest["record_count"] == 384
    target_values = {}; zero_losses = []
    for entry in target_manifest["records"]:
        arrays = ACCESS.load_npz(ROOT / entry["npz_path"]); DECODE["train_target_npz_decode_count"] += 1
        assert sha_file(ROOT / entry["npz_path"]) == entry["npz_sha256"]
        zero_losses.append(float(np.mean(arrays["y_def"] ** 2)))
        parts = entry["record_id"].split("_")
        key = ("_".join(parts[:2]), "_".join(parts[2:4]), int(parts[-1][1:]))
        if key in selected:
            metadata = ACCESS.load_json(ROOT / entry["json_path"]); DECODE["train_target_json_decode_count"] += 1
            assert sha_file(ROOT / entry["json_path"]) == entry["json_sha256"]
            target_values[key] = {"a_cons": arrays["a_cons"], "a_def": arrays["a_def"],
                                  "y_def": arrays["y_def"], "metadata": metadata}
    zero_loss = float(np.mean(zero_losses))
    assert abs(zero_loss - 1) <= 1e-12 and len(target_values) == 96

    cache_dir = STAGE06 / "01_update_map_qualification/blind_batches/case_cache"; cache_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for row in origins["selection"]:
        lineage, variant = row["lineage"], row["variant"]
        stem = f"{lineage.lower()}_{variant.lower()}_n8"
        trajectory = ACCESS.load_npz(STAGE04B / f"exact_trajectories/train/{stem}.npz")
        metadata = ACCESS.load_json(STAGE04B / f"exact_trajectories/train/{stem}.json")
        DECODE["train_trajectory_npz_decode_count"] += 1; DECODE["train_trajectory_json_decode_count"] += 1
        assert metadata["role"] == "TRAIN_LINEAGE"
        for origin in row["origins"]:
            target = target_values[(lineage, variant, origin)]
            frames = list(range(origin - 3, origin + 1)); states = [make_state(trajectory, frame) for frame in frames]
            history_tokens = torch.stack([build_node_token(state, build_reciprocal_graph(state)) for state in states], dim=1).numpy()
            current_index = int(np.flatnonzero(trajectory["frame_n"] == origin)[0])
            accepted_index = int(np.flatnonzero(trajectory["frame_n"] == origin + 1)[0])
            source_mid = evaluate_symbolic(lineage, variant, trajectory["material_labels"], (origin + .5) / 256.)["source"]
            v0 = trajectory["velocity"][accepted_index] - (L / CS / 256.) * target["a_def"]
            record_id = f"{lineage}_{variant}_N8_O{origin:02d}"; path = cache_dir / f"{record_id}.npz"
            np.savez_compressed(path, frames=np.asarray(frames), physical_times=np.asarray([state.physical_time for state in states]),
                                x=np.stack([state.x_unwrapped.numpy() for state in states]),
                                velocity=np.stack([state.velocity.numpy() for state in states]),
                                density=np.stack([state.density.numpy() for state in states]),
                                material_labels=trajectory["material_labels"], mass=states[-1].mass.numpy(),
                                smoothing=states[-1].smoothing_length.numpy(), history_tokens=history_tokens,
                                source_start=trajectory["external_source"][current_index], source_midpoint=source_mid,
                                v0_accepted=v0, a_cons=target["a_cons"], y_def=target["y_def"])
            cases.append({"record_id": record_id, "lineage": lineage, "variant": variant, "origin": origin,
                          "path": str(path.relative_to(ROOT)), "sha256": sha_file(path),
                          "target_canonical_sha256": target["metadata"]["canonical_sha256"]})
    result = {"schema": "sph-pio-poc.stage06a.cached-blind-batch.v1", "contract_sha256": freeze["contract_sha256"],
              "case_count": len(cases), "lineage_batch_size": 16, "global_batch_size": 96,
              "zero_correction_baseline_all384": zero_loss, "zero_correction_absolute_error": abs(zero_loss - 1),
              "cases": cases, "decode_counts": DECODE, "target_values_enter_tokens": False,
              "historical_origin_overlap_count": origins["historical_origin_overlap_count"],
              "pass": len(cases) == 96 and abs(zero_loss - 1) <= 1e-12 and origins["historical_origin_overlap_count"] == 0}
    write_json(STAGE06 / "01_update_map_qualification/blind_batches/cached_blind_batch_manifest.json", result)
    write_json(STAGE06 / "09_manifests/stage06a_batch_manifest.json", result)
    print(json.dumps({"cases": len(cases), "zero_loss": zero_loss, "decode_counts": DECODE}))


if __name__ == "__main__":
    main()
