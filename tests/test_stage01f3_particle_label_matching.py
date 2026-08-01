from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.labeled_particle_error import labeled_state_error

def test_particle_labels_are_not_permuted()->None:
    exact=torch.tensor([[.1,.2],[.3,.4]],dtype=torch.float64); numerical=exact.flip(0)
    scalar=torch.ones(2,dtype=torch.float64); vector=torch.zeros((2,2),dtype=torch.float64)
    result=labeled_state_error(numerical_positions=numerical,exact_positions=exact,numerical_velocity=vector,exact_velocity=vector,numerical_density=scalar,exact_density=scalar,numerical_pressure=scalar,exact_pressure=scalar)
    assert result["position"]["L2"]>0
