# Stage 02M — Validation selection

Validation was evaluated every 20 updates on exactly five frozen graphs without gradients. Best updates were `[100, 40, 40, 40, 20, 40, 240, 540, 20]` using minimum graph-mean Q_L2 with earlier tie-break. Early-stopping states: `['EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED']`. Test metrics played no selection role.
