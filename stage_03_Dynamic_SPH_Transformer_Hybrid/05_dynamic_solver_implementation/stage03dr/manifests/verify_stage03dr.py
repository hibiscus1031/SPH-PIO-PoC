"""Read-only integrity verification for the completed Stage 03D-R attribution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve()
STAGE03DR = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
MANIFESTS = STAGE03 / "10_manifests"
EXPECTED_STATUS = "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED"
CONTRACT_HASH = "sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def check_entry(item: dict[str, object], errors: list[dict[str, object]]) -> None:
    path = ROOT / str(item["path"])
    actual = sha(path) if path.exists() else None
    if actual != item["sha256"]:
        errors.append({"path": item["path"], "expected": item["sha256"], "actual": actual})


def main() -> None:
    final = json.loads((MANIFESTS / "stage03dr_final_manifest.json").read_text(encoding="utf-8"))
    attribution_manifest = json.loads((MANIFESTS / "stage03dr_attribution_manifest.json").read_text(encoding="utf-8"))
    input_freeze = json.loads((MANIFESTS / "stage03dr_input_freeze_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((STAGE03DR / "results/stage03dr_summary.json").read_text(encoding="utf-8"))
    cross = json.loads((STAGE03DR / "ad_crosscheck/reverse_vs_jvp.json").read_text(encoding="utf-8"))
    extended = json.loads((STAGE03DR / "fd_conditioning/extended_fd_results.json").read_text(encoding="utf-8"))
    history = json.loads((STAGE03DR / "history_path/reference_prehistory_trace.json").read_text(encoding="utf-8"))
    attribution = json.loads((STAGE03DR / "attribution/failure_attribution.json").read_text(encoding="utf-8"))
    route = json.loads((STAGE03DR / "route_decision/dynamic_route_decision.json").read_text(encoding="utf-8"))
    resources = json.loads((STAGE03DR / "results/resource_audit.json").read_text(encoding="utf-8"))
    stage03d = json.loads((MANIFESTS / "stage03d_final_manifest.json").read_text(encoding="utf-8"))

    hash_errors: list[dict[str, object]] = []
    for item in final["reports"]:
        check_entry(item, hash_errors)
    for key in ("contract", "input_freeze", "attribution_manifest", "qualification_summary"):
        check_entry(final[key], hash_errors)
    for item in attribution_manifest["artifacts"]:
        check_entry(item, hash_errors)

    historical_errors: list[dict[str, object]] = []
    for item in input_freeze["evidence"]:
        check_entry(item, historical_errors)
    for key in ("stage03d_failure_matrix", "selected_row_manifest"):
        check_entry(input_freeze[key], historical_errors)

    python_text = "\n".join(path.read_text(encoding="utf-8") for path in STAGE03DR.rglob("*.py") if path.resolve() != HERE)
    prohibited = [token for token in ("torch.optim", "optimizer.step(", ".backward(", ".train(") if token in python_text]
    required_reports = {
        "stage03dr_freeze_and_scope.md", "stage03dr_failure_matrix.md", "stage03dr_derivative_scale.md", "stage03dr_ad_crosscheck.md", "stage03dr_fd_conditioning.md", "stage03dr_objective_decomposition.md", "stage03dr_history_path.md", "stage03dr_horizon_scaling.md", "stage03dr_failure_attribution.md", "stage03dr_route_decision.md", "stage03dr_final_report.md"
    }
    gates = {
        "contract_hash": final["contract"]["sha256"] == CONTRACT_HASH,
        "required_reports": {Path(item["path"]).name for item in final["reports"]} == required_reports,
        "manifest_hashes": not hash_errors,
        "historical_hashes": not historical_errors,
        "historical_stage03d_preserved": stage03d["final_status"] == "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED" and final["historical_stage03d_status"] == stage03d["final_status"],
        "matrix_complete": summary["matrix"]["row_count"] == 360 and summary["matrix"]["fail_count"] == 144,
        "formal_ad_crosscheck": cross["passed"] == cross["required"] == 60 and cross["pass"],
        "historical_backend_diagnostic": cross["historical_default_backend_match_count"] == 48,
        "extended_fd_complete": extended["required"] == 60 and extended["extended_fd_path_count"] == 2640,
        "history_complete": len(history["rows"]) == 6 and history["pass"],
        "failure_attribution_complete": attribution["classified_count"] == 144 and attribution["unique_primary_for_all"],
        "route_status": route["final_status"] == summary["final_status"] == final["final_status"] == EXPECTED_STATUS,
        "stage03e_false": not final["stage03e_authorization"] and not summary["stage03e_authorization"] and not route["stage03e_authorization"],
        "topology_preserved": final["topology_component_status"] == "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
        "resources": resources["pass"],
        "prohibitions": final["new_optimizer_steps"] == summary["new_optimizer_steps"] == 0 and final["new_training_runs"] == summary["new_training_runs"] == 0 and not prohibited,
    }
    result = {"final_status": final["final_status"], "gates": gates, "hash_errors": hash_errors, "historical_errors": historical_errors, "prohibited_calls": prohibited, "pass": all(gates.values())}
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
