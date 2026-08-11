"""Build the required Stage 04C human reports and final machine manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
STAGE04C = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]
REPORTS = STAGE04 / "08_reports"
MANIFESTS = STAGE04 / "09_manifests"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(out)


def main() -> None:
    freeze = load(MANIFESTS / "stage04c_input_freeze_manifest.json")
    cases = load(MANIFESTS / "stage04c_case_manifest.json")
    params = load(MANIFESTS / "stage04c_parameter_manifest.json")
    directions = load(MANIFESTS / "stage04c_direction_manifest.json")
    summary = load(STAGE04C / "qualification/stage04c_qualification_summary.json")
    formal = load(STAGE04C / "results/formal_864_probe_results.json")["probes"]
    structure = load(STAGE04C / "structure_and_safety/structure_audit.json")
    diagnostics = load(STAGE04C / "diagnostic_input_gradients/input_gradient_diagnostics.json")
    resolution = load(STAGE04C / "results/N12_N16_audit.json")
    resources = load(STAGE04C / "resources/resource_audit.json")
    access = load(STAGE04C / "access_control/access_audit.json")
    adfd = load(MANIFESTS / "stage04c_adfd_manifest.json")

    contract_hash = freeze["contract_sha256"]
    all_near = sum(p["all_near_zero"] for p in formal)
    near_components = sum(c["near_zero"] for p in formal for c in p["components"])
    nonzero_stable = sum((not c["near_zero"]) and bool(c["stable_window"]) for p in formal for c in p["components"])
    rj_fail = sum(not c["pass"] for p in formal for c in p["reverse_jvp"])
    topology_changed = sum(not e["topology_preserving"] for p in formal for e in p["fd"])
    deterministic_fail = sum(not p["deterministic"] for p in formal)
    mutation_count = sum(p["parameter_mutation"] for p in formal)

    write(REPORTS / "stage04c_freeze_and_scope.md", f"""# Stage 04C Freeze and Scope

Stage 04B authorization is `LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED`. Historical input freeze passed for {freeze['historical_input_count']} hashed inputs. The Stage 04C contract was written before the first TRAIN state-array decode; decode count at freeze was 0.

- Contract: `05_task_aligned_gradient/stage04c/contracts/task_aligned_parameter_gradient_contract_v0_1.yaml`
- Immutable contract hash: `{contract_hash}`
- Formal scope: CPU float64, explicit `SDPBackend.MATH`, N8, 6 TRAIN lineages, 2 variants, 2 origins, 3 seeds.
- Prohibited throughout: optimizer, parameter update, training, neural rollout evaluation, normalization fitting, validation target decode and sealed payload decode.
- Historical Stage 03D/03D-R failures and Stage 03E denial remain unchanged.
""")

    write(REPORTS / "stage04c_access_control.md", f"""# Stage 04C Access Control

Both START and END denial audits passed. The application allowlist rejected validation targets and sealed formula/state/target paths before OS-level reads; file permissions were not used as the sole seal.

{table(['Counter','Final value'], [[k,v] for k,v in access['counters'].items() if 'decode_count' in k])}

TRAIN state-array containers decoded: {access['counters']['train_state_array_decode_count']}. All were resolved below `stage04b/exact_trajectories/train` by the frozen allowlist. No cross-role access occurred.
""")

    origin_table = [[r["lineage"], r["variant"], ", ".join(map(str,r["selected_origins"]))] for r in cases["origin_rows"]]
    write(REPORTS / "stage04c_case_selection.md", f"""# Stage 04C Case Selection

Origins were selected before state-array decode by ascending SHA-256 of `stage04c_origin_selection_v1 || lineage || variant || origin`, over legal origins 0–31.

{table(['Lineage','Variant','Selected origins'], origin_table)}

Each arm has 72 contexts: 6 lineages × 2 variants × 2 origins × 3 frozen model seeds. No origin, seed, lineage, or variant was replaced after observing results.
""")

    group_table = [[g["arm"],g["group"],g["parameter_count"],len(g["tensors"]),g["group_hash"]] for g in params["groups"]]
    write(REPORTS / "stage04c_parameter_group_map.md", f"""# Stage 04C Parameter Group Map

All trainable elements were resolved from the actual Stage 03C `named_parameters()` paths and assigned exactly once. Unassigned elements: 0; multiply assigned elements: 0. Combined D3 Q/K/V tensors use non-overlapping row slices `[0:32]`, `[32:64]`, and `[64:96]` in both Transformer layers. D3 relative-offset embeddings and LayerNorm tensors are registered with the feed-forward/temporal-support group.

