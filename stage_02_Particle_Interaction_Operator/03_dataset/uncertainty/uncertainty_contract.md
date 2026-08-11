# Stage 02B Uncertainty Contract

**性质：** 未来不确定度账本协议；本文件不计算误差、不运行收敛研究。

## 1. 禁止单一总 GCI

本阶段冻结：

> `GCI not justified`

不得生成或报告 single total GCI。原因是 reference、time、space、model-form、topology 与 resource 项并非天然
同分布、独立或可用一个渐近网格收敛模型合并。若未来某一空间子问题满足 GCI 前置条件，只能报告该明确
子问题的 component-specific GCI，并保持其他项分列；更改本合同需要新版本资格。

## 2. 六类强制账本

| 项 | 含义 | 最低证据 | 对标签资格的作用 |
|---|---|---|---|
| `reference_uncertainty` | analytic/MMS 评价、数值 reference、插值/敏感性等对 \(a_{ref}\) 的界 | value、units、norm、method、rule id、status、evidence | 必须 available 且通过预冻结资格规则 |
| `time_error` | 状态推进、时间离散和 comparison-time alignment 误差 | R2/步长敏感性或可审计上界 | 必须 isolated/bounded/not applicable，不能混入空间目标 |
| `space_error` | 候选粒子/空间离散分量及其分辨率敏感性 | 明确 support path、resolution family 与范数 | 是目标归因证据，不等于总误差 |
| `model_form_uncertainty` | continuous model、WCSPH/EOS/forcing 不一致或未决性 | model-form checklist 和 configuration identity | compatible 才可训练；misaligned 为 RX/rejected |
| `topology_uncertainty` | cutoff event 敏感性、图身份及结构缺陷状态 | graph hash、defect counts、reciprocal status | 结构缺陷 FAIL；合法 reciprocal crossing 单独记录 |
| `resource_uncertainty` | OOM、timeout、截断、device fallback 或未完成执行对结果身份的影响 | resource policy、峰值、停止线、退出状态 | PASS 才可训练；不得当作数值误差合并 |

## 3. 统一记录结构

每项使用 `availability`、`value_kind`、可选 `value`、`units`、`norm`、`method`、
`qualification_rule_id`、`status` 和 `evidence_uris`。分类项可用 `categorical_only`，不得为了相加而伪造数值。
`UNRESOLVED` 与零不确定度不同；`not_applicable` 必须附理由。

## 4. Reference uncertainty 的资格语义

`available` 意味着数值/分类结果、方法、单位、范数和证据均可机器审计，而不是仅出现字段名。未来 campaign
必须在生成前定义 \(u_{ref}\) 的 absolute floor、相对目标规则、零目标处理和 confidence/coverage 解释，形成
不可变 `qualification_rule_id`。本协议不凭空选择一个与具体 reference method 无关的数值阈值。

只有 `availability=available` 且 `status=PASS` 的 R1 reference uncertainty 能通过训练资格门。使用生成后
target 分布调节 floor/ratio 属于泄漏。

## 5. 误差分解状态

每个非目标项必须标为 `isolated`、`bounded`、`not_applicable`、`unresolved` 或 `failed`。只有前三项可支持
`discretization_attributed`；后两项使记录 diagnostic/rejected。cross terms 虽未单列为六类 uncertainty，仍须
在 target attribution evidence 中说明状态，不得被吸收到 `space_error`。

## 6. 不允许的操作

- 不把 resource/topology failure 转换为大误差条后继续训练；
- 不把 RX 的 model-form mismatch 当随机 uncertainty 平均掉；
- 不用 R3 validation 结果调节 uncertainty rule；
- 不因 \(\|\Delta a\|\) 接近零而删除样本或将相对不确定度写零；
- 不在不同 units/norms 间直接相加；
- 不把 Stage 01 plateau-aware 结论扩大为所有 resolution/support path 的 GCI 资格。
