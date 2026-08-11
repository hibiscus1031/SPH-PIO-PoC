# Stage 04 hypothesis register

## H04-1 — Local-causal dynamic training

**Hypothesis.** A conservative dynamic neural-SPH model may be trained through task-aligned one-step or short-window RK2 state-transition supervision without relying on a fully qualified long-chain `K=8` reverse-mode gradient.

**中文。** 守恒型动态 neural-SPH 模型可能通过任务相关的一步或短窗 RK2 状态转移监督获得可资格化训练信号，而不依赖完整八步长链反向传播。

**Current epistemic status.** Prospective and untested. Stage 04A defines how later stages may test it; Stage 04A does not establish trainability.

**Initial formal horizon.** `K=1` only. `K=2` is conditional on successful K=1 qualification, formal training, and sealed evaluation. `K=4` and `K=8` are excluded from the first training backpropagation horizon.

**Primary falsification route.** H04-1 is not supported if Stage 04C cannot qualify task-aligned parameter gradients under the fixed formal environment, or if later preregistered training/transfer gates fail. A qualified local gradient alone is insufficient to support solver usefulness.

**Required evidence chain.** New reference families and lineage qualification (04B) precede parameter-gradient qualification (04C), which precedes protocol preregistration and sealed-test preflight (04D), which alone may authorize K=1 formal training (04E). K=2/autonomous rollout (04F) and independent validation/refinement/utility assessment (04G) remain separate.

## Preserved negative and component evidence

- Stage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`.
- Stage 03D-R remains `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED` and does not repair or supersede Stage 03D.
- The topology event component remains `TOPOLOGY_EVENT_COMPONENT_QUALIFIED`; this component result does not qualify long-chain training.
- Stage 03E authorization remains `false`.

## Claim boundary

Possible future support for H04-1 would show only that a specifically preregistered local-causal training route is feasible under its qualified environment. It would not automatically prove long-horizon differentiability, autonomous stability, independent-family transfer, refinement behavior, or full solver validity.
