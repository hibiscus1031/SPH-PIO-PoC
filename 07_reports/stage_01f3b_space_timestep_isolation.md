# Stage 01F3B space-timestep isolation

Before any N16/N24/N48 formal spatial result existed, MMS-A and MMS-B were run at N32 with `dt=6.25e-5` and `3.125e-5`, `t_final=0.02`.

Maximum relative changes between candidate steps were:

| Solution | position | velocity | density | pressure |
|---|---:|---:|---:|---:|
| MMS-A | 5.206e-6 | 6.910e-7 | 4.681e-6 | 4.681e-6 |
| MMS-B | 5.274e-6 | 5.141e-7 | 3.901e-6 | 3.901e-6 |

All values are far below the preregistered 10% threshold. The frozen formal space step is therefore **`dt_space=6.25e-5`**. This selection was not revisited after viewing the spatial trends.
