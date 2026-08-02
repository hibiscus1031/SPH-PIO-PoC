import csv
import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_every_numerical_source_file_matches_frozen_commit_manifest():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    with (STAGE / "manifests/numerical_source_identity.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 103
    assert all(hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["frozen_sha256"] for row in rows)
    canonical = "".join(f"{row['path']},{row['frozen_sha256']}\n" for row in rows).encode()
    assert hashlib.sha256(canonical).hexdigest() == config["numerical_source"]["canonical_tree_sha256"]

