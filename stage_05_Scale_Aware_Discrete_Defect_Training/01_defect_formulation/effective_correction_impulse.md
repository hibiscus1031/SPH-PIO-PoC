# Effective Correction Impulse

With the origin-specific accepted time step `dt > 0`, define

```text
a_def^star  = Delta_v_def^star  / dt
a_eff^theta = Delta_v_eff^theta / dt.
```

The acceleration notation is an exact rescaling of the discrete velocity impulses, not a new target identity. Implementations may evaluate the normalized impulse form

```text
Delta_v / (dt * s_a)
```

but reporting and manifest identity remain anchored to `a_eff^theta - a_cons^star`. The object is the correction induced across a complete RK2 accepted-state transition. It must not be named continuum acceleration truth, direct pair-force truth, Stage 02 static `delta_a`, or high-resolution SPH truth.
