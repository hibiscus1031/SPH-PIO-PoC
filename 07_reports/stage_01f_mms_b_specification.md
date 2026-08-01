# Stage 01F MMS-B specification

`psi=sin(kx)sin(ky)`，`rho_B=rho0(1+epsilon psi)`，`a(t)=U_v exp(-lambda t)`，`u_B=[a sin(kx)cos(ky), -a cos(kx)sin(ky)]`，`p_B=c_s^2(rho_B-rho0)`。

手工导数为 `div(u_B)=0`、`u_B·grad(rho_B)=0`、`partial_t rho_B=0`、`partial_t u_B=-lambda u_B`、`laplacian(u_B)=-2k^2u_B`；对流加速度为 `(a^2 k/2)[sin(2kx),sin(2ky)]`；`grad(p_B)=c_s^2 rho0 epsilon k[cos(kx)sin(ky),sin(kx)cos(ky)]`。

外部加速度冻结为 `f_B=partial_t u_B+convection+grad(p_B)/rho_B-nu laplacian(u_B)`，代回冻结 WCSPH 连续方程后逐点闭合。