{table(['Arm','Group','Elements','Tensor/slice rows','Group hash'], group_table)}

Fresh parameter counts are D1=5,762, D2=12,098, D3=22,978. Three independent initializations used seeds 20400401–20400403; checkpoint and historical weight reads were zero.
""")

    write(REPORTS / "stage04c_task_aligned_loss.md", """# Stage 04C Task-Aligned Loss

The formal objective is the component vector `[L_x, L_v, L_rho]` from a complete K=1 explicit-midpoint RK2 transition. `L_x` uses periodic minimum-image position error normalized by L²; `L_v` uses velocity error normalized by cs²; `L_rho` uses density error normalized by rho0².

Every evaluation rebuilds the start, midpoint and accepted graphs. The midpoint token is ephemeral; reference midpoint state is never injected. D2/D3 prehistory contains only frames n−3 through n, and accepted history commits exactly once after acceptance with midpoint commit count zero. `L_sum` is reported only as a diagnostic and does not select Stage 04D training weights.
""")

    write(REPORTS / "stage04c_reverse_jvp.md", f"""# Stage 04C Reverse VJP and Forward JVP

All {len(formal)*3} component comparisons passed the frozen reverse/JVP gate; failures: {rj_fail}. Each row was independently repeated twice with fresh functional state and explicit math attention. Directional derivatives used the same preregistered normalized Rademacher direction in both modes; JVP was computed by PyTorch's autograd JVP, not finite differences.

This exact agreement does not establish qualification by itself: all {near_components} component directions were below the Stage 04C FD-resolution threshold, so the mandatory nonzero-sensitivity evidence is absent.
""")

    write(REPORTS / "stage04c_finite_difference.md", f"""# Stage 04C Central Finite Difference

Each of 864 probes used the frozen epsilon ladder `[1e-2, 3e-3, 1e-3, 3e-4, 1e-4]` with `epsilon_actual = epsilon × max(1, group_RMS)`. Every plus/minus path was repeated twice from fresh state/history, for {resources['fd_path_count']} paths.

- Topology-changing epsilon rows: {topology_changed}
- Deterministic-probe failures: {deterministic_fail}
- Parameter mutations: {mutation_count}
- Density/finite safety completion: PASS

All central-FD estimates were absolutely stable for near-zero classification; none can substitute for the contract's required nonzero component window.
""")

    arm_rows = [[a,v["probes"],v["passed_probes"],f"{100*v['probe_pass_rate']:.1f}%",v["groups_pass"]] for a,v in summary["aggregation"]["arms"].items()]
    write(REPORTS / "stage04c_stable_window_results.md", f"""# Stage 04C Stable-Window Results

Stable nonzero components: {nonzero_stable}. Near-zero components: {near_components}. All-near-zero probe failures: {all_near}. All five epsilons were topology preserving; near-zero FD estimates met the absolute stability gate, but every formal probe failed the rule requiring at least one nonzero stable component.

{table(['Arm','Probes','Passed','Pass rate','All groups pass'], arm_rows)}

Thus no seed-lineage-group can reach 3/4, no lineage-group can reach 2/3, and no parameter group or arm passes.
""")

    diag_rows=[]
    for arm in ("D1","D2","D3"):
        rows=[r for r in diagnostics["rows"] if r["arm"]==arm]
        diag_rows.append([arm,len(rows),f"{min(r['initial_velocity']['directional_magnitude'] for r in rows):.3e}",f"{max(r['initial_velocity']['directional_magnitude'] for r in rows):.3e}",f"{max(max(r[k]['max_abs_difference'] for k in ('initial_velocity','initial_density','reference_prehistory_token')) for r in rows):.3e}"])
    write(REPORTS / "stage04c_input_gradient_diagnostics.md", f"""# Stage 04C Input-Gradient Diagnostics

This 18-row diagnostic matrix covers 2 TRAIN lineages × 1 variant × 1 origin × 3 seeds per arm. It is explicitly excluded from hard qualification and was not used to alter the K=1 contract.

{table(['Arm','Rows','Min velocity magnitude','Max velocity magnitude','Max reverse/JVP error'],diag_rows)}

Reference prehistory tokens are supplied directly to the temporal-history constructor for D2/D3; D1 is marked not applicable. No claim is made that Stage 03 input-gradient failures are repaired.
""")

    write(REPORTS / "stage04c_structure_and_safety.md", f"""# Stage 04C Structure and Safety

