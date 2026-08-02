# Stage 01F5-P 原始矩阵只读审计

## 冻结身份

Stage 01F5 证据提交 `ca297db20149765091312ac27843a8c20d4e9943` 的历史状态保持 `PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED`。Annotated tag `stage-01f5-requalification-design-approved` 精确指向该提交。指定的 9 项 Stage 01F5 证据 SHA-256 全部复核通过。

原始矩阵 SHA-256 为 `d0e84aed88018c5ed9edddc6fd15240cfc319b016f768c90f528053bd3bf9a80`。它包含 64 行：62 行无条件计划和 2 行条件计划；条件 ID 仅为 `f5_space_a_n64`、`f5_space_b_n64`。

## 条件分支缺口

冻结空间协议已经要求：正式 N64 前运行 20-step smoke；触发后通过资源、cutoff margin 与 topology 预审；MMS-B 正式空间误差具有独立连续轨迹参考和三层 sensitivity。但原始 64 行没有为以下必要依赖分配 ID：

- `f5_n64_smoke_a`
- `f5_n64_smoke_b`
- `f5_ref_space_b_n64_baseline`
- `f5_ref_space_b_n64_tighter`
- `f5_ref_space_b_n64_third`

这是一项前执行清单完整性缺口，不追溯修改 Stage 01F5 的历史状态或原矩阵。

## Formal-space t_final 审计

原预注册配置在 `main_configuration` 和 `heldout` 中分别定义了 `t_final=0.015`，但 `spatial_matrix` 没有 `t_final`。原 CSV 也没有 `t_final` 字段，正式空间行不能提供该值。因此 MMS-B N64 reference 的 formal-space `t_final` 无法从用户指定的冻结来源唯一读取。

本审计没有把主配置或 held-out 的数值推断为空间数值，也没有修改旧文件。按预注册规则，结论必须为 `EXECUTION_MANIFEST_INCOMPLETE`。
