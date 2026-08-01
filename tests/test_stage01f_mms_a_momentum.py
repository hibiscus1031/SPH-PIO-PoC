from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.mms_a_translating_density_wave import manual_fields  # noqa:E402


def test_mms_a_source_closes_momentum()->None:
    p=2*torch.rand((509,2),generator=torch.Generator().manual_seed(2),dtype=torch.float64)-1; f=manual_fields(p,.137); assert float(f["momentum_residual"].abs().max())<1e-14; assert torch.allclose(f["source"],f["pressure_gradient"]/f["density"][:,None])
