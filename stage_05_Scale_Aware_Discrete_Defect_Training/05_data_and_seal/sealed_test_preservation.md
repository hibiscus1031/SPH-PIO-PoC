# Sealed-Test Preservation

Throughout Stages 05A–05C the required counts are:

```text
sealed formula decode = 0
sealed state decode   = 0
sealed target decode  = 0
sealed origin decode  = 0
```

Stage 05D performs sealed-test preflight without decoding payload. SEALED_TEST remains closed through Stage 05E training and checkpoint selection. Only Stage 05F, after every formal training run is terminated and selected checkpoint hashes are irrevocably frozen, may authorize one one-time test release under an audited protocol.

Sealed results may not tune, rerun, replace, or select anything. Stage 05G independent D-R3 validation is distinct from and cannot retroactively influence the one-time release.
