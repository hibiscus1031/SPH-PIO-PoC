import csv
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_execution_preflight_v2"
G_TAG = "stage-01g-independent-validation-design-approved"
G_COMMIT = "fa3c4f43625ec3436820d83c26947d47ed0ba5c8"


def _git(*args, text=True):
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=text
    ).stdout


def test_stage01g_annotated_tag_and_nine_frozen_blobs_are_identical():
    assert _git("cat-file", "-t", G_TAG).strip() == "tag"
    assert _git("rev-list", "-n", "1", G_TAG).strip() == G_COMMIT
    with (STAGE / "manifests/stage01gv2_identity_sha256.csv").open(newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["scope"] == "stage01g"]
    assert len(rows) == 9
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
        assert payload == _git("show", f"{G_TAG}:{row['path']}", text=False)
        assert row["verification"] == "SHA256_AND_TAG_BLOB_MATCH"

    evaluation = json.loads(
        (ROOT / "06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json").read_text()
    )
    assert evaluation["unique_status"] == "INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED"
    assert evaluation["numerical_execution_count"] == 0
    assert evaluation["v2_status"] is None


def test_preflight_v2_is_add_only_relative_to_stage01ge_commit():
    changed = _git(
        "diff", "--name-only", "1641ff5f05fa91b8faed49a91edf062f4a90db07"
    ).splitlines()
    allowed_prefixes = (
        "06_experiments/stage_01g_execution_preflight_v2/",
        "07_reports/stage01g_preflight_v2_",
        "tests/test_stage01gv2_",
    )
    assert changed
    assert all(path.startswith(allowed_prefixes) for path in changed)
