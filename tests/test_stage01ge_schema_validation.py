import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(STAGE))

from evaluator.common_metrics import MetricContractError
from evaluator.schema import validate_dataset


def _minimal_dataset():
    field = {"position": [[0.0, 0.0]], "velocity": [[0.0, 0.0]], "density": [1.0], "pressure": [0.0]}
    return {
        "metadata": {"run_id": "fixture", "benchmark": "shear", "N": 1, "H_over_dx": 1.0, "dt": 0.1, "t_final": 0.1, "domain_length": 2.0, "rho0": 1.0, "c_s": 20.0, "config_sha256": "5025492f21f6b00c33ebc9533d27fbf632668945cba6a6a4a10df115c9ff1fe1", "nu": 0.02, "U_s": 0.5, "k_s": 6.28, "claim": "fixture"},
        "samples": [{"time": 0.0, "numerical": copy.deepcopy(field), "reference": copy.deepcopy(field)}, {"time": 0.1, "numerical": copy.deepcopy(field), "reference": copy.deepcopy(field)}],
        "diagnostics": {"hard_safety": {}, "topology": {}, "resource": {}, "determinism": {}, "viscous_power": -1.0},
    }


def test_schema_returns_deep_copy_and_rejects_missing_or_misaligned_evidence():
    original = _minimal_dataset()
    validated = validate_dataset(original, "shear")
    validated["samples"][0]["numerical"]["density"][0] = 99.0
    assert original["samples"][0]["numerical"]["density"][0] == 1.0
    missing = _minimal_dataset()
    del missing["samples"][0]["reference"]["pressure"]
    with pytest.raises(MetricContractError):
        validate_dataset(missing, "shear")
    misaligned = _minimal_dataset()
    misaligned["samples"][1]["numerical"]["density"].append(1.0)
    with pytest.raises(MetricContractError):
        validate_dataset(misaligned, "shear")
    wrong_config = _minimal_dataset()
    wrong_config["metadata"]["config_sha256"] = "0" * 64
    with pytest.raises(MetricContractError):
        validate_dataset(wrong_config, "shear")
