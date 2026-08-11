# Stage 04C-R Coefficient and Acceleration Sensitivity

| Arm | Hidden JVP RMS | Alpha JVP RMS | Pair-force JVP RMS | Correction-acceleration JVP RMS | Max saturation fraction |
|---|---|---|---|---|---|
| D1 | 1.724e-02 | 6.388e-04 | 5.647e-03 | 6.630e-04 | 0.000 |
| D2 | 1.879e-02 | 2.502e-04 | 2.211e-03 | 2.576e-04 | 0.000 |
| D3 | 7.269e-02 | 5.257e-04 | 4.647e-03 | 7.630e-04 | 0.000 |

Hidden, alpha/beta, pair-force and nodal correction-acceleration sensitivities are clearly nonzero and finite. Final-head weights are nonzero; coefficient tanh saturation is 0%; no arm has zero correction output/JVP or hidden collapse. D3's exact-zero fraction comes from standard zero-initialized normalization biases, not a dead head. `NETWORK_PARAMETERIZATION_DEAD_SENSITIVITY` is rejected.
