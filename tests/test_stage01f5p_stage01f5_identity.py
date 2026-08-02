import csv
import hashlib
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"
CONFIG = STAGE / "configs/preregistered_stage01f5p.yml"


def test_stage01f5_commit_tag_status_and_manifest_are_frozen():
    frozen = yaml.safe_load(CONFIG.read_text())["frozen_stage01f5"]
    assert frozen["evidence_commit"] == "ca297db20149765091312ac27843a8c20d4e9943"
    assert frozen["historical_status"] == "PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED"
    assert not frozen["status_changed"]
    tag_commit = subprocess.check_output(
        ("git", "rev-parse", frozen["tag"] + "^{}"), cwd=ROOT, text=True
    ).strip()
    assert tag_commit == frozen["evidence_commit"]
    with (ROOT / frozen["manifest"]).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 9
    assert all(
        hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
        == row["sha256"]
        for row in rows
    )
    evaluation = json.loads(
        (ROOT / "06_experiments/stage_01f5_requalification_design/results/stage01f5_evaluation.json").read_text()
    )
    assert evaluation["status"] == frozen["historical_status"]
