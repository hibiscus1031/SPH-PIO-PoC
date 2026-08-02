# Stage 01F5-P N64 条件依赖图

```mermaid
flowchart TD
    A["N16/N24/N32/N48 完成"] --> B["计算四个 N64 trigger"]
    B --> C["提交 immutable n64_trigger_decision.json"]
    C -->|NOT_TRIGGERED| D["七条条件 run 全部标记 NOT_TRIGGERED；不运行"]
    C -->|TRIGGERED| E1["f5_n64_smoke_a"]
    C -->|TRIGGERED| E2["f5_n64_smoke_b"]
    E1 -->|PASS| F["两条 smoke 均 PASS"]
    E2 -->|PASS| F
    F --> G["formal-space t_final 从冻结来源解析"]
    G --> H1["f5_ref_space_b_n64_baseline"]
    G --> H2["f5_ref_space_b_n64_tighter"]
    G --> H3["f5_ref_space_b_n64_third"]
    H1 -->|PASS| I["三层 sensitivity PASS"]
    H2 -->|PASS| I
    H3 -->|PASS| I
    I --> J1["f5_space_a_n64"]
    I --> J2["f5_space_b_n64"]
```

## 阻断规则

- 未提交 trigger decision：任何 N64 条目均不得运行。
- NOT_TRIGGERED：七条条件条目全部记为 `NOT_TRIGGERED`，不得运行。
- 任一 smoke 失败：不得运行 N64 reference 或正式 N64。
- Formal-space `t_final` 未从冻结来源解析：不得运行三层 reference；执行 manifest 状态为 incomplete。
- 任一 reference 或 sensitivity 失败：不得运行正式 N64。

当前审计停在 formal-space `t_final` 参数缺口之前；事实上因执行 manifest 不完整，连 smoke 也未获启动资格。本阶段所有节点的数值执行计数均为 0。
