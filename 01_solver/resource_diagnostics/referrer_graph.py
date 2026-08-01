"""Sanitized, bounded, type-level pre-GC referrer graphs."""

from __future__ import annotations

from collections import deque
import gc
import inspect
from typing import Any

from resource_diagnostics.retired_object_provenance import ownership_category


def _safe_relation(container: Any, child: Any) -> str:
    if isinstance(container, dict):
        names = sorted(
            str(key) for key, value in container.items()
            if value is child and isinstance(key, str) and len(key) <= 80
        )
        return "key:" + (names[0] if names else "unresolved")
    namespace = getattr(container, "__dict__", None)
    if isinstance(namespace, dict):
        names = sorted(
            str(key) for key, value in namespace.items()
            if value is child and isinstance(key, str) and len(key) <= 80
        )
        if names:
            return "attribute:" + names[0]
    if isinstance(container, (tuple, list)):
        return "container_member"
    return "reference"


def build_type_referrer_graph(
    target: Any,
    *,
    maximum_depth: int = 4,
    maximum_nodes: int = 80,
) -> dict[str, Any]:
    if maximum_depth < 1 or maximum_depth > 4:
        raise ValueError("maximum_depth must be between one and four")
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    queue: deque[tuple[Any, int, int, tuple[int, ...]]] = deque()
    queue.append((target, 0, 0, (id(target),)))
    seen = {id(target): 0}
    excluded_ids = {id(nodes), id(edges), id(queue), id(seen)}
    cycle_paths: list[list[str]] = []
    nodes.append(
        {
            "node": 0,
            "object_type": type(target).__name__,
            "source_module": type(target).__module__,
            "project_owned": type(target).__module__.startswith(("dynamic_solver", "structure_preserving", "resource_diagnostics")),
            "diagnostic_owned": ownership_category(target) in {"observer", "ledger", "weakref_tracker", "diagnostics"},
            "depth": 0,
        }
    )
    while queue and len(nodes) < maximum_nodes:
        current, depth, current_node, ancestry = queue.popleft()
        if depth >= maximum_depth:
            continue
        referrers = gc.get_referrers(current)
        try:
            accepted = 0
            for owner in referrers:
                if id(owner) in excluded_ids or inspect.isframe(owner):
                    continue
                module = type(owner).__module__
                if module in {__name__, "collections"}:
                    continue
                if isinstance(owner, list) and owner is referrers:
                    continue
                relation = _safe_relation(owner, current)
                owner_id = id(owner)
                if owner_id in ancestry:
                    path = [nodes[seen[item]]["object_type"] for item in ancestry if item in seen]
                    path.append(type(owner).__name__)
                    cycle_paths.append(path)
                    continue
                if owner_id not in seen:
                    node_id = len(nodes)
                    seen[owner_id] = node_id
                    category = ownership_category(owner)
                    nodes.append(
                        {
                            "node": node_id,
                            "object_type": type(owner).__name__,
                            "source_module": module,
                            "project_owned": module.startswith(("dynamic_solver", "structure_preserving", "resource_diagnostics")),
                            "diagnostic_owned": category in {"observer", "ledger", "weakref_tracker", "diagnostics"},
                            "depth": depth + 1,
                        }
                    )
                    queue.append((owner, depth + 1, node_id, ancestry + (owner_id,)))
                owner_node = seen[owner_id]
                edges.append(
                    {
                        "from_node": current_node,
                        "to_node": owner_node,
                        "container_type": type(owner).__name__,
                        "attribute_or_key": relation,
                    }
                )
                accepted += 1
                if accepted >= 10 or len(nodes) >= maximum_nodes:
                    break
        finally:
            del referrers
    return {
        "maximum_depth": maximum_depth,
        "nodes": nodes,
        "edges": edges,
        "cycle_type_paths": cycle_paths,
        "cycle_localized": bool(cycle_paths),
    }
