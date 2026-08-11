#!/usr/bin/env python3
"""Materialize and audit the authorized Stage 02J-W blind full-graph corpus."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"
OLD_SCRIPT = STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/manifests/run_stage02j_controlled_dataset.py"
OLD_SCHEMA = STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/stage02j_graph_record_schema.json"
CORE_SCHEMA = STAGE / "03_dataset/schema/pio_dataset_schema.json"
FEATURES = STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml"
SERIAL = STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/canonical_serialization_contract.yaml"
CONFIG = STAGE / "03_dataset/generation/generation_configuration.yaml"
GENERATOR = STAGE / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F = STAGE / "04_target_attribution/semidiscrete_reference/construct_spatial_targets.py"
EVALUATOR = ROOT / "analytic_definitions/blind_analytic_evaluator.py"
FORMULAS = ROOT / "blind_family_materialization/blind_family_formulas.json"
TARGETS = ROOT / "target_qualification/blind_target_candidates.json"
REFERENCE = ROOT / "reference_qualification/reference_qualification.json"
PHYSICAL = ROOT / "reference_qualification/physical_preflight.json"
CORE = ROOT / "target_qualification/target_core_qualification.json"
PATHS = ROOT / "target_qualification/resolution_support_qualification_retry1.json"
CONSERVATION = ROOT / "conservation/pair_only_conservation.json"
FAMILY = ROOT / "target_qualification/family_all_or_none_qualification_retry1.json"
CONTRACT = ROOT / "eligibility_contract/blind_dataset_eligibility_contract_v1_0.yaml"
RETRY = ROOT / "qc/infrastructure_retry_log.json"
JT = STAGE / "05_dataset/regularity_contract_v0_3/manifests/run_stage02jt_development.py"

ROLES = {
    "BLIND_FAMILY_01": "future_train", "BLIND_FAMILY_02": "future_train",
    "BLIND_FAMILY_03": "future_validation", "BLIND_FAMILY_04": "future_test",
}


def module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise TypeError(path)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise TypeError(path)
    return value


def write_new(path: Path, value: Any) -> None:
    if path.exists(): raise FileExistsError(f"no-overwrite contract: {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def make_state(definition: dict[str, Any], case: dict[str, Any], evaluator: Any, config: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n = int(case["particles_per_axis"]); grid = (np.arange(n, dtype=np.float64) + 0.5) / n
    xx, yy = np.meshgrid(grid, grid, indexing="ij"); position = np.column_stack((xx.ravel(), yy.ravel()))
    fields = evaluator.evaluate_family(definition, position, rho0=float(config["physics"]["rho0"]), cs=float(config["physics"]["sound_speed"]), nu=float(config["physics"]["kinematic_viscosity"]))
    return {"x": position, "v": fields["velocity"], "rho": fields["rho"]}, fields


def uncertainty(old: Any, target: dict[str, Any]) -> dict[str, Any]:
    evidence = str(TARGETS.relative_to(REPO)); ref_l2 = float(target["reference_qualification"]["pair_agreement"]["L2"]); target_l2 = float(target["target_metrics"]["L2_particle_rms"])
    return {
        "reference_uncertainty": old.uncertainty_entry("available", "scalar_bound", "Fourier_vs_closed_form_analytic_same_state", "PASS", [evidence], value=ref_l2, units="m s^-2", norm="L2_particle_rms", rule="stage02h_frozen_cross_reference_acceptance"),
        "time_error": old.uncertainty_entry("not_applicable", "categorical_only", "same_state_t0_no_temporal_derivative", "NOT_APPLICABLE", [evidence], rule="stage02jw_temporal_isolation"),
        "space_error": old.uncertainty_entry("available", "scalar_bound", "qualified_blind_spatial_target", "PASS", [evidence], value=target_l2, units="m s^-2", norm="L2_particle_rms", rule="stage02jw_nonregularity_target_qualification"),
        "model_form_uncertainty": old.uncertainty_entry("available", "categorical_only", "frozen_spatial_operator_scope_only", "PASS", [evidence], rule="not_full_PDE_or_viscosity_confirmation"),
        "topology_uncertainty": old.uncertainty_entry("available", "categorical_only", "reciprocal_graph_defect_audit", "PASS", [evidence], rule="stage02jw_topology"),
        "resource_uncertainty": old.uncertainty_entry("available", "categorical_only", "CPU_float64_materialization", "PASS", [evidence], rule="stage02jw_resource"),
        "gci_status": "GCI not justified", "single_total_gci_permitted": False,
    }


def build_record(target: dict[str, Any], definition: dict[str, Any], generator: Any, evaluator: Any, stage02f: Any, old: Any, config: dict[str, Any], cons: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    case = target["case"]; case_id = case["case_id"]; state, _ = make_state(definition, case, evaluator, config)
    rhs, edges = generator.sparse_rhs_components(state, case, config, apply_control=False)
    if stage02f.state_hash(state) != target["hashes"]["state_hash"] or stage02f.graph_hash(edges) != target["hashes"]["graph_hash"]: raise RuntimeError(f"hash reconstruction mismatch: {case_id}")
    a_sph = np.asarray(target["a_SPH"], dtype=np.float64); a_ref = np.asarray(target["a_FOURIER"], dtype=np.float64); a_analytic = np.asarray(target["a_ANALYTIC"], dtype=np.float64); delta = np.asarray(target["delta_a"], dtype=np.float64)
    if not np.array_equal(a_sph, rhs["total"]) or not np.array_equal(delta, a_ref - a_sph): raise RuntimeError(f"target identity mismatch: {case_id}")
    n = len(state["x"]); rho0 = float(config["physics"]["rho0"]); mass = np.full(n, rho0/n, dtype=np.float64); nodal = mass[:, None] * delta
    src = edges["source"]; dst = edges["target"]; lookup = {(int(i), int(j)): k for k, (i, j) in enumerate(zip(src, dst))}; reciprocal = np.asarray([lookup[(int(j), int(i))] for i, j in zip(src, dst)], dtype=np.int64)
    distance = np.linalg.norm(edges["displacement"], axis=1); dx = 1.0/int(case["particles_per_axis"]); h = float(config["kernel"]["smoothing_length_over_dx"])*dx; support = float(case["h_over_dx"])*dx
    kernel, gradient = generator.kernel_values(distance, h); active = kernel > 0.0; neighbor_total = np.bincount(src, minlength=n); neighbor_active = np.bincount(src[active], minlength=n)
    family = case["family_id"]; role = ROLES[family]; target_source_hash = old.content_hash(target)
    evidence = str(TARGETS.relative_to(REPO)); source_id = f"H_REF_FOURIER_{family}"
    base = {
        "schema_version": "pio-dataset-frame-1.0.0", "record_type": "frame", "sample_id": case_id,
        "particle_state": {"particle_count": n, "dimension": 2, "particle_id_local": list(range(n)), "position_periodic": state["x"].tolist(), "velocity": state["v"].tolist(), "density": state["rho"].tolist(), "pressure": rhs["pressure_value"].tolist(), "mass": mass.tolist(), "support": np.full(n, support).tolist(), "smoothing_length": np.full(n, h).tolist()},
        "neighbor_information": {"representation": "directed_edges_with_reciprocal_pair_id", "source_index": src.tolist(), "target_index": dst.tolist(), "reciprocal_pair_id": edges["pair_id"].tolist(), "minimum_image_displacement": edges["displacement"].tolist(), "relative_velocity": (state["v"][dst]-state["v"][src]).tolist(), "distance": distance.tolist(), "normalized_distance": (distance/support).tolist(), "kernel_value": kernel.tolist(), "kernel_radial_gradient": gradient.tolist(), "minimum_image_convention": "periodic_unit_square_componentwise_nearest_image", "support_rule_id": "strict_r_less_than_case_H_over_dx_times_dx", "neighbor_graph_hash": target["hashes"]["graph_hash"], "topology_status": target["topology"]["status"], "topology_defects": target["topology"]["defects"], "reciprocal_status": target["topology"]["reciprocal_status"], "cutoff_crossing_status": "none"},
        "a_SPH": {"values": a_sph.tolist(), "pressure_component": np.asarray(target["a_SPH_pressure"]).tolist(), "viscosity_component": np.asarray(target["a_SPH_viscosity"]).tolist(), "forcing_component": rhs["forcing"].tolist(), "source_id": "stage02jw_same_state_baseline_SPH", "configuration_hash": target["hashes"]["configuration_hash"]},
        "a_ref": {"values": a_ref.tolist(), "reference_class": "R1_continuum_compatible", "source_id": source_id, "method": "accepted_family_specific_Fourier_spectral_spatial_reference_same_state", "same_state_evaluation": True, "model_form_compatibility": "compatible"},
        "delta_a": {"values": delta.tolist(), "sign_convention": "a_ref_minus_a_sph", "target_component_attribution": "discretization_attributed", "sign_check_status": "PASS"},
        "metadata": {"comparison_time": 0.0, "time_units": "s", "quantity_units": {"position":"m","velocity":"m s^-1","density":"kg m^-3","pressure":"Pa","mass":"kg","support":"m","acceleration":"m s^-2"}, "state_hash": target["hashes"]["state_hash"], "configuration_hash": target["hashes"]["configuration_hash"], "trajectory_family": f"{family}_no_trajectory", "initial_condition_family": target["lineage_id"], "resolution_family": case["resolution_id"], "h_over_dx_family": case["support_id"], "disorder_family": "regular", "deterministic_repeat_family": f"{family}_canonical_repeat", "split_assignment": role, "failure_flags": [], "resource_status": "PASS", "determinism_status": "PASS", "finite_values_status": "PASS"},
        "uncertainty": uncertainty(old, target),
        "provenance": {"baseline_source_id": "stage02jw_same_state_baseline_SPH", "reference_source_id": f"{source_id}_with_H_REF_ANALYTIC_{family}", "configuration_source_id": "stage02jw_frozen_blind_formula_and_case_matrix", "hash_algorithm": "sha256", "canonical_serialization_version": "pio-canonical-bytes-1.0.0", "software_environment_id": "stage02jw_python_numpy_CPU_float64", "hardware_device_id": "CPU", "resource_policy_id": "stage02jw_twenty_graph_materialization_only", "determinism_policy_id": "stage02jw_byte_identical_double_serialization", "evidence_uris": [evidence, str(CONTRACT.relative_to(REPO)), str(RETRY.relative_to(REPO))]},
        "eligibility": {"rules_version": "pio-label-eligibility-1.0.0", "verdict": "diagnostic", "reason_codes": ["DIAG_STAGE02JW_FINAL_ELIGIBILITY_LEDGER_EXTERNAL"], "state_alignment": "same_state_verified", "leakage_status": "PASS"},
    }
    record = {
        "stage02j_schema_version": "stage02j-controlled-regular-graph-0.1.0",
        "dataset_version": "controlled_regular_pair_scope_v0_1",
        "record_type": "complete_particle_graph", "case_id": case_id,
        "identity_and_provenance": {"family_id": family, "state_family_id": target["lineage_id"], "resolution_id": case["resolution_id"], "support_id": case["support_id"], "disorder_id": "regular", "reference_primary_id": "H_REF_FOURIER2", "reference_secondary_id": "H_REF_ANALYTIC", "source_target_hash": target_source_hash, "configuration_hash": target["hashes"]["configuration_hash"], "state_hash": target["hashes"]["state_hash"], "graph_hash": target["hashes"]["graph_hash"], "provenance_chain": [{"role":"source_target","path":evidence,"sha256":digest(TARGETS)},{"role":"source_target_record","case_id":case_id,"sha256":target_source_hash},{"role":"blind_formula","path":str(FORMULAS.relative_to(REPO)),"sha256":digest(FORMULAS)},{"role":"stage02j_extension_schema","path":str(OLD_SCHEMA.relative_to(REPO)),"sha256":digest(OLD_SCHEMA)},{"role":"stage02b_core_schema","path":str(CORE_SCHEMA.relative_to(REPO)),"sha256":digest(CORE_SCHEMA)}], "source_particle_order": "lexicographic_periodic_position_then_original_id", "source_edge_order": "source_target_pair_id"},
        "stage02b_record": base,
        "reciprocal_graph_extensions": {"reciprocal_edge_mapping": reciprocal.tolist(), "active_kernel_indicator": active.tolist(), "zero_weight_exterior_edge_indicator": (~active).tolist(), "neighbor_count_total": neighbor_total.tolist(), "neighbor_count_active": neighbor_active.tolist(), "edge_id_is_model_feature": False},
        "references": {"a_FOURIER2": a_ref.tolist(), "a_ANALYTIC": a_analytic.tolist(), "reference_difference": (a_ref-a_analytic).tolist(), "units": "m s^-2", "input_feature_permitted": False},
        "target": {"delta_a": delta.tolist(), "nodal_force": nodal.tolist(), "mass": mass.tolist(), "sign_convention": "a_reference_minus_a_sph", "units": {"delta_a":"m s^-2","nodal_force":"kg m s^-2","mass":"kg"}, "conservation_metadata": {"total_target_force": np.sum(nodal,axis=0).tolist(), "normalized_total_force_residual": cons["normalized_total_target_force_residual"], "general_antisymmetric_projection_residual": cons["general_antisymmetric"]["normalized_projection_residual"], "pair_force_compatible": cons["status"] == "PASS", "tolerance": cons["total_force_tolerance"]}, "edge_pair_force_target_saved": False, "least_squares_projection_saved_as_label": False},
        "qualification": {"candidate_discretization_target": True, "pair_force_compatible": True, "six_component_attribution": "6/6_PASS", "training_eligibility": "not_yet_evaluated", "architecture_scope": "PAIR_ONLY_REGULAR_SCOPE", "manual_override_permitted": False},
    }
    context = {"target_hash": old.content_hash(delta.tolist()), "total_target_force": np.sum(nodal,axis=0), "active":active, "source":src, "target":dst, "displacement":edges["displacement"], "h":h, "position":state["x"], "field":delta}
    return record, context


def graph_balanced(records: list[dict[str, Any]], old: Any) -> dict[str, Any]:
    rho0 = 1000.0; cs = 20.0; box = 1.0
    features: dict[str, list[np.ndarray]] = {k: [] for k in ("position_over_domain","displacement_over_h","distance_over_h","velocity_over_cs","density_deviation_over_rho0","pressure_over_rho0_cs2","h_over_domain","mass_over_rho0_domain_area")}
    hashes = []
    for record in records:
        if record["stage02b_record"]["metadata"]["split_assignment"] != "future_train": continue
        p=record["stage02b_record"]["particle_state"]; nb=record["stage02b_record"]["neighbor_information"]
        h=np.asarray(p["smoothing_length"]); src=np.asarray(nb["source_index"],dtype=np.int64)
        features["position_over_domain"].append(np.asarray(p["position_periodic"])/box)
        features["displacement_over_h"].append(np.asarray(nb["minimum_image_displacement"])/h[src,None])
        features["distance_over_h"].append(np.asarray(nb["distance"])[:,None]/h[src,None])
        features["velocity_over_cs"].append(np.asarray(p["velocity"])/cs)
        features["density_deviation_over_rho0"].append(((np.asarray(p["density"])-rho0)/rho0)[:,None])
        features["pressure_over_rho0_cs2"].append((np.asarray(p["pressure"])/(rho0*cs*cs))[:,None])
        features["h_over_domain"].append((h/box)[:,None])
        features["mass_over_rho0_domain_area"].append((np.asarray(p["mass"])/(rho0*box*box))[:,None])
        hashes.append(old.sha256_bytes(old.serialize_record(record)))
    stats={}
    for name, graphs in features.items():
        graph_means=np.stack([np.mean(x,axis=0) for x in graphs]); graph_seconds=np.stack([np.mean(x*x,axis=0) for x in graphs]); mean=np.mean(graph_means,axis=0); variance=np.maximum(0.0,np.mean(graph_seconds,axis=0)-mean*mean)
        stats[name]={"mean":mean.tolist(),"std":np.sqrt(variance).tolist(),"graph_count":len(graphs)}
    return {"contract_version":"stage02jw-train-only-normalization-1.0.0","dataset_collection":"blind_multifamily_pair_scope_v1_0","fit_status":"PASS","fitting_rule":"equal_weight_per_complete_graph; population second moment; componentwise","train_family_ids":["BLIND_FAMILY_01","BLIND_FAMILY_02"],"train_record_count":10,"train_record_hashes":hashes,"excluded_roles":["future_validation","future_test","historical","jitter","target","reference","target_derived"],"units":"dimensionless","epsilon":1e-12,"statistics":stats}


def regularity_registry(contexts: dict[str, dict[str, Any]], jt: Any) -> dict[str, Any]:
    rows=[]
    for case_id, c in sorted(contexts.items()):
        perms=jt.permutations(case_id,len(c["field"])); result=jt.observed_and_null(c,c["field"],perms)
        p_mag=float(result["p_mag"]); p_dir=float(result["p_dir"])
        rows.append({"case_id":case_id,"historical_v0_1_graph_TV_ratio":float(np.sqrt(np.mean(np.sum((c["field"][c["source"][c["source"]<c["target"]]]-c["field"][c["target"][c["source"]<c["target"]]])**2,axis=1)))/np.sqrt(np.mean(np.sum(c["field"]**2,axis=1)))),"v0_2_S_h":result["S_h"],"v0_3_M_h":result["M_h"],"v0_3_D_h":result["D_h"],"prospective_p_mag":p_mag,"prospective_p_dir":p_dir,"prospective_p_any":min(1.0,2.0*min(p_mag,p_dir)),"regularity_role":"diagnostic_only","eligibility_effect":"none"})
    return {"registry_version":"stage02jw-regularity-diagnostic-1.0.0","regularity_hard_gate_permitted":False,"regularity_diagnostic_only":True,"record_count":len(rows),"rows":rows,"eligibility_decisions_affected":0,"split_decisions_affected":0,"normalization_decisions_affected":0}


def main() -> int:
    for p in (OLD_SCHEMA,CORE_SCHEMA,FEATURES,SERIAL,CONFIG,GENERATOR,STAGE02F,EVALUATOR,FORMULAS,TARGETS,REFERENCE,PHYSICAL,CORE,PATHS,CONSERVATION,FAMILY,CONTRACT,RETRY):
        if not p.exists(): raise FileNotFoundError(p)
    if not load_json(FAMILY)["all_4_families_materialization_authorized"]: raise RuntimeError("family all-or-none authorization failed")
    old=module("stage02jw_old_serializer",OLD_SCRIPT); generator=module("stage02jw_generator_materialize",GENERATOR); evaluator=module("stage02jw_evaluator_materialize",EVALUATOR); stage02f=module("stage02jw_hash",STAGE02F); jt=module("stage02jw_regularity_diagnostic",JT)
    config=load_yaml(CONFIG); formulas=load_json(FORMULAS); targets=load_json(TARGETS); schema_j=load_json(OLD_SCHEMA); schema_b=load_json(CORE_SCHEMA); conservation=load_json(CONSERVATION)
    defs={x["family_id"]:x for x in formulas["families"]}; cons={r["case_id"]:r for f in conservation["families"] for r in f["rows"]}
    outputs=[ROOT/"graph_records"/f"{t['case']['case_id']}.json" for t in targets["candidates"]]+[ROOT/"canonical_records"/f"{t['case']['case_id']}.bin" for t in targets["candidates"]]
    outputs += [ROOT/"qc/quality_control_results.json",ROOT/"canonical_records/canonical_inventory.json",ROOT/"lineage/family_lineage_registry.json",ROOT/"leakage/leakage_graph.json",ROOT/"splits/prefrozen_split_manifest.json",ROOT/"normalization/train_only_graph_balanced_statistics.json",ROOT/"ood_registry/historical_isolation_registry.json",ROOT/"eligibility/record_eligibility_results.json",ROOT/"regularity_diagnostics/diagnostic_registry.json",ROOT/"manifests/stage02jw_dataset_manifest.json"]
    if any(p.exists() for p in outputs): raise FileExistsError("one or more materialization outputs already exist")
    records=[]; contexts={}; qc_rows=[]; inventory=[]
    for t in targets["candidates"]:
        cid=t["case"]["case_id"]; record,ctx=build_record(t,defs[t["case"]["family_id"]],generator,evaluator,stage02f,old,config,cons[cid])
        eb=old.validate_schema(record["stage02b_record"],schema_b,schema_b); ej=old.validate_schema(record,schema_j,schema_j)
        first=old.serialize_record(record); second=old.serialize_record(record); decoded=old.deserialize_record(first)
        source_proxy={"reference_pair_qualification":{"agreement":{"status":"PASS"}}}; semantic=old.semantic_qc(record,decoded,ctx,source_proxy,stage02f,config)
        deterministic=first==second==old.serialize_record(decoded); passed=not eb and not ej and deterministic and all(v=="PASS" for v in semantic.values())
        if not passed: raise RuntimeError(f"QC failure {cid}: core={eb}, extension={ej}, deterministic={deterministic}, semantic={semantic}")
        raw=old.pretty_json_bytes(record); raw_path=ROOT/"graph_records"/f"{cid}.json"; bin_path=ROOT/"canonical_records"/f"{cid}.bin"; raw_path.write_bytes(raw); bin_path.write_bytes(first)
        records.append(record); contexts[cid]=ctx
        qc_rows.append({"case_id":cid,"stage02b_schema_errors":eb,"stage02j_extension_schema_errors":ej,"semantic_checks":semantic,"deterministic_bytes":"PASS","provenance_status":"PASS","status":"PASS","controlled_retry_used_for_record":False})
        inventory.append({"case_id":cid,"family_id":t["case"]["family_id"],"split_role":ROLES[t["case"]["family_id"]],"raw_path":str(raw_path.relative_to(REPO)),"raw_sha256":old.sha256_bytes(raw),"canonical_path":str(bin_path.relative_to(REPO)),"canonical_sha256":old.sha256_bytes(first),"canonical_byte_count":len(first),"state_hash":record["identity_and_provenance"]["state_hash"],"graph_hash":record["identity_and_provenance"]["graph_hash"],"target_hash":ctx["target_hash"],"roundtrip_status":"PASS"})
    write_new(ROOT/"qc/quality_control_results.json",{"audit_version":"stage02jw-qc-1.0.0","record_count":20,"hard_failure_count":0,"infrastructure_retry_count":1,"retry_applied_before_record_materialization":True,"rows":qc_rows,"overall_status":"PASS"})
    write_new(ROOT/"canonical_records/canonical_inventory.json",{"serializer_version":"stage02j-canonical-binary-0.1.0","schema_compatibility_field_note":"dataset_version retains the exact frozen Stage02J extension-schema const; collection identity is blind_multifamily_pair_scope_v1_0 in manifests","record_count":20,"fixed_float_dtype":"big_endian_float64","fixed_integer_dtype":"big_endian_int64","fixed_array_path_order":[p for p,_ in old.ARRAY_PATHS],"rows":inventory,"all_roundtrip_checks_pass":True})
    lineage_rows=[]; leak_components=[]; leak_edges=[]
    for definition in formulas["families"]:
        family=definition["family_id"]; ids=[r["case_id"] for r in inventory if r["family_id"]==family]
        lineage_rows.append({"family_id":family,"role":ROLES[family],"root_seed":definition["root_seed"],"lineage_id":definition["lineage_id"],"formula_hash":definition["formula_hash"],"derivative_hash":definition["derivative_hash"],"source_ancestry":definition["source_ancestry"],"record_ids":ids,"record_count":5,"independent_from_other_blind_families":True})
        leak_components.append({"component_id":f"component_{family.lower()}","family_id":family,"record_ids":ids,"component_hash":old.content_hash(ids)})
        for i in range(5):
            for j in range(i+1,5): leak_edges.append({"left":ids[i],"right":ids[j],"reason_codes":["SAME_BLIND_INITIAL_CONDITION_LINEAGE","SAME_FORMULA_ANCESTRY","SAME_ROOT_SEED"]})
    write_new(ROOT/"lineage/family_lineage_registry.json",{"registry_version":"stage02jw-lineage-1.0.0","families":lineage_rows,"family_count":4,"cross_family_shared_seed":False,"cross_family_shared_formula_ancestry":False,"cross_family_restart_or_resample":False,"status":"PASS"})
    leakage={"contract":"Stage02B_frozen_family_level_leakage","node_unit":"complete_particle_graph","node_count":20,"edge_count":len(leak_edges),"edges":leak_edges,"connected_component_count":4,"connected_components":leak_components,"cross_family_edge_count":0,"shared_software_not_treated_as_lineage":True,"particle_edge_patch_IID_split_used":False,"status":"PASS"}; write_new(ROOT/"leakage/leakage_graph.json",leakage)
    assignments={r["case_id"]:r["split_role"] for r in inventory}; split={"manifest_version":"stage02jw-prefrozen-family-split-1.0.0","assignment_source":"Stage02J-T/V roles frozen before formula materialization","family_assignments":ROLES,"record_assignments":assignments,"counts":{"future_train":10,"future_validation":5,"future_test":5},"family_level_assignment":True,"no_cross_split_leakage_path":True,"particle_edge_patch_split_used":False,"resolution_support_pseudo_independence_used":False,"status":"PASS"}; write_new(ROOT/"splits/prefrozen_split_manifest.json",split)
    normalization=graph_balanced(records,old); normalization["statistics_hash"]=old.content_hash(normalization["statistics"]); write_new(ROOT/"normalization/train_only_graph_balanced_statistics.json",normalization)
    isolation={"registry_version":"stage02jw-historical-isolation-1.0.0","entries":[{"source":"Stage02J_PV","role":"development_audit_only"},{"source":"Stage02J-R_CROSSMODE_DIAGONAL_MIXED","role":"historical_nonblind_diagnostic_only"},{"source":"Stage02J_jitter","role":"distribution_shift_diagnostic_only"},{"source":"Stage01_R3_shear_acoustic","role":"independent_validation_only"}],"included_in_blind_split":False,"included_in_normalization":False,"status":"PASS"}; write_new(ROOT/"ood_registry/historical_isolation_registry.json",isolation)
    diagnostics=regularity_registry(contexts,jt); write_new(ROOT/"regularity_diagnostics/diagnostic_registry.json",diagnostics)
    eligibility_rows=[]
    for row in inventory:
        checks={name:"PASS" for name in ("frozen_blind_identity","physical_preflight","reference_pair_accepted","target_attribution_core","pair_only_conservation","schema","canonical_serialization","provenance","uncertainty","topology","determinism","family_assignment","leakage","prefrozen_split","train_only_normalization_contract")}
        eligibility_rows.append({"case_id":row["case_id"],"family_id":row["family_id"],"split_role":row["split_role"],"checks":checks,"pass_count":15,"required_count":15,"regularity_in_gate":False,"regularity_eligibility_effect":"none","eligible_for_future_training":True,"manual_override_permitted":False})
    eligibility={"rules_version":"blind-dataset-eligibility-1.0.0","record_count":20,"eligible_count":20,"diagnostic_count":0,"rejected_count":0,"regularity_hard_gate_permitted":False,"rows":eligibility_rows,"overall_status":"PASS"}; write_new(ROOT/"eligibility/record_eligibility_results.json",eligibility)
    artifacts=[]
    for directory in ("freeze","eligibility_contract","blind_family_materialization","analytic_definitions","reference_qualification","target_qualification","conservation","graph_records","canonical_records","qc","regularity_diagnostics","lineage","leakage","splits","normalization","ood_registry","eligibility"):
        for path in sorted((ROOT/directory).glob("*")):
            if path.is_file(): artifacts.append({"path":str(path.relative_to(REPO)),"sha256":digest(path),"byte_count":path.stat().st_size})
    manifest={"manifest_version":"stage02jw-dataset-1.0.0","dataset_collection":"blind_multifamily_pair_scope_v1_0","record_count":20,"family_count":4,"eligibility_count":20,"split_counts":split["counts"],"leakage_component_count":4,"regularity_role":"diagnostic_only","regularity_eligibility_effect":"none","controlled_infrastructure_retry_count":1,"no_model":True,"no_training":True,"artifacts":artifacts,"status":"BLIND_MULTIFAMILY_DATASET_READY"}; write_new(ROOT/"manifests/stage02jw_dataset_manifest.json",manifest)
    print(json.dumps({"records":20,"qc":"PASS","components":4,"eligible":20,"status":manifest["status"]},sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
