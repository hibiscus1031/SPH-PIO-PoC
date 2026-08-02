import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/"06_experiments/stage_01f3b_mms_convergence/evaluate_stage01f3b.py";SPEC=importlib.util.spec_from_file_location("f3b_eval",PATH);MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)

def base()->dict[str,bool]:
    return {"evidence_complete":True,"provenance_complete":True,"prerequisite":True,"semidiscrete_time":True,"continuous_time":True,"hard_paths":True,"balance_resources":True,"determinism":True,"reference_source_topology":True,"space_formal_pass":True,"space_platform_explainable":True}

def test_unique_status_truth_table()->None:
    case=base();assert MOD.classify_status(case)=="MMS_CONVERGENCE_VERIFICATION_PASS"
    case=base();case["space_formal_pass"]=False;assert MOD.classify_status(case)=="MMS_CONVERGENCE_VERIFICATION_CONDITIONAL"
    case=base();case["semidiscrete_time"]=False;assert MOD.classify_status(case)=="MMS_CONVERGENCE_VERIFICATION_FAIL"
    case=base();case["evidence_complete"]=False;assert MOD.classify_status(case)=="MMS_CONVERGENCE_EVIDENCE_INCOMPLETE"
