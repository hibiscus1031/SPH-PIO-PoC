# Stage 01B viscosity, sound-speed, Reynolds-number and CFL audit

Audit target: official diffSPH commit
`fff180c81d57a51035de9f4d358dbcaccf973928`.

Audit date: 2026-07-31.

## Decision

The original Stage 01 artificial-viscosity path is **not qualified for a
fixed-physical-\(\nu\) or fixed-Reynolds-number study**.

- The reachable fluid operator hard-codes \(\alpha=0.01\).
- The later configuration read is unreachable.
- The official notebook's \(\alpha\)-to-\(\nu\) formula is a
  setting-specific theoretical/empirical estimate, not an exact relation for
  the reachable discrete operator.
- That operator also retains a quadratic artificial-viscosity term when its
  linear \(\alpha\) is zero.
- No wired official velocity-diffusion operator directly accepts physical
  kinematic viscosity \(\nu\).
- Fixed \(c_s\), and therefore a fixed initial/nominal Mach number, is
  controllable without changing third-party source.

The alpha-mapping branch is stopped. A project adapter that calls diffSPH's
public generic Laplacian and multiplies it by an explicit physical \(\nu\) is a
**conditional B-path candidate**. It must pass parameter propagation,
manufactured-Laplacian, conservation, and automatic-differentiation gates
before any fixed-Re TGV run. At the time of this audit, the fixed-Re
time/space-convergence branches remain closed.

## 1. Source identity

The installed package reports diffSPH `0.2.1`. Stage 01 independently recorded:

- checkout commit:
  `fff180c81d57a51035de9f4d358dbcaccf973928`;
- 133-file checkout Python-tree SHA-256:
  `09d59c684565d12051cb0a491daf08478f43ab3803a74e9947a3a7e5beb474f8`;
- 133-file installed Python-tree SHA-256:
  `09d59c684565d12051cb0a491daf08478f43ab3803a74e9947a3a7e5beb474f8`.

The following installed files were also compared byte-for-byte with the same
commit:

| Repository-relative source | SHA-256 |
|---|---|
| `src/diffSPH/modules/velocityDiffusion.py` | `e5e40801372a7ce6712c518046fb7b479a91f026958e04efbc9f7d875d528b16` |
| `src/diffSPH/modules/viscosity.py` | `6b6071bedef16c0d91396a7c9cc80084ff5c452c00ce4e2225b197ac3deaa8bc` |
| `src/diffSPH/schemes/deltaSPH.py` | `220958abb9517e4933fd8f646d3cb36eb304ad62322a315e561cf9258a2369eb` |

Evidence: `06_experiments/stage_01_tgv/logs/stage01_source_provenance.txt`
and the Stage 01 raw configuration snapshots. No installed source file was
modified.

## 2. YAML-to-operator call chain

The complete reachable path is:

1. A Stage 01 YAML file declares `diffusion_alpha`; for example
   `01_solver/configs/tgv_cpu_32.yml:8`.
2. `01_solver/diffsph_adapter/run_tgv.py:515-523` reads the YAML with
   `yaml.safe_load` and constructs `TGVConfig`.
3. `01_solver/diffsph_adapter/tgv.py:37` stores the value, while
   `tgv.py:202-206` rejects every value other than `0.01`.
4. `tgv.py:227-234` calls `getSimulationScheme`.
5. `src/diffSPH/schema.py:71-80` selects `deltaPlusSPHScheme`,
   `DeltaPlusSPHSystem`, and `getDeltaSPHConfig`.
6. `src/diffSPH/schemes/deltaSPH.py:331-333` creates
   `config["diffusion"]["alpha"]=0.01`.
7. The adapter writes the YAML value to that configuration again at
   `tgv.py:279`.
8. `tgv.py:345-350` passes the simulator and configuration to the official
   integrator.
9. `src/diffSPH/schemes/deltaSPH.py:135-136` calls
   `computeViscosity_deltaSPH_inviscid(..., config)` for fluid particles. It
   does not pass `alphaOverride`.
10. `src/diffSPH/modules/velocityDiffusion.py:94` executes
    `alpha = alphaOverride if alphaOverride is not None else 0.01`.
11. `velocityDiffusion.py:96-104` creates a new local diffusion configuration
    containing `correctXi=True`, `viscosityFormulation="Monaghan1992"`, and
    `C_l=alpha`.
