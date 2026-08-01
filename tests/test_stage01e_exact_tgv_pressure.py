import math
from pathlib import Path
import sys
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from benchmark_alignment.incompressible_tgv_exact import pressure,pressure_acceleration  # noqa:E402


def test_exact_pressure_gradient_matches_acceleration() -> None:
    generator=torch.Generator().manual_seed(20262001)
    positions=(2*torch.rand((97,2),generator=generator,dtype=torch.float64)-1).requires_grad_(True)
    value=pressure(positions,0.137,reference_density=1.7,velocity_amplitude=0.83,viscosity=0.031,wave_number=math.pi)
    gradient=torch.autograd.grad(value.sum(),positions)[0]
    expected=pressure_acceleration(positions.detach(),0.137,reference_density=1.7,velocity_amplitude=0.83,viscosity=0.031,wave_number=math.pi)
    assert torch.allclose(-gradient/1.7,expected,rtol=2e-14,atol=2e-14)
