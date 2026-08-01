from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYZER = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy" / "analyze_stage01dp.py"


def _load_analyzer():
    specification = importlib.util.spec_from_file_location("stage01dp_analyzer_test", ANALYZER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_policy_classifier_has_the_four_preregistered_outcomes() -> None:
    analyzer = _load_analyzer()
    assert analyzer.classify_policy({"evidence_complete": False, "all_operational_gates_pass": False, "complete_finite_topology_safe_reclaimable": False}) == "POLICY_EVIDENCE_INCOMPLETE"
    assert analyzer.classify_policy({"evidence_complete": True, "all_operational_gates_pass": True, "complete_finite_topology_safe_reclaimable": True}) == "POLICY_PASS_ISOLATED_DEFAULT_GC"
    assert analyzer.classify_policy({"evidence_complete": True, "all_operational_gates_pass": False, "complete_finite_topology_safe_reclaimable": True}) == "POLICY_CONDITIONAL_REDUCED_SCOPE"
    assert analyzer.classify_policy({"evidence_complete": True, "all_operational_gates_pass": False, "complete_finite_topology_safe_reclaimable": False}) == "POLICY_FAIL_OPERATIONAL_ENVELOPE"
