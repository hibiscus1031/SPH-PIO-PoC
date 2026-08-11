# Stage 02J Graph Materialization

## Materialized corpus

| case | particles | directed edges | active edges | retained zero-weight exterior edges | resolution | support |
|---|---:|---:|---:|---:|---|---|
| `i_res_n12_h26_regular` | 144 | 2,880 | 2,880 | 0 | N12×N12 | H/dx 2.6 |
| `i_anchor_n16_h26_regular` | 256 | 5,120 | 5,120 | 0 | N16×N16 | H/dx 2.6 |
| `i_res_n20_h26_regular` | 400 | 8,000 | 8,000 | 0 | N20×N20 | H/dx 2.6 |
| `i_sup_n16_h22_regular` | 256 | 3,072 | 3,072 | 0 | N16×N16 | H/dx 2.2 |
| `i_sup_n16_h30_regular` | 256 | 6,144 | 5,120 | 1,024 | N16×N16 | H/dx 3.0 |

Each row is exactly one full graph sample. The H/dx 3.0 record intentionally retains graph edges inside the declared support but outside the compact kernel's positive-weight region; the 1,024 flags are evidence, not topology failures.

## Graph and state reconstruction

The materializer reconstructs the already frozen Stage 02I regular state and neighbor graph using the original deterministic CPU float64 definitions. This is source materialization, not generation of a new physical state. Recomputed state and graph hashes exactly match the Stage 02I hashes before any record is written.

Particle order is lexicographic periodic position followed by original audit ID. Edge order is source, target, pair ID. The frozen regular records already satisfy these orders, so no physical array permutation was required. Reciprocal mapping is explicit and every directed edge has exactly one reverse edge.

## Canonical serialization

The binary serializer uses magic `SPHPIOJ1`, canonical UTF-8 metadata with array references, a fixed array-path order, big-endian float64, big-endian int64, and uint8 booleans. NaN and infinity are prohibited.

| case | canonical bytes | canonical SHA-256 suffix |
|---|---:|---|
| N12/H2.6 | 335,593 | `15135dfc…a136` |
| N16/H2.6 anchor | 586,481 | `34852381…de87` |
| N20/H2.6 | 909,032 | `555ca4e3…b035` |
| N16/H2.2 | 385,770 | `cc4da41a…2d19` |
| N16/H3.0 | 686,824 | `93741010…a9bf` |

Double serialization is byte-identical. Decode/re-encode comparison preserves the complete record, state hash, graph hash, target hash, total target force, topology, and dual-reference agreement. Canonical ordering did not change a target.

