"""Tests for truth-preserving Stage 01 artifact post-processing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from diffsph_adapter import analyze_stage01


def _state_hash(
    positions: np.ndarray,
    velocities: np.ndarray,
    densities: np.ndarray,
) -> str:
    digest = hashlib.sha256()
    for array in (positions[-1], velocities[-1], densities[-1]):
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def _write_run(
    raw: Path,
    *,
    run_id: str,
    metric_offset: float = 0.0,
    velocity_offset: float = 0.0,
) -> str:
    backend = "cpu"
    resolution = 2
    particle_count = 4
    stem = f"{backend}_n{resolution}_{run_id}"
    config = {
        "backend": backend,
        "dtype": "float32",
        "resolution": resolution,
        "particle_count": particle_count,
        "run_id": run_id,
        "seed": 20260731,
        "total_steps": 2,
        "target_dt": 0.05,
        "scheme": "synthetic-test-only",
        "kernel": "synthetic-test-only",
        "n_h": 1,
        "integration_scheme": "synthetic-test-only",
        "solver_configuration": "synthetic-test-only",
        "package_versions": {
            "torch": "test",
            "numpy": "test",
            "scipy": "test",
            "diffSPH": "test",
            "torchCompactRadius": "test",
            "h5py": "test",
            "PyYAML": "test",
        },
        "project_git_hash": "a" * 40,
        "diffsph_commit": "b" * 40,
        "diffsph_installed_python_tree_sha256": "c" * 64,
        "torchcompactradius_installed_python_tree_sha256": "d" * 64,
        "pytorch_mps_fallback_env": "0",
    }
    (raw / f"{stem}_config.json").write_text(
        json.dumps(config, sort_keys=True) + "\n"
    )

    steps = np.asarray([0, 2], dtype=np.int64)
    times = np.asarray([0.0, 0.1], dtype=np.float64)
    base_positions = np.asarray(
        [[-0.5, -0.5], [0.5, -0.5], [-0.5, 0.5], [0.5, 0.5]],
        dtype=np.float32,
    )
    positions = np.stack((base_positions, base_positions + 0.01))
    initial_velocity = np.asarray(
        [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]],
        dtype=np.float32,
    )
    final_velocity = initial_velocity * 0.9 + velocity_offset
    velocities = np.stack((initial_velocity, final_velocity))
    densities = np.asarray(
        [[1.0, 1.0, 1.0, 1.0], [0.99, 1.01, 1.0, 1.0]],
        dtype=np.float32,
    )
    np.savez_compressed(
        raw / f"{stem}_trajectory.npz",
        steps=steps,
        times=times,
        positions=positions,
        velocities=velocities,
        densities=densities,
    )
    final_hash = _state_hash(positions, velocities, densities)

    numerical = pd.DataFrame(
        {
            "backend": [backend, backend],
            "dtype": ["float32", "float32"],
            "resolution": [resolution, resolution],
            "particle_count": [particle_count, particle_count],
            "run_id": [run_id, run_id],
            "seed": [20260731, 20260731],
            "step": steps,
            "time": times,
            "dt": [0.05, 0.05],
            "velocity_relative_l2": [0.0, 0.1 + metric_offset],
            "velocity_rmse": [0.0, 0.05 + metric_offset],
            "total_kinetic_energy": [2.0, 1.62 + metric_offset],
            "kinetic_energy_relative_error": [0.0, 0.01 + metric_offset],
            "kinetic_energy_relative_initial": [0.0, 0.19 + metric_offset],
            "momentum_x": [0.0, 0.001 + metric_offset],
            "momentum_y": [0.0, 0.001 + metric_offset],
            "relative_momentum_drift": [0.0, 0.001 + metric_offset],
            "mean_density": [1.0, 1.0 + metric_offset],
            "min_density": [1.0, 0.99 + metric_offset],
            "max_density": [1.0, 1.01 + metric_offset],
            "relative_density_fluctuation": [0.0, 0.01 + metric_offset],
            "max_particle_speed": [1.0, 0.9 + metric_offset],
            "has_nan_or_inf": [False, False],
            "step_time_seconds": [0.0, 0.002],
        }
    )
    numerical.to_csv(raw / f"{stem}_numerical.csv", index=False)
    runtime = pd.DataFrame(
        [
            {
                "backend": backend,
                "dtype": "float32",
                "resolution": resolution,
                "particle_count": particle_count,
                "run_id": run_id,
                "seed": 20260731,
                "record_type": "summary",
                "measured_steps": 2,
                "mean_step_seconds": 0.002,
                "total_wall_seconds": 0.004,
                "first_nonfinite_step": np.nan,
                "pytorch_mps_fallback": False,
                "unsupported_operator": False,
                "final_state_sha256": final_hash,
            }
        ]
    )
    runtime.to_csv(raw / f"{stem}_runtime.csv", index=False)
    return stem


def _write_stability_run(raw: Path) -> str:
    """Write a wall-time run whose terminal state is newer than its snapshots."""

    backend = "cpu"
    resolution = 2
    particle_count = 4
    run_id = "stability-0.5s"
    stem = f"{backend}_n{resolution}_{run_id}"
    config = {
        "backend": backend,
        "dtype": "float32",
        "resolution": resolution,
        "particle_count": particle_count,
        "run_id": run_id,
        "seed": 20260731,
        # The wall-time loop intentionally runs beyond this short-run value.
        "total_steps": 2,
        "target_dt": 0.05,
        "scheme": "synthetic-stability-test-only",
        "kernel": "synthetic-stability-test-only",
        "n_h": 1,
        "integration_scheme": "synthetic-stability-test-only",
        "solver_configuration": "synthetic-stability-test-only",
        "package_versions": {
            "torch": "test",
            "numpy": "test",
            "scipy": "test",
            "diffSPH": "test",
            "torchCompactRadius": "test",
            "h5py": "test",
            "PyYAML": "test",
        },
        "project_git_hash": "a" * 40,
        "diffsph_commit": "b" * 40,
        "diffsph_installed_python_tree_sha256": "c" * 64,
        "torchcompactradius_installed_python_tree_sha256": "d" * 64,
        "pytorch_mps_fallback_env": "0",
    }
    (raw / f"{stem}_config.json").write_text(
        json.dumps(config, sort_keys=True) + "\n"
    )
    steps = np.asarray([0, 2, 4], dtype=np.int64)
    times = np.asarray([0.0, 0.1, 0.2], dtype=np.float64)
    base_positions = np.asarray(
        [[-0.5, -0.5], [0.5, -0.5], [-0.5, 0.5], [0.5, 0.5]],
        dtype=np.float32,
    )
    positions = np.stack(
        (base_positions, base_positions + 0.01, base_positions + 0.02)
    )
    initial_velocity = np.asarray(
        [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]],
        dtype=np.float32,
    )
    velocities = np.stack(
        (initial_velocity, initial_velocity * 0.9, initial_velocity * 0.8)
    )
    densities = np.asarray(
        [
            [1.0, 1.0, 1.0, 1.0],
            [0.99, 1.01, 1.0, 1.0],
            [0.98, 1.02, 1.0, 1.0],
        ],
        dtype=np.float32,
    )
    np.savez_compressed(
        raw / f"{stem}_trajectory.npz",
        steps=steps,
        times=times,
        positions=positions,
        velocities=velocities,
        densities=densities,
    )
    numerical = pd.DataFrame(
        {
            "backend": [backend] * 3,
            "dtype": ["float32"] * 3,
            "resolution": [resolution] * 3,
            "particle_count": [particle_count] * 3,
            "run_id": [run_id] * 3,
            "seed": [20260731] * 3,
            "step": steps,
            "time": times,
            "dt": [0.05] * 3,
            "velocity_relative_l2": [0.0, 0.1, 0.2],
            "velocity_rmse": [0.0, 0.05, 0.1],
            "total_kinetic_energy": [2.0, 1.62, 1.28],
            "kinetic_energy_relative_error": [0.0, 0.01, 0.02],
            "kinetic_energy_relative_initial": [0.0, 0.19, 0.36],
            "momentum_x": [0.0, 0.001, 0.002],
            "momentum_y": [0.0, 0.001, 0.002],
            "relative_momentum_drift": [0.0, 0.001, 0.002],
            "mean_density": [1.0, 1.0, 1.0],
            "min_density": [1.0, 0.99, 0.98],
            "max_density": [1.0, 1.01, 1.02],
            "relative_density_fluctuation": [0.0, 0.01, 0.02],
            "max_particle_speed": [1.0, 0.9, 0.8],
            "has_nan_or_inf": [False, False, False],
            "step_time_seconds": [0.0, 0.1, 0.1],
        }
    )
    numerical.to_csv(raw / f"{stem}_numerical.csv", index=False)

    # The summary hash represents step 6, which is deliberately not present
    # in the fixed-interval trajectory ending at step 4.
    terminal_state_hash = "f" * 64
    runtime = pd.DataFrame(
        [
            {
                "backend": backend,
                "dtype": "float32",
                "resolution": resolution,
                "particle_count": particle_count,
                "run_id": run_id,
                "seed": 20260731,
                "record_type": "summary",
                "measured_steps": 6,
                "mean_step_seconds": 0.1,
                "total_wall_seconds": 0.6,
                "first_nonfinite_step": np.nan,
                "pytorch_mps_fallback": False,
                "unsupported_operator": False,
                "final_state_sha256": terminal_state_hash,
                "sustain_target_seconds": 0.5,
                "segment_end_seconds": np.nan,
                "segment_steps": np.nan,
            },
            {
                "backend": backend,
                "dtype": np.nan,
                "resolution": resolution,
                "particle_count": particle_count,
                "run_id": run_id,
                "seed": np.nan,
                "record_type": "segment",
                "measured_steps": np.nan,
                "mean_step_seconds": 0.1,
                "total_wall_seconds": np.nan,
                "first_nonfinite_step": np.nan,
                "pytorch_mps_fallback": np.nan,
                "unsupported_operator": np.nan,
                "final_state_sha256": np.nan,
                "sustain_target_seconds": np.nan,
                "segment_end_seconds": 0.3,
                "segment_steps": 3,
            },
            {
                "backend": backend,
                "dtype": np.nan,
                "resolution": resolution,
                "particle_count": particle_count,
                "run_id": run_id,
                "seed": np.nan,
                "record_type": "segment",
                "measured_steps": np.nan,
                "mean_step_seconds": 0.1,
                "total_wall_seconds": np.nan,
                "first_nonfinite_step": np.nan,
                "pytorch_mps_fallback": np.nan,
                "unsupported_operator": np.nan,
                "final_state_sha256": np.nan,
                "sustain_target_seconds": np.nan,
                "segment_end_seconds": 0.6,
                "segment_steps": 3,
            },
        ]
    )
    runtime.to_csv(raw / f"{stem}_runtime.csv", index=False)
    return stem


def test_analysis_aggregates_repeats_and_creates_all_figures(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    reports = tmp_path / "reports"
    figures = tmp_path / "figures"
    raw.mkdir()
    first = _write_run(raw, run_id="run-1")
    second = _write_run(raw, run_id="run-2")
    stability = _write_stability_run(raw)
    (raw / "cpu_n2_pre-reference-fix_numerical.csv").write_text("ignored\n")

    summary = analyze_stage01.analyze(raw, reports, figures)

    assert summary["valid_runs"] == [first, second, stability]
    assert summary["canonical_runs"] == [first, second]
    assert summary["stability_runs"] == [stability]
    assert summary["figure_runs"] == [first, second]
    assert set(summary["excluded_runs"]) == {"cpu_n2_pre-reference-fix"}
    numerical = pd.read_csv(reports / "stage_01_numerical_metrics.csv")
    runtime = pd.read_csv(reports / "stage_01_runtime_metrics.csv")
    assert len(numerical) == 7
    assert len(runtime) == 5
    assert set(numerical["analysis_role"]) == {"canonical", "stability"}
    canonical_runtime = runtime[runtime["analysis_role"] == "canonical"]
    stability_numerical = numerical[numerical["analysis_role"] == "stability"]
    stability_runtime = runtime[runtime["analysis_role"] == "stability"]
    assert canonical_runtime["analysis_config_sha256"].nunique() == 1
    assert set(canonical_runtime["analysis_repeat_count"]) == {2}
    assert set(canonical_runtime["analysis_repeat_status"]) == {
        "EXACT_STATE_HASH_AND_METRICS_MATCH"
    }
    assert set(canonical_runtime["analysis_repeat_final_state_hash_match"]) == {True}
    assert set(canonical_runtime["analysis_repeat_max_abs_metric_difference"]) == {
        0.0
    }
    assert stability_numerical["step"].tolist() == [0, 2, 4]
    assert stability_runtime["record_type"].tolist() == [
        "summary",
        "segment",
        "segment",
    ]
    assert set(stability_runtime["analysis_repeat_status"]) == {
        "NOT_APPLICABLE_STABILITY"
    }
    assert set(stability_runtime["analysis_stability_measured_steps"]) == {6}
    assert set(stability_runtime["analysis_stability_last_numerical_step"]) == {4}
    assert set(stability_runtime["analysis_stability_target_met"]) == {True}
    assert stability_runtime["analysis_source_runtime_sha256"].str.len().eq(64).all()
    assert (
        stability_numerical["analysis_source_trajectory_sha256"]
        .str.len()
        .eq(64)
        .all()
    )
    for filename in analyze_stage01.FIGURE_FILENAMES:
        path = figures / filename
        assert path.is_file()
        assert path.stat().st_size > 0


def test_repeat_audit_exposes_hash_and_metric_differences(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_run(raw, run_id="run-1")
    _write_run(
        raw,
        run_id="run-2",
        metric_offset=0.02,
        velocity_offset=0.05,
    )

    discovery = analyze_stage01.discover_runs(raw)
    _, runtime = analyze_stage01.build_aggregate_frames(discovery.runs)

    assert set(runtime["analysis_repeat_status"]) == {"REPEAT_DIFFERENCE"}
    assert set(runtime["analysis_repeat_final_state_hash_match"]) == {False}
    assert set(runtime["analysis_repeat_metrics_within_tolerance"]) == {False}
    assert (
        runtime["analysis_repeat_max_abs_diff_velocity_relative_l2"].min()
        == pytest.approx(0.02)
    )


def test_stability_fallback_is_rejected(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    stem = _write_stability_run(raw)
    runtime_path = raw / f"{stem}_runtime.csv"
    runtime = pd.read_csv(runtime_path)
    runtime.loc[runtime["record_type"] == "summary", "pytorch_mps_fallback"] = True
    runtime.to_csv(runtime_path, index=False)

    discovery = analyze_stage01.discover_runs(raw)

    assert not discovery.runs
    assert "pytorch_mps_fallback=True" in discovery.invalid[stem]


def test_no_valid_run_preserves_existing_report(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    reports = tmp_path / "reports"
    figures = tmp_path / "figures"
    raw.mkdir()
    reports.mkdir()
    existing = reports / "stage_01_numerical_metrics.csv"
    existing.write_text("do-not-overwrite\n")
    (raw / "cpu_n2_pre-reference-fix_numerical.csv").write_text("ignored\n")

    with pytest.raises(analyze_stage01.AnalysisError, match="no valid Stage 01"):
        analyze_stage01.analyze(raw, reports, figures)

    assert existing.read_text() == "do-not-overwrite\n"
    assert not figures.exists()
