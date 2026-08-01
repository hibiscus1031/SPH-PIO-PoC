from hashlib import sha256
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FROZEN = (
    "01_solver/manufactured_solutions/governing_equations.py",
    "01_solver/manufactured_solutions/mms_a_translating_density_wave.py",
    "01_solver/manufactured_solutions/mms_b_deforming_vortex.py",
    "01_solver/manufactured_solutions/source_terms.py",
    "06_experiments/stage_01f_mms_design/configs/preregistered_mms_specification.yml",
    "06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json",
    "07_reports/stage_01f_final_report.md",
)


def test_stage01f_files_are_byte_identical_to_f835b05() -> None:
    for relative in FROZEN:
        committed = subprocess.check_output(("git", "show", f"f835b05:{relative}"), cwd=ROOT)
        assert sha256((ROOT / relative).read_bytes()).digest() == sha256(committed).digest()


def test_stage01f_tag_targets_final_evidence_commit() -> None:
    target = subprocess.check_output(
        ("git", "rev-list", "-n", "1", "stage-01f-mms-specification-pass"),
        cwd=ROOT,
        text=True,
    ).strip()
    assert target == "f835b059d98c5a417551a9a349b3537b8c4d2b35"
