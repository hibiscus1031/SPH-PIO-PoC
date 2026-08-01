from pathlib import Path
import sys
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from benchmark_alignment.material_acceleration import exact_balance  # noqa:E402


def test_material_and_momentum_identities_at_random_coordinates() -> None:
    generator=torch.Generator().manual_seed(20262002); positions=2*torch.rand((113,2),generator=generator,dtype=torch.float64)-1
    result=exact_balance(positions,0.219,reference_density=1.0,velocity_amplitude=1.0,viscosity=0.02)
    assert float(result["kinematic_residual"].abs().max())<2e-15
    assert float(result["momentum_residual"].abs().max())<2e-15
