"""External governing-source API; source values never enter model tokens."""

from __future__ import annotations

import numpy as np
import torch

from baseline_d0.state import DynamicParticleState
from reference_core import evaluate_symbolic


DR1_FAMILIES = {"DR1_LAGRANGIAN_COMPRESSION", "DR1_COUPLED_DEFORMATION"}
DR3_FAMILIES = {"DR3_OBLIQUE_SHEAR_A", "DR3_OBLIQUE_SHEAR_B"}


def evaluate_external_momentum_source(
    family_id: str,
    material_labels: torch.Tensor,
    physical_time: float,
    current_state: DynamicParticleState,
) -> torch.Tensor:
    if family_id in DR3_FAMILIES:
        return torch.zeros_like(current_state.velocity)
    if family_id not in DR1_FAMILIES:
        raise KeyError(f"unsupported source family {family_id}")
    tau = float(physical_time) * 20.0 / 2.0
    labels = np.ascontiguousarray(material_labels.detach().cpu().numpy(), dtype=np.float64)
    source = evaluate_symbolic(family_id, labels, tau)["source"]
    return torch.from_numpy(np.ascontiguousarray(source)).to(dtype=torch.float64)

