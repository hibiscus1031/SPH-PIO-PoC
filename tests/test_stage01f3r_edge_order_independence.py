from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from dynamic_solver.sourced_acceleration import initialize_mms_state
from manufactured_solutions.dense_all_pairs_rhs import evaluate_dense_all_pairs,dense_kernel_geometry

def test_dense_aggregation_is_order_independent_to_roundoff()->None:
    state=initialize_mms_state("MMS_B",16,support_ratio=(4+17**.5)/2);base=evaluate_dense_all_pairs("MMS_B",state.positions,state.velocities,state.masses,state.supports,0.)
    geometry=dense_kernel_geometry(state.positions,state.supports);pairs=int(torch.count_nonzero(torch.triu(geometry["included"],diagonal=1)));order=torch.randperm(pairs,generator=torch.Generator().manual_seed(31))
    shuffled=evaluate_dense_all_pairs("MMS_B",state.positions,state.velocities,state.masses,state.supports,0.,pair_order=order)
    assert float((base.total_acceleration-shuffled.total_acceleration).abs().max())<=1e-14
