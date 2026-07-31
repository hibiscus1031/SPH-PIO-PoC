# Stage 01 multi-step gradient check

Date: 2026-07-31  
Result: **PASS for the tested initial-velocity amplitude parameter**

## Test definition

- Solver: official diffSPH `DeltaSPH`, commit
  `fff180c81d57a51035de9f4d358dbcaccf973928`
- Case: 2-D periodic Taylor–Green vortex, \(16\times16=256\) particles
- Backends: CPU and MPS; `PYTORCH_ENABLE_MPS_FALLBACK=0`
- Scalar parameter:
  \(\alpha=0.9\), the initial velocity amplitude, with
  `requires_grad=True`
- Rollout: 3 complete SPH steps, \(\Delta t=5\times10^{-4}\)
- Loss:
  \(L=\mathrm{mean}[(\mathbf v_\mathrm{final}-\mathbf
  v_\mathrm{target})^2]\), where the target amplitude is 1
- Independent check: centered finite difference with
  \(\epsilon=10^{-3}\)

Command:

```text
PYTHONPATH=01_solver PYTORCH_ENABLE_MPS_FALLBACK=0 \
python -m diffsph_adapter.gradient_check \
  --backend both --steps 3 --alpha 0.9 --epsilon 0.001
```

## Results

| Backend | Loss | Autograd gradient | Centered-FD gradient | Relative difference |
|---|---:|---:|---:|---:|
| CPU | 0.00261908164248 | -0.0489228777587 | -0.0488819787279 | 0.000835990 |
| MPS | 0.00261908210814 | -0.0489228889346 | -0.0488820951432 | 0.000833839 |

For both backends:

- `alpha.requires_grad` and `loss.requires_grad` were `True`;
- the final gradients were finite and non-zero;
- the velocity retained `requires_grad=True` after every step;
- each step reported `IndexPutBackward0` as the velocity `grad_fn`;
- all 85 audited tensors were on the requested device, with zero device
  mismatches;
- no `.item()` or NumPy conversion occurred in the differentiable loss/value
  path.

The CPU and MPS autograd gradients differ by approximately
\(2.28\times10^{-7}\) relative.  The finite-difference discrepancy is below
0.1% on both devices and has the same sign and magnitude as autograd.

## Scope limitation

`torchCompactRadius` chooses discrete neighbor indices outside the
differentiable value path.  On MPS it explicitly detaches positions, performs
compact neighbor search on CPU, and transfers indices back to MPS.  This does
not break the tested derivative with respect to initial velocity amplitude,
but this test does **not** establish differentiability of neighbor-topology
changes with respect to particle position.

## Evidence

- Machine-readable result:
  `06_experiments/stage_01_tgv/processed/gradient_check.json`
- Complete command output:
  `06_experiments/stage_01_tgv/logs/gradient_check.txt`
- Implementation:
  `01_solver/diffsph_adapter/gradient_check.py`
- Regression test:
  `tests/test_short_rollout_gradient.py`
