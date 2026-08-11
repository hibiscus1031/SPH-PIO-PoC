"""Read-only integrity and status verification for completed Stage 03D artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve()
STAGE03D = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
MANIFESTS = STAGE03 / "10_manifests"
CONTRACT_HASH = "sha256:a506af65ac124f8edf843e507f70c88566852fdfefb017eea127ddbe227fa692"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    final = json.loads((MANIFESTS / "stage03d_final_manifest.json").read_text(encoding="utf-8"))
    summary_path = ROOT / final["qualification"]["path"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    freeze_path = ROOT / final["input_freeze"]["path"]
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    ledger_path = ROOT / freeze["historical_tree_ledger"]["path"]
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    hash_errors = []
    for group in ("reports", "manifests"):
        for item in final[group]:
            path = ROOT / item["path"]
            actual = sha(path) if path.exists() else None
            if actual != item["sha256"]:
                hash_errors.append({"path": item["path"], "expected": item["sha256"], "actual": actual})
    for key in ("input_freeze", "qualification"):
        item = final[key]
        path = ROOT / item["path"]
        actual = sha(path) if path.exists() else None
        if actual != item["sha256"]:
            hash_errors.append({"path": item["path"], "expected": item["sha256"], "actual": actual})

    historical_errors = []
    for item in ledger["files"]:
        path = ROOT / item["path"]
        actual = sha(path) if path.exists() else None
        if actual != item["sha256"]:
            historical_errors.append({"path": item["path"], "expected": item["sha256"], "actual": actual})

    python_text = "\n".join(path.read_text(encoding="utf-8") for path in STAGE03D.rglob("*.py") if path.resolve() != HERE)
    prohibited_calls = [token for token in ("torch.optim", "optimizer.step(", ".backward(", ".train(") if token in python_text]
    gates = {
        "contract_hash": final["contract"]["sha256"] == CONTRACT_HASH,
        "manifest_hashes": not hash_errors,
        "historical_hashes": not historical_errors,
        "summary_status_match": final["final_status"] == summary["final_status"],
        "gate_map_match": final["completion_gates"] == summary["gates"],
        "required_counts": summary["counts"]["fixed_topology_arm_case_seed_horizon_count"] == 72 and summary["counts"]["required_probe_count"] == 360 and summary["counts"]["adfd_comparison_count"] == 2880,
        "event_counts": summary["counts"]["event_birth_count"] == 1 and summary["counts"]["event_death_count"] == 1,
        "prohibitions": final["optimizer_steps"] == 0 and final["training_runs"] == 0 and not prohibited_calls,
        "status_logic": final["final_status"] == "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED" and not summary["gates"]["B_fixed_topology_adfd"] and not summary["gates"]["C_history_and_conservation"],
    }
    result = {
        "gates": gates,
        "hash_errors": hash_errors,
        "historical_errors": historical_errors,
        "prohibited_calls": prohibited_calls,
        "final_status": final["final_status"],
        "pass": all(gates.values()),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
