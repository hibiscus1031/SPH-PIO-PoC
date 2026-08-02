import hashlib
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_stage01f5q_commit_tag_and_artifacts_are_frozen():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    frozen = config["frozen_stage01f5q"]
    assert frozen["evidence_commit"] == "8ab58b8647c1dd1e5cfe71a77cf6ec71c93a1484"
    assert subprocess.check_output(("git", "rev-list", "-n", "1", frozen["tag"]), cwd=ROOT, text=True).strip() == frozen["evidence_commit"]
    import csv
    with (STAGE / "manifests/stage01f5q_frozen_sha256_manifest.csv").open() as stream:
        for row in csv.DictReader(stream):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]

