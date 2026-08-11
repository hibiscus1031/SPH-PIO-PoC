# D-R2 semidiscrete reference contract

The D-R2 state is unwrapped position, velocity, and independent density. Every RHS call wraps positions only for graph/field evaluation, rebuilds the frozen reciprocal graph, applies

`drho_i/dt=sum_j m_j (v_i-v_j)·grad_i W_ij`,

the frozen conservative pressure force with `p_i=cs^2(rho_i-rho0)`, the frozen conservative viscosity force, and the exact D-R1 MMS external acceleration evaluated at the persistent material label and physical time. Masses and supports are fixed. No learned term exists.

Primary DOP853 uses `rtol=1e-11, atol=1e-13`; sensitivity uses `rtol=1e-12, atol=1e-14`; both limit maximum step to one output interval and evaluate the same 17 times. Normalized L2/Linf position, velocity, density and pressure differences must be `<=1e-9/1e-8`. Output graph reciprocity and primary/sensitivity event sequence must agree. DOP853-versus-D-R1 exact difference is spatial/model-form diagnostic only.
