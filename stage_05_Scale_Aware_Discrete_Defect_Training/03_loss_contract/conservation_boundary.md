# Conservation Boundary

The reciprocal antisymmetric pair head hard-codes zero net learned pair force. Therefore the first-round loss contains no conservation penalty, antisymmetry penalty, center-of-mass projection penalty, torque penalty, or equivalent soft surrogate.

The target is projected prospectively into the exactly representable conservative subspace through `a_cons^star`; the incompatible center component is reported rather than fitted. A nonzero incompatible fraction is a target-compatibility fact and must be adjudicated by the Stage 05B coverage gate, not hidden inside an auxiliary penalty.
