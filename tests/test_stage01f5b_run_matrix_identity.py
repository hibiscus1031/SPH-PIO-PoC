import csv
import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_69_run_ids_and_output_directories_are_unique_and_frozen():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    path = ROOT / config["frozen_stage01f5q"]["matrix"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == config["frozen_stage01f5q"]["matrix_sha256"]
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 69
    assert len({row["run_id"] for row in rows}) == 69
    assert len({row["output_dir"] for row in rows}) == 69

