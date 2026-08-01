from hashlib import sha256
from pathlib import Path
import yaml


def test_fixed_physics_and_source_hashes() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml").read_text())
    p = cfg["physics"]
    assert (p["reference_density"], p["velocity_amplitude"], p["physical_viscosity"], p["reynolds_number"], p["device"], p["dtype"]) == (1.0, 1.0, 0.02, 100.0, "cpu", "float64")
    assert all(p["prohibited_features"].values())
    for name, expected in cfg["fixed_source_sha256"].items():
        assert sha256((root / name).read_bytes()).hexdigest() == expected
