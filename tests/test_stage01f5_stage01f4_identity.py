import csv
import hashlib
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5_requalification_design"
CONFIG = STAGE / "configs/preregistered_stage01f5.yml"


def test_stage01f4_commit_status_tag_and_manifest_are_frozen():
    frozen = yaml.safe_load(CONFIG.read_text())["frozen_stage01f4"]
    assert frozen["evidence_commit"] == "82de6171a0be9818303acca539bffc8d3ee21c22"
    assert frozen["status"] == "PLATEAU_AWARE_PROTOCOL_APPROVED"
    evaluator = json.loads((ROOT / frozen["evaluator"]).read_text())
    assert evaluator["status"] == frozen["status"]
    tag_commit = subprocess.check_output(
        ("git", "rev-parse", frozen["tag"] + "^{}"), cwd=ROOT, text=True
    ).strip()
    assert tag_commit == frozen["evidence_commit"]
    with (ROOT / frozen["manifest"]).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 7
    assert all(
        hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
        == row["sha256"]
        for row in rows
    )


def test_stage01f3c_tag_and_historical_states_are_unchanged():
    config = yaml.safe_load(CONFIG.read_text())
    frozen = config["frozen_stage01f4"]
    tag_commit = subprocess.check_output(
        ("git", "rev-parse", frozen["stage01f3c_tag"] + "^{}"), cwd=ROOT, text=True
    ).strip()
    assert tag_commit == frozen["stage01f3c_tag_commit"]
    assert config["historical_states"]["stage01f3b"] == "MMS_CONVERGENCE_VERIFICATION_FAIL"
    assert config["historical_states"]["stage01f3c"] == "CT2_MIXED_OR_UNRESOLVED"
