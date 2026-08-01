from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.torus_position_error import minimum_image_displacement

def test_torus_crossing_uses_minimum_image()->None:
    a=torch.tensor([[-.99,.99]],dtype=torch.float64); b=torch.tensor([[.99,-.99]],dtype=torch.float64)
    assert torch.allclose(minimum_image_displacement(a,b),torch.tensor([[.02,-.02]],dtype=torch.float64),atol=2e-16,rtol=0)
