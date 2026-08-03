import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2_MANIFEST = ROOT / "06_experiments/stage_01g_execution_preflight_v2/manifests/stage01gv2_identity_sha256.csv"
G_MANIFEST = ROOT / "06_experiments/stage_01gp_preexecution_audit/manifests/stage01g_frozen_sha256_manifest.csv"
GE_MANIFEST = ROOT / "06_experiments/stage_01ge_evaluator_qualification/manifests/stage01ge_evaluator_sha256.csv"


def _rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def test_preflight_identity_manifest_reconciles_both_authoritative_manifests():
    combined = _rows(V2_MANIFEST)
    assert len(combined) == 18
    assert len({row["path"] for row in combined}) == 18
    combined_identity = {(row["path"], row["sha256"]) for row in combined}
    source_identity = {
        (row["path"], row["sha256"])
        for row in _rows(G_MANIFEST) + _rows(GE_MANIFEST)
    }
    assert combined_identity == source_identity
    assert sum(row["scope"] == "stage01g" for row in combined) == 9
    assert sum(row["scope"] == "stage01ge" for row in combined) == 9
    for row in combined:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
