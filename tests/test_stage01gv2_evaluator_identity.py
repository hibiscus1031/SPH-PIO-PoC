import ast
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
GE_COMMIT = "1641ff5f05fa91b8faed49a91edf062f4a90db07"
EXPECTED_MODULES = {
    "__init__.py",
    "acoustic_evaluator.py",
    "common_metrics.py",
    "gate_rules.py",
    "provenance.py",
    "report_generator.py",
    "schema.py",
    "shear_evaluator.py",
    "uncertainty_report.py",
}


def test_stage01ge_commit_status_and_evaluator_modules_are_present():
    subprocess.run(
        ["git", "cat-file", "-e", f"{GE_COMMIT}^{{commit}}"], cwd=ROOT, check=True
    )
    evaluation = json.loads((GE / "results/stage01ge_evaluation.json").read_text())
    assert evaluation["unique_status"] == "INDEPENDENT_VALIDATION_EVALUATOR_READY"
    assert evaluation["current_v2_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    modules = {path.name for path in (GE / "evaluator").glob("*.py")}
    assert modules == EXPECTED_MODULES
    for path in (GE / "evaluator").glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


def test_fresh_dependency_audit_excludes_every_forbidden_dependency():
    audit = json.loads(
        (ROOT / "06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_dependency_audit.json").read_text()
    )
    assert audit["evaluator_file_count"] == 9
    assert audit["forbidden_dependency_hits"] == []
    assert not any(audit["forbidden_dependencies"].values())
    assert audit["external_runtime_dependencies"] == []
    assert audit["status"] == "PASS"
