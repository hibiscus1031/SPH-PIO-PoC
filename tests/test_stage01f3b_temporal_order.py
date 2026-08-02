import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/"06_experiments/stage_01f3b_mms_convergence/analyze_stage01f3b.py";SPEC=importlib.util.spec_from_file_location("f3b_analysis",PATH);MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)

def test_temporal_order_helpers_recover_second_order()->None:
    dt=[1e-3,5e-4,2.5e-4,1.25e-4,6.25e-5];error=[value**2 for value in dt]
    assert abs(MOD.fitted_order(dt,error)-2)<1e-12
    assert all(abs(value-2)<1e-12 for value in MOD.local_orders(error,dt))
