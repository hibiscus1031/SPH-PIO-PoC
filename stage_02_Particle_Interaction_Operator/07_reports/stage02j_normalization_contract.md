# Stage 02J Normalization Contract

The normalization decision is `prospective_specification_only`.

Because no formal leakage-audited train split exists, fitted statistics are prohibited and were not computed. The contract records future field-wise rules, units, a prospective epsilon of `1e-12` in field-native units, and the requirement that any future fitting use only a formally assigned train split.

`train_record_hashes` is empty and `normalization_statistics` is null. The five-record corpus, jitter diagnostics, validation/test data, target values, and target-derived statistics were not used for fitting.

Prospective physical transformations include domain-length scaling for position, local-support scaling for edge displacement/distance, and either train-only or prefrozen physical scales for velocity, density, and pressure. These are specifications, not fitted numerical statistics.

