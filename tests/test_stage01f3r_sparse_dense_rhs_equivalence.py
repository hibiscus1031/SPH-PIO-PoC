from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters,evaluate_internal_acceleration
from dynamic_solver.sourced_acceleration import initialize_mms_state
from manufactured_solutions.dense_all_pairs_rhs import evaluate_dense_all_pairs
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.sparse_dense_equivalence import difference_metrics,equivalence_gate

def test_initial_sparse_dense_rhs_equivalence()->None:
    for solution in ("MMS_A","MMS_B"):
        state=initialize_mms_state(solution,16,support_ratio=(4+17**.5)/2);sparse=evaluate_internal_acceleration(state,DynamicPhysicalParameters());dense=evaluate_dense_all_pairs(solution,state.positions,state.velocities,state.masses,state.supports,0.)
        comparisons={"density":difference_metrics(sparse.densities,dense.density),"pressure":difference_metrics(sparse.pressures,dense.pressure),"total_acceleration":difference_metrics(sparse.acceleration+evaluate_mms_source(solution,state.positions,0.),dense.total_acceleration)}
        assert all(equivalence_gate(comparisons).values())
