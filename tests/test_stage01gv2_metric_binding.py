import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "06_experiments/stage_01g_execution_preflight_v2"
GE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_metric_and_threshold_sources_remain_frozen_without_hidden_adaptation():
    audit = json.loads((V2 / "results/stage01gv2_metric_binding_audit.json").read_text())
    threshold = ROOT / audit["threshold_source"]
    metric_contract = ROOT / audit["metric_contract_source"]
    assert _sha256(threshold) == audit["threshold_source_sha256"]
    assert _sha256(metric_contract) == audit["metric_contract_source_sha256"]
    assert audit["shear_gate_count"] == 8
    assert audit["acoustic_gate_count"] == 10
    assert audit["adaptive_threshold"] is False
    assert audit["hidden_normalization"] is False
    assert audit["epsilon_denominator"] is False
    assert audit["metric_feedback_to_solver"] is False
    assert audit["threshold_override_path"] is False
    assert audit["status"] == "PASS"


def test_gate_entry_points_have_only_frozen_run_results_argument():
    path = GE / "evaluator/gate_rules.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    for name in ("evaluate_shear_gates", "evaluate_acoustic_gates"):
        function = functions[name]
        assert [argument.arg for argument in function.args.args] == ["run_results"]
        assert function.args.kwonlyargs == []
        assert function.args.vararg is None
        assert function.args.kwarg is None
