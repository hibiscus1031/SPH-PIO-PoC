#!/usr/bin/env python3
"""Preregistered analytic spatial families and closed-form derivatives."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


NEW_FAMILIES = ("FAMILY_CROSSMODE_A", "FAMILY_DIAGONAL_B", "FAMILY_MIXED_C")


def evaluate_family(
    family_id: str, position: np.ndarray, *, rho0: float, cs: float, nu: float
) -> dict[str, np.ndarray]:
    x = np.asarray(position[:, 0], dtype=np.float64)
    y = np.asarray(position[:, 1], dtype=np.float64)
    k = 2.0 * math.pi
    u0 = 0.02 * cs
    if family_id == "FAMILY_CROSSMODE_A":
        rho = rho0 * (1.0 + 0.003 * np.cos(k * x) + 0.002 * np.cos(2.0 * k * y))
        ux = u0 * (np.sin(k * x) * np.cos(2.0 * k * y) + 0.20 * np.sin(2.0 * k * x) * np.cos(k * y))
        uy = u0 * (-0.70 * np.cos(k * x) * np.sin(2.0 * k * y) + 0.15 * np.cos(2.0 * k * x) * np.sin(k * y))
        grad_rho_x = rho0 * (-0.003 * k * np.sin(k * x))
        grad_rho_y = rho0 * (-0.004 * k * np.sin(2.0 * k * y))
    elif family_id == "FAMILY_DIAGONAL_B":
        phase_11 = k * (x + y)
        phase_2m1 = k * (2.0 * x - y)
        phase_21 = k * (2.0 * x + y)
        phase_1m2 = k * (x - 2.0 * y)
        rho = rho0 * (1.0 + 0.0025 * np.cos(phase_11) + 0.0015 * np.cos(phase_2m1))
        ux = u0 * (0.80 * np.sin(phase_21) + 0.25 * np.sin(phase_1m2))
        uy = u0 * (-0.60 * np.cos(phase_21) + 0.20 * np.cos(phase_1m2))
        grad_rho_x = rho0 * (-0.0025 * k * np.sin(phase_11) - 0.0030 * k * np.sin(phase_2m1))
        grad_rho_y = rho0 * (-0.0025 * k * np.sin(phase_11) + 0.0015 * k * np.sin(phase_2m1))
    elif family_id == "FAMILY_MIXED_C":
        rho = rho0 * (
            1.0
            + 0.0020 * np.cos(2.0 * k * x) * np.cos(2.0 * k * y)
            + 0.0015 * np.sin(k * x) * np.sin(2.0 * k * y)
        )
        ux = u0 * (np.sin(2.0 * k * x) * np.cos(k * y) + 0.30 * np.sin(k * x) * np.cos(2.0 * k * y))
        uy = u0 * (-0.75 * np.cos(2.0 * k * x) * np.sin(k * y) + 0.25 * np.cos(k * x) * np.sin(2.0 * k * y))
        grad_rho_x = rho0 * (
            -0.0040 * k * np.sin(2.0 * k * x) * np.cos(2.0 * k * y)
            + 0.0015 * k * np.cos(k * x) * np.sin(2.0 * k * y)
        )
        grad_rho_y = rho0 * (
            -0.0040 * k * np.cos(2.0 * k * x) * np.sin(2.0 * k * y)
            + 0.0030 * k * np.sin(k * x) * np.cos(2.0 * k * y)
        )
    else:
        raise ValueError(f"Unknown preregistered family: {family_id}")
    velocity = np.column_stack((ux, uy)).astype(np.float64)
    pressure = cs * cs * (rho - rho0)
    grad_pressure = cs * cs * np.column_stack((grad_rho_x, grad_rho_y))
    laplacian_velocity = -5.0 * k * k * velocity
    pressure_acceleration = -grad_pressure / rho[:, None]
    viscosity_acceleration = nu * laplacian_velocity
    total = pressure_acceleration + viscosity_acceleration
    return {
        "rho": rho.astype(np.float64),
        "pressure": pressure.astype(np.float64),
        "velocity": velocity,
        "grad_pressure": grad_pressure.astype(np.float64),
        "laplacian_velocity": laplacian_velocity.astype(np.float64),
        "pressure_acceleration": pressure_acceleration.astype(np.float64),
        "viscosity_acceleration": viscosity_acceleration.astype(np.float64),
        "acceleration": total.astype(np.float64),
    }


def fourier_spatial_reference(
    position: np.ndarray, rho: np.ndarray, velocity: np.ndarray, *, rho0: float, cs: float, nu: float
) -> dict[str, np.ndarray]:
    particle_count = position.shape[0]
    n_axis = int(round(math.sqrt(particle_count)))
    if n_axis * n_axis != particle_count:
        raise ValueError("Fourier reference requires a full regular square grid")
    expected = (np.arange(n_axis, dtype=np.float64) + 0.5) / n_axis
    if not np.array_equal(position[:, 0].reshape(n_axis, n_axis)[:, 0], expected):
        raise ValueError("Unexpected canonical x grid")
    p_grid = (cs * cs * (rho - rho0)).reshape(n_axis, n_axis)
    u_grid = velocity.reshape(n_axis, n_axis, 2)
    wave = 2.0 * math.pi * np.fft.fftfreq(n_axis, d=1.0 / n_axis)
    kx = wave[:, None]
    ky = wave[None, :]
    p_hat = np.fft.fft2(p_grid)
    grad_px = np.fft.ifft2(1j * kx * p_hat).real
    grad_py = np.fft.ifft2(1j * ky * p_hat).real
    k2 = kx * kx + ky * ky
    lap_u = np.empty_like(u_grid)
    for component in range(2):
        lap_u[:, :, component] = np.fft.ifft2(-k2 * np.fft.fft2(u_grid[:, :, component])).real
    grad_pressure = np.stack((grad_px, grad_py), axis=-1).reshape(particle_count, 2)
    laplacian_velocity = lap_u.reshape(particle_count, 2)
    pressure_acceleration = -grad_pressure / rho[:, None]
    viscosity_acceleration = nu * laplacian_velocity
    return {
        "grad_pressure": grad_pressure.astype(np.float64),
        "laplacian_velocity": laplacian_velocity.astype(np.float64),
        "pressure_acceleration": pressure_acceleration.astype(np.float64),
        "viscosity_acceleration": viscosity_acceleration.astype(np.float64),
        "acceleration": (pressure_acceleration + viscosity_acceleration).astype(np.float64),
    }


def closed_form_unit_tests(*, rho0: float, cs: float, nu: float) -> dict[str, Any]:
    n_axis = 32
    grid = (np.arange(n_axis, dtype=np.float64) + 0.5) / n_axis
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    position = np.column_stack((xx.ravel(), yy.ravel()))
    rows = []
    for family_id in NEW_FAMILIES:
        analytic = evaluate_family(family_id, position, rho0=rho0, cs=cs, nu=nu)
        fourier = fourier_spatial_reference(
            position, analytic["rho"], analytic["velocity"], rho0=rho0, cs=cs, nu=nu
        )
        grad_error = float(np.max(np.abs(analytic["grad_pressure"] - fourier["grad_pressure"])))
        lap_error = float(np.max(np.abs(analytic["laplacian_velocity"] - fourier["laplacian_velocity"])))
        acceleration_error = float(np.max(np.abs(analytic["acceleration"] - fourier["acceleration"])))
        rows.append(
            {
                "family_id": family_id,
                "rho_min": float(np.min(analytic["rho"])),
                "rho_max": float(np.max(analytic["rho"])),
                "grad_pressure_Fourier_Linf": grad_error,
                "laplacian_velocity_Fourier_Linf": lap_error,
                "acceleration_Fourier_Linf": acceleration_error,
                "status": "PASS" if min(analytic["rho"]) > 0.0 and acceleration_error <= 1.0e-11 else "FAIL",
            }
        )
    return {"verification_grid": "32x32_regular_midpoint", "rows": rows, "all_pass": all(r["status"] == "PASS" for r in rows)}

