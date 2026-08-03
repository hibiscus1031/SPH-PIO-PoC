# Independent validation qualification summary

## Shear gates

| Gate | Status |
|---|---|

## Acoustic gates

| Gate | Status |
|---|---|

## Evidence completeness

- Uncertainty complete: `False`
- Provenance complete: `False`
- Single total GCI: `not generated`

## Execution controls

- Hard safety: `FAIL`
- Determinism: `FAIL`
- Executed runs: `0/12`
- V3 started: `False`
- Stage 02 started: `False`
- Training started: `False`
- Label generation started: `False`

## Preserved execution blocker

`g_shear_n24` produced no completed formal run. The canonical launch failed with `TypeError` before solver initialization; `infra_retry1` failed with `KeyError` before time stepping; `infra_retry2` failed with `AttributeError` during first-step diagnostics before any checkpoint, reference file, or evaluator result was written. All three failure summaries, tracebacks, status records, parent/child process records, and logs are retained. The remaining four shear runs and all seven acoustic runs were not started.

## Unique status

`V2_QUALIFICATION_EVIDENCE_INCOMPLETE`
