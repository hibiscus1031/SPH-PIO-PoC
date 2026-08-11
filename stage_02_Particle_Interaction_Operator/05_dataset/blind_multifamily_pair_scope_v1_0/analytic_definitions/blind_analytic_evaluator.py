#!/usr/bin/env python3
"""Generic closed-form and Fourier references for frozen blind families."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def phase(position: np.ndarray, mode: list[int], offset: float) -> np.ndarray:
    return 2.0 * math.pi * (mode[0] * position[:, 0] + mode[1] * position[:, 1]) + offset


def evaluate_family(definition: dict[str, Any], position: np.ndarray, *, rho0: float, cs: float, nu: float) -> dict[str, np.ndarray]:
    density_sum = np.zeros(len(position)); grad_rho = np.zeros((len(position), 2))
    for amplitude, mode, offset in zip(definition["density"]["amplitudes"], definition["density"]["modes"], definition["density"]["phases"]):
        theta = phase(position, mode, offset); density_sum += amplitude * np.cos(theta)
        grad_rho += (-rho0 * amplitude * 2.0 * math.pi * np.sin(theta))[:, None] * np.asarray(mode, dtype=np.float64)[None, :]
    rho = rho0 * (1.0 + density_sum)
    velocity = np.zeros((len(position), 2)); laplacian = np.zeros_like(velocity)
    for component, key in enumerate(("velocity_x", "velocity_y")):
        block = definition[key]
        for amplitude, mode, offset in zip(block["amplitudes_over_cs"], block["modes"], block["phases"]):
            theta = phase(position, mode, offset); value = cs * amplitude * np.sin(theta)
            velocity[:, component] += value
            laplacian[:, component] += -(2.0 * math.pi) ** 2 * (mode[0] ** 2 + mode[1] ** 2) * value
    pressure = cs * cs * (rho - rho0); grad_p = cs * cs * grad_rho
    pressure_acceleration = -grad_p / rho[:, None]; viscosity_acceleration = nu * laplacian
    return {"rho": rho, "pressure": pressure, "velocity": velocity, "grad_p": grad_p, "laplacian_velocity": laplacian, "pressure_acceleration": pressure_acceleration, "viscosity_acceleration": viscosity_acceleration, "acceleration": pressure_acceleration + viscosity_acceleration}


def fourier_reference(position: np.ndarray, rho: np.ndarray, velocity: np.ndarray, *, rho0: float, cs: float, nu: float) -> dict[str, np.ndarray]:
    n_axis = int(round(math.sqrt(len(position))))
    if n_axis * n_axis != len(position): raise ValueError("Regular square grid required")
    wave = 2.0 * math.pi * np.fft.fftfreq(n_axis, d=1.0 / n_axis)
    kx = wave[:, None]; ky = wave[None, :]
    rho_hat = np.fft.fft2(rho.reshape(n_axis, n_axis))
    grad_rho_x = np.fft.ifft2(1j * kx * rho_hat).real.ravel(); grad_rho_y = np.fft.ifft2(1j * ky * rho_hat).real.ravel()
    grad_p = cs * cs * np.column_stack((grad_rho_x, grad_rho_y))
    lap = np.zeros_like(velocity); k2 = kx * kx + ky * ky
    for component in range(2): lap[:, component] = np.fft.ifft2(-k2 * np.fft.fft2(velocity[:, component].reshape(n_axis, n_axis))).real.ravel()
    pressure_acceleration = -grad_p / rho[:, None]; viscosity_acceleration = nu * lap
    return {"grad_p": grad_p, "laplacian_velocity": lap, "pressure_acceleration": pressure_acceleration, "viscosity_acceleration": viscosity_acceleration, "acceleration": pressure_acceleration + viscosity_acceleration}
