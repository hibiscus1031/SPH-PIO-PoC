import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_validation_design"
SNAPSHOT = "ac8e06aa0ba3c5cc54fb567d1d40bd0f36e4487f"
ARCHIVE = "6cbfea24cf1f2fd55f2bad0b949083ed4ab953c3"
TAG = "stage-01f5b-plateau-aware-mms-requalification-pass"


def test_snapshot_archive_ancestry_diff_and_tag_are_reconciled():
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", SNAPSHOT, ARCHIVE],
        cwd=ROOT,
        check=True,
    )
    peeled = subprocess.run(
        ["git", "rev-list", "-n", "1", TAG],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert peeled == ARCHIVE

    observed = subprocess.run(
        ["git", "diff", "--name-status", SNAPSHOT, ARCHIVE],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    with (STAGE / "manifests/stage01f5b_commit_diff_audit.csv").open(newline="") as stream:
        audit = list(csv.DictReader(stream))
    expected = [f"{row['status']}\t{row['path']}" for row in audit]
    assert observed == expected
    assert all(row["scientific_or_qualification_change"] == "false" for row in audit)

    freeze = json.loads((STAGE / "results/stage01g_freeze_audit.json").read_text())
    assert freeze["frozen_identity_pass"]
    assert sum(freeze["diff_class_counts"].values()) == 2
    assert freeze["diff_class_counts"]["report_manifest_test_archive_metadata"] == 2
