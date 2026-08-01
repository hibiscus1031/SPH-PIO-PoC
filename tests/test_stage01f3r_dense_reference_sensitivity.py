from pathlib import Path
import sys,numpy as np,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.dense_semidiscrete_reference import integrate_dense_reference

def test_dense_reference_sensitivity_on_two_particle_fixture()->None:
    p=torch.tensor([[-.2,0.],[.2,0.]],dtype=torch.float64);v=torch.zeros_like(p);m=torch.ones(2,dtype=torch.float64);h=torch.full((2,),.5,dtype=torch.float64);times=np.linspace(0,1e-4,3)
    a=integrate_dense_reference("MMS_A",p,v,m,h,times,rtol=1e-10,atol=1e-12,max_step=5e-5);b=integrate_dense_reference("MMS_A",p,v,m,h,times,rtol=1e-11,atol=1e-13,max_step=2.5e-5)
    assert np.max(np.abs(a.states-b.states))<=1e-8
