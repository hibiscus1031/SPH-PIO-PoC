#!/usr/bin/env python3
"""Finalize required Stage 02M-Q evidence layout without changing scientific results."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_2"
REPORTS = STAGE / "07_reports"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


for name in ("train_metrics", "validation_metrics", "checkpoint_selection", "conditioning_diagnostics", "comparison_with_v01"):
    (ROOT / name).mkdir(parents=True, exist_ok=True)

run_rows = []
for terminal_path in sorted((ROOT / "runs").glob("K*/seed_*/run_terminal.json")):
    run_dir = terminal_path.parent
    terminal = json.loads(terminal_path.read_text())
    run_id = terminal["run_id"]
    selected_path = run_dir / "selected_metrics.json"
    shutil.copyfile(selected_path, ROOT / "train_metrics" / f"{run_id}_selected_metrics.json")
    shutil.copyfile(selected_path, ROOT / "validation_metrics" / f"{run_id}_selected_metrics.json")
    shutil.copyfile(terminal_path, ROOT / "checkpoint_selection" / f"{run_id}_selection.json")

    conditioning_path = run_dir / "conditioning_history.json"
    conditioning = json.loads(conditioning_path.read_text())
    for snapshot in conditioning["snapshots"]:
        for row in snapshot["parameters"]:
            row["near_zero_gradient_fraction"] = 1.0 - row["nonzero_gradient_fraction"]
        for row in snapshot["modules"].values():
            row["near_zero_gradient_fraction"] = 1.0 - row["nonzero_gradient_fraction"]
    conditioning["derived_layout_note"] = "near_zero_gradient_fraction is the exact complement of the frozen abs(gradient)>1e-14 nonzero criterion; no model, optimizer, checkpoint, or metric was changed"
    write_json(ROOT / "conditioning_diagnostics" / f"{run_id}_conditioning_history.json", conditioning)
    run_rows.append({
        "run_id": run_id,
        "train_metric_source": str(selected_path.relative_to(REPO)),
        "validation_metric_source": str(selected_path.relative_to(REPO)),
        "checkpoint_selection_source": str(terminal_path.relative_to(REPO)),
        "conditioning_source": str(conditioning_path.relative_to(REPO)),
    })

old_closure = ROOT / "manifests/stage02mq_training_validation_closure.json"
canonical_closure = ROOT / "manifests/training_validation_summary_manifest.json"
old_release = ROOT / "test_seal/stage02mq_test_release_manifest.json"
canonical_release = ROOT / "test_seal/test_release_manifest.json"
for source, destination in ((old_closure, canonical_closure), (old_release, canonical_release)):
    if not destination.exists():
        os.link(source, destination)
    if sha(source) != sha(destination):
        raise RuntimeError(f"canonical alias byte drift: {destination}")

old_comparison = ROOT / "comparison/stage02mq_v01_descriptive_comparison.json"
canonical_comparison = ROOT / "comparison_with_v01/stage02mq_v01_descriptive_comparison.json"
shutil.copyfile(old_comparison, canonical_comparison)

layout = {
    "manifest_version": "stage02mq-required-layout-1.0.0",
    "scientific_result_modified": False,
    "post_test_optimizer_steps": 0,
    "post_test_checkpoint_changes": 0,
    "canonical_closure_sha256": sha(canonical_closure),
    "canonical_release_sha256": sha(canonical_release),
    "canonical_release_byte_identical_to_evaluated_release": sha(canonical_release) == sha(old_release),
    "run_rows": run_rows,
    "status": "PASS" if len(run_rows) == 9 else "FAIL",
}
write_json(ROOT / "manifests/stage02mq_required_layout_audit.json", layout)

manifest_path = ROOT / "manifests/stage02mq_run_manifest.json"
manifest = json.loads(manifest_path.read_text())
artifacts = []
for path in sorted(ROOT.rglob("*")):
    if path.is_file() and "__pycache__" not in path.parts and path != manifest_path:
        artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
for path in sorted(REPORTS.glob("stage02mq_*.md")):
    artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
manifest["artifacts"] = artifacts
manifest["required_layout_audit"] = str((ROOT / "manifests/stage02mq_required_layout_audit.json").relative_to(REPO))
manifest["required_layout_status"] = layout["status"]
write_json(manifest_path, manifest)
print(json.dumps({"status": layout["status"], "runs": len(run_rows), "artifacts": len(artifacts), "release_sha256": sha(canonical_release)}, sort_keys=True))
