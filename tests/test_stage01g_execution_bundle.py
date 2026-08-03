import ast
import csv
import hashlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_validation_execution"
WORKER = STAGE / "stage01g_worker.py"
COORDINATOR = STAGE / "run_stage01g_campaign.py"
ANALYZER = STAGE / "evaluate_stage01g_execution.py"


def _tree(path):
    return ast.parse(path.read_text(), filename=str(path))


def test_execution_adapter_has_no_source_reference_or_accelerator_dependency():
    tree = _tree(WORKER)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "").lower())
    joined = "\n".join(imports)
    for forbidden in ("manufactured", "sourced_", "dop853", "scipy", "training", "learned_corrector"):
        assert forbidden not in joined
    assert "dynamic_solver.periodic_rollout" in imports
    assert "evaluator.shear_evaluator" in imports
    assert "evaluator.acoustic_evaluator" in imports


def test_worker_preserves_gc_no_grad_cpu_float64_and_zero_source_contract():
    tree = _tree(WORKER)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "gc"
        and node.func.attr == "collect"
        for node in calls
    )
    text = WORKER.read_text()
    assert "with torch.no_grad():" in text
    assert "dtype=torch.float64" in text
    assert '"source_call_count": 0' in text
    assert '"device": "cpu"' in text
    assert '"parent_scalar_only": True' in text
    assert "jitter_fraction=0.0" in text
    assert "seed=0" in text
    for pair in (
        '"positions": "position"',
        '"velocities": "velocity"',
        '"densities": "density"',
        '"pressures": "pressure"',
    ):
        assert pair in text


def test_coordinator_freezes_exact_phase_order_and_independent_subprocesses():
    tree = _tree(COORDINATOR)
    phases = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "PHASES" for target in node.targets)
    )
    assert phases["A"] == (
        "g_shear_n24",
        "g_shear_n32",
        "g_shear_n48",
        "g_shear_n32_dt_half",
        "g_shear_n48_rep2",
    )
    assert phases["B"] == (
        "g_acoustic_e5e3_n24",
        "g_acoustic_e5e3_n32",
        "g_acoustic_e5e3_n48",
        "g_acoustic_e5e3_n32_dt_half",
        "g_acoustic_e5e3_n48_rep2",
        "g_acoustic_e2p5e3_n48",
        "g_acoustic_e1e2_n48",
    )
    text = COORDINATOR.read_text()
    assert "subprocess.Popen(" in text
    assert "phase_a_completed_first" in text
    assert "parent_scalar_only" in text
    assert "child_reclaimed" in text


def test_historical_failed_preflight_evidence_remains_byte_identical():
    manifest = STAGE / "manifests/stage01g_preflight_evidence_sha256.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 12
    for row in rows:
        payload = (ROOT / row["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]


def test_analyzer_has_only_frozen_v2_outcomes_and_no_downstream_start():
    text = ANALYZER.read_text()
    assert "V2_QUALIFICATION_PASS" in text
    assert "V2_QUALIFICATION_FAIL" in text
    assert "V2_QUALIFICATION_EVIDENCE_INCOMPLETE" in text
    for boundary in (
        '"v3_started": False',
        '"stage02_started": False',
        '"training_started": False',
        '"label_generation_started": False',
    ):
        assert boundary in text


def test_original_execution_code_manifest_remains_valid_at_preserved_commit():
    manifest = STAGE / "manifests/stage01g_execution_code_sha256.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    assert {Path(row["path"]).name for row in rows} == {
        "stage01g_worker.py",
        "run_stage01g_campaign.py",
        "evaluate_stage01g_execution.py",
    }
    for row in rows:
        payload = subprocess.check_output(
            ("git", "show", f"543a60a7d084c8eaee97e742aaf1622415b8db35:{row['path']}"),
            cwd=ROOT,
        )
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]


def test_retry1_execution_code_manifest_remains_valid_at_preserved_commit():
    manifest = STAGE / "manifests/stage01g_execution_code_sha256_retry1.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    for row in rows:
        payload = subprocess.check_output(
            ("git", "show", f"38080c86f4f1c829b3159d62fcf461044deb5218:{row['path']}"),
            cwd=ROOT,
        )
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]


def test_retry2_execution_code_manifest_remains_valid_at_execution_commit():
    manifest = STAGE / "manifests/stage01g_execution_code_sha256_retry2.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3
    for row in rows:
        payload = subprocess.check_output(
            ("git", "show", f"83e36b826e65cd6fcb2f9538e3c1443768e30b19:{row['path']}"),
            cwd=ROOT,
        )
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]
