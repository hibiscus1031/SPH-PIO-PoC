import csv
import hashlib
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f3c_ct2_adjudication/configs/preregistered_stage01f3c.yml"


def test_stage01f3b_frozen_identity():
    config = yaml.safe_load(CONFIG.read_text())
    frozen = config["frozen_stage01f3b"]
    assert frozen["evidence_commit"] == "5a0ef2556a7128865f07d60abcd54666ca5fba47"
    evaluator = json.loads((ROOT / frozen["evaluator"]).read_text())
    assert evaluator["status"] == "MMS_CONVERGENCE_VERIFICATION_FAIL"
    tag = subprocess.check_output(
        ("git", "rev-list", "-n", "1", frozen["tag"]), cwd=ROOT, text=True
    ).strip()
    assert tag == frozen["evidence_commit"]
    with (ROOT / frozen["manifest"]).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) >= 11
    assert all(
        hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
        for row in rows
    )
