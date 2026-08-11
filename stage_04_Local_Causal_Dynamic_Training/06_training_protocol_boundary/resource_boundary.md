# Resource boundary

Stage 04A performs no resource benchmark and freezes no numerical compute budget. Stage 04D must prospectively set equal optimizer-budget accounting across D1/D2/D3, maximum wall-time/memory policies, checkpoint frequency, seed count, and abort/recovery rules before formal training.

Formal qualification and formal test conclusions use CPU float64. For D3, math SDPA is mandatory. MPS float32 may be used only for resource/smoke diagnostics and must not create a formal checkpoint, qualify gradients/training, set budgets from performance, or support a test conclusion.

Resource failures, nonfinite execution, out-of-memory events, and timeout/abort outcomes must be retained and included under preregistered failure rules. Reallocating additional steps or seeds to one arm after observing outcomes is prohibited.

All later run manifests must bind hardware/software, precision, deterministic settings, backend identity, budget counters, and input/contract hashes. Stage 04A counters remain: optimizer steps `0`, training runs `0`, rollouts `0`, performance evaluations `0`.
