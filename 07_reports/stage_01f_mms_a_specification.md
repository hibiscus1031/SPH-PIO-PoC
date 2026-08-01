# Stage 01F MMS-A specification

令 `xi=x-U_c t`：

- `rho_A=rho0[1+epsilon sin(k xi)sin(k y)]`；`u_A=[U_c,0]`；`p_A=c_s^2(rho_A-rho0)`。
- `partial_t rho_A=-rho0 epsilon k U_c cos(k xi)sin(k y)`。
- `grad rho_A=rho0 epsilon k[cos(k xi)sin(k y), sin(k xi)cos(k y)]`。
- `div(rho_A u_A)=U_c partial_x rho_A=-partial_t rho_A`。
- `grad p_A=c_s^2 grad rho_A`；material acceleration 与 `laplacian(u_A)` 均为零。
- `f_A=grad(p_A)/rho_A`，故 `-grad(p_A)/rho_A+f_A=0`，完整动量方程闭合。

闭式粒子轨迹为 `x_i(t)=wrap(x_i(0)+U_c t)`、`y_i(t)=y_i(0)`；仅验证公式，未运行 SPH。
