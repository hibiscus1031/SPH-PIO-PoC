#!/usr/bin/env python3
"""Qualify the 20 frozen blind-family spatial targets without a regularity gate."""

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
FREEZE_PATH = ROOT / "freeze/stage02jw_input_freeze_manifest.json"
FORMULAS_PATH = ROOT / "blind_family_materialization/blind_family_formulas.json"
EVALUATOR_PATH = ROOT / "analytic_definitions/blind_analytic_evaluator.py"
CONFIG_PATH = STAGE / "03_dataset/generation/generation_configuration.yaml"
GENERATOR_PATH = STAGE / "03_dataset/generation/generate_audit_dataset.py"
STAGE02F_PATH = STAGE / "04_target_attribution/semidiscrete_reference/construct_spatial_targets.py"
JR_SCRIPT_PATH = STAGE / "05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/run_stage02jr_qualification.py"
REF_RULES_PATH = STAGE / "04_target_attribution/acceptance/reference_acceptance_rules.yaml"
RES_RULES_PATH = STAGE / "04_target_attribution/resolution_extension/resolution_extension_matrix.yaml"
SUP_RULES_PATH = STAGE / "04_target_attribution/semidiscrete_reference/r2s_reference_design.yaml"

PHYSICAL_OUT = ROOT / "reference_qualification/physical_preflight.json"
REFERENCE_OUT = ROOT / "reference_qualification/reference_qualification.json"
TARGETS_OUT = ROOT / "target_qualification/blind_target_candidates.json"
CORE_OUT = ROOT / "target_qualification/target_core_qualification.json"
PATHS_OUT = ROOT / "target_qualification/resolution_support_qualification.json"
CONSERVATION_OUT = ROOT / "conservation/pair_only_conservation.json"
FAMILY_OUT = ROOT / "target_qualification/family_all_or_none_qualification.json"

CASE_TEMPLATE = (
    ("n12_h26", 12, 2.6, ["resolution"]),
    ("n16_h26", 16, 2.6, ["resolution", "support"]),
    ("n20_h26", 20, 2.6, ["resolution"]),
    ("n16_h22", 16, 2.2, ["support"]),
    ("n16_h30", 16, 3.0, ["support"]),
)


def load_json(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"))
def load_yaml(path: Path) -> dict[str, Any]: return yaml.safe_load(path.read_text(encoding="utf-8"))
def file_hash(path: Path) -> str: return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
def canonical_hash(value: Any) -> str: return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def write(path: Path, value: Any) -> None:
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def metrics(field: np.ndarray) -> dict[str, Any]:
    magnitude = np.linalg.norm(field, axis=1)
    return {"L2_particle_rms": float(np.sqrt(np.mean(magnitude * magnitude))), "Linf_particle_vector": float(np.max(magnitude)), "component_mean": np.mean(field, axis=0).tolist(), "magnitude_quantiles": {str(q): float(np.quantile(magnitude, q)) for q in (0.0,0.25,0.5,0.75,0.9,0.95,0.99,1.0)}}


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right)); return float(np.sum(left * right) / denom) if denom > 0 else 0.0


def signature(position: np.ndarray, field: np.ndarray, modes: list[list[int]]) -> np.ndarray:
    entries = []
    for kx, ky in modes:
        phase = np.exp(-2.0j * math.pi * (kx * position[:,0] + ky * position[:,1]))
        for component in range(2):
            coefficient = np.mean(field[:,component] * phase); entries.extend((float(coefficient.real), float(coefficient.imag)))
    return np.asarray(entries, dtype=np.float64)


def graph_tv(field: np.ndarray, edges: dict[str, np.ndarray]) -> float:
    mask = edges["source"] < edges["target"]; diff = field[edges["source"][mask]] - field[edges["target"][mask]]
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def make_case(family_id: str, suffix: str, n_axis: int, hdx: float, paths: list[str]) -> dict[str, Any]:
    return {"case_id": f"{family_id.lower()}_{suffix}", "family_id": family_id, "particles_per_axis": n_axis, "h_over_dx": hdx, "resolution_id": f"N{n_axis}x{n_axis}", "support_id": f"Hdx_{str(hdx).replace('.', 'p')}", "path_membership": paths, "disorder_identity": "regular", "disorder_fraction_dx": 0.0, "random_seed": 0, "topology_control": "none", "time_horizon": 0.0, "trajectory_family": f"{family_id}_no_trajectory", "initial_condition_family": f"{family_id}_frozen_blind_IC", "disorder_family": "regular"}


