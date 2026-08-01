from pathlib import Path


def test_formal_forward_is_no_grad() -> None:
    text = (Path(__file__).resolve().parents[1] / "06_experiments/stage_01d2_v2_requalification/stage01d2_worker.py").read_text()
    assert "with torch.no_grad():" in text
    assert text.index("with torch.no_grad():") < text.index("for step in range(steps + 1)")
