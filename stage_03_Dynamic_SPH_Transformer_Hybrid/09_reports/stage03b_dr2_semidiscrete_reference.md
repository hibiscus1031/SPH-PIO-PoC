# Stage 03B D-R2 same-semidscrete DOP853 reference

六个 D-R1/N case 均以冻结 WCSPH continuity、pressure、viscosity、EOS 和 label/time exact MMS source 积分。Primary 为 `rtol=1e-11, atol=1e-13`，sensitivity 为 `rtol=1e-12, atol=1e-14`，max step 为一个输出间隔。每条 primary 另做一次完全相同的 repeat。

| Family | N | nfev per path | max primary/sensitivity normalized Linf | repeat | graph/event | Verdict |
|---|---:|---:|---:|---|---|---|
| Compression | 8 | 239 | 0 | bitwise | identical/reciprocal | PASS |
| Compression | 12 | 239 | 0 | bitwise | identical/reciprocal | PASS |
| Compression | 16 | 239 | 0 | bitwise | identical/reciprocal | PASS |
| Coupled | 8 | 239 | 0 | bitwise | identical/reciprocal | PASS |
| Coupled | 12 | 239 | 0 | bitwise | identical/reciprocal | PASS |
| Coupled | 16 | 239 | 0 | bitwise | identical/reciprocal | PASS |

两种 tolerance 在冻结 max-step 下产生相同 float64 输出，但二者仍分别执行并记录；全部 L2/Linf 门因此通过。三路径合计 4302 RHS calls 和 4302 次 graph rebuild。

DOP853 与 exact D-R1 的差异只作 `semidiscrete_spatial_model_form_diagnostic_only`：velocity normalized L2 从 4.80e-6 到 4.17e-5，全部 field 中最大 normalized Linf 为 4.30e-4。该差异没有进入 D-R2 时间门，也没有被称为 spatial 或 continuum truth。
