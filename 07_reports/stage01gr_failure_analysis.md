# Stage 01G-R failure analysis

The retained Stage 01G execution status is `V2_QUALIFICATION_EVIDENCE_INCOMPLETE`. The canonical `TypeError`, `infra_retry1` `KeyError`, and `infra_retry2` `AttributeError`, together with all tracebacks, logs, summaries, status files, and parent/child records, remain byte-identical under a 21-item SHA-256 manifest. None is reclassified as a benchmark failure.

The canonical launch is category **B — runner failure**: the execution adapter omitted the required explicit `jitter_fraction` and `seed` keyword arguments when resolving the regular layout. The first retry is category **B — runner failure**: plural storage-array keys were incorrectly used to index singular evaluator reference fields. The second retry is category **C — diagnostic failure**: the diagnostic adapter requested `midpoint_state`, which is absent from the frozen unsourced `DynamicStepResult` schema.

Configuration loading, output-directory creation, and child reclamation worked. Solver initialization worked on the retry paths; the solver itself did not fail. Evaluator handoff was never reached. Environment, solver-initialization, and unknown categories are excluded by evidence.

Root cause: execution-layer interfaces were implicit and inconsistent across parameter resolution, reference serialization, and diagnostic registration.
