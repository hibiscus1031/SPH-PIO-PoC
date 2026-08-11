# Stage 03B D-R3 source-free oblique shear

通用 family 为 `kappa=(2pi/L)(m,n)`、`e_perp=(-n,m)/sqrt(m^2+n^2)`，`rho=rho0, p=0`，

`u=U_b+A e_perp sin(kappa·(x-U_b t)+phi) exp(-nu|kappa|^2t)`。

材料粒子轨迹使用冻结闭式表达 `x(t)=x0+U_b t+e_perp A sin(s0)[1-exp(-nu|kappa|^2t)]/(nu|kappa|^2)` 并周期 wrap。A case 为 `(m,n)=(1,2), phi=0.17, U_b/cs=(0.011,-0.007), A/cs=0.015`；B case 为 `(2,-1), 0.31, (-0.006,0.009), 0.012`。

| Case | momentum residual | continuity | path residual | max Mach | deterministic graph | Verdict |
|---|---:|---:|---:|---:|---|---|
| A | 1.24e-16 | 0 | 0 | 0.0280011 | PASS | PASS |
| B | 1.40e-16 | 0 | 0 | 0.0197422 | PASS | PASS |

密度和压力保持 exact/roundoff constant，source exactly absent，Galilean/transverse/rotation consistency 均在 roundoff。两族各生成 N=8、12、16 共 6 条、每条 17-frame canonical exact trajectory。其角色严格为 `independent_source_free_validation_only`，D-R2 身份未混用。
