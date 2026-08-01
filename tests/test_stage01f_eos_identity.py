from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.exact_fields import solution_module  # noqa:E402


def test_eos_is_exact_for_both_solutions()->None:
    p=torch.tensor([[-1+1e-14,.3],[1-1e-14,-.7],[.2,.8]],dtype=torch.float64); t=torch.tensor([0.,.1,.2],dtype=torch.float64)
    for name in ("MMS_A","MMS_B"):
        f=solution_module(name).manual_fields(p,t); assert float((f["pressure"]-400*(f["density"]-1)).abs().max())<=1e-13
