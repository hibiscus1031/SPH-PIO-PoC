from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.mms_b_deforming_vortex import manual_fields  # noqa:E402


def test_mms_b_source_closes_both_momentum_components()->None:
    p=2*torch.rand((527,2),generator=torch.Generator().manual_seed(7),dtype=torch.float64)-1; f=manual_fields(p,torch.linspace(0,.2,527,dtype=torch.float64)); assert float(f["momentum_residual"].abs().max())<1e-13
