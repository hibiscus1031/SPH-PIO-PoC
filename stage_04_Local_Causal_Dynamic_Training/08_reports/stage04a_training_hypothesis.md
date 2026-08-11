# Stage 04A — Training hypothesis report

Stage 04 opens a distinct route: conservative dynamic neural-SPH models may obtain qualifiable training signals from task-aligned one-step or short-window RK2 state-transition supervision without depending on a fully qualified K=8 reverse-mode chain.

The route is motivated by a strict evidence boundary, not by reinterpretation. Stage 03C verified the dynamic RK2 hybrid implementation, but Stage 03D did not qualify multistep AD/FD and topology as a combined route, and Stage 03D-R left the gradient failure mixed or unresolved. Stage 04 therefore does not reuse the long-chain training premise, change a backend to overwrite history, or declare the failed gradients repaired. It defines a new optimizer-variable-aligned question.

The initial formal task is uniquely K=1 with H=4 accepted reference states. Starting from the current reference state, the solver performs a complete RK2 start → predicted midpoint → accepted transition, rebuilds the midpoint graph, uses an ephemeral noncommitted midpoint token, and produces `S_theta^(n+1)`. No reference midpoint is injected. The target is the next accepted reference state.

D1 is an instantaneous conservative pair MLP baseline; D2 is a causal GRU pair PIO; D3 is a causal temporal reciprocal Transformer PIO. Every arm is freshly initialized and shares legal information, the reciprocal antisymmetric pair head, lineage split, loss, budget, and checkpoint rule. D3 is not presumed superior.

This report contains no optimizer, training, rollout, or performance result. The hypothesis remains prospective.
