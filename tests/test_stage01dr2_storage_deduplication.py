from __future__ import annotations

import torch

from resource_diagnostics.semantic_tensor_ledger import explicit_storage_totals
from resource_diagnostics.weakref_tracker import tensor_storage_key


def test_views_and_base_share_one_storage_accounting_key() -> None:
    base = torch.arange(128, dtype=torch.float64)
    matrix = base.reshape(16, 8)
    left = matrix[:, :4]
    right = matrix[:, 4:]
    totals = explicit_storage_totals((base, matrix, left, right))
    assert totals["tensor_count"] == 4
    assert totals["unique_storage_count"] == 1
    assert totals["unique_storage_bytes"] == base.untyped_storage().nbytes()
    assert tensor_storage_key(base) == tensor_storage_key(left)
    assert tensor_storage_key(base) == tensor_storage_key(right)
