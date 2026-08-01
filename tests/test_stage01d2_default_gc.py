from pathlib import Path


def test_worker_requires_default_gc_throughout() -> None:
    text = (Path(__file__).resolve().parents[1] / "06_experiments/stage_01d2_v2_requalification/stage01d2_worker.py").read_text()
    assert text.count("gc.isenabled()") >= 3
    assert "gc.disable" not in text
    assert "gc.enable" not in text
