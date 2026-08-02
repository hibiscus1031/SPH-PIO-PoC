import csv,hashlib,json,subprocess
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/"06_experiments/stage_01f3b_mms_convergence";CFG=yaml.safe_load((STAGE/"configs/preregistered_stage01f3b.yml").read_text())

def test_stage01f3r_frozen_identity_and_status()->None:
    with (STAGE/"configs/stage01f3r_frozen_sha256_manifest.csv").open() as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==14
    assert all(hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest()==row["sha256"] for row in rows)
    assert json.loads((ROOT/CFG["frozen_stage01f3r"]["evaluator"]).read_text())["status"]=="SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT"
    assert subprocess.check_output(("git","rev-list","-n","1",CFG["frozen_stage01f3r"]["tag"]),cwd=ROOT,text=True).strip()==CFG["frozen_stage01f3r"]["evidence_commit"]
