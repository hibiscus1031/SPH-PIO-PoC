# Stage 05A Gradient Qualification Strategy

Stage 05C uses four mutually supporting evidence layers: (A) optimizer-group full-gradient L2/RMS/Linf, finite/nonzero counts, and deterministic repeats; (B) CPU float64 math-SDPA reverse/JVP agreement on preregistered blocks and directions; (C) hash-selected coordinate and compact-block central FD over a preregistered epsilon ladder and stable-window rule; and (D) full negative-gradient local descent over preregistered small steps.

Local descent is temporary and optimizer-free. At least one admissible descent region must be finite, directionally consistent with first order, and topology/safety compliant; parameters must be bitwise restored, checkpoints remain absent, and optimizer instances remain zero.

The former single-complete-group unit-random-direction absolute threshold is not the sole Stage 05C hard gate. This prospective strategy does not revise or repair Stage 04C evidence.
