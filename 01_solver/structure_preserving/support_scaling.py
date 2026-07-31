"""Load and validate the immutable Stage 01C support-scaling design."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01c_disorder_statistics"
    / "configs"
    / "preregistered_design.yml"
)


@dataclass(frozen=True)
class StaticExperimentDesign:
    resolutions: tuple[int, ...]
    jitter_fractions: tuple[float, ...]
    seeds: tuple[int, ...]
    support_ratios: dict[str, dict[int, float]]
    bootstrap_seed: int
    bootstrap_resamples: int
    domain_length: float

    def dx(self, resolution: int) -> float:
        return self.domain_length / resolution

    def support_ratio(self, family: str, resolution: int) -> float:
        return self.support_ratios[family][resolution]

    def support(self, family: str, resolution: int) -> float:
        return self.dx(resolution) * self.support_ratio(family, resolution)


def load_preregistered_design(
    path: Path = PREREGISTRATION_PATH,
) -> tuple[StaticExperimentDesign, dict[str, Any]]:
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    if record["status"] != "PREREGISTERED_BEFORE_STAGE_01C_RESULTS":
        raise ValueError("Stage 01C design is not preregistered")
    resolutions = tuple(int(value) for value in record["resolutions"])
    jitters = tuple(float(value) for value in record["jitter_fractions"])
    seeds = tuple(int(value) for value in record["random_seeds"])
    if len(seeds) < 10 or len(set(seeds)) != len(seeds):
        raise ValueError("at least ten unique preregistered seeds are required")
    families: dict[str, dict[int, float]] = {}
    for family, values in record["support_families"].items():
        ratios = {
            int(resolution): float(ratio)
            for resolution, ratio in values["ratios_by_resolution"].items()
        }
        if set(ratios) != set(resolutions):
            raise ValueError(f"incomplete support family: {family}")
        families[family] = ratios
    bootstrap = record["statistics"]["bootstrap"]
    extent = (
        float(record["domain"]["maximum"][0])
        - float(record["domain"]["minimum"][0])
    )
    design = StaticExperimentDesign(
        resolutions=resolutions,
        jitter_fractions=jitters,
        seeds=seeds,
        support_ratios=families,
        bootstrap_seed=int(bootstrap["seed"]),
        bootstrap_resamples=int(bootstrap["resamples"]),
        domain_length=extent,
    )
    increasing_supports = [
        design.support("increasing_neighbor", resolution)
        for resolution in resolutions
    ]
    if not all(
        left > right
        for left, right in zip(
            increasing_supports,
            increasing_supports[1:],
        )
    ):
        raise ValueError("increasing-neighbor H must still decrease")
    return design, record
