import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bundle_v3_and_69_dry_rows_are_identical():
    bundle_path = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/manifests/stage01f5_execution_bundle_v3.json"
    bundle = json.loads(bundle_path.read_text())
    assert bundle["status"] == "FORMAL_SPACE_EXECUTION_BUNDLE_READY"
    assert bundle["numerical_runs_executed"] == 0
    dry_path = ROOT / bundle["dry_resolution"]["path"]
    assert hashlib.sha256(dry_path.read_bytes()).hexdigest() == bundle["dry_resolution"]["sha256"]
    with dry_path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 69
    assert all(row["resolution_status"] == "RESOLVED" for row in rows)

