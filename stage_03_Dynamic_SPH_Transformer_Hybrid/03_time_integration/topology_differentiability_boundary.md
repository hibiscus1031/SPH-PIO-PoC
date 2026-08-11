# Topology differentiability boundary

Neighbor indices, sorting, edge existence, and cutoff decisions are discrete variables. Forward execution rebuilds the graph at every RK2 stage, but differentiation treats the realized topology and edge ordering as fixed. Within that topology, derivatives may propagate through position-dependent continuous geometry/kernel values, velocity, density, hidden state, and network parameters.

The project must never claim that neighbor search is fully differentiable. Cutoff crossing is a piecewise-smooth event. Edge birth/death, reciprocal consistency, finite jump size, gradient boundedness on either side, and repeated-topology determinism are audited separately from fixed-topology AD/FD.

AD/FD discrepancies for perturbations that change topology are classified as topology-event evidence, not automatically as network-gradient failure. Each sample records base and perturbed graph hashes and whether the edge set changed. Stable-epsilon windows are established only on fixed-topology samples; one-sided event diagnostics may be reported separately.
