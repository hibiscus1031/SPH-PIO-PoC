# Stage 01F final report

## 1. Stage 01E 冻结

Stage 01E tag `stage-01e-model-form-alignment-dominant` 固定于 `de0016ae2623ec0f03d1bd8486a8833dd185f3b2`；历史分类保持 `E_MODEL_FORM_ALIGNMENT_DOMINANT`。

## 2. WCSPH 连续方程约定

`dx/dt=u`；`partial_t rho+div(rho u)=0`；`partial_t u+(u·grad)u=-(1/rho)grad(p)+nu laplacian(u)+f_MMS`；`p=c_s^2(rho-rho0)`。`f_MMS` 是单位质量外部加速度；内部守恒与外部作用分开，动量比较 `d sum(m_i u_i)/dt` 与 `sum(m_i f_i)`。

## 3. 公共参数

Domain `[-1,1)^2`，rho0=1.0，c_s=20.0，nu=0.02，k=pi，U_ref=1.0，Ma=0.05，epsilon=0.0025，rho∈[0.9975,1.0025]，U_c=0.5，lambda=0.7，U_v=1.0，t∈[0,0.2]。

## 4. MMS-A 完整公式

`xi=x-U_c t`；`rho_A=rho0[1+epsilon sin(k xi)sin(ky)]`；`u_A=[U_c,0]`；`p_A=c_s^2(rho_A-rho0)`。`partial_t rho_A=-rho0 epsilon k U_c cos(k xi)sin(ky)`；`grad rho_A=rho0 epsilon k[cos(k xi)sin(ky),sin(k xi)cos(ky)]`；`div(rho_A u_A)=U_c partial_x rho_A`；`grad p_A=c_s^2 grad rho_A`。material acceleration 与 `laplacian u_A` 为零，`f_A=grad(p_A)/rho_A`。轨迹为 `x_i(t)=wrap(x_i(0)+U_c t)`、`y_i(t)=y_i(0)`。

## 5. MMS-B 完整公式

`psi=sin(kx)sin(ky)`；`rho_B=rho0(1+epsilon psi)`；`a=U_v exp(-lambda t)`；`u_B=[a sin(kx)cos(ky),-a cos(kx)sin(ky)]`；`p_B=c_s^2(rho_B-rho0)`。`div u_B=0`、`u_B·grad rho_B=0`、`partial_t rho_B=0`、`partial_t u_B=-lambda u_B`、`laplacian u_B=-2k^2u_B`；convection=`(a^2k/2)[sin(2kx),sin(2ky)]`；`grad p_B=c_s^2rho0 epsilon k[cos(kx)sin(ky),sin(kx)cos(ky)]`；`f_B=partial_t u_B+convection+grad(p_B)/rho_B-nu laplacian(u_B)`。

## 6. EOS、连续和动量闭合

| solution | point_set | point_count | minimum_density | maximum_density | maximum_eos_residual | maximum_continuity_residual | maximum_x_momentum_residual | maximum_y_momentum_residual | maximum_autograd_continuity_residual | maximum_autograd_momentum_residual | manual_autograd_maximum_difference | source_manual_autograd_maximum_difference | maximum_periodicity_residual | all_fields_finite |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MMS_A | random | 10000 | 0.9975004541841647 | 1.002499388252246 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 8.881784197001252e-16 | 8.881784197001252e-16 | 8.881784197001252e-14 | True |
| MMS_A | boundary_near | 72 | 0.9999999999927822 | 1.0007099648299023 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 4.440892098500626e-16 | 4.440892098500626e-16 | 6.050715484207103e-15 | True |
| MMS_B | random | 10000 | 0.9975006499129251 | 1.0024969234595926 | 0.0 | 6.505213034913027e-19 | 6.661338147750939e-16 | 8.881784197001252e-16 | 4.440892098500626e-16 | 8.881784197001252e-16 | 7.105427357601002e-15 | 1.7763568394002505e-15 | 8.881784197001252e-14 | True |
| MMS_B | boundary_near | 72 | 0.9999999999927822 | 1.0000000000072178 | 0.0 | 1.6155871338926322e-27 | 2.220446049250313e-16 | 1.9612805525230202e-16 | 0.0 | 2.220446049250313e-16 | 3.552713678800501e-15 | 2.220446049250313e-16 | 3.9968028886505635e-15 | True |

## 7. Manual/autograd 对照

最大差 `7.105427357601002e-15`；source 最大差 `1.7763568394002505e-15`，满足 1e-11 门。

## 8. 项尺度审计

| term | L1 | L2 | Linf | x_component_rms | y_component_rms | fraction_of_maximum_L2 |
|---|---|---|---|---|---|---|
| partial_time_velocity | 0.441841312188601 | 0.46148255334844906 | 0.698245264979846 | 0.32584702010268823 | 0.3267871884502243 | 0.17695907667447722 |
| convection | 1.3160673761767332 | 1.3771370098175848 | 2.2151238669547837 | 0.9751914280172717 | 0.9723723682473466 | 0.5280739042967967 |
| pressure_acceleration | 2.1247879855328824 | 2.2173770319038195 | 3.141313633254562 | 1.5706926782745811 | 1.5651470895827064 | 0.8502704801249913 |
| viscous_acceleration | 0.24918851196341224 | 0.2602657279745033 | 0.3937945451591367 | 0.18377035335356257 | 0.1843005870484544 | 0.09980091896909313 |
| manufactured_force | 2.2428022560299965 | 2.6078490124435003 | 4.425148346677687 | 1.8500717208178796 | 1.8379638460896093 | 1.0 |

最小/最大 L2 比 `0.09980091896909313` > 1e-4。

## 9. 粒子质量初始化

规则格点 `V_i^0=(2/N)^2`、`m_i=rho_exact(x_i,y_i,0)V_i^0`；质量固定；MMS-A/B 的解析密度沿各自粒子轨迹不变；不覆盖 numerical kernel density；无 jitter 质量设计。

## 10. Source injection contract

接口按 numerical position 与 physical stage time 在 start/midpoint 分别重算。禁止复用起点 source、analytic position、numerical residual feedback、混入内部 pair antisymmetry 或 internal-force-zero gate；external momentum/power 单独审计。

## 11. MMS-B 独立轨迹参考计划

后续独立求解 `dx/dt=u_exact`，DOP853 或同等级，rtol≤1e-12、atol≤1e-14；使用连续 unwrapped trajectory，仅场评价时 wrap，并做时间步敏感性。Stage 01F 未生成正式轨迹。

## 12. 后续误差指标

只定义：particle-position、velocity、density、pressure 的 L1/L2/Linf；one-step local truncation error；trajectory self-convergence；internal-force balance；external-force momentum balance；energy balance with external power；CPU determinism；resource policy。必须区分 continuum closure、trajectory-reference error、SPH spatial error、RK2 temporal error 与 forcing discretization error。

## 13. 唯一 MMS 规范状态

**MMS_SPECIFICATION_PASS**

## 14. Stage 01F2 资格

具备申请 Stage 01F2 设计审计资格。

## 15. V3 和 Stage 02 边界

V3、Stage 02、Stage 01F2、训练和学习标签均未开始。
