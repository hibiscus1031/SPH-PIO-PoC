# Dynamic loss contract

Future solver-in-the-loop training must include

`L_roll = sum_{k=1}^K w_k [lambda_v L_v,k + lambda_rho L_rho,k + lambda_x L_x,k]`,

where `L_v,k` is graph-balanced velocity error, `L_rho,k` graph-balanced density error, and `L_x,k` periodic minimum-image position error. Graph balancing must prevent high-degree particles/large edge counts from implicitly redefining family weights. Family-level aggregation precedes across-family aggregation.

Pressure is EOS-derived and may be reported but is not an independent state freedom. A one-step acceleration error may be a diagnostic, never a replacement for state rollout loss. Conservation and pair antisymmetry penalties are forbidden because those properties are architectural hard gates. Energy, torque, and power remain diagnostics.

Stage 03A intentionally does not choose numerical `lambda` or `w`. Stage 03F must preregister their values, scaling, horizon weighting, family weighting, and checkpoint metric before results. Post-result tuning is forbidden, and all arms use the same frozen loss/budget.
