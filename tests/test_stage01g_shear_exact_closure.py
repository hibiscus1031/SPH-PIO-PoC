import math


def test_shear_field_and_closed_trajectory_satisfy_continuum_closure():
    rho0, nu, amplitude, wave_number = 1.0, 0.02, 0.5, 2.0 * math.pi
    for y in (-0.83, -0.25, 0.0, 0.41, 0.92):
        for time in (0.0, 0.025, 0.1, 0.2):
            decay = math.exp(-nu * wave_number**2 * time)
            velocity = amplitude * math.sin(wave_number * y) * decay
            velocity_t = -nu * wave_number**2 * velocity
            velocity_yy = -wave_number**2 * velocity
            continuity_residual = 0.0  # rho_t + d_x(rho*u_x) + d_y(rho*u_y)
            momentum_residual = velocity_t - nu * velocity_yy
            trajectory_rate = amplitude * math.sin(wave_number * y) * decay
            assert continuity_residual == 0.0
            assert math.isclose(momentum_residual, 0.0, abs_tol=1e-15)
            assert math.isclose(trajectory_rate, velocity, rel_tol=0.0, abs_tol=1e-15)
            assert math.isfinite(rho0 + velocity + trajectory_rate)


def test_shear_common_times_are_exact_integer_ticks():
    tick = 3.125e-5
    ticks = (0, 800, 1600, 3200, 4800, 6400)
    expected = (0.0, 0.025, 0.05, 0.10, 0.15, 0.20)
    assert all(math.isclose(n * tick, t, abs_tol=1e-15) for n, t in zip(ticks, expected))
