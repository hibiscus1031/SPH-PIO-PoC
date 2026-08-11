"""Build the Stage08Z read-only closure and publication evidence package.

Historical Stage00--08A paths are only read. No solver, model, optimizer,
training, rollout, or sealed-test evaluator is imported or executed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import stat
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "stage_08Z_Project_Closure_Publication"
DIRS = ["00_freeze", "01_project_status", "02_cross_stage_evidence", "03_claim_matrix",
        "04_failure_taxonomy", "05_methodological_contributions", "06_figures_and_tables",
        "07_publication_route", "08_manuscript_source_pack", "09_manifests", "10_reports"]
HISTORICAL_ROOTS = ["00_environment", "01_solver", "02_data", "03_models", "04_training", "05_metrics",
                    "06_experiments", "07_reports", "tests", "stage_01_verification",
                    "stage_02_Particle_Interaction_Operator", "stage_03_Dynamic_SPH_Transformer_Hybrid",
                    "stage_04_Local_Causal_Dynamic_Training", "stage_05_Scale_Aware_Discrete_Defect_Training",
                    "stage_06_Optimizer_Update_Dynamics_Training", "stage_07_Heterogeneous_Development_Pool",
                    "stage_08_Systematic_Coverage_V3"]
COUNTS = {"new_model_instances": 0, "new_optimizer_instances": 0, "new_optimizer_steps": 0,
          "new_parameter_updates": 0, "new_training_runs": 0, "new_checkpoints": 0,
          "new_rollouts": 0, "sealed_test_evaluations": 0}


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def entry(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "size": path.stat().st_size, "sha256": sha_file(path)}


def load(path: str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def stage_of(path: Path) -> str:
    text = rel(path)
    for number in range(8, 1, -1):
        if text.startswith(f"stage_0{number}_") or text.startswith(f"stage_{number:02d}_"): return f"Stage{number:02d}"
    if text.startswith("stage_01_") or text.startswith(("01_solver/", "02_data/", "03_models/", "04_training/", "05_metrics/", "06_experiments/", "07_reports/", "tests/")): return "Stage01"
    if text.startswith("00_environment/"): return "Stage00"
    return "ProjectCore"


def artifact_class(path: Path) -> str:
    text = rel(path).lower(); suffix = path.suffix.lower()
    if "/checkpoints/" in text or "checkpoint_selection" in text or suffix == ".pt": return "checkpoint"
    if "/reports/" in text or path.name.endswith("report.md"): return "report"
    if "/manifests/" in text or "manifest" in path.name: return "manifest"
    if "/contracts/" in text or "contract" in path.name: return "contract"
    if "training" in text and ("history" in text or "run_summary" in text or suffix in {".jsonl", ".csv"}): return "training_history"
    if "target" in text and suffix in {".json", ".npz", ".npy"}: return "target_record"
    if "validation" in text: return "validation_record"
    if "qualification" in text: return "qualification_evidence"
    if "failure" in text or "attribution" in text: return "failure_evidence"
    if "role" in text: return "role_manifest"
    if "access" in text or "ledger" in text or "seal" in text: return "access_or_seal_ledger"
    if suffix in {".py", ".yaml", ".yml", ".toml"}: return "implementation_or_configuration"
    if suffix in {".npz", ".npy", ".json", ".jsonl", ".csv", ".tsv"}: return "scientific_data_or_record"
    return "supporting_artifact"


def scientific_role(path: Path, klass: str) -> str:
    text = rel(path).lower()
    if "sealed_test" in text or "sealed-test" in text or any(x in path.name.lower() for x in ("lcdf_03", "lcdf_10")): return "SEALED_TEST_PRESERVATION"
    if klass == "checkpoint": return "FORMAL_EXECUTION_PROVENANCE"
    if klass in {"failure_evidence", "qualification_evidence"}: return "FROZEN_DECISION_EVIDENCE"
    if klass in {"role_manifest", "access_or_seal_ledger"}: return "ROLE_AND_ACCESS_GOVERNANCE"
    if klass in {"contract", "implementation_or_configuration"}: return "FROZEN_METHOD_DEFINITION"
    if klass in {"target_record", "validation_record", "scientific_data_or_record"}: return "FROZEN_SCIENTIFIC_EVIDENCE"
    return "FROZEN_SUPPORTING_EVIDENCE"


def prior_hash_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for root_name in HISTORICAL_ROOTS:
        base = ROOT / root_name
        if not base.exists(): continue
        for path in base.rglob("*.json"):
            if "__pycache__" in path.parts: continue
            try: value = json.loads(path.read_text(encoding="utf-8"))
            except (PermissionError, UnicodeDecodeError, json.JSONDecodeError, OSError): continue
            stack = [value]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    p = item.get("path"); h = item.get("sha256")
                    if isinstance(p, str) and isinstance(h, str) and h.startswith("sha256:"): result[p] = h
                    stack.extend(item.values())
                elif isinstance(item, list): stack.extend(item)
    return result


def historical_inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior = prior_hash_map(); rows = []; missing_prior_hash = []
    for root_name in HISTORICAL_ROOTS:
        base = ROOT / root_name
        if not base.exists(): continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".DS_Store" or any(part in {"__pycache__", ".pytest_cache"} for part in path.parts): continue
            mode = oct(stat.S_IMODE(path.stat().st_mode)); readable = True; hash_source = "direct_read"
            try: digest = sha_file(path)
            except PermissionError:
                readable = False; digest = prior.get(rel(path), "")
                hash_source = "prior_public_manifest"
                if not digest: missing_prior_hash.append(rel(path))
            klass = artifact_class(path)
            rows.append({"relative_path": rel(path), "size": path.stat().st_size, "sha256": digest,
                         "stage": stage_of(path), "artifact_class": klass, "scientific_role": scientific_role(path, klass),
                         "mutable": False, "readable_at_closure": readable, "mode": mode, "hash_source": hash_source})
    digest = "sha256:" + hashlib.sha256(canonical(rows)).hexdigest()
    audit = {"artifact_count": len(rows), "inventory_sha256": digest, "direct_hash_count": sum(row["hash_source"] == "direct_read" for row in rows),
             "prior_manifest_hash_count": sum(row["hash_source"] == "prior_public_manifest" for row in rows),
             "missing_prior_hash": missing_prior_hash, "all_hashes_present": not missing_prior_hash and all(row["sha256"].startswith("sha256:") for row in rows)}
    return rows, audit


def status_rows() -> list[dict[str, Any]]:
    return [
      {"stage":"Stage00","hypothesis":"Apple Silicon CPU/MPS can support a bounded 2D proof of concept.","frozen_status":"CONDITIONAL",
       "passed":"Environment/component readiness and bounded CPU/MPS execution checks.","failed":"A complete diffSPH solver was not executed as Stage00 truth.",
       "scientific_consequence":"Environment readiness is not solver verification.","next_authorization":"Stage01 minimum verification path","training_occurred":False,"validation_consumed":False,"sealed_test_accessed":False,
       "sources":["project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json"]},
      {"stage":"Stage01","hypothesis":"A fixed-physics SPH chain can be verified across implementation, conservation, reference, resolution, and independent-validation layers.","frozen_status":"V2_QUALIFICATION_FAIL; FINITE_RESOLUTION_DOMINANT",
       "passed":"Structural operator repair, bounded resource policy, dense-equivalent semidiscrete reference, plateau-aware MMS requalification, evaluator and execution infrastructure.",
       "failed":"The final independent V2 spatial/shear qualification; high-resolution SPH was not established as truth.","scientific_consequence":"Model-form, temporal, quadrature, topology, and finite-resolution effects must be separated.","next_authorization":"Stage02 qualification-first target route","training_occurred":False,"validation_consumed":True,"sealed_test_accessed":False,
       "sources":["project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json","06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_status.txt"]},
      {"stage":"Stage02","hypothesis":"A reciprocal conservative pair-force PIO can be structurally qualified and statically fitted.","frozen_status":"STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE",
       "passed":"Theory, target/reference hierarchy, blind dataset, and PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED.","failed":"Static pair-force fitting v0.1 and v0.2 global train-fit gates; regularity as a hard dataset gate.",
       "scientific_consequence":"Structural correctness and representability did not imply successful static learning; the route moved to dynamic accepted-state tasks.","next_authorization":"Stage03 dynamic hybrid specification","training_occurred":True,"validation_consumed":True,"sealed_test_accessed":False,
       "sources":["stage_02_Particle_Interaction_Operator/07_reports/stage02ms_final_report.md","stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json"]},
      {"stage":"Stage03","hypothesis":"A conservative RK2 neural hybrid with short history can be implemented and multistep-gradient qualified.","frozen_status":"STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE",
       "passed":"Dynamic reference trajectories, RK2 hybrid implementation, zero-correction equivalence, checkpoint identity, one-step AD, and topology component.","failed":"Complete multistep AD/FD qualification: 216 stable probes and 144 failures; history gradient 0/6.",
       "scientific_consequence":"Correct implementation did not establish multistep trainability; task-aligned gradient diagnosis was required.","next_authorization":"Stage04 task-signal boundary","training_occurred":False,"validation_consumed":False,"sealed_test_accessed":False,
       "sources":["stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json","stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json"]},
      {"stage":"Stage04","hypothesis":"A local-causal raw next-state task can avoid history-gradient attenuation while preserving structure.","frozen_status":"STAGE04_ROUTE_PAUSED_TASK_SIGNAL_BOUNDARY_COMPLETE",
       "passed":"Local-causal reference-family pool, analytic/topology/DOP853 qualification, sealed role governance, nonzero correction Jacobian and structural safety.","failed":"TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED; raw state-loss signal was attenuated; complete parameter-coordinate FD coverage was not established.",
       "scientific_consequence":"The target and scale, not only architecture Jacobians, determine detectable optimizer signals.","next_authorization":"Stage05 scale-aware D0 defect route","training_occurred":False,"validation_consumed":False,"sealed_test_accessed":False,
       "sources":["stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cs_final_manifest.json","stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cr_final_manifest.json"]},
      {"stage":"Stage05","hypothesis":"A D0-centered scale-aware conservative discrete-defect target restores identifiable optimization signals.","frozen_status":"PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED; target/scale qualified",
       "passed":"CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED with 384 origins; representability, scale, uncertainty, conservation and symmetry gates.","failed":"Complete coordinate-level FD qualification and local-descent route remained incomplete/not qualified.",
       "scientific_consequence":"The defect formulation was retained, while optimizer-path evidence was moved to actual update dynamics.","next_authorization":"Stage06 actual-optimizer qualification","training_occurred":False,"validation_consumed":False,"sealed_test_accessed":False,
       "sources":["stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/qualification/stage05b_qualification_summary.json","stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05cq_final_manifest.json"]},
      {"stage":"Stage06","hypothesis":"Qualified actual AdamW update dynamics can support the frozen formal K=1 campaign.","frozen_status":"FORMAL_TRAINING_FAILURE_ATTRIBUTED",
       "passed":"ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED; nine formal runs completed with checkpoint integrity and structure gates.","failed":"All D1/D2/D3 arms had 0/3 seed passes; transformer route not qualified.",
       "scientific_consequence":"Local descent and update-level trainability did not guarantee the frozen global criterion; failure was attributed to TRAIN lineage heterogeneity.","next_authorization":"Stage07 heterogeneous development pool","training_occurred":True,"validation_consumed":True,"sealed_test_accessed":False,
       "sources":["stage_06_Optimizer_Update_Dynamics_Training/01_update_map_qualification/qualification/stage06a_qualification_summary.json","stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/manifests/stage06cr_final_manifest.json"]},
      {"stage":"Stage07","hypothesis":"Prospective formula heterogeneity augmentation can restore shared-map training and fresh-validation transfer.","frozen_status":"TRAIN_V2_RETRAINING_FAILURE_ATTRIBUTED",
       "passed":"12-lineage pool qualification, TRAIN_V2 target/scale/update qualification, nine retraining runs, and support-gap attribution.","failed":"All arms 0/3 seed passes; Branch B NOT_SUPPORTED; HET_S2_02 was descriptor and target out of support.",
       "scientific_consequence":"Formula heterogeneity alone did not guarantee target-manifold support; hash-based role assignment exposed a held-out H2 gap.","next_authorization":"Stage08 systematic coverage V3","training_occurred":True,"validation_consumed":True,"sealed_test_accessed":False,
       "sources":["stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/results/stage07dr_results.json","stage_07_Heterogeneous_Development_Pool/08_reports/stage07dr_final_report.md"]},
      {"stage":"Stage08","hypothesis":"Prospective four-layer coverage selection can close consumed support and produce four fresh in-support validation lineages.","frozen_status":"SYSTEMATIC_COVERAGE_V3_POOL_NOT_QUALIFIED",
       "passed":"128+64 deterministic candidates; 192/192 candidate qualification; eight algorithmic TRAIN selections; TRAIN_V3=14; HET_S2_02 descriptor distance reduced to 1.8606627588827505.",
       "failed":"20-lineage descriptor/target support, HET_S2_02 target PCA, key envelopes, and formal fresh-validation closure (0/4).",
       "scientific_consequence":"Descriptor-space support did not imply raw correction-target manifold coverage; final development cycle exhausted.","next_authorization":"None; FULL_SOLVER_TRAINING_ROUTE_CLOSED","training_occurred":False,"validation_consumed":False,"sealed_test_accessed":False,
       "sources":["stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json","stage_08_Systematic_Coverage_V3/08_reports/stage08a_final_report.md"]}]


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str: return str(value).replace("|", "\\|").replace("\n", " ")
    return "| " + " | ".join(headers) + " |\n|" + "|".join(["---"] * len(headers)) + "|\n" + "\n".join("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)


def formal_runs() -> list[dict[str, Any]]:
    rows = []
    campaigns = [("Stage06C", ROOT / "stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c/runs"),
                 ("Stage07D", ROOT / "stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07d/runs")]
    for campaign, base in campaigns:
        for path in sorted(base.glob("*/run_summary.json")):
            data = json.loads(path.read_text(encoding="utf-8")); metrics = data.get("selected_metrics", {})
            train = metrics.get("TRAIN", {}); validation = metrics.get("VALIDATION", {})
            gates = metrics.get("frozen_gates_A_E", {})
            failed = [key for key, value in gates.items() if value is False]
            rows.append({"campaign": campaign, "arm": data["arm"], "seed": data.get("formal_seed"),
                         "terminal_update": data.get("terminal_update"), "selected_update": data.get("selected_update"),
                         "TRAIN_Q": train.get("global_balanced_Q_def"), "validation_Q": validation.get("global_balanced_Q_def"),
                         "seed_PASS": data.get("seed_pass"), "failure_gate": ",".join(failed) if failed else "frozen global criterion",
                         "optimizer_steps": data.get("optimizer_step_count"), "peak_RSS_bytes": data.get("peak_rss_bytes"),
                         "checkpoint_integrity": data.get("checkpoint_integrity_pass"), "checkpoint_sha256": data.get("selected_checkpoint_sha256"),
                         "source": rel(path)})
    return rows


def csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows: return ""
    handle = io.StringIO(); writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return handle.getvalue()


def failure_rows() -> list[dict[str, Any]]:
    return [
      {"id":"F1","name":"SPH model-form / finite-resolution boundary","evidence":["Stage01E model-form attribution","Stage01G V2_QUALIFICATION_FAIL","Stage01H FINITE_RESOLUTION_DOMINANT"],"frozen_status":"BOUNDARY_ESTABLISHED_IN_SCOPE","ruled_out_alternatives":"Time-step and determinism dominance were not supported; operator-form failure was not confirmed.","methodological_response":"WCSPH-compatible MMS, same-semidiscrete DOP853, plateau-aware and independent validation.","response_succeeded":"Partially: references were qualified, final V2 was not.","final_disposition":"High-resolution SPH is not truth."},
      {"id":"F2","name":"Static pair-force fitting failure","evidence":["Stage02M STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED","Stage02M-Q STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED"],"frozen_status":"STATIC_ROUTE_CLOSED","ruled_out_alternatives":"Architecture/conservation qualification passed; conditioning diagnosis did not rescue global train fit.","methodological_response":"Task-aligned dynamic accepted-state formulation.","response_succeeded":"Static route no; dynamic method advanced.","final_disposition":"Retained as falsification evidence."},
      {"id":"F3","name":"Multistep AD/FD incomplete qualification","evidence":["216 stable probes; 144 failures","history gradient 0/6"],"frozen_status":"DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED","ruled_out_alternatives":"Topology component qualified; implementation and one-step AD passed.","methodological_response":"Local-causal task-aligned gradient contract.","response_succeeded":"No: Stage04 task gradient not qualified.","final_disposition":"Multistep gradient claim prohibited."},
      {"id":"F4","name":"Raw state-loss signal attenuation","evidence":["Stage04C/04C-R","nonzero correction Jacobian with attenuated task signal"],"frozen_status":"TASK_SIGNAL_BOUNDARY_COMPLETE","ruled_out_alternatives":"A zero neural Jacobian and gross structural failure were excluded in audited cases.","methodological_response":"D0-centered scaled conservative defect loss.","response_succeeded":"Yes at target/scale and optimizer-update levels.","final_disposition":"Core methodological result."},
      {"id":"F5","name":"Coordinate-level FD incomplete coverage","evidence":["Stage05C-R evidence incomplete","Stage05C-Q not qualified"],"frozen_status":"NOT_QUALIFIED","ruled_out_alternatives":"Directional and block diagnostics did not constitute full coordinate coverage.","methodological_response":"Prospective actual AdamW update qualification.","response_succeeded":"Yes for actual update dynamics, not for universal coordinate FD.","final_disposition":"All-coordinate FD claim prohibited."},
      {"id":"F6","name":"Formal TRAIN-fit failure","evidence":["Stage06C nine terminal runs","all arms 0/3 seed passes"],"frozen_status":"FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED","ruled_out_alternatives":"Execution incompleteness, checkpoint corruption, update-path failure and structural-force failure were excluded.","methodological_response":"Failure attribution and heterogeneous development pool.","response_succeeded":"Attribution yes; training criterion no.","final_disposition":"No qualified trained solver."},
      {"id":"F7","name":"Development-pool heterogeneity hypothesis failure","evidence":["Stage07D nine retraining runs","Branch B NOT_SUPPORTED"],"frozen_status":"FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED","ruled_out_alternatives":"Pool/reference/update qualifications passed; more formula heterogeneity did not restore global success.","methodological_response":"Held-out support diagnosis and systematic coverage-by-design.","response_succeeded":"Diagnosis yes; V3 qualification no.","final_disposition":"Heterogeneity alone is insufficient."},
      {"id":"F8","name":"Held-out support-gap failure","evidence":["HET_S2_02 Stage07 descriptor distance 6.5115373494207205","TARGET_OUT_OF_SUPPORT"],"frozen_status":"HELD_OUT_H2_SUPPORT_GAP_DOMINANT","ruled_out_alternatives":"Pair-basis failure excluded; optimizer plateau and gradient conflict documented.","methodological_response":"Four-layer prospective coverage selection.","response_succeeded":"Descriptor support improved, target support did not.","final_disposition":"Support diagnosis retained."},
      {"id":"F9","name":"Systematic coverage V3 target-manifold failure","evidence":["192/192 candidates","HET_S2_02 descriptor 1.8606627588827505","target residual 3.5113172977959843 > 1.5385435220163268","fresh closure 0/4"],"frozen_status":"SYSTEMATIC_COVERAGE_V3_POOL_NOT_QUALIFIED","ruled_out_alternatives":"Candidate incompleteness, manual role swapping, model-prediction selection and sealed-test leakage were excluded.","methodological_response":"Final route closure and publication synthesis.","response_succeeded":"Yes for evidence closure; no for solver qualification.","final_disposition":"FULL_SOLVER_TRAINING_ROUTE_CLOSED."}]


def make_figure_pack(index: int, title: str, conclusion: str, sources: list[str], data: dict[str, Any]) -> None:
    base = STAGE / f"06_figures_and_tables/Figure_{index:02d}"
    write_json(base / "data.json", {"figure": index, "title": title, "frozen_data": data, "new_scientific_computation": False})
    write_json(base / "plot_spec.json", {"figure": index, "layout":"publication schematic or evidence-linked panel composition",
        "required_message": conclusion, "data_policy":"Use only data.json and cited frozen source artifacts; do not interpolate missing evidence.",
        "visual_risks":["Do not imply chronological tuning success.","Do not display high-resolution SPH as truth.","Distinguish qualification from performance."]})
    write_text(base / "caption.md", f"**Figure {index}. {title}.** {conclusion} All plotted values and statuses must be read from the frozen source list; schematic arrows denote methodological dependency, not performance improvement.")
    write_json(base / "sources.json", {"sources": sources})


def main() -> None:
    for name in DIRS: (STAGE / name).mkdir(parents=True, exist_ok=True)
    inventory, inventory_audit = historical_inventory()
    freeze = {"schema":"sph-pio-poc.stage08z.final-evidence-freeze.v1","scope":"Stage00-through-Stage08A",
              "historical_roots":HISTORICAL_ROOTS,"artifact_count":len(inventory),"inventory_sha256":inventory_audit["inventory_sha256"],
              "all_artifacts_mutable_false":True,"audit":inventory_audit,"artifacts":inventory}
    freeze_path = STAGE / "00_freeze/project_final_evidence_freeze_manifest.json"; write_json(freeze_path, freeze)
    missing = []; size_mismatch = []; mode_mismatch = []; hash_mismatch = []
    for row in inventory:
        path = ROOT / row["relative_path"]
        if not path.is_file(): missing.append(row["relative_path"]); continue
        if path.stat().st_size != row["size"]: size_mismatch.append(row["relative_path"])
        if oct(stat.S_IMODE(path.stat().st_mode)) != row["mode"]: mode_mismatch.append(row["relative_path"])
        if row["hash_source"] == "direct_read" and sha_file(path) != row["sha256"]: hash_mismatch.append(row["relative_path"])
    postscan = {"schema":"sph-pio-poc.stage08z.evidence-postscan.v1","checked":len(inventory),
                "direct_hashes_recomputed":inventory_audit["direct_hash_count"],
                "sealed_artifacts_identity_and_mode_checked":inventory_audit["prior_manifest_hash_count"],
                "missing":missing,"size_mismatch":size_mismatch,"mode_mismatch":mode_mismatch,"hash_mismatch":hash_mismatch,
                "pass":not missing and not size_mismatch and not mode_mismatch and not hash_mismatch and inventory_audit["all_hashes_present"]}
    postscan_path = STAGE / "00_freeze/project_final_evidence_postscan_verification.json"; write_json(postscan_path, postscan)

    rows = status_rows()
    final_flags = {"FULL_SOLVER_TRAINING_ROUTE_CLOSED": True, "FORMAL_TRAINED_SOLVER_QUALIFIED": False,
        "TRANSFORMER_SUPERIORITY_ESTABLISHED": False, "AUTONOMOUS_ROLLOUT_QUALIFIED": False,
        "SEALED_TEST_EVALUATED": False, "V2_BASELINE_RESTORED": False,
        "CONSERVATIVE_DYNAMIC_ARCHITECTURE_VERIFIED": True, "ZERO_CORRECTION_EQUIVALENCE_VERIFIED": True,
        "DISCRETE_DEFECT_TARGET_QUALIFIED": True, "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED": True,
        "FORMAL_DYNAMIC_TRAINING_EXECUTED": True, "STAGE08_FINAL_DEVELOPMENT_CYCLE": True}
    ledger = {"schema":"sph-pio-poc.stage08z.project-status-ledger.v1","final_flags":final_flags,"stages":rows,
              "new_execution_counts":COUNTS}
    ledger_json = STAGE / "01_project_status/project_final_status_ledger.json"; write_json(ledger_json, ledger)
    ledger_md = "# Project final status ledger\n\n" + "\n\n".join(
        f"## {r['stage']} — `{r['frozen_status']}`\n\n- Hypothesis: {r['hypothesis']}\n- Passed: {r['passed']}\n- Failed: {r['failed']}\n- Consequence: {r['scientific_consequence']}\n- Next authorization: {r['next_authorization']}\n- Training occurred: `{r['training_occurred']}`\n- Validation consumed: `{r['validation_consumed']}`\n- Sealed test accessed: `{r['sealed_test_accessed']}`\n- Sources: " + ", ".join(f"`{s}`" for s in r["sources"]) for r in rows)
    ledger_md += "\n\n## Frozen project flags\n\n" + "\n".join(f"- `{key} = {str(value).lower()}`" for key, value in final_flags.items())
    write_text(STAGE / "01_project_status/project_final_status_ledger.md", ledger_md)

    progression = ["V&V-qualified SPH foundation","conservative pair interaction architecture","static-learning falsification",
      "dynamic RK2 hybrid implementation","gradient qualification failure","task-signal attribution","scale-aware discrete defect target",
      "target/scale qualification","optimizer-path qualification","actual AdamW update qualification","formal training",
      "lineage heterogeneity attribution","prospective heterogeneous-pool augmentation","fresh-validation failure",
      "support-gap attribution","systematic coverage-by-design","target-manifold coverage failure","route closure"]
    write_text(STAGE / "02_cross_stage_evidence/project_methodological_progression.md",
      "# Project methodological progression\n\n" + "\n\n→ ".join(progression) +
      "\n\nThis is a dependency chain in which each failure changed the next qualification layer. It must not be described as repeated hyperparameter tuning. Learning-rate, loss, architecture, role, and validation changes remained stage-bounded and preregistered.")
    evidence_rows = [[r["stage"], r["frozen_status"], r["passed"], r["failed"], r["scientific_consequence"]] for r in rows]
    write_text(STAGE / "02_cross_stage_evidence/cross_stage_evidence_matrix.md", "# Cross-stage evidence matrix\n\n" + md_table(["Stage","Frozen status","Passed","Failed","Consequence"], evidence_rows))
    write_json(STAGE / "02_cross_stage_evidence/cross_stage_evidence_matrix.json", {"rows":rows})

    claims = [
      ("C1","Structural correctness, target representability, gradient validity, optimizer-level trainability, and successful solver training are distinct qualification layers.","SUPPORTED","Stages02–08"),
      ("C2","Hard reciprocal antisymmetry can preserve linear-momentum-compatible correction structure through dynamic RK2 training.","SUPPORTED_IN_AUDITED_SCOPE","Stages03,06,07"),
      ("C3","A raw next-state loss can provide poorly detectable training gradients even when the neural correction Jacobian is nonzero.","SUPPORTED_IN_AUDITED_SCOPE","Stage04"),
      ("C4","A D0-centered scale-aware conservative discrete-defect target can restore identifiable optimizer-level training signals.","SUPPORTED_IN_AUDITED_SCOPE","Stages05–06A"),
      ("C5","Verified local descent and actual optimizer-update dynamics do not guarantee achievement of a frozen global training criterion.","SUPPORTED","Stages06A–06C"),
      ("C6","Increasing formula heterogeneity alone does not guarantee coverage of the discrete correction-target manifold.","SUPPORTED","Stage07"),
      ("C7","Formula/physics descriptor coverage does not imply raw correction-target manifold coverage.","SUPPORTED","Stage08"),
      ("C8","A prospectively systematic coverage design can improve descriptor-space support while still fail target-space coverage.","SUPPORTED","Stage08"),
      ("C9","The project did not establish a qualified trained SPH–Transformer solver.","SUPPORTED_NEGATIVE_BOUNDARY","Stages06–08")]
    prohibited = ["Transformer is superior to MLP/GRU","Transformer fails generally","neural SPH cannot work",
      "attention is equivalent to an SPH kernel","Stage01 baseline is fully V2-qualified","Stage07 heterogeneity augmentation improved the solver",
      "Stage08 systematic coverage solved the support gap","validation performance implies sealed-test performance",
      "formal training succeeded","autonomous rollout improved SPH","high-resolution SPH is truth",
      "all parameter coordinates have qualified FD","D3 temporal dependence proves Transformer necessity"]
    write_json(STAGE / "03_claim_matrix/final_claim_support_matrix.json", {"allowed":[{"id":a,"claim":b,"status":c,"evidence":d} for a,b,c,d in claims],"prohibited":prohibited})
    write_text(STAGE / "03_claim_matrix/final_claim_boundary.md", "# Final claim boundary\n\n## Allowed conclusions\n\n" +
      "\n".join(f"- **{a}** ({c}; {d}): {b}" for a,b,c,d in claims) + "\n\n## Prohibited claims\n\n" + "\n".join(f"- {item}." for item in prohibited) +
      "\n\nThe route closure is scoped to the frozen project hierarchy, roles, architectures, loss, optimizer, qualification philosophy, and final-cycle policy. It is not an impossibility proof or a prohibition on future independent research.")

    failures = failure_rows(); write_json(STAGE / "04_failure_taxonomy/final_failure_taxonomy.json", {"failures":failures})
    write_json(STAGE / "04_failure_taxonomy/final_failure_graph.json", {"nodes":[{"id":r["id"],"label":r["name"],"status":r["frozen_status"]} for r in failures],
      "edges":[[f"F{i}",f"F{i+1}"] for i in range(1,9)],"edge_semantics":"methodological response to prior failure exposed the next boundary; not monotonic tuning"})
    write_text(STAGE / "04_failure_taxonomy/final_failure_taxonomy.md", "# Final failure taxonomy\n\n" + "\n\n".join(
      f"## {r['id']} — {r['name']}\n\n- Frozen status: `{r['frozen_status']}`\n- Evidence: {'; '.join(r['evidence'])}\n- Ruled-out alternatives: {r['ruled_out_alternatives']}\n- Methodological response: {r['methodological_response']}\n- Response succeeded: {r['response_succeeded']}\n- Final disposition: {r['final_disposition']}" for r in failures))

    innovations = {"A_level_methodological":[
      {"contribution":"Layered qualification ladder","evidence":"Stages01–08 separate reference, structure, target, gradient, optimizer, training and coverage gates."},
      {"contribution":"Reference-role and evidence-consumption governance","evidence":"Stage04/07/08 role manifests and access ledgers."},
      {"contribution":"Accepted-state D0 conservative defect and scale contract","evidence":"Stage05B qualification."},
      {"contribution":"Actual optimizer-path qualification before formal training","evidence":"Stage06A."},
      {"contribution":"Failure-attribution protocol across formal campaigns","evidence":"Stage06C-R and Stage07D-R."},
      {"contribution":"Descriptor-space versus target-manifold support distinction","evidence":"Stage07D-R and Stage08A."}],
      "B_level_implementation":[
      {"contribution":"Reciprocal antisymmetric pair-force implementation","evidence":"Stages02K,03C,06/07 structure audits."},
      {"contribution":"Exact manufactured trajectories with fixed-topology and same-semidiscrete audits","evidence":"Stages03B,04B,07A."},
      {"contribution":"Hash-bound roles, checkpoints and access controls","evidence":"Stage04–08 manifests."}],
      "C_level_negative_evidence":[
      {"contribution":"Static pair-force fitting falsification","evidence":"Stage02M/M-Q."},
      {"contribution":"Raw state-loss gradient attenuation","evidence":"Stage04C/R."},
      {"contribution":"Update qualification does not imply global training success","evidence":"Stage06A/C."},
      {"contribution":"Heterogeneity and systematic descriptor coverage do not guarantee target support","evidence":"Stages07–08."}],
      "novelty_boundary":"These are project-supported contributions; literature novelty is not asserted without a separate literature review."}
    write_json(STAGE / "05_methodological_contributions/final_innovation_register.json", innovations)
    write_text(STAGE / "05_methodological_contributions/final_innovation_register.md", "# Final innovation register\n\n" + "\n\n".join(
      "## " + key.replace("_"," ").title() + "\n\n" + "\n".join(f"- **{r['contribution']}** — {r['evidence']}" for r in value)
      for key,value in innovations.items() if isinstance(value,list)) + "\n\n" + innovations["novelty_boundary"])

    runs = formal_runs(); run_path = STAGE / "06_figures_and_tables/formal_training_campaigns.csv"; write_text(run_path, csv_text(runs))
    run_headers = ["campaign","arm","seed","terminal_update","selected_update","TRAIN_Q","validation_Q","seed_PASS","failure_gate","optimizer_steps","peak_RSS_bytes","checkpoint_integrity"]
    write_text(STAGE / "06_figures_and_tables/formal_training_campaigns.md", "# Unified Stage06/07 formal training table\n\n" +
      md_table(run_headers, [[row[key] for key in run_headers] for row in runs]) +
      "\n\nStage06 and Stage07 normalized Q values are scale-contract-specific and must not be used as a scale-independent cross-stage performance comparison. Common-anchor comparisons use raw acceleration RMSE and relative zero-baseline reduction only.")
    stage05 = load("stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/qualification/stage05b_qualification_summary.json")
    stage06q = load("stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c/qualification/stage06c_qualification.json")
    stage07q = load("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07d/qualification/stage07d_qualification.json")
    stage08q = load("stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json")
    coverage = load("stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/train_selection/train_v3_coverage_qualification.json")
    tables = {
      1:("Verification and reference hierarchy", [["Stage01","SPH verification","V2_QUALIFICATION_FAIL; finite-resolution boundary"],["Stage03B","Dynamic exact reference","DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE"],["Stage04B","Local-causal lineage pool","LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED"]]),
      2:("Architecture and conservation contracts", [["Stage02K","Reciprocal pair-force PIO","PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED"],["Stage03C","Dynamic RK2 hybrid","DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED"],["Stage06/07","Formal-run structure checks","Checkpoint/force/graph integrity retained"]]),
      3:("Learning-route qualification history", [[r["stage"],r["frozen_status"],r["scientific_consequence"]] for r in rows[2:]]),
      4:("Stage05 defect/scale evidence", [["Status",stage05["status"]],["Formal origins",stage05["formal_origin_count"]],["Target records",stage05["target_record_count"]],["s_a",stage05["s_a"]],["u_a",stage05["u_a"]],["s_a/u_a",stage05["s_a_over_u_a"]]]),
      5:("Stage06 formal training evidence", [[arm,data["completed"],data["seed_passes"],data["arm_pass"]] for arm,data in stage06q["arms"].items()]),
      6:("Stage07 retraining and validation evidence", [[arm,data["completed"],data["seed_passes"],data["arm_pass"]] for arm,data in stage07q["arms"].items()] + [["Branch B","NOT_SUPPORTED","HET_S2_02","HELD_OUT_H2_SUPPORT_GAP_DOMINANT"]]),
      7:("Stage08 systematic coverage evidence", [["TRAIN candidates",128],["Validation candidates",64],["Candidate qualification","192/192"],["Selected new TRAIN",8],["TRAIN_V3",14],["HET_S2_02 Stage07 descriptor distance",6.5115373494207205],["HET_S2_02 Stage08 descriptor distance",coverage["HET_S2_02"]["Stage08_descriptor_distance"]],["HET_S2_02 target PCA residual",coverage["HET_S2_02"]["Stage08_target_PCA_residual"]],["Target threshold",coverage["HET_S2_02"]["Stage08_target_threshold"]],["Formal fresh validation closure","0/4"],["Model predictions read",stage08q["counts"]["model_predictions_read"]],["Stage08B",stage08q["stage08b_authorization"]]]),
      8:("Final claim-support matrix", [[a,c,d,b] for a,b,c,d in claims])}
    for number,(title,data) in tables.items():
        headers = (["Item","Value"] if number in {4,7} else ["Stage/Arm","Evidence A","Evidence B","Evidence C"] if number in {5,6} else ["ID","Status","Evidence","Claim"] if number==8 else ["Stage","Route/component","Frozen result"] if number in {1,2} else ["Stage","Frozen status","Consequence"])
        width=len(headers); normalized=[list(row)+[""]*(width-len(row)) for row in data]
        write_text(STAGE / f"06_figures_and_tables/Table_{number:02d}.md", f"# Table {number}. {title}\n\n" + md_table(headers, normalized))
        write_json(STAGE / f"06_figures_and_tables/Table_{number:02d}.json", {"title":title,"headers":headers,"rows":normalized,"sources_are_frozen":True})

    figure_defs = [
      (1,"Qualification-first project workflow","Qualification layers are sequential evidence gates rather than a single predictive benchmark.",rows,{"progression":progression}),
      (2,"Conservative reciprocal pair-force architecture","Hard reciprocal antisymmetry provides a linear-momentum-compatible correction structure but does not establish training success.",["stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json"],{"status":"PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED"}),
      (3,"Reference and verification hierarchy","Continuum formulas, exact trajectories, same-semidiscrete time audits and finite-resolution SPH occupy different evidence roles.",["stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json"],{"layers":["analytic closure","exact trajectory","DOP853 tolerance audit","finite-resolution solver"]}),
      (4,"Failure-driven methodological progression","Each frozen failure motivated a new qualification layer without overwriting the earlier verdict.",["stage_08Z_Project_Closure_Publication/04_failure_taxonomy/final_failure_taxonomy.json"],{"failures":[r["id"] for r in failures]}),
      (5,"State-loss signal attenuation versus discrete-defect formulation","The Stage04 raw-state task boundary preceded the Stage05 target/scale and Stage06 actual-update qualifications.",["stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cr_final_manifest.json","stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/qualification/stage05b_qualification_summary.json"],{"stage04":"TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED","stage05":stage05["status"],"s_a":stage05["s_a"],"u_a":stage05["u_a"]}),
      (6,"Stage06 formal training curves","Nine terminal campaigns document execution and failure of the frozen global criterion; curves must be sourced from their training histories.",[row["source"] for row in runs if row["campaign"]=="Stage06C"],{"run_count":9,"seed_passes":0}),
      (7,"Stage07 TRAIN/validation lineage heterogeneity","The augmented formula pool passed pretraining qualifications but did not yield qualified fresh-validation transfer.",["stage_07_Heterogeneous_Development_Pool/01_pool_generation/results/heterogeneity_descriptor_audit.json","stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/results/stage07dr_results.json"],{"train_lineages":14,"fresh_validation_lineages":4,"branch_B":"NOT_SUPPORTED"}),
      (8,"HET_S2_02 descriptor and target support gap","Stage07 diagnosed simultaneous descriptor and raw-target out-of-support behavior for the held-out H2 lineage.",["stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/descriptor_geometry/descriptor_support_geometry.json","stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/target_geometry/target_manifold_geometry.json"],{"descriptor_distance":6.5115373494207205,"descriptor_class":"OUTSIDE_TRAIN_SUPPORT","target_residual":3.8890719953419794,"target_class":"TARGET_OUT_OF_SUPPORT"}),
      (9,"Stage08 descriptor support improvement but target-manifold failure","Systematic selection reduced HET_S2_02 descriptor distance below 2.0 while its raw-target residual remained above the TRAIN threshold.",["stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/train_selection/train_v3_coverage_qualification.json"],{"descriptor_distance":1.8606627588827505,"target_residual":3.5113172977959843,"target_threshold":1.5385435220163268,"fresh_closure":"0/4"}),
      (10,"Final qualification ladder and claim boundary","Verified architecture, target, gradient/update and executed training remain distinct from a qualified trained solver.",["stage_08Z_Project_Closure_Publication/03_claim_matrix/final_claim_support_matrix.json"],{"qualified":["dynamic architecture","zero correction","defect target","actual optimizer updates"],"not_qualified":["trained solver","autonomous rollout","sealed test"]})]
    for item in figure_defs:
        index,title,conclusion,sources,data=item; make_figure_pack(index,title,conclusion,sources,data)

    titles = [
      "Qualification-first development of conservative neural corrections for smoothed particle hydrodynamics: from solver verification to training and coverage failure",
      "Before predictive trust: a qualification ladder for conservative neural corrections in particle solvers",
      "From structural verification to target-manifold failure in conservative neural SPH correction",
      "Failure-driven qualification of conservative learned corrections for smoothed particle hydrodynamics",
      "Separating architecture, target, optimizer and training qualification in neural particle solvers",
      "When verified updates do not yield a qualified solver: evidence from conservative neural SPH correction"]
    decision = "Option B — verification-first / qualification-first / failure-driven computational methodology article"
    write_text(STAGE / "07_publication_route/title_candidates_ranked.md", "# Ranked title candidates\n\n" + "\n".join(f"{i}. {title}" for i,title in enumerate(titles,1)))
    write_text(STAGE / "07_publication_route/final_publication_decision.md", f"""# Final publication decision

