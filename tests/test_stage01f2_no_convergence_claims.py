from pathlib import Path


def test_stage01f2_report_uses_only_implementation_language() -> None:
    report = Path(__file__).resolve().parents[1] / "07_reports/stage_01f2_final_report.md"
    if not report.exists():
        return
    text = report.read_text(encoding="utf-8")
    for prohibited in ("V2_PASS", "V2_CONDITIONAL", "V3 eligibility"):
        assert prohibited not in text