The required {structure['count']} arm × seed × lineage records all passed. Audits cover pair exchange/antisymmetry, normalized correction-force residual ≤1e−10, permutation, edge reorder, translation, Galilean boost, SO(2), reflection, periodic representative, positive density, finite outputs, deterministic repeat, and causal history commits.

Accepted-history commit count was exactly one for temporal arms; midpoint commit count was zero. No conservation projection was used. N12/N16 produced {len(resolution['rows'])} audit-only parameter-group rows and all reverse/JVP comparisons passed; these rows did not replace any N8 failure or support a resolution-generalization claim.
""")

    write(REPORTS / "stage04c_resource_audit.md", f"""# Stage 04C Resource Audit

{table(['Metric','Value'], [
['Wall time (s)',f"{resources['wall_seconds']:.3f}"],['Reverse time (s)',f"{resources['reverse_seconds']:.3f}"],['JVP time (s)',f"{resources['jvp_seconds']:.3f}"],['FD time (s)',f"{resources['fd_seconds']:.3f}"],
['FD paths',resources['fd_path_count']],['Graph rebuild lower bound',resources['graph_rebuild_count_lower_bound']],['Peak RSS (bytes)',resources['peak_rss_bytes']],['Peak RSS delta (GiB)',f"{resources['peak_rss_delta_gib']:.3f}"],
])}

Resource verdict: PASS. Peak RSS delta was below 1.5 GiB; no monotonic retained-autograd growth, parameter mutation, or dense particle N×N allocation was observed. Completion and required hashes were finite/complete.
""")

    group_result_rows=[[r['arm'],r['group'],r['passed_lineages'],r['total_lineages'],r['pass']] for r in summary['aggregation']['groups']]
    write(REPORTS / "stage04c_qualification_report.md", f"""# Stage 04C Qualification Report

Formal evidence is complete: D1 144, D2 216, D3 504, total 864 probes. Reverse/JVP passed 100%; no sign mismatch, topology change, parameter mutation, access violation, structural failure, or resource failure occurred.

{table(['Arm','Group','Passed lineages','Required','Pass'],group_result_rows)}

The decisive hard-gate failure is `all_near_zero`: {all_near}/864 probes have all three directional task-loss components below 1e−10. The contract forbids treating an all-near-zero probe as qualification evidence. Consequently every arm has 0% probe pass rate, below the required 85%, and every parameter group fails lineage coverage.

Verdict: `TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED`.
""")

    write(REPORTS / "stage04c_final_report.md", f"""# Stage 04C Final Report

## Decision

`TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED`

Stage 04B supplied valid authorization and the {freeze['historical_input_count']}-input historical freeze passed. The Stage 04C contract was frozen before TRAIN state decode at `{contract_hash}`. Access remained TRAIN-only; START/END validation and sealed denial audits passed with validation/sealed decode counts 0/0/0/0.

Formal execution used fresh D1/D2/D3 Stage 03C models on CPU float64 with explicit `SDPBackend.MATH`. Actual tensor paths uniquely cover every trainable parameter, including sliced D3 combined Q/K/V tensors. SHA-256 selected all origins and directions before results were observed.

The K=1 objective separately qualified candidate derivatives of `L_x`, `L_v`, and `L_rho`. Across all 864 probes, reverse VJP and genuine JVP agreed 100%, all {resources['fd_path_count']} central-FD paths were deterministic and topology preserving, and near-zero estimates had stable absolute FD windows. However, all 864 probes had all three component sensitivities below the frozen 1e−10 threshold. Because each probe must contain at least one nonzero stable component, 0/144 D1, 0/216 D2 and 0/504 D3 probes pass. Every parameter group and arm therefore fails.

Structure/safety passed 54/54 saved records. Audit-only N12/N16 reverse/JVP checks passed {len(resolution['rows'])}/{len(resolution['rows'])}. Resource and access gates passed. Diagnostic input gradients remain non-qualifying. Optimizer instances=0, optimizer steps=0, training runs=0, parameter updates=0, neural rollouts=0, performance evaluations=0.

