# Stage 01F5 最终报告

## 1. Stage 01F4 冻结

Stage 01F4 最终证据提交为 `82de6171a0be9818303acca539bffc8d3ee21c22`，唯一状态为 `PLATEAU_AWARE_PROTOCOL_APPROVED`。Annotated tag `stage-01f4-plateau-aware-protocol-approved` 精确指向该提交。Stage 01F4 的 7 项指定证据 SHA-256 全部复核通过。

`stage-01f3c-ct2-mixed-or-unresolved` 仍指向 `f831d4fa7d63ad3357e2b1e84c1260d7f3c46a2e`。

## 2. Stage 01F3B/F3C 历史状态

Stage 01F3B 保持 `MMS_CONVERGENCE_VERIFICATION_FAIL`；Stage 01F3C 保持 `CT2_MIXED_OR_UNRESOLVED`。本阶段未修改或重新分类任何历史状态、文件、数据、轨迹、标签或失败证据。

## 3. 数值运行数

本阶段实际数值运行数为 `0`。没有导入或调用动态 solver，没有运行 SPH、RK2、DOP853、参考轨迹、时间收敛或空间收敛，没有生成 reference NPZ。

## 4. 全新 N20 主配置

MMS-A/MMS-B 共用 N20、400 粒子、`dx=0.1`、`H/dx=4.357388321059432`、`H=0.4357388321059432`、`t_final=0.015`。五级时间步为 `1e-3` 至 `6.25e-5`，共同时间为 `0.000:0.001:0.015` 共 16 个且禁止插值。静态 novelty audit 通过，旧轨迹不得作为新证据。

## 5. N28 held-out

沿用 Stage 01F4 封存的 N28、784 粒子、`dx=2/28`、`H/dx=4.75`、`t_final=0.015` 和相同五级时间步、16 个共同时间。该身份未根据任何新结果改变。

## 6. 三层半离散参考设计

未来参考固定使用 production sparse SPH RHS、SciPy DOP853、continuous unwrapped positions，periodic wrap 只用于场量/邻域评价。Baseline、tighter、third 分别使用 `(rtol,atol,max_step)`：`(1e-12,1e-14,3.125e-5)`、`(1e-13,1e-15,1.5625e-5)`、`(1e-13,1e-15,7.8125e-6)`。

三层 finite、两组 sensitivity、按字段/范数 reference uncertainty、每解至少 10 状态 sparse/dense 抽查及零 structural topology defects 都是硬要求。允许 reciprocal cutoff crossing，不要求 edge identity 恒定。

## 7. 主时间矩阵

主配置冻结 6 条参考与 10 条 RK2 未来运行。每条 RK2 使用独立子进程和新输出目录，并在两个共主范数上评价 position/velocity。

## 8. T1–T5

时间误差直接定义为 `q_RK2-q_semidiscrete`。T1 要求四个字段—范数组合逐级严格下降；T2 要求 fitted order `>=1.80`；T3 要求最细三层局部阶中位数位于 `[1.70,2.30]`；T4 要求每组合至少 4 点高于匹配 reference floor 20 倍；T5 要求 self-difference 最细/最粗比 `<=0.30`。任一 T 门失败都不能判 PASS。

## 9. P1–P3

P1 要求最细 total error 与空间平台相对距离 `<=1%`；P2 要求最细 time/space `<=1%`；P3 要求 total exact error finite 且预登记比值 `<=2.0`。平台内不要求 total exact error 严格单调。cross term、cosine 和平方范数重构只作必报诊断，符号不是门。

## 10. Held-out 门

H1/H2 要求 position/velocity 的 endpoint/integrated time error 下降且四个 fitted order `>=1.80`；H3/H4 要求最细平台距离及 time/space 均 `<=1%`；H5 要求 reference、source、守恒、topology、resource、determinism 全部通过。不要求 cross term 同号、平台接近方向相同或 total exact error 单调。

## 11. 空间时间步隔离

未来先只在 N32 运行 MMS-A/MMS-B 的 `6.25e-5` 与 `3.125e-5` 共四条隔离轨迹。任一 position/velocity/density/pressure endpoint L2 相对变化大于 0.10 时选择 `3.125e-5`，否则选择 `6.25e-5`。决定必须在正式 N16/N24/N48 前写入 immutable 文件，查看空间趋势后不可更改。

## 12. 正式 consistency path

正式路径冻结为 N16/24/32/48，对应 `H/dx=4.06155281280883/4.5/5.049509756796392/5.5`。每个 MMS 的 position、velocity、density、pressure 均须通过 S1–S4：八条主轨迹和安全门完整、N48 优于 N16、四级严格下降、global slope 为正。结果只能称为 `increasing-neighbor consistency-path convergence`。

Observed order/GCI 按变量独立资格化；六项前置条件不全时必须写 `GCI not justified`。不得把路径 GCI 称为 fixed-stencil single-h GCI。

## 13. 条件 N64

