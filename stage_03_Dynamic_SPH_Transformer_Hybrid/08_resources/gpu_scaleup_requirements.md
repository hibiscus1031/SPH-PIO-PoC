# GPU scale-up requirements

A complete two-dimensional research campaign should use an NVIDIA GPU with at least 24 GB memory. Long rollout or 3D work should use at least 48 GB or a preregistered multi-GPU configuration. Exact device, CUDA/library versions, precision, deterministic settings, memory limit, and throughput measurement protocol must be frozen per execution stage.

Scale-up does not relax the local-edge, causal, antisymmetric, split/seal, or V&V contracts. Mixed precision requires separate conservation, zero-equivalence, AD/FD, and stability qualification and cannot replace CPU float64 reference verification.

Hardware changes are provenance-relevant and must not be confounded with arm comparisons. Equal-budget comparisons use the same hardware class and accounting policy; equal-error utility additionally reports memory and reference uncertainty.
