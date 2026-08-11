# Apple M2 resource scope

Stage 03 PoC on Apple M2/16 GB is limited to 2D, CPU float64 verification, optional MPS float32 smoke only, `N<=1024`, history `H=4`, rollout `K<=8`, local edge operations, truncated BPTT, and single-family or small-family preflight.

Dense `N x N` attention is forbidden. MPS smoke cannot replace float64 verification or establish scientific thresholds. This device does not authorize large-scale long-rollout training, production 3D training, broad hyperparameter searches, or a complete CMAME experiment matrix.

Resource exhaustion is recorded as evidence, not solved by silently shrinking successful cases after inspection. Stage 03A performs no compute experiment.
