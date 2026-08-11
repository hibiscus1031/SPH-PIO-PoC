"""Transactional accepted-token and accepted-hidden history."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import torch

from baseline_d0.state import _tensor_bytes


@dataclass(frozen=True)
class TemporalHistoryState:
    accepted_tokens: torch.Tensor
    accepted_hidden: torch.Tensor
    accepted_times: torch.Tensor
    material_labels: torch.Tensor
    history_length: int = 4
    commit_count: int = 0

    def __post_init__(self) -> None:
        count = int(self.material_labels.shape[0])
        if self.accepted_tokens.shape != (count, self.history_length, 10):
            raise ValueError("accepted_tokens has invalid shape")
        if self.accepted_hidden.shape != (count, self.history_length, 32):
            raise ValueError("accepted_hidden has invalid shape")
        if self.accepted_times.shape != (self.history_length,):
            raise ValueError("accepted_times has invalid shape")

    @property
    def history_hash(self) -> str:
        digest = hashlib.sha256()
        for value in (self.accepted_tokens, self.accepted_hidden, self.accepted_times, self.material_labels):
            digest.update(_tensor_bytes(value))
        digest.update(str(self.history_length).encode("ascii"))
        digest.update(str(self.commit_count).encode("ascii"))
        return "sha256:" + digest.hexdigest()

    @property
    def last_hidden(self) -> torch.Tensor:
        return self.accepted_hidden[:, -1, :]

    def evaluation_tokens(self, current_token: torch.Tensor) -> torch.Tensor:
        return torch.cat((self.accepted_tokens[:, 1:, :], current_token[:, None, :]), dim=1)

    def commit(self, token: torch.Tensor, hidden: torch.Tensor, physical_time: float) -> "TemporalHistoryState":
        time = torch.tensor([physical_time], dtype=torch.float64)
        return TemporalHistoryState(
            accepted_tokens=torch.cat((self.accepted_tokens[:, 1:, :], token[:, None, :]), dim=1),
            accepted_hidden=torch.cat((self.accepted_hidden[:, 1:, :], hidden[:, None, :]), dim=1),
            accepted_times=torch.cat((self.accepted_times[1:], time), dim=0),
            material_labels=self.material_labels,
            history_length=self.history_length,
            commit_count=self.commit_count + 1,
        )

    def permuted(self, permutation: torch.Tensor) -> "TemporalHistoryState":
        return TemporalHistoryState(
            self.accepted_tokens[permutation],
            self.accepted_hidden[permutation],
            self.accepted_times,
            self.material_labels[permutation],
            self.history_length,
            self.commit_count,
        )

    def detached_clone(self) -> "TemporalHistoryState":
        return TemporalHistoryState(
            self.accepted_tokens.detach().clone(),
            self.accepted_hidden.detach().clone(),
            self.accepted_times.detach().clone(),
            self.material_labels.detach().clone(),
            self.history_length,
            self.commit_count,
        )


def repeat_initial_history(token: torch.Tensor, hidden: torch.Tensor, material_labels: torch.Tensor, physical_time: float) -> TemporalHistoryState:
    return TemporalHistoryState(
        accepted_tokens=token[:, None, :].repeat(1, 4, 1),
        accepted_hidden=hidden[:, None, :].repeat(1, 4, 1),
        accepted_times=torch.full((4,), float(physical_time), dtype=torch.float64),
        material_labels=material_labels.clone(),
        history_length=4,
        commit_count=0,
    )


def align_history_by_material_labels(history: TemporalHistoryState, labels: torch.Tensor) -> TemporalHistoryState:
    lookup = {
        tuple(float(component) for component in label): index
        for index, label in enumerate(history.material_labels.detach().cpu().tolist())
    }
    requested = [tuple(float(component) for component in label) for label in labels.detach().cpu().tolist()]
    if len(lookup) != len(requested) or any(label not in lookup for label in requested):
        raise ValueError("material-label alignment is not bijective")
    order = torch.tensor([lookup[label] for label in requested], dtype=torch.int64)
    return history.permuted(order)
