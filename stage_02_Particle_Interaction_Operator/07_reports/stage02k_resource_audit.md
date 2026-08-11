# Stage 02K — Resource audit

CPU float64 hard gate: K1 **PASS**, K2 **PASS**. Both are below 100,000 parameters and 1.5 GB RSS delta, complete repeated forward/backward finitely, retain no output tensors, and use edge-shaped intermediates consistent with O(E d). Dense N×N and global all-pairs attention are absent. MPS was not used for the hard gate.
