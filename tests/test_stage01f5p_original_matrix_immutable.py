import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"
ORIGINAL = ROOT / "06_experiments/stage_01f5_requalification_design/manifests/stage01f5_run_matrix.csv"
EXTENDED = STAGE / "manifests/stage01f5_execution_run_matrix_v2.csv"


def test_original_matrix_hash_and_extended_prefix_are_identical():
    original_lines = ORIGINAL.read_text().splitlines()
    extended_lines = EXTENDED.read_text().splitlines()
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == "d0e84aed88018c5ed9edddc6fd15240cfc319b016f768c90f528053bd3bf9a80"
    assert len(original_lines) == 65
    assert extended_lines[:65] == original_lines


def test_all_64_original_row_hashes_match_amendment_manifest():
    manifest = json.loads((STAGE / "manifests/stage01f5p_amendment_manifest.json").read_text())
    lines = ORIGINAL.read_text().splitlines()[1:]
    hashes = manifest["original_matrix"]["row_hashes"]
    assert len(hashes) == len(lines) == 64
    for expected, line in zip(hashes, lines, strict=True):
        assert expected["run_id"] == line.split(",", 1)[0]
        assert expected["sha256"] == hashlib.sha256(line.encode()).hexdigest()
