from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_gci_is_variable_specific_and_path_scoped()->None:
    source=(ROOT/"06_experiments/stage_01f3b_mms_convergence/analyze_stage01f3b.py").read_text()
    assert "local_order_stability_25_percent" in source
    assert "GCI not justified" in source
    assert "increasing-neighbor consistency path, not to a fixed-stencil single-h family" in source
    assert 'for field in ("position", "velocity", "density", "pressure")' in source
