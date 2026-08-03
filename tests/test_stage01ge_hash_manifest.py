import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "06_experiments/stage_01ge_evaluator_qualification/manifests/stage01ge_evaluator_sha256.csv"


def test_all_evaluator_and_report_generator_hashes_are_frozen():
    with MANIFEST.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 9
    assert len({row["path"] for row in rows}) == 9
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