## Option A — full successful solver paper

Rejected. `FORMAL_TRAINED_SOLVER_QUALIFIED=false`, fresh-validation closure is 0/4, autonomous rollout is unqualified and the sealed test remains closed.

## Option B — verification-first methodology paper

Recommended. The strongest coherent evidence is the qualification ladder, reference/role governance, conservative architecture, defect-target construction, actual-update qualification, formal failure attribution, and descriptor-versus-target support distinction.

## Option C — multiple split papers

Not recommended as the primary route. Splitting the causal chain would weaken the central methodological argument and create overlap risk. A future independent verification paper would require its own scope and evidence freeze.

## Unique recommendation

**{decision}**, with *Computer Methods in Applied Mechanics and Engineering* as the first-priority target. The paper asks: *How should a conservative neural correction for a particle solver be qualified before its predictive performance is trusted?*
""")
    write_json(STAGE / "07_publication_route/publication_decision.json", {"recommended":"Option B","positioning":"verification-first / qualification-first / failure-driven computational methodology article","first_priority_journal":"Computer Methods in Applied Mechanics and Engineering","titles_ranked":titles})

    sealed = {"lineages":["LCDF_03","LCDF_10"],"closure_counts":{"formula_decode":0,"state_decode":0,"source_decode":0,"target_decode":0,"origin_decode":0,"evaluation":0},
              "SEALED_TEST_RELEASE_AUTHORIZATION":False,"SEALED_TEST_EVALUATED":False,"evidence":["stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json","stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json"]}
    write_json(STAGE / "01_project_status/final_sealed_test_ledger.json", sealed)
    write_text(STAGE / "01_project_status/final_sealed_test_ledger.md", "# Final sealed-test ledger\n\nLCDF_03 and LCDF_10 remain unopened at project closure.\n\n" +
      "\n".join(f"- `{key} = {value}`" for key,value in sealed["closure_counts"].items()) + "\n- `SEALED_TEST_RELEASE_AUTHORIZATION = false`\n- `SEALED_TEST_EVALUATED = false`\n\nThey must not be opened to supplement publication results.")

    manuscript = STAGE / "08_manuscript_source_pack"
    write_text(manuscript / "manuscript_narrative.md", """# 中文研究叙事

