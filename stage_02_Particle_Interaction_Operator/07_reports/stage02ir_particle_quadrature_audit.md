# Stage 02I-R Particle Quadrature Audit

## Contract

The original masses and target fields remain frozen. The primary diagnostic is `sum_i m_i a_ref_i`, compared with the zero continuum integral. `sum_i (m_i/rho_i) a_ref_i` is reported only as an alternative acceleration-weight diagnostic; it neither replaces the physical force-density volume integral nor changes a target. The physically dimensioned identity `sum_i (m_i/rho_i)(rho_i a_ref_i) = sum_i m_i a_ref_i` holds at roundoff.

## Regular versus jitter geometry

Regular cases have total reference residuals at roundoff scale. Disorder introduces non-zero sampling residual together with larger local quadrature defects:

| candidate | zeroth-defect RMS | first-moment RMS | isotropy median | isotropy minimum | `||F_ref,total||` |
|---|---:|---:|---:|---:|---:|
| jitter05 | 1.34016e-2 | 9.98945e-4 | 0.970776 | 0.921065 | 1.62988e-4 |
| jitter10 | 2.78877e-2 | 2.11220e-3 | 0.940413 | 0.856082 | 9.08541e-4 |

For jitter05, the mass-weighted total is `(1.021054e-4, -1.270418e-4)` and the diagnostic `(m/rho)*a_ref` sum is `(1.019039e-4, -1.272770e-4)`. For jitter10, neither alternative weighting nor pressure/viscosity separation removes the finite residual. Alternative weights are therefore attribution diagnostics only.

## Pressure and viscosity attribution

Both pressure and viscosity particle sums are finite for the jitter cases, while their continuum integrals are zero. Pressure dominates the total magnitude; viscosity is smaller but independently non-zero. This rules out an explanation based solely on one final combined total.

Local correlations between the global-force-aligned particle contribution and the zeroth, first-moment, and anisotropy defects are weak and mixed in sign (absolute values below 0.08). They do not provide a single local causal scalar. The global attribution instead rests on the joint evidence: zero continuum integral, exact SPH cancellation, stable dual references, increasing quadrature defects under stronger jitter, and the general-pair zero-sum obstruction.

## Fourier/analytic reference comparison

`H_REF_FOURIER2` and `H_REF_ANALYTIC` agree in field values and total-force residuals:

| candidate | total-force difference norm | particle-field RMS difference | classification |
|---|---:|---:|---|
| jitter05 | 2.57115e-17 | 2.74857e-14 | `PARTICLE_QUADRATURE_CONTAMINATION_CANDIDATE` |
| jitter10 | 4.96092e-17 | 1.71647e-14 | `PARTICLE_QUADRATURE_CONTAMINATION_CANDIDATE` |

The two references reproduce the same non-zero particle sum to many orders below the residual itself. Reference sensitivity therefore remains closed and is not reopened.

## Attribution result

The jitter non-zero force is attributed to particle quadrature contamination under the frozen equal-mass target contract. No independent preregistered conservative quadrature contract exists in this stage, so no versioned target is constructed and no existing target is altered.

