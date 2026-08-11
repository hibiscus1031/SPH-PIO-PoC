# Conservative-compatible dynamic neural-SPH architecture

Conservative-compatible dynamic neural-SPH construction. (a--e) An unordered neighbor pair is evaluated once, resolved in radial/transverse bases, and applied reciprocally so that the correction forces are antisymmetric. (f) D1--D3 are comparison arms, not a performance ranking. (g,h) Midpoint RK2 rebuilds the graph at each source evaluation and commits only accepted states to causal history. (i) D0 is the exact zero-correction identity. These contracts establish architecture semantics, not trainability.
