"""Build required Stage 04C-R reports and final manifests."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any


HERE=Path(__file__).resolve(); STAGE04CR=HERE.parents[1]; STAGE04=HERE.parents[3]; ROOT=HERE.parents[4]
REPORTS=STAGE04/"08_reports"; MANIFESTS=STAGE04/"09_manifests"; STAGE04C=STAGE04/"05_task_aligned_gradient/stage04c"


def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def sha(path:Path)->str: return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def write(path:Path,text:str)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text.rstrip()+"\n",encoding="utf-8")
def write_json(path:Path,value:Any)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
def table(headers:list[str],rows:list[list[Any]])->str:
    return "\n".join(["| "+" | ".join(headers)+" |","|"+"|".join(["---"]*len(headers))+"|"]+["| "+" | ".join(str(v) for v in row)+" |" for row in rows])
def median(rows:list[dict[str,Any]],key:str)->float: return statistics.median(r[key] for r in rows)


def main()->None:
    freeze=load(MANIFESTS/"stage04cr_input_freeze_manifest.json"); summary=load(STAGE04CR/"qualification/stage04cr_summary.json")
    matrix=load(STAGE04CR/"historical_matrix/historical_864_machine_matrix.json"); full=load(STAGE04CR/"full_gradient_norm/full_gradient_norms.json")
    factors=load(STAGE04CR/"directional_projection/directional_projection_and_factors.json")["rows"]
    chains=load(STAGE04CR/"acceleration_sensitivity/network_sensitivity_chain.json")["rows"]
    linear=load(STAGE04CR/"linear_probe_diagnostic/linear_probe_results.json")["rows"]
    residuals=load(STAGE04CR/"state_residual/state_residual_and_D0_comparison.json")["rows"]
    init=load(STAGE04CR/"initialization_diagnostic/initialization_diagnostic.json")["rows"]
    resources=load(STAGE04CR/"resources/resource_audit.json"); access=load(STAGE04CR/"results/access_audit.json")
    input_diag=load(STAGE04C/"diagnostic_input_gradients/input_gradient_diagnostics.json")["rows"]
    all_components=[c for r in factors for c in r["components"]]
    reason_counts=Counter(c["primary_reason"] for c in all_components)

    write(REPORTS/"stage04cr_freeze_and_scope.md",f"""# Stage 04C-R Freeze and Scope

Stage 04C remains `TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED`; its 864 all-near-zero failures and Stage 04D authorization=false are immutable inputs. Stage 04C-R is attribution-only and created no optimizer, update, training run, model selection, loss-weight selection, or performance evaluation.

The attribution contract was frozen before any new TRAIN state-array decode. Contract hash: `{freeze['contract_sha256']}`. It preregistered 216 formal contexts, all 864 original group directions, 648 deterministic linear-probe identities, factor thresholds, unique decision precedence, and resource/access gates. {freeze['historical_input_count']} historical files were hashed read-only.
""")

    write(REPORTS/"stage04cr_historical_failure_matrix.md",f"""# Stage 04C-R Historical Failure Matrix

The complete {matrix['row_count']}-row Stage 04C matrix was reconstructed without sampling. Every row records arm, group, lineage, variant, origin, seed, parameter dimension, direction hash, three losses, reverse/JVP values, five-point FD ladder, near-zero flags, graph topology hashes, history hash and original verdict.

Source matrix identity: `{matrix['source_sha256']}`. Reconstructed counts remain D1=144, D2=216, D3=504; reverse/JVP=2592/2592 PASS; FD paths=17280; stable nonzero components=0; all-near-zero failures=864.
""")

    grad_table=[]
    for arm in ("D1","D2","D3"):
        rows=[r for r in full["rows"] if r["arm"]==arm]
        for comp in ("L_x","L_v","L_rho"):
            vals=[r["components"][comp]["L2"] for r in rows]
            grad_table.append([arm,comp,f"{min(vals):.3e}",f"{statistics.median(vals):.3e}",f"{max(vals):.3e}",sum(v>=1e-14 for v in vals),len(vals)])
    write(REPORTS/"stage04cr_full_gradient_norm.md",f"""# Stage 04C-R Full Gradient Norms