12. `velocityDiffusion.py:106-116` returns the computed acceleration.
13. `deltaSPH.py:166-169` adds that acceleration to the total velocity update.

Thus, the YAML value is recorded but does not control the reachable fluid
velocity-diffusion operator. The boundary path is different:
`deltaSPH.py:137-140` can pass `config["diffusion"]["boundary"]` as
`alphaOverride`; periodic TGV has no such boundary contribution.

## 3. Hard-coded alpha and unreachable configuration read

The exact hard-coded statement is
`src/diffSPH/modules/velocityDiffusion.py:94`.

The unconditional return spans lines 106-116. Lines 120-146 are therefore
unreachable, including:

```python
alpha = getSetConfig(config, 'diffusion', 'alpha', 0.01)
```

at line 122. A repository-wide source search found only these other uses of
the configuration alpha:

- `src/diffSPH/io.py:19`: output metadata;
- `src/diffSPH/modules/timestep.py:22`: a time-step estimate;
- `src/diffSPH/modules/velocityDiffusion.py:122`: unreachable operator code.

None propagates the YAML alpha into the reachable fluid force.

## 4. Dynamic alpha probe

The reproducible probe is
`01_solver/viscosity_audit/audit_viscosity_paths.py`. It uses CPU,
float32, a regular \(16\times16\) periodic state, and the same precomputed
neighborhood for all comparisons.

Command:

```text
conda run -n sph-pio-poc python 01_solver/viscosity_audit/audit_viscosity_paths.py --resolution 16 --output 06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe.json
```

Results:

| Probe | Values | Observed result |
|---|---|---|
| `config["diffusion"]["alpha"]` | 0, 0.01, 1 | outputs bitwise identical; max absolute difference 0 |
| `alphaOverride` output L2 norm | 0, 0.01, 1 | 4.2830787, 12.3705845, 822.1221924 |
| `alphaOverride` max difference from 0.01 | 0, 0.01, 1 | 1.0867927, 0, 107.5924988 |

`alphaOverride=0` does not eliminate the operator. The reason is visible in
`src/diffSPH/modules/viscosity.py`:

- lines 24-25 default to \(C_l=1\), \(C_q=2\);
- lines 88-89 apply both pair coefficients;
- lines 146-150 use
  \(v_\mathrm{sig}=C_l c-C_q\mu_{ij}\).

The reachable wrapper overrides only \(C_l=\alpha\), leaving \(C_q=2\).
Therefore alpha controls only one artificial-viscosity component.

Machine-readable evidence:
`06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe.json`.
Two failed pre-numerical attempts caused by upstream import-order and return-API
assumptions are preserved, with the user path redacted, in
`06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe_import_failure.txt`.

## 5. Official notebook mapping and its qualification

The official notebook at the audited commit contains, in
`examples/weaklyCompressible/05_TGV.ipynb`, Cell 20 / raw JSON lines 639-649:

\[
\nu_\mathrm{nb}
=
\alpha c_s H\frac{1}{2d+2}\frac54,
\qquad
Re_\mathrm{nb}
=
\frac{\sqrt{\kappa}\,L^{3/2}}{\nu_\mathrm{nb}},
\]

where \(H\) is the stored particle support radius and
\(\kappa=\mathrm{Kernel\_Scale}\). The saved notebook output is
\(Re_\mathrm{nb}=1853.2601725\).

Cell 21 / raw JSON lines 674-679 instead infers total effective viscosity from
kinetic-energy decay:

\[
\nu_\mathrm{decay}
=
\frac{\log(E_k/E_{k0})}{-4tk^2},
\qquad
Re_\mathrm{decay}
=
\frac{U_\mathrm{mag}\,2}{\nu_\mathrm{decay}},
\]

with saved output \(1875.9188\).

This evidence does not establish an exact \(\alpha\)-to-physical-\(\nu\)
identity:

1. the \(5/4\) factor has no derivation in the notebook or reachable operator;
2. the formula omits the retained \(C_q=2\) contribution;
3. the Monaghan switch makes dissipation flow-state dependent;
4. particle disorder, pressure/density diffusion, and shifting contribute to
   measured energy decay;
