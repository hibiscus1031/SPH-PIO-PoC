import csv
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "06_experiments/stage_01gp_preexecution_audit"
G_TAG = "stage-01g-independent-validation-design-approved"
G_COMMIT = "fa3c4f43625ec3436820d83c26947d47ed0ba5c8"
F5_TAG = "stage-01f5b-plateau-aware-mms-requalification-pass"
F5_ARCHIVE = "6cbfea24cf1f2fd55f2bad0b949083ed4ab953c3"


def _git(*args, text=True):
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=text
    ).stdout


def test_stage01g_tag_and_all_nine_frozen_files_match():
    assert _git("cat-file", "-t", G_TAG).strip() == "tag"
    assert _git("rev-list", "-n", "1", G_TAG).strip() == G_COMMIT
    manifest = AUDIT / "manifests/stage01g_frozen_sha256_manifest.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 9
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
        assert payload == _git("show", f"{G_TAG}:{row['path']}", text=False)
    evaluation = json.loads((ROOT / "06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json").read_text())
    assert evaluation["unique_status"] == "INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED"
    assert evaluation["numerical_execution_count"] == 0
    assert evaluation["v2_status"] is None


def test_stage01f5b_identity_and_stage01g_add_only_boundary_hold():
    assert _git("cat-file", "-t", F5_TAG).strip() == "tag"
    assert _git("rev-list", "-n", "1", F5_TAG).strip() == F5_ARCHIVE
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", "ac8e06aa0ba3c5cc54fb567d1d40bd0f36e4487f", F5_ARCHIVE],
        cwd=ROOT,
        check=True,
    )
    f5 = ROOT / "06_experiments/stage_01f5b_requalification_execution"
    evaluation = json.loads((f5 / "results/stage01f5b_evaluation.json").read_text())
    assert evaluation["unique_status"] == "PLATEAU_AWARE_MMS_REQUALIFICATION_PASS"
    assert evaluation["n64_decision"] == "TRIGGERED"
    assert evaluation["gate_blocks"]["n64_branch"]
    assert evaluation["gate_blocks"]["determinism"]
    assert all(evaluation["gate_blocks"].values())
    with (f5 / "manifests/stage01f5b_final_evidence_sha256.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 339

    paths = _git("diff", "--name-only", F5_ARCHIVE, G_COMMIT).splitlines()
    assert len(paths) == 23
    assert not any(path.startswith("01_solver/") for path in paths)
    assert not any(path.startswith("06_experiments/stage_01f5b_requalification_execution/") for path in paths)
    assert not any(path.startswith("07_reports/stage_01f5b_") for path in paths)


def test_stage01gp_audit_assets_match_provenance_manifest():
    manifest = AUDIT / "manifests/stage01gp_audit_sha256_manifest.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 24
    assert len({row["path"] for row in rows}) == 24
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
