from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_stage01f_code_is_not_connected_to_dynamic_solver()->None:
    paths=list((ROOT/"01_solver/manufactured_solutions").glob("*.py"))+list((ROOT/"06_experiments/stage_01f_mms_design").glob("*.py")); text="\n".join(path.read_text() for path in paths)
    assert "dynamic_solver" not in text and "explicit_midpoint_dynamic_step" not in text and "rollout_periodic" not in text
