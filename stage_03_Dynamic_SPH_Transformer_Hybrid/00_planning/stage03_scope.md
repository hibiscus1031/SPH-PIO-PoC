# Stage 03 scope

## Scientific scope

Stage 03 investigates a dynamic hybrid WCSPH solver in which a causal local temporal model supplies an additive momentum-acceleration correction through hard-antisymmetric reciprocal pair forces. It is distinct from Stage 02 static protocol v0.3, continuation of failed static fitting, direct K2 checkpoint embedding, or retrospective repair of Stage 01.

Stage 03A is specification-only. Authorized outputs are contracts, evidence hashes, reports, and manifests. Prohibited outputs are executable dynamic-model code, trajectory payloads, learned weights, optimizer state, training logs, numerical rollout results, solver-in-the-loop evidence, and speed/accuracy claims.

## Frozen boundaries

- Two-dimensional PoC; baseline is frozen WCSPH with linear EOS and explicit midpoint/RK2.
- The learned term corrects momentum acceleration only; all other state evolution remains baseline-controlled.
- History length is four accepted physical instants. Midpoint evaluations are ephemeral.
- D0/D1/D2/D3 arms are comparison roles, not implemented artifacts.
- Stage 03B may qualify dynamic references only after Stage 03A closes.
- Stages 03B, 03C, 03D, and 03E cannot be skipped before training preregistration.

## Non-claims

No statement in Stage 03A establishes learnability, improved accuracy, restored convergence, physical validation, stability, computational utility, or superiority of D3 over D0–D2.
