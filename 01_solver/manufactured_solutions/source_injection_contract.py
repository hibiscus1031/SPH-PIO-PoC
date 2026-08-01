"""Unconnected interface contract for future start/midpoint source evaluation."""

from __future__ import annotations
from dataclasses import dataclass
import torch
from manufactured_solutions.governing_equations import MMSParameters,PARAMETERS
from manufactured_solutions.source_terms import manufactured_acceleration


@dataclass(frozen=True)
class SourceStageEvaluation:
    stage:str
    physical_time:float
    numerical_positions:torch.Tensor
    external_acceleration:torch.Tensor
    uses_analytic_positions:bool=False
    uses_numerical_residual_feedback:bool=False
    included_in_internal_pair_force:bool=False


def evaluate_source_stage(*,solution:str,stage:str,numerical_positions:torch.Tensor,physical_stage_time:float,parameters:MMSParameters=PARAMETERS)->SourceStageEvaluation:
    if stage not in ("start","midpoint"): raise ValueError("stage must be start or midpoint")
    acceleration=manufactured_acceleration(solution,numerical_positions,physical_stage_time,parameters)
    return SourceStageEvaluation(stage=stage,physical_time=float(physical_stage_time),numerical_positions=numerical_positions,external_acceleration=acceleration)


def required_stage_evaluations(*,solution:str,start_numerical_positions:torch.Tensor,start_time:float,midpoint_numerical_positions:torch.Tensor,midpoint_time:float,parameters:MMSParameters=PARAMETERS)->tuple[SourceStageEvaluation,SourceStageEvaluation]:
    return (evaluate_source_stage(solution=solution,stage="start",numerical_positions=start_numerical_positions,physical_stage_time=start_time,parameters=parameters),evaluate_source_stage(solution=solution,stage="midpoint",numerical_positions=midpoint_numerical_positions,physical_stage_time=midpoint_time,parameters=parameters))
