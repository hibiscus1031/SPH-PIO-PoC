"""MMS-A: a periodic density wave translated by a constant velocity."""

from __future__ import annotations

import torch
from manufactured_solutions.governing_equations import MMSParameters,PARAMETERS,validate_points


def density(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    p,t=validate_points(positions,time); k=parameters.wave_number; xi=p[:,0]-parameters.translation_speed*t
    return parameters.rho0*(1+parameters.density_amplitude*torch.sin(k*xi)*torch.sin(k*p[:,1]))


def velocity(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    p,_=validate_points(positions,time); return torch.stack((torch.full_like(p[:,0],parameters.translation_speed),torch.zeros_like(p[:,1])),dim=-1)


def pressure(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    return parameters.sound_speed**2*(density(positions,time,parameters)-parameters.rho0)


def manual_fields(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->dict[str,torch.Tensor]:
    p,t=validate_points(positions,time); k=parameters.wave_number; eps=parameters.density_amplitude; rho0=parameters.rho0; uc=parameters.translation_speed; xi=p[:,0]-uc*t
    sx,cx=torch.sin(k*xi),torch.cos(k*xi); sy,cy=torch.sin(k*p[:,1]),torch.cos(k*p[:,1]); rho=density(p,t,parameters); vel=velocity(p,t,parameters)
    grad_rho=rho0*eps*k*torch.stack((cx*sy,sx*cy),dim=-1); partial_rho=-uc*grad_rho[:,0]; div_rho_u=uc*grad_rho[:,0]; grad_p=parameters.sound_speed**2*grad_rho; zeros=torch.zeros_like(vel); source=grad_p/rho[:,None]
    return {"density":rho,"velocity":vel,"pressure":parameters.sound_speed**2*(rho-rho0),"partial_time_density":partial_rho,"density_gradient":grad_rho,"divergence_rho_velocity":div_rho_u,"partial_time_velocity":zeros,"velocity_jacobian":torch.zeros((len(p),2,2),dtype=torch.float64),"velocity_divergence":torch.zeros_like(rho),"density_advection":uc*grad_rho[:,0],"convection":zeros,"velocity_laplacian":zeros,"pressure_gradient":grad_p,"material_acceleration":zeros,"source":source,"continuity_residual":partial_rho+div_rho_u,"momentum_residual":zeros-(-grad_p/rho[:,None]+parameters.viscosity*zeros+source)}


def wrap_position(value:torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    extent=parameters.domain_maximum-parameters.domain_minimum; return torch.remainder(value-parameters.domain_minimum,extent)+parameters.domain_minimum


def exact_particle_trajectory(initial_positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    p,t=validate_points(initial_positions,time); result=p.clone(); result[:,0]=wrap_position(p[:,0]+parameters.translation_speed*t,parameters); return result
