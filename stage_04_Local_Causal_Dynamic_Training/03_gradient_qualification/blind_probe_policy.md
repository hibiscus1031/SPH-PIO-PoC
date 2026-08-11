# Blind-probe policy

Stage 04C probe cases, model seeds, parameter directions, origin selection, epsilon candidates, comparison metrics, stable-window rule, and pass/fail aggregation must be committed before formal derivative results are decoded. The preregistration hash must precede the formal run manifest.

Probe design may use Stage 04B train-role metadata and unsealed qualification fixtures that are explicitly assigned for gradient qualification. It may not use sealed-test targets/states, D-R3 values, Stage 03D-R thresholds, or validation outcomes to select favorable directions or epsilons.

Formal D3 probes are blind to alternative backend outcomes until the math-backend verdict is sealed. Any exploratory backend or MPS run is diagnostic only, stored separately, and cannot alter the formal case set. Failed, nonfinite, structurally zero, topology-changing, or unstable-window cases remain in the record under preregistered classifications.

The blind policy does not require concealment of model source code or loss definitions. It requires that outcome-sensitive choices be fixed before formal values are inspected. Stage 04A defines this policy but performs no probe.
