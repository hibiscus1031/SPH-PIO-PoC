# Stage 01F source-injection audit

接口只接受 `(solution, stage, numerical_positions, physical_stage_time, parameters)`，未连接动态求解器。未来每个 RK2 力评估必须在 start 与 midpoint 分别重算。

机器审计：`{'included_in_internal_pair_force': False, 'separate_position_objects': True, 'source_values_differ': True, 'stage_count': 2, 'stages': ['start', 'midpoint'], 'times': [0.03, 0.030125], 'uses_analytic_positions': False, 'uses_numerical_residual_feedback': False}`。

禁止复用 step-start source、使用 analytic particle position、用 numerical SPH residual 修正 source、混入 pressure/viscosity pair antisymmetry，或把 external force 纳入 internal-force-zero gate。外力动量平衡单独比较质量加权 source。
