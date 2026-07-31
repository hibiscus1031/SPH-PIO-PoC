"""Unit tests for differentiable Stage 01 numerical metrics."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = PROJECT_ROOT / "05_metrics"


def _load_module(name: str) -> ModuleType:
    module_name = f"_stage01_metrics_{name}"
    spec = importlib.util.spec_from_file_location(
        module_name, METRICS_DIR / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load metric module {name!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


velocity_error = _load_module("velocity_error")
conservation = _load_module("conservation")
energy = _load_module("energy")
density = _load_module("density")
runtime = _load_module("runtime")


def _devices() -> list[str]:
    devices = ["cpu"]
    if torch.backends.mps.is_available():
        devices.append("mps")
    return devices


@pytest.mark.parametrize("device", _devices())
def test_total_momentum_and_energy_match_hand_calculation(device: str) -> None:
    velocity = torch.tensor(
        [[1.0, 2.0], [-2.0, 1.0], [0.5, -1.0]],
        dtype=torch.float32,
        device=device,
        requires_grad=True,
    )
    mass = torch.tensor([2.0, 1.0, 4.0], dtype=torch.float32, device=device)

    momentum = conservation.total_momentum(velocity, mass)
    kinetic = energy.total_kinetic_energy(velocity, mass)

    torch.testing.assert_close(
        momentum, torch.tensor([2.0, 1.0], device=device)
    )
    torch.testing.assert_close(kinetic, torch.tensor(10.0, device=device))

    (momentum.square().sum() + kinetic).backward()
    assert velocity.grad is not None
    assert bool(torch.isfinite(velocity.grad).all())
    assert bool((velocity.grad != 0).any())


@pytest.mark.parametrize("device", _devices())
def test_momentum_metrics_handle_zero_net_reference(device: str) -> None:
    reference = torch.tensor(
        [[1.0, 0.0], [-1.0, 0.0]], dtype=torch.float32, device=device
    )
    identical = reference.clone()
    perturbed = reference.clone()
    perturbed[0, 1] = 0.25

    unchanged = conservation.momentum_metrics(identical, reference)
    changed = conservation.momentum_metrics(perturbed, reference)

    torch.testing.assert_close(
        unchanged["relative_momentum_drift"],
        torch.zeros((), device=device),
    )
    assert bool(torch.isfinite(changed["relative_momentum_drift"]))
    assert bool(changed["relative_momentum_drift"] > 0)


@pytest.mark.parametrize("device", _devices())
def test_velocity_density_and_energy_metrics_preserve_autograd(device: str) -> None:
    velocity = torch.tensor(
        [[1.0, 0.0], [0.0, 1.0]],
        dtype=torch.float32,
        device=device,
        requires_grad=True,
    )
    reference_velocity = torch.tensor(
        [[0.8, 0.0], [0.0, 0.8]], dtype=torch.float32, device=device
    )
    rho = torch.tensor(
        [990.0, 1000.0, 1010.0],
        dtype=torch.float32,
        device=device,
        requires_grad=True,
    )

    velocity_values = velocity_error.velocity_metrics(
        velocity, reference_velocity
    )
    energy_values = energy.kinetic_energy_metrics(
        velocity, reference_velocity
    )
    density_values = density.density_statistics(rho, 1000.0)
    loss = (
        velocity_values["velocity_relative_l2"]
        + velocity_values["velocity_rmse"]
        + energy_values["total_kinetic_energy"]
        + energy_values["kinetic_energy_relative_error"]
        + density_values["relative_density_fluctuation"]
    )
    loss.backward()

    assert velocity.grad is not None
    assert rho.grad is not None
    assert bool(torch.isfinite(velocity.grad).all())
    assert bool(torch.isfinite(rho.grad).all())


@pytest.mark.parametrize("device", _devices())
def test_zero_reference_guards_are_finite(device: str) -> None:
    zero_velocity = torch.zeros((4, 2), dtype=torch.float32, device=device)
    nonzero_velocity = torch.ones((4, 2), dtype=torch.float32, device=device)
    zero_energy = torch.zeros((), dtype=torch.float32, device=device)
    zero_density = torch.zeros(4, dtype=torch.float32, device=device)

    exact = velocity_error.velocity_relative_l2(zero_velocity, zero_velocity)
    nonzero = velocity_error.velocity_relative_l2(
        nonzero_velocity, zero_velocity
    )
    energy_error = energy.relative_energy_error(zero_energy, 0.0)
    density_error = density.relative_density_fluctuation(
        zero_density, 0.0
    )

    torch.testing.assert_close(exact, torch.zeros((), device=device))
    torch.testing.assert_close(energy_error, torch.zeros((), device=device))
    torch.testing.assert_close(density_error, torch.zeros((), device=device))
    assert bool(torch.isfinite(nonzero))
    assert bool(nonzero > 0)


@pytest.mark.parametrize("device", _devices())
def test_nan_inf_diagnostic_stays_on_input_device(device: str) -> None:
    finite = torch.ones(3, dtype=torch.float32, device=device)
    nan_state = torch.tensor([1.0, float("nan")], device=device)
    inf_state = torch.tensor([float("inf")], device=device)

    finite_result = conservation.state_is_finite(finite)
    bad_result = conservation.has_nonfinite(finite, nan_state, inf_state)

    assert finite_result.device.type == device
    assert bad_result.device.type == device
    assert bool(finite_result)
    assert bool(bad_result)


def test_invalid_shapes_and_empty_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="same shape"):
        velocity_error.velocity_rmse(torch.ones(2, 2), torch.ones(2, 3))
    with pytest.raises(ValueError, match="empty"):
        density.density_statistics(torch.empty(0))
    with pytest.raises(ValueError, match="mass must be scalar"):
        conservation.total_momentum(torch.ones(2, 2), torch.ones(2, 2))
    with pytest.raises(ValueError, match="eps must be positive"):
        energy.relative_energy_error(torch.tensor(1.0), 1.0, eps=0.0)


def test_runtime_tracker_statistics_and_validation() -> None:
    tracker = runtime.RuntimeTracker("cpu")
    tracker.record(0.1)
    tracker.record(0.2)
    tracker.record(0.3)
    summary = tracker.summary()

    assert summary.count == 3
    assert summary.total_seconds == pytest.approx(0.6)
    assert summary.mean_seconds == pytest.approx(0.2)
    assert summary.min_seconds == pytest.approx(0.1)
    assert summary.max_seconds == pytest.approx(0.3)
    assert summary.std_seconds > 0
    with pytest.raises(ValueError, match="non-negative"):
        tracker.record(-1.0)
    with pytest.raises(ValueError, match="CUDA"):
        runtime.synchronize_device("cuda")
