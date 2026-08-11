# Hidden-state contract

Canonical hidden state is `H^n={q_i^n}`, field name `temporal_hidden`; smoothing length is `ell_i`, field name `smoothing_length`. This resolves the source notation collision and makes serialization unique.

The committed history after accepted step `n` consists only of accepted causal tokens/states for physical instants through `n`. It is aligned by persistent particle identity but particle identity is never embedded or supplied to the model. History length is four; excess oldest entries are evicted deterministically.

Initial rollout history may use the preceding three reference states as a declared warm start. These states must precede the rollout origin, share its lineage, and be tagged `warm_start_reference`; they are not loss targets within the autonomous segment. Once the origin is accepted, every new token derives from the model-evolved state.

Checkpoint state must include model parameters, committed history cache, accepted particle state, RNG/determinism state where applicable, graph reconstruction configuration, and exact accepted step/time. Provisional midpoint token/hidden state is never checkpointed as committed history. Hidden norms and non-finite values are monitored; explosion is a named failure.
