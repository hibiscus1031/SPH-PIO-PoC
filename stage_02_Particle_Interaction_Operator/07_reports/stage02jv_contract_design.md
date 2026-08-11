# Stage 02J-V Contract Design

Exactly one v0.4 candidate was preregistered. It directly reused the frozen M/D edge set, distance normalization, RMS normalization, epsilon values, and 256 case-hashed PCG64 permutations. No metric sweep was performed.

The candidate froze:

- `p_any=min(1,2*min(p_mag,p_dir)) <= 0.01`;
- four hard negatives and sign-flip ablation semantics;
- 512-realization, one-sided 95% Clopper–Pearson calibration;
- component-applicable refinement;
- exact invariance of `M_h`, `D_h`, `p_mag`, `p_dir`, and `p_any`.

Gate results: decomposition reuse PASS, positive controls PASS, hard-negative calibration PASS, development targets PASS, invariance FAIL. Consequently `regularity_contract_v0_4.yaml` was not generated and its final hash is **NOT GENERATED**. No factor, threshold, or tolerance was changed.