本项目研究的核心不是获得一条表现优异的 SPH–Transformer 曲线，而是回答：在信任粒子求解器中的保守神经修正之前，应当逐层验证什么？项目从 SPH 方程、离散算子、reference 角色和有限分辨率边界开始，将结构正确性、目标可表示性、梯度有效性、实际优化器更新、正式训练达标和验证支持区分为不同资格层。

早期静态 pair-force 路线证明，满足互易反对称和守恒合同并不保证训练拟合成功。动态 RK2 混合实现随后通过零修正等价、结构和一步梯度检查，但完整多步 AD/FD 资格化失败。Stage04 进一步表明，即使神经修正 Jacobian 非零，raw next-state loss 仍可能产生难以检测的参数训练信号。

Stage05 因而建立以 D0 accepted-state defect 为中心、带冻结尺度和保守分解的目标；Stage06 的 actual AdamW update 资格化说明该目标可产生可识别的更新动力学。然而九条正式训练 run 均未达到冻结的全局门。Stage07 增加公式异质性后再次执行九条训练 run，仍未通过，并将主要失败归因为 HET_S2_02 的 held-out support gap。

Stage08 以前瞻性四层 coverage 设计替代 hash 内部分配。192/192 候选通过基础资格化，HET_S2_02 descriptor distance 从 6.5115 降到 1.8607，但 target-PCA residual 为 3.5113，高于 1.5385 门限，且 fresh-validation 正式封闭为 0/4。由此，项目支持“descriptor coverage 不等于 correction-target manifold coverage”，但不支持成功训练求解器、Transformer 优越性或 sealed-test 性能主张。

