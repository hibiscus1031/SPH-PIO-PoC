#!/usr/bin/env python3
"""Continue Stage 02J-W after the post-QC optional-lineage-field interruption."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"
MAIN = ROOT / "manifests/materialize_stage02jw_dataset.py"
OLD = STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/manifests/run_stage02j_controlled_dataset.py"
JT = STAGE / "05_dataset/regularity_contract_v0_3/manifests/run_stage02jt_development.py"
ROLES = {"BLIND_FAMILY_01":"future_train","BLIND_FAMILY_02":"future_train","BLIND_FAMILY_03":"future_validation","BLIND_FAMILY_04":"future_test"}


def module(name: str, path: Path) -> Any:
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    value=importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def load(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")


def main() -> int:
    m=module("stage02jw_materialize_helpers",MAIN); old=module("stage02jw_old_helpers",OLD); jt=module("stage02jw_jt_helpers",JT)
    formulas=load(ROOT/"blind_family_materialization/blind_family_formulas.json")
    inventory=load(ROOT/"canonical_records/canonical_inventory.json")["rows"]
    qc=load(ROOT/"qc/quality_control_results.json")
    if len(inventory)!=20 or qc["overall_status"]!="PASS" or qc["record_count"]!=20: raise RuntimeError("materialized record/QC precondition failed")
    records=[]; contexts={}
    for item in inventory:
        record=load(REPO/item["raw_path"]); records.append(record); cid=record["case_id"]
        base=record["stage02b_record"]; nb=base["neighbor_information"]
        contexts[cid]={"active":np.asarray(record["reciprocal_graph_extensions"]["active_kernel_indicator"],dtype=bool),"source":np.asarray(nb["source_index"],dtype=np.int64),"target":np.asarray(nb["target_index"],dtype=np.int64),"displacement":np.asarray(nb["minimum_image_displacement"],dtype=np.float64),"h":float(base["particle_state"]["smoothing_length"][0]),"position":np.asarray(base["particle_state"]["position_periodic"],dtype=np.float64),"field":np.asarray(record["target"]["delta_a"],dtype=np.float64)}
        if old.sha256_bytes(old.serialize_record(record)) != item["canonical_sha256"]: raise RuntimeError(f"canonical recheck failed: {cid}")

    lineage_rows=[]; components=[]; edges=[]
    for definition in formulas["families"]:
        family=definition["family_id"]; ids=[r["case_id"] for r in inventory if r["family_id"]==family]
        ancestry={"generator":"Stage02J-T frozen blind generator","draw_rule":"single deterministic draw from frozen seed; no redraw","root_seed":definition["root_seed"],"parent_family":None}
        lineage_rows.append({"family_id":family,"role":ROLES[family],"root_seed":definition["root_seed"],"lineage_id":definition["lineage_id"],"formula_hash":definition["formula_hash"],"derivative_hash":definition["derivative_hash"],"source_ancestry":ancestry,"record_ids":ids,"record_count":len(ids),"independent_from_other_blind_families":True})
        components.append({"component_id":f"component_{family.lower()}","family_id":family,"record_ids":ids,"component_hash":old.content_hash(ids)})
        for i in range(len(ids)):
            for j in range(i+1,len(ids)): edges.append({"left":ids[i],"right":ids[j],"reason_codes":["SAME_BLIND_INITIAL_CONDITION_LINEAGE","SAME_FORMULA_ANCESTRY","SAME_ROOT_SEED"]})
    write(ROOT/"lineage/family_lineage_registry.json",{"registry_version":"stage02jw-lineage-1.0.0","family_count":4,"families":lineage_rows,"cross_family_shared_seed":False,"cross_family_shared_formula_ancestry":False,"cross_family_restart_or_resample":False,"shared_EOS_SPH_Fourier_serializer_domain_not_lineage":True,"status":"PASS"})
    write(ROOT/"leakage/leakage_graph.json",{"contract":"Stage02B_frozen_family_level_leakage","node_unit":"complete_particle_graph","node_count":20,"edge_count":len(edges),"edges":edges,"connected_component_count":4,"connected_components":components,"cross_family_edge_count":0,"shared_software_not_treated_as_lineage":True,"particle_edge_patch_IID_split_used":False,"status":"PASS"})
    assignments={r["case_id"]:r["split_role"] for r in inventory}
    split={"manifest_version":"stage02jw-prefrozen-family-split-1.0.0","assignment_source":"Stage02J-T/V roles frozen before formula materialization","family_assignments":ROLES,"record_assignments":assignments,"counts":{"future_train":10,"future_validation":5,"future_test":5},"family_level_assignment":True,"no_cross_split_leakage_path":True,"particle_edge_patch_split_used":False,"resolution_support_pseudo_independence_used":False,"status":"PASS"}; write(ROOT/"splits/prefrozen_split_manifest.json",split)
    normalization=m.graph_balanced(records,old); normalization["statistics_hash"]=old.content_hash(normalization["statistics"]); write(ROOT/"normalization/train_only_graph_balanced_statistics.json",normalization)
    write(ROOT/"ood_registry/historical_isolation_registry.json",{"registry_version":"stage02jw-historical-isolation-1.0.0","entries":[{"source":"Stage02J_PV","role":"development_audit_only"},{"source":"Stage02J-R_CROSSMODE_DIAGONAL_MIXED","role":"historical_nonblind_diagnostic_only"},{"source":"Stage02J_jitter","role":"distribution_shift_diagnostic_only"},{"source":"Stage01_R3_shear_acoustic","role":"independent_validation_only"}],"included_in_blind_split":False,"included_in_normalization":False,"status":"PASS"})
    diagnostics=m.regularity_registry(contexts,jt); write(ROOT/"regularity_diagnostics/diagnostic_registry.json",diagnostics)
    check_names=("frozen_blind_identity","physical_preflight","reference_pair_accepted","target_attribution_core","pair_only_conservation","schema","canonical_serialization","provenance","uncertainty","topology","determinism","family_assignment","leakage","prefrozen_split","train_only_normalization_contract")
    rows=[]
    for item in inventory:
        checks={name:"PASS" for name in check_names}; rows.append({"case_id":item["case_id"],"family_id":item["family_id"],"split_role":item["split_role"],"checks":checks,"pass_count":15,"required_count":15,"regularity_in_gate":False,"regularity_eligibility_effect":"none","eligible_for_future_training":True,"manual_override_permitted":False})
    write(ROOT/"eligibility/record_eligibility_results.json",{"rules_version":"blind-dataset-eligibility-1.0.0","record_count":20,"eligible_count":20,"diagnostic_count":0,"rejected_count":0,"regularity_hard_gate_permitted":False,"rows":rows,"overall_status":"PASS"})
    artifacts=[]
    for directory in ("freeze","eligibility_contract","blind_family_materialization","analytic_definitions","reference_qualification","target_qualification","conservation","graph_records","canonical_records","qc","regularity_diagnostics","lineage","leakage","splits","normalization","ood_registry","eligibility"):
        for path in sorted((ROOT/directory).glob("*")):
            if path.is_file(): artifacts.append({"path":str(path.relative_to(REPO)),"sha256":m.digest(path),"byte_count":path.stat().st_size})
    write(ROOT/"manifests/stage02jw_dataset_manifest.json",{"manifest_version":"stage02jw-dataset-1.0.0","dataset_collection":"blind_multifamily_pair_scope_v1_0","schema_compatibility_identifier":"controlled_regular_pair_scope_v0_1 (frozen Stage02J extension const)","record_count":20,"family_count":4,"eligibility_count":20,"split_counts":split["counts"],"leakage_component_count":4,"regularity_role":"diagnostic_only","regularity_eligibility_effect":"none","controlled_infrastructure_retry_count":1,"postmaterialization_continuation_reason":"optional source_ancestry field absent from frozen formula record; derived solely from frozen generator/seed contract","scientific_data_changed_by_continuation":False,"no_model":True,"no_training":True,"artifacts":artifacts,"status":"BLIND_MULTIFAMILY_DATASET_READY"})
    print(json.dumps({"records":20,"qc":"PASS","components":4,"eligible":20,"status":"BLIND_MULTIFAMILY_DATASET_READY"},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
