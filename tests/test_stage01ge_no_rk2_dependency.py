import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "06_experiments/stage_01ge_evaluator_qualification/evaluator"


def test_evaluator_has_no_rk2_import_or_call_target():
    for path in EVALUATOR.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        imported = [
            (node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        imported.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        call_names = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        assert not any("rk2" in value.lower() for value in imported + call_names)
