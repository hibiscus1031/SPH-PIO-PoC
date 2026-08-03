"""Final stop-on-failure preflight for the Stage 01G formal reapplication."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stage01g_reapplication_contract import (  # noqa: E402
    ALL_IDS, CODE_FILES, CONFIG, CONFIG_SHA256, FROZEN_PYTHON, GE_MANIFEST,
    G_MANIFEST, GR_CODE_MANIFEST, GR_EVALUATION, GR_EVIDENCE_MANIFEST,
    MATRIX, MATRIX_SHA256, METRICS, METRICS_SHA256, PREFLIGHT_REPORT,
    PREFLIGHT_RESULT, PREFLIGHT_V2, ROOT, SOURCE_MANIFEST, STAGE,
    STAGE01G_COMMIT, STAGE01G_TAG, STAGE01GE_COMMIT, STAGE01GP_COMMIT,
    STAGE01GR_COMMIT, attempt_run_dir, checkpoint_path, evaluator_path,
    execution_code_hashes, git, log_paths, matrix_rows, read_csv, read_json,
    reference_path, sha256, verify_manifest, write_json_new, write_text_new,
)

EVALUATOR_ROOT = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(EVALUATOR_ROOT))
from evaluator.gate_rules import HARD_SAFETY_LIMITS, THRESHOLDS, metric_binding  # noqa: E402


def main() -> int:
    if PREFLIGHT_RESULT.exists() or PREFLIGHT_REPORT.exists():
        raise RuntimeError("refusing to overwrite final execution preflight evidence")
    rows = matrix_rows()
    source_rows = read_csv(SOURCE_MANIFEST)
    gr = read_json(GR_EVALUATION)
    v2 = read_json(PREFLIGHT_V2)
    expected_thresholds = {
        "SHEAR2": 0.02, "SHEAR3": 0.02, "SHEAR4": 0.01,
        "SHEAR5": 5.0e-3, "SHEAR6": 1.0e-3, "SHEAR8": 0.10,
        "ACOUSTIC2": 0.02, "ACOUSTIC3": 0.05, "ACOUSTIC4": 0.05,
        "ACOUSTIC5": 0.10, "ACOUSTIC6": 1.0e-3, "ACOUSTIC8": 0.10,
    }
    expected_hard = {
        "pair_force_residual": ("<=", 1.0e-12),
        "normalized_internal_force_residual": ("<=", 1.0e-10),
        "force_assembly_defect": ("<=", 1.0e-10),
        "momentum_update_defect": ("<=", 1.0e-10),
        "viscous_power_positive_tolerance": ("<=", 1.0e-12),
        "structural_topology_defects": ("<=", 0.0),
        "minimum_separation_over_dx": (">=", 0.25),
        "current_rss_bytes": ("<", 2_000_000_000.0),
        "peak_rss_bytes": ("<", 4_000_000_000.0),
        "rss_q4_minus_q1_bytes": ("<=", 250_000_000.0),
        "rss_q4_over_q1": ("<=", 1.50),
        "step_time_q4_over_q1": ("<=", 1.30),
        "source_call_count": ("<=", 0.0),
    }
    binding = metric_binding()
    target_paths = []
    for run_id in ALL_IDS:
        target_paths.extend((attempt_run_dir(run_id), checkpoint_path(run_id), reference_path(run_id), evaluator_path(run_id), *log_paths(run_id)))
    tracked_code = all(
        subprocess.run(("git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))), cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        for path in CODE_FILES
    )
    checks = {
        "frozen_python_environment": Path(sys.executable).resolve() == FROZEN_PYTHON,
        "working_tree_clean_before_preflight": git("status", "--porcelain") == "",
        "execution_code_tracked": tracked_code,
        "stage01g_tag_identity": git("cat-file", "-t", STAGE01G_TAG) == "tag" and git("rev-list", "-n", "1", STAGE01G_TAG) == STAGE01G_COMMIT,
        "stage01g_frozen_identity_9_of_9": verify_manifest(G_MANIFEST, 9, "sha256"),
        "stage01gp_commit_ancestor": subprocess.run(("git", "merge-base", "--is-ancestor", STAGE01GP_COMMIT, "HEAD"), cwd=ROOT).returncode == 0,
        "stage01ge_commit_ancestor": subprocess.run(("git", "merge-base", "--is-ancestor", STAGE01GE_COMMIT, "HEAD"), cwd=ROOT).returncode == 0,
        "stage01ge_evaluator_identity_9_of_9": verify_manifest(GE_MANIFEST, 9, "sha256"),
        "stage01gr_commit_is_head": git("rev-parse", "HEAD") != STAGE01GR_COMMIT and subprocess.run(("git", "merge-base", "--is-ancestor", STAGE01GR_COMMIT, "HEAD"), cwd=ROOT).returncode == 0,
        "stage01gr_code_identity_5_of_5": verify_manifest(GR_CODE_MANIFEST, 5, "sha256"),
        "stage01gr_evidence_identity_29_of_29": verify_manifest(GR_EVIDENCE_MANIFEST, 29, "sha256"),
        "stage01gr_ready_status": gr.get("unique_status") == "EXECUTION_INFRA_READY_FOR_BENCHMARK" and all(gr.get("checks", {}).values()),
        "preflight_v2_authorized": v2.get("unique_status") == "INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED" and all(v2.get("checks", {}).values()),
        "exact_12_unique_run_ids": len(rows) == 12 and tuple(row["run_id"] for row in rows) == ALL_IDS and len({row["run_id"] for row in rows}) == 12,
        "frozen_future_output_binding": all(row["future_output_directory"] == f"06_experiments/stage_01g_validation_execution/runs/{row['run_id']}" for row in rows),
        "reapplication_output_targets_clean": all(not path.exists() for path in target_paths),
        "threshold_hash_immutable": sha256(CONFIG) == CONFIG_SHA256 and THRESHOLDS == expected_thresholds and HARD_SAFETY_LIMITS == expected_hard,
        "run_matrix_hash_immutable": sha256(MATRIX) == MATRIX_SHA256,
        "metric_contract_hash_immutable": sha256(METRICS) == METRICS_SHA256,
        "metric_binding_exact": binding["authoritative_sources"] == {"stage01g_config_sha256": CONFIG_SHA256, "stage01g_metric_contract_sha256": METRICS_SHA256} and binding["normalization"]["adaptive_threshold"] is False,
        "numerical_source_identity_103_of_103": len(source_rows) == 103 and all((ROOT / row["path"]).is_file() and sha256(ROOT / row["path"]) == row["frozen_sha256"] for row in source_rows),
    }
    payload = {
        "schema_version": "sph-pio-poc.stage01g.execution-preflight.v1",
        "execution_attempt": "reapplication_01",
        "checks": checks,
        "overall_status": "PASS" if all(checks.values()) else "FAIL",
        "execution_code_sha256": execution_code_hashes(),
        "git_head": git("rev-parse", "HEAD"),
        "benchmark_runs_started": 0,
        "frozen_chain": {
            "stage01g": STAGE01G_COMMIT, "stage01gp": STAGE01GP_COMMIT,
            "stage01ge": STAGE01GE_COMMIT, "stage01gr": STAGE01GR_COMMIT,
        },
    }
    write_json_new(PREFLIGHT_RESULT, payload)
    table = "\n".join(f"| `{name}` | {'PASS' if passed else 'FAIL'} |" for name, passed in checks.items())
    report = f"""# Stage 01G execution final preflight

Execution attempt: `reapplication_01`. No benchmark was launched by this preflight.

The historical Stage 01G failures remain preserved. This application uses clean, distinct output targets below each frozen run directory and does not overwrite any prior evidence.

| Check | Status |
|---|---|
{table}

Overall preflight: **{payload['overall_status']}**.

Frozen execution environment: CPU, float64, 2D periodic, default cyclic GC, `torch.no_grad()`, one independent child per run, scalar-only parent aggregation, no in-loop `gc.collect()`.

Downstream V3, Stage 02, training, and label generation remain stopped.
"""
    write_text_new(PREFLIGHT_REPORT, report)
    print(json.dumps({"preflight": payload["overall_status"], "checks": len(checks), "benchmark_runs_started": 0}, sort_keys=True))
    return 0 if payload["overall_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
