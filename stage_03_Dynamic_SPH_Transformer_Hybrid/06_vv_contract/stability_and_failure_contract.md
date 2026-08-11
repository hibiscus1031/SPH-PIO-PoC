# Stability and failure contract

Frozen failure codes are `DYN_NAN_INF`, `DYN_NEGATIVE_DENSITY`, `DYN_PARTICLE_CLUSTERING`, `DYN_VOID_FORMATION`, `DYN_GRAPH_DISCONNECTION`, `DYN_FORCE_EXPLOSION`, `DYN_HIDDEN_STATE_EXPLOSION`, `DYN_ROLLOUT_ERROR_DIVERGENCE`, `DYN_CONSERVATION_FAILURE`, `DYN_TOPOLOGY_NONDETERMINISM`, and `DYN_REFERENCE_UNCERTAINTY_DOMINANT`.

Stage 03F or the relevant execution preregistration must give every scale-dependent code a numerical detector before results. Every failure record retains first failure step/time/RK stage, state and graph hashes, model/checkpoint/normalization hashes, trajectory family/lineage, dt, resolution, support, arm, dtype/backend, preceding metrics, and detector values.

Failed trajectories cannot be deleted, truncated before the failure in summaries, relabeled as outliers after inspection, or excluded to improve results. Multiple simultaneous codes may be stored with one deterministic primary-code rule.
