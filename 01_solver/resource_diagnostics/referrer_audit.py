"""Sparse, redacted direct-referrer summaries for confirmed survivors."""

from __future__ import annotations

import gc
from typing import Any


def _safe_type_name(value: Any) -> str:
    value_type = type(value)
    module = getattr(value_type, "__module__", "")
    name = getattr(value_type, "__qualname__", value_type.__name__)
    if module in {"", "builtins"}:
        return str(name)
    return f"{module}.{name}"


def audit_direct_referrers(value: Any, *, maximum_referrers: int = 32) -> dict[str, Any]:
    """Describe direct holders without serializing contents or local values."""

    if maximum_referrers <= 0:
        raise ValueError("maximum_referrers must be positive")
    referrers = gc.get_referrers(value)
    rows: list[dict[str, Any]] = []
    try:
        for referrer in referrers[:maximum_referrers]:
            row: dict[str, Any] = {"type": _safe_type_name(referrer)}
            if isinstance(referrer, (list, tuple, dict, set)):
                row["container_length"] = len(referrer)
            if isinstance(referrer, dict):
                row["string_key_count"] = sum(
                    isinstance(key, str) for key in referrer.keys()
                )
            rows.append(row)
    finally:
        del referrers
    return {
        "direct_referrer_count": len(rows),
        "truncated": len(rows) >= maximum_referrers,
        "referrers": rows,
        "contents_redacted": True,
    }
