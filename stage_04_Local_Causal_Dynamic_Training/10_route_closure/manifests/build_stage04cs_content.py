"""Build non-computational Stage 04C-S closure content and project delta."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE=Path(__file__).resolve(); CLOSURE=HERE.parents[1]; STAGE04=HERE.parents[2]; ROOT=HERE.parents[3]
REPORTS=STAGE04/"08_reports"; MANIFESTS=STAGE04/"09_manifests"; DELTA=ROOT/"project_wide_synthesis/11_stage04_update_interface/stage04_completed_delta"


def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def sha(path:Path)->str: return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path:Path,value:Any)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
def write(path:Path,text:str)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text.rstrip()+"\n",encoding="utf-8")
def table(headers:list[str],rows:list[list[Any]])->str: return "\n".join(["| "+" | ".join(headers)+" |","|"+"|".join(["---"]*len(headers))+"|"]+["| "+" | ".join(str(v) for v in r)+" |" for r in rows])


def main()->None:
    freeze=load(MANIFESTS/"stage04cs_input_freeze_manifest.json")
    s04a=MANIFESTS/"stage04a_final_manifest.json"; s04av=STAGE04/"00_stage04a_verification/manifests/stage04a_target_verification_manifest.json"; s04b=MANIFESTS/"stage04b_final_manifest.json"; s04c=MANIFESTS/"stage04c_final_manifest.json"; s04cr=MANIFESTS/"stage04cr_final_manifest.json"
    ledger_rows=[
        {"order":1,"stage":"Stage 04A","exact_status":"LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_COMPLETE","research_question":"能否建立不继承 Stage 03 多步梯度歧义的 K=1 local-causal 动态训练假设？","execution_scope":"合同、训练定义、backend、数据与模型臂边界；非执行。","principal_PASS":"K=1 完整 RK2、optimizer-variable 梯度对象、component-vector loss 与 math-SDPA 边界冻结。","principal_blocker":"尚无新 reference pool 与 task-gradient 资格。","optimizer_instances":0,"optimizer_steps":0,"training_runs":0,"validation_decode":0,"sealed_decode":0,"downstream_authorization":"Stage 04A Verification；通过后可进入 Stage 04B。","claim_boundary":"合同完整不等于可训练性或性能成立。","artifact":"stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04a_final_manifest.json","artifact_sha256":sha(s04a),"superseded":False},
        {"order":2,"stage":"Stage 04A Verification","exact_status":"STAGE04A_TARGET_VERIFIED","research_question":"Stage 04A 的目标、梯度、数据与模型边界是否内部一致？","execution_scope":"只读合同验证。","principal_PASS":"训练目标与 optimizer-variable 梯度边界通过验证。","principal_blocker":"未生成 reference trajectories 或梯度证据。","optimizer_instances":0,"optimizer_steps":0,"training_runs":0,"validation_decode":0,"sealed_decode":0,"downstream_authorization":"Stage 04B reference-family pool。","claim_boundary":"target verified 不等于 reference 或训练资格。","artifact":"stage_04_Local_Causal_Dynamic_Training/00_stage04a_verification/manifests/stage04a_target_verification_manifest.json","artifact_sha256":sha(s04av),"superseded":False},
        {"order":3,"stage":"Stage 04B","exact_status":"LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED","research_question":"能否构建角色预分配、可封存、局部因果的动态 reference family pool？","execution_scope":"10 formula lineages；analytic、exact trajectory、DOP853、topology 与 seal 资格。","principal_PASS":"20/20 analytic；60/60 trajectories；20/20 DOP853；10/10 fixed topology；6/2/2 split；leakage=0。","principal_blocker":"reference pool PASS 不证明参数 task-gradient 可辨识。","optimizer_instances":0,"optimizer_steps":0,"training_runs":0,"validation_decode":0,"sealed_decode":0,"downstream_authorization":"Stage 04C task-aligned gradient qualification。","claim_boundary":"只支持 reference-family pool 与 seal，不支持模型训练/性能。","artifact":"stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_final_manifest.json","artifact_sha256":sha(s04b),"superseded":False},
        {"order":4,"stage":"Stage 04C","exact_status":"TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED","research_question":"K=1 task-aligned 三分量 loss 对全部 optimizer parameter groups 的方向梯度是否可检测且 AD/FD 一致？","execution_scope":"D1/D2/D3；72 contexts/arm；864 probes；reverse/JVP/central FD；结构、访问与资源门。","principal_PASS":"2592/2592 reverse/JVP；17280 FD paths；topology change=0；structure/resources/access PASS。","principal_blocker":"2592 near-zero components；864/864 all-near-zero probe failures；0 parameter groups qualified。","optimizer_instances":0,"optimizer_steps":0,"training_runs":0,"validation_decode":0,"sealed_decode":0,"downstream_authorization":"仅 Stage 04C-R failure attribution；Stage 04D=false。","claim_boundary":"不得写成 model/Transformer untrainable。","artifact":"stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04c_final_manifest.json","artifact_sha256":sha(s04c),"superseded":False},
        {"order":5,"stage":"Stage 04C-R","exact_status":"TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED","research_question":"全近零 task-loss 方向梯度由 residual、state Jacobian、方向投影、网络 dead zone 或 RK2 时间尺度中的哪一项主导？","execution_scope":"864-row 重建；full gradients；exact factorization；network chain；RK2 attenuation；linear probes。","principal_PASS":"full gradients 可检测；network outputs/Jacobians 非零；2592/2592 factorization PASS；dead/task-resolved/RK2-defect 被排除。","principal_blocker":"residual factor 50.8%；projection 25.9%；604 rows（23.3%）未解析；无单因达到 80%。","optimizer_instances":0,"optimizer_steps":0,"training_runs":0,"validation_decode":0,"sealed_decode":0,"downstream_authorization":"Stage 04C-S route closure only；Stage 04D=false。","claim_boundary":"归因不覆盖 Stage 04C failure，不授权改 loss/阈值或训练。","artifact":"stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cr_final_manifest.json","artifact_sha256":sha(s04cr),"superseded":False},
    ]
    ledger={"schema":"sph-pio-poc.stage04cs.status-ledger.v1","chronology":[r["stage"] for r in ledger_rows],"non_override_rule":"Later stages extend evidence and never overwrite earlier verdicts; Stage04C-R does not supersede Stage04C.","rows":ledger_rows,"stage04d_authorization":False,"training":"NOT_AUTHORIZED / NOT_EXECUTED","pass":True}
    write_json(CLOSURE/"status_ledger/stage04_status_ledger.json",ledger); write_json(MANIFESTS/"stage04cs_status_ledger.json",ledger)

    evidence_rows=[
        {"category":"Training hypothesis","evidence":"K=1 local-causal formulation","status":"PASS","boundary":"Contract definition only."},
        {"category":"Training hypothesis","evidence":"Complete start/midpoint/accept RK2 transition","status":"PASS","boundary":"No rollout or optimizer execution."},
        {"category":"Training hypothesis","evidence":"Optimizer-variable gradient boundary","status":"PASS","boundary":"Input-gradient evidence remains diagnostic."},
        {"category":"Training hypothesis","evidence":"CPU float64 + explicit math SDPA","status":"PASS","boundary":"No MPS formal evidence."},
        {"category":"Reference family pool","evidence":"10 formula lineages; 20/20 analytic; 60/60 trajectories","status":"PASS","boundary":"TRAIN/VALIDATION/SEALED roles frozen before outcomes."},
        {"category":"Reference family pool","evidence":"20/20 DOP853; 10/10 fixed topology","status":"PASS","boundary":"Reference evidence, not model performance."},
        {"category":"Reference family pool","evidence":"6/2/2 split; leakage=0; sealed formula/state/target decode=0/0/0","status":"PASS","boundary":"Private payload remains unopened."},
        {"category":"Task-gradient qualification","evidence":"864 probes; 2592/2592 reverse/JVP; 17280 FD paths","status":"PASS","boundary":"Implementation consistency only."},
        {"category":"Task-gradient qualification","evidence":"2592 near-zero components; 864 all-near-zero failures","status":"NOT_QUALIFIED","boundary":"At least one nonzero stable component per probe was required."},
        {"category":"Task-gradient qualification","evidence":"Parameter groups qualified","status":"NOT_QUALIFIED","value":"0","boundary":"D1/D2/D3 all remain required baselines."},
        {"category":"Attribution","evidence":"Full gradients and nonzero coefficient/force/acceleration sensitivity","status":"DIAGNOSTIC","boundary":"Rejects dead-network explanation; does not qualify Stage04C."},
        {"category":"Attribution","evidence":"Exact residual-Jacobian factorization","status":"PASS","boundary":"2592/2592 reconstructed derivatives."},
        {"category":"Attribution","evidence":"MSE residual factor 50.8%; direction projection 25.9%; RK2 dt/dt² attenuation","status":"DIAGNOSTIC","boundary":"Contributions are partial and component dependent."},
        {"category":"Attribution","evidence":"604 unresolved rows; mixed/unresolved verdict","status":"UNRESOLVED","boundary":"No unique next correction branch."},
        {"category":"Route","evidence":"Stage 04D","status":"NOT_AUTHORIZED","boundary":"Training protocol preregistration may not begin."},
        {"category":"Route","evidence":"Training / rollout / performance","status":"NOT_EXECUTED","boundary":"No claims permitted."},
    ]
    evidence={"schema":"sph-pio-poc.stage04cs.evidence-matrix.v1","allowed_statuses":["PASS","DIAGNOSTIC","NOT_QUALIFIED","UNRESOLVED","NOT_AUTHORIZED","NOT_EXECUTED"],"rows":evidence_rows,"complete":True}
    write_json(CLOSURE/"evidence_matrix/stage04_evidence_matrix.json",evidence); write_json(MANIFESTS/"stage04cs_evidence_matrix.json",evidence)

    boundary={"excluded":["dead network","zero head","tanh saturation","hidden collapse","Autograd contradiction","parameter mutation","topology change","data leakage","task fully resolved","RK2 implementation defect"],"observed":[{"finding":"position gradients extremely small","scope":"all arms/groups"},{"finding":"velocity gradients usually nonzero","scope":"component-dependent"},{"finding":"density gradients near detection boundary","scope":"mixed across groups"},{"finding":"MSE residual factor primary","share":0.508},{"finding":"group-direction projection primary","share":0.259},{"finding":"unresolved rows","count":604,"share":0.233},{"finding":"dt/dt² attenuation matches contracted RK2","scope":"V≈dt·A; X≈0.5dt²·A"}],"forbidden_phrasing":["Transformer cannot be trained","The model is untrainable"],"permitted_phrasing":"The preregistered K=1 task-aligned gradient qualification did not establish sufficiently detectable nonzero task-loss sensitivities across all required parameter groups.","stage04c_preserved":True}
    write_json(CLOSURE/"failure_boundary/stage04_task_signal_failure_boundary.json",boundary)

    innovations=[
        "Formula-lineage-level dynamic training pool","Role assignment before scientific outcomes","Sealed formula/state/target triple zero-decode",
        "Task-aligned optimizer-variable gradient boundary","Component-vector loss qualification","Complete actual parameter-group mapping",
        "Reverse/JVP/FD 864-probe system","Full-gradient versus random-direction projection separation","Exact residual-Jacobian loss factorization",
        "Hidden-to-coefficient-to-force-to-acceleration-to-RK2-state sensitivity chain","Separation of genuine RK2 signal attenuation from implementation defects","Transparent mixed/unresolved negative evidence",
    ]
    innovation={"schema":"sph-pio-poc.stage04cs.innovation-register.v1","novelty_label":"POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION","rows":[{"id":i+1,"innovation":v,"status":"POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION"} for i,v in enumerate(innovations)],"literature_verification_performed":False}
    write_json(CLOSURE/"innovation_register/stage04_innovation_register.json",innovation)

    claims={"SUPPORTED":["Stage04B reference-family pool qualified","lineage leakage is zero","sealed decode is zero","reverse/JVP implementation is consistent","dynamic model outputs and Jacobians are nonzero","the K=1 task-gradient contract was not qualified","no training was executed"],"CONDITIONAL":["MSE residual scale contributes substantially","random direction projection contributes partially","RK2 time scaling attenuates the accepted-state signal","the velocity state-Jacobian path is detectable"],"UNSUPPORTED":["the model is untrainable","the Transformer fails","loss scaling will solve the problem","full-gradient training will succeed","D3 is superior","rollout improves SPH","Stage01 V2 is restored"]}
    write_json(CLOSURE/"claim_boundary/stage04_claim_boundary.json",claims)

    publication={"decision_finalized":False,"options":[
        {"option":"A","definition":"Stage00–04 single integrated solver paper","current_support":"NOT_SUPPORTED","mainline_coherence":"Low under current evidence","length":"Very high","innovation":"Broad but incomplete","generality":"Limited by missing training/rollout","CMAME_readiness":"Not ready","realistic_tier":"Not assessable before training evidence","reason":"No training, rollout or performance evidence."},
        {"option":"B","definition":"Stage00–03 verification-first paper + independent Stage04 training paper","current_support":"PARTIAL","mainline_coherence":"Strong for Stage00–03; incomplete for Stage04","length":"Manageable if split","innovation":"Stage04 negative evidence is methodological","generality":"Requires broader confirmation for standalone methods paper","CMAME_readiness":"Stage04 training paper not ready","realistic_tier":"Methodology/verification venue after generalization","reason":"Stage04 cannot yet support a training paper; negative task-gradient evidence may join the methods paper or later generalize."},
        {"option":"C","definition":"Stage00–04 verification-first negative-evidence methods paper","current_support":"PROMISING_BUT_NOT_SELECTED","mainline_coherence":"High: preregistration, failure preservation, attribution","length":"High but controllable","innovation":"Strong methodological transparency","generality":"Needs literature verification and cross-case framing","CMAME_readiness":"Potentially closer than A/B, not yet established","realistic_tier":"Verification/computational-methods journal; exact tier deferred","reason":"Best current narrative coherence, but no final submission decision is authorized."},
    ],"selection":"DEFERRED"}
    write_json(CLOSURE/"publication_delta/publication_option_update.json",publication)

    # Versioned project-wide import package; no existing synthesis artifact is rewritten.
    status_delta={"schema":"project-wide.stage04-status-delta.v1","source_stage":"Stage04C-S","ledger":ledger,"terminal_route_status":"STAGE04_ROUTE_PAUSED_TASK_SIGNAL_BOUNDARY_COMPLETE"}
    failure_delta={"schema":"project-wide.stage04-failure-delta.v1","boundary":boundary,"primary_status":"TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED","training_route":"PAUSED"}
    innovation_delta={"schema":"project-wide.stage04-innovation-delta.v1","register":innovation}
    evidence_delta={"schema":"project-wide.stage04-evidence-delta.v1","matrix":evidence}
    claim_delta={"schema":"project-wide.stage04-claim-delta.v1","claims":claims}
    for name,value in (("stage04_status_delta.json",status_delta),("stage04_failure_delta.json",failure_delta),("stage04_innovation_delta.json",innovation_delta),("stage04_evidence_delta.json",evidence_delta),("stage04_claim_delta.json",claim_delta)): write_json(DELTA/name,value)
    pub_md=f"""# Stage 04 Publication Delta

