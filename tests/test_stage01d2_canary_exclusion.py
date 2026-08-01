from pathlib import Path
import yaml


def test_stage01dp_canaries_are_not_in_formal_matrix() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml").read_text())
    assert cfg["scope"]["stage01dp_canaries_are_formal_v2_data"] is False
    assert all(row["run_id"].startswith("stage01d2_") for row in cfg["trajectory_matrix"])
    assert all("canary" not in row["run_id"] for row in cfg["trajectory_matrix"])
