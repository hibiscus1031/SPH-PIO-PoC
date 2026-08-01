from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import yaml

from resource_diagnostics.rollout_memory_probe import (
    ProbeArtifacts,
    run_frozen_state_regression,
    run_qualifying_probe,
)
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
    configuration["resolutions"][16]["steps"] = 2
    configuration["warmup"]["post_warmup_last_step"] = 2
    configuration["sampling"]["solver_step_interval"] = 1
    configuration["sampling"]["mandatory_solver_steps"] = [0, 1, 2]
    configuration["sampling"]["stage01d_diagnostic_steps"] = []
    configuration["sampling"]["minimal_safety_audit_steps"] = [0, 2]
    configuration["sampling"]["tensor_inventory_steps"] = []
    configuration["sampling"]["tensor_inventory_phases"] = []
    configuration["sampling"]["archive_checkpoint_steps"] = [0, 1, 2]
    return configuration


def test_archive_exists_only_for_variant_c_and_is_written_after_solver(
    tmp_path: Path,
) -> None:
    configuration = _short_configuration()
    for variant in ("A", "B", "C"):
        archive = tmp_path / f"{variant}.npz"
        sampler = MemorySampler(run_id=f"archive_{variant}", particle_count=256)
        artifacts = ProbeArtifacts()
        summary = run_qualifying_probe(
            configuration=configuration,
            run_id=f"archive_{variant}",
            variant=variant,
            resolution=16,
            config_hash="0" * 64,
            git_hash="0" * 40,
            sampler=sampler,
            artifacts=artifacts,
            archive_path=archive if variant == "C" else None,
        )
        phases = [row["phase"] for row in sampler.rows]
        assert phases.index("before_archive") < phases.index("after_archive")
        if variant in {"A", "B"}:
            assert not archive.exists()
            assert summary["archive_write_count"] == 0
        else:
            assert archive.is_file()
            assert summary["archive_write_count"] == 1
            assert not archive.with_name(archive.name + ".tmp.npz").exists()
            with np.load(archive, allow_pickle=False) as state:
                assert set(state.files) == {
                    "steps",
                    "times",
                    "positions",
                    "velocities",
                    "densities",
                    "pressures",
                }
                assert state["steps"].tolist() == [0, 1, 2]
                assert state["positions"].shape == (3, 256, 2)
                assert state["positions"].dtype == np.float64


def test_frozen_first_four_steps_reproduce_bitwise_for_n16_and_n32() -> None:
    configuration = yaml.safe_load(CONFIG_PATH.read_text())
    for resolution in (16, 32):
        rows = run_frozen_state_regression(
            configuration=configuration,
            resolution=resolution,
        )
        assert len(rows) == 20
        assert all(row["shape_exact"] for row in rows)
        assert all(row["dtype_exact"] for row in rows)
        assert all(row["bitwise_equal"] for row in rows)
        assert all(row["within_preregistered_tolerance"] for row in rows)
