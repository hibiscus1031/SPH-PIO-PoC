# No-Writeback Local-Descent Contract

Stage 05C shall audit the complete negative gradient without constructing an optimizer. Starting from a bitwise-captured parameter state `theta`, temporarily evaluate the preregistered ladder

```text
L_def(theta - alpha g),  g = grad_theta L_def,
```

for small positive `alpha`. The audit must demonstrate at least one preregistered local descent region, finite losses, direction consistent with the first-order prediction `-alpha ||g||_2^2`, and passing topology/structure/safety checks.

Every temporary mutation must be reverted and verified bitwise against the captured state. No checkpoint is saved, `optimizer_instances=0`, optimizer steps and parameter updates remain zero, and the audit is classified only as trainability qualification—not training. Any restoration mismatch invalidates the audit and blocks Stage 05D.
