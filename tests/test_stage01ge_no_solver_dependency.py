import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "06_experiments/stage_01ge_evaluator_qualification/evaluator"


def test_evaluator_has_no_solver_or_training_imports():
    forbidden = ("01_solver", "solver", "training", "train", "learned_corrector")
    for path in EVALUATOR.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not [name for name in imports if any(token in name.lower() for token in forbidden)]
