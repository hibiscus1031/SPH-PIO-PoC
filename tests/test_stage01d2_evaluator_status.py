from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "06_experiments/stage_01d2_v2_requalification/analyze_stage01d2.py"
SPEC = spec_from_file_location("stage01d2_analysis", PATH); MOD = module_from_spec(SPEC); SPEC.loader.exec_module(MOD)


def base() -> dict:
    return {"evidence_complete": True, "prerequisite_pass": True, "conservation_pass": True, "resource_pass": True, "ad_pass": True, "disorder_status": "D_PASS", "mach_complete": True, "time_pass": True, "space_pass": True, "provenance_pass": True}


def test_unique_status_precedence() -> None:
    case = base(); assert MOD.classify_status(case) == "STAGE01D2_V2_REQUALIFIED_PASS"
    case["space_pass"] = False; assert MOD.classify_status(case) == "STAGE01D2_V2_REQUALIFIED_CONDITIONAL"
    case["resource_pass"] = False; assert MOD.classify_status(case) == "STAGE01D2_V2_REQUALIFICATION_FAIL"
    case["evidence_complete"] = False; assert MOD.classify_status(case) == "STAGE01D2_EVIDENCE_INCOMPLETE"