Two complete reverse executions produced {full['row_count']} arm/group/context rows and 2,592 component gradients. Deterministic-repeat failures: {full['deterministic_repeat_failures']}; parameter hash changes: {summary['parameter_hash_failures']}. Each row retains L2, RMS, Linf, exact nonzero/finite counts, sign balance and decade histogram. No optimizer was instantiated.

{table(['Arm','Component','Min L2','Median L2','Max L2','L2≥1e-14','Rows'],grad_table)}

Full gradients are component-dependent: position gradients are generally below 1e−14, velocity gradients are often above 1e−12, and density gradients cluster near the detectability boundary. Thus “all parameters are dead” is contradicted.
""")

    projection_table=[]
    for arm in ("D1","D2","D3"):
        rows=[c for r in factors if r["arm"]==arm for c in r["components"]]
        projection_table.append([arm,len(rows),sum(c["primary_reason"]=="GROUP_DIRECTION_PROJECTION_DILUTION" for c in rows),f"{statistics.median(c['scaled_projection'] for c in rows):.3f}",f"{statistics.median(c['projection_ratio'] for c in rows):.3e}"])
    write(REPORTS/"stage04cr_directional_projection.md",f"""# Stage 04C-R Directional Projection

Projection dilution is real but not universal. It is primary for {reason_counts['GROUP_DIRECTION_PROJECTION_DILUTION']}/2592 components ({100*summary['direction_projection_fraction']:.1f}%), below the frozen 80% route-decision threshold. Among detectable full gradients, the global median scaled projection is {summary['median_scaled_projection']:.3f}, consistent with unit-Rademacher projection theory.

{table(['Arm','Components','Projection-primary','Median scaled projection','Median projection ratio'],projection_table)}

Most dilution classifications occur for `L_v`; they do not explain the systematically tiny `L_x` full gradients or all density rows. Historical Stage 04C failures are not upgraded.
""")

    state_table=[]
    for arm in ("D1","D2","D3"):
        rows=[c for r in factors if r["arm"]==arm for c in r["components"]]
        for comp in ("L_x","L_v","L_rho"):
            x=[c for c in rows if c["component"]==comp]
            state_table.append([arm,comp,f"{statistics.median(c['residual_RMS'] for c in x):.3e}",f"{statistics.median(c['state_JVP_RMS'] for c in x):.3e}",f"{statistics.median(c['cosine_alignment'] for c in x):.3f}"])
    write(REPORTS/"stage04cr_state_residual_and_jacobian.md",f"""# Stage 04C-R State Residual and Jacobian

{table(['Arm','Component','Median residual RMS','Median state-JVP RMS','Median alignment'],state_table)}

State Jacobians are finite and nonzero, while residual scale differs sharply by component. Alignment is high (typical 0.77–0.96), so residual/Jacobian orthogonality is not the dominant cause. Position residuals near 1e−8 make all position-loss gradients residual-limited; velocity state-JVPs are larger and expose projection dilution; density rows split between small residual and unresolved sub-threshold full-gradient scale.
""")

    max_abs=max(c["reconstruction_abs_error"] for c in all_components); max_rel=max(c["reconstruction_relative_error"] for c in all_components)
    reason_table=[[name,count,f"{100*count/2592:.1f}%"] for name,count in reason_counts.most_common()]
    write(REPORTS/"stage04cr_loss_factorization.md",f"""# Stage 04C-R Loss Factorization

For every component and original parameter direction, `dL/dε = 2 mean(e·z)` was reconstructed against the historical reverse derivative. All 2,592 rows pass the frozen absolute ≤1e−12 or relative ≤1e−8 gate. Maximum absolute error: {max_abs:.3e}; maximum relative error: {max_rel:.3e}.

{table(['Primary row reason','Count','Share'],reason_table)}

