# Stage 05B–05H Roadmap

| Stage | Purpose | Required boundary |
|---|---|---|
| 05B | TRAIN-only defect target, conservative compatibility, scale, uncertainty qualification | preregister gates before TRAIN target decode; no model |
| 05C | optimizer-aligned gradient and no-writeback local-descent qualification | no optimizer, training, checkpoint, validation/test decode |
| 05D | training-protocol preregistration, validation opening, sealed-test preflight | freeze protocol before validation; test stays sealed |
| 05E | formal K=1 D1/D2/D3 training | only after 05B/05C/05D PASS |
| 05F | frozen-checkpoint validation and one-time sealed test | all training ended and checkpoint hashes closed |
| 05G | conditional K=2, autonomous rollout, independent D-R3 validation | new prospective contract and prior required PASSes |
| 05H | time/space/support refinement, equal-error cost, publication qualification | frozen refinement and cost protocol |

Stages 05B, 05C, and 05D cannot be skipped or combined into direct training. Each stage consumes only authorized artifacts, emits an explicit gate status, and cannot revise earlier contracts after observing outcomes.
