"""Frozen continuum equation and parameter contract for Stage 01F."""

from __future__ import annotations

from dataclasses import dataclass
import math
import torch


@dataclass(frozen=True)
class MMSParameters:
    rho0: float = 1.0
    sound_speed: float = 20.0
    viscosity: float = 0.02
    wave_number: float = math.pi
    density_amplitude: float = 0.0025
    translation_speed: float = 0.5
    decay_rate: float = 0.7
    vortex_amplitude: float = 1.0
    domain_minimum: float = -1.0
    domain_maximum: float = 1.0

    @property
    def density_minimum(self) -> float: return self.rho0*(1.0-self.density_amplitude)
    @property
    def density_maximum(self) -> float: return self.rho0*(1.0+self.density_amplitude)


PARAMETERS=MMSParameters()


def validate_points(positions:torch.Tensor,time:float|torch.Tensor)->tuple[torch.Tensor,torch.Tensor]:
    if not torch.is_tensor(positions) or positions.ndim!=2 or positions.shape[1]!=2: raise ValueError("positions must have shape [points,2]")
    if positions.dtype!=torch.float64 or positions.device.type!="cpu": raise ValueError("positions must be float64 on CPU")
    times=torch.as_tensor(time,dtype=torch.float64,device="cpu")
    if times.numel()==1: times=times.reshape(1).expand(positions.shape[0])
    elif times.shape!=(positions.shape[0],): raise ValueError("time must be scalar or [points]")
    if not bool(torch.isfinite(positions).all() and torch.isfinite(times).all()): raise ValueError("points and times must be finite")
    return positions,times


def momentum_residual(*,partial_time_velocity:torch.Tensor,convection:torch.Tensor,density:torch.Tensor,pressure_gradient:torch.Tensor,velocity_laplacian:torch.Tensor,source:torch.Tensor,viscosity:float)->torch.Tensor:
    return partial_time_velocity+convection-(-pressure_gradient/density[:,None]+viscosity*velocity_laplacian+source)


def external_momentum_rate(mass:torch.Tensor,source:torch.Tensor)->torch.Tensor:
    """Target external momentum rate; internal pair-force balance is separate."""
    return torch.sum(mass[:,None]*source,dim=0)
