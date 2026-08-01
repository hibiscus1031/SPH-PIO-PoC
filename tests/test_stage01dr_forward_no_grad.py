from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import torch
import yaml

from resource_diagnostics import rollout_memory_probe as probe
from resource_diagnostics.rollout_memory_probe import ProbeArtifacts
from resource_diagnostics.rss_sampler import MemorySampler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01dr_memory_diagnosis"
    / "configs"
    / "preregistered_memory_diagnosis.yml"
)


def _short_configuration() -> dict:
    configuration = deepcopy(yaml.safe_load(CONFIG_PATH.read_text()))
    configuration["resolutions"][16]["steps"] = 1
    configuration["warmup"]["post_warmup_last_step"] = 1
    configuration["sampling"]["mandatory_solver_steps"] = [0, 1]
    configuration["sampling"]["stage01d_diagnostic_steps"] = []
    configuration["sampling"]["minimal_safety_audit_steps"] = []
    configuration["sampling"]["tensor_inventory_steps"] = []
    configuration["sampling"]["tensor_inventory_phases"] = []
    configuration["sampling"]["archive_checkpoint_steps"] = [0, 1]
    return configuration


@pytest.mark.parametrize("variant", ("A", "B", "C"))
def test_qualifying_forward_wraps_prepare_and_step_in_no_grad(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variant: str,
) -> None:
    configuration = _short_configuration()
    observed_grad_modes: list[bool] = []
    output_grad_functions: list[object | None] = []
    original_initialize = probe._initialize_state
    original_prepare = probe.prepare_dynamic_state
    original_step = probe.explicit_midpoint_dynamic_step

    def differentiable_initialize(*args, **kwargs):
        state, parameters, dx, dt = original_initialize(*args, **kwargs)
        state = state.with_updates(
            positions=state.positions.detach().clone().requires_grad_(True),
            velocities=state.velocities.detach().clone().requires_grad_(True),
        )
        return state, parameters, dx, dt

    def prepare_spy(*args, **kwargs):
        observed_grad_modes.append(torch.is_grad_enabled())
        return original_prepare(*args, **kwargs)

    def step_spy(*args, **kwargs):
        observed_grad_modes.append(torch.is_grad_enabled())
        result = original_step(*args, **kwargs)
        output_grad_functions.extend(
            (result.state.positions.grad_fn, result.state.velocities.grad_fn)
        )
        return result

    def lightweight_sample(*args, **kwargs):
        return {"current_rss_bytes": 1, "peak_rss_bytes": 1}, None

    monkeypatch.setattr(probe, "_initialize_state", differentiable_initialize)
    monkeypatch.setattr(probe, "prepare_dynamic_state", prepare_spy)
    monkeypatch.setattr(probe, "explicit_midpoint_dynamic_step", step_spy)
    monkeypatch.setattr(probe, "sample_memory_checkpoint", lightweight_sample)
    sampler = MemorySampler(run_id=f"test_{variant}", particle_count=256)
    artifacts = ProbeArtifacts()

    with torch.enable_grad():
        summary = probe.run_qualifying_probe(
            configuration=configuration,
            run_id=f"test_{variant}",
            variant=variant,
            resolution=16,
            config_hash="0" * 64,
            git_hash="0" * 40,
            sampler=sampler,
            artifacts=artifacts,
            archive_path=(tmp_path / "state.npz" if variant == "C" else None),
        )

    assert summary["torch_no_grad"] is True
    assert observed_grad_modes and not any(observed_grad_modes)
    assert output_grad_functions and all(value is None for value in output_grad_functions)
