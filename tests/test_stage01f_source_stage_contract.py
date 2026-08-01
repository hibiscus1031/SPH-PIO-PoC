from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.source_injection_contract import required_stage_evaluations  # noqa:E402


def test_source_is_recomputed_at_numerical_start_and_midpoint_state()->None:
    start=torch.tensor([[.1,.2],[-.3,.4]],dtype=torch.float64); midpoint=start+torch.tensor([[1e-3,-2e-3],[2e-3,1e-3]],dtype=torch.float64); values=required_stage_evaluations(solution="MMS_B",start_numerical_positions=start,start_time=.01,midpoint_numerical_positions=midpoint,midpoint_time=.010125)
    assert [x.stage for x in values]==["start","midpoint"] and values[0].numerical_positions is start and values[1].numerical_positions is midpoint
    assert not torch.equal(values[0].external_acceleration,values[1].external_acceleration)
    assert all(not x.uses_analytic_positions and not x.uses_numerical_residual_feedback and not x.included_in_internal_pair_force for x in values)
