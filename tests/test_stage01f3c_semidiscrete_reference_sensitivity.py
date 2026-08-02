import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"


def test_three_level_reference_protocol_and_optional_evidence():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f3c.yml").read_text())
    refs = config["references"]
    assert refs["baseline"] == {"rtol": 1.0e-12, "atol": 1.0e-14, "max_step": 3.125e-5}
    assert refs["tighter"] == {"rtol": 1.0e-13, "atol": 1.0e-15, "max_step": 1.5625e-5}
    assert refs["third"] == {"rtol": 1.0e-13, "atol": 1.0e-15, "max_step": 7.8125e-6}
    for path in (STAGE / "run_summaries").glob("f3c_ref_*.json"):
        payload = json.loads(path.read_text())
        assert payload["comparisons"]["baseline_tighter_position_linf"] <= 1.0e-9
        assert payload["comparisons"]["baseline_tighter_velocity_linf"] <= 1.0e-9
        assert payload["comparisons"]["tighter_third_position_linf"] <= 1.0e-9
        assert payload["comparisons"]["tighter_third_velocity_linf"] <= 1.0e-9
        assert payload["sparse_dense_audit"]["sample_count"] >= 10
