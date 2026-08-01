from __future__ import annotations

import math

from resource_diagnostics.cutoff_shell_audit import (
    directed_shell_edge_count,
    offsets_on_shell,
)


def test_q5_cutoff_shell_offsets_and_directed_edge_count() -> None:
    offsets = set(offsets_on_shell(32, 5.0))
    expected = {
        (5, 0),
        (-5, 0),
        (0, 5),
        (0, -5),
        (4, 3),
        (4, -3),
        (-4, 3),
        (-4, -3),
        (3, 4),
        (3, -4),
        (-3, 4),
        (-3, -4),
    }
    assert offsets == expected
    assert all(math.hypot(*offset) == 5.0 for offset in offsets)
    assert directed_shell_edge_count(32, 5.0) == 12 * 32 * 32
