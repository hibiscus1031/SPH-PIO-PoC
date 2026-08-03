# Stage 01G — Viscous transverse shear-wave design

## Continuous problem and independent reference

The future benchmark is a smooth viscous transverse shear wave on the periodic domain \([-1,1)^2\), with

\[
\rho_0=1,\quad c_s=20,\quad \nu=0.02,\quad U_s=0.5,\quad
k_s=2\pi,\quad t_f=0.2.
\]

It has no external source. The frozen continuum fields are

\[
\rho=\rho_0,\qquad p=0,\qquad
u_x=U_s\sin(k_s y)e^{-\nu k_s^2t},\qquad u_y=0.
\]

Because \(y(t)=y_0\), integration gives the closed-form unwrapped particle trajectory

\[
x(t)=x_0+U_s\sin(k_s y_0)
\frac{1-e^{-\nu k_s^2t}}{\nu k_s^2},\qquad y(t)=y_0.
\]

This reference calls neither project RK2 nor a Stage 01F source adapter. It contains no manufactured force, receives no validation metric, and will not be corrected from an SPH residual. Position errors use the minimum-image periodic displacement even though the reference trajectory is retained unwrapped.

On each regular grid, \(\Delta x=2/N\) and every particle has mass \(m_i=\rho_0(2/N)^2\).

## Prospective matrix

| Run ID | N | H/dx | dt | Purpose |
|---|---:|---:|---:|---|
| `g_shear_n24` | 24 | 4.5 | 6.25e-5 | formal resolution |
| `g_shear_n32` | 32 | 5.049509756796392 | 6.25e-5 | formal resolution |
| `g_shear_n48` | 48 | 5.5 | 6.25e-5 | formal resolution |
| `g_shear_n32_dt_half` | 32 | 5.049509756796392 | 3.125e-5 | time-step isolation |
| `g_shear_n48_rep2` | 48 | 5.5 | 6.25e-5 | float64 determinism |

Each future run has its own directory. None exists or has been executed in Stage 01G. Common times are constructed from a 3.125e-5 integer tick: ticks `0, 800, 1600, 3200, 4800, 6400`, giving \(t=0,0.025,0.05,0.10,0.15,0.20\).

## Metrics and gates

The frozen metrics are velocity-vector L2/Linf; periodic position L2/Linf; fitted decay rate; amplitude ratio; density L2/Linf drift; pressure L2/Linf; \(\|u_y\|_2/U_s\); momentum; viscous power; and topology/resource/determinism diagnostics.

| Gate | Prospective requirement |
|---|---|
| SHEAR1 | All states and exact values finite; every hard-safety gate passes. |
| SHEAR2 | N48 velocity relative L2 <= 0.02. |
| SHEAR3 | N48 decay-rate relative error <= 0.02. |
| SHEAR4 | N48 particle-position relative L2 <= 0.01. |
| SHEAR5 | N48 density Linf drift <= 5e-3. |
| SHEAR6 | N48 transverse leakage <= 1e-3. |
| SHEAR7 | Velocity and position errors both satisfy N24 > N32 > N48. |
| SHEAR8 | Halving N32 dt changes each primary error by no more than 0.10 relatively. |

No outcome may be described as free-surface, wall-boundary, or turbulence validation.
