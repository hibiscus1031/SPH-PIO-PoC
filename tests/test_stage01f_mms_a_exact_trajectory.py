from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.mms_a_translating_density_wave import density,exact_particle_trajectory,velocity  # noqa:E402


def test_mms_a_closed_trajectory_preserves_material_density()->None:
    initial=2*torch.rand((233,2),generator=torch.Generator().manual_seed(3),dtype=torch.float64)-1; times=.2*torch.rand(233,generator=torch.Generator().manual_seed(4),dtype=torch.float64); final=exact_particle_trajectory(initial,times)
    assert torch.allclose(density(initial,0.),density(final,times),rtol=0,atol=2e-15); assert torch.equal(velocity(final,times),torch.tensor([.5,0.],dtype=torch.float64).expand_as(final))
