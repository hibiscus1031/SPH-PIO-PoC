import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair"


def test_dry_resolution_is_explicit_hash_linked_and_passes_12_of_12():
    with (STAGE / "results/stage01gr_dry_run_results.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 12
    assert len({row["run_id"] for row in rows}) == 12
    assert {row["status"] for row in rows} == {"PASS"}
    for row in rows:
        assert all(row[key] == "True" for key in (
            "config_resolve", "directory_resolve", "metadata_schema",
            "evaluator_schema", "provenance_schema", "hash_linked",
        ))


def test_minimal_smoke_passes_all_infrastructure_boundaries_only():
    result = json.loads((STAGE / "results/stage01gr_minimal_smoke.json").read_text())
    assert result["run_id"] == "g_shear_n24_infra_smoke"
    assert result["status"] == "PASS"
    assert result["steps"] <= 1
    assert result["solver_entry"] == "PASS"
    assert result["diagnostic_initialization"] == "PASS"
    assert result["output_schema"] == "PASS"
    assert result["child_reclaimed"] is True
    assert result["parent_scalar_only"] is True
    assert result["type_error"] is False
    assert result["key_error"] is False
    assert result["attribute_error"] is False
    assert result["formal_benchmark"] is False
    assert result["benchmark_metrics_generated"] is False
    assert result["evaluator_qualification_performed"] is False
    assert result["v2_evidence_generated"] is False


def test_repair_final_status_is_ready_without_changing_v2_status():
    evaluation = json.loads((STAGE / "results/stage01gr_evaluation.json").read_text())
    assert evaluation["unique_status"] == "EXECUTION_INFRA_READY_FOR_BENCHMARK"
    assert evaluation["stage01g_v2_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert evaluation["formal_benchmark_run_count"] == 0
    assert not any(evaluation["downstream"].values())
