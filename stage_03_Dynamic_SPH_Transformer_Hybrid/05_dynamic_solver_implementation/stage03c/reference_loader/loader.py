"""Read-only loader for the 12 required Stage 03B exact cases and D-R2 diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from temporal_history.history import TemporalHistoryState
from tokenization.tokens import build_node_token


ROOT = Path(__file__).resolve().parents[4]
RECORDS = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/trajectory_records"
FAMILY_STEMS = {
    "DR1_LAGRANGIAN_COMPRESSION": "dr1_lagrangian_compression",
    "DR1_COUPLED_DEFORMATION": "dr1_coupled_deformation",
    "DR3_OBLIQUE_SHEAR_A": "dr3_oblique_shear_a",
    "DR3_OBLIQUE_SHEAR_B": "dr3_oblique_shear_b",
}


@dataclass(frozen=True)
class ReferenceCase:
    family_id: str
    resolution: int
    exact_path: Path
    exact: dict[str, np.ndarray]
    dop853_path: Path | None
    dop853: dict[str, np.ndarray] | None

    @property
    def case_id(self) -> str:
        return f"{self.family_id}_N{self.resolution}"

    @property
    def dt(self) -> float:
        return float(self.exact["physical_time"][1] - self.exact["physical_time"][0])

    def state_at(self, frame: int = 0) -> DynamicParticleState:
        position_key = "position_unwrapped" if "position_unwrapped" in self.exact else "position"
        x = torch.from_numpy(np.ascontiguousarray(self.exact[position_key][frame])).to(torch.float64)
        velocity = torch.from_numpy(np.ascontiguousarray(self.exact["velocity"][frame])).to(torch.float64)
        density = torch.from_numpy(np.ascontiguousarray(self.exact["density"][frame])).to(torch.float64)
        labels = torch.from_numpy(np.ascontiguousarray(self.exact["material_labels"])).to(torch.float64)
        count = self.resolution**2
        mass = torch.full((count,), 4.0 / count, dtype=torch.float64)
        support = torch.full((count,), 2.6 * 2.0 / self.resolution, dtype=torch.float64)
        return DynamicParticleState(
            x,
            velocity,
            density,
            eos_pressure(density),
            mass,
            support,
            labels,
            float(self.exact["physical_time"][frame]),
            int(frame),
        )


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def load_case(family_id: str, resolution: int) -> ReferenceCase:
    stem = FAMILY_STEMS[family_id]
    exact_path = RECORDS / f"{stem}_n{resolution}_exact.npz"
    dop_path = RECORDS / f"{stem}_n{resolution}_dop853.npz" if family_id.startswith("DR1_") else None
    return ReferenceCase(
        family_id,
        int(resolution),
        exact_path,
        _load_npz(exact_path),
        dop_path,
        None if dop_path is None else _load_npz(dop_path),
    )


def required_cases() -> list[ReferenceCase]:
    return [load_case(family, resolution) for family in FAMILY_STEMS for resolution in (8, 12, 16)]


def load_reference_prehistory(case: ReferenceCase, origin_frame: int, model: torch.nn.Module, arm: str) -> TemporalHistoryState:
    if arm not in {"D2", "D3"}:
        raise ValueError("reference prehistory is defined only for temporal arms")
    if origin_frame <= 0:
        raise ValueError("reference prehistory requires an origin after frame zero")
    start = max(0, origin_frame - 3)
    frame_ids = list(range(start, origin_frame + 1))
    while len(frame_ids) < 4:
        frame_ids.insert(0, frame_ids[0])
    if any(frame > origin_frame for frame in frame_ids) or any(frame == origin_frame for frame in frame_ids[:-1]):
        raise RuntimeError("future or non-prehistory reference access")
    tokens = []
    times = []
    for frame in frame_ids:
        state = case.state_at(frame).with_eos()
        tokens.append(build_node_token(state, build_reciprocal_graph(state)))
        times.append(state.physical_time)
    token_history = torch.stack(tokens, dim=1)
    if arm == "D2":
        hidden_items = []
        hidden = torch.zeros((case.resolution**2, 32), dtype=torch.float64)
        for token in tokens:
            hidden = model.recurrent(model.encoder(token), hidden)
            hidden_items.append(hidden)
        hidden_history = torch.stack(hidden_items, dim=1)
    else:
        hidden_items = []
        for index in range(4):
            prefix = tokens[: index + 1]
            padded = [prefix[0]] * (4 - len(prefix)) + prefix
            sequence = torch.stack(padded, dim=1)
            hidden_items.append(model.temporal_hidden(sequence)[:, -1, :])
        hidden_history = torch.stack(hidden_items, dim=1)
    return TemporalHistoryState(
        token_history,
        hidden_history,
        torch.tensor(times, dtype=torch.float64),
        case.state_at(origin_frame).material_labels,
        history_length=4,
        commit_count=0,
    )
