# Stage 01G-P — Shear-wave contract audit

## Frozen continuum problem

The Stage 01G shear design defines

\[
\rho=\rho_0,\qquad p=0,\qquad
u_x=U_s\sin(k_sy)e^{-\nu k_s^2t},\qquad u_y=0,
\]

with \(\rho_0=1\), \(c_s=20\), \(\nu=0.02\), \(U_s=0.5\), \(k_s=2\pi\), and \(t_f=0.2\). All quantities are explicit; no implementation default supplies a physical parameter or horizon.

The reference is an analytic continuum field plus the analytic unwrapped trajectory

\[
x(t)=x_0+U_s\sin(k_sy_0)(1-e^{-\nu k_s^2t})/(\nu k_s^2),
\qquad y(t)=y_0.
\]

The frozen contract says project RK2 is not used for the reference, no manufactured/MMS source is used, and no SPH residual correction is allowed.

## Run and evidence contract

The exact IDs are `g_shear_n24`, `g_shear_n32`, `g_shear_n48`, `g_shear_n32_dt_half`, and `g_shear_n48_rep2`. Their five output directories are unique and their status is `PREREGISTERED_NOT_EXECUTED`.

The future evidence covers viscous decay rate and amplitude, periodic particle trajectory, momentum, density drift, pressure, transverse leakage, viscous power, topology/resource safety, time-step isolation, and determinism. N=24/32/48, H/dx=4.5/5.049509756796392/5.5, main dt=6.25e-5, half dt=3.125e-5, and tick-defined common times are frozen.

All SHEAR1–SHEAR8 identifiers and thresholds are present. No shear benchmark was run during this audit. Shear contract audit: **PASS**.
