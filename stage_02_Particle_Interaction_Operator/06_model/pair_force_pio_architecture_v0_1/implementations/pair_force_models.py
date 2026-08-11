"""Frozen Stage 02K pair-force architectures. No optimizer or training code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor, nn

torch.set_default_dtype(torch.float64)


@dataclass
class PairGraph:
    position: Tensor
    velocity: Tensor
    density: Tensor
    pressure: Tensor
    mass: Tensor
    smoothing_length: Tensor
    pair_i: Tensor
    pair_j: Tensor
    active: Tensor
    displacement: Tensor | None = None
    relative_velocity: Tensor | None = None
    domain_length: float = 1.0
    sound_speed: float = 20.0

    def with_geometry(self) -> tuple[Tensor, Tensor]:
        if self.displacement is None:
            raw = self.position[self.pair_j] - self.position[self.pair_i]
            length = torch.as_tensor(self.domain_length, dtype=raw.dtype, device=raw.device)
            displacement = raw - length * torch.round(raw / length)
        else:
            displacement = self.displacement
        if self.relative_velocity is None:
            relative_velocity = (
                self.velocity[self.pair_j] - self.velocity[self.pair_i]
            ) / self.sound_speed
        else:
            relative_velocity = self.relative_velocity
        return displacement, relative_velocity


def _linear(in_features: int, out_features: int) -> nn.Linear:
    return nn.Linear(in_features, out_features, dtype=torch.float64)


def _mlp(in_features: int, out_features: int, hidden: int = 32) -> nn.Sequential:
    return nn.Sequential(
        _linear(in_features, hidden), nn.Tanh(),
        _linear(hidden, hidden), nn.Tanh(),
        _linear(hidden, out_features),
    )


def node_features(graph: PairGraph) -> Tensor:
    rho = (graph.density - 1000.0) / 1000.0
    pressure = graph.pressure / (1000.0 * graph.sound_speed**2)
    mass = graph.mass / (1000.0 * graph.domain_length**2)
    h = graph.smoothing_length / graph.domain_length
    return torch.stack((rho, pressure, mass, h, torch.ones_like(rho)), dim=-1)


def pair_geometry(graph: PairGraph, epsilon_r: float = 1e-12) -> dict[str, Tensor]:
    displacement, dv = graph.with_geometry()
    distance = torch.linalg.vector_norm(displacement, dim=-1)
    rhat = displacement / (distance[:, None] + epsilon_r)
    radial = torch.sum(dv * rhat, dim=-1)
    transverse = dv - radial[:, None] * rhat
    return {
        "displacement": displacement,
        "dv": dv,
        "distance": distance,
        "rhat": rhat,
        "radial": radial,
        "transverse": transverse,
    }


def symmetric_pair_features(graph: PairGraph, geom: dict[str, Tensor]) -> Tensor:
    node = node_features(graph)[:, :4]
    left, right = node[graph.pair_i], node[graph.pair_j]
    h_pair = 0.5 * (
        graph.smoothing_length[graph.pair_i] + graph.smoothing_length[graph.pair_j]
    )
    return torch.cat(
        (
            left + right,
            torch.abs(left - right),
            left * right,
            (geom["distance"] / h_pair)[:, None],
            torch.sum(geom["dv"] ** 2, dim=-1, keepdim=True),
            geom["radial"][:, None],
            torch.sum(geom["transverse"] ** 2, dim=-1, keepdim=True),
            graph.active.to(dtype=left.dtype)[:, None],
        ),
        dim=-1,
    )


class PairForceBase(nn.Module):
    alpha_max = 1.0
    beta_max = 1.0
    epsilon_r = 1e-12

    def coefficients(self, graph: PairGraph, pair_features: Tensor) -> Tensor:
        raise NotImplementedError

    def forward(self, graph: PairGraph, *, return_details: bool = False) -> Any:
        geom = pair_geometry(graph, self.epsilon_r)
        features = symmetric_pair_features(graph, geom)
        raw = self.coefficients(graph, features)
        alpha = self.alpha_max * torch.tanh(raw[:, 0])
        beta = self.beta_max * torch.tanh(raw[:, 1])
        scale = (
            torch.sqrt(graph.mass[graph.pair_i] * graph.mass[graph.pair_j])
            * graph.sound_speed**2
            / graph.domain_length
        )
        mask = graph.active.to(dtype=scale.dtype)
        central = (scale * mask * alpha)[:, None] * geom["rhat"]
        transverse = (scale * mask * beta)[:, None] * geom["transverse"]
        force = central + transverse
        nodal = torch.zeros(
            (graph.position.shape[0], 2), dtype=force.dtype, device=force.device
        )
        nodal.index_add_(0, graph.pair_i, force)
        nodal.index_add_(0, graph.pair_j, -force)
        acceleration = nodal / graph.mass[:, None]
        if return_details:
            return {
                "acceleration": acceleration,
                "nodal_force": nodal,
                "pair_force": force,
                "reverse_pair_force": -force,
                "central_pair_force": central,
                "transverse_pair_force": transverse,
                "alpha": alpha,
                "beta": beta,
                "pair_features": features,
                "geometry": geom,
            }
        return acceleration

    def zero_coefficient_head(self) -> None:
        head = self.coefficient_head
        assert isinstance(head, nn.Linear)
        nn.init.zeros_(head.weight)
        nn.init.zeros_(head.bias)


class K0CentralPairMLP(PairForceBase):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = _mlp(17, 32)
        self.coefficient_head = _linear(32, 1)

    def coefficients(self, graph: PairGraph, pair_features: Tensor) -> Tensor:
        alpha = self.coefficient_head(torch.tanh(self.encoder(pair_features)))
        return torch.cat((alpha, torch.zeros_like(alpha)), dim=-1)


class K1ConservativePairMLP(PairForceBase):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = _mlp(17, 32)
        self.coefficient_head = _linear(32, 2)

    def coefficients(self, graph: PairGraph, pair_features: Tensor) -> Tensor:
        return self.coefficient_head(torch.tanh(self.encoder(pair_features)))


class ReciprocalInteractionBlock(nn.Module):
    def __init__(self, hidden: int = 32, heads: int = 4) -> None:
        super().__init__()
        self.hidden = hidden
        self.heads = heads
        pair_in = 2 * hidden + 17
        self.logit = _mlp(pair_in, heads, hidden)
        self.value = _mlp(pair_in, hidden, hidden)
        self.update = _mlp(2 * hidden, hidden, hidden)

    def forward(self, z: Tensor, graph: PairGraph, pair_features: Tensor) -> Tensor:
        zi, zj = z[graph.pair_i], z[graph.pair_j]
        symmetric = torch.cat((zi + zj, torch.abs(zi - zj), pair_features), dim=-1)
        logits = torch.clamp(self.logit(symmetric), -20.0, 20.0)
        exp_logits = torch.exp(logits) * graph.active[:, None].to(logits.dtype)
        normalizer = torch.zeros(
            (z.shape[0], self.heads), dtype=z.dtype, device=z.device
        )
        normalizer.index_add_(0, graph.pair_i, exp_logits)
        normalizer.index_add_(0, graph.pair_j, exp_logits)
        denom = torch.sqrt(
            torch.clamp(normalizer[graph.pair_i] * normalizer[graph.pair_j], min=1e-30)
        )
        weight = exp_logits / denom
        value = self.value(symmetric)
        message = torch.mean(weight, dim=-1, keepdim=True) * value
        aggregate = torch.zeros_like(z)
        aggregate.index_add_(0, graph.pair_i, message)
        aggregate.index_add_(0, graph.pair_j, message)
        return z + self.update(torch.cat((z, aggregate), dim=-1))


class K2ReciprocalPairAttentionPIO(PairForceBase):
    def __init__(self) -> None:
        super().__init__()
        self.node_encoder = _mlp(5, 32)
        self.blocks = nn.ModuleList(
            [ReciprocalInteractionBlock(32, 4), ReciprocalInteractionBlock(32, 4)]
        )
        self.pair_decoder = _mlp(81, 32)
        self.coefficient_head = _linear(32, 2)

    def coefficients(self, graph: PairGraph, pair_features: Tensor) -> Tensor:
        z = self.node_encoder(node_features(graph))
        for block in self.blocks:
            z = block(z, graph, pair_features)
        zi, zj = z[graph.pair_i], z[graph.pair_j]
        symmetric = torch.cat((zi + zj, torch.abs(zi - zj), pair_features), dim=-1)
        hidden = torch.tanh(self.pair_decoder(symmetric))
        return self.coefficient_head(hidden)


def directed_softmax_negative_control() -> dict[str, Tensor]:
    """Fixed asymmetric directed logits: ordinary source-wise softmax is not reciprocal."""
    source = torch.tensor([0, 0, 1, 1, 2, 2], dtype=torch.int64)
    target = torch.tensor([1, 2, 0, 2, 0, 1], dtype=torch.int64)
    reverse = torch.tensor([2, 4, 0, 5, 1, 3], dtype=torch.int64)
    logits = torch.tensor([2.0, -1.0, 0.25, 1.5, -0.5, 0.75])
    weight = torch.empty_like(logits)
    for i in range(3):
        mask = source == i
        weight[mask] = torch.softmax(logits[mask], dim=0)
    displacement = torch.tensor(
        [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [-1.0, 1.0], [0.0, -1.0], [1.0, -1.0]]
    )
    unit = displacement / torch.linalg.vector_norm(displacement, dim=-1, keepdim=True)
    force = weight[:, None] * unit
    nodal = torch.zeros((3, 2), dtype=torch.float64)
    nodal.index_add_(0, source, force)
    return {
        "source": source,
        "target": target,
        "reverse": reverse,
        "weight": weight,
        "force": force,
        "pair_residual": force + force[reverse],
        "total_force": torch.sum(nodal, dim=0),
    }


MODEL_CLASSES = {
    "K0": K0CentralPairMLP,
    "K1": K1ConservativePairMLP,
    "K2": K2ReciprocalPairAttentionPIO,
}
