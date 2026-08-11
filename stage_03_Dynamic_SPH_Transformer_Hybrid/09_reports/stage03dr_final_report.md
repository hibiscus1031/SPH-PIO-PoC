# Stage 03D-R Final Report

Stage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`. Stage 03D-R contract: `sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9`.

Final status: **DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED**.

1. Stage 03D failure is preserved and not overwritten.
2. Complete failure matrix: 360 rows, 216 historical stable windows, 144 failures.
3. Failure axes are fully reported by arm, horizon, probe, case/source role, seed and magnitude decade.
4. AD derivative magnitudes and near-zero rows remain explicit.
5. Reverse AD versus JVP on the common math-attention backend: 60/60; the Stage 03D historical default-backend reverse matches 48/60, with 12 D3 input/history rows retained as backend-sensitivity diagnostics.
6. Extended FD: 30/60 selected rows form an attribution stable region.
7. Three-point, five-point and Richardson results are retained for all 2640 paths.
8. Original objective is decomposed into x/v/rho without replacement.
9. Cancellation ratios are retained per selected row.
10. Horizon scaling labels: `{"BOUNDED_OR_NONMONOTONE": 90}`.
11. REFERENCE_PREHISTORY traces: `{"HISTORY_FD_CONDITIONING_LIMITED": 1, "HISTORY_SENSITIVITY_BELOW_FD_RESOLUTION": 5}`; all temporal-module-only paths are stable, but rollout attenuation leaves only one full-rollout extended window.
12. Temporal-module-only reverse/JVP/FD is separated from rollout attenuation.
13. AD/FD perturb-object identity is explicit; no silent loader/history modification occurred.
14. Harness paths start independently, use fixed RNG, correct parameter indices, fresh history and unchanged base parameter hashes.
15. Topology component: `TOPOLOGY_EVENT_COMPONENT_QUALIFIED`; Stage 03D overall remains NOT_QUALIFIED.
16. Unique failure attribution: `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`.
17. Next authorized branch: NONE — no immediate contract modification or training; Stage 03E remains false.
18. new optimizer steps = 0.
19. new training runs = 0.
20. No rollout-performance evaluation, dataset, split, normalization or training was performed.
21. Historical integrity: 45 frozen artifacts checked, 0 mismatches. Peak RSS delta=439599104 bytes; resource gate=True.