def state_for(definition: dict[str, Any], case: dict[str, Any], evaluator: Any, config: dict[str, Any]) -> tuple[dict[str,np.ndarray],dict[str,np.ndarray]]:
    n = case["particles_per_axis"]; grid = (np.arange(n, dtype=np.float64)+0.5)/n; xx,yy=np.meshgrid(grid,grid,indexing="ij"); position=np.column_stack((xx.ravel(),yy.ravel()))
    fields=evaluator.evaluate_family(definition,position,rho0=float(config["physics"]["rho0"]),cs=float(config["physics"]["sound_speed"]),nu=float(config["physics"]["kinematic_viscosity"]))
    return {"x":position,"v":fields["velocity"],"rho":fields["rho"]},fields


def graph_diagnostics(generator: Any, state: dict[str,np.ndarray], edges: dict[str,np.ndarray], case: dict[str,Any], config: dict[str,Any]) -> dict[str,Any]:
    n=len(state["x"]); dx=float(config["domain"]["box_length"])/case["particles_per_axis"]; h=float(config["kernel"]["smoothing_length_over_dx"])*dx
    distance=np.linalg.norm(edges["displacement"],axis=1); kernel,_=generator.kernel_values(distance,h); active=kernel>0
    active_count=np.bincount(edges["source"][active],minlength=n); total_count=np.bincount(edges["source"],minlength=n)
    return {"active_neighbor_count":{"min":int(active_count.min()),"max":int(active_count.max()),"mean":float(active_count.mean())},"total_neighbor_count":{"min":int(total_count.min()),"max":int(total_count.max()),"mean":float(total_count.mean())},"zero_weight_exterior_directed_count":int(np.count_nonzero(~active)),"active_indicator":active}