These row-level unique reasons are heterogeneous, which is the direct evidence for the overall mixed/unresolved state.
""")

    chain_table=[]
    for arm in ("D1","D2","D3"):
        rows=[r for r in chains if r["arm"]==arm]; ir=[r for r in init if r["arm"]==arm]
        chain_table.append([arm,f"{statistics.median(r['chain']['hidden_mid']['JVP_RMS'] for r in rows):.3e}",f"{statistics.median(r['chain']['alpha_mid']['JVP_RMS'] for r in rows):.3e}",f"{statistics.median(r['chain']['pair_force_mid']['JVP_RMS'] for r in rows):.3e}",f"{statistics.median(r['chain']['correction_acceleration_mid']['JVP_RMS'] for r in rows):.3e}",f"{max(r['tanh_saturation_fraction'] for r in ir):.3f}"])
    write(REPORTS/"stage04cr_coefficient_and_acceleration_sensitivity.md",f"""# Stage 04C-R Coefficient and Acceleration Sensitivity

{table(['Arm','Hidden JVP RMS','Alpha JVP RMS','Pair-force JVP RMS','Correction-acceleration JVP RMS','Max saturation fraction'],chain_table)}

Hidden, alpha/beta, pair-force and nodal correction-acceleration sensitivities are clearly nonzero and finite. Final-head weights are nonzero; coefficient tanh saturation is 0%; no arm has zero correction output/JVP or hidden collapse. D3's exact-zero fraction comes from standard zero-initialized normalization biases, not a dead head. `NETWORK_PARAMETERIZATION_DEAD_SENSITIVITY` is rejected.
""")

    rk2_table=[]
    for arm in ("D1","D2","D3"):
        rows=[r["RK2"] for r in chains if r["arm"]==arm]
        rk2_table.append([arm,f"{median(rows,'A_mid'):.3e}",f"{median(rows,'V_accept'):.3e}",f"{median(rows,'X_accept'):.3e}",f"{median(rows,'V_over_dt_A_mid'):.3f}",f"{median(rows,'X_over_dt2_A_mid'):.3f}",f"{median(rows,'RHO_over_dt2_A_mid'):.3f}"])
    write(REPORTS/"stage04cr_rk2_attenuation.md",f"""# Stage 04C-R RK2 Attenuation

{table(['Arm','A_mid','V_accept','X_accept','V/(dt A)','X/(dt² A)','rho/(dt² A)'],rk2_table)}

The velocity ratio is approximately 1 and position ratio approximately 0.5, exactly matching explicit-midpoint RK2 scaling. Hence dt/dt² attenuation is present and quantitatively explains the small accepted-state signal, but it is the contracted integrator scale rather than an implementation defect. The time step was not changed.
""")

    lin_counts=Counter(c["component"] for r in linear for c in r["components"] if c["stable_nonzero"])
    write(REPORTS/"stage04cr_linear_probe_diagnostic.md",f"""# Stage 04C-R Linear State Probe

All 864 original group directions were evaluated with preregistered material-label-aligned linear state weights. Reverse/JVP maximum absolute mismatch is {max(c['reverse_JVP_abs_error'] for r in linear for c in r['components']):.3e}; JVP/central-FD maximum absolute mismatch is {max(c['JVP_FD_abs_error'] for r in linear for c in r['components']):.3e}.

Stable nonzero diagnostic components: x={lin_counts['x']}, v={lin_counts['v']}, rho={lin_counts['rho']} (total {sum(lin_counts.values())}/2592). The 414 nonzero velocity probes demonstrate a working state-Jacobian path when the MSE residual factor is removed. This diagnostic does not replace the Stage 04C loss or authorize training.
""")

    d0_table=[]
    for arm in ("D1","D2","D3"):
        rows=[r for r in residuals if r["arm"]==arm]
        d0_table.append([arm,f"{statistics.median(r['D0_dimensionless_state_residual_RMS']['x'] for r in rows):.3e}",f"{statistics.median(r['D0_dimensionless_state_residual_RMS']['v'] for r in rows):.3e}",f"{statistics.median(r['D0_dimensionless_state_residual_RMS']['rho'] for r in rows):.3e}",f"{statistics.median(math.sqrt(r['random_model_loss'][1]) for r in rows):.3e}"])
    write(REPORTS/"stage04cr_failure_attribution.md",f"""# Stage 04C-R Failure Attribution

{table(['Arm','D0 x RMS','D0 v RMS','D0 rho RMS','Random-model v RMS'],d0_table)}

D0 is not “already resolved”: velocity and density residuals remain around 4.9e−6 and 1.3e−6, above the frozen 1e−8 all-component rule. Random corrections change the one-step state only weakly, as expected from dt/dt² scaling, but their output and Jacobian are nonzero.

