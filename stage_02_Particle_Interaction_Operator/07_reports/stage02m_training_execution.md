# Stage 02M — Training execution

All 9 frozen runs reached terminal states: `['EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED']`. Optimizer steps by run: `[300, 300, 300, 300, 300, 300, 440, 740, 300]`. Each update used all 10 complete train graphs, graph-balanced loss, global norm clipping, AdamW and the frozen warmup/cosine schedule. No run, seed, initialization or budget was added or replaced.
