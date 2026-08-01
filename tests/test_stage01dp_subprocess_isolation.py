from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_three_serial_workers_and_scalar_only_parent_contract() -> None:
    campaign = _load("stage01dp_campaign_test", ROOT / "run_stage01dp_campaign.py")
    configuration = yaml.safe_load((ROOT / "configs" / "preregistered_resource_policy.yml").read_text(encoding="utf-8"))
    assert campaign.planned_repeats(configuration) == (1, 2, 3)
    assert campaign.is_scalar_summary({"status": "PASS", "rss": 1, "path": "relative/path.json"})
    assert not campaign.is_scalar_summary({"tensor_like": [1, 2, 3]})
    policy = configuration["formal_runtime_policy"]
    assert policy["one_trajectory_per_independent_subprocess"] is True
    assert policy["parent_receives_tensor_or_full_state"] is False
