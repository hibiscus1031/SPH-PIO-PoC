"""Deeply verify Stage 05B records and close the artifact index."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


HERE=Path(__file__).resolve(); STAGE05B=HERE.parents[1]; STAGE05=HERE.parents[3]; ROOT=HERE.parents[4]
TOP=STAGE05/"09_manifests"; REPORTS=STAGE05/"08_reports"


def sha_bytes(value:bytes)->str: return "sha256:"+hashlib.sha256(value).hexdigest()
def sha_file(path:Path)->str: return sha_bytes(path.read_bytes())
def canonical(value:Any)->bytes: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha_array(value:np.ndarray)->str:
    array=np.ascontiguousarray(value); digest=hashlib.sha256(); digest.update(str(array.dtype).encode()); digest.update(b"\0")
    digest.update(np.asarray(array.shape,dtype=np.int64).tobytes()); digest.update(array.tobytes())
    return "sha256:"+digest.hexdigest()
def write_json(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")


target=json.loads((TOP/"stage05b_target_manifest.json").read_text())
assert target["generated"] and target["record_count"]==384 and target["Stage05C_readable"]
seen=set(); failures=[]; loss_terms=[]; array_count=0
for entry in target["records"]:
    rid=entry["record_id"]
    if rid in seen: failures.append({"record_id":rid,"reason":"duplicate"})
    seen.add(rid)
    jp=ROOT/entry["json_path"]; npz=ROOT/entry["npz_path"]
    if sha_file(jp)!=entry["json_sha256"] or sha_file(npz)!=entry["npz_sha256"]:
        failures.append({"record_id":rid,"reason":"file_hash"}); continue
    meta=json.loads(jp.read_text()); claimed=meta.pop("canonical_sha256")
    if sha_bytes(canonical(meta))!=claimed or claimed!=entry["canonical_sha256"]:
        failures.append({"record_id":rid,"reason":"canonical_hash"})
    with np.load(npz,allow_pickle=False) as archive:
        arrays={key:archive[key] for key in archive.files}
    expected={"a_def","a_cm","a_cons","a_incompatible","y_def"}
    if set(arrays)!=expected: failures.append({"record_id":rid,"reason":"array_schema"}); continue
    for key,value in arrays.items():
        array_count+=1
        if sha_array(value)!=meta["array_hashes"][key]: failures.append({"record_id":rid,"reason":f"array_hash:{key}"})
        if not np.isfinite(value).all(): failures.append({"record_id":rid,"reason":f"nonfinite:{key}"})
    if arrays["a_def"].shape!=(64,2) or arrays["a_cons"].shape!=(64,2) or arrays["a_incompatible"].shape!=(64,2) or arrays["a_cm"].shape!=(2,):
        failures.append({"record_id":rid,"reason":"shape"})
    if not np.array_equal(arrays["y_def"],arrays["a_cons"]/meta["s_a"]): failures.append({"record_id":rid,"reason":"normalization"})
    loss_terms.append(float(np.mean(arrays["y_def"]**2)))

zero_loss=float(np.mean(loss_terms)); final=json.loads((TOP/"stage05b_final_manifest.json").read_text())
report_paths=sorted(REPORTS.glob("stage05b_*.md")); manifest_paths=sorted(TOP.glob("stage05b_*.json"))
freeze=json.loads((STAGE05B/"freeze/stage05b_freeze_record.json").read_text())
historical_mismatches=[]
for item in freeze["inputs"]:
    path=ROOT/item["path"]
    if sha_file(path)!=item["sha256"]: historical_mismatches.append(item["path"])
contract_hash=sha_file(STAGE05B/"contracts/conservative_discrete_defect_target_contract_v0_1.yaml")
decode_zero=all(value==0 for key,value in final["decode_counts"].items() if key.startswith("validation_") or key.startswith("sealed_"))
execution_zero=all(value==0 for value in final["execution_counts"].values())
audit={
    "schema":"sph-pio-poc.stage05b.target-record-verification.v1","record_count":len(seen),"array_count":array_count,
    "duplicate_count":384-len(seen),"failure_count":len(failures),"failures":failures[:100],"zero_baseline_loss_recomputed":zero_loss,
    "zero_baseline_absolute_error":abs(zero_loss-1.0),"zero_baseline_pass":abs(zero_loss-1.0)<=1e-12,
    "report_count":len(report_paths),"required_report_count":14,"top_manifest_count":len(manifest_paths),"required_top_manifest_count":8,
    "contract_sha256":contract_hash,"contract_hash_matches_freeze":contract_hash==freeze["contract_sha256"],
    "historical_hash_mismatches":historical_mismatches,"forbidden_decode_counts_zero":decode_zero,"execution_counts_zero":execution_zero,
}
audit["pass"]=(audit["record_count"]==384 and audit["array_count"]==1920 and audit["failure_count"]==0 and audit["zero_baseline_pass"]
               and len(report_paths)==14 and len(manifest_paths)==8 and audit["contract_hash_matches_freeze"] and not historical_mismatches
               and decode_zero and execution_zero and final["status"]=="CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED")
write_json(STAGE05B/"target_records/target_record_verification_audit.json",audit)
assert audit["pass"],audit

index_path=STAGE05B/"manifests/final_artifact_index.json"
write_json(STAGE05B/"manifests/artifact_index.json",{
    "schema":"sph-pio-poc.stage05b.intermediate-artifact-index.v1",
    "superseded_by":"stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/manifests/final_artifact_index.json",
    "role":"non_authoritative_execution_intermediate"
})
paths=[p for p in STAGE05B.rglob("*") if p.is_file() and p!=index_path and "__pycache__" not in p.parts and p.suffix!=".pyc" and p.name!=".DS_Store"]
paths+=report_paths
paths+=[p for p in manifest_paths if p.name!="stage05b_final_manifest.json"]
paths=sorted(set(paths),key=lambda p:str(p.relative_to(ROOT)))
artifacts=[{"path":str(p.relative_to(ROOT)),"sha256":sha_file(p),"size_bytes":p.stat().st_size} for p in paths]
index={"schema":"sph-pio-poc.stage05b.final-artifact-index.v1","artifact_count_excluding_index_and_final_manifest":len(artifacts),
       "artifacts":artifacts,"all_paths_unique":len({a["path"] for a in artifacts})==len(artifacts)}
index["canonical_listing_sha256"]=sha_bytes(canonical(artifacts)); write_json(index_path,index)
final["closure_audit"]={"path":str((STAGE05B/"target_records/target_record_verification_audit.json").relative_to(ROOT)),
    "sha256":sha_file(STAGE05B/"target_records/target_record_verification_audit.json"),"pass":True}
final["artifact_index"]={"path":str(index_path.relative_to(ROOT)),"sha256":sha_file(index_path),
    "artifact_count_excluding_index_and_final_manifest":len(artifacts),"canonical_listing_sha256":index["canonical_listing_sha256"]}
final["required_report_count"]=14; final["required_top_manifest_count"]=8; final["all_hashes_complete"]=True
write_json(TOP/"stage05b_final_manifest.json",final)
print(json.dumps({"pass":True,"records":384,"arrays":1920,"artifacts":len(artifacts),"zero_loss":zero_loss}))
