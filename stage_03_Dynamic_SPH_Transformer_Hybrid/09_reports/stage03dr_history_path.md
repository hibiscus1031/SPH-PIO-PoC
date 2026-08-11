# Stage 03D-R History Path

Stage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`. Stage 03D-R contract: `sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9`.

REFERENCE_PREHISTORY traces: 6; classifications: `{"HISTORY_FD_CONDITIONING_LIMITED": 1, "HISTORY_SENSITIVITY_BELOW_FD_RESOLUTION": 5}`. Each trace covers reference state, tokenization, stored token, GRU/Transformer hidden, pair coefficients, nodal correction and final objective, with leaf/grad_fn/hash/order metadata. Reverse and FD perturb the same stored tokenized prior slots. All six temporal-module-only probes have broad extended-FD windows, while only one full-rollout history probe forms a window; rollout/module sensitivity ratios range from about `1.54e-4` to `4.91e-3`. No detach, cache reuse, label misalignment, or perturb-object mismatch was found.
