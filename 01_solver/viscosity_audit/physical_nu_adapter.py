"""Explicit-physical-viscosity adapter for the pinned diffSPH DeltaSPH scheme.

The adapter leaves the imported diffSPH module and installed source untouched.
It clones the official scheme function with a private globals dictionary in
which only the velocity-diffusion callable is replaced.
"""

from __future__ import annotations

import hashlib
import inspect
import math
from pathlib import Path
from types import FunctionType
from typing import Any, Callable

import torch


DIFFSPH_COMMIT = "fff180c81d57a51035de9f4d358dbcaccf973928"
EXPECTED_SOURCE_HASHES = {
    "schemes/deltaSPH.py": (
        "220958abb9517e4933fd8f646d3cb36eb304ad62322a315e561cf9258a2369eb"
    ),
    "operations.py": (
        "8dbe115be1b276b28e1cdce0be017bb8201c1da608efddb6a9f8817b769e4bf6"
    ),
    "sphOperations/laplacian.py": (
        "acf7babf15545845c69c416b84e734470d7a6b0236fefb9eca8920af5c825092"
    ),
}
VELOCITY_SCHEME_NAME = "deltaSPH_viscid"
LAPLACIAN_MODE_NAME = "default"
SUPPORT_SCHEME_NAME = "Symmetric"


class PhysicalViscosityConfigurationError(ValueError):
    """Raised when a fixed-physics viscosity configuration is not credible."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_pinned_operator_sources() -> dict[str, str]:
    """Fail closed unless the installed scheme/operator files are pinned."""

    # Import after the established diffSPH example order has been initialized.
    import diffSPH.operations as operations
    import diffSPH.schemes.deltaSPH as delta_sph
    import diffSPH.sphOperations.laplacian as laplacian

    files = {
        "schemes/deltaSPH.py": Path(inspect.getsourcefile(delta_sph) or ""),
        "operations.py": Path(inspect.getsourcefile(operations) or ""),
        "sphOperations/laplacian.py": Path(
            inspect.getsourcefile(laplacian) or ""
        ),
    }
    observed = {name: _sha256(path) for name, path in files.items()}
    mismatches = {
        name: {"expected": EXPECTED_SOURCE_HASHES[name], "observed": digest}
        for name, digest in observed.items()
        if digest != EXPECTED_SOURCE_HASHES[name]
    }
    if mismatches:
        raise RuntimeError(
            "Installed diffSPH operator source does not match audited commit "
            f"{DIFFSPH_COMMIT}: {mismatches}"
        )
    return observed


def _physical_nu_tensor(
    value: float | torch.Tensor,
    reference: torch.Tensor,
) -> torch.Tensor:
    if torch.is_tensor(value):
        if value.numel() != 1:
            raise PhysicalViscosityConfigurationError(
                "physical kinematic viscosity nu must be scalar"
            )
        nu = value.reshape(()).to(device=reference.device, dtype=reference.dtype)
    else:
        nu = torch.as_tensor(
            value,
            device=reference.device,
            dtype=reference.dtype,
        )
    detached = nu.detach()
    if not bool(torch.isfinite(detached)):
        raise PhysicalViscosityConfigurationError("nu must be finite")
    if bool(detached < 0):
        raise PhysicalViscosityConfigurationError("nu must be non-negative")
    return nu


def physical_nu_laplacian(
    particles: Any,
    kernel: Any,
    neighborhood: Any,
    supportScheme: Any = None,
    config: dict[str, Any] | None = None,
    alphaOverride: float | None = None,
) -> torch.Tensor:
    """Return explicit ``nu * Laplacian(velocity)`` using diffSPH's operator.

    ``alphaOverride`` is rejected because this adapter is qualified only for
    the boundary-free periodic TGV problem.
    """

    del supportScheme
    if config is None:
        raise PhysicalViscosityConfigurationError("config is required")
    if alphaOverride is not None:
        raise PhysicalViscosityConfigurationError(
            "physical-nu adapter is restricted to boundary-free periodic flow"
        )
    diffusion = config.get("diffusion", {})
    if diffusion.get("velocityScheme") != VELOCITY_SCHEME_NAME:
        raise PhysicalViscosityConfigurationError(
            "diffusion.velocityScheme does not select the Stage 01B "
            "physical-nu adapter"
        )
    if "nu" not in diffusion:
        raise PhysicalViscosityConfigurationError(
            "diffusion.nu is required for fixed-physics viscosity"
        )

    from diffSPH.enums import GradientMode, LaplacianMode, Operation
    from diffSPH.neighborhood import SupportScheme
    from diffSPH.operations import SPHOperation

    discrete_laplacian = SPHOperation(
        particles,
        quantity=particles.velocities,
        kernel=kernel,
        neighborhood=neighborhood[0],
        kernelValues=neighborhood[1],
        operation=Operation.Laplacian,
        supportScheme=SupportScheme.Symmetric,
        gradientMode=GradientMode.Difference,
        laplacianMode=LaplacianMode.default,
        positiveDivergence=False,
    )
    nu = _physical_nu_tensor(diffusion["nu"], discrete_laplacian)
    return nu * discrete_laplacian


def make_physical_nu_delta_sph_scheme() -> Callable[..., Any]:
    """Clone the official scheme with a private viscosity callable binding."""

    verify_pinned_operator_sources()
    import diffSPH.schemes.deltaSPH as delta_sph

    official = delta_sph.deltaPlusSPHScheme
    if official.__closure__ is not None:
        raise RuntimeError("Unexpected closure on official DeltaSPH scheme")
    private_globals = dict(official.__globals__)
    private_globals["computeViscosity_deltaSPH_inviscid"] = (
        physical_nu_laplacian
    )
    cloned = FunctionType(
        official.__code__,
        private_globals,
        name="stage01b_fixed_physics_delta_sph",
        argdefs=official.__defaults__,
        closure=None,
    )
    cloned.__kwdefaults__ = dict(official.__kwdefaults__ or {})
    cloned.__annotations__ = dict(official.__annotations__)
    cloned.__doc__ = (
        "Official deltaPlusSPHScheme code with a private, explicit-physical-nu "
        "velocity-diffusion binding."
    )
    cloned.__module__ = __name__
    cloned.__wrapped__ = official
    setattr(cloned, "_stage01b_upstream_code_identity", official.__code__)
    setattr(cloned, "_stage01b_diff_sph_commit", DIFFSPH_COMMIT)
    return cloned


def physical_reynolds_number(
    velocity_scale: float,
    length_scale: float,
    nu: float,
) -> float:
    if not all(
        math.isfinite(value) and value > 0
        for value in (velocity_scale, length_scale, nu)
    ):
        raise PhysicalViscosityConfigurationError(
            "velocity scale, length scale and nu must be finite and positive"
        )
    return velocity_scale * length_scale / nu
