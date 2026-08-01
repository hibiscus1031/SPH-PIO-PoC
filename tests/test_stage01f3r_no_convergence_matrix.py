from pathlib import Path
import yaml

def test_stage_scope_prohibits_convergence_matrix_and_orders()->None:
    cfg=yaml.safe_load((Path(__file__).resolve().parents[1]/"06_experiments/stage_01f3r_reference_qualification/configs/preregistered_stage01f3r.yml").read_text())
    scope=cfg["scope"]
    assert scope["convergence_matrix_run"] is False and scope["time_order_computed"] is False and scope["space_order_computed"] is False and scope["gci_computed"] is False
