from pathlib import Path


def test_no_manual_collection_or_gc_disable_in_worker() -> None:
    text = (Path(__file__).resolve().parents[1] / "06_experiments/stage_01d2_v2_requalification/stage01d2_worker.py").read_text()
    assert "gc.collect(" not in text
    assert "gc.disable(" not in text
