# Stage 05C Coordinate and Block Finite Differences

The frozen six-epsilon, central plus/minus, twice-repeated ladder produced valid adjacent stable windows for 1076/1080 probes. All paths were deterministic, safe, and topology-preserving, but four required probes failed the frozen stable-window rule:

- D1 / seed 20500502 / LCDF_07 / D1_TOKEN_ENCODER / coordinate / sha256:3e83f230a85ff39ee97ea8f9964fa11ad2668f84291c8bbce244ccf2ca8526f8
- D1 / seed 20500502 / LCDF_07 / D1_TOKEN_ENCODER / block / sha256:1cc6c29e128dae209787d9e95468f6a3cd675beed7c7b403b94a62da2564eb92
- D2 / seed 20500503 / LCDF_06 / D2_PAIR_HEAD / coordinate / sha256:9fb0443d1cbac82cd765f6a2642297e9307a89a07034f0f68d4079762a228a69
- D2 / seed 20500503 / LCDF_06 / D2_PAIR_HEAD / coordinate / sha256:b0aa122c427bea6da621fd27751034f17184b92e878ee50c76afe36044b59fb7

The failures were retained. Seeds, coordinates, blocks, directions, epsilons, and gates were not changed. Therefore overall hard gate F fails even though the 2/3-seed parameter-group aggregation passes.