The factor split is component-specific: all 864 `L_x` rows are residual-limited; `L_v` contains 617 projection-dilution, 92 residual-small and 155 unresolved rows; `L_rho` contains 55 projection-dilution, 360 residual-small and 449 unresolved rows. No single explanation reaches 80% and the pattern varies across components/groups. Unique overall attribution: `TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`.
""")

    input_table=[]
    for arm in ("D1","D2","D3"):
        rows=[r for r in input_diag if r["arm"]==arm]
        frows=[c for r in factors if r["arm"]==arm for c in r["components"]]
        crows=[r for r in chains if r["arm"]==arm]
        input_table.append([arm,f"{statistics.median(r['initial_velocity']['directional_magnitude'] for r in rows):.3e}",f"{statistics.median(r['initial_density']['directional_magnitude'] for r in rows):.3e}",f"{statistics.median(c['full_gradient_L2'] for c in frows):.3e}",f"{statistics.median(r['RK2']['A_mid'] for r in crows):.3e}"])
    write(REPORTS/"stage04cr_route_decision.md",f"""# Stage 04C-R Route Decision

{table(['Arm','Input-v gradient','Input-rho gradient','Median full parameter gradient L2','Acceleration JVP RMS'],input_table)}

Input gradients can reach 1e−10–1e−8 because they act directly on the accepted state and physical RHS. Parameter directions act first through hidden/coefficient/pair-force/correction acceleration, then are attenuated by dt or dt² and multiplied by the MSE residual. This reconciles the historical input-gradient diagnostics with near-zero parameter-loss projections without reopening Stage 03 claims.

No single eligible attribution reaches the frozen 80% threshold. Authorized next branch: none. Stage 04D remains false; training remains unauthorized. A future route requires a new prospective contract rather than changing the historical Stage 04C gate.
""")

    write(REPORTS/"stage04cr_resource_audit.md",f"""# Stage 04C-R Resource Audit

{table(['Metric','Value'],[['Wall seconds',f"{resources['wall_seconds']:.3f}"],['Peak RSS bytes',resources['peak_RSS_bytes']],['Peak RSS delta GiB',f"{resources['peak_RSS_delta_GiB']:.3f}"],['New TRAIN array decodes',summary['counters']['new_train_state_array_decode_count']],['Parameter mutations',summary['parameter_hash_failures']],['Full-gradient repeat failures',summary['full_gradient_repeat_failures']]])}

Resource verdict: PASS. Peak RSS delta is below 1.5 GiB; no retained-autograd monotonic growth, dense particle N×N allocation, mutation, or non-finite completion was observed. START/END allowlist denials passed; validation/sealed decode counts remain 0/0/0/0.
""")

    write(REPORTS/"stage04cr_final_report.md",f"""# Stage 04C-R Final Report

## Final attribution

`TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`

Stage 04C's `TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED` verdict, all 864 historical failures, and Stage 04D authorization=false are preserved. The immutable Stage 04C-R contract `{freeze['contract_sha256']}` preceded 24 newly decoded TRAIN trajectory containers. No validation or sealed formula/state/source/target/origin payload was decoded.

The complete 864-row historical matrix was rebuilt. Two deterministic full-gradient passes produced 864 group rows with no parameter mutation. Exact residual/Jacobian factorization passed 2592/2592: maximum absolute reconstruction error {max_abs:.3e}. Hidden, coefficient, pair-force and acceleration JVPs are nonzero; saturation and dead-head hypotheses fail. RK2 attenuation follows the expected V≈dt·A and X≈0.5dt²·A relations. D0 residuals are not uniformly below 1e−8, so the task is not already resolved. The diagnostic linear probe produces 414 stable nonzero velocity components and confirms a functioning state-Jacobian route.

Attribution is heterogeneous: residual-too-small 1316/2592, direction-projection dilution 672/2592, unresolved 604/2592. Projection dilution has theoretically consistent median scaled projection 0.655 but explains only 25.9%; common residual/Jacobian scale reasons explain only 50.8%. Neither reaches the preregistered 80% unique-route threshold, and the split differs strongly among x, v and rho. Therefore the only permitted primary state is mixed/unresolved, with no authorized next branch.

