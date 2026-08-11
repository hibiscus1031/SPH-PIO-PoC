# Stage 08 — Systematic Coverage V3

Stage08 is the project's final development cycle. Stage08A prospectively builds a
coverage-constrained TRAIN_V3 pool and a new in-support validation pool. It does
not instantiate a model, optimizer, scheduler, checkpoint, or training loop.

The only scientific authorization is Stage07D-R status
`TRAIN_V2_RETRAINING_FAILURE_ATTRIBUTED`, with Branch B `NOT_SUPPORTED`, all
three arm attributions `HELD_OUT_H2_SUPPORT_GAP_DOMINANT`, and unique next route
`SYSTEMATIC_COVERAGE_V3`.

Run order:

1. `python 01_systematic_coverage_design/freeze/prepare_stage08a.py`
2. `python 01_systematic_coverage_design/qualification/run_stage08a.py`

No later Stage08 stage is authorized unless the Stage08A final status is exactly
`SYSTEMATIC_COVERAGE_V3_POOL_AND_FRESH_VALIDATION_QUALIFIED`.
