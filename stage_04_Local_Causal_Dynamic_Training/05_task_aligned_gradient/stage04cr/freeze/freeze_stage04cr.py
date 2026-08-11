"""Freeze Stage 04C-R attribution inputs before any new TRAIN-array decode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve()
STAGE04CR = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    for name in (
        "freeze", "contracts", "historical_matrix", "full_gradient_norm", "directional_projection",
        "state_residual", "state_jacobian", "loss_factorization", "coefficient_sensitivity",
        "acceleration_sensitivity", "rk2_attenuation", "linear_probe_diagnostic",
        "initialization_diagnostic", "trainability_attribution", "route_decision", "resources",
        "qualification", "manifests", "results",
    ):
        (STAGE04CR / name).mkdir(parents=True, exist_ok=True)

    stage04c = STAGE04 / "05_task_aligned_gradient/stage04c"
    historical = [
        STAGE04 / "08_reports/stage04c_final_report.md",
        stage04c / "contracts/task_aligned_parameter_gradient_contract_v0_1.yaml",
        stage04c / "results/formal_864_probe_results.json",
        stage04c / "structure_and_safety/structure_audit.json",
        stage04c / "resources/resource_audit.json",
        stage04c / "diagnostic_input_gradients/input_gradient_diagnostics.json",
        STAGE04 / "09_manifests/stage04c_final_manifest.json",
        STAGE04 / "09_manifests/stage04c_case_manifest.json",
        STAGE04 / "09_manifests/stage04c_parameter_manifest.json",
        STAGE04 / "09_manifests/stage04c_direction_manifest.json",
        STAGE04 / "09_manifests/stage04c_adfd_manifest.json",
        STAGE04 / "09_manifests/stage04b_trajectory_manifest.json",
        STAGE04 / "09_manifests/stage04b_role_assignment_manifest.json",
        STAGE04 / "09_manifests/stage04b_test_seal_manifest.json",
        ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json",
        ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json",
        ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json",
    ]
    stage03c = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
    sources = sorted(path for path in stage03c.rglob("*.py") if any(part in {
        "arm_d1", "arm_d2", "arm_d3", "baseline_d0", "graph_rebuild", "pair_force_head",
        "rk2_core", "temporal_history", "tokenization",
    } for part in path.parts))
    rows = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in historical + sources]
    final04c = json.loads((STAGE04 / "09_manifests/stage04c_final_manifest.json").read_text(encoding="utf-8"))
    if final04c["final_status"] != "TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED":
        raise RuntimeError("Stage04C failure authorization is absent")
    formal = json.loads((stage04c / "results/formal_864_probe_results.json").read_text(encoding="utf-8"))["probes"]
    if len(formal) != 864 or sum(p["all_near_zero"] for p in formal) != 864:
        raise RuntimeError("historical 864-row failure matrix mismatch")
    contexts = sorted({(p["arm"], p["lineage"], p["variant"], p["origin"], p["model_seed"]) for p in formal})
    definitions = [{k: p[k] for k in ("arm","group","lineage","variant","origin","model_seed","resolution","direction_seed_sha256")} for p in formal]
    linear_identities = []
    for arm, lineage, variant, origin, seed in contexts:
        for component in ("x", "v", "rho"):
            raw = "stage04cr_linear_state_probe_v1" + lineage + variant + str(origin) + str(seed) + component
            linear_identities.append({"arm":arm,"lineage":lineage,"variant":variant,"origin":origin,"model_seed":seed,"component":component,"weight_seed_sha256":sha_text(raw)})

    contract = {
        "stage": "Stage 04C-R — K=1 Task-Signal Sensitivity Attribution and Training-Route Decision",
        "version": "v0.1", "authorization": "Stage04C:TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED",
        "historical_failure_preserved": {"formal_probes":864,"reverse_jvp_pass":2592,"fd_paths":17280,"topology_changes":0,"stable_nonzero_components":0,"near_zero_components":2592,"all_near_zero_failures":864,"stage04d_authorization":False},
        "environment": {"device":"CPU","dtype":"float64","D3_attention":"SDPBackend.MATH","flash":False,"memory_efficient":False,"automatic":False},
        "context_matrix": {"contexts":len(contexts),"formal_group_rows":864,"parameter_seeds":[20400401,20400402,20400403],"reuse_stage04c_directions":True,"definitions":definitions},
        "full_gradient_norms": {"metrics":["L2","RMS","Linf","nonzero_element_count","finite_count","sign_balance","histogram_decade"],"repeat":2,"detectable_L2_threshold":1e-14,"no_optimizer":True},
        "state_normalization": {"y_x":"x/L","y_v":"v/cs","y_rho":"(rho-rho0)/rho0","L":2.0,"cs":20.0,"rho0":1.0},
        "loss_factorization": {"identity":"dL/depsilon=2 mean(e dot z)","absolute_gate":1e-12,"relative_gate":1e-8},
        "projection": {"ratio":"abs(dot(gradient,d))/max(L2,1e-30)","scaled":"ratio*sqrt(group_dimension)","dilution_gradient_L2_min":1e-12,"directional_abs_max":1e-10,"scaled_projection_interval":[0.05,5.0]},
        "factor_thresholds": {"residual_too_small_RMS":1e-6,"state_jacobian_too_small_RMS":1e-14,"orthogonal_alignment_max":1e-4,"network_dead_output_and_jvp_RMS":1e-14,"coefficient_saturation_abs_tanh_min":0.99,"task_already_resolved_D0_dimensionless_state_RMS":1e-8},
        "primary_reason_precedence": ["GROUP_DIRECTION_PROJECTION_DILUTION","TASK_RESIDUAL_TOO_SMALL","TASK_STATE_JACOBIAN_TOO_SMALL","TASK_RESIDUAL_JACOBIAN_ORTHOGONAL","MULTIPLE_FACTORS","UNRESOLVED"],
        "network_chain": ["hidden","alpha_beta","pair_force","correction_acceleration","midpoint_state","accepted_state","loss_derivative"],
        "rk2_attenuation_ratios": ["V_accept/(dt*A_mid)","X_accept/(dt^2*A_mid)","RHO_accept/(dt^2*A_mid)"],
        "linear_probe": {"namespace":"stage04cr_linear_state_probe_v1","weights":"material-label-aligned unit-L2 Rademacher","objective":"mean(w dot y_accept)","modes":["reverse","JVP","central_FD"],"fd_epsilon":1e-4,"diagnostic_only":True,"identities":linear_identities},
        "overall_decision_rules": {
            "COMMON_SIGNAL_SCALE":"AD/FD consistent; detectable full gradients/state Jacobians and network sensitivity; >=80% rows attributed to residual/alignment/RK2 scale; no dead parameterization",
            "DIRECTION_PROJECTION":"AD/FD consistent; >=80% rows satisfy projection dilution; median scaled projection in [0.05,5]; normal state/Jacobian chain",
            "PARAMETERIZATION_DEAD_ZONE":"network coefficient or correction-acceleration output and JVP <=1e-14 in >=80% rows while residual is not small",
            "TASK_ALREADY_RESOLVED":"D0 dimensionless state residual RMS <=1e-8 in all contexts with detectable state Jacobian",
            "MIXED_OR_UNRESOLVED":"no single eligible rule reaches 80% or results conflict across arm/group/lineage",
            "EVIDENCE_INCOMPLETE":"required provenance, full gradients, state-Jacobian, chain, or access evidence missing",
        },
        "resource_gates": {"peak_RSS_delta_GiB_max":1.5,"parameter_mutation":False,"retained_autograd_monotonic_growth":False,"dense_particle_NxN":False,"finite_completion":True,"validation_sealed_decode_counts":0},
        "prohibited_counts": {"new_optimizer_instances":0,"new_optimizer_steps":0,"new_parameter_updates":0,"new_training_runs":0,"new_performance_evaluations":0},
    }
    contract_path = STAGE04CR / "contracts/task_signal_sensitivity_attribution_contract_v0_1.yaml"
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding="utf-8")
    freeze_record = {
        "freeze_completed_before_new_train_state_array_decode":True,"new_train_state_array_decode_count_at_freeze":0,
        "historical_input_count":len(rows),"historical_inputs":rows,"historical_matrix_rows":864,
        "historical_matrix_sha256":sha(stage04c/"results/formal_864_probe_results.json"),
        "contract_path":str(contract_path.relative_to(ROOT)),"contract_sha256":sha(contract_path),
        "linear_probe_identity_count":len(linear_identities),"stage04c_status":final04c["final_status"],"stage04d_authorization":False,"pass":True,
    }
    write_json(STAGE04CR / "freeze/stage04cr_freeze_record.json", freeze_record)
    write_json(STAGE04CR / "historical_matrix/reconstructed_864_definitions.json", {"rows":definitions,"row_count":len(definitions),"source_sha256":freeze_record["historical_matrix_sha256"]})
    write_json(STAGE04CR / "linear_probe_diagnostic/preregistered_linear_probe_identities.json", {"identities":linear_identities,"count":len(linear_identities)})
    write_json(STAGE04 / "09_manifests/stage04cr_input_freeze_manifest.json", freeze_record)
    write_json(STAGE04 / "09_manifests/stage04cr_contract_manifest.json", {"contract":str(contract_path.relative_to(ROOT)),"sha256":sha(contract_path),"immutable_after_new_train_decode":True,"stage04d_authorization":False})
    print(json.dumps({"contract_sha256":sha(contract_path),"contexts":len(contexts),"historical_rows":len(definitions),"linear_identities":len(linear_identities)}))


if __name__ == "__main__":
    main()
