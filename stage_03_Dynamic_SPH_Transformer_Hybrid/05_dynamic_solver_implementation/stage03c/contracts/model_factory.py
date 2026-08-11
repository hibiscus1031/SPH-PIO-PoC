"""Deterministic D0-D3 arm construction and parameter hashing."""

from __future__ import annotations

import hashlib

import torch
from torch import nn

from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO


ARM_SEEDS = {"D1": 20300301, "D2": 20300302, "D3": 20300303}


def create_model(arm: str, *, zero_head: bool = False) -> nn.Module | None:
    if arm == "D0":
        return None
    constructors = {
        "D1": D1InstantaneousPairMLP,
        "D2": D2CausalRecurrentPairPIO,
        "D3": D3CausalTemporalTransformerPIO,
    }
    if arm not in constructors:
        raise KeyError(arm)
    torch.manual_seed(ARM_SEEDS[arm])
    model = constructors[arm]().to(device="cpu", dtype=torch.float64)
    model.eval()
    if zero_head:
        model.zero_final_heads()
    return model


def parameter_count(model: nn.Module | None) -> int:
    return 0 if model is None else sum(parameter.numel() for parameter in model.parameters())


def parameter_hash(model: nn.Module | None) -> str:
    digest = hashlib.sha256()
    if model is not None:
        for name, parameter in sorted(model.state_dict().items()):
            digest.update(name.encode("utf-8"))
            digest.update(str(parameter.dtype).encode("ascii"))
            digest.update(str(tuple(parameter.shape)).encode("ascii"))
            digest.update(parameter.detach().contiguous().cpu().numpy().tobytes())
    return "sha256:" + digest.hexdigest()

