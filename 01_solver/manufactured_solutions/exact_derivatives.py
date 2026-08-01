"""Independent PyTorch-autograd reconstruction of MMS derivatives."""

from __future__ import annotations
import torch
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.governing_equations import MMSParameters,PARAMETERS,validate_points


def _gradient(output:torch.Tensor,inputs:torch.Tensor,*,create_graph:bool=True)->torch.Tensor:
    if not output.requires_grad:
        return torch.zeros_like(inputs)
    value=torch.autograd.grad(output,inputs,grad_outputs=torch.ones_like(output),create_graph=create_graph,retain_graph=True,allow_unused=True)[0]
    return torch.zeros_like(inputs) if value is None else value


def autograd_fields(solution:str,positions:torch.Tensor,time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->dict[str,torch.Tensor]:
    base_p,base_t=validate_points(positions,time); p=base_p.detach().clone().requires_grad_(True); t=base_t.detach().clone().requires_grad_(True); module=solution_module(solution)
    rho=module.density(p,t,parameters); vel=module.velocity(p,t,parameters); pressure=module.pressure(p,t,parameters)
    grad_rho=_gradient(rho,p); dt_rho=_gradient(rho,t); grad_p=_gradient(pressure,p)
    jac=[]; dt_u=[]; lap=[]
    for component in range(2):
        first=_gradient(vel[:,component],p); jac.append(first); dt_u.append(_gradient(vel[:,component],t))
        second=[]
        for dimension in range(2): second.append(_gradient(first[:,dimension],p)[:,dimension])
        lap.append(second[0]+second[1])
    jacobian=torch.stack(jac,dim=1); partial_u=torch.stack(dt_u,dim=-1); laplacian=torch.stack(lap,dim=-1); divergence=jacobian[:,0,0]+jacobian[:,1,1]; advection=torch.sum(vel*grad_rho,dim=-1); convection=torch.einsum("nd,ncd->nc",vel,jacobian)
    flux_x=rho*vel[:,0]; flux_y=rho*vel[:,1]; div_flux=_gradient(flux_x,p)[:,0]+_gradient(flux_y,p)[:,1]
    source=partial_u+convection+grad_p/rho[:,None]-parameters.viscosity*laplacian
    return {"density":rho,"velocity":vel,"pressure":pressure,"partial_time_density":dt_rho,"density_gradient":grad_rho,"divergence_rho_velocity":div_flux,"partial_time_velocity":partial_u,"velocity_jacobian":jacobian,"velocity_divergence":divergence,"density_advection":advection,"convection":convection,"velocity_laplacian":laplacian,"pressure_gradient":grad_p,"material_acceleration":partial_u+convection,"source":source,"continuity_residual":dt_rho+div_flux,"momentum_residual":partial_u+convection-(-grad_p/rho[:,None]+parameters.viscosity*laplacian+source)}
