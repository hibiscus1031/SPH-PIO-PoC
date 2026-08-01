from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"


def test_canary_worker_contains_no_gc_collect_call() -> None:
    tree = ast.parse((ROOT / "stage01dp_worker.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "gc"
        and node.func.attr == "collect"
    ]
    assert calls == []
