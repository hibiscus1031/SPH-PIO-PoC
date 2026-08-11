"""Shared read-only helpers for Stage 02M-R diagnostics."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

torch.set_default_dtype(torch.float64)
torch.set_num_threads(1)
try:
    torch.set_num_interop_threads(1)
except RuntimeError:
    pass

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_failure_attribution_v0_1"
MROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_1"
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
KROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"
sys.path.insert(0, str(MROOT / "execution_preflight"))
sys.path.insert(0, str(LROOT / "loss"))
sys.path.insert(0, str(KROOT / "implementations"))

from controlled_loader import ControlledStage02MLoader  # noqa: E402
from frozen_execution import initialize_frozen, model_hash  # noqa: E402
from loss_contract import A0, EPSILON_METRIC, graph_node_mse, static_metrics  # noqa: E402
from pair_force_models import MODEL_CLASSES, PairGraph, node_features, pair_geometry, symmetric_pair_features  # noqa: E402

PROTOCOL_HASH = "sha256:ab02a49a508c4ddcab5db037886abd329ab29d2eedfc8ffe5d818ad691668648"
ARCHITECTURES = ("K0", "K1", "K2")
SEEDS = (20261201, 20261202, 20261203)


@dataclass
class Item:
    case_id: str
    family_id: str
    resolution_id: str
    support_id: str
    split_role: str
    graph: PairGraph
    target: torch.Tensor | None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def tensor_hash(model: torch.nn.Module) -> str:
    return model_hash(model)


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
        pair_i=torch.as_tensor(source[unique]),
        pair_j=torch.as_tensor(target[unique]),
        active=torch.as_tensor(a["reciprocal_graph_extensions.active_kernel_indicator"][unique]),
        displacement=torch.as_tensor(a["stage02b_record.neighbor_information.minimum_image_displacement"][unique]),
        relative_velocity=torch.as_tensor(a["stage02b_record.neighbor_information.relative_velocity"][unique] / 20.0),
    )


def load_items(include_test_inputs: bool = False) -> tuple[ControlledStage02MLoader, dict[str, list[Item]]]:
    loader = ControlledStage02MLoader(PROTOCOL_HASH)
    roles = ["future_train", "future_validation"] + (["future_test"] if include_test_inputs else [])
    result: dict[str, list[Item]] = {role: [] for role in roles}
    for case_id in sorted(loader.rows):
        role = loader.rows[case_id]["split_role"]
        if role not in result:
            continue
        record = loader.load_inputs(case_id)
        target = None
        if role == "future_train":
            target = torch.as_tensor(loader.load_target(case_id, "training").target)
        elif role == "future_validation":
            target = torch.as_tensor(loader.load_target(case_id, "validation").target)
        identity = loader.rows[case_id]
        tokens = case_id.split("_")
        n_token = next(token for token in tokens if token.startswith("n") and token[1:].isdigit())
        h_token = next(token for token in tokens if token.startswith("h") and token[1:].isdigit())
        resolution_id = f"N{n_token[1:]}x{n_token[1:]}"
        support_id = f"Hdx_{h_token[1]}.{h_token[2:]}".replace(".", "p")
        result[role].append(Item(case_id, identity["family_id"], resolution_id, support_id, role, input_to_graph(record), target))
    return loader, result


def make_model(architecture: str, seed: int, checkpoint: Path | None = None) -> tuple[torch.nn.Module, dict[str, Any] | None]:
    model = MODEL_CLASSES[architecture]().to(dtype=torch.float64, device="cpu")
    initialize_frozen(model, seed)
    state = None
    if checkpoint is not None:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(state["model_parameters"])
    return model, state


def metric_row(prediction: torch.Tensor, target: torch.Tensor) -> dict[str, float]:
    base = {key: float(value) for key, value in static_metrics(prediction, target).items()}
    pred_rms = float(torch.sqrt(torch.mean(torch.sum(prediction * prediction, dim=-1))))
    target_rms = float(torch.sqrt(torch.mean(torch.sum(target * target, dim=-1))))
    base.update({
        "prediction_RMS": pred_rms,
        "target_RMS": target_rms,
        "prediction_to_target_RMS": pred_rms / (target_rms + EPSILON_METRIC),
        "zero_correction_improvement_Q_L2": 1.0 - base["Q_L2"],
    })
    return base


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_keys = ("Q_L2", "Q_Linf", "cosine", "prediction_RMS", "target_RMS", "prediction_to_target_RMS", "zero_correction_improvement_Q_L2")
    families = sorted({row["family_id"] for row in rows})
    def means(group: list[dict[str, Any]]) -> dict[str, float]:
        return {key: float(np.mean([row[key] for row in group])) for key in metric_keys}
    family_means = {family: means([row for row in rows if row["family_id"] == family]) for family in families}
    return {
        "per_graph": rows,
        "graph_balanced_mean": means(rows),
        "family_means": family_means,
        "family_balanced_mean": {key: float(np.mean([family_means[f][key] for f in families])) for key in metric_keys},
        "maximum": {key: float(max(row[key] for row in rows)) for key in ("Q_L2", "Q_Linf")},
        "per_resolution_Q_L2": {value: float(np.mean([row["Q_L2"] for row in rows if row["resolution_id"] == value])) for value in sorted({row["resolution_id"] for row in rows})},
        "per_support_Q_L2": {value: float(np.mean([row["Q_L2"] for row in rows if row["support_id"] == value])) for value in sorted({row["support_id"] for row in rows})},
    }


def evaluate(model: torch.nn.Module, items: list[Item], details: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    rows, coefficients = [], []
    model.eval()
    with torch.no_grad():
        for item in items:
            assert item.target is not None
            output = model(item.graph, return_details=details)
            prediction = output["acceleration"] if details else output
            rows.append({"case_id": item.case_id, "family_id": item.family_id, "resolution_id": item.resolution_id, "support_id": item.support_id, **metric_row(prediction, item.target)})
            if details:
                alpha, beta = output["alpha"], output["beta"]
                coefficients.append({
                    "case_id": item.case_id,
                    "alpha_RMS": float(torch.sqrt(torch.mean(alpha * alpha))),
                    "beta_RMS": float(torch.sqrt(torch.mean(beta * beta))),
                    "alpha_saturation_fraction_abs_ge_0p99": float(torch.mean((torch.abs(alpha) >= 0.99).to(torch.float64))),
                    "beta_saturation_fraction_abs_ge_0p99": float(torch.mean((torch.abs(beta) >= 0.99).to(torch.float64))),
                })
    model.train()
    coeff = {}
    if coefficients:
        coeff = {"per_graph": coefficients, "mean": {key: float(np.mean([row[key] for row in coefficients])) for key in coefficients[0] if key != "case_id"}}
    return aggregate(rows), coeff


def graph_loss(model: torch.nn.Module, items: list[Item]) -> torch.Tensor:
    contributions = []
    for item in items:
        assert item.target is not None
        contributions.append(graph_node_mse(model(item.graph), item.target))
    return torch.stack(contributions).mean()


def terminal(architecture: str, seed: int) -> dict[str, Any]:
    return json.loads((MROOT / f"runs/{architecture}/seed_{seed}/run_terminal.json").read_text())


def checkpoint_paths(architecture: str, seed: int) -> list[Path]:
    return sorted((MROOT / f"checkpoints/{architecture}_seed{seed}").glob("update_*.pt"))


def module_name(parameter_name: str) -> str:
    if parameter_name.startswith("coefficient_head"):
        return "coefficient_head"
    if parameter_name.startswith("encoder"):
        return "encoder"
    if parameter_name.startswith("node_encoder"):
        return "node_encoder"
    if parameter_name.startswith("blocks"):
        return "interaction_blocks"
    if parameter_name.startswith("pair_decoder"):
        return "pair_decoder"
    return parameter_name.split(".")[0]
