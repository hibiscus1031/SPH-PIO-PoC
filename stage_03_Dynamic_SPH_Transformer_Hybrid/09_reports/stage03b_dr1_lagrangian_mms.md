# Stage 03B D-R1 Lagrangian MMS qualification

## Family formulas

令 `k=2pi/L`、`tau=t cs/L`。Compression family 使用 `Ac=0.02/k`，`x=X+Ac sin(kX) sin(pi tau), y=Y`。Coupled family 使用 `Ax=0.012/k, Ay=0.010/k`，`x=X+Ax sin(kX)cos(kY)sin(2pi tau)`，`y=Y-Ay cos(kX)sin(kY)sin(2pi tau)`。

两族均由 `F=partial x/partial X`、`J=det F`、`rho=rho0/J`、`p=cs^2(rho-rho0)`、`u=partial_t x` 与 `D_tu=partial_t^2x` 生成。source 为 `f_MMS=D_tu+grad_x(p)/rho-nu laplacian_x(u)`；continuity source 为零。该 source 未被定义为 learned correction target。

## Closure and derivative audit

每族使用 8192 个预注册材料点，覆盖全部输出时刻、seam、extrema 和 Jacobian-risk 点。

| Family | min J observed / analytic lower bound | min rho | max Mach | continuity normalized | momentum-with-source | route disagreement max | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Compression | 0.996098 / 0.98 | 0.996113 | 0.0099999 | 2.86e-16 | 0 | 7.37e-14 | PASS |
| Coupled | 0.999228 / 0.978 | 0.999253 | 0.0119912 | 4.16e-16 | 0 | 1.85e-13 | PASS |

EOS 与 particle-path residual 均为 0，periodic mapping residual 为 4.44e-16。两个公式均未修改 amplitude 或观察后重试。

## Inventory

两族各生成 N=8、12、16 共 6 条 exact canonical NPZ 轨迹，每条 17 frames，保存 material labels、position、velocity、density、pressure、material acceleration、MMS source、Jacobian、state/graph hashes、reciprocal edge map、event codes、minimum separation 与 safety metrics。它们不是 training dataset。
