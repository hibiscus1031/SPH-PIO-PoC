# Analytic closure contract

D-R1 Route 1 is a frozen SymPy-derived closed-form material-map route. With `F=dx/dX`, it applies `D_x,a g=sum_A (F^{-1})_{A a} partial_XA g`, computes `rho=rho0/det(F)`, physical velocity and material acceleration from tau derivatives, `grad_x p`, `laplacian_x u=sum_a D_x,a(D_x,a u)`, and `f_MMS=D_t u+grad_x(p)/rho-nu laplacian_x(u)`.

Route 2 independently differentiates the primitive material map with PyTorch automatic differentiation in float64; it does not call Route 1 derivative expressions. The audit uses 8192 preregistered points cycling through every output time and including seam/extrema/Jacobian-risk points.

The frozen D-R1 gates are EOS absolute residual `<=1e-12`, normalized continuity/source-momentum and particle-path residuals `<=1e-10`, derivative-route normalized disagreement `<=1e-9`, positive Jacobian/density, Mach `<=0.03`, and periodic-map closure. Formula or amplitude retry after observation is forbidden.
