from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.exact_fields import solution_module  # noqa:E402
from manufactured_solutions.governing_equations import PARAMETERS  # noqa:E402
from manufactured_solutions.particle_initialization import regular_initialization  # noqa:E402


def test_density_bounds_and_positive_initialized_masses()->None:
    p=2*torch.rand((1000,2),generator=torch.Generator().manual_seed(9),dtype=torch.float64)-1; t=torch.linspace(0,.2,1000,dtype=torch.float64)
    for name in ("MMS_A","MMS_B"):
        rho=solution_module(name).density(p,t); assert float(rho.min())>=PARAMETERS.density_minimum and float(rho.max())<=PARAMETERS.density_maximum
        init=regular_initialization(name,16); assert bool((init.mass>0).all()) and init.masses_fixed_during_rollout and not init.analytic_density_overwrites_numerical_density
