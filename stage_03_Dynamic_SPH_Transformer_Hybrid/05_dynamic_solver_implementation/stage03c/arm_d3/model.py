"""D3 two-block pre-LN causal Transformer along each particle's time axis."""

from __future__ import annotations

import torch
from torch import nn

from arm_d1.model import TokenEncoder
from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph
from pair_force_head.head import AntisymmetricPairForceHead, PairForceOutput
from temporal_history.history import TemporalHistoryState


class D3CausalTemporalTransformerPIO(nn.Module):
    arm_id = "D3_CAUSAL_TEMPORAL_RECIPROCAL_TRANSFORMER_PIO"

    def __init__(self) -> None:
        super().__init__()
        self.encoder = TokenEncoder()
        layer = nn.TransformerEncoderLayer(
            d_model=32,
            nhead=4,
            dim_feedforward=64,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.temporal = nn.TransformerEncoder(layer, num_layers=2, enable_nested_tensor=False)
        self.relative_offset_embedding = nn.Parameter(torch.empty(4, 32))
        nn.init.normal_(self.relative_offset_embedding, mean=0.0, std=0.02)
        self.pair_head = AntisymmetricPairForceHead()

    @staticmethod
    def causal_mask(reference: torch.Tensor) -> torch.Tensor:
        return torch.triu(torch.ones((4, 4), dtype=torch.bool, device=reference.device), diagonal=1)

    def temporal_hidden(self, sequence: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(sequence)
        # Chronological slots correspond to offsets -3,-2,-1,0.
        offsets = self.relative_offset_embedding[torch.tensor([3, 2, 1, 0], device=sequence.device)]
        output = self.temporal(encoded + offsets[None, :, :], mask=self.causal_mask(sequence))
        return output

    def initialize_hidden(self, token: torch.Tensor) -> torch.Tensor:
        sequence = token[:, None, :].repeat(1, 4, 1)
        return self.temporal_hidden(sequence)[:, -1, :]

    def evaluate(
        self,
        token: torch.Tensor,
        state: DynamicParticleState,
        graph: ReciprocalGraph,
        *,
        history: TemporalHistoryState,
        stage: str,
    ) -> PairForceOutput:
        if stage not in {"start", "midpoint"}:
            raise ValueError(stage)
        sequence = history.evaluation_tokens(token)
        q = self.temporal_hidden(sequence)[:, -1, :]
        return self.pair_head(q, state, graph)

    def accepted_hidden(self, token: torch.Tensor, *, history: TemporalHistoryState) -> torch.Tensor:
        return self.temporal_hidden(history.evaluation_tokens(token))[:, -1, :]

    def zero_final_heads(self) -> None:
        self.pair_head.zero_final_heads()

