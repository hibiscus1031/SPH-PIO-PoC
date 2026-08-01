"""Regular-grid MMS particle mass specification; no rollout is performed."""

from __future__ import annotations
from dataclasses import dataclass
import torch
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.governing_equations import MMSParameters,PARAMETERS


@dataclass(frozen=True)
class ParticleInitialization:
    positions:torch.Tensor
    initial_density:torch.Tensor
    volume:torch.Tensor
    mass:torch.Tensor
    masses_fixed_during_rollout:bool=True
    analytic_density_overwrites_numerical_density:bool=False


def regular_initialization(solution:str,resolution:int,parameters:MMSParameters=PARAMETERS)->ParticleInitialization:
    if resolution<=0: raise ValueError("resolution must be positive")
    dx=2.0/resolution; axis=-1.0+(torch.arange(resolution,dtype=torch.float64)+0.5)*dx; x,y=torch.meshgrid(axis,axis,indexing="ij"); positions=torch.stack((x.reshape(-1),y.reshape(-1)),dim=-1); rho=solution_module(solution).density(positions,0.0,parameters); volume=torch.full_like(rho,dx**2); mass=rho*volume
    return ParticleInitialization(positions=positions,initial_density=rho,volume=volume,mass=mass)
