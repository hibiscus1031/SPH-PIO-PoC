import csv
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_validation_design"
TAG = "stage-01f5b-plateau-aware-mms-requalification-pass"


def test_frozen_stage01f5b_artifacts_match_hashes_and_archive_tag():
    manifest = STAGE / "manifests/stage01f5b_frozen_sha256.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    for row in rows:
        path = ROOT / row["path"]
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
        archived = subprocess.run(
            ["git", "show", f"{TAG}:{row['path']}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert payload == archived

    inventory = ROOT / "06_experiments/stage_01f5b_requalification_execution/manifests/stage01f5b_final_evidence_sha256.csv"
    with inventory.open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 339


def test_stage01g_design_assets_match_their_provenance_manifest():
    manifest = STAGE / "manifests/stage01g_design_sha256_manifest.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 22
    assert len({row["path"] for row in rows}) == len(rows)
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
