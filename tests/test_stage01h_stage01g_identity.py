import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE01G_COMMIT = "448b090be03d5e5201096f37962cebfd962e3e6a"
PATHS = (
    "06_experiments/stage_01g_validation_execution/results/stage01g_execution_final_state.json",
    "06_experiments/stage_01g_validation_execution/results/stage01g_shear_gates_reapplication_01.json",
    "07_reports/stage01g_shear_execution_report.md",
    "07_reports/stage01g_v2_qualification_report.md",
    *(
        f"06_experiments/stage_01g_validation_execution/evaluator_results/{run_id}.reapplication_01.json"
        for run_id in (
            "g_shear_n24", "g_shear_n32", "g_shear_n48",
            "g_shear_n32_dt_half", "g_shear_n48_rep2",
        )
    ),
)


def test_stage01g_execution_files_remain_byte_identical_to_failed_commit():
    for relative in PATHS:
        current = (ROOT / relative).read_bytes()
        frozen = subprocess.check_output(("git", "show", f"{STAGE01G_COMMIT}:{relative}"), cwd=ROOT)
        assert hashlib.sha256(current).hexdigest() == hashlib.sha256(frozen).hexdigest()


def test_stage01g_failure_remains_shear3_only():
    import json

    final_state = json.loads((ROOT / PATHS[0]).read_text())
    gates = json.loads((ROOT / PATHS[1]).read_text())
    assert final_state["unique_status"] == "V2_QUALIFICATION_FAIL"
    assert [name for name, item in gates["gates"].items() if item["status"] == "FAIL"] == ["SHEAR3"]
    assert gates["gates"]["SHEAR3"]["evidence"] == 0.027949503268503754
