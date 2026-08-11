# Split and sealed-test contract

Stage 04B must assign complete formula-lineage components to four disjoint roles:

1. train families;
2. validation families;
3. sealed-test families;
4. independent D-R3 validation.

The split manifest must list every component and prove pairwise disjointness before training. The same role allocation is shared by D1, D2, and D3.

Before sealed-test release, target/state decode count must equal exactly `0`. Encrypted, access-controlled, or physically separated payload handling must allow metadata/provenance validation without exposing target/state values. Access attempts and decode events must be logged. Test release requires the preregistered 04D trigger and must occur only after checkpoints and selection decisions are frozen.

No test target may set normalization, thresholds, budgets, or checkpoint choices. If the seal is broken early, the designated test components cannot support a formal sealed-test claim and a prospective replacement protocol is required.

Stage 04A creates no test and releases no state. It freezes only these handling rules.
