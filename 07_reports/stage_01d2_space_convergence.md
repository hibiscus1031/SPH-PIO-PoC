# Stage 01D2 space convergence

| run_id | resolution | support_ratio | velocity_relative_l2 | modal_error | kinetic_energy_error | status |
|---|---|---|---|---|---|---|
| stage01d2_s_n16_inc | 16 | 4.0 | 0.01865615480046095 | 0.002550509801116485 | 0.0059537335716813855 | PASS |
| stage01d2_s_n24_inc | 24 | 4.5 | 0.004906640448520584 | 0.0016072477529518459 | 0.003284279398274692 | PASS |
| stage01d2_t_n32_dt1p25e4 | 32 | 5.0 | 0.01498544527448892 | 0.0011821416163716458 | 0.0025234233918977056 | PASS |

门判定：S1=PASS, S2=PASS, S3=PASS, S4=PASS, S5=PASS, S6=PASS。velocity 与 modal 的三点拟合斜率分别为 `0.511542` 和 `1.11132`。主 velocity 序列非单调，条件 N48 因此实际运行并 PASS：velocity L2=`0.019456041`、modal error=`0.00079542288`、peak RSS=`515063808` bytes、wall=`293.828` s；N48 未消除非单调性。**GCI not justified**；仅当正、有限、单调并近似进入渐近区时才允许 Richardson/GCI。
