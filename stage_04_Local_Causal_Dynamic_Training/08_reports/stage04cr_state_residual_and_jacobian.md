# Stage 04C-R State Residual and Jacobian

| Arm | Component | Median residual RMS | Median state-JVP RMS | Median alignment |
|---|---|---|---|---|
| D1 | L_x | 9.593e-09 | 3.579e-11 | 0.789 |
| D1 | L_v | 4.890e-06 | 1.831e-08 | 0.772 |
| D1 | L_rho | 1.329e-06 | 1.220e-10 | 0.948 |
| D2 | L_x | 9.465e-09 | 1.342e-11 | 0.826 |
| D2 | L_v | 4.825e-06 | 7.115e-09 | 0.816 |
| D2 | L_rho | 1.330e-06 | 3.590e-11 | 0.956 |
| D3 | L_x | 9.952e-09 | 4.135e-11 | 0.876 |
| D3 | L_v | 5.072e-06 | 2.107e-08 | 0.887 |
| D3 | L_rho | 1.327e-06 | 1.204e-10 | 0.957 |

State Jacobians are finite and nonzero, while residual scale differs sharply by component. Alignment is high (typical 0.77–0.96), so residual/Jacobian orthogonality is not the dominant cause. Position residuals near 1e−8 make all position-loss gradients residual-limited; velocity state-JVPs are larger and expose projection dilution; density rows split between small residual and unresolved sub-threshold full-gradient scale.
