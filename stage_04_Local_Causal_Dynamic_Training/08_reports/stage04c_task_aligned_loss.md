# Stage 04C Task-Aligned Loss

The formal objective is the component vector `[L_x, L_v, L_rho]` from a complete K=1 explicit-midpoint RK2 transition. `L_x` uses periodic minimum-image position error normalized by L²; `L_v` uses velocity error normalized by cs²; `L_rho` uses density error normalized by rho0².

Every evaluation rebuilds the start, midpoint and accepted graphs. The midpoint token is ephemeral; reference midpoint state is never injected. D2/D3 prehistory contains only frames n−3 through n, and accepted history commits exactly once after acceptance with midpoint commit count zero. `L_sum` is reported only as a diagnostic and does not select Stage 04D training weights.
