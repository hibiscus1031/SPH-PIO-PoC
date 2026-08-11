# 全项目状态本体

[PROJECT_EVIDENCE] 本体用于跨阶段归一化，不替代各阶段 exact status。

| 术语 | 严格含义 |
|---|---|
| PASS | 预注册的整体门全部满足；只适用于明确范围。 |
| FAIL | 已执行且至少一个决定性门失败。 |
| NOT_QUALIFIED | 已执行但不足以产生资格；可含通过的组成部分。 |
| EVIDENCE_INCOMPLETE | 结论所需证据缺失或不可用，不能判为失败。 |
| NOT_AUTHORIZED | 上游合同未授权该活动。 |
| NOT_EXECUTED | 活动没有执行；不得改写为 FAIL。 |
| DIAGNOSTIC | 仅用于归因或机制理解，不产生资格。 |
| CONDITIONAL | 在明确条件和边界内成立。 |
| TERMINATED | 路线按预注册停止规则关闭。 |
| PAUSED | 路线暂停，等待新假设或新授权。 |
| QUALIFIED_COMPONENT | 组成分量通过，但总体不因此通过。 |

## 不可违反规则

- `NOT_EXECUTED` 不等于 `FAIL`。
- `QUALIFIED_COMPONENT` 不得提升为整体 `PASS`。
- 后续诊断不得改写冻结的历史 verdict。