5. the two notebook Reynolds-number definitions are different;
6. `src/diffSPH/modules/timestep.py:41` uses yet another estimate,
   \[
   \nu_\mathrm{dt}
   =\frac{\alpha c_sH}{2(d+2)}.
   \]
   In two dimensions, the notebook and time-step coefficients differ by a
   factor of \(5/3\).

Classification:

- hard-coded alpha and callable behavior: exact source/dynamic facts;
- notebook formula: official demonstration formula;
- energy-decay viscosity: a posteriori total effective-dissipation estimate;
- notebook alpha-to-\(\nu\) mapping: setting-specific theoretical/empirical
  estimate;
- using that mapping as an exact, resolution-independent physical viscosity:
  **not justified**.

The Stage 01 adapter at `tgv.py:269-278` reuses the notebook's viscosity
estimate but defines \(Re=U_0L/\nu_\mathrm{ref}\), not the notebook's
\(\sqrt{\kappa}L^{3/2}/\nu_\mathrm{ref}\). This reinforces that the Stage 01
quantity is diagnostic rather than a fixed-physics input.

## 6. Search for a direct physical-viscosity operator

The audited commit contains no wired velocity operator that directly accepts
kinematic viscosity \(\nu\):

- `velocityDiffusion.py:29-50`: an earlier
  `computeViscosity_Monaghan1997` definition is overwritten by a same-named
  definition at lines 53-80;
- `velocityDiffusion.py:53-80`: takes artificial-viscosity configuration
  parameters, not physical \(\nu\);
- `velocityDiffusion.py:84-146`: the reachable DeltaSPH path described above;
- `modules/viscosity.py:15-182,188-364`: Monaghan-Gingold, Cleary, Monaghan,
  Dukowicz, Price, and Wadsley formulations use artificial-viscosity or signal
  parameters;
- `modules/sps.py:22-108`: an SPS/Smagorinsky turbulent model, not fixed
  molecular kinematic viscosity;
- viscosity switches vary artificial alpha rather than accepting fixed
  physical \(\nu\).

The only reachable source read of `config["diffusion"]["nu"]` is
`modules/timestep.py:42`, and only when
`velocityScheme=="deltaSPH_viscid"`. No corresponding
`deltaSPH_viscid` force implementation exists in the audited Python tree.

Priority-A decision: **FAIL**.

## 7. Fixed physical nu without changing third-party source

diffSPH exposes the public generic operator:

- `src/diffSPH/operations.py:498-539`: `SPHOperation`;
- `src/diffSPH/sphOperations/laplacian.py:632-802`: precomputed Laplacian;
- lines 766-785: Brookshaw, dot, and default Laplacian forms.

A project-owned adapter can calculate \(L_h(\mathbf v)\), return
\(\nu L_h(\mathbf v)\), and supply that callable to the DeltaSPH execution path
without changing an installed file. Multiplication by the explicit \(\nu\) is
exact and differentiable. However, the following properties are not implied by
the API and must be measured:

- consistency of \(L_h\) with \(\nabla^2\) on regular and jittered particles;
- sign and decay behavior;
- pairwise force antisymmetry;
- total internal force and torque;
- sensitivity to density and support variation.

In particular, the generic default/Brookshaw forms contain
\(m_j/\rho_j\). Strict mass-weighted pair antisymmetry does not follow for
unequal density. This prevents an a priori conservation claim.

Priority-B decision: **CONDITIONAL CANDIDATE**. Before fixed-Re execution it
must pass:

1. \(\nu=0\Rightarrow\mathbf a_\nu=0\);
2. \(\mathbf a(2\nu)=2\mathbf a(\nu)\);
3. manufactured periodic Laplacian errors decrease overall on regular, 5%
   jitter, and 10% jitter layouts;
4. pairwise antisymmetry, total internal force, and torque are quantified;
5. viscosity autograd agrees with a finite-difference sanity check;
6. Laplacian mode, support scheme, and physics are frozen before viewing TGV
   results.

Priority-C decision: **NOT ENTERED**. A source patch that only changes line 94
to read configuration alpha would not remove the \(C_q\) term or establish a
unique physical-\(\nu\) relation. Such a patch is insufficient for fixed-Re
V&V, so no patch has been created and no installed package has been altered.

## 8. Sound speed and Mach-number control

The official example calculates

\[
c_s=\frac{0.3H}{\kappa\,\Delta t_\mathrm{target}}
\]

