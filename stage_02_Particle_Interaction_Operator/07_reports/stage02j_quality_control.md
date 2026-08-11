# Stage 02J Quality Control

All five records pass the frozen Stage 02B schema, Stage 02J extension schema, and semantic QC. Results are retained in `quality_control_results.json`.

The hard checks for every record are:

- schema completeness and field units;
- finite values and shape consistency;
- reciprocal topology, duplicate-edge absence, and missing-reciprocal absence;
- strict-support compliance and zero-weight exterior-edge retention;
- target sign, `delta_a=a_ref-a_SPH`, and `y=m*delta_a`;
- Fourier/analytic agreement and historical pair-force compatibility;
- deterministic binary bytes and reversible canonical record;
- state, graph, target, and total-force round-trip identity;
- complete hash-bearing provenance chain;
- absence of edge-pair label and projection writeback.

Summary: 5 PASS, 0 hard failures, 0 rejected records, and 0 infrastructure retries. Because no failure occurred, no retry or before/after repair lineage was needed. The records are accepted as controlled development/audit records; this QC result alone does not confer future-training eligibility.

