# Stage 05A Defect Formulation Report

For the same accepted origin and physical/numerical metadata, a full D0 RK2 step produces `S_0^(n+1)` and a full hybrid RK2 step produces `S_theta^(n+1)`. The unique reference and model velocity impulses are respectively `v_ref^(n+1)-v_0^(n+1)` and `v_theta^(n+1)-v_0^(n+1)`; division by the same `dt` defines `a_def^star` and `a_eff^theta`.

Because the learned reciprocal pair force has zero mass-weighted total force, the target is prospectively decomposed as

```text
a_cm^star = sum_i(m_i a_def,i^star) / sum_i m_i
a_cons,i^star = a_def,i^star - a_cm^star
a_incompatible,i^star = a_cm^star.
```

Only `a_cons^star` is trainable under the first contract. Stage 05B must quantify total, conservative, and incompatible norms, incompatible energy fraction, family/origin distributions, and uncertainty relation, then enforce a preregistered coverage gate. The formulation is an accepted-state discrete correction requirement, not continuum, pair-force, static Stage 02, or high-resolution truth.
