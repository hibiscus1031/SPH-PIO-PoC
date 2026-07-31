"""Official diffSPH Taylor–Green setup exposed through a headless adapter.

The numerical scheme is not reimplemented here.  Initialization, neighborhood
search, kernels, density/pressure/viscosity terms, shifting, time integration,
and state updates are all delegated to diffSPH.  The adapter fixes two concerns
in the upstream example: it selects MPS explicitly instead of keying device
selection only on CUDA availability, and it records/audits every state tensor.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import torch


DIFFSPH_COMMIT = "fff180c81d57a51035de9f4d358dbcaccf973928"
DIFFSPH_EXAMPLE_PATH = "examples/weaklyCompressible/scripts/05_TGV.py"


@dataclass(frozen=True)
class TGVConfig:
    """Configuration shared by CPU and MPS Taylor–Green runs."""

    resolution: int
    backend: str
    dtype: str = "float32"
    seed: int = 20260731
    domain_length: float = 2.0
    initial_density: float = 1.0
    velocity_amplitude: float = 1.0
    diffusion_alpha: float = 0.01
    wave_number: int = 2
    target_dt: float = 5.0e-4
    total_time: float = 0.2
    total_steps: int | None = None
    metric_interval: int = 20
    kernel: str = "Wendland4"
    n_h: int = 4
    integration_scheme: str = "symplecticEuler"
    scheme: str = "DeltaSPH"
    shuffle_iterations: int = 256
    warmup_steps: int = 3
    run_id: str = "run-1"

    def __post_init__(self) -> None:
        derived_steps = int(round(self.total_time / self.target_dt))
        if self.total_steps is None:
            object.__setattr__(self, "total_steps", derived_steps)
        elif self.total_steps != derived_steps:
            raise ValueError(
                "total_steps must equal round(total_time/target_dt); "
                f"got {self.total_steps} versus {derived_steps}"
            )

    @property
    def particle_count(self) -> int:
        return self.resolution**2

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "TGVConfig":
        allowed = {field.name for field in dataclasses.fields(cls)}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"Unknown TGV configuration keys: {unknown}")
        return cls(**dict(values))

    def as_dict(self) -> dict[str, Any]:
        result = dataclasses.asdict(self)
        result["particle_count"] = self.particle_count
        result["diffsph_commit"] = DIFFSPH_COMMIT
        result["diffsph_example"] = DIFFSPH_EXAMPLE_PATH
        return result


@dataclass
class SimulationContext:
    """Objects produced by the official diffSPH initialization path."""

    spec: TGVConfig
    device: torch.device
    torch_dtype: torch.dtype
    simulator: Any
    integrator: Any
    system: Any
    config: dict[str, Any]
    dt: torch.Tensor
    initial_positions: torch.Tensor
    initial_velocities: torch.Tensor
    initial_densities: torch.Tensor
    diffusion_alpha: float
    reference_kinematic_viscosity: float
    reference_reynolds_number: float
    sound_speed: float
    smoothing_length: float


def resolve_device(backend: str) -> torch.device:
    normalized = backend.lower()
    if normalized == "cpu":
        return torch.device("cpu")
    if normalized == "mps":
        if not torch.backends.mps.is_built():
            raise RuntimeError("PyTorch was not built with MPS support")
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS is built but unavailable")
        if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") == "1":
            raise RuntimeError("PYTORCH_ENABLE_MPS_FALLBACK=1 is forbidden for validation")
        return torch.device("mps")
    raise ValueError(f"Unsupported backend {backend!r}; expected 'cpu' or 'mps'")


def resolve_dtype(name: str) -> torch.dtype:
    if name == "float32":
        return torch.float32
    if name == "float64":
        return torch.float64
    raise ValueError(f"Unsupported dtype {name!r}")


def wrap_periodic_positions(
    positions: torch.Tensor,
    domain_min: torch.Tensor,
    domain_max: torch.Tensor,
) -> torch.Tensor:
    """Wrap positions into a half-open periodic box without changing device."""

    extent = domain_max - domain_min
    return domain_min + torch.remainder(positions - domain_min, extent)


def taylor_green_velocity(
    positions: torch.Tensor,
    time: float | torch.Tensor,
    *,
    amplitude: float | torch.Tensor,
    viscosity: float,
    wave_number: int,
) -> torch.Tensor:
    """Analytical 2-D periodic TGV velocity used by the official example.

    For the official even ``wave_number=2`` case this is
    ``u=(-sin(pi*x)cos(pi*y), cos(pi*x)sin(pi*y))`` multiplied by
    ``amplitude*exp(-2*nu*pi^2*t)``.
    """

    k_tgv = wave_number / 2.0
    phase = math.pi / 2.0 if wave_number % 2 == 0 else 0.0
    spatial_k = k_tgv * math.pi
    if torch.is_tensor(time):
        t = time.to(device=positions.device, dtype=positions.dtype)
    else:
        t = torch.as_tensor(time, device=positions.device, dtype=positions.dtype)
    if torch.is_tensor(amplitude):
        amp = amplitude.to(device=positions.device, dtype=positions.dtype)
    else:
        amp = torch.as_tensor(amplitude, device=positions.device, dtype=positions.dtype)
    decay = torch.exp(-2.0 * viscosity * spatial_k**2 * t)
    x, y = positions[:, 0], positions[:, 1]
    ux = torch.cos(spatial_k * x + phase) * torch.sin(spatial_k * y + phase)
    uy = -torch.sin(spatial_k * x + phase) * torch.cos(spatial_k * y + phase)
    return amp * decay * torch.stack((ux, uy), dim=-1)


def build_context(
    spec: TGVConfig,
    *,
    amplitude: torch.Tensor | float | None = None,
) -> SimulationContext:
    """Build the official DeltaSPH periodic TGV system on an explicit device."""

    # Imports remain local so simple analytical unit tests do not require the
    # optional visualization stack imported by diffSPH at module import time.
    # Keep the upstream example's import order.  diffSPH 0.2.2 has a circular
    # dependency between sampling, particle shifting, DeltaSPH, and adaptive
    # smoothing when adaptiveSmoothingASPH is imported first.
    from diffSPH.sampling import buildDomainDescription
    from diffSPH.enums import SimulationScheme
    from diffSPH.integration import getIntegrationEnum, getIntegrator
    from diffSPH.modules.adaptiveSmoothingASPH import n_h_to_nH
    from diffSPH.boundary import sampleDomainSDF
    from diffSPH.kernels import Kernel_Scale, getKernelEnum
    from diffSPH.modules.particleShifting import shuffleParticles
    from diffSPH.regions import buildRegion, filterRegion
    from diffSPH.schema import getSimulationScheme
    from diffSPH.schemes.initializers import initializeSimulation
    from diffSPH.util import volumeToSupport

    device = resolve_device(spec.backend)
    dtype = resolve_dtype(spec.dtype)
    torch.manual_seed(spec.seed)
    if device.type == "mps" and hasattr(torch.mps, "manual_seed"):
        torch.mps.manual_seed(spec.seed)

    if spec.scheme != "DeltaSPH":
        raise ValueError("Stage 01 adapter supports only the official DeltaSPH TGV scheme")
    if not math.isclose(spec.diffusion_alpha, 0.01, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(
            "Official diffSPH commit fff180c hard-codes reachable DeltaSPH "
            "diffusion alpha to 0.01; other configured values would be ignored"
        )

    length = spec.domain_length
    dx = length / spec.resolution
    kernel = getKernelEnum(spec.kernel)
    scheme = SimulationScheme.DeltaSPH
    integration_enum = getIntegrationEnum(spec.integration_scheme)
    target_neighbors = n_h_to_nH(spec.n_h, 2)
    sound_speed = (
        0.3
        * volumeToSupport(dx**2, target_neighbors, 2)
        / Kernel_Scale(kernel, 2)
        / spec.target_dt
    )
    domain = buildDomainDescription(
        l=length,
        dim=2,
        periodic=True,
        device=device,
        dtype=dtype,
    )
    simulator, system_class, config, _ = getSimulationScheme(
        scheme,
        kernel,
        integration_enum,
        1.0,
        target_neighbors,
        domain,
    )
    config["particle"] = {
        "nx": spec.resolution,
        "dx": dx,
        "targetNeighbors": target_neighbors,
        "band": 0,
    }
    config["fluid"] = {
        "rho0": spec.initial_density,
        "c_s": sound_speed,
    }
    config["surfaceDetection"]["active"] = False
    config["shifting"]["freeSurface"] = False

    fluid_sdf = lambda x: sampleDomainSDF(x, domain, invert=True)
    regions = [buildRegion(sdf=fluid_sdf, config=config, type="fluid")]
    for region in regions:
        filterRegion(region, regions)
    particle_state, config, _ = initializeSimulation(scheme, config, regions)
    # CPU is the canonical initializer for cross-backend comparisons.  MPS
    # receives the complete shuffled CPU state below so positions, densities,
    # velocities, masses, supports, and identifiers are byte-identical before
    # the first step.
    if spec.shuffle_iterations and device.type == "cpu":
        particle_state.positions = shuffleParticles(
            particle_state,
            config,
            spec.shuffle_iterations,
        )

    # The reachable official implementation hard-codes alpha=0.01.  The
    # notebook gives the following *post-hoc* effective-viscosity mapping.
    # Since c_s and h vary with resolution, so do reference nu and Re.  This
    # is an official-demo baseline, not a fixed-Re convergence study.
    support = float(config["particle"]["support"])
    reference_viscosity = (
        spec.diffusion_alpha
        * sound_speed
        * support
        / (2 * domain.dim + 2)
        * (5.0 / 4.0)
    )
    reference_reynolds = (
        spec.velocity_amplitude * spec.domain_length / reference_viscosity
    )
    config["diffusion"]["alpha"] = spec.diffusion_alpha

    system = system_class(
        config["domain"],
        None,
        0.0,
        copy.deepcopy(particle_state),
        "momentum",
        None,
        rigidBodies=config["rigidBodies"],
        regions=config["regions"],
        config=config,
    )
    actual_amplitude = spec.velocity_amplitude if amplitude is None else amplitude
    if device.type == "mps":
        cpu_spec = dataclasses.replace(spec, backend="cpu")
        cpu_context = build_context(cpu_spec, amplitude=actual_amplitude)
        source_state = cpu_context.system.systemState
        target_state = system.systemState
        for field in dataclasses.fields(source_state):
            value = getattr(source_state, field.name)
            if torch.is_tensor(value):
                value = value.to(device=device, dtype=value.dtype)
            else:
                value = copy.deepcopy(value)
            setattr(target_state, field.name, value)
        velocity = target_state.velocities
    else:
        velocity = taylor_green_velocity(
            system.systemState.positions,
            0.0,
            amplitude=actual_amplitude,
            viscosity=reference_viscosity,
            wave_number=spec.wave_number,
        )
        system.systemState.velocities = velocity
    dt = torch.as_tensor(spec.target_dt, device=device, dtype=dtype)
    integrator = getIntegrator(integration_enum)

    context = SimulationContext(
        spec=spec,
        device=device,
        torch_dtype=dtype,
        simulator=simulator,
        integrator=integrator,
        system=system,
        config=config,
        dt=dt,
        initial_positions=system.systemState.positions.detach().clone(),
        initial_velocities=velocity.detach().clone(),
        initial_densities=system.systemState.densities.detach().clone(),
        diffusion_alpha=float(spec.diffusion_alpha),
        reference_kinematic_viscosity=float(reference_viscosity),
        reference_reynolds_number=float(reference_reynolds),
        sound_speed=float(sound_speed),
        smoothing_length=support,
    )
    audit = audit_system_device(context)
    if audit["mismatches"]:
        raise RuntimeError(f"Initialization device mismatch: {audit['mismatches']}")
    return context


def advance_one_step(context: SimulationContext) -> tuple[Any, Any]:
    """Advance one full official diffSPH integration step."""

    system, current_state, updates = context.integrator.function(
        context.system,
        context.dt,
        context.simulator,
        context.config,
        priorStep=context.system.priorStep,
        verbose=False,
    )
    context.system = system
    return current_state, updates


def _walk_tensors(
    value: Any,
    path: str,
    seen: set[int],
) -> Iterable[tuple[str, torch.Tensor]]:
    if torch.is_tensor(value):
        yield path, value
        return
    if value is None or isinstance(value, (str, bytes, int, float, bool, torch.dtype)):
        return
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_tensors(child, f"{path}.{key}", seen)
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            yield from _walk_tensors(child, f"{path}[{index}]", seen)
    elif dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            yield from _walk_tensors(getattr(value, field.name), f"{path}.{field.name}", seen)


def audit_system_device(
    context: SimulationContext,
    extras: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit all tensors in state/domain and selected step outputs."""

    targets: dict[str, Any] = {
        "state": context.system.systemState,
        "priorStep": context.system.priorStep,
        "domain": context.config["domain"],
        "regions": context.config.get("regions", []),
        "dt": context.dt,
    }
    if extras:
        targets.update(extras)
    tensors: list[tuple[str, torch.Tensor]] = []
    seen: set[int] = set()
    for name, value in targets.items():
        tensors.extend(_walk_tensors(value, name, seen))
    expected = context.device.type
    mismatches = [
        f"{path}={tensor.device}"
        for path, tensor in tensors
        if tensor.device.type != expected
    ]
    device_counts: dict[str, int] = {}
    for _, tensor in tensors:
        key = str(tensor.device)
        device_counts[key] = device_counts.get(key, 0) + 1
    return {
        "expected_device": str(context.device),
        "tensor_count": len(tensors),
        "device_counts": device_counts,
        "mismatches": mismatches,
    }


def synchronize(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()
