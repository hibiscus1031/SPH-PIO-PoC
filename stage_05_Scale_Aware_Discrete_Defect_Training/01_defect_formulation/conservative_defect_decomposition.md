# Conservative Defect Decomposition

For node masses `m_i > 0`, freeze the mass-weighted center component

```text
M             = sum_i m_i
a_cm^star     = (sum_i m_i a_def,i^star) / M
a_cons,i^star = a_def,i^star - a_cm^star
a_incompatible,i^star = a_cm^star.
```

Therefore `sum_i m_i a_cons,i^star = 0`. This is the unique prospectively frozen representability decomposition; it is not an after-the-fact mean subtraction.

Stage 05B must report, per family and origin and in aggregate, the mass-weighted total-defect norm, conservative-defect norm, incompatible-defect norm, incompatible energy fraction, their distributions, and their relation to uncertainty. The energy fraction is uniquely defined as

```text
f_incompatible = ||a_incompatible^star||_m^2 / ||a_def^star||_m^2,
||a||_m^2 = sum_i m_i ||a_i||_2^2,
```

with zero-denominator handling preregistered in Stage 05B before decode. Initial training may fit only `a_cons^star`.
