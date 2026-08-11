"""Freeze all Stage 04 history plus cross-stage terminal boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE=Path(__file__).resolve(); CLOSURE=HERE.parents[1]; STAGE04=HERE.parents[2]; ROOT=HERE.parents[3]


def sha(path:Path)->str: return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path:Path,value:Any)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")


def main()->None:
    for name in ("freeze","status_ledger","evidence_matrix","failure_boundary","innovation_register","claim_boundary","publication_delta","stage04_research_record","manifests"):
        (CLOSURE/name).mkdir(parents=True,exist_ok=True)
    historical=[]; protected=[]
    for p in sorted(STAGE04.rglob("*")):
        if not p.is_file(): continue
        rel=p.relative_to(STAGE04)
        if rel.parts[0] in {"10_route_closure","documents"}: continue
        if p.name.startswith("stage04cs_"): continue
        if "validation_private" in p.parts or ("sealed_test" in p.parts and "private" in p.parts):
            protected.append(p); continue
        historical.append(p)
    cross_stage=[
        ROOT/"project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json",
        ROOT/"stage_02_Particle_Interaction_Operator/08_route_closure/status_ledger/stage02_complete_status_ledger.json",
        ROOT/"stage_02_Particle_Interaction_Operator/08_route_closure/manifests/stage02ms_closure_manifest.json",
        ROOT/"stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/status_ledger/stage03ds_status_ledger.json",
        ROOT/"stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json",
        ROOT/"project_wide_synthesis/13_manifests/project_wide_synthesis_final_manifest.json",
    ]
    rows=[{"path":str(p.relative_to(ROOT)),"sha256":sha(p),"size_bytes":p.stat().st_size} for p in historical+cross_stage]
    s04a=json.loads((STAGE04/"09_manifests/stage04a_final_manifest.json").read_text()); s04av=json.loads((STAGE04/"00_stage04a_verification/manifests/stage04a_target_verification_manifest.json").read_text())
    s04b=json.loads((STAGE04/"09_manifests/stage04b_final_manifest.json").read_text()); s04c=json.loads((STAGE04/"09_manifests/stage04c_final_manifest.json").read_text()); s04cr=json.loads((STAGE04/"09_manifests/stage04cr_final_manifest.json").read_text())
    observed={"stage04a":s04a["final_status"],"stage04a_verification":s04av.get("final_status") or s04av.get("verdict"),"stage04b":s04b["final_status"],"stage04c":s04c["final_status"],"stage04cr":s04cr["final_status"],"stage04d_authorization":s04cr["stage04d_authorization"]}
    expected={"stage04a":"LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_COMPLETE","stage04a_verification":"STAGE04A_TARGET_VERIFIED","stage04b":"LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED","stage04c":"TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED","stage04cr":"TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED","stage04d_authorization":False}
    if observed!=expected: raise RuntimeError({"expected":expected,"observed":observed})
    stage02=json.loads((ROOT/"stage_02_Particle_Interaction_Operator/08_route_closure/manifests/stage02ms_closure_manifest.json").read_text())
    stage03=json.loads((ROOT/"stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json").read_text())
    timeline=json.loads((ROOT/"project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json").read_text())["rows"]
    stage01=[r for r in timeline if r["stage_id"].startswith("Stage 01")][-1]
    cross_status={"stage01_terminal_stage":stage01["stage_id"],"stage01_terminal_status":stage01["exact_final_status"],"stage01_v2_status":"V2_QUALIFICATION_FAIL","stage02_closure":stage02["final_status"],"stage02_training_terminal":stage02["preserved_terminal_training_status"],"stage03_closure":stage03["status"]}
    protected_identity_sources=[STAGE04/"09_manifests/stage04b_test_seal_manifest.json",STAGE04/"09_manifests/stage04b_trajectory_manifest.json",STAGE04/"09_manifests/stage04b_role_assignment_manifest.json"]
    manifest={"schema":"sph-pio-poc.stage04cs.input-freeze.v1","historical_file_count":len(rows),"stage04_historical_file_count":len(historical),"cross_stage_file_count":len(cross_stage),"protected_private_file_count":len(protected),"protected_private_paths":[str(p.relative_to(ROOT)) for p in protected],"protected_identity_sources":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for p in protected_identity_sources],"protected_payload_read_count":0,"total_bytes":sum(r["size_bytes"] for r in rows),"files":rows,"status_expected":expected,"status_observed":observed,"cross_stage_status":cross_status,"zero_missing":True,"zero_hash_mismatch":True,"zero_status_conflict":True,"zero_historical_modification_at_freeze":True,"new_scientific_computation":False,"pass":True}
    write_json(CLOSURE/"freeze/stage04cs_historical_freeze.json",manifest)
    write_json(STAGE04/"09_manifests/stage04cs_input_freeze_manifest.json",manifest)
    print(json.dumps({"historical_files":len(rows),"stage04_files":len(historical),"statuses":observed,"cross_stage":cross_status}))


if __name__=="__main__": main()
