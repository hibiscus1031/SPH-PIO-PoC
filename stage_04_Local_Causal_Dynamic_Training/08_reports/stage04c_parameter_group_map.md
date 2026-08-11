# Stage 04C Parameter Group Map

All trainable elements were resolved from the actual Stage 03C `named_parameters()` paths and assigned exactly once. Unassigned elements: 0; multiply assigned elements: 0. Combined D3 Q/K/V tensors use non-overlapping row slices `[0:32]`, `[32:64]`, and `[64:96]` in both Transformer layers. D3 relative-offset embeddings and LayerNorm tensors are registered with the feed-forward/temporal-support group.

| Arm | Group | Elements | Tensor/slice rows | Group hash |
|---|---|---|---|---|
| D1 | D1_TOKEN_ENCODER | 1408 | 4 | sha256:3dbc8832b18490cf3561936e482b2f8346832c724b9ccb267877ad4c6be3b96b |
| D1 | D1_PAIR_HEAD | 4354 | 6 | sha256:9bde3c750cb0643ecd34b5abfdfaa1b1c163f3c9a07a30a3d8851aaf7ba48bf8 |
| D2 | D2_TOKEN_ENCODER | 1408 | 4 | sha256:2703db0bc13d5d9d28a1bbbccde6286812dc49d98a973cb1bcb24e5778f4dedb |
| D2 | D2_GRU | 6336 | 4 | sha256:7dc06d90feaca6f079d76d63a7450d140ea5e5d16bae23ede293802629ca5cb7 |
| D2 | D2_PAIR_HEAD | 4354 | 6 | sha256:786de1849031fbcacf90fd478465f4aed5df35a367bb262c571d735b0baf9cd3 |
| D3 | D3_TOKEN_ENCODER | 1408 | 4 | sha256:9a209bd22930130dab12edf6be249ba04380e547bc64afc699fd5a3677188c46 |
| D3 | D3_ATTENTION_O | 2112 | 4 | sha256:73992b9af59d65f897c7f544a7362a0e376a3e3c66a037880b2f07966a409209 |
| D3 | D3_FEED_FORWARD | 8768 | 17 | sha256:a6b482b83369ce35a69d238e247588213d676d43dea7782c82d70643c02511a7 |
| D3 | D3_PAIR_HEAD | 4354 | 6 | sha256:9525dfbf14e994d8a2b276c2c480f2662ca0f5102b97aae6645601615ad4c64c |
| D3 | D3_ATTENTION_Q | 2112 | 4 | sha256:467523ffc68c2c58758e1b215967c0165474b6d13921d9ab90c8ec05c3cf6671 |
| D3 | D3_ATTENTION_K | 2112 | 4 | sha256:0b7ec3ec6eb837b99871029decdab1ee09fbe603b753a31304c57b0d00dc4f62 |
| D3 | D3_ATTENTION_V | 2112 | 4 | sha256:ea960b5c38691b96b7bb89f9470565fcb9a3c2aa766ae088a11e57aa07f128b7 |

Fresh parameter counts are D1=5,762, D2=12,098, D3=22,978. Three independent initializations used seeds 20400401–20400403; checkpoint and historical weight reads were zero.
