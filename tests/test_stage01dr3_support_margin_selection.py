from __future__ import annotations

import math

from resource_diagnostics.cutoff_shell_audit import select_mid_shell_support


def test_support_margin_is_geometry_only_midpoint_to_sqrt26() -> None:
    selection = select_mid_shell_support(32, target_shell=5.0)
    assert selection.next_shell == math.sqrt(26.0)
    assert selection.support_ratio == 0.5 * (5.0 + math.sqrt(26.0))
    assert selection.dimensionless_margin == 0.5 * (math.sqrt(26.0) - 5.0)
    assert 5.0 < selection.support_ratio < selection.next_shell
