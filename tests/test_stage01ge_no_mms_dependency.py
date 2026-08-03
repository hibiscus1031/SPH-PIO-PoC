import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "06_experiments/stage_01ge_evaluator_qualification/evaluator"


def test_evaluator_has_no_mms_source_adapter_or_stage01f5b_evaluator_import():
    forbidden = ("mms", "manufactured", "source_adapter", "stage01f5b", "evaluate_stage01f5b")
    for path in EVALUATOR.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not any(any(token in name.lower() for token in forbidden) for name in imports)
