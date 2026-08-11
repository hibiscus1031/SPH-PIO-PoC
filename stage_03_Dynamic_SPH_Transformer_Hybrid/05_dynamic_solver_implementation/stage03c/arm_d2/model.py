"""D2 shared GRUCell with accepted-only hidden-state commits."""

from __future__ import annotations

import torch
from torch import nn

from arm_d1.model import TokenEncoder
from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph
from pair_force_head.head import AntisymmetricPairForceHead, PairForceOutput
from temporal_history.history import TemporalHistoryState


class D2CausalRecurrentPairPIO(nn.Module):
    arm_id = "D2_CAUSAL_RECURRENT_PAIR_PIO"

    def __init__(self) -> None:
        super().__init__()
        self.encoder = TokenEncoder()
        self.recurrent = nn.GRUCell(32, 32)
        self.pair_head = AntisymmetricPairForceHead()

    def initialize_hidden(self, token: torch.Tensor) -> torch.Tensor:
        zeros = torch.zeros((token.shape[0], 32), dtype=token.dtype, device=token.device)
        return self.recurrent(self.encoder(token), zeros)

    def evaluate(
        self,
        token: torch.Tensor,
        state: DynamicParticleState,
        graph: ReciprocalGraph,
        *,
        history: TemporalHistoryState,
        stage: str,
    ) -> PairForceOutput:
        if stage == "start":
            q = history.last_hidden
        elif stage == "midpoint":
            q = self.recurrent(self.encoder(token), history.last_hidden)
        else:
            raise ValueError(stage)
        return self.pair_head(q, state, graph)

    def accepted_hidden(self, token: torch.Tensor, *, history: TemporalHistoryState) -> torch.Tensor:
        return self.recurrent(self.encoder(token), history.last_hidden)

    def zero_final_heads(self) -> None:
        self.pair_head.zero_final_heads()

