from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from benchmark_alignment.residual_decomposition import compute_initial_case  # noqa:E402


def test_residual_decomposition_closes_in_float64() -> None:
    row=compute_initial_case(resolution=16,support_ratio=4.0,jitter_fraction=0.05,seed=20261001)
    assert row["closure_Linf"]<=1e-11
    assert row["closure_relative_L2"]<=1e-11
    assert row["R_total_L2"]>0
