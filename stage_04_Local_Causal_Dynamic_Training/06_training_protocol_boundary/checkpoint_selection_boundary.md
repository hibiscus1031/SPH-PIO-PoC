# Checkpoint-selection boundary

Stage 04D must define one checkpoint schedule and one selection rule shared by D1/D2/D3 before formal training. The rule may use only preregistered training and validation information and must define tie-breaking, failed/nonfinite-run handling, and whether a terminal or validation-selected checkpoint is used.

Sealed-test and D-R3 data cannot select checkpoints, trigger early stopping, tune schedules, or decide which seed to report. The sealed test is released only after model parameters, chosen checkpoints, normalizers, thresholds, and analysis code hashes are frozen.

Each formal checkpoint must record model-arm identifier, fresh-initialization seed, optimizer state, step/budget counter, split-manifest hash, loss-contract hash, common-head identity, precision/device, deterministic settings, and backend identity. D3 resume requires exact math-SDPA identity compatibility.

Stage 04A creates no checkpoint and makes no selection.
