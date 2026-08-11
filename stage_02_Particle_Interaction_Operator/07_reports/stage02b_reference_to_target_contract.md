# Stage 02B — Reference-to-Target Contract Report

规范合同见 `../03_dataset/target_definition/reference_to_target_contract.md`。

## 冻结定义

\[
\boxed{\Delta a=a_{ref}-a_{SPH}}
\]

机器可读符号固定为 `a_ref_minus_a_sph`。baseline 与 reference 必须在相同粒子状态、时刻、质量、EOS、
support、forcing 和 configuration 下评价；不同 trajectory 的近似状态不能直接形成同状态标签。

## Reference class 决策

| class | 用途 | 未来训练地位 |
|---|---|---|
| R1 continuum-compatible | analytic/MMS verification 和候选 discretization target | 只有 model-form、同状态、uncertainty 与归因门全部通过才可能 eligible |
| R2 semidiscrete-qualified | 隔离 time error/state drift | 本合同下 diagnostic，不直接作为主空间标签 |
| R3 independent benchmark | shear/acoustic 等独立 validation | 默认非训练数据 |
| RX model-form-misaligned | 模型形式错配诊断 | rejected |

R1 的 class 必须逐 configuration 证明；解析 reference 不自动意味着 WCSPH-compatible。R2/R3 的用途不因
数值误差较小而升级。RX 不得通过 uncertainty 调整进入训练。

## 目标归因

每条候选必须分列 space、time、reference、forcing、model-form 和 cross-term 状态。只有
`discretization_attributed` 可继续资格判断。禁止把全部 continuum–SPH difference 定义为离散误差。

## 独立验证隔离

R3 不进入未来训练、归一化统计、阈值选择或模型选择。Shear/acoustic 必须保留完整类别或在生成前冻结严格
未见参数范围；查看结果后不得改变隔离策略。
