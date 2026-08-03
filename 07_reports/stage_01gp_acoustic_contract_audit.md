# Stage 01G-P — Acoustic-wave contract audit

## Frozen linear theory

The Stage 01G acoustic design defines

\[
\rho=\rho_0[1+\epsilon\cos(kx)\cos(c_skt)],
\]

\[
u_x=c_s\epsilon\sin(kx)\sin(c_skt),\qquad u_y=0,
\]

\[
p=c_s^2(\rho-\rho_0).
\]

Parameters are \(\rho_0=1\), \(c_s=20\), \(\nu=0\), \(k=\pi\), and \(t_f=0.1\). The main amplitude is 0.005; the additional audit amplitudes are 0.0025 and 0.01. All are explicit in both the frozen YAML and run matrix.

## Claim and reference boundary

The permitted claim is exactly **linear-acoustic-regime validation**. Finite-amplitude model-form departure is retained as uncertainty. The design does not claim finite-amplitude nonlinear validation or full-compressible validation.

The reference is independent linear theory: no MMS source, no project RK2 reference, and no SPH-residual correction. Exact density is evaluator-only and cannot overwrite kernel-sum numerical density.

## Run contract

The seven exact IDs comprise three main-amplitude resolutions, one N32 half-dt isolation run, one N48 repeat, and two N48 amplitude-audit runs. All seven IDs and output directories are unique and `PREREGISTERED_NOT_EXECUTED`. ACOUSTIC1–ACOUSTIC10, tick-defined common times, metrics, and thresholds are present.

No acoustic benchmark was run during this audit. Acoustic contract audit: **PASS**.
