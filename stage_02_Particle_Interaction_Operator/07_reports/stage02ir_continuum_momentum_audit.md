# Stage 02I-R Continuum Momentum Audit

## Frozen operator

The audited periodic-vortex reference operator is

\[
a_{ref}=-\frac{\nabla p}{\rho}+\nu\nabla^2v,
\qquad
F_{continuum}=\int_\Omega \rho a_{ref}\,dV.
\]

The zero-force conclusion was not assumed. Pressure, viscosity, and total integrals were evaluated through three independent routes.

## Results

| method | pressure integral | viscosity integral | total integral |
|---|---:|---:|---:|
| analytic closed form | (0, 0) | (0, 0) | (0, 0) |
| Fourier spectral zero mode | (0, 0) | (0, 0) | (0, 0) |
| 512×512 periodic midpoint grid | (-9.916e-19, -7.142e-19) | (-3.317e-20, -3.838e-20) | (-1.025e-18, -7.526e-19) |

The analytic result follows from the vanishing integral of periodic gradients and non-zero trigonometric modes. The spectral result independently evaluates the exact zero mode. The high-order grid result provides a numerical cross-check at roundoff scale.

## Qualification

Pressure, viscosity, and total continuum momentum balances are PASS. The frozen continuum operator is compatible with zero global internal force; `CONTINUUM_OPERATOR_NOT_PAIR_FORCE_COMPATIBLE` is not triggered. Consequently, the two jitter residuals cannot be attributed to a non-zero continuum integral.

