# Baseline-Centered Transition

For a future TRAIN origin with accepted reference history `S_ref^(n-3:n)`, define the full D0 RK2 transition

```text
S_0^(n+1) = Phi_D0(S_ref^n; same external source, same graph convention, same EOS, same dt)
```

and the full hybrid RK2 transition

```text
S_theta^(n+1) = Phi_hybrid(S_ref^n, S_ref^(n-3:n), theta;
                          same external source, same graph convention,
                          same EOS, same dt).
```

Both transitions start from the same accepted `S_ref^n` and differ only by the learned conservative correction. The reference velocity defect and model correction are uniquely

```text
Delta_v_def^star   = v_ref^(n+1)   - v_0^(n+1)
Delta_v_eff^theta  = v_theta^(n+1) - v_0^(n+1).
```

These identities describe an accepted-state discrete correction requirement. They are frozen before target materialization and are not a continuum-acceleration or direct pair-force truth.
