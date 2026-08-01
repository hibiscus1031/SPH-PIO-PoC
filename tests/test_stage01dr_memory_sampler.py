from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = (
    PROJECT_ROOT / "06_experiments" / "stage_01dr_memory_diagnosis"
)
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from analyze_memory_diagnosis import (  # noqa: E402
    _classify_repeated_n32_growth,
    _derive_resource_status,
    _variant_rows,
)
from resource_diagnostics.rollout_memory_probe import (  # noqa: E402
    sample_memory_checkpoint,
)


def test_memory_sampler_separates_current_and_peak_and_tracks_allocation() -> None:
    code = r'''
import json
from resource_diagnostics.rss_sampler import MemorySampler
s = MemorySampler(run_id="sampler_child", particle_count=0)
b = s.sample(phase="baseline", step=None, edge_count=None)
payload = bytearray(64 * 1024 * 1024)
for i in range(0, len(payload), 4096):
    payload[i] = 1
a = s.sample(phase="allocated", step=None, edge_count=None)
print(json.dumps({"before": b, "after": a}, allow_nan=False))
'''
    environment = {
        **dict(__import__("os").environ),
        "PYTHONPATH": str(PROJECT_ROOT / "01_solver"),
    }
    output = subprocess.check_output(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
    )
    evidence = json.loads(output)
    before = evidence["before"]
    after = evidence["after"]
    assert before["current_rss_bytes"] > 0
    assert before["current_vms_bytes"] > 0
    assert after["current_rss_bytes"] - before["current_rss_bytes"] > 16 * 1024**2
    assert (
        after["tracemalloc_current_bytes"]
        - before["tracemalloc_current_bytes"]
        > 60 * 1024**2
    )
    assert after["peak_rss_bytes"] >= after["current_rss_bytes"]
    assert after["minor_page_faults"] >= before["minor_page_faults"]
    assert after["major_page_faults"] >= before["major_page_faults"]
    json.dumps(evidence, allow_nan=False)


def test_online_resource_safety_uses_current_rss_and_consecutive_pressure() -> None:
    configuration = yaml.safe_load(
        (
            EXPERIMENT_ROOT
            / "configs"
            / "preregistered_memory_diagnosis.yml"
        ).read_text()
    )
    configuration["sampling"]["tensor_inventory_steps"] = []
    configuration["sampling"]["tensor_inventory_phases"] = []

    class FakeSampler:
        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows
            self.low_system_memory_sample_streak = 0

        def sample(self, **kwargs):
            return self.rows.pop(0)

    peak_only = FakeSampler(
        [
            {
                "current_rss_bytes": 10,
                "peak_rss_bytes": 10_000,
                "system_memory_free_percent": 50.0,
            }
        ]
    )
    sample_memory_checkpoint(
        peak_only,
        configuration=configuration,
        phase="solver_step",
        step=30,
        edge_count=0,
        step_wall_seconds=0.0,
        tracker=None,
        current_rss_limit_bytes=100,
    )

    pressure = FakeSampler(
        [
            {
                "current_rss_bytes": 10,
                "peak_rss_bytes": 10,
                "system_memory_free_percent": 9.0,
            },
            {
                "current_rss_bytes": 10,
                "peak_rss_bytes": 10,
                "system_memory_free_percent": 8.0,
            },
        ]
    )
    sample_memory_checkpoint(
        pressure,
        configuration=configuration,
        phase="solver_step",
        step=25,
        edge_count=0,
        step_wall_seconds=0.0,
        tracker=None,
    )
    with pytest.raises(MemoryError, match="system memory pressure"):
        sample_memory_checkpoint(
            pressure,
            configuration=configuration,
            phase="solver_step",
            step=50,
            edge_count=0,
            step_wall_seconds=0.0,
            tracker=None,
        )


def test_incomplete_repeats_do_not_become_growth_or_medians() -> None:
    metrics = []
    for resolution in (16, 32):
        for variant in ("A", "B", "C"):
            for repeat in (1, 2, 3):
                metrics.append(
                    {
                        "resolution": resolution,
                        "variant": variant,
                        "repeat": repeat,
                        "evaluable": False,
                        "provenance_pass": False,
                        "sampling_coverage_pass": False,
                        "solver_completed": False,
                        "numerical_pass": False,
                        "system_memory_pressure_pass": False,
                        "rss_limit_pass": False,
                        "completion_pass": False,
                        "process_reclamation_pass": False,
                        "rss_quartile_limit_pass": False,
                        "rss_slope_limit_pass": False,
                        "final_quartile_rss_median_bytes": None,
                        "final_quartile_rss_bytes_per_particle": None,
                        "final_live_tensor_unique_storage_bytes_per_particle": None,
                        "final_edge_count": None,
                        "final_edges_per_particle": None,
                        "mean_step_wall_seconds": None,
                        "rss_theil_sen_bytes_per_step": None,
                        "final_minus_first_rss_bytes": None,
                        "rss_significantly_positive": False,
                        "tensor_count_sustained_positive": False,
                        "tensor_bytes_sustained_positive": False,
                        "tracemalloc_sustained_positive": False,
                        "gc_object_sustained_positive": False,
                    }
                )
    rows = _variant_rows(metrics)
    assert len(rows) == 6
    assert all(row["trusted_solver_repeat_count"] == 0 for row in rows)
    assert all(row["median_final_quartile_rss_bytes"] is None for row in rows)
    assert all(row["rss_over_limit_repeat_count"] == 0 for row in rows)


@pytest.mark.parametrize(
    ("positive_repeats", "expected"),
    ((0, (False, False)), (1, (False, True)), (2, (True, False)), (3, (True, False))),
)
def test_significant_positive_rss_repeat_classification(
    positive_repeats: int,
    expected: tuple[bool, bool],
) -> None:
    row = {
        "resolution": 32,
        "rss_over_limit_repeat_count": 0,
        "rss_significant_positive_repeat_count": positive_repeats,
        "synchronized_rss_tensor_or_python_repeat_count": 0,
        "tensor_count_positive_repeat_count": 0,
        "tensor_bytes_positive_repeat_count": 0,
        "tracemalloc_positive_repeat_count": 0,
        "gc_object_positive_repeat_count": 0,
    }
    assert _classify_repeated_n32_growth([row]) == expected


@pytest.mark.parametrize(
    ("arguments", "expected"),
    (
        (
            {"confirmed_linear": True, "hard_complete": True},
            "RESOURCE_FAIL_LINEAR_GROWTH",
        ),
        (
            {"hard_complete": False},
            "RESOURCE_FAIL_UNRESOLVED",
        ),
        (
            {"isolated_overhead_only": True},
            "RESOURCE_CONDITIONAL",
        ),
        (
            {
                "retention_fix_applied": True,
                "retention_fix_contract_pass": True,
            },
            "RESOURCE_PASS_AFTER_RETENTION_FIX",
        ),
        ({}, "RESOURCE_PASS_ALLOCATOR_PLATEAU"),
    ),
)
def test_resource_status_truth_table(arguments: dict, expected: str) -> None:
    defaults = {
        "confirmed_linear": False,
        "hard_complete": True,
        "ambiguous_growth": False,
        "archive_localized": True,
        "isolated_overhead_only": False,
        "retention_fix_applied": False,
        "retention_fix_contract_pass": True,
    }
    defaults.update(arguments)
    assert _derive_resource_status(**defaults) == expected
