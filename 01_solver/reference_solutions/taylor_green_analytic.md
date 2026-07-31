# Two-dimensional periodic Taylor–Green reference

The validation domain is \([-1,1)^2\).  The official diffSPH example uses
`wave_number=2`, yielding the initial velocity

\[
u_x(x,y,0)=-U_0\sin(\pi x)\cos(\pi y),\qquad
u_y(x,y,0)= U_0\cos(\pi x)\sin(\pi y).
\]

For the incompressible Navier–Stokes Taylor–Green solution with kinematic
viscosity \(\nu\), the velocity reference is

\[
\mathbf{u}(x,y,t)=\mathbf{u}(x,y,0)\exp(-2\nu\pi^2t).
\]

Consequently, its kinetic energy decays as
\(\exp(-4\nu\pi^2t)\).  The adapter evaluates this reference at the current
periodically wrapped particle positions.

Important limitation: in official commit `fff180c`, the reachable DeltaSPH
velocity-diffusion function hard-codes its dimensionless coefficient
\(\alpha=0.01\); changing `config["diffusion"]["alpha"]` does not affect that
path.  The official notebook estimates

\[
\nu_{\mathrm{eff}} =
0.01\,c_s h\,\frac{5}{4(2d+2)}.
\]

Because the official setup has \(c_s\propto h/\Delta t\), this estimate varies
as \(h^2\) at fixed time step.  Stage 01 therefore uses a resolution-specific
analytical decay for diagnostics and does **not** call the three-resolution
comparison a fixed-Re convergence study.

The weakly compressible numerical solution is not expected to match the
incompressible density identically; density fluctuation is reported separately.
