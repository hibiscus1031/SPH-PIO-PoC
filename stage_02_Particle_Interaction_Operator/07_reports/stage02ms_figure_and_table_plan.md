# Stage 02M-S — Figure and table plan

| Figure | Title | Form | Integrity rule |
|---:|---|---|---|
| 1 | V&V-first PIO qualification pipeline | 流程图 | 显示资格门、失败保留与停止规则；不显示 solver 成功箭头。 |
| 2 | Reference and target qualification hierarchy | 层级图 | 区分 R1/R2/R3/RX 和 candidate/qualified/pair-compatible。 |
| 3 | Stage decision/failure tree | 决策树 | 保留所有 NOT READY/NOT QUALIFIED 节点。 |
| 4 | Blind dataset family/split/leakage structure | 网络/分组图 | family为统计单元；不得以粒子数扩充 n。 |
| 5 | K0/K1/K2 architecture and conservation contract | 结构示意 | K0标为 diagnostic，K1/K2标结构合格，不画性能排序。 |
| 6 | Static fitting v0.1 and v0.2 train/validation trajectories | 全 seed 轨迹 | 九条seed全部展示；v0.1/v0.2不同protocol/family不得作paired significance。 |
| 7 | Frozen gate outcomes across seeds | 门槛矩阵 | 同时展示A-E，突出B train-fit failure；validation/test PASS不着成功色。 |
| 8 | Supported/unsupported claim boundary | 边界图 | 明确 supported/conditional/unsupported，不用营销性箭头。 |

Tables: Stage status ledger; reference qualification; dataset inventory; architecture hard gates; v0.1/v0.2 static fitting results; final evidence/claim matrix.

All failed seeds remain visible; particle count is never treated as sample count; validation/test PASS is not colored or captioned as overall model success.
