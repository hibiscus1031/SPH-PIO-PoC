"""Dense all-pairs DOP853 semidiscrete-reference adapter."""

from __future__ import annotations
from collections.abc import Sequence
import numpy as np,torch
from manufactured_solutions.dense_all_pairs_rhs import dense_rhs
from manufactured_solutions.semidiscrete_reference import SemidiscreteReference,integrate_semidiscrete_dop853

def integrate_dense_reference(solution_id:str,initial_positions:torch.Tensor,initial_velocity:torch.Tensor,masses:torch.Tensor,supports:torch.Tensor,sample_times:Sequence[float],*,rtol:float,atol:float,max_step:float)->SemidiscreteReference:
    count=len(initial_positions);y0=np.concatenate((initial_positions.numpy().reshape(-1),initial_velocity.numpy().reshape(-1)))
    def rhs(time:float,state:np.ndarray)->np.ndarray:
        positions=torch.from_numpy(state[:2*count].reshape(count,2));velocity=torch.from_numpy(state[2*count:].reshape(count,2))
        with torch.no_grad():dx,dv,_=dense_rhs(solution_id,positions,velocity,masses,supports,time)
        return np.concatenate((dx.numpy().reshape(-1),dv.numpy().reshape(-1)))
    return integrate_semidiscrete_dop853(rhs,y0,sample_times,rtol=rtol,atol=atol,max_step=max_step)
