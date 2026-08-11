# Final claim boundary

## Allowed conclusions

- **C1** (SUPPORTED; Stages02–08): Structural correctness, target representability, gradient validity, optimizer-level trainability, and successful solver training are distinct qualification layers.
- **C2** (SUPPORTED_IN_AUDITED_SCOPE; Stages03,06,07): Hard reciprocal antisymmetry can preserve linear-momentum-compatible correction structure through dynamic RK2 training.
- **C3** (SUPPORTED_IN_AUDITED_SCOPE; Stage04): A raw next-state loss can provide poorly detectable training gradients even when the neural correction Jacobian is nonzero.
- **C4** (SUPPORTED_IN_AUDITED_SCOPE; Stages05–06A): A D0-centered scale-aware conservative discrete-defect target can restore identifiable optimizer-level training signals.
- **C5** (SUPPORTED; Stages06A–06C): Verified local descent and actual optimizer-update dynamics do not guarantee achievement of a frozen global training criterion.
- **C6** (SUPPORTED; Stage07): Increasing formula heterogeneity alone does not guarantee coverage of the discrete correction-target manifold.
- **C7** (SUPPORTED; Stage08): Formula/physics descriptor coverage does not imply raw correction-target manifold coverage.
- **C8** (SUPPORTED; Stage08): A prospectively systematic coverage design can improve descriptor-space support while still fail target-space coverage.
- **C9** (SUPPORTED_NEGATIVE_BOUNDARY; Stages06–08): The project did not establish a qualified trained SPH–Transformer solver.

## Prohibited claims

- Transformer is superior to MLP/GRU.
- Transformer fails generally.
- neural SPH cannot work.
- attention is equivalent to an SPH kernel.
- Stage01 baseline is fully V2-qualified.
- Stage07 heterogeneity augmentation improved the solver.
- Stage08 systematic coverage solved the support gap.
- validation performance implies sealed-test performance.
- formal training succeeded.
- autonomous rollout improved SPH.
- high-resolution SPH is truth.
- all parameter coordinates have qualified FD.
- D3 temporal dependence proves Transformer necessity.

The route closure is scoped to the frozen project hierarchy, roles, architectures, loss, optimizer, qualification philosophy, and final-cycle policy. It is not an impossibility proof or a prohibition on future independent research.
