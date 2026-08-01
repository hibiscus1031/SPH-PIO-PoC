"""Analytic and autograd-reconstructed external acceleration sources."""

from __future__ import annotations
import torch
from manufactured_solutions.exact_derivatives import autograd_fields
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.governing_equations import MMSParameters,PARAMETERS


def manufactured_acceleration(solution:str,positions:torch.Tensor,physical_time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    return solution_module(solution).manual_fields(positions,physical_time,parameters)["source"]


def reconstructed_manufactured_acceleration(solution:str,positions:torch.Tensor,physical_time:float|torch.Tensor,parameters:MMSParameters=PARAMETERS)->torch.Tensor:
    return autograd_fields(solution,positions,physical_time,parameters)["source"]
