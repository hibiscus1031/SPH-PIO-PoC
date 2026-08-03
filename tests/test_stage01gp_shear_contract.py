import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE_G = ROOT / "06_experiments/stage_01g_validation_design"


def test_frozen_shear_parameters_reference_metrics_gates_and_ids_are_complete():
    config = yaml.safe_load((STAGE_G / "configs/preregistered_stage01g.yml").read_text())
    shear = config["shear_wave"]
    assert shear["parameters"] == {
        "rho0": 1.0, "c_s": 20.0, "nu": 0.02, "U_s": 0.5,
        "k_s": "2*pi", "t_final": 0.2,
    }
    exact = shear["exact_reference"]
    assert exact["rho"] == "rho0"
    assert exact["pressure"] == "0"
    assert exact["u_x"] == "U_s*sin(k_s*y)*exp(-nu*k_s^2*t)"
    assert exact["u_y"] == "0"
    assert "x0+" in exact["x_unwrapped"] and exact["y_unwrapped"] == "y0"
    assert exact["kind"] == "closed_form_continuum_and_unwrapped_trajectory"
    assert exact["project_rk2_used"] is False
    assert exact["sph_residual_correction"] is False
    assert set(shear["gates"]) == {f"SHEAR{i}" for i in range(1, 9)}
    metrics = set(shear["metrics"])
    for required in ("velocity_vector_L2_Linf", "particle_position_periodic_L2_Linf", "fitted_decay_rate", "amplitude_ratio", "density_L2_Linf_drift", "pressure_L2_Linf", "transverse_leakage_L2_over_U_s", "momentum", "viscous_power", "topology_resource_determinism"):
        assert required in metrics

    with (STAGE_G / "manifests/stage01g_run_matrix.csv").open(newline="") as stream:
        ids = {row["run_id"] for row in csv.DictReader(stream) if row["benchmark"] == "shear"}
    assert ids == {"g_shear_n24", "g_shear_n32", "g_shear_n48", "g_shear_n32_dt_half", "g_shear_n48_rep2"}
