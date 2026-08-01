from __future__ import annotations

import torch

from resource_diagnostics.referrer_graph import build_type_referrer_graph


class _Owner:
    def __init__(self, tensor: torch.Tensor) -> None:
        self.tensor = tensor


def test_referrer_graph_is_bounded_and_type_only() -> None:
    tensor = torch.ones(2, dtype=torch.float64)
    owner = _Owner(tensor)
    graph = build_type_referrer_graph(tensor, maximum_depth=2, maximum_nodes=20)
    assert len(graph["nodes"]) <= 20
    assert max(node["depth"] for node in graph["nodes"]) <= 2
    assert any(node["object_type"] == "_Owner" for node in graph["nodes"])
    assert "tensor([" not in str(graph)
    assert owner.tensor is tensor
