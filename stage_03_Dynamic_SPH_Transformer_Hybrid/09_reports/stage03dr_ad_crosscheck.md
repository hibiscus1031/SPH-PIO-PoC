# Stage 03D-R AD Crosscheck

Stage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`. Stage 03D-R contract: `sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9`.

With both routes on `SDPBackend.MATH`, reverse VJP versus forward JVP passes 60/60 selected cells at the frozen gate. No FD was used internally by either AD route. The Stage 03D historical default-backend reverse agrees in 48/60 cells; all 12 backend-sensitive cells are D3 `historical_token`, `initial_density`, or `initial_velocity` rows. CPU flash SDPA has no forward-AD implementation, so this historical comparison is retained as a separate backend-sensitivity diagnostic rather than presented as a formal reverse/JVP contradiction.
