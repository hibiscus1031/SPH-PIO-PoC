"""Frozen Wendland C4 and actual pair-term cutoff probes."""

from __future__ import annotations
import math,torch
from structure_preserving.kernels import wendland_c4_shape,wendland_c4_shape_derivative
from structure_preserving.conservative_pressure import pressure_pair_force
from structure_preserving.conservative_viscosity import viscosity_gamma,viscosity_pair_force

Q_VALUES=(1-1e-4,1-1e-6,1-1e-8,1-1e-10,1.0,1+1e-10,1+1e-8,1+1e-6,1+1e-4)

def cutoff_probe(*,support:float=.5,mass:float=.015625,density_i:float=1.001,density_j:float=.999,pressure_i:float=.4,pressure_j:float=-.4,velocity_difference:tuple[float,float]=(.7,-.3),viscosity:float=.02)->list[dict[str,float]]:
    q=torch.tensor(Q_VALUES,dtype=torch.float64);h=torch.full_like(q,support);r=q*h;inside=q<1
    shape=torch.where(inside,wendland_c4_shape(q),torch.zeros_like(q));derivative=torch.where(inside,wendland_c4_shape_derivative(q),torch.zeros_like(q));kernel=9/(math.pi*h.square())*shape;d_w_dr=9/math.pi*derivative/h.pow(3);gradient=torch.stack((d_w_dr,torch.zeros_like(d_w_dr)),dim=-1)
    scalar=lambda value:torch.full_like(q,value);pressure=pressure_pair_force(scalar(mass),scalar(mass),scalar(density_i),scalar(density_j),scalar(pressure_i),scalar(pressure_j),gradient)
    radial=r*d_w_dr;gamma=viscosity_gamma(scalar(density_i),scalar(density_j),viscosity,radial,r,h);zero_gamma=torch.where(inside,gamma,torch.zeros_like(gamma));dv=torch.tensor(velocity_difference,dtype=torch.float64).expand(len(q),2);visc=viscosity_pair_force(scalar(mass),scalar(mass),torch.zeros_like(dv),dv,zero_gamma)
    rows=[]
    for index,value in enumerate(Q_VALUES):
        rows.append({"q":value,"W":float(kernel[index]),"dW_dr":float(d_w_dr[index]),"gradW_l2":float(torch.linalg.vector_norm(gradient[index])),"pressure_pair_l2":float(torch.linalg.vector_norm(pressure[index])),"viscosity_gamma":float(zero_gamma[index]),"viscosity_pair_l2":float(torch.linalg.vector_norm(visc[index])),"total_pair_l2":float(torch.linalg.vector_norm(pressure[index]+visc[index])),"acceleration_contribution_l2":float(torch.linalg.vector_norm((pressure[index]+visc[index])/mass))})
    return rows
