# Teacher-forcing boundary

## Permitted K=1 inputs

For each origin, the three strictly earlier accepted reference states and current accepted reference state are supplied as the fixed `H=4` causal input. Starting the transition from `S_ref^n` is permitted supervised initialization, not a midpoint correction. The target `S_ref^(n+1)` is accessed only by the loss evaluator after `S_theta^(n+1)` has been produced.

## Forbidden within-step injection

The reference midpoint state, reference midpoint graph, reference midpoint token, reference midpoint force, and any target-derived correction are forbidden model inputs. The RK2 midpoint must be produced from the model/solver start evaluation. Its graph must be rebuilt from that predicted midpoint state, and its token is ephemeral and not committed.

No teacher forcing occurs between RK2 start and midpoint or between midpoint and accepted state. Consequently, the one-step computational map being differentiated is the same complete start → midpoint → accepted map used to generate the prediction.

## Future K=2 boundary

Stage 04A does not decide whether a future K=2 campaign uses an accepted reference state or the model-predicted accepted state at its inter-step boundary. Stage 04F must define and qualify that choice before K=2 execution. It may not silently mix teacher-forced and autonomous transitions in one formal result.

## Leakage rule

Neither targets nor target-derived statistics may enter token construction, graph construction, normalization, checkpoint selection, or threshold selection. D-R3 is excluded from all these roles and remains independent validation only.
