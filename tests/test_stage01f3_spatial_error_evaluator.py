from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.convergence_metrics import fitted_order,strictly_decreasing

def test_spatial_global_slope_and_monotonicity()->None:
    dx=[2/16,2/24,2/32,2/48]; errors=[x**1.5 for x in dx]
    assert strictly_decreasing(errors)
    assert abs(fitted_order(dx,errors)-1.5)<1e-12
