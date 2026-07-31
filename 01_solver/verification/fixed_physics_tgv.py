"""Fixed-physics Taylor--Green configuration layered on official diffSPH."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any, Mapping

import torch

from diffsph_adapter import TGVConfig, build_context
from viscosity_audit.physical_nu_adapter import (
    VELOCITY_SCHEME_NAME,
    make_physical_nu_delta_sph_scheme,
    physical_reynolds_number,
)


@dataclass(frozen=True)
class FixedPhysicsTGVConfig:
    """Prerecorded Stage 01B physical and numerical configuration."""

    resolution: int
    backend: str = "cpu"
    dtype: str = "float32"
    seed: int = 20260731
    domain_length: float = 2.0
    initial_density: float = 1.0
    velocity_amplitude: float = 1.0
    physical_viscosity: float = 0.02
    sound_speed: float = 10.0
    target_reynolds: float = 100.0
    maximum_nominal_mach: float = 0.1
    wave_number: int = 2
    target_dt: float = 1.0e-3
    total_time: float = 0.2
    total_steps: int | None = None
    metric_interval: int = 20
    kernel: str = "Wendland4"
    n_h: int = 4
    integration_scheme: str = "symplecticEuler"
    scheme: str = "DeltaSPH"
    shuffle_iterations: int = 0
    warmup_steps: int = 0
    cfl: float = 0.3
    max_dt: float = 1.0e-3
    min_dt: float = 1.0e-6
    pressure_term: str = "Antuono"
    eos: str = "isoThermal"
    density_diffusion: str = "deltaSPH"
    shifting_active: bool = True
    verlet_scale: float = 1.0
    run_id: str = "qualification"

    def __post_init__(self) -> None:
        if self.resolution <= 0:
            raise ValueError("resolution must be positive")
        if self.target_dt <= 0 or self.total_time <= 0:
            raise ValueError("target_dt and total_time must be positive")
        if self.verlet_scale < 1.0:
            raise ValueError("verlet_scale must be at least 1")
        derived_steps = int(round(self.total_time / self.target_dt))
        if self.total_steps is None:
            object.__setattr__(self, "total_steps", derived_steps)
        elif self.total_steps != derived_steps:
            raise ValueError(
                "total_steps must equal round(total_time/target_dt)"
            )
        reynolds = physical_reynolds_number(
            self.velocity_amplitude,
            self.domain_length,
            self.physical_viscosity,
        )
        if not math.isclose(
            reynolds,
            self.target_reynolds,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        ):
            raise ValueError(
                f"physical inputs imply Re={reynolds}, not "
                f"target_reynolds={self.target_reynolds}"
            )
        nominal_mach = self.velocity_amplitude / self.sound_speed
        if nominal_mach > self.maximum_nominal_mach + 1.0e-12:
            raise ValueError(
                f"nominal Mach {nominal_mach} exceeds "
                f"{self.maximum_nominal_mach}"
            )

    @property
    def particle_count(self) -> int:
        return self.resolution**2

    @property
    def reynolds_number(self) -> float:
        return physical_reynolds_number(
            self.velocity_amplitude,
            self.domain_length,
            self.physical_viscosity,
        )

    @property
    def nominal_mach(self) -> float:
        return self.velocity_amplitude / self.sound_speed

    def as_dict(self) -> dict[str, Any]:
        values = dataclasses.asdict(self)
        values["particle_count"] = self.particle_count
        values["reynolds_number"] = self.reynolds_number
        values["nominal_mach"] = self.nominal_mach
        values["velocity_diffusion"] = VELOCITY_SCHEME_NAME
        return values

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
    ) -> "FixedPhysicsTGVConfig":
        allowed = {field.name for field in dataclasses.fields(cls)}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"Unknown fixed-physics keys: {unknown}")
        return cls(**dict(values))


def fixed_timestep_limits(
    context: Any,
    spec: FixedPhysicsTGVConfig,
) -> dict[str, float]:
    from diffSPH.kernels import Kernel_Scale

    support = float(context.config["particle"]["support"])
    kernel_scale = float(
        Kernel_Scale(context.config["kernel"], context.config["domain"].dim)
    )
    acoustic = spec.cfl * support / (spec.sound_speed * kernel_scale)
    viscous = (
        0.125
        * support**2
        / (spec.physical_viscosity * kernel_scale)
    )
    return {
        "support": support,
        "kernel_scale": kernel_scale,
        "acoustic": acoustic,
        "viscous": viscous,
        "configured_max_dt": spec.max_dt,
        "permitted_initial_dt": min(acoustic, viscous, spec.max_dt),
    }


def build_fixed_physics_context(
    spec: FixedPhysicsTGVConfig,
    *,
    amplitude: float | torch.Tensor | None = None,
    viscosity: float | torch.Tensor | None = None,
) -> Any:
    r"""Build the official state, then explicitly bind fixed \(c_s\) and \(\nu\)."""

    base_spec = TGVConfig(
        resolution=spec.resolution,
        backend=spec.backend,
        dtype=spec.dtype,
        seed=spec.seed,
        domain_length=spec.domain_length,
        initial_density=spec.initial_density,
        velocity_amplitude=spec.velocity_amplitude,
        diffusion_alpha=0.01,
        wave_number=spec.wave_number,
        target_dt=spec.target_dt,
        total_time=spec.total_time,
        total_steps=spec.total_steps,
        metric_interval=spec.metric_interval,
        kernel=spec.kernel,
        n_h=spec.n_h,
        integration_scheme=spec.integration_scheme,
        scheme=spec.scheme,
        shuffle_iterations=spec.shuffle_iterations,
        warmup_steps=spec.warmup_steps,
        run_id=spec.run_id,
    )
    context = build_context(base_spec, amplitude=amplitude)
    state = context.system.systemState

    context.config["fluid"]["c_s"] = spec.sound_speed
    state.soundspeeds = torch.full_like(state.soundspeeds, spec.sound_speed)
    context.config["diffusion"].update(
        {
            "alpha": 0.0,
            "nu": (
                spec.physical_viscosity
                if viscosity is None
                else viscosity
            ),
            "velocityScheme": VELOCITY_SCHEME_NAME,
            "physicalOperator": "SPHOperation_Laplacian",
            "physicalSupportScheme": "Symmetric",
            "physicalLaplacianMode": "default",
        }
    )
    context.config["timestep"] = {
        "active": False,
        "dt": spec.target_dt,
        "CFL": spec.cfl,
        "maxDt": spec.max_dt,
        "minDt": spec.min_dt,
        "viscosityConstraint": True,
        "acousticConstraint": True,
        "accelerationConstraint": True,
    }
    context.config["pressure"]["term"] = spec.pressure_term
    context.config["EOS"] = {"type": spec.eos}
    context.config["diffusion"]["scheme"] = spec.density_diffusion
    context.config["shifting"]["active"] = spec.shifting_active
    context.config["neighborhood"]["verletScale"] = spec.verlet_scale

    context.simulator = make_physical_nu_delta_sph_scheme()
    context.spec = spec
    context.diffusion_alpha = 0.0
    context.reference_kinematic_viscosity = spec.physical_viscosity
    context.reference_reynolds_number = spec.reynolds_number
    context.sound_speed = spec.sound_speed
    setattr(context, "physical_kinematic_viscosity", spec.physical_viscosity)
    setattr(context, "nominal_mach", spec.nominal_mach)
    setattr(context, "viscosity_parameter", context.config["diffusion"]["nu"])

    limits = fixed_timestep_limits(context, spec)
    if spec.target_dt > limits["permitted_initial_dt"] * (1.0 + 1.0e-12):
        raise ValueError(
            f"target_dt={spec.target_dt} exceeds audited initial limit "
            f"{limits['permitted_initial_dt']}"
        )
    setattr(context, "timestep_limits", limits)
    return context
