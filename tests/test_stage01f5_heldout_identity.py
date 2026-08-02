from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
F4 = ROOT / "06_experiments/stage_01f4_protocol_adjudication/configs/preregistered_stage01f4.yml"
F5 = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"


def test_n28_heldout_matches_stage01f4_sealed_identity():
    old = yaml.safe_load(F4.read_text())["prospective_heldout"]["sealed_configuration"]
    new = yaml.safe_load(F5.read_text())["heldout"]
    assert new["resolution"] == old["resolution"] == 28
    assert new["support_ratio"] == old["support_ratio"] == 4.75
    assert new["t_final"] == old["t_final"] == 0.015
    assert new["dt"] == old["dt"]
    assert new["particle_count"] == 784
    assert not new["prior_data_used_in_design"]
    assert all(new["requirements_explicitly_not_imposed"].values())
