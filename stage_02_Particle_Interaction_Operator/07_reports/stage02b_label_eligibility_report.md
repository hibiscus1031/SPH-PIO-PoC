# Stage 02B — Label Eligibility Report

机器可读规则见 `../03_dataset/eligibility/label_eligibility_rules.yaml`，版本为
`pio-label-eligibility-1.0.0`。

## 唯一允许的未来训练候选

`eligible_for_future_training` 只有在以下条件全部满足时才能由规则导出：

- reference 为允许训练目标的 R1，且 class/model-form 证据有效；
- reference uncertainty available，并对预冻结 `qualification_rule_id` 为 PASS；
- state/configuration/neighbor graph 三个 SHA-256 hash 存在且复核一致；
- topology PASS，四类结构缺陷均为零；
- resource PASS；
- determinism PASS；
- model-form compatible；
- failure flags 为空，全部数值 finite；
- same-state alignment、目标符号、discretization attribution 与 leakage gate 均 PASS。

合法 reciprocal cutoff crossing 不构成 topology defect，但必须记录。

## Diagnostic 与 rejected

- `diagnostic`：R2 时间/状态 reference、R3 独立 validation，或 evidence/uncertainty/attribution 尚未解决但无
  已确认硬失败的记录；
- `rejected`：RX/model-form mismatch、topology/resource/determinism/nonfinite/leakage/sign/hash 等硬失败记录。

两类记录都必须保留 reason code 和 provenance，不能通过删除失败记录让数据表面全部合格。Verdict 必须从规则
重新计算，禁止人工覆盖为 eligible。

## 资格不等于执行授权

`eligible_for_future_training` 只是未来记录可能进入训练集合的必要资格，不授权生成数据、建立 split 或启动训练。
R3 不进入训练或 normalization statistics。
