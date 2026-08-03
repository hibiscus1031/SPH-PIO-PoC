import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "06_experiments/stage_01h_viscous_decay_diagnosis/diagnostics/run_stage01h_diagnosis.py"


def test_stage01h_changes_are_outside_solver_benchmark_and_evaluator():
    changed = subprocess.check_output(
        ("git", "diff", "--name-only", "448b090be03d5e5201096f37962cebfd962e3e6a", "HEAD"),
        cwd=ROOT, text=True,
    ).splitlines()
    forbidden = (
        "01_solver/",
        "06_experiments/stage_01g_validation_design/",
        "06_experiments/stage_01ge_evaluator_qualification/",
        "06_experiments/stage_01g_validation_execution/",
        "07_reports/stage01g_",
    )
    assert changed
    assert not any(path.startswith(forbidden) for path in changed)


def test_diagnosis_script_has_no_solver_import_or_execution_call():
    tree = ast.parse(SCRIPT.read_text(), filename=str(SCRIPT))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    text = SCRIPT.read_text()
    assert not any(name.startswith(("dynamic_solver", "structure_preserving")) for name in imports)
    assert "explicit_midpoint_dynamic_step" not in text
    assert "prepare_dynamic_state" not in text
    assert "torch" not in imports
