# Stage 01E — Support-path analysis

| support_family | layout | endpoint_improvement | global_fitted_positive_slope | global_slope | pairwise_monotonicity | asymptotic_convergence | N16_error | N64_error |
|---|---|---|---|---|---|---|---|---|
| constant_neighbor | regular | True | True | 4.308153686037942e-05 | True | True | 1.5709017499210132 | 1.5707973860173388 |
| constant_neighbor | jitter_05 | False | False | -1.014354744431719 | False | False | 15.474072296187408 | 63.05803286880127 |
| constant_neighbor | jitter_10 | False | False | -1.0172891210846653 | False | False | 30.775504041948665 | 125.9401791054421 |
| increasing_neighbor | regular | True | True | 4.381679080049331e-05 | True | True | 1.5709017499210132 | 1.5707988434666655 |
| increasing_neighbor | jitter_05 | False | False | -0.14481071868758078 | False | False | 15.474072296187408 | 18.832991568175366 |
| increasing_neighbor | jitter_10 | False | False | -0.1467200086176638 | False | False | 30.775504041948665 | 37.56042506837107 |

Fixed H/dx family 可用 dx 作单一描述参数；increasing family 同时改变 H 与 dx/H，global slope 不称为标准空间阶。两项描述拟合结果：`{'status': 'two-term asymptotic fit not identifiable', 'C_H': 1.5117453653065651, 'C_Q': 2.2529993456950694, 'p': 0.23952217385129476, 'q': 1.1995788082760125e-05, 'jacobian_rank': 4, 'relative_residual_rms': 0.8679616782454468, 'bootstrap_success_fraction': 0.89, 'reason': 'bootstrap rank or positivity instability'}`。最终表述：**two-term asymptotic fit not identifiable**。Stage 01D2 的非单调性与 truncation–quadrature competition 是否一致，只作为机制相容性判断，不作为已证明的渐近阶。
