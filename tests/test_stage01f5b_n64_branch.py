import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_n64_branch_has_seven_runs_and_four_frozen_triggers():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    assert len(config["phases"]["K"]["run_ids"]) == 7
    assert len(config["n64_branch"]["triggers"]) == 4
    decision = STAGE / "manifests/n64_trigger_decision.json"
    if decision.exists():
        payload = json.loads(decision.read_text())
        assert payload["immutable"] is True
        assert payload["decision"] in {"TRIGGERED", "NOT_TRIGGERED"}


def test_authorized_infrastructure_retry_is_preserved_and_bounded():
    original = STAGE / "runs/f5_n64_smoke_a/status.json"
    retry = STAGE / "runs/f5_n64_smoke_a_infra_retry1/status.json"
    failure = STAGE / "runs/f5_n64_smoke_a/infrastructure_failure.json"
    if not all(path.exists() for path in (original, retry, failure)):
        return
    original_payload = json.loads(original.read_text())
    retry_payload = json.loads(retry.read_text())
    failure_payload = json.loads(failure.read_text())
    assert original_payload["status"] == "FAIL"
    assert retry_payload["status"] == "PASS"
    assert failure_payload["solver_worker_launched"] is False
    assert failure_payload["numerical_state_generated"] is False
    assert failure_payload["retry_authorized"] == "f5_n64_smoke_a_infra_retry1"
    retry_markers = sorted(path.parent.name for path in (STAGE / "runs").glob("f5_n64_smoke_a_infra_retry*/status.json"))
    assert retry_markers == ["f5_n64_smoke_a_infra_retry1"]
