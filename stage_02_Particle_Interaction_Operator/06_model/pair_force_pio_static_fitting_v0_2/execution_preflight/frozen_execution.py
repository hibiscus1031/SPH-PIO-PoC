"""Exact Stage 02L initialization and Stage 02M update-counter execution semantics."""

from __future__ import annotations

import hashlib
import math

import torch


def initialize_frozen(model: torch.nn.Module, seed: int) -> None:
    torch.manual_seed(seed)
    for name, module in model.named_modules():
        if not isinstance(module, torch.nn.Linear): continue
        if name == "coefficient_head":
            torch.nn.init.normal_(module.weight, mean=0.0, std=1e-3)
            torch.nn.init.zeros_(module.bias)
        else:
            torch.nn.init.xavier_uniform_(module.weight, gain=1.0)
            torch.nn.init.zeros_(module.bias)


def model_hash(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in model.state_dict().items():
        digest.update(name.encode()); digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return "sha256:" + digest.hexdigest()


def learning_rate_at(update: int) -> float:
    if update < 1 or update > 1000: raise ValueError(update)
    if update <= 50: return 1e-3 * update / 50.0
    progress = (update - 50) / 950.0
    return 1e-5 + 0.5 * (1e-3 - 1e-5) * (1.0 + math.cos(math.pi * progress))


class FrozenPostOptimizerScheduler:
    """Update u uses lr_at(u); post-optimizer scheduler transition records counter u and prepares u+1."""
    def __init__(self, optimizer: torch.optim.Optimizer) -> None:
        self.optimizer = optimizer
        self.update_count = 0
        self.last_lr_used = 0.0
        self._set_lr(learning_rate_at(1))

    def _set_lr(self, value: float) -> None:
        for group in self.optimizer.param_groups: group["lr"] = value

    def lr_for_current_update(self, update: int) -> float:
        if update != self.update_count + 1: raise RuntimeError("scheduler/update counter drift")
        value = learning_rate_at(update)
        current = float(self.optimizer.param_groups[0]["lr"])
        if current != value: raise RuntimeError(f"prepared LR mismatch: {current} != {value}")
        return value

    def step(self, completed_optimizer_update: int) -> None:
        if completed_optimizer_update != self.update_count + 1: raise RuntimeError("post-optimizer scheduler ordering mismatch")
        self.update_count = completed_optimizer_update
        self.last_lr_used = learning_rate_at(completed_optimizer_update)
        self._set_lr(learning_rate_at(min(completed_optimizer_update + 1, 1000)))

    def state_dict(self) -> dict[str, float | int]:
        return {"update_count": self.update_count, "last_lr_used": self.last_lr_used, "prepared_lr": float(self.optimizer.param_groups[0]["lr"]), "counter_semantics": "update_u_uses_lr_at_u_then_post_optimizer_transition_sets_counter_u_and_prepares_u_plus_1"}

    def load_state_dict(self, state: dict[str, object]) -> None:
        expected = "update_u_uses_lr_at_u_then_post_optimizer_transition_sets_counter_u_and_prepares_u_plus_1"
        if state.get("counter_semantics") != expected: raise RuntimeError("scheduler semantic mismatch")
        self.update_count = int(state["update_count"])
        self.last_lr_used = float(state["last_lr_used"])
        self._set_lr(float(state["prepared_lr"]))


def optimizer_counter(optimizer: torch.optim.Optimizer) -> int:
    values = []
    for state in optimizer.state.values():
        step = state.get("step", 0); values.append(int(step.item()) if isinstance(step, torch.Tensor) else int(step))
    return max(values, default=0)
