# Stage 03D-S — Recommended manuscript framework

## Working title

Verification-first development of a conservative dynamic neural-SPH solver: zero-correction equivalence, topology events, and limits of multistep gradient qualification

## Recommended argument

The paper should not begin from “Transformer improves SPH.” It should present a verification-first route in which conservative architecture, zero-correction identity, RK2/history/graph semantics and topology events can be positively qualified, while complete multistep gradient qualification remains falsified under the frozen contract.

## Main-text sequence

1. Problem and verification-first hypothesis.
2. Conservative dynamic neural-SPH formulation and D0-D3 controls.
3. Dynamic reference hierarchy and qualified trajectories.
4. Independent implementation verification and bitwise zero correction.
5. Structural conservation/equivariance, checkpoint and one-step AD.
6. Complete 360-probe multistep AD/FD results, including all failures.
7. TE1 topology-event qualification as an independent component.
8. D-R attribution: backend sensitivity, FD conditioning, history attenuation and unresolved cases.
9. Claim boundary, limitations and future hypotheses.

## Publication boundary

Paper A is not ready. Paper B is the strongest current framing but remains incomplete for a high-impact full computational-method claim. Paper C can become valuable if the diagnostic methodology is shown to generalize beyond this single PoC. Stage 03D NOT_QUALIFIED must remain visible in the abstract, results and discussion.
