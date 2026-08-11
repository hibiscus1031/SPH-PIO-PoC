# Stage07B actual optimizer update

- Fresh seeds: 20700701, 20700702, 20700703; all nine models were freshly initialized.
- Optimizer: AdamW, betas `(0.9,0.999)`, eps `1e-12`, weight decay `0`, AMSGrad false, global clip `1.0`.
- Sole LR: `1e-5`; higher-LR experiments: 0.
- Formal contexts: 135/135; full-gradient identity 135/135; actual one-step descent 135/135.

| arm | lineages passing 2/3 | GLOBAL seeds | coordinate diagnostic | arm pass |
| --- | --- | --- | --- | --- |
| D1 | 14 | 3 | PASS | PASS |
| D2 | 14 | 3 | PASS | PASS |
| D3 | 14 | 3 | PASS | PASS |