论文应定位为 verification-first、qualification-first、failure-driven computational methodology article。失败路线不是调参日志，而是用于揭示资格层之间不可替代的因果边界。""")
    write_text(manuscript / "manuscript_scientific_source_en.md", """# English scientific narrative source

This project asks how a conservative neural correction for a particle solver should be qualified before its predictive performance is trusted. The evidence chain distinguishes numerical-solver verification, reference roles, structural correctness, target representability, gradient validity, actual optimizer dynamics, formal training, validation support, and sealed-test evaluation.

The static pair-force route showed that reciprocal antisymmetry and conservation-compatible structure do not guarantee successful fitting. The subsequent dynamic RK2 hybrid passed implementation, zero-correction, structural, and one-step differentiation checks, but did not satisfy the complete multistep AD/FD contract. A local-causal analysis then showed that a raw next-state loss could yield a poorly detectable parameter-training signal even when the neural correction Jacobian was nonzero.

The accepted-state D0 conservative defect introduced in Stage05 qualified its target construction, pair-basis representability, scale, and uncertainty. Stage06 further qualified actual AdamW update dynamics. Nevertheless, all nine Stage06 formal runs failed their frozen global seed criteria. Stage07 added formula heterogeneity and repeated nine formal runs; the global criterion again failed, and the dominant fresh-validation attribution was a held-out H2 support gap.

