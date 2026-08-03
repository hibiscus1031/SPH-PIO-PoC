import csv
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "06_experiments/stage_01f5b_requalification_execution/manifests/numerical_source_identity.csv"


def test_all_103_frozen_numerical_source_files_remain_identical():
    with SOURCE_MANIFEST.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 103
    for row in rows:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["frozen_sha256"]


def test_stage01gr_additions_do_not_modify_solver_or_frozen_benchmark_evaluator():
    changed = subprocess.check_output(
        ("git", "diff", "--name-only", "7dc7fd10056cb3aacf9c0347c7516f1a77b6af32"),
        cwd=ROOT,
        text=True,
    ).splitlines()
    forbidden_prefixes = (
        "01_solver/",
        "06_experiments/stage_01g_validation_design/",
        "06_experiments/stage_01ge_evaluator_qualification/",
        "06_experiments/stage_01g_validation_execution/",
        "07_reports/stage_01g_",
    )
    assert changed
    assert not any(path.startswith(forbidden_prefixes) for path in changed)
