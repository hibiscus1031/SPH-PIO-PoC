# Publication P1 — Table package

所有表格均由 `publication_input_freeze_manifest.json` 中的只读机器 artifact 生成；不得脱离其解释边界。

## Table 1. Stage 03 status ledger

| 阶段 | 唯一状态 | 主要通过证据 | 主要边界 |
|---|---|---|---|
| Stage 03A | `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE` | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 | 尚无动态实现、trajectory payload 或计算资格化。 |
| Stage 03B | `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 | acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。 |
| Stage 03C | `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED` | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 | 未执行 multistep AD/FD、训练或 rollout 性能评价。 |
| Stage 03D | `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED` | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 | 144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。 |
| Stage 03D-R | `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED` | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 | 19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。 |

## Table 2. Dynamic reference trajectory inventory

| 层级 | 冻结对象 | 结果 | 证据角色与边界 |
|---|---|---|---|
| D-R1 | Lagrangian compression；coupled deformation | 两族PASS | 解析/MMS verification，不等于物理验证 |
| D-R2 | 同半离散DOP853 time reference | 6/6 PASS | 时间参考，不是空间真值 |
| D-R3 | oblique shear A/B | 两族PASS；6条exact trajectories | source-free independent validation |
| Acoustic | acoustic candidate | linear-regime conditional | 不外推为无限制精确D-R3 |
| Vortex | periodic vortex candidate | rejected as exact source-free | 不作为D-R3精确参考 |
| D-R4 | 外部V&V-qualified reference | NOT_AVAILABLE | 当前独立验证缺口 |

## Table 3. Implementation and structural gates

| 资格门 | 结果 | 状态 | 允许解释 |
|---|---:|---|---|
| Independent RK2 | 48/48 | PASS | 冻结RK2实现一致 |
| Zero correction | 288/288 | PASS | 与D0 bitwise等价 |
| Structural smoke | 72/72 | PASS | 结构守恒/等变等冻结门通过 |
| Checkpoint/resume | 6/6 | PASS | state/graph/history/RNG可复现 |
| One-step autograd | 6/6 | PASS | 一步梯度通路有限非零 |
| Dynamic training / performance | 0 / 0 | NOT_EXECUTED | 不可写为训练失败或性能不足 |

## Table 4. AD/FD failure taxonomy

| 主因 | 数量 | 解释边界 |
|---|---:|---|
| AD/FD方向或符号不一致 (`AD_FD_DIRECTION_OR_SIGN_MISMATCH`) | 5 | 归因诊断，不代表合同已修复 |
| 导数接近结构零 (`DERIVATIVE_NEAR_STRUCTURAL_ZERO`) | 29 | 归因诊断，不代表合同已修复 |
| FD非单调且无相邻稳定窗 (`FD_NONMONOTONE_NO_ADJACENT_WINDOW`) | 69 | 归因诊断，不代表合同已修复 |
| FD舍入误差主导 (`FD_ROUNDOFF_DOMINATED`) | 3 | 归因诊断，不代表合同已修复 |
| FD截断误差主导 (`FD_TRUNCATION_DOMINATED`) | 3 | 归因诊断，不代表合同已修复 |
| 固定图数值非光滑 (`NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH`) | 16 | 归因诊断，不代表合同已修复 |
| 未决 (`UNRESOLVED`) | 19 | 归因诊断，不代表合同已修复 |

## Table 5. Topology-event evidence

| TE1证据 | 结果 | 状态 | 禁止外推 |
|---|---:|---|---|
| edge birth | 1/1 | PASS | 非任意拓扑族 |
| edge death | 1/1 | PASS | 非连续edge membership |
| stage replay | 6/6 | PASS | 仅冻结TE1语义 |
| fixed-side gradients | 12/12 | PASS | 不穿过cutoff事件求导 |
| force jump | finite and bounded | PASS | 不声称事件处连续 |
| empty graph | deterministic | PASS | 不构造合成非物理pair |

## Table 6. Final claim/evidence matrix

| 主张类别 | 可写入正文 | 不可写入正文 | 主要证据状态 |
|---|---|---|---|
| 实现 | RK2 hybrid冻结实现通过 | solver performance verified | PASS |
| 退化极限 | zero correction 288/288 bitwise等价 | nonzero correction准确 | PASS |
| 守恒 | 540/540多阶段守恒检查通过 | 长时稳定性已证明 | PASS |
| 多步梯度 | 216/360稳定窗；144 failure | 全部梯度有效 | NOT_QUALIFIED |
| 失败归因 | mixed or unresolved；19未决 | 单一根因已解决 | UNRESOLVED |
| 拓扑 | TE1 birth/death与fixed-side通过 | cutoff membership可微 | COMPONENT PASS |
| 训练 | 未授权、未执行 | Transformer可训练 | NOT_EXECUTED |
| 性能 | 未测试 | rollout改进SPH或D3优于D1/D2 | NOT_TESTED |