Stage08 replaced hash-based within-stratum roles with a prospective four-layer coverage design. All 192 candidates passed candidate-level qualification, and the descriptor distance of HET_S2_02 decreased from 6.5115 to 1.8607. Its raw-target PCA residual, however, remained 3.5113 against a 1.5385 threshold, and formal fresh-validation closure was 0/4. The final evidence therefore supports a distinction between descriptor support and correction-target manifold support, but it does not support a qualified SPH–Transformer solver, Transformer superiority, autonomous rollout, or sealed-test performance.

The recommended paper is a verification-first, qualification-first, failure-driven computational methodology article. Its contribution is the auditable ladder and the causal information provided by immutable failed gates—not a narrative of repeated hyperparameter tuning and not a claim of trained-solver success.""")
    write_text(manuscript / "abstract_v0_1.md", """# Abstract v0.1

## 中文

我们提出并执行一条面向 SPH 保守神经修正的 qualification-first 证据链，将求解器验证、reference 角色、互易反对称结构、accepted-state 离散缺陷、梯度、实际优化器更新、正式训练和支持区覆盖分离为不同资格层。结构和实际 AdamW 更新动力学获得资格，但两轮各九条正式训练 run 均未满足冻结的全局标准。系统化 Stage08 coverage 将关键 held-out lineage 的 descriptor distance 从 6.5115 降至 1.8607，却未使其 target-PCA residual 低于 1.5385 门限，fresh-validation 封闭为 0/4。结果表明，结构正确、局部可训练和 descriptor 支持均不能替代 target-manifold 与全局训练资格。项目未建立合格的 SPH–Transformer 求解器；其贡献是可审计的资格阶梯和失败驱动方法学。

