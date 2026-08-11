# Rotation- and Reflection-Invariant Scaling

`s_a` reduces each vector through the Euclidean squared norm and then applies only scalar weighted means and a square root. For every orthogonal transform `Q`, including reflections,

```text
||Q a||_2^2 = ||a||_2^2,
RMS_bal(Q a) = RMS_bal(a),
```

so `s_a` is invariant to rotations, reflections, and coordinate-axis permutations. The same rule applies to `u_a`. Per-axis standardization, covariance whitening, learned normalization, or any orientation-dependent scale is outside the Stage 05 contract.
