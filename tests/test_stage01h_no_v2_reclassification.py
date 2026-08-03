import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE_G = ROOT / "06_experiments/stage_01g_validation_execution/results/stage01g_execution_final_state.json"
STAGE_H = ROOT / "06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json"


def test_stage01h_does_not_reclassify_or_reconsider_v2():
    stage_g = json.loads(STAGE_G.read_text())
    stage_h = json.loads(STAGE_H.read_text())
    assert stage_g["unique_status"] == "V2_QUALIFICATION_FAIL"
    assert stage_h["stage01g_status_preserved"] == "V2_QUALIFICATION_FAIL"
    assert stage_h["stage01g_failure_gate_preserved"] == "SHEAR3"
    assert stage_h["stage01g_failure_reclassified"] is False
    assert stage_h["v2_reconsideration_allowed"] is False
    assert stage_h["benchmark_data_regenerated"] is False
