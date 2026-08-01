from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.exact_derivatives import autograd_fields  # noqa:E402
from manufactured_solutions.exact_fields import solution_module  # noqa:E402


def test_all_manual_derivatives_and_sources_match_autograd()->None:
    p=2*torch.rand((193,2),generator=torch.Generator().manual_seed(8),dtype=torch.float64)-1; t=torch.linspace(0,.2,193,dtype=torch.float64); keys=("partial_time_density","density_gradient","divergence_rho_velocity","partial_time_velocity","velocity_jacobian","velocity_divergence","density_advection","convection","velocity_laplacian","pressure_gradient","material_acceleration","source")
    for name in ("MMS_A","MMS_B"):
        manual=solution_module(name).manual_fields(p,t); automatic=autograd_fields(name,p,t)
        assert max(float((manual[k]-automatic[k]).detach().abs().max()) for k in keys)<=1e-11
