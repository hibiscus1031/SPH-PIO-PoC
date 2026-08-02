import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAG = ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/n64_dependency_dag.json"


def _reachable(edges, start, target):
    successors = {}
    for edge in edges:
        successors.setdefault(edge["from"], set()).add(edge["to"])
    pending = [start]
    seen = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(successors.get(node, ()))
    return False


def test_trigger_smoke_reference_formal_order_and_failure_stops():
    dag = json.loads(DAG.read_text())
    edges = dag["edges"]
    for formal in ("f5_space_a_n64", "f5_space_b_n64"):
        assert _reachable(edges, "formal_space_n16_n24_n32_n48_complete", formal)
        assert _reachable(edges, "f5_n64_smoke_a", formal)
        assert _reachable(edges, "f5_n64_smoke_b", formal)
        assert _reachable(edges, "formal_space_t_final_resolved_from_frozen_source", formal)
        assert _reachable(edges, "f5_ref_space_b_n64_baseline", formal)
        assert _reachable(edges, "f5_ref_space_b_n64_tighter", formal)
        assert _reachable(edges, "f5_ref_space_b_n64_third", formal)
    assert dag["failure_rules"]["any_smoke_failure"] == "STOP_NO_REFERENCE_OR_FORMAL_N64"
    assert dag["failure_rules"]["any_reference_failure"] == "STOP_NO_FORMAL_N64"
    assert len(dag["not_triggered_terminal"]["run_ids"]) == 7
