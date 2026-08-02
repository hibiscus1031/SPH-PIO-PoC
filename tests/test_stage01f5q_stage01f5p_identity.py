import csv
import hashlib
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"
CONFIG = STAGE / "configs/formal_space_horizon_amendment.yml"


def test_stage01f5p_commit_tag_status_and_manifest_are_frozen():
    frozen = yaml.safe_load(CONFIG.read_text())["frozen_stage01f5p"]
    assert frozen["evidence_commit"] == "38487d66b40fa2c8dd65eb7aa6c279da4a8e5e2c"
    assert frozen["historical_status"] == "EXECUTION_MANIFEST_INCOMPLETE"
    assert not frozen["status_changed"]
    tag_commit = subprocess.check_output(
        ("git", "rev-parse", frozen["tag"] + "^{}"), cwd=ROOT, text=True
    ).strip()
    assert tag_commit == frozen["evidence_commit"]
    with (ROOT / frozen["manifest"]).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8
    assert all(
        hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
        == row["sha256"]
        for row in rows
    )
    old = json.loads(
        (ROOT / "06_experiments/stage_01f5p_branch_completeness/results/stage01f5p_evaluation.json").read_text()
    )
    assert old["status"] == frozen["historical_status"]
