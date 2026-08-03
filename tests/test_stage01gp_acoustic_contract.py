import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE_G = ROOT / "06_experiments/stage_01g_validation_design"


def test_frozen_acoustic_theory_parameters_claim_gates_and_ids_are_complete():
    config = yaml.safe_load((STAGE_G / "configs/preregistered_stage01g.yml").read_text())
    acoustic = config["acoustic_wave"]
    params = acoustic["parameters"]
    assert (params["rho0"], params["c_s"], params["nu"], params["k_a"], params["t_final"]) == (1.0, 20.0, 0.0, "pi", 0.1)
    assert params["epsilon_main"] == 0.005
    assert params["epsilon_audit"] == [0.0025, 0.005, 0.01]
    reference = acoustic["linear_reference"]
    assert reference["rho"] == "rho0*(1+epsilon_a*cos(k_a*x)*cos(c_s*k_a*t))"
    assert reference["u_x"] == "c_s*epsilon_a*sin(k_a*x)*sin(c_s*k_a*t)"
    assert reference["u_y"] == "0"
    assert reference["pressure"] == "c_s^2*(rho-rho0)"
    assert reference["project_rk2_used"] is False
    assert reference["sph_residual_correction"] is False
    assert acoustic["claim"] == "linear-acoustic-regime_validation"
    assert "finite_amplitude_nonlinear_exact_solution" in acoustic["excluded_claims"]
    assert set(acoustic["gates"]) == {f"ACOUSTIC{i}" for i in range(1, 11)}

    with (STAGE_G / "manifests/stage01g_run_matrix.csv").open(newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["benchmark"] == "acoustic"]
    assert len(rows) == 7
    assert {float(row["epsilon"]) for row in rows} == {0.0025, 0.005, 0.01}
