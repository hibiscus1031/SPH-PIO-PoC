from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy"


def test_default_gc_policy_is_enabled_and_disable_is_prohibited() -> None:
    configuration = yaml.safe_load((ROOT / "configs" / "preregistered_resource_policy.yml").read_text(encoding="utf-8"))
    policy = configuration["formal_runtime_policy"]
    assert policy["python_default_gc_required_enabled"] is True
    assert policy["cyclic_gc_disable_prohibited"] is True
    source = (ROOT / "stage01dp_worker.py").read_text(encoding="utf-8")
    assert "gc.isenabled()" in source
    assert "gc.disable(" not in source
