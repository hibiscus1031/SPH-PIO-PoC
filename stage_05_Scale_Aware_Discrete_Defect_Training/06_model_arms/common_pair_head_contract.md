# Common Reciprocal Pair-Head Contract

All arms terminate in the same head. For each unordered interacting pair `{i,j}`, a shared pair representation produces one reciprocal pair force satisfying

```text
F_ji^theta = -F_ij^theta.
```

Node accelerations are assembled as `a_i^theta = (1/m_i) sum_j F_ij^theta`, giving exact global cancellation `sum_i m_i a_i^theta = 0` up to the implementation's prescribed deterministic arithmetic semantics. Edge ordering, reciprocal construction, graph convention, support, EOS, and full RK2 coupling are common across arms.

Because conservation and antisymmetry are architectural invariants, no corresponding penalty is allowed in `L_def`. Stage 05C/D must audit the invariant but may not modify the head by arm.
