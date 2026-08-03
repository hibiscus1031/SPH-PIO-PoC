# Stage 01F5B N64 branch

| MMS | field | nonmonotone | N48/N32 >0.95 | sign inconsistent | asymptotic unclear |
|---|---|---|---|---|---|
| MMS_A | density | False | False | False | True |
| MMS_A | position | False | False | False | True |
| MMS_A | pressure | False | False | False | True |
| MMS_A | velocity | False | False | False | True |
| MMS_B | density | False | False | False | True |
| MMS_B | position | False | False | False | True |
| MMS_B | pressure | False | False | False | True |
| MMS_B | velocity | False | False | False | True |

Immutable decision: `TRIGGERED`.

The original `f5_n64_smoke_a` raw status remains `FAIL`. It generated no numerical state and retained the original pure-infrastructure failure evidence. The protocol-authorized unique `f5_n64_smoke_a_infra_retry1` status is `PASS`; the effective frozen-DAG predecessor status is `PASS`.

| Conditional run | Raw status | Effective status |
|---|---|---|
| f5_space_a_n64 | PASS | PASS |
| f5_space_b_n64 | PASS | PASS |
| f5_n64_smoke_a | FAIL | PASS |
| f5_n64_smoke_b | PASS | PASS |
| f5_ref_space_b_n64_baseline | PASS | PASS |
| f5_ref_space_b_n64_tighter | PASS | PASS |
| f5_ref_space_b_n64_third | PASS | PASS |
| f5_n64_smoke_a_infra_retry1 | PASS | PASS |
