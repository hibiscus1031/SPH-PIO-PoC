from __future__ import annotations

import torch

from resource_diagnostics.edge_working_set_model import robust_edge_step_fit
from resource_diagnostics.semantic_tensor_ledger import SemanticTensorLedger


def test_edge_dependent_category_counts_each_storage_once() -> None:
    row = torch.arange(10, dtype=torch.int64)
    col = row.flip(0)
    displacement = torch.zeros((10, 2), dtype=torch.float64)
    distance = displacement[:, 0]
    ledger = SemanticTensorLedger()
    ledger.register_many(
        {
            "row": row,
            "col": col,
            "displacement": displacement,
            "distance_view": distance,
        },
        category="current_neighborhood",
        generation=0,
    )
    snapshot = ledger.snapshot(step=0)
    expected = row.nbytes + col.nbytes + displacement.nbytes
    assert snapshot["summary"]["current_edge_dependent_bytes"] == expected


def test_edge_adjusted_model_recovers_zero_step_term() -> None:
    steps = list(range(20))
    edges = [100 + (index % 5) * 7 for index in steps]
    values = [4096.0 + 32.0 * edge for edge in edges]
    fit = robust_edge_step_fit(
        steps=steps,
        edge_counts=edges,
        values=values,
        bootstrap_samples=100,
        seed=7,
    )
    assert abs(fit.edge_coefficient - 32.0) < 1.0e-8
    assert abs(fit.step_coefficient) < 1.0e-8
    assert fit.step_ci95_lower <= 0.0 <= fit.step_ci95_upper
