"""Sanitized owner/provenance descriptions for retired Tensor objects."""

from __future__ import annotations

import gc
import inspect
from typing import Any

import torch

from resource_diagnostics.weakref_tracker import tensor_storage_key


def ownership_category(value: Any) -> str:
    module = type(value).__module__
    name = type(value).__name__.lower()
    if "observer" in name or "callback" in name:
        return "observer"
    if "ledger" in name:
        return "ledger"
    if "tracker" in name or "weak" in name:
        return "weakref_tracker"
    if module.startswith("resource_diagnostics") or "diagnostic" in module:
        return "diagnostics"
    if module.startswith(("dynamic_solver", "structure_preserving")):
        return "solver"
    return "external_or_runtime"


def safe_owner_description(target: torch.Tensor) -> dict[str, str | bool]:
    """Describe one direct non-audit owner without serializing its contents."""

    referrers = gc.get_referrers(target)
    owner: Any | None = None
    try:
        for candidate in referrers:
            if inspect.isframe(candidate):
                continue
            if isinstance(candidate, (list, tuple, dict, set)):
                continue
            module = type(candidate).__module__
            if module.startswith("resource_diagnostics.retired_object_provenance"):
                continue
            owner = candidate
            break
        if owner is None:
            return {
                "python_owner_object_type": "unresolved",
                "owner_creation_location": "unresolved",
                "owner_source_module": "unresolved",
                "owner_category": "unresolved",
                "owner_project_owned": False,
                "owner_diagnostic_owned": False,
            }
        module = type(owner).__module__
        category = ownership_category(owner)
        return {
            "python_owner_object_type": type(owner).__name__,
            "owner_creation_location": f"{module}:{type(owner).__qualname__}",
            "owner_source_module": module,
            "owner_category": category,
            "owner_project_owned": module.startswith(
                ("dynamic_solver", "structure_preserving", "resource_diagnostics")
            ),
            "owner_diagnostic_owned": category in {
                "observer", "ledger", "weakref_tracker", "diagnostics"
            },
        }
    finally:
        del referrers, owner


def tensor_scalar_metadata(value: torch.Tensor) -> dict[str, Any]:
    key = tensor_storage_key(value)
    base = getattr(value, "_base", None)
    try:
        base_key = None if base is None else tensor_storage_key(base)
        return {
            "tensor_object_id": id(value),
            "storage_key": f"{key[0]}:{key[1]}:{key[2]}",
            "shape": "x".join(str(int(item)) for item in value.shape),
            "dtype": str(value.dtype),
            "nbytes": key[2],
            "gc_is_tracked": gc.is_tracked(value),
            "is_tensor_view": base is not None,
            "base_storage": "none" if base_key is None else f"{base_key[0]}:{base_key[1]}:{base_key[2]}",
        }
    finally:
        del base
