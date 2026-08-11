# Parameter-Group Coverage

Before model instantiation, Stage 05C must freeze the optimizer-variable map for D1, D2, and D3: stable group names, ordered parameter paths, shapes, dtypes, element counts, and hashes. Every trainable element must belong to exactly one group; frozen and nontrainable state must be listed separately.

For every group, the evidence matrix records full-gradient statistics, deterministic repeat, reverse/JVP directions, coordinate FD, block FD, and local-descent participation. Stage-level PASS requires the prospectively frozen group and element coverage; missing groups cannot be hidden by an aggregate norm. Common pair-head groups and arm-specific temporal groups are reported distinctly without presuming D3 superiority.
