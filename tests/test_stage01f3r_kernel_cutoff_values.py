from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.cutoff_smoothness import cutoff_probe

def test_kernel_and_gradient_are_zero_at_and_outside_cutoff()->None:
    rows=cutoff_probe()
    for row in rows:
        if row["q"]>=1.0:
            assert row["W"]==0.0 and row["dW_dr"]==0.0 and row["gradW_l2"]==0.0
    assert rows[3]["W"]<1e-50 and rows[3]["gradW_l2"]<1e-38
