"""Prospective optimizer/schedule construction. This module exposes no update operation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch


def create_zero_step_adamw(parameters: object) -> torch.optim.AdamW:
    return torch.optim.AdamW(parameters, lr=1e-3, betas=(0.9, 0.999), eps=1e-8, weight_decay=1e-6)


@dataclass
class ProspectiveWarmupCosineSchedule:
    base_lr: float = 1e-3
    minimum_lr: float = 1e-5
    warmup_updates: int = 50
    maximum_updates: int = 1000
    update_count: int = 0

    def learning_rate_at(self, update: int) -> float:
        if update < 0 or update > self.maximum_updates: raise ValueError(update)
        if update <= self.warmup_updates:
            return self.base_lr * update / self.warmup_updates
        progress = (update - self.warmup_updates) / (self.maximum_updates - self.warmup_updates)
        return self.minimum_lr + 0.5 * (self.base_lr - self.minimum_lr) * (1.0 + math.cos(math.pi * progress))

    def state_dict(self) -> dict[str, float | int]:
        return dict(self.__dict__)

    def load_state_dict(self, state: dict[str, float | int]) -> None:
        for key, value in state.items(): setattr(self, key, value)
