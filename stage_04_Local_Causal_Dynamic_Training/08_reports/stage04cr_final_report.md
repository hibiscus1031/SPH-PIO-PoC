# Stage 04C-R Final Report

## Final attribution

`TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`

Stage 04C's `TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED` verdict, all 864 historical failures, and Stage 04D authorization=false are preserved. The immutable Stage 04C-R contract `sha256:e05a5e7b8738bf152c7d05b0ac14aa996fc887cc09e93b48d40bbb0defbc3ef0` preceded 24 newly decoded TRAIN trajectory containers. No validation or sealed formula/state/source/target/origin payload was decoded.

The complete 864-row historical matrix was rebuilt. Two deterministic full-gradient passes produced 864 group rows with no parameter mutation. Exact residual/Jacobian factorization passed 2592/2592: maximum absolute reconstruction error 5.493e-25. Hidden, coefficient, pair-force and acceleration JVPs are nonzero; saturation and dead-head hypotheses fail. RK2 attenuation follows the expected V≈dt·A and X≈0.5dt²·A relations. D0 residuals are not uniformly below 1e−8, so the task is not already resolved. The diagnostic linear probe produces 414 stable nonzero velocity components and confirms a functioning state-Jacobian route.

Attribution is heterogeneous: residual-too-small 1316/2592, direction-projection dilution 672/2592, unresolved 604/2592. Projection dilution has theoretically consistent median scaled projection 0.655 but explains only 25.9%; common residual/Jacobian scale reasons explain only 50.8%. Neither reaches the preregistered 80% unique-route threshold, and the split differs strongly among x, v and rho. Therefore the only permitted primary state is mixed/unresolved, with no authorized next branch.

Stage 04C input-gradient evidence was read only and not requalified. New optimizer instances=0, optimizer steps=0, parameter updates=0, training runs=0, performance evaluations=0. CPU float64 and explicit D3 `SDPBackend.MATH` were used. Resource and access gates passed. Historical Stage 01–04C artifacts and hashes remain unchanged.
