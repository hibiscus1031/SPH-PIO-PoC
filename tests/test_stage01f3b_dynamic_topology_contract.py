from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_dynamic_topology_is_structural_not_single_identity()->None:
    text=(ROOT/"06_experiments/stage_01f3b_mms_convergence/stage01f3b_worker.py").read_text()
    assert "topology_switches_reciprocal" in text
    assert "topology_structural" in text
    assert 'unique_checkpoint_edge_identities"] == 1' not in text
    assert "gc.collect" not in text and "gc.disable" not in text