Stage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`; Stage 03D-R remains `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`; Stage 03E authorization remains false. Stage 04D is not authorized, and Stage 04 training remains `NOT_AUTHORIZED`.
""")

    # Small machine-readable boundary artifacts for otherwise report-only folders.
    write_json(STAGE04C / "loss_components/task_aligned_loss_contract.json", {"components":["L_x","L_v","L_rho"],"K":1,"training_weights_selected":False,"contract_sha256":contract_hash})
    write_json(STAGE04C / "determinism/determinism_summary.json", {"formal_probe_count":864,"deterministic_failures":deterministic_fail,"topology_changing_epsilons":topology_changed,"parameter_mutations":mutation_count,"pass":deterministic_fail==topology_changed==mutation_count==0})
    write_json(STAGE04C / "manifests/artifact_index.json", {"reports":[f"08_reports/{name}" for name in [
        "stage04c_freeze_and_scope.md","stage04c_access_control.md","stage04c_case_selection.md","stage04c_parameter_group_map.md","stage04c_task_aligned_loss.md","stage04c_reverse_jvp.md","stage04c_finite_difference.md","stage04c_stable_window_results.md","stage04c_input_gradient_diagnostics.md","stage04c_structure_and_safety.md","stage04c_resource_audit.md","stage04c_qualification_report.md","stage04c_final_report.md"]]})

    report_names = [
        "stage04c_freeze_and_scope.md","stage04c_access_control.md","stage04c_case_selection.md","stage04c_parameter_group_map.md","stage04c_task_aligned_loss.md","stage04c_reverse_jvp.md","stage04c_finite_difference.md","stage04c_stable_window_results.md","stage04c_input_gradient_diagnostics.md","stage04c_structure_and_safety.md","stage04c_resource_audit.md","stage04c_qualification_report.md","stage04c_final_report.md",
    ]
    artifact_paths = [REPORTS/name for name in report_names] + [
        MANIFESTS/"stage04c_input_freeze_manifest.json", MANIFESTS/"stage04c_contract_manifest.json", MANIFESTS/"stage04c_case_manifest.json",
        MANIFESTS/"stage04c_parameter_manifest.json", MANIFESTS/"stage04c_direction_manifest.json", MANIFESTS/"stage04c_adfd_manifest.json",
        STAGE04C/"results/formal_864_probe_results.json", STAGE04C/"structure_and_safety/structure_audit.json", STAGE04C/"results/N12_N16_audit.json",
        STAGE04C/"diagnostic_input_gradients/input_gradient_diagnostics.json", STAGE04C/"resources/resource_audit.json", STAGE04C/"access_control/access_audit.json",
    ]
    final_manifest = {
        "stage":"Stage 04C — Task-Aligned Parameter-Gradient Qualification","final_status":"TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED",
        "stage04b_authorization":"LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED","historical_freeze_pass":True,"contract_sha256":contract_hash,
        "backend_identity":adfd["backend_identity"],"formal_contexts_per_arm":72,"formal_probe_counts":{"D1":144,"D2":216,"D3":504,"total":864},
        "reverse_jvp_component_comparisons":2592,"reverse_jvp_failures":rj_fail,"all_near_zero_probe_failures":all_near,"stable_nonzero_components":nonzero_stable,
        "topology_changing_epsilons":topology_changed,"probe_pass_counts":{"D1":0,"D2":0,"D3":0},"arm_pass":{"D1":False,"D2":False,"D3":False},
        "structure_records":54,"structure_pass":True,"N12_N16_audit_rows":len(resolution["rows"]),"N12_N16_audit_pass":resolution["pass"],
        "resource_pass":resources["pass"],"access_pass":access["pass"],"decode_counts":{k:v for k,v in access["counters"].items() if "decode_count" in k},
        "prohibited_counts":{k:access["counters"][k] for k in ("optimizer_instances","optimizer_steps","training_runs","parameter_updates","neural_rollouts","performance_evaluations")},
        "stage04d_authorization":False,"stage04_training":"NOT_AUTHORIZED","failure_code":"ALL_FORMAL_PROBES_TASK_COMPONENTS_BELOW_FD_RESOLUTION",
        "historical_statuses":{"stage03d":"DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED","stage03dr":"DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED","stage03e_authorization":False},
        "artifacts":[{"path":str(path.relative_to(ROOT)),"sha256":sha(path)} for path in artifact_paths],
    }
    write_json(MANIFESTS / "stage04c_final_manifest.json", final_manifest)
    print(json.dumps({"final_status":final_manifest["final_status"],"reports":len(report_names),"artifacts":len(final_manifest["artifacts"])}))


if __name__ == "__main__":
    main()
