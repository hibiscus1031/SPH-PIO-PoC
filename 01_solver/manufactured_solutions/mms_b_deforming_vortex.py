"""MMS-B: a divergence-free decaying vortex tangent to density contours."""

from __future__ import annotations

import torch
from manufactured_solutions.governing_equations import MMSParameters,PARAMETERS,validate_points


def density(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    p,_=validate_points(positions,time); k=parameters.wave_number
    return parameters.rho0*(1+parameters.density_amplitude*torch.sin(k*p[:,0])*torch.sin(k*p[:,1]))


def amplitude(time:torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor: return parameters.vortex_amplitude*torch.exp(-parameters.decay_rate*time)


def velocity(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    p,t=validate_points(positions,time); k=parameters.wave_number; a=amplitude(t,parameters); x,y=p[:,0],p[:,1]
    return a[:,None]*torch.stack((torch.sin(k*x)*torch.cos(k*y),-torch.cos(k*x)*torch.sin(k*y)),dim=-1)


def pressure(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    return parameters.sound_speed**2*(density(positions,time,parameters)-parameters.rho0)


def manual_fields(positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->dict[str,torch.Tensor]:
    p,t=validate_points(positions,time); k=parameters.wave_number; x,y=p[:,0],p[:,1]; sx,cx=torch.sin(k*x),torch.cos(k*x); sy,cy=torch.sin(k*y),torch.cos(k*y); a=amplitude(t,parameters); rho=density(p,t,parameters); vel=velocity(p,t,parameters)
    grad_rho=parameters.rho0*parameters.density_amplitude*k*torch.stack((cx*sy,sx*cy),dim=-1); jac=torch.stack((torch.stack((a*k*cx*cy,-a*k*sx*sy),dim=-1),torch.stack((a*k*sx*sy,-a*k*cx*cy),dim=-1)),dim=1)
    partial_u=-parameters.decay_rate*vel; convection=(a.square()*k/2)[:,None]*torch.stack((torch.sin(2*k*x),torch.sin(2*k*y)),dim=-1); laplacian=-2*k**2*vel; grad_p=parameters.sound_speed**2*grad_rho; source=partial_u+convection+grad_p/rho[:,None]-parameters.viscosity*laplacian; div_u=jac[:,0,0]+jac[:,1,1]; density_advection=torch.sum(vel*grad_rho,dim=-1); zeros=torch.zeros_like(rho)
    momentum=partial_u+convection-(-grad_p/rho[:,None]+parameters.viscosity*laplacian+source)
    return {"density":rho,"velocity":vel,"pressure":parameters.sound_speed**2*(rho-parameters.rho0),"partial_time_density":zeros,"density_gradient":grad_rho,"divergence_rho_velocity":rho*div_u+density_advection,"partial_time_velocity":partial_u,"velocity_jacobian":jac,"velocity_divergence":div_u,"density_advection":density_advection,"convection":convection,"velocity_laplacian":laplacian,"pressure_gradient":grad_p,"material_acceleration":partial_u+convection,"source":source,"continuity_residual":rho*div_u+density_advection,"momentum_residual":momentum}
