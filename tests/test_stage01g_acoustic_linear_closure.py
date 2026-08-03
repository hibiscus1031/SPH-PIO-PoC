import math


def test_acoustic_fields_satisfy_linearized_continuity_momentum_and_eos():
    rho0, sound_speed, epsilon, wave_number = 1.0, 20.0, 0.005, math.pi
    omega = sound_speed * wave_number
    for x in (-0.77, -0.2, 0.0, 0.36, 0.88):
        for time in (0.0, 0.0125, 0.05, 0.1):
            spatial_cos = math.cos(wave_number * x)
            spatial_sin = math.sin(wave_number * x)
            temporal_cos = math.cos(omega * time)
            temporal_sin = math.sin(omega * time)
            density = rho0 * (1.0 + epsilon * spatial_cos * temporal_cos)
            density_t = -rho0 * epsilon * spatial_cos * omega * temporal_sin
            velocity_x = sound_speed * epsilon * spatial_sin * temporal_sin
            velocity_x_x = sound_speed * epsilon * wave_number * spatial_cos * temporal_sin
            velocity_x_t = sound_speed * epsilon * spatial_sin * omega * temporal_cos
            density_x = -rho0 * epsilon * wave_number * spatial_sin * temporal_cos
            pressure = sound_speed**2 * (density - rho0)
            pressure_x = sound_speed**2 * density_x
            assert math.isclose(density_t + rho0 * velocity_x_x, 0.0, abs_tol=2e-15)
            assert math.isclose(velocity_x_t + pressure_x / rho0, 0.0, abs_tol=2e-13)
            assert math.isclose(pressure, sound_speed**2 * (density - rho0), abs_tol=0.0)


def test_acoustic_horizon_is_one_linear_period():
    period = 2.0 * math.pi / (20.0 * math.pi)
    assert math.isclose(period, 0.1, rel_tol=0.0, abs_tol=1e-15)
