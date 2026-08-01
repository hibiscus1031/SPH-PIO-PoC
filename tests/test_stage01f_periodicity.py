from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.exact_fields import solution_module  # noqa:E402


def test_both_solutions_are_periodic_in_fields_and_source()->None:
    g=torch.Generator().manual_seed(20262021); p=2*torch.rand((257,2),generator=g,dtype=torch.float64)-1; t=.2*torch.rand(257,generator=g,dtype=torch.float64)
    for name in ("MMS_A","MMS_B"):
        base=solution_module(name).manual_fields(p,t)
        for d in (0,1):
            shifted=p.clone(); shifted[:,d]+=2; other=solution_module(name).manual_fields(shifted,t)
            for key in ("density","velocity","pressure","source"): assert torch.allclose(base[key],other[key],rtol=0,atol=2e-12)
