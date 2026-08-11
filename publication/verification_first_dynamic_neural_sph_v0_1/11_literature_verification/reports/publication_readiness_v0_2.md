# Publication readiness v0.2

## Classification

`B. VERIFICATION_METHODS_CMAME_POTENTIAL_BUT_INCOMPLETE`

## Supporting evidence

- P1 freeze PASS；历史hash无冲突。
- raw=454，verified=87，core=40；核心题录无冲突。
- 直接竞争与方法比较、novelty matrix、citation map和逐句external claim audit已建立。
- 项目正负证据完整保留：288/288、540/540、216/360、144 failures、TE1、NOT_QUALIFIED、no training/performance。

## Literature gap

在verified集合内，未发现zero fallback、RK2/history事务、多步stable-window及SPH cutoff event联合资格的同构报告；JAX-SPH构成多步AD/FD的直接部分先例。

## Fatal weaknesses for a full solver paper

- Stage 03D NOT_QUALIFIED。
- training/rollout/performance均未执行。
- 缺D-R4或等价独立验证。
- 单一实现，缺跨代码一般性。

## Required additions

训练资格、自主rollout、精度–成本与长期稳定性、跨问题/实现复现、独立validation。

## Overclaim risks

不得将可微代码写成已资格AD/FD；不得将hard linear momentum写成角动量/能量守恒；不得将未报告写成未曾发生；不得暗示现有文献的性能增益可迁移到本项目。
