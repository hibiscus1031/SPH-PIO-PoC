"""D1 instantaneous invariant-token pair MLP."""

from __future__ import annotations

import torch
from torch import nn

from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph
from pair_force_head.head import AntisymmetricPairForceHead, PairForceOutput


class TokenEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear_1 = nn.Linear(10, 32)
        self.linear_2 = nn.Linear(32, 32)

    def forward(self, token: torch.Tensor) -> torch.Tensor:
        return torch.tanh(self.linear_2(torch.tanh(self.linear_1(token))))


class D1InstantaneousPairMLP(nn.Module):
    arm_id = "D1_INSTANTANEOUS_CONSERVATIVE_PAIR_MLP"

    def __init__(self) -> None:
        super().__init__()
        self.encoder = TokenEncoder()
        self.pair_head = AntisymmetricPairForceHead()

    def evaluate(self, token: torch.Tensor, state: DynamicParticleState, graph: ReciprocalGraph, **_: object) -> PairForceOutput:
        return self.pair_head(self.encoder(token), state, graph)

    def accepted_hidden(self, token: torch.Tensor, **_: object) -> torch.Tensor:
        return self.encoder(token)

    def zero_final_heads(self) -> None:
        self.pair_head.zero_final_heads()

