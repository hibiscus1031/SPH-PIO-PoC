# Time/space/support refinement contract

Future solution verification requires: time path `dt, dt/2, dt/4`; at least three particle-resolution levels `N`; at least three support ratios `H/dx`; and horizon path `1,2,4,8,long autonomous`. Family lineage stays explicit across all variants, so refinement variants cannot be split as independent samples.

Reports decompose baseline-SPH error, hybrid error, reference uncertainty, time error, spatial error, learned-model error, support sensitivity, and identifiable cross terms. D-R2 isolates time error for the same semidiscrete operator but is not spatial truth. Convergence order/GCI is reported only when assumptions and asymptotic behavior are demonstrated.

`hybrid error decreased` must never be rewritten as `spatial convergence restored` without the full D6 evidence. D8 speed/utility claims require equal-error comparisons with wall time, memory, and reference uncertainty.