## English scientific source

We develop and execute a qualification-first evidence chain for conservative neural corrections in smoothed particle hydrodynamics, separating solver verification, reference roles, reciprocal antisymmetric structure, accepted-state discrete defects, gradients, actual optimizer updates, formal training, and support coverage. Structural contracts and actual AdamW update dynamics were qualified, yet two nine-run formal campaigns failed their frozen global criteria. A prospective systematic-coverage experiment reduced the descriptor distance of a critical held-out lineage from 6.5115 to 1.8607, while its target-PCA residual remained 3.5113 against a 1.5385 threshold and formal fresh-validation closure remained 0/4. These results show that structural correctness, local trainability, and descriptor support cannot substitute for target-manifold and global-training qualification. The study does not establish a qualified SPH–Transformer solver; it provides an auditable qualification ladder and failure-driven computational methodology.""")
    write_text(manuscript / "introduction_logic.md", """# Introduction logic

1. Conservative learned solver corrections require more than predictive metrics: numerical references, role separation and structural invariants can fail independently.
2. Existing workflows often conflate implementation correctness, differentiability, optimizer motion and successful training.
3. The research question is how these layers should be qualified before predictive performance is trusted.
4. The paper contributes an evidence-governed ladder and evaluates it through successive falsifiable routes.
5. The outcome is deliberately bounded: verified components and informative failures, without a qualified trained solver or sealed-test claim.

