from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.dense_all_pairs_rhs import minimum_image_matrix

def test_dense_pairs_use_periodic_minimum_image_and_reciprocity()->None:
    positions=torch.tensor([[-.99,0.],[.99,0.]],dtype=torch.float64);d=minimum_image_matrix(positions)
    assert torch.allclose(d[0,1],torch.tensor([.02,0.],dtype=torch.float64),atol=2e-16,rtol=0)
    assert torch.equal(d[0,1],-d[1,0])
