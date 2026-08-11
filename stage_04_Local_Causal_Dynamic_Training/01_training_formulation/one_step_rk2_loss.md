# One-step RK2 accepted-state loss

For a K=1 transition, compare the predicted accepted state

`S_theta^(n+1) = (x_theta, v_theta, rho_theta)`

with the reference accepted state

`S_ref^(n+1) = (x_ref, v_ref, rho_ref)`.

The frozen basic form is

`L_state = L_x + L_v + L_rho`.

The exact numerical component-weight convention, including whether each component carries an explicit preregistered multiplier, must be fixed in Stage 04D and may not be adjusted after observing formal results. Any multiplier is part of that component's prospective definition and does not add a new loss term.

## Components

`L_x = mean_nodes(||minimum_image(x_theta - x_ref)||^2) / L^2`,

`L_v = mean_nodes(||v_theta - v_ref||^2) / cs^2`,

`L_rho = mean_nodes((rho_theta - rho_ref)^2) / rho0^2`.

Here `L` is the prospectively declared periodic domain length scale, `cs` is the declared sound-speed scale, and `rho0` is the declared reference density. Their values and provenance must be fixed before training. No quantity may be inferred from validation or sealed-test targets.

## Aggregation

The training objective is a family-balanced, trajectory-origin-balanced, node-mean loss. Node errors are averaged within an origin; origins are balanced within a trajectory/family unit; family contributions are balanced so that larger particle counts, longer trajectories, or families with more available origins do not silently dominate. The exact sampler and aggregation formula must be preregistered in Stage 04D and shared by D1/D2/D3.

## Prohibitions

The objective contains no direct `delta_a` target, direct pair-force target, conservation penalty, or antisymmetry penalty. Conservation and antisymmetry are architectural/verification properties rather than auxiliary labels. It contains no test-derived scale, validation-derived weight, or D-R3-derived threshold. Component weights and normalization cannot be tuned after outcomes are known.
