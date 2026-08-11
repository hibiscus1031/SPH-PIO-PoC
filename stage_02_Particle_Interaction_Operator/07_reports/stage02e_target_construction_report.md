# Stage 02E — Qualified Target Construction Report

## 1. Stage 02D preservation

Stage 02D 的4 diagnostic、2 rejected、0 attribution PASS 与
`stage02e_data_qualification_upgrade_authorized=false` 均保持。Stage 02E 未改写或删除既有 records，也未直接
升级 R2 labels。

## 2. Excitation matrix

8-case audit matrix 覆盖3级 resolution、3级 H/dx、regular/5%/10% disorder 和2个 initial-condition families。
Resolution path 固定 support/disorder/state；support path 固定 N/disorder/state，从设计上分离 N 与 H/dx。

## 3. R2 target construction

目标继续为

\[
\Delta a=a_{ref}-a_{SPH}.
\]

R2 reference 是同一中心状态/时刻/config/graph contract 下的 DOP853 五点速度导数；sparse SPH RHS 在中心状态
瞬时评价。8/8 reference qualification audit PASS for audit use。

## 4. Non-zero target audit

8/8 targets 非零，完整空间分布和 provenance 已保存，未删除小 target。L2 为约 `4.06e-8`–`3.25e-7`，Linf
为约 `5.61e-8`–`4.38e-7 m s^-2`。

## 5. Attribution results

分解显示 sparse/dense instantaneous spatial-assembly difference 为0或 `5.82e-18` roundoff，而 temporal
five-point reference component 几乎精确等于 observed target。Window sensitivity 与 target 同量级。因此所有
targets 保持 diagnostic；非零不等于 discretization-attributed。

Resolution magnitude 增加且 Fourier direction 稳定；support H/dx 2.6→3.0 平台；disorder L2 非单调、Linf
增加。但这些都是 reference-temporal error trends，禁止作为性能、收敛或 correction evidence。

## 6. Candidate target pool

Pool 包含8 diagnostic audit candidates、0 rejected、0 `candidate_discretization_target`，并明确
`training_permitted=false`。Stage 02D 的2个 topology rejected records 继续在原数据中保留。

## 7. Stage 02F decision

`stage02f_data_qualification_authorized=false`，原因是没有 candidate 达到六分量6/6 PASS。Stage 02E construction
完成只表示非零候选、归因和 provenance 已完成，不表示获得训练数据。

## 8. Historical boundary

Stage 01G `V2_QUALIFICATION_FAIL`、Stage 01H `FINITE_RESOLUTION_DOMINANT` 和 viscosity operator form
`NOT CONFIRMED` 均保持。Stage 01H diagnosis 未被写成 operator corrected。