at `examples/weaklyCompressible/scripts/05_TGV.py:99-100`, then writes it to
`config["fluid"]["c_s"]` at lines 117-126.

Propagation is direct:

- `src/diffSPH/regions.py:147-162,203-209` copies it into particle
  `soundspeeds`;
- `src/diffSPH/modules/eos.py:62-79` reads it for the isothermal EOS;
- `src/diffSPH/modules/viscosity.py:67-75` reads particle sound speeds for
  artificial viscosity.

Thus a project adapter can set one fixed `config["fluid"]["c_s"]` before
initialization without changing diffSPH. For \(U_0=1\), \(c_s=10\) gives the
initial/nominal \(Ma_0=U_0/c_s=0.1\). Runtime
\(\max_i\|\mathbf v_i\|/c_{s,i}\) must still be monitored because the source
contains no Mach controller.

The Stage 01 adapter currently derives \(c_s\) from resolution and target time
step at `tgv.py:214-219`; it must not be reused unchanged for fixed-physics
work.

Fixed-\(c_s\)/fixed-initial-Mach decision: **PASS, subject to explicit adapter
configuration and runtime monitoring**.

## 9. Particle spacing, support and CFL

For the official TGV setup:

- `05_TGV.py:71-73`: \(dx=L/n_x\);
- `src/diffSPH/modules/adaptiveSmoothingASPH.py:227-231`:
  \(N_H=\pi n_h^2\) in two dimensions;
- `src/diffSPH/util.py:147-168`:
  \(H=\sqrt{N_Hdx^2/\pi}\);
- with \(n_h=4\), \(H=4dx\);
- Wendland4 has \(\kappa=\mathrm{Kernel\_Scale}=2.171239\) in two dimensions.

The code's \(H\) is the compact-support radius stored in
`particles.supports`; it is not the printed `dx` that the example labels
“Smoothing length”.

`src/diffSPH/modules/timestep.py:12-71` implements:

\[
\Delta t_v=\frac{0.125H^2}{\nu_\mathrm{dt}\kappa},\qquad
\Delta t_c=\frac{\mathrm{CFL}\,H}{c_s\kappa},\qquad
\Delta t_a=\frac{0.25}{\kappa}
\sqrt{\frac{H}{a_\max+10^{-7}}}.
\]

Defaults are `CFL=0.3`, `maxDt=1e-3`, and `minDt=1e-6`. The TGV script's
local `CFL=0.3` at line 106 is not written to the configuration; the module
default supplies the same value. The official helper computes a time step only
once (`exampleUtil.py:32-35`) and the loop reuses it
(`exampleUtil.py:149-150`); per-step recomputation is commented out at
`deltaSPH.py:241`.

If the B path later qualifies and the physics is preregistered as
\(L=2,\ U_0=1,\ \nu=0.02,\ Re=100,\ c_s=10\), then:

| Grid | \(dx\) | \(H\) | acoustic bound | physical-\(\nu\) diffusion bound |
|---:|---:|---:|---:|---:|
| 16 | 0.125000 | 0.500000 | \(6.91\times10^{-3}\) | \(7.20\times10^{-1}\) |
| 24 | 0.083333 | 0.333333 | \(4.61\times10^{-3}\) | \(3.20\times10^{-1}\) |
| 32 | 0.062500 | 0.250000 | \(3.45\times10^{-3}\) | \(1.80\times10^{-1}\) |

The source default `maxDt=1e-3` is stricter initially, so the proposed
\(10^{-3},5\times10^{-4},2.5\times10^{-4}\) sequence is below these initial
limits. These bounds are source calculations, not proof of later-time
stability; acceleration and Mach margins must be logged.

## 10. Gate summary

| Gate | Status | Consequence |
|---|---|---|
| A: official wired operator accepts physical \(\nu\) | FAIL | Do not use an official direct-\(\nu\) claim |
| Existing alpha-to-\(\nu\) mapping | FAIL | Stop this fixed-Re branch |
| Fixed \(c_s\)/initial Mach | PASS | Expose explicitly in a new adapter |
| B: public generic Laplacian times explicit \(\nu\) | CONDITIONAL | V1 qualification only; no fixed-Re TGV yet |
| C: patch third-party source | NOT ENTERED | No patch or installed-source change |

No Stage 01B fixed-Re time or space convergence experiment was run before this
audit. The next permitted work is limited to qualifying the B-path operator.
