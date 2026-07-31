"""Project-wide pytest policy for confirmed third-party warnings only."""

from __future__ import annotations

import pytest


_CONFIRMED_UPSTREAM_WARNING_FILTERS = (
    (
        "ignore:`torch\\.jit\\.script` is deprecated\\. Please switch to "
        "`torch\\.compile` or `torch\\.export`\\."
        ":DeprecationWarning:torch\\.jit\\._script"
    ),
    (
        "ignore:Using default support configuration\\."
        ":UserWarning:diffSPH\\.regions"
    ),
    (
        "ignore:None of the inputs have requires_grad=True\\. "
        "Gradients will be None"
        ":UserWarning:torch\\.utils\\.checkpoint"
    ),
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Keep ``pytest -W error`` strict outside two audited upstream warnings."""

    for item in items:
        for warning_filter in _CONFIRMED_UPSTREAM_WARNING_FILTERS:
            item.add_marker(pytest.mark.filterwarnings(warning_filter))
