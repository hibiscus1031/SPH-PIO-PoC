# Correction scope

The learned operator may modify momentum acceleration only, additively. It may not predict, replace, or directly update density, pressure, EOS, continuity, position, smoothing length, time step, RK2 coefficients, neighbor topology, particle mass, or boundary rules.

`a_SPH` is not a model input. It remains a separately evaluated baseline term and may only appear in audits or diagnostic decompositions. Reference acceleration, `delta_a`, target-derived features, and future states are forbidden.

The following workarounds are prohibited: node-wise correction heads, directed-softmax force generation, conservation penalties in place of antisymmetry, post-rollout mean subtraction, and conservation projection. Energy, torque, and power are diagnostic unless a later separately preregistered contract upgrades them. Pressure may be reported as EOS-derived but is not an independent loss state.
