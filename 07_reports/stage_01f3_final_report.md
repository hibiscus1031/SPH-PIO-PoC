# Stage 01F3 final report

## 1. Stage 01F2 冻结

`dd28381`、evaluator v2、annotated tag 和 26 项 SHA-256 manifest 全部通过；Stage 01F/01F2 原文件未修改。

## 2. 前置门

完整 pytest `219 passed`。Stage 01F2 身份、source-disabled、解析/轨迹参考及两条新 N16 10-step smoke 全部 PASS。

## 3. 半离散 DOP853 参考

MMS-A 双参考通过。MMS-B 位置/速度敏感性分别为 `2.55e-15`/`3.16e-14`，但 baseline/sensitivity 分别出现 28/27 个 edge identity，edge count 为 12480–12672，违反 topology identity 硬门。

## 4. RK2 半离散时间阶

未运行。参考硬门失败后禁止启动五级 RK2 矩阵，因此 SD1–SD5 未评价，无正式 RK2 时间阶。

## 5. MMS-A 连续时间误差

未运行，CT1–CT5 未评价。

## 6. MMS-B 连续时间误差

未运行，CT1–CT5 未评价。

## 7. 空间时间步隔离

未运行，空间 dt 未选择。

## 8. MMS-A 空间误差

未运行，A-S1–A-S6 未评价。

## 9. MMS-B 空间误差

未运行，B-S1–B-S6 未评价。

## 10. Consistency path

N16/N24/N32/N48/N64 的 ratio、H、初始 edge count 和 shell margin 已在任何空间轨迹前冻结。初始 margin 为正，但并未阻止 MMS-B 动态拓扑切换。

## 11. Fixed-ratio comparison

未获授权运行，不能评价 quadrature floor 或误差平台。

## 12. 条件 N64

未触发也未运行；阶段已在更早的 reference hard gate 停止。

## 13. 内部守恒、外力和能量诊断

前置 smoke 的内外力硬门通过。Reference 失败并非守恒或非有限值问题，而是 topology identity switching。正式能量矩阵未运行。

## 14. 资源和确定性

前置轨迹资源与回收通过，峰值 RSS 约 264 MB。正式矩阵和规定的四组重复未运行，不能授予完整资源/确定性资格。

## 15. GCI 资格

GCI not justified。没有正式空间误差序列，未计算任何外推或 GCI。

## 16. 数值不确定性

主导限制是“初始 shell-safe ratio 不能保证 MMS-B 动态半离散轨迹的 edge identity 稳定”。其他误差来源见独立 uncertainty report。

## 17. 所有失败与限制

唯一硬失败为 MMS-B 半离散参考 topology identity。其数值敏感性、有限性和 topology structural audit 均通过，但未预登记 edge switching 使参考不具资格。后续所有矩阵均按协议未运行。

## 18. 唯一 Stage 01F3 状态

**MMS_CONVERGENCE_VERIFICATION_FAIL**

## 19. Stage 01G 申请资格

不具备申请 Stage 01G 的资格。必须先解决或重新审计动态 topology identity 与半离散参考合同。

## 20. 后续边界

未启动 Stage 01G、V3 或 Stage 02；未训练网络，未生成学习标签。Stage 01D2 历史失败状态保持不变。Stage 01F3 在失败证据封存后停止。
