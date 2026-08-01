import csv,hashlib,json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]; MANIFEST=ROOT/"06_experiments/stage_01e_error_decomposition/configs/stage01d2_frozen_sha256_manifest.csv"


def test_frozen_stage01d2_identity_and_unique_status() -> None:
    with MANIFEST.open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream): assert hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest()==row["sha256"]
    assert subprocess.check_output(("git","rev-list","-n","1","stage-01d2-v2-requalification-fail"),cwd=ROOT,text=True).strip()=="8dcb26bac834da4b5deb62674d053c9e83df69e3"
    evidence=json.loads((ROOT/"06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json").read_text())
    assert evidence["final_status"]=="STAGE01D2_V2_REQUALIFICATION_FAIL"
