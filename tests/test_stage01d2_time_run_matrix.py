from pathlib import Path
import yaml


def test_time_matrix_is_exact_and_independent() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml").read_text())
    rows = {x["run_id"]: x for x in cfg["trajectory_matrix"]}
    selected = [rows[x] for x in cfg["time_study"]["run_ids"]]
    assert [x["dt"] for x in selected] == [1e-3, 5e-4, 2.5e-4, 1.25e-4]
    assert [x["steps"] for x in selected] == [200, 400, 800, 1600]
    assert all(x["resolution"] == 32 and x["support_ratio"] == 5.0 and x["t_final"] == 0.2 for x in selected)
