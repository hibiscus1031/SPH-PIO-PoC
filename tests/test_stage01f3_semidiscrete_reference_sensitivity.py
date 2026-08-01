from pathlib import Path
import sys,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.semidiscrete_reference import integrate_semidiscrete_dop853

def test_independent_reference_tolerance_sensitivity()->None:
    rhs=lambda t,y:-1.3*y
    times=np.linspace(0,.01,11); y=np.array([1.,2.])
    a=integrate_semidiscrete_dop853(rhs,y,times,rtol=1e-12,atol=1e-14,max_step=3.125e-5)
    b=integrate_semidiscrete_dop853(rhs,y,times,rtol=1e-13,atol=1e-15,max_step=1.5625e-5)
    assert np.max(np.abs(a.states-b.states))<=1e-12
