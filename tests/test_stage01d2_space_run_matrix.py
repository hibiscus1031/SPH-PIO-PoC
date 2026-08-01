from pathlib import Path
import yaml


def test_space_and_disorder_matrices_are_exact() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml").read_text())
    rows = {x["run_id"]: x for x in cfg["trajectory_matrix"]}
    selected = [rows[x] for x in cfg["space_study"]["run_ids"]]
    assert [(x["resolution"], x["support_ratio"]) for x in selected] == [(16,4.0),(24,4.5),(32,5.0)]
    disorder = cfg["disorder_study"]
    assert disorder["jitter_05_seeds"] == [20261001, 20261019, 20261037]
    assert disorder["jitter_10_seeds"] == [20261061, 20261079, 20261103]
