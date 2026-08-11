# Reference-role boundary

New qualified D-R1 families supply the prospective train, validation, and sealed-test roles defined in Stage 04B. Their role is accepted-state supervision and later evaluation under the K=1 loss; they do not provide direct pair-force or direct acceleration targets.

The Stage 03B 18-trajectory set is historical evidence and may not be recycled as the Stage 04 split. Stage 02/03 model weights are also excluded from initialization.

D-R3 oblique shear retains the immutable role `independent_validation_only`. It cannot enter training, normalization, validation selection, checkpoint selection, architecture choice, optimizer choice, threshold selection, epsilon selection, or test calibration. Its values remain unopened for these purposes and are evaluated only in the Stage 04G independent-validation step under a preregistered protocol.

Reference midpoint values are not model inputs at training or evaluation time. Only accepted prehistory/current states form the causal input, and only the next accepted reference state is the K=1 loss target. Reference uncertainty and qualification metadata must accompany each sample and cannot be erased by aggregation.
