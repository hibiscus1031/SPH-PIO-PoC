# 全项目证据等级矩阵

[PROJECT_EVIDENCE] 证据上限不是单一最高数字，而是不同路线的分层状态。

| 等级 | 名称 | 状态 | 证据边界 |
|---|---|---|---|
| L0 | specification | achieved | Stage 01–03 多阶段合同、阈值、停止规则与哈希冻结 |
| L1 | implementation | achieved | Stage 01 SPH 路径、Stage 02 K1/K2、Stage 03 D0–D3/RK2 |
| L2 | code verification | achieved | 算子、守恒、zero-correction、one-step AD、图更新语义 |
| L3 | solution verification | partial/failed | MMS 实现与 plateau-aware 子路线通过；Stage 01 V2 最终 FAIL |
| L4 | reference qualification | achieved_with_scope | Stage 02 Fourier/analytic；Stage 03 D-R1/D-R2/D-R3；D-R4 unavailable |
| L5 | data qualification | achieved_static_scope | Stage 02J-W 20-record blind multifamily static pair dataset |
| L6 | structural model qualification | achieved | K1/K2 antisymmetry与结构门；Stage 03实现资格 |
| L7 | training qualification | failed_static/not_executed_dynamic | static fitting v0.1/v0.2 未资格；动态训练未授权 |
| L8 | rollout validation | not_executed | autonomous rollout 未授权/未执行 |
| L9 | physical validation | partial/unavailable | 独立 shear/acoustic 有边界；D-R4 不可用 |
| L10 | cost/utility | not_executed | 没有完整性能、成本或效用比较 |

[PROJECT_EVIDENCE] Stage 02/03 尚未达到正式动态训练资格、autonomous rollout、full solver performance 或 D-R4 physical validation。
