from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.mms_a_translating_density_wave import manual_fields  # noqa:E402


def test_mms_a_continuity_closes()->None:
    p=2*torch.rand((511,2),generator=torch.Generator().manual_seed(1),dtype=torch.float64)-1; f=manual_fields(p,torch.linspace(0,.2,511,dtype=torch.float64)); assert float(f["continuity_residual"].abs().max())<1e-14
