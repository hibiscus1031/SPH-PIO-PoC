# Precision contract

The formal qualification environment is CPU float64. Model parameters, differentiable state tensors, loss accumulation, JVP/VJP directions, and central finite-difference perturbations must use float64 unless a later contract identifies a nondifferentiable integer/boolean field. Accidental casts to float32 invalidate formal hard evidence.

Normalization scales `L`, `cs`, and `rho0` must be represented consistently in float64 and be prospectively sourced without test or D-R3 information. Central finite-difference perturbed parameter states must be generated from the same unrounded float64 base parameter vector.

MPS float32 is permitted only for resource feasibility or smoke diagnostics. MPS results cannot qualify gradients, choose a training protocol, establish training success, form a sealed-test conclusion, or support a D1/D2/D3 performance comparison. Any such artifact must carry `evidence_role=diagnostic_only` and be excluded from hard-gate aggregation.

Stage 04A performs no precision experiment. This contract defines the environment for later qualification.