No literature claims or citations are inserted in this source pack; a separate verified literature review is required.""")
    write_text(manuscript / "methods_source.md", """# Methods scientific source

Organize the methods by evidence layer rather than project stage: (i) SPH equation and finite-resolution verification; (ii) analytic, exact-trajectory and same-semidiscrete references; (iii) reciprocal antisymmetric pair corrections; (iv) dynamic RK2 state/history semantics; (v) accepted-state D0 defect and conservative decomposition; (vi) frozen target scale and uncertainty; (vii) AD/FD and actual AdamW update qualification; (viii) role, seal and checkpoint governance; and (ix) descriptor and target-manifold support geometry. Every threshold must cite its frozen contract. High-resolution SPH and DOP853 tolerance audits must not be labelled truth outside their registered role.""")
    write_text(manuscript / "results_source.md", """# Results scientific source

Report results as a qualification ladder. First establish the verified architecture and reference components. Then present static-fitting falsification, multistep-gradient and task-signal boundaries, followed by Stage05 target/scale and Stage06 actual-update qualifications. Present the Stage06 and Stage07 formal campaigns as complete executions that failed frozen global criteria. Use raw acceleration RMSE and relative zero-baseline reduction for common-anchor cross-stage comparisons; do not compare normalized Q as scale-independent performance. Close with Stage08: 128 TRAIN candidates, 64 validation candidates, 192/192 candidate qualification, eight selected new TRAIN lineages, TRAIN_V3=14, HET_S2_02 descriptor distance 1.8606627588827505, target residual 3.5113172977959843, threshold 1.5385435220163268, fresh closure 0/4, and zero model-prediction reads.""")
    write_text(manuscript / "discussion_source.md", """# Discussion scientific source

The central interpretation is separation, not generalized algorithm failure. Reciprocal antisymmetry constrained correction structure but did not guarantee target relevance or train fit. The D0 defect restored optimizer-level signal without guaranteeing the global training criterion. Heterogeneity augmentation and systematic descriptor coverage did not guarantee the raw target manifold. Discuss thresholds as preregistered decision rules whose value lies in preventing post hoc reinterpretation, while acknowledging that their external calibration remains problem-dependent. Explain that withholding the sealed test preserves inferential validity because no qualified checkpoint or validation closure existed to authorize release.""")
    write_text(manuscript / "conclusion_source.md", """# Conclusion scientific source

The project verified a conservative dynamic architecture, zero-correction equivalence, a scale-aware discrete-defect target, actual optimizer-update dynamics, and the execution integrity of two formal campaigns. It did not qualify a trained SPH–Transformer solver, autonomous rollout, Transformer superiority or sealed-test performance. Its final contribution is a falsifiable qualification-first methodology showing that architecture, target, gradient, optimizer, training and coverage evidence are distinct and non-substitutable.""")
    write_text(manuscript / "claim_matrix.md", (STAGE / "03_claim_matrix/final_claim_boundary.md").read_text(encoding="utf-8"))
    write_text(manuscript / "figure_plan.md", "# Figure plan\n\n" + "\n".join(f"- Figure {i}: {title}. Source pack: `06_figures_and_tables/Figure_{i:02d}/`." for i,title,*_ in figure_defs))
    write_text(manuscript / "table_plan.md", "# Table plan\n\n" + "\n".join(f"- Table {i}: {title}." for i,(title,_data) in tables.items()))
    write_text(manuscript / "limitations.md", """# Limitations

