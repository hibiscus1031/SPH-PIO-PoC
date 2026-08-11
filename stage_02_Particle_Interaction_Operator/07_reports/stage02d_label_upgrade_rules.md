# Stage 02D — Label Upgrade Rules

机器规则见 `../04_target_attribution/qualification/label_upgrade_rules.yaml`。

## 1. Required gates

从 `diagnostic` 升级为 `eligible_for_future_training` 必须同时满足：

1. reference class valid；
2. same-state PASS；
3. uncertainty PASS；
4. model-form compatible；
5. topology PASS；
6. resource PASS；
7. determinism PASS；
8. discretization attribution PASS；
9. leakage PASS。

Verdict 只能由版本化规则计算，`manual_override_permitted=false`。

## 2. Reference policy

- R1：只有独立 WCSPH model-form alignment PASS 后才是条件性候选；
- R2：当前训练升级权限为 false；若未来改变用途，必须有新版本 reference-to-target contract、明确训练权限、
  discretization attribution PASS 和独立 validation 保留；
- R3：validation only；
- RX：rejected。

因此满足同状态、uncertainty、resource 等执行门仍不足以自动升级 R2。

## 3. Discretization attribution score

Score 是六分量 categorical evidence vector，不是可调数值总分：spatial consistency、resolution trend、support
consistency、time contamination、reference sensitivity、model-form compatibility。六项全部 PASS 才能使
attribution gate PASS；没有自动选择阈值。

当前4个正控制每条只有 reference sensitivity 一项达到 audit PASS；spatial、time、model-form 仍 diagnostic，
resolution 与 support 未测试。2个负控制 topology FAIL，保持 rejected。

## 4. Failure retention

Unresolved、rejected 和 topology failure 必须保留 reason codes 与 provenance。禁止删除、覆盖或重新分类失败
记录来改善资格计数。

## 5. Stage 02E gate

当前 `stage02e_data_qualification_upgrade_authorized=false`。未来至少需要训练允许的 reference 路径、无混杂
multi-resolution、multi-support、预冻结 temporal decision rule 和相应 WCSPH model-form evidence。
