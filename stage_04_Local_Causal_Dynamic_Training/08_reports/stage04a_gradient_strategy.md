# Stage 04A — Gradient strategy report

The Stage 04 gradient question is aligned with the future optimization task. Stage 04C must differentiate the accepted-state loss `L_state = L_x + L_v + L_rho` with prospectively registered component weights, rather than the Stage 03D generic random scalar projection of a final state.

Hard evidence covers only optimizer variables: D1 token encoder and coefficient head; D2 token encoder, GRU, and pair head; D3 token encoder, Q/K/V/O attention, feed-forward, and pair head. Initial velocity, initial density, and reference prehistory tokens are fixed K=1 inputs. Their gradients remain diagnostic only; this boundary does not assert that the corresponding historical failures were fixed.

Every hard parameter group must be checked using reverse VJP, forward JVP, and central FD at no fewer than three preregistered epsilons, with a stable-window rule and independent deterministic repeat. Thresholds, directions, epsilons, coverage, and failure aggregation are frozen before formal values are decoded.

The formal environment is CPU float64. D3 must explicitly use PyTorch `SDPBackend.MATH`; flash, memory-efficient, and automatic backend selection are disabled. Alternative backends and MPS float32 are diagnostic only. Backend identity must enter checkpoints, run manifests, and result hashes.

Stage 04A performs no derivative probe and makes no trainability claim.
