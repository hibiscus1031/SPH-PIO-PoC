# R2S Semidiscrete Spatial Reference Definition

For each particle, R2S uses the same particle state, EOS-derived pressure, cubic-spline kernel weights, physical pressure/
viscosity model, timestamp, and neighbor graph as baseline SPH. In normalized minimum-image coordinates
\(\xi_{ij}=r_{ij}/H\), it fits neighbor differences with the quadratic basis

\[
[\xi_x,\xi_y,\tfrac12\xi_x^2,\xi_x\xi_y,\tfrac12\xi_y^2].
\]

The fitted coefficients recover \(\nabla p\) and \(\nabla^2v\) after support-scale conversion. The spatial reference is

\[
a_{R2S,i}=-\frac{\nabla p_i^{WLS}}{\rho_i}+\nu\nabla^2v_i^{WLS},
\qquad
\Delta a_{space,i}=a_{R2S,i}-a_{SPH,i}.
\]

This definition contains no trajectory, velocity finite difference, or time integrator. “Higher spatial fidelity” is
qualified only when the local basis is full rank, conditioning and quadratic reproduction pass, solver sensitivity passes,
and the state/configuration/graph/determinism contracts pass.

R2S is a diagnostic spatial reference class. Its current definition does not claim pairwise force antisymmetry, linear/angular
momentum conservation, training permission, or model performance.