This versioned package adds Stage 04 evidence without rewriting the Stage 00–03 synthesis.

{table(['Option','Current support','CMAME readiness','Boundary'],[[x['option'],x['current_support'],x['CMAME_readiness'],x['reason']] for x in publication['options']])}

No final merge/split decision is made. Option A is not supported; Option B lacks a viable Stage 04 training paper; Option C is methodologically coherent but requires literature verification and broader framing.
"""
    write(DELTA/"stage04_publication_delta.md",pub_md)
    delta_files=[DELTA/n for n in ("stage04_status_delta.json","stage04_failure_delta.json","stage04_innovation_delta.json","stage04_evidence_delta.json","stage04_claim_delta.json","stage04_publication_delta.md")]
    delta_manifest={"schema":"project-wide.stage04-delta-manifest.v1","version":"stage04_completed_delta","existing_stage00_03_artifacts_rewritten":False,"files":[{"path":str(p.relative_to(ROOT)),"sha256":sha(p)} for p in delta_files],"complete":True}
    write_json(DELTA/"stage04_delta_manifest.json",delta_manifest)

    # Human-readable reports (final report is completed after DOCX QA).
    write(REPORTS/"stage04cs_freeze_and_scope.md",f"# Stage 04C-S Freeze and Scope\n\nNon-computational closure. {freeze['historical_file_count']} readable historical files were frozen with zero missing/hash/status conflicts; {freeze['protected_private_file_count']} protected validation/sealed files remained unread, with identity preserved by three Stage04B manifests. Stage04A–04C-R verdicts are unchanged; Stage04D=false; training/rollout/performance are not authorized or executed.\n")
    write(REPORTS/"stage04cs_status_ledger.md","# Stage 04C-S Status Ledger\n\n"+table(["Stage","Exact status","Principal PASS","Principal blocker","Downstream"],[[r["stage"],r["exact_status"],r["principal_PASS"],r["principal_blocker"],r["downstream_authorization"]] for r in ledger_rows])+"\n\nAll rows have `superseded=false`; Stage04C-R does not overwrite Stage04C.\n")
    write(REPORTS/"stage04cs_evidence_matrix.md","# Stage 04C-S Evidence Matrix\n\n"+table(["Category","Evidence","Status","Boundary"],[[r["category"],r["evidence"],r["status"],r["boundary"]] for r in evidence_rows]))
    write(REPORTS/"stage04cs_task_signal_failure_boundary.md",f"# Stage 04C-S Task-Signal Failure Boundary\n\nExcluded: {', '.join(boundary['excluded'])}.\n\nObserved: MSE residual factor 50.8%, group-direction projection 25.9%, unresolved 23.3%; dt/dt² attenuation matches RK2.\n\nPermitted wording: **{boundary['permitted_phrasing']}**\n")
    write(REPORTS/"stage04cs_innovation_register.md","# Stage 04C-S Innovation Register\n\n"+"\n".join(f"{r['id']}. {r['innovation']} — `{r['status']}`" for r in innovation['rows']))
    write(REPORTS/"stage04cs_claim_boundary.md","# Stage 04C-S Claim Boundary\n\n"+"\n\n".join("## "+k+"\n\n"+"\n".join("- "+x for x in v) for k,v in claims.items()))
    write(REPORTS/"stage04cs_publication_implications.md","# Stage 04C-S Publication Implications\n\n"+table(["Option","Support","Coherence","Readiness","Reason"],[[x["option"],x["current_support"],x["mainline_coherence"],x["CMAME_readiness"],x["reason"]] for x in publication["options"]])+"\n\nNo final submission or merge/split decision is made.\n")
    write(REPORTS/"stage04cs_project_wide_delta.md",f"# Stage 04C-S Project-Wide Delta\n\nA versioned import package was created at `{DELTA.relative_to(ROOT)}`. It contains status, failure, innovation, evidence, claim and publication deltas plus a manifest. Existing Stage00–03 synthesis artifacts were not rewritten.\n")
    write_json(CLOSURE/"manifests/content_build_index.json",{"ledger_rows":len(ledger_rows),"evidence_rows":len(evidence_rows),"innovations":len(innovations),"claims":sum(len(v) for v in claims.values()),"project_delta_files":7,"complete":True})
    print(json.dumps({"ledger":len(ledger_rows),"evidence":len(evidence_rows),"innovations":len(innovations),"delta":str(DELTA.relative_to(ROOT))}))


if __name__=="__main__": main()
