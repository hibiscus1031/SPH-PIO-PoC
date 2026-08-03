import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_validation_execution"
EXPECTED_RUNS = {
    "g_shear_n24",
    "g_shear_n32",
    "g_shear_n48",
    "g_shear_n32_dt_half",
    "g_shear_n48_rep2",
    "g_acoustic_e5e3_n24",
    "g_acoustic_e5e3_n32",
    "g_acoustic_e5e3_n48",
    "g_acoustic_e5e3_n32_dt_half",
    "g_acoustic_e5e3_n48_rep2",
    "g_acoustic_e2p5e3_n48",
    "g_acoustic_e1e2_n48",
}


def test_all_three_infrastructure_failures_are_retained_without_reclassification():
    expected = {
        "": "TypeError",
        ".infra_retry1": "KeyError",
        ".infra_retry2": "AttributeError",
    }
    for suffix, failure_type in expected.items():
        run = STAGE / "runs/g_shear_n24"
        summary = json.loads((run / f"summary{suffix}.json").read_text())
        status = json.loads((run / f"status{suffix}.json").read_text())
        assert summary["status"] == status["status"] == "FAIL"
        assert summary["failure_type"] == failure_type
        assert status["child_reclaimed"] is True
        assert status["parent_scalar_only"] is True
        assert (run / f"failure{suffix}.txt").is_file()


def test_no_formal_run_completed_and_phase_b_never_started():
    evaluation = json.loads((STAGE / "results/stage01g_execution_evaluation.json").read_text())
    assert evaluation["executed_run_count"] == 0
    assert evaluation["executed_run_ids"] == []
    assert set(evaluation["missing_run_ids"]) == EXPECTED_RUNS
    assert not (STAGE / "results/stage01g_phase_b_preflight.json").exists()
    assert not (STAGE / "results/stage01g_phase_b_execution.json").exists()
    assert not list((STAGE / "checkpoints").glob("*.npz"))
    assert not list((STAGE / "references").glob("*.npz"))


def test_unique_status_is_evidence_incomplete_and_downstream_is_frozen():
    evaluation = json.loads((STAGE / "results/stage01g_execution_evaluation.json").read_text())
    assert evaluation["unique_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert evaluation["current_v2_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert evaluation["shear_gates"] == "NOT_EVALUATED"
    assert evaluation["acoustic_gates"] == "NOT_EVALUATED"
    assert evaluation["uncertainty_complete"] is False
    assert evaluation["provenance_complete"] is False
    assert not any(evaluation["downstream"].values())


def test_final_execution_evidence_manifest_is_complete_and_self_consistent():
    manifest = STAGE / "manifests/stage01g_execution_evidence_sha256.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 40
    assert len({row["path"] for row in rows}) == 40
    for row in rows:
        path = ROOT / row["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
