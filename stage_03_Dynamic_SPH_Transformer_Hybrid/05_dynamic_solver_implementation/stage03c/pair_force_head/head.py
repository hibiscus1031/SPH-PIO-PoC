"""Exchange-symmetric coefficients and structurally antisymmetric pair forces."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from baseline_d0.state import DynamicParticleState
from graph_rebuild.graph import ReciprocalGraph


@dataclass(frozen=True)
class PairForceOutput:
    acceleration: torch.Tensor
    pair_i: torch.Tensor
    pair_j: torch.Tensor
    pair_force_on_i: torch.Tensor
    alpha: torch.Tensor
    beta: torch.Tensor
    particle_hidden: torch.Tensor


class AntisymmetricPairForceHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_1 = nn.Linear(100, 32)
        self.hidden_2 = nn.Linear(32, 32)
        self.output = nn.Linear(32, 2)
        self.alpha_bound = 0.05
        self.beta_bound = 0.05
        self.epsilon_r = 2.0e-12

    def coefficients_from_pairs(
        self,
        q_i: torch.Tensor,
        q_j: torch.Tensor,
        pair_scalars: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        symmetric = torch.cat((q_i + q_j, torch.abs(q_i - q_j), q_i * q_j, pair_scalars), dim=-1)
        hidden = torch.tanh(self.hidden_1(symmetric))
        hidden = torch.tanh(self.hidden_2(hidden))
        raw = self.output(hidden)
        return self.alpha_bound * torch.tanh(raw[:, 0]), self.beta_bound * torch.tanh(raw[:, 1])

    def zero_final_heads(self) -> None:
        with torch.no_grad():
            self.output.weight.zero_()
            self.output.bias.zero_()

    def forward(
        self,
        q: torch.Tensor,
        state: DynamicParticleState,
        graph: ReciprocalGraph,
        pair_order: torch.Tensor | None = None,
    ) -> PairForceOutput:
        selected = graph.unordered & graph.active_kernel
        i = graph.row[selected]
        j = graph.col[selected]
        displacement = graph.displacement[selected]
        distance = graph.distance[selected]
        support = graph.edge_support[selected]
        if pair_order is not None:
            i, j = i[pair_order], j[pair_order]
            displacement, distance, support = displacement[pair_order], distance[pair_order], support[pair_order]
        rhat = displacement / (distance[:, None] + self.epsilon_r)
        dv = (state.velocity[j] - state.velocity[i]) / 20.0
        radial = torch.einsum("nd,nd->n", dv, rhat)
        transverse = dv - radial[:, None] * rhat
        pair_scalars = torch.stack(
            (
                distance / support,
                radial,
                dv.square().sum(dim=-1),
                transverse.square().sum(dim=-1),
            ),
            dim=-1,
        )
        alpha, beta = self.coefficients_from_pairs(q[i], q[j], pair_scalars)
        force_scale = torch.sqrt(state.mass[i] * state.mass[j]) * (20.0**2 / 2.0)
        pair_force = force_scale[:, None] * (alpha[:, None] * rhat + beta[:, None] * transverse)
        force = torch.zeros_like(state.velocity)
        force.index_add_(0, i, pair_force)
        force.index_add_(0, j, -pair_force)
        acceleration = force / state.mass[:, None]
        return PairForceOutput(acceleration, i, j, pair_force, alpha, beta, q)

