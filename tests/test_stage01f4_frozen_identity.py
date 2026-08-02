import csv
import hashlib
import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f4_protocol_adjudication"
CONFIG = STAGE / "configs/preregistered_stage01f4.yml"


def test_stage01f3c_commit_status_tag_and_manifest_are_frozen():
    config = yaml.safe_load(CONFIG.read_text())
    frozen = config["frozen_stage01f3c"]
    expected_commit = "f831d4fa7d63ad3357e2b1e84c1260d7f3c46a2e"
    assert frozen == {
        "evidence_commit": expected_commit,
        "status": "CT2_MIXED_OR_UNRESOLVED",
        "tag": "stage-01f3c-ct2-mixed-or-unresolved",
        "evaluator": (
            "06_experiments/stage_01f3c_ct2_adjudication/"
            "results/stage01f3c_evaluation.json"
        ),
        "manifest": (
            "06_experiments/stage_01f4_protocol_adjudication/"
            "configs/stage01f3c_frozen_sha256_manifest.csv"
        ),
    }
    tag_commit = subprocess.check_output(
        ("git", "rev-list", "-n", "1", frozen["tag"]), cwd=ROOT, text=True
    ).strip()
    assert tag_commit == expected_commit
    evaluator = json.loads((ROOT / frozen["evaluator"]).read_text())
    assert evaluator["status"] == frozen["status"]
    with (ROOT / frozen["manifest"]).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 16
    assert all(
        hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
        == row["sha256"]
        for row in rows
    )


def test_stage01f3b_historical_status_is_unchanged():
    config = yaml.safe_load(CONFIG.read_text())
    frozen = config["frozen_stage01f3b"]
    evaluator = json.loads((ROOT / frozen["evaluator"]).read_text())
    assert frozen["status"] == "MMS_CONVERGENCE_VERIFICATION_FAIL"
    assert evaluator["status"] == frozen["status"]