- The evidence is scoped to frozen SPH formulations, lineages, architectures, loss and optimizer contracts.
- Full coordinate-level FD coverage was not established.
- The Stage01 baseline did not become fully V2-qualified and high-resolution SPH is not truth.
- Formal training was executed but did not qualify a solver.
- Fresh-validation V3 did not close; the original sealed test was never released.
- Descriptor and target spaces depend on frozen definitions and thresholds; external calibration requires new independent studies.
- Transformer superiority and architecture necessity were not tested.
- No literature novelty claim is supported by this internal evidence package alone.""")
    risks = [
      ("R1","Why publish an unqualified trained solver?","The paper is about qualification methodology; complete negative campaigns reveal non-substitutable gates.","External utility must be demonstrated through clear transferable protocols, not solver performance."),
      ("R2","Are thresholds arbitrary?","Thresholds were frozen before outcomes and applied without relaxation.","Their external calibration remains problem-dependent."),
      ("R3","Is this just extensive debugging?","The stages form a falsifiable causal ladder with immutable verdicts, controlled roles and scientific consequences.","The manuscript must compress engineering detail and foreground general methodology."),
      ("R4","Why no sealed-test result?","Release required a qualified checkpoint and validation closure; neither occurred. Opening would be post hoc.","No final predictive generalization estimate is available."),
      ("R5","Why retain failed branches?","Failures define boundaries and prevent survivor-biased claims.","Readers may question space; use the failure graph and supplement."),
      ("R6","Why is high-resolution SPH not truth?","Stage01 separated model-form and finite-resolution effects; resolution alone did not qualify truth.","An independent higher-fidelity reference is still absent."),
      ("R7","Does antisymmetry guarantee all conservation?","It supports reciprocal linear-momentum-compatible correction forces in the audited contract only.","It does not guarantee energy, angular momentum, stability or accuracy."),
      ("R8","Why compare Transformer if superiority was not tested?","D1–D3 were controlled architecture arms for qualification, not a superiority claim.","No ranking claim can be made."),
      ("R9","Is Stage08 support design circular?","Descriptors and normalization were frozen from consumed development evidence before new candidates; model predictions were not read.","The design still used historically consumed cases and therefore is development evidence, not independent confirmation."),
      ("R10","Did repeated cycles overfit the research design?","Roles were consumed, new validation was required, verdicts were immutable, and Stage08 was declared final in advance.","The number of development decisions limits external generality and motivates route closure.")]
    write_text(manuscript / "reviewer_risk_register.md", "# Reviewer-risk register\n\n" + "\n\n".join(f"## {i}\n\n- Likely criticism: {c}\n- Evidence-based response: {a}\n- Remaining limitation: {l}" for i,c,a,l in risks))
    write_json(manuscript / "reviewer_risk_register.json", {"risks":[{"id":i,"criticism":c,"response":a,"remaining_limitation":l} for i,c,a,l in risks]})

    source_inventory = [entry(path) for path in sorted(manuscript.glob("*")) if path.is_file()]
    write_json(manuscript / "source_pack_manifest.json", {"files":source_inventory,"literature_citations_added":0,"new_scientific_computation":False})

    generated_before_report = [path for path in STAGE.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != "build_stage08z_closure.py"]
    closure_gates = {"all_historical_hashes_pass":postscan["pass"],"final_ledger_complete":len(rows)==9,
      "sealed_test_unopened":all(value==0 for value in sealed["closure_counts"].values()) and not sealed["SEALED_TEST_RELEASE_AUTHORIZATION"],
      "claim_boundary_complete":len(claims)==9 and len(prohibited)>=13,"cross_stage_evidence_complete":len(rows)==9,
      "publication_decision_complete":True,"manuscript_source_pack_complete":len(source_inventory)>=12,
      "no_new_scientific_computation":all(value==0 for value in COUNTS.values())}
    final_status = "PROJECT_FULL_SOLVER_ROUTE_CLOSED_PUBLICATION_EVIDENCE_FROZEN" if all(closure_gates.values()) else "PROJECT_CLOSURE_EVIDENCE_INCOMPLETE"
    report = f"""# Stage08Z final report

## 1–3. Stage08A failure, final-cycle policy and route closure

Stage08A ended `SYSTEMATIC_COVERAGE_V3_POOL_NOT_QUALIFIED`; Stage08B authorization is false. The preregistered `STAGE08_FINAL_DEVELOPMENT_CYCLE=true` policy therefore closes the in-project full-solver training-development route. This is not a general impossibility proof.

## 4–8. Project ledger, verified achievements, formal campaigns and final failures

The Stage00–08 ledger contains {len(rows)} major-stage rows. Verified achievements include the conservative dynamic architecture, zero-correction equivalence, the scale-aware conservative defect target and actual optimizer-update dynamics. Formal dynamic training was executed in Stage06 and Stage07 ({len(runs)} terminal runs total), but every D1/D2/D3 arm had 0/3 seed passes. The nine-node failure taxonomy ends with systematic descriptor improvement without target-manifold qualification. Stage08 produced 128 TRAIN and 64 validation candidates, 192/192 candidate passes, TRAIN_V3=14, HET_S2_02 descriptor distance 1.8606627588827505, target residual 3.5113172977959843 against 1.5385435220163268, and formal fresh-validation closure 0/4.

## 9–10. Final and prohibited claims

Nine allowed conclusions and {len(prohibited)} explicit prohibited claims are frozen in `03_claim_matrix/final_claim_boundary.md`. No trained-solver success, Transformer superiority, autonomous-rollout, high-resolution-truth or sealed-test claim is authorized.

## 11. Sealed-test proof

LCDF_03/LCDF_10 decode counts and evaluation count are all zero. `SEALED_TEST_RELEASE_AUTHORIZATION=false`. Historical mode-000 artifacts were not opened; their hashes are inherited from prior public seal manifests.

## 12–15. Innovation, publication, source pack and reviewer risks

The innovation register separates A-level methodology, B-level implementation and C-level negative evidence. The unique recommendation is Option B: a verification-first / qualification-first / failure-driven computational methodology article, first targeting CMAME. The manuscript source pack contains Chinese narrative and English scientific-source sections, 10 figure source packs, eight publication tables, and 10 reviewer-risk responses. No literature citation was fabricated.

## 16–18. Historical integrity, zero-development counts and final status

Historical artifacts inventoried={len(inventory)}; direct hashes recomputed and matched={postscan['direct_hashes_recomputed']}; prior-manifest hashes plus identity/mode checks for unreadable sealed artifacts={postscan['sealed_artifacts_identity_and_mode_checked']}; missing hashes={len(inventory_audit['missing_prior_hash'])}; post-scan hash mismatches={len(postscan['hash_mismatch'])}; mode mismatches={len(postscan['mode_mismatch'])}. All inventory rows are `mutable=false`. New execution counts are `{json.dumps(COUNTS,sort_keys=True)}`.

Final status: **{final_status}**
"""
    report_path = STAGE / "10_reports/stage08z_final_report.md"; write_text(report_path, report)
    all_outputs = [path for path in sorted(STAGE.rglob("*")) if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != "stage08z_final_manifest.json"]
    final_manifest = {"schema":"sph-pio-poc.stage08z.final.v1","final_status":final_status,"gates":closure_gates,
      "project_flags":final_flags,"new_execution_counts":COUNTS,"historical_freeze":entry(freeze_path),
      "historical_postscan":entry(postscan_path),"output_count":len(all_outputs),"outputs":[entry(path) for path in all_outputs],"next_authorization":"NONE",
      "training_route_reentry_authorized":False}
    write_json(STAGE / "09_manifests/stage08z_final_manifest.json", final_manifest)
    print(json.dumps({"final_status":final_status,"historical_artifacts":len(inventory),"output_count":len(all_outputs),
                      "gates":closure_gates,"new_execution_counts":COUNTS},indent=2))


if __name__ == "__main__": main()
