# Stage 02M-P — Failure-evidence basis

Stage 02M 的 164 个历史 checkpoint 均为 `NEVER_FIT_TRAIN`。Stage 02M-R 以 K1 两个 seed 的 head-only tangent 可达性，加上极小 loss、Adam epsilon 与 weight-decay dominance，将主失败源归因为 optimization conditioning。v0.2 只改变 supervision loss scale、Adam epsilon 与 weight decay；architecture、features、seed count、budget 和 success gates 不变，以隔离该机制。历史 validation/test metrics 未用于选择这些数值。