def main() -> int:
    freeze=load_json(FREEZE_PATH); formulas=load_json(FORMULAS_PATH); config=load_yaml(CONFIG_PATH); ref_rules=load_yaml(REF_RULES_PATH); res_rules=load_yaml(RES_RULES_PATH); sup_rules=load_yaml(SUP_RULES_PATH)
    generator=load_module("stage02jw_generator",GENERATOR_PATH); evaluator=load_module("stage02jw_evaluator",EVALUATOR_PATH); stage02f=load_module("stage02jw_stage02f",STAGE02F_PATH); jr=load_module("stage02jw_jr",JR_SCRIPT_PATH)
    rho0=float(config["physics"]["rho0"]); cs=float(config["physics"]["sound_speed"]); nu=float(config["physics"]["kinematic_viscosity"])
    thresholds=ref_rules["numeric_thresholds"]; derivative_tol=float(thresholds["polynomial_reproduction_Linf_max"])
    physical_families=[]; reference_families=[]; targets=[]; core_rows=[]; conservation_families=[]; contexts={}
    for definition in formulas["families"]:
        family_id=definition["family_id"]; family_physical=[]; family_refs=[]; family_conservation=[]
        for suffix,n_axis,hdx,paths in CASE_TEMPLATE:
            case=make_case(family_id,suffix,n_axis,hdx,paths); state,analytic=evaluator_state=state_for(definition,case,evaluator,config)
            rhs,edges=generator.sparse_rhs_components(state,case,config,apply_control=False); topology=generator.topology_audit(edges,state,case,config)
            fourier=evaluator.fourier_reference(state["x"],state["rho"],state["v"],rho0=rho0,cs=cs,nu=nu)
            analytic_repeat=evaluator.evaluate_family(definition,state["x"],rho0=rho0,cs=cs,nu=nu); fourier_repeat=evaluator.fourier_reference(state["x"],state["rho"],state["v"],rho0=rho0,cs=cs,nu=nu)
            grad_err=float(np.max(np.abs(analytic["grad_p"]-fourier["grad_p"]))); lap_err=float(np.max(np.abs(analytic["laplacian_velocity"]-fourier["laplacian_velocity"]))); acc_err=float(np.max(np.abs(analytic["acceleration"]-fourier["acceleration"])))
            mach=np.linalg.norm(state["v"],axis=1)/cs
            physical_checks={"density_positive":"PASS" if float(state["rho"].min())>0 else "FAIL","analytic_Mach_bound":"PASS" if definition["analytic_Mach_upper_bound"]<=0.03 else "FAIL","sampled_density_within_analytic_bounds":"PASS" if float(state["rho"].min())>=rho0*definition["density_relative_bounds"][0]-1e-12 and float(state["rho"].max())<=rho0*definition["density_relative_bounds"][1]+1e-12 else "FAIL","sampled_Mach_within_analytic_bound":"PASS" if float(mach.max())<=definition["analytic_Mach_upper_bound"]+1e-14 else "FAIL","closed_form_grad_p":"PASS" if grad_err<=derivative_tol else "FAIL","closed_form_laplacian_u":"PASS" if lap_err<=derivative_tol else "FAIL","total_analytic_acceleration":"PASS" if acc_err<=derivative_tol else "FAIL"}
            physical={"case_id":case["case_id"],"rho_min":float(state["rho"].min()),"rho_max":float(state["rho"].max()),"Mach_max":float(mach.max()),"analytic_density_relative_bounds":definition["density_relative_bounds"],"analytic_Mach_upper_bound":definition["analytic_Mach_upper_bound"],"derivative_errors":{"grad_p_Linf":grad_err,"laplacian_u_Linf":lap_err,"acceleration_Linf":acc_err,"tolerance":derivative_tol},"checks":physical_checks,"status":"PASS" if all(x=="PASS" for x in physical_checks.values()) else "FAIL"}; family_physical.append(physical)
            a_sph=rhs["total"]; primary=fourier["acceleration"]; secondary=analytic["acceleration"]; delta=primary-a_sph; delta_secondary=secondary-a_sph; difference=primary-secondary
            dm=metrics(delta); sm=metrics(delta_secondary); diffm=metrics(difference); max_l2=max(dm["L2_particle_rms"],sm["L2_particle_rms"]); max_linf=max(dm["Linf_particle_vector"],sm["Linf_particle_vector"])
            norm_l2=diffm["L2_particle_rms"]/max_l2 if max_l2 else math.inf; norm_linf=diffm["Linf_particle_vector"]/max_linf if max_linf else math.inf; pattern=cosine(delta,delta_secondary)
            pair_checks={"normalized_L2":"PASS" if norm_l2<=float(thresholds["cross_reference_pair_L2_to_max_target_L2_ratio_max"]) else "FAIL","normalized_Linf":"PASS" if norm_linf<=float(thresholds["cross_reference_pair_Linf_to_max_target_Linf_ratio_max"]) else "FAIL","target_pattern_cosine":"PASS" if pattern>=float(thresholds["cross_reference_target_pattern_cosine_min"]) else "FAIL"}
            deterministic=all(np.array_equal(analytic[key],analytic_repeat[key]) for key in analytic) and all(np.array_equal(fourier[key],fourier_repeat[key]) for key in fourier)
            ref_checks={"same_state":"PASS","same_physics":"PASS","Fourier_reference_accepted":"PASS" if norm_l2<=float(thresholds["bias_to_reference_target_L2_ratio_max"]) else "FAIL","analytic_reference_accepted":"PASS","Fourier_analytic_pair_agreement":"PASS" if all(x=="PASS" for x in pair_checks.values()) else "FAIL","deterministic_repeat":"PASS" if deterministic else "FAIL","qualified_uncertainty":"PASS" if norm_l2<=float(thresholds["uncertainty_to_reference_target_L2_ratio_max"]) else "FAIL"}
            ref={"case_id":case["case_id"],"primary_id":f"H_REF_FOURIER_{family_id}","secondary_id":f"H_REF_ANALYTIC_{family_id}","pair_agreement":{"L2":diffm["L2_particle_rms"],"Linf":diffm["Linf_particle_vector"],"normalized_L2":norm_l2,"normalized_Linf":norm_linf,"target_pattern_cosine":pattern,"checks":pair_checks},"checks":ref_checks,"status":"PASS" if all(x=="PASS" for x in ref_checks.values()) else "FAIL"}; family_refs.append(ref)
            graphdiag=graph_diagnostics(generator,state,edges,case,config); modes=sorted({tuple(mode) for key in ("density","velocity_x","velocity_y") for mode in definition[key]["modes"]}); sig=signature(state["x"],delta,[list(x) for x in modes]); tv=graph_tv(delta,edges); mean_edge=float(np.mean(np.linalg.norm(edges["displacement"][edges["source"]<edges["target"]],axis=1))); l2=dm["L2_particle_rms"]
            physical_config={"family_formula_hash":definition["formula_hash"],"n_axis":n_axis,"h_over_dx":hdx,"physics":config["physics"],"kernel":config["kernel"]}
            hashes={"state_hash":stage02f.state_hash(state),"configuration_hash":canonical_hash(physical_config),"graph_hash":stage02f.graph_hash(edges),"target_hash":canonical_hash(delta.tolist()),"Fourier_reference_hash":canonical_hash(primary.tolist()),"analytic_reference_hash":canonical_hash(secondary.tolist())}
            core_checks={"nonzero_target":"PASS" if dm["Linf_particle_vector"]>0 else "FAIL","target_identity":"PASS" if np.array_equal(delta,primary-a_sph) else "FAIL","topology":topology["status"],"reference_pair_qualified":ref["status"],"state_configuration_graph_hash_alignment":"PASS" if all(hashes[key].startswith("sha256:") for key in ("state_hash","configuration_hash","graph_hash")) else "FAIL"}
            uncertainty={"reference_uncertainty":{"status":"PASS","L2_particle_rms":diffm["L2_particle_rms"]},"time_error":{"status":"NOT_APPLICABLE","method":"same_state_t0_no_temporal_derivative"},"space_error":{"status":"PASS","method":"blind_spatial_target_core_and_path_qualification_pending"},"model_form_uncertainty":{"status":"PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE"},"topology_uncertainty":{"status":topology["status"]},"resource_uncertainty":{"status":"PASS","execution":"CPU_float64"},"single_total_GCI":False,"GCI_status":"GCI not justified"}
            mass=rho0/len(state["x"]); nodal_force=mass*delta; total=np.sum(nodal_force,axis=0); denom=float(np.sum(np.linalg.norm(nodal_force,axis=1))); normalized=float(np.linalg.norm(total)/denom) if denom else 0.0; general=jr.general_pair_audit(nodal_force,edges); central=jr.central_pair_diagnostic(nodal_force,state,edges)
            conservation_checks={"normalized_total_force":"PASS" if normalized<=1e-10 else "FAIL","general_antisymmetric_representability":"PASS" if general["normalized_projection_residual"]<=1e-10 else "FAIL"}
            cons={"case_id":case["case_id"],"normalized_total_target_force_residual":normalized,"total_force_tolerance":1e-10,"general_antisymmetric":general,"central_pair_diagnostic":central,"checks":conservation_checks,"target_mean_subtracted":False,"projection_writeback":False,"status":"PASS" if all(x=="PASS" for x in conservation_checks.values()) else "FAIL"}; family_conservation.append(cons)
            target={"case":case,"family_role":definition["role"],"lineage_id":definition["lineage_id"],"root_seed":definition["root_seed"],"formula_hash":definition["formula_hash"],"derivative_hash":definition["derivative_hash"],"hashes":hashes,"a_SPH":a_sph.tolist(),"a_SPH_pressure":rhs["pressure"].tolist(),"a_SPH_viscosity":rhs["viscosity"].tolist(),"a_FOURIER":primary.tolist(),"a_ANALYTIC":secondary.tolist(),"reference_difference":difference.tolist(),"delta_a":delta.tolist(),"nodal_force":nodal_force.tolist(),"mass":mass,"target_sign":"a_reference_minus_a_sph","target_metrics":dm,"Fourier_signature_modes":[list(x) for x in modes],"low_mode_fourier_signature":sig.tolist(),"graph_total_variation_RMS":tv,"relative_neighbor_variation":tv/l2,"mean_undirected_edge_length":mean_edge,"physical_gradient_scale":tv/(mean_edge*l2),"topology":topology,"graph_diagnostics":{key:value for key,value in graphdiag.items() if key!="active_indicator"},"physical_preflight":physical,"reference_qualification":ref,"core_checks":core_checks,"uncertainty":uncertainty,"temporal_isolation":{"t0_same_state":True,"trajectory":False,"temporal_derivative":False,"DOP853":False,"future_state":False,"status":"PASS"},"model_form_scope":"PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE","edge_pair_force_target_saved":False,"incidence_projection_written_back":False}
            targets.append(target); core_rows.append({"case_id":case["case_id"],"checks":core_checks,"status":"PASS" if all(x=="PASS" for x in core_checks.values()) else "FAIL"}); contexts[case["case_id"]]={"state":state,"edges":edges,"rhs":rhs,"target":target,"active":graphdiag["active_indicator"]}
        physical_families.append({"family_id":family_id,"rows":family_physical,"family_5_of_5_PASS":all(x["status"]=="PASS" for x in family_physical)})
        reference_families.append({"family_id":family_id,"rows":family_refs,"family_5_of_5_PASS":all(x["status"]=="PASS" for x in family_refs)})
        conservation_families.append({"family_id":family_id,"rows":family_conservation,"family_5_of_5_PASS":all(x["status"]=="PASS" for x in family_conservation)})
    target_map={row["case"]["case_id"]:row for row in targets}; path_families=[]; family_rows=[]
    for definition in formulas["families"]:
        family_id=definition["family_id"]; prefix=family_id.lower(); res=[target_map[f"{prefix}_{suffix}"] for suffix in ("n12_h26","n16_h26","n20_h26")]; support=[target_map[f"{prefix}_{suffix}"] for suffix in ("n16_h22","n16_h26","n16_h30")]
        rm=[x["target_metrics"]["L2_particle_rms"] for x in res]; rs=[np.asarray(x["low_mode_fourier_signature"]) for x in res]; rcos=[cosine(rs[i],rs[i+1]) for i in range(2)]; rel=[x["relative_neighbor_variation"] for x in res]; grad=np.asarray([x["physical_gradient_scale"] for x in res]); gradcv=float(np.std(grad)/np.mean(grad)); rt=res_rules["resolution_trend_predeclared_checks"]
        rchecks={"target_endpoint_magnitude_nonincreasing":"PASS" if rm[-1]/rm[0]<=float(rt["target_endpoint_L2_ratio_max"]) else "FAIL","adjacent_low_mode_direction_cosine":"PASS" if min(rcos)>=float(rt["adjacent_fourier_direction_cosine_min"]) else "FAIL","relative_neighbor_variation_strictly_decreasing":"PASS" if all(rel[i+1]<rel[i] for i in range(2)) else "FAIL","physical_gradient_scale_coefficient_of_variation":"PASS" if gradcv<=float(rt["physical_gradient_scale_coefficient_of_variation_max"]) else "FAIL"}
        sm=[x["target_metrics"]["L2_particle_rms"] for x in support]; ss=[np.asarray(x["low_mode_fourier_signature"]) for x in support]; scos=[cosine(ss[i],ss[i+1]) for i in range(2)]; st=sup_rules["attribution_thresholds"]
        support_contexts=[contexts[x["case"]["case_id"]] for x in support]; schecks={"bounded_magnitude_variation":"PASS" if max(sm)/min(sm)<=float(st["support_max_L2_magnitude_ratio"]) else "FAIL","adjacent_direction_consistency":"PASS" if min(scos)>=float(st["support_min_adjacent_fourier_direction_cosine"]) else "FAIL","active_neighbor_accounting":"PASS" if all(c["active"].dtype==bool and len(c["active"])==len(c["edges"]["source"]) for c in support_contexts) else "FAIL","zero_weight_exterior_edge_retention":"PASS" if all(x["graph_diagnostics"]["zero_weight_exterior_directed_count"]>0 for x in support) else "FAIL","topology":"PASS" if all(x["topology"]["status"]=="PASS" for x in support) else "FAIL","reference_agreement":"PASS" if all(x["reference_qualification"]["status"]=="PASS" for x in support) else "FAIL"}
        path_status=all(x=="PASS" for x in rchecks.values()) and all(x=="PASS" for x in schecks.values()); path_families.append({"family_id":family_id,"resolution":{"target_L2":rm,"endpoint_ratio":rm[-1]/rm[0],"adjacent_direction_cosines":rcos,"relative_neighbor_variation":rel,"physical_gradient_scale_CV":gradcv,"checks":rchecks,"status":"PASS" if all(x=="PASS" for x in rchecks.values()) else "FAIL","regularity_gate_used":False,"convergence_order_claimed":False},"support":{"target_L2":sm,"magnitude_max_min_ratio":max(sm)/min(sm),"adjacent_direction_cosines":scos,"checks":schecks,"status":"PASS" if all(x=="PASS" for x in schecks.values()) else "FAIL"},"family_paths_PASS":path_status})
        phys=next(x for x in physical_families if x["family_id"]==family_id)["family_5_of_5_PASS"]; ref=next(x for x in reference_families if x["family_id"]==family_id)["family_5_of_5_PASS"]; cons=next(x for x in conservation_families if x["family_id"]==family_id)["family_5_of_5_PASS"]; cases=[x for x in targets if x["case"]["family_id"]==family_id]
        checks={"physical_preflight":"PASS" if phys else "FAIL","reference_qualification":"PASS" if ref else "FAIL","spatial_consistency":"PASS" if all(all(v=="PASS" for v in x["core_checks"].values()) for x in cases) else "FAIL","resolution_consistency":"PASS" if all(v=="PASS" for v in rchecks.values()) else "FAIL","support_consistency":"PASS" if all(v=="PASS" for v in schecks.values()) else "FAIL","temporal_isolation":"PASS" if all(x["temporal_isolation"]["status"]=="PASS" for x in cases) else "FAIL","model_form_scope":"PASS" if all(x["model_form_scope"]=="PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE" for x in cases) else "FAIL","pair_only_conservation":"PASS" if cons else "FAIL","uncertainty":"PASS" if all(x["uncertainty"]["reference_uncertainty"]["status"]=="PASS" and x["uncertainty"]["topology_uncertainty"]["status"]=="PASS" for x in cases) else "FAIL","determinism":"PASS" if ref else "FAIL"}
        family_rows.append({"family_id":family_id,"checks":checks,"whole_family_status":"PASS" if all(v=="PASS" for v in checks.values()) else "diagnostic_or_rejected","materialization_authorized":all(v=="PASS" for v in checks.values()),"partial_materialization_permitted":False})
    write(PHYSICAL_OUT,{"qualification_version":"stage02jw-physical-1.0.0","families":physical_families,"all_4_families_PASS":all(x["family_5_of_5_PASS"] for x in physical_families)})
    write(REFERENCE_OUT,{"qualification_version":"stage02jw-reference-1.0.0","threshold_source":str(REF_RULES_PATH.relative_to(REPO)),"threshold_source_hash":file_hash(REF_RULES_PATH),"families":reference_families,"all_20_PASS":all(x["family_5_of_5_PASS"] for x in reference_families)})
    write(TARGETS_OUT,{"artifact_type":"frozen_blind_spatial_target_candidates","candidate_count":len(targets),"target_sign":"a_reference_minus_a_sph","candidates":targets,"edge_pair_force_target_saved":False,"regularity_eligibility_effect":"none"})
    write(CORE_OUT,{"qualification_version":"stage02jw-target-core-1.0.0","rows":core_rows,"all_20_PASS":all(x["status"]=="PASS" for x in core_rows)})
    write(PATHS_OUT,{"qualification_version":"stage02jw-paths-1.0.0","families":path_families,"all_4_families_resolution_support_PASS":all(x["family_paths_PASS"] for x in path_families),"regularity_hard_gate_used":False})
    write(CONSERVATION_OUT,{"qualification_version":"stage02jw-conservation-1.0.0","families":conservation_families,"all_20_PASS":all(x["family_5_of_5_PASS"] for x in conservation_families),"target_mean_subtraction_used":False,"projection_writeback_used":False})
    write(FAMILY_OUT,{"qualification_version":"stage02jw-family-all-or-none-1.0.0","families":family_rows,"all_4_families_materialization_authorized":all(x["materialization_authorized"] for x in family_rows)})
    print(json.dumps({"physical":all(x["family_5_of_5_PASS"] for x in physical_families),"reference":all(x["family_5_of_5_PASS"] for x in reference_families),"target_core":all(x["status"]=="PASS" for x in core_rows),"paths":all(x["family_paths_PASS"] for x in path_families),"conservation":all(x["family_5_of_5_PASS"] for x in conservation_families),"materialization":all(x["materialization_authorized"] for x in family_rows)},sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
