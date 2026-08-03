# Stage 01G — Low-amplitude acoustic standing-wave design

## Linear theory and model-form boundary

The future benchmark is a periodic, inviscid, low-amplitude standing mode on \([-1,1)^2\):

\[
\rho_0=1,\quad c_s=20,\quad \nu=0,\quad k_a=\pi,\quad t_f=0.1.
\]

The independent linear theory is

\[
\rho=\rho_0[1+\epsilon_a\cos(k_ax)\cos(c_sk_at)],
\]
\[
u_x=c_s\epsilon_a\sin(k_ax)\sin(c_sk_at),\qquad u_y=0,
\]
\[
p=c_s^2(\rho-\rho_0).
\]

The horizon is one theoretical period. The main amplitude is \(\epsilon_a=0.005\), and the amplitude audit uses 0.0025, 0.005, and 0.01. This is explicitly **linear-acoustic-regime validation**, not validation against a finite-amplitude nonlinear exact solution. Finite-amplitude departure from linear theory is a model-form uncertainty and cannot be reported as pure numerical error.

Initialization uses \(V_i=(2/N)^2\) and \(m_i=\rho(x_i,0)V_i\). Masses remain fixed. Numerical density must always be obtained from the kernel sum; the linear exact density may be used only by the evaluator and must never overwrite numerical density.

The reference does not use project RK2, an MMS source adapter, or an SPH residual correction. There is no external source.

## Prospective matrix

| Run ID | epsilon | N | H/dx | dt | Purpose |
|---|---:|---:|---:|---:|---|
| `g_acoustic_e5e3_n24` | 0.005 | 24 | 4.5 | 6.25e-5 | main resolution |
| `g_acoustic_e5e3_n32` | 0.005 | 32 | 5.049509756796392 | 6.25e-5 | main resolution |
| `g_acoustic_e5e3_n48` | 0.005 | 48 | 5.5 | 6.25e-5 | main resolution |
| `g_acoustic_e5e3_n32_dt_half` | 0.005 | 32 | 5.049509756796392 | 3.125e-5 | time-step isolation |
| `g_acoustic_e5e3_n48_rep2` | 0.005 | 48 | 5.5 | 6.25e-5 | float64 determinism |
| `g_acoustic_e2p5e3_n48` | 0.0025 | 48 | 5.5 | 6.25e-5 | amplitude audit |
| `g_acoustic_e1e2_n48` | 0.01 | 48 | 5.5 | 6.25e-5 | amplitude audit |

Each future run has a unique directory and is `PREREGISTERED_NOT_EXECUTED`. Evaluation times use integer ticks; ticks `0, 800, 1600, 2400, 3200` correspond to \(t=0,0.025,0.05,0.075,0.10\).

## Metrics and gates

Metrics are density/velocity fundamental amplitudes; phase speed; one-period phase error; density/velocity signal-normalized L2; pressure error; second-harmonic/fundamental ratio; transverse leakage; mean momentum drift; mean density and pressure bias; and topology/resource/determinism.

| Gate | Prospective requirement |
|---|---|
| ACOUSTIC1 | All states finite; every hard-safety gate passes. |
| ACOUSTIC2 | Main-amplitude N48 phase-speed relative error <= 0.02. |
| ACOUSTIC3 | N48 density fundamental-amplitude relative error <= 0.05. |
| ACOUSTIC4 | N48 velocity fundamental-amplitude relative error <= 0.05. |
| ACOUSTIC5 | N48 one-period density and velocity signal-normalized L2 are each <= 0.10. |
| ACOUSTIC6 | Transverse velocity leakage <= 1e-3. |
| ACOUSTIC7 | Main-amplitude density, velocity, and phase errors each satisfy N24 > N32 > N48. |
| ACOUSTIC8 | Halving N32 dt changes each primary error by no more than 0.10 relatively. |
| ACOUSTIC9 | The second-harmonic/fundamental ratio must not systematically increase along epsilon 0.01 -> 0.005 -> 0.0025. |
| ACOUSTIC10 | The claim remains explicitly limited to the linear-acoustic regime. |
