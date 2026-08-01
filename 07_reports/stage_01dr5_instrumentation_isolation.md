# Stage 01D-R5 Instrumentation Isolation

| run | mode | components | max retired | same-slot | RSS slope | current tensor Δ | external tensor Δ | finite |
|---|---|---|---|---|---|---|---|---|
| stage01dr5_i0_r1 | I0 | [] | -1 | -1 | 7.44e+04 | 0 | 36028416 | True |
| stage01dr5_i1_r1 | I1 | ["weakref_tracker"] | 103 | 13 | 1.26e+05 | 0 | 0 | True |
| stage01dr5_i2_r1 | I2 | ["semantic_ledger"] | -1 | -1 | 4.898e+04 | 0 | 0 | True |
| stage01dr5_i3_r1 | I3 | ["observer_callback"] | -1 | -1 | 9.436e+04 | 0 | 0 | True |
| stage01dr5_i4_r1 | I4 | ["observer_callback","semantic_ledger","weakref_tracker"] | 63 | 13 | 8.413e+04 | 0 | 0 | True |
| stage01dr5_i0_r2 | I0 | [] | -1 | -1 | 1.118e+05 | 0 | 33259520 | True |
| stage01dr5_i1_r2 | I1 | ["weakref_tracker"] | 95 | 13 | 9.905e+04 | 0 | 0 | True |
| stage01dr5_i2_r2 | I2 | ["semantic_ledger"] | -1 | -1 | 3.751e+04 | 0 | 0 | True |
| stage01dr5_i3_r2 | I3 | ["observer_callback"] | -1 | -1 | 1.013e+05 | 0 | 0 | True |
| stage01dr5_i4_r2 | I4 | ["observer_callback","semantic_ledger","weakref_tracker"] | 55 | 13 | 1.009e+05 | 0 | 0 | True |
| stage01dr5_i0_r3 | I0 | [] | -1 | -1 | 8.306e+04 | 0 | 36028416 | True |
| stage01dr5_i1_r3 | I1 | ["weakref_tracker"] | 85 | 13 | 1.037e+05 | 0 | 0 | True |
| stage01dr5_i2_r3 | I2 | ["semantic_ledger"] | -1 | -1 | 6.79e+04 | 0 | 0 | True |
| stage01dr5_i3_r3 | I3 | ["observer_callback"] | -1 | -1 | 1.5e+05 | 0 | 0 | True |
| stage01dr5_i4_r3 | I4 | ["observer_callback","semantic_ledger","weakref_tracker"] | 58 | 13 | 9.815e+04 | 0 | 0 | True |

I0 不注册 solver Tensor，只在固定 checkpoint 读取外部 GC 类型计数；I1–I4 分别打开
预登记组件。instrumentation isolated=`False`。
