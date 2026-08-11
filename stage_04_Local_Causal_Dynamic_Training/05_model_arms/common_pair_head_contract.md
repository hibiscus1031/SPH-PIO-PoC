# Common reciprocal antisymmetric pair-head contract

All three arms terminate in the same reciprocal antisymmetric pair-force head. For an unordered interacting pair `{i,j}`, the shared head constructs one pair coefficient/force contribution from symmetrically/reciprocally combined legal features and applies equal-and-opposite contributions so that the learned internal pair correction satisfies `f_ij = -f_ji` by construction.

The head interface, physical scaling convention, edge canonicalization, aggregation, cutoff/support treatment, and mapping from pair output to the RK2 acceleration correction must be identical across D1/D2/D3. Arm-specific temporal modules may change only the legal latent representation passed into the shared interface; they may not change conservation semantics or receive extra target fields.

No conservation or antisymmetry penalty is added to `L_state`, because these properties are imposed structurally and later verified independently. Structural enforcement does not by itself establish trajectory accuracy or long-rollout stability.

Stage 04D must freeze a single implementation identity/hash for the common head before training. Any arm-specific head change creates a different comparison and requires a new prospective contract.