非单调、N48/N32 比大于 0.95、局部阶异号或近渐近区不清楚时触发 N64。运行前必须通过 20-step smoke、peak RSS `<2 GB`、预计 wall time `<2 h`、cutoff margin `>1e-12`、structural defects `=0`。启动后不得删除不利结果。

## 14. 硬安全和确定性

所有未来轨迹独立子进程、默认 cyclic GC、`torch.no_grad()`、时间循环内无 `gc.collect()`，父进程只接收标量树和相对路径；每步 source 仅 start/midpoint 两次。力、组装、动量、黏性、topology、最小间距、RSS、步时和子进程回收门限已全部冻结。

六条 `_rep2` 必须在 scalar summary、positions、unwrapped positions、velocities、densities、pressures、masses 与 topology event-sequence hash 上 bitwise identical。

## 15. 完整运行 ID 清单

主参考（6）：

- `f5_ref_main_a_baseline`, `f5_ref_main_a_tighter`, `f5_ref_main_a_third`
- `f5_ref_main_b_baseline`, `f5_ref_main_b_tighter`, `f5_ref_main_b_third`

主 RK2（10）：

- `f5_main_a_dt1e3`, `f5_main_a_dt5e4`, `f5_main_a_dt2p5e4`, `f5_main_a_dt1p25e4`, `f5_main_a_dt6p25e5`
- `f5_main_b_dt1e3`, `f5_main_b_dt5e4`, `f5_main_b_dt2p5e4`, `f5_main_b_dt1p25e4`, `f5_main_b_dt6p25e5`

Held-out 参考（6）：

- `f5_ref_hold_a_baseline`, `f5_ref_hold_a_tighter`, `f5_ref_hold_a_third`
- `f5_ref_hold_b_baseline`, `f5_ref_hold_b_tighter`, `f5_ref_hold_b_third`

Held-out RK2（10）：

- `f5_hold_a_dt1e3`, `f5_hold_a_dt5e4`, `f5_hold_a_dt2p5e4`, `f5_hold_a_dt1p25e4`, `f5_hold_a_dt6p25e5`
- `f5_hold_b_dt1e3`, `f5_hold_b_dt5e4`, `f5_hold_b_dt2p5e4`, `f5_hold_b_dt1p25e4`, `f5_hold_b_dt6p25e5`

空间时间步隔离（4）：

- `f5_space_iso_a_dt6p25e5`, `f5_space_iso_a_dt3p125e5`
- `f5_space_iso_b_dt6p25e5`, `f5_space_iso_b_dt3p125e5`

正式空间（8）：

- `f5_space_a_n16`, `f5_space_a_n24`, `f5_space_a_n32`, `f5_space_a_n48`
- `f5_space_b_n16`, `f5_space_b_n24`, `f5_space_b_n32`, `f5_space_b_n48`

确定性重复（6）：

- `f5_main_a_dt6p25e5_rep2`, `f5_main_b_dt6p25e5_rep2`
- `f5_hold_a_dt6p25e5_rep2`, `f5_hold_b_dt6p25e5_rep2`
- `f5_space_a_n32_rep2`, `f5_space_b_n32_rep2`

MMS-B 空间连续参考（12）：

- `f5_ref_space_b_n16_baseline`, `f5_ref_space_b_n16_tighter`, `f5_ref_space_b_n16_third`
- `f5_ref_space_b_n24_baseline`, `f5_ref_space_b_n24_tighter`, `f5_ref_space_b_n24_third`
- `f5_ref_space_b_n32_baseline`, `f5_ref_space_b_n32_tighter`, `f5_ref_space_b_n32_third`
- `f5_ref_space_b_n48_baseline`, `f5_ref_space_b_n48_tighter`, `f5_ref_space_b_n48_third`

条件 N64（2）：`f5_space_a_n64`, `f5_space_b_n64`。

无条件计划合计 62，含条件 N64 的完整冻结矩阵共 64；全部 ID 和输出目录唯一。

## 16. 防事后调参

Run IDs、参数、共同时间、参考容差、主范数、T/P/H/S 门、reference floor、N64 条件、失败处理、资源上限、配置 SHA-256 与设计提交均须在首条轨迹前冻结。首条轨迹后不得删门、放宽阈值、改变范数、替换 held-out/主配置、补入旧轨迹、删除不利 run 或修改 branch trigger。

## 17. 唯一设计状态

`PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED`

Stage 01F4 冻结、N20 novelty、N28 identity、64 个唯一 run IDs、T/P/H/S、安全、确定性、条件分支、零数值运行与 provenance 全部完整。该状态不重新判定任何历史结果。

## 18. Stage 01F5B 申请资格

具备申请 `Stage 01F5B — One-shot plateau-aware MMS requalification execution` 的资格。该资格只允许提出执行申请；本阶段没有启动或自动运行 Stage 01F5B。

## 19. 下游仍未开始

Stage 01G、V3 和 Stage 02 仍未开始；未生成 V2、Stage 01G、V3 或 Stage 02 资格。训练和学习标签均未开始。
