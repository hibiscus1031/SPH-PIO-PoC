# Stage 02K — Differentiability audit

K1: **PASS**; K2: **PASS**. Parameter and input gradients are finite and nonzero as audited; manual backward is repeated. Central finite differences at `1e-4`, `3e-5`, and `1e-5` cover coefficient head, scalar encoder, K2 attention logit, density, pressure and relative velocity. No optimizer step was executed.
