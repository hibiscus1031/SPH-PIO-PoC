from pathlib import Path


def test_parent_uses_one_waited_child_per_case() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "06_experiments/stage_01d2_v2_requalification/run_stage01d2_campaign.py").read_text()
    assert "subprocess.Popen(command" in text
    assert "child.wait()" in text
    assert '"scalar_only_protocol": True' in text
    assert "stage01d2_worker.py" in text and "stage01d2_ad_worker.py" in text
