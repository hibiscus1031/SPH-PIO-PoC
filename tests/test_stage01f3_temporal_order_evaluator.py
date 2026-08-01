from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.convergence_metrics import fitted_order,successive_orders

def test_second_order_synthetic_errors()->None:
    dt=[1e-3,5e-4,2.5e-4,1.25e-4,6.25e-5]; e=[x*x for x in dt]
    assert abs(fitted_order(dt,e)-2)<1e-12
    assert all(abs(p-2)<1e-12 for p in successive_orders(e))