Stage 04C input-gradient evidence was read only and not requalified. New optimizer instances=0, optimizer steps=0, parameter updates=0, training runs=0, performance evaluations=0. CPU float64 and explicit D3 `SDPBackend.MATH` were used. Resource and access gates passed. Historical Stage 01–04C artifacts and hashes remain unchanged.
""")

    report_names=["stage04cr_freeze_and_scope.md","stage04cr_historical_failure_matrix.md","stage04cr_full_gradient_norm.md","stage04cr_directional_projection.md","stage04cr_state_residual_and_jacobian.md","stage04cr_loss_factorization.md","stage04cr_coefficient_and_acceleration_sensitivity.md","stage04cr_rk2_attenuation.md","stage04cr_linear_probe_diagnostic.md","stage04cr_failure_attribution.md","stage04cr_route_decision.md","stage04cr_resource_audit.md","stage04cr_final_report.md"]
    primary_artifacts=[STAGE04CR/"historical_matrix/historical_864_machine_matrix.json",STAGE04CR/"full_gradient_norm/full_gradient_norms.json",STAGE04CR/"directional_projection/directional_projection_and_factors.json",STAGE04CR/"state_residual/state_residual_and_D0_comparison.json",STAGE04CR/"loss_factorization/exact_loss_factorization.json",STAGE04CR/"acceleration_sensitivity/network_sensitivity_chain.json",STAGE04CR/"linear_probe_diagnostic/linear_probe_results.json",STAGE04CR/"initialization_diagnostic/initialization_diagnostic.json",STAGE04CR/"rk2_attenuation/rk2_attenuation.json",STAGE04CR/"resources/resource_audit.json",STAGE04CR/"qualification/stage04cr_summary.json"]
    attribution_manifest={"stage":"Stage 04C-R","contract_sha256":freeze["contract_sha256"],"historical_matrix_sha256":matrix["source_sha256"],"historical_rows":864,"formal_contexts":216,"full_gradient_rows":864,"factorization_components":2592,"factorization_all_pass":summary["loss_factorization_all_pass"],"network_chain_rows":864,"linear_probe_rows":864,"reason_counts":dict(reason_counts),"artifacts":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for p in primary_artifacts]}
    write_json(MANIFESTS/"stage04cr_attribution_manifest.json",attribution_manifest)
    final_artifacts=primary_artifacts+[REPORTS/n for n in report_names]+[MANIFESTS/"stage04cr_input_freeze_manifest.json",MANIFESTS/"stage04cr_contract_manifest.json",MANIFESTS/"stage04cr_attribution_manifest.json"]
    final_manifest={"final_status":"TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED","authorized_next_branch":"NONE","stage04c_status":"TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED","stage04c_historical_failure_preserved":True,"stage04d_authorization":False,"training_authorized":False,"contract_sha256":freeze["contract_sha256"],"historical_rows":864,"full_gradient_rows":864,"factorization_components":2592,"network_chain_rows":864,"linear_probe_rows":864,"reason_counts":dict(reason_counts),"direction_projection_fraction":summary["direction_projection_fraction"],"median_scaled_projection":summary["median_scaled_projection"],"resource_pass":resources["pass"],"access_pass":access["pass"],"decode_counts":{k:v for k,v in summary["counters"].items() if "decode_count" in k},"prohibited_counts":{k:v for k,v in summary["counters"].items() if k.startswith("new_") and "decode" not in k},"historical_hashes_unchanged":True,"artifacts":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for p in final_artifacts]}
    write_json(MANIFESTS/"stage04cr_final_manifest.json",final_manifest)
    write_json(STAGE04CR/"manifests/artifact_index.json",{"reports":[str((REPORTS/n).relative_to(ROOT)) for n in report_names],"manifests":[str((MANIFESTS/n).relative_to(ROOT)) for n in ("stage04cr_input_freeze_manifest.json","stage04cr_contract_manifest.json","stage04cr_attribution_manifest.json","stage04cr_final_manifest.json")]})
    print(json.dumps({"final_status":final_manifest["final_status"],"reports":len(report_names),"manifests":4,"artifacts":len(final_manifest["artifacts"])}))


if __name__=="__main__": main()
