import csv,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/"06_experiments/stage_01f3_mms_convergence"

def test_stage01f2_manifest_and_authoritative_status()->None:
    with (STAGE/"configs/stage01f2_frozen_sha256_manifest.csv").open() as stream:
        rows=list(csv.DictReader(stream))
    assert all(hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest()==row["sha256"] for row in rows)
    evidence=json.loads((ROOT/"06_experiments/stage_01f2_mms_implementation/results/stage01f2_evaluation_v2.json").read_text())
    assert evidence["status"]=="MMS_IMPLEMENTATION_VERIFIED_PASS"
    assert subprocess.check_output(("git","rev-list","-n","1","stage-01f2-mms-implementation-verified-pass"),cwd=ROOT,text=True).strip()=="dd28381d176b02483ebe012eebedd665252b5c56"

def test_cleaned_initial_ad_evidence_is_not_reintroduced()->None:
    result=ROOT/"06_experiments/stage_01f2_mms_implementation/results"
    assert not (result/"source_ad_fd.csv").exists()
    assert not (result/"source_ad_fd_summary.json").exists()
