import copy
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(STAGE))

from evaluator.acoustic_evaluator import evaluate_acoustic
from evaluator.gate_rules import (
    ACOUSTIC_RUN_IDS,
    SHEAR_RUN_IDS,
    evaluate_acoustic_gates,
    evaluate_shear_gates,
    metric_binding,
)
from evaluator.shear_evaluator import evaluate_shear


CONFIG_SHA = "5025492f21f6b00c33ebc9533d27fbf632668945cba6a6a4a10df115c9ff1fe1"


def _diagnostics():
    return {
        "hard_safety": {
            "pair_force_residual": 0.0,
            "normalized_internal_force_residual": 0.0,
            "force_assembly_defect": 0.0,
            "momentum_update_defect": 0.0,
            "viscous_power_positive_tolerance": 0.0,
            "structural_topology_defects": 0,
            "minimum_separation_over_dx": 1.0,
            "current_rss_bytes": 1,
            "peak_rss_bytes": 1,
            "rss_q4_minus_q1_bytes": 0,
            "rss_q4_over_q1": 1.0,
            "step_time_q4_over_q1": 1.0,
            "source_call_count": 0,
        },
        "topology": {"status": "PASS"},
        "resource": {
            "independent_child_process": True,
            "cyclic_gc_default": True,
            "torch_no_grad": True,
            "in_loop_gc_collect": False,
            "parent_scalar_only": True,
            "child_fully_reclaimed": True,
        },
        "determinism": {"status": "PASS"},
        "viscous_power": -1.0,
    }


def _positions():
    return [[-0.875 + 0.25 * index, -0.875 + 0.25 * index] for index in range(8)]


def _shear_dataset():
    positions = _positions()
    times = [0.0, 0.1, 0.2]
    nu, amplitude, wave_number = 0.02, 0.5, 2.0 * math.pi
    samples = []
    for time in times:
        velocity = [[amplitude * math.sin(wave_number * p[1]) * math.exp(-nu * wave_number**2 * time), 0.0] for p in positions]
        exact_position = [[p[0] + amplitude * math.sin(wave_number * p[1]) * (1.0 - math.exp(-nu * wave_number**2 * time)) / (nu * wave_number**2), p[1]] for p in positions]
        fields = {"position": exact_position, "velocity": velocity, "density": [1.0] * 8, "pressure": [0.0] * 8}
        samples.append({"time": time, "numerical": copy.deepcopy(fields), "reference": copy.deepcopy(fields)})
    return {
        "metadata": {"run_id": "g_shear_n48", "benchmark": "shear", "N": 48, "H_over_dx": 5.5, "dt": 6.25e-5, "t_final": 0.2, "domain_length": 2.0, "rho0": 1.0, "c_s": 20.0, "config_sha256": CONFIG_SHA, "nu": nu, "U_s": amplitude, "k_s": wave_number, "claim": "viscous_transverse_shear_wave_periodic_validation"},
        "samples": samples,
        "weights": [1.0] * 8,
        "diagnostics": _diagnostics(),
    }


def _acoustic_dataset():
    positions = _positions()
    times = [0.0, 0.025, 0.05, 0.075, 0.1]
    rho0, sound_speed, epsilon, wave_number = 1.0, 20.0, 0.005, math.pi
    samples = []
    for time in times:
        density = [rho0 * (1.0 + epsilon * math.cos(wave_number * p[0]) * math.cos(sound_speed * wave_number * time)) for p in positions]
        velocity = [[sound_speed * epsilon * math.sin(wave_number * p[0]) * math.sin(sound_speed * wave_number * time), 0.0] for p in positions]
        pressure = [sound_speed**2 * (value - rho0) for value in density]
        fields = {"position": copy.deepcopy(positions), "velocity": velocity, "density": density, "pressure": pressure}
        samples.append({"time": time, "numerical": copy.deepcopy(fields), "reference": copy.deepcopy(fields)})
    return {
        "metadata": {"run_id": "g_acoustic_e5e3_n48", "benchmark": "acoustic", "N": 48, "H_over_dx": 5.5, "dt": 6.25e-5, "t_final": 0.1, "domain_length": 2.0, "rho0": rho0, "c_s": sound_speed, "config_sha256": CONFIG_SHA, "nu": 0.0, "epsilon": epsilon, "k_a": wave_number, "claim": "linear-acoustic-regime_validation"},
        "samples": samples,
        "weights": [1.0] * 8,
        "diagnostics": _diagnostics(),
    }


def test_exact_synthetic_fixtures_produce_zero_error_without_input_mutation():
    shear_input = _shear_dataset()
    acoustic_input = _acoustic_dataset()
    frozen_shear = copy.deepcopy(shear_input)
    frozen_acoustic = copy.deepcopy(acoustic_input)
    shear = evaluate_shear(shear_input)
    acoustic = evaluate_acoustic(acoustic_input)
    assert shear_input == frozen_shear and acoustic_input == frozen_acoustic
    assert shear["summary"]["velocity_relative_l2"] == 0.0
    assert shear["summary"]["position_relative_l2"] == 0.0
    assert abs(shear["summary"]["decay_rate_relative_error"]) < 1e-14
    assert acoustic["summary"]["density_signal_normalized_l2"] == 0.0
    assert acoustic["summary"]["velocity_signal_normalized_l2"] == 0.0
    assert abs(acoustic["summary"]["phase_speed_relative_error"]) < 1e-14
    assert abs(acoustic["summary"]["mean_momentum_drift"]) < 1e-14


def _shear_gate_result(error, diagnostics):
    return {"summary": {"all_finite": True, "velocity_relative_l2": error, "position_relative_l2": error / 2, "decay_rate_relative_error": error / 2, "density_drift_linf": 0.001, "transverse_leakage": 0.0001}, "diagnostics": diagnostics}


def _acoustic_gate_result(error, ratio, diagnostics, claim="linear-acoustic-regime_validation"):
    return {"summary": {"all_finite": True, "phase_speed_relative_error": error, "density_fundamental_amplitude_relative_error": error, "velocity_fundamental_amplitude_relative_error": error, "one_period_phase_error": error, "density_signal_normalized_l2": error, "velocity_signal_normalized_l2": error, "transverse_leakage": 0.0001, "second_harmonic_ratio": ratio, "claim": claim}, "diagnostics": diagnostics}


def test_gate_rules_bind_all_18_gates_and_accept_consistent_pass_fixtures():
    diagnostics = _diagnostics()
    shear_errors = [0.015, 0.010, 0.005, 0.0101, 0.005]
    shear_runs = {run_id: _shear_gate_result(error, diagnostics) for run_id, error in zip(SHEAR_RUN_IDS, shear_errors)}
    acoustic_errors = [0.03, 0.02, 0.01, 0.0202, 0.01, 0.01, 0.01]
    ratios = [0.0, 0.0, 0.01, 0.0, 0.01, 0.005, 0.02]
    acoustic_runs = {run_id: _acoustic_gate_result(error, ratio, diagnostics) for run_id, error, ratio in zip(ACOUSTIC_RUN_IDS, acoustic_errors, ratios)}
    assert evaluate_shear_gates(shear_runs)["status"] == "PASS"
    assert evaluate_acoustic_gates(acoustic_runs)["status"] == "PASS"
    binding = metric_binding()
    assert set(binding["shear"]) == {f"SHEAR{i}" for i in range(1, 9)}
    assert set(binding["acoustic"]) == {f"ACOUSTIC{i}" for i in range(1, 11)}
    assert json.loads((STAGE / "results/stage01ge_metric_binding.json").read_text()) == binding
