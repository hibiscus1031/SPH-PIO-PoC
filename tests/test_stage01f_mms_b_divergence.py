from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.mms_b_deforming_vortex import manual_fields  # noqa:E402


def test_mms_b_is_divergence_free_and_tangent_to_density()->None:
    p=2*torch.rand((521,2),generator=torch.Generator().manual_seed(5),dtype=torch.float64)-1; f=manual_fields(p,.173); assert float(f["velocity_divergence"].abs().max())<1e-14; assert float(f["density_advection"].abs().max())<1e-14
