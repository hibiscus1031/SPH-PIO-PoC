import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "06_experiments/stage_01g_execution_preflight_v2"


def test_all_prohibited_execution_and_generation_counts_are_zero():
    audit = json.loads((V2 / "results/stage01gv2_zero_execution_audit.json").read_text())
    for key in (
        "benchmark_execution_count",
        "solver_call_count",
        "rk2_call_count",
        "dop853_call_count",
        "trajectory_count",
        "checkpoint_count",
        "reference_generation_count",
        "training_run_count",
        "label_generation_count",
    ):
        assert audit[key] == 0
    assert audit["v2_status_generated"] is False
    assert audit["current_v2_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert audit["stage02_started"] is False
    assert audit["status"] == "PASS"


def test_preflight_v2_contains_only_static_audit_artifacts():
    forbidden_suffixes = {".npz", ".npy", ".pt", ".pth", ".ckpt", ".h5", ".hdf5"}
    forbidden_names = {"trajectory", "checkpoint", "reference_data", "stage01g_evaluation.json"}
    files = [path for path in V2.rglob("*") if path.is_file()]
    assert files
    assert not any(path.suffix.lower() in forbidden_suffixes for path in files)
    assert not any(any(name in part.lower() for name in forbidden_names) for path in files for part in path.parts)
