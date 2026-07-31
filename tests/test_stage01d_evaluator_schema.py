from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01d_fixed_physics_tgv"
    / "evaluate_dynamic_verification.py"
)


def _load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "stage01d_evaluator_schema_test",
        EVALUATOR_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_method_id_is_not_a_support_family_alias() -> None:
    evaluator = _load_evaluator()
    summary = pd.DataFrame(
        {
            "support_family": ["increasing_neighbor"],
            "method_id": ["explicit_midpoint_rk2_stage01c_pairs"],
        }
    )

    support = evaluator._series(
        summary,
        "support_family",
        ("support_method",),
        required=False,
        source="synthetic run summary",
    )

    assert support is not None
    assert support.tolist() == ["increasing_neighbor"]
