"""Accepted-state checkpoint with physically and temporally separate payloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
from typing import Any

import numpy as np
import torch
from torch import nn

from baseline_d0.state import DynamicParticleState
from contracts.model_factory import parameter_hash
from graph_rebuild.graph import build_reciprocal_graph
from temporal_history.history import TemporalHistoryState


CONTRACT_HASH = "sha256:0872955dc49c781c48c98a13b7f367d85d70869461a0d06e163c858b20c30e87"


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def save_checkpoint(
    directory: Path,
    *,
    arm: str,
    family_id: str,
    dt: float,
    state: DynamicParticleState,
    history: TemporalHistoryState | None,
    model: nn.Module | None,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    physical_path = directory / "accepted_physical_state.pt"
    history_path = directory / "temporal_history.pt"
    model_path = directory / "model_state.pt"
    rng_path = directory / "rng_state.pt"
    metadata_path = directory / "checkpoint_metadata.json"
    torch.save(
        {
            "x_unwrapped": state.x_unwrapped,
            "velocity": state.velocity,
            "density": state.density,
            "pressure": state.pressure,
            "mass": state.mass,
            "smoothing_length": state.smoothing_length,
            "material_labels": state.material_labels,
            "physical_time": state.physical_time,
            "accepted_step_index": state.accepted_step_index,
        },
        physical_path,
    )
    torch.save(
        None
        if history is None
        else {
            "accepted_tokens": history.accepted_tokens,
            "accepted_hidden": history.accepted_hidden,
            "accepted_times": history.accepted_times,
            "material_labels": history.material_labels,
            "history_length": history.history_length,
            "commit_count": history.commit_count,
        },
        history_path,
    )
    torch.save(None if model is None else model.state_dict(), model_path)
    torch.save(
        {
            "torch_rng": torch.random.get_rng_state(),
            "numpy_rng": np.random.get_state(),
            "python_rng": random.getstate(),
        },
        rng_path,
    )
    graph = build_reciprocal_graph(state)
    metadata = {
        "schema_version": "sph-pio-poc.stage03c.checkpoint.v1",
        "arm_id": arm,
        "family_id": family_id,
        "implementation_contract_hash": CONTRACT_HASH,
        "parameter_hash": parameter_hash(model),
        "accepted_state_hash": state.state_hash,
        "history_hash": None if history is None else history.history_hash,
        "physical_time": state.physical_time,
        "accepted_step": state.accepted_step_index,
        "dt": float(dt),
        "graph_configuration": {
            "domain": [[-1.0, -1.0], [1.0, 1.0]],
            "minimum_image": "remainder(delta+extent/2,extent)-extent/2",
            "support_over_dx": 2.6,
            "accepted_graph_hash": graph.graph_hash,
        },
        "eos_configuration": "p=20^2*(rho-1)",
        "source_configuration": "D-R1 exact material-label MMS; D-R3 exact zero",
        "provenance": provenance,
        "payloads": {},
    }
    for name, path in (
        ("physical", physical_path),
        ("history", history_path),
        ("model", model_path),
        ("rng", rng_path),
    ):
        metadata["payloads"][name] = {"path": path.name, "sha256": _sha(path), "byte_count": path.stat().st_size}
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def load_checkpoint(
    directory: Path,
    *,
    model: nn.Module | None,
) -> tuple[DynamicParticleState, TemporalHistoryState | None, dict[str, Any]]:
    metadata = json.loads((directory / "checkpoint_metadata.json").read_text(encoding="utf-8"))
    if metadata["implementation_contract_hash"] != CONTRACT_HASH:
        raise RuntimeError("implementation contract hash mismatch")
    for payload in metadata["payloads"].values():
        path = directory / payload["path"]
        if _sha(path) != payload["sha256"]:
            raise RuntimeError(f"checkpoint payload hash mismatch: {path.name}")
    physical = torch.load(directory / "accepted_physical_state.pt", map_location="cpu", weights_only=False)
    state = DynamicParticleState(**physical)
    history_payload = torch.load(directory / "temporal_history.pt", map_location="cpu", weights_only=False)
    history = None if history_payload is None else TemporalHistoryState(**history_payload)
    model_payload = torch.load(directory / "model_state.pt", map_location="cpu", weights_only=False)
    if model is None:
        if model_payload is not None:
            raise RuntimeError("D0 checkpoint unexpectedly contains model state")
    else:
        model.load_state_dict(model_payload)
        if parameter_hash(model) != metadata["parameter_hash"]:
            raise RuntimeError("parameter hash mismatch")
    rng = torch.load(directory / "rng_state.pt", map_location="cpu", weights_only=False)
    torch.random.set_rng_state(rng["torch_rng"])
    np.random.set_state(rng["numpy_rng"])
    random.setstate(rng["python_rng"])
    if state.state_hash != metadata["accepted_state_hash"]:
        raise RuntimeError("accepted state hash mismatch")
    if (None if history is None else history.history_hash) != metadata["history_hash"]:
        raise RuntimeError("history hash mismatch")
    if build_reciprocal_graph(state).graph_hash != metadata["graph_configuration"]["accepted_graph_hash"]:
        raise RuntimeError("accepted graph reconstruction mismatch")
    return state, history, metadata

