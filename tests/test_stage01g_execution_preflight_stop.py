import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "06_experiments/stage_01g_validation_execution"


def test_preflight_has_one_blocking_failure_and_no_numeric_execution():
    with (EXECUTION / "manifests/stage01g_preflight_audit.csv").open(newline="") as stream:
        checks = list(csv.DictReader(stream))
    assert len(checks) == 7
    failures = [row for row in checks if row["status"] == "FAIL"]
    assert len(failures) == 1
    assert failures[0]["check_id"] == "PREFLIGHT6"
    assert failures[0]["blocking"] == "true"

    preflight = json.loads((EXECUTION / "results/preflight_audit.json").read_text())
    assert preflight["overall_status"] == "FAIL"
    assert preflight["stop_before_benchmark"] is True
    assert preflight["evaluator_audit"]["executable_evaluator_candidates"] == []
    assert preflight["evaluator_audit"]["expected_sha256"] is None

    evaluation = json.loads((EXECUTION / "results/stage01g_evaluation.json").read_text())
    assert evaluation["unique_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert evaluation["benchmark_execution_count"] == 0
    assert evaluation["executed_run_ids"] == []
    assert evaluation["trajectory_count"] == 0
    assert evaluation["checkpoint_count"] == 0
    assert evaluation["reference_data_count"] == 0
    assert set(evaluation["shear_gates"].values()) == {"NOT_EVALUATED"}
    assert set(evaluation["acoustic_gates"].values()) == {"NOT_EVALUATED"}


def test_preflight_evidence_matches_sha256_manifest():
    with (EXECUTION / "manifests/stage01g_preflight_evidence_sha256.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 12
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
