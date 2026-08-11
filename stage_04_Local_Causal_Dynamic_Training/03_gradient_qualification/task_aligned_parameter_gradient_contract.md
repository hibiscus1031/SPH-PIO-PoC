# Task-aligned parameter-gradient contract

## Objective

Stage 04C must differentiate the exact accepted-state objective `L_state` used for formal training. The generic Stage 03D random scalar projection of final state is not an admissible hard-gate objective for Stage 04.

For a frozen parameter vector `theta` and preregistered direction `p`, the core scalar is the directional derivative `d/dalpha L_state(theta + alpha p)|_(alpha=0)`. Reverse-mode VJP/backpropagation, forward-mode JVP, and central finite differences must estimate this same scalar under identical inputs and math backend.

## Hard-gated optimizer variables

- D1: token encoder parameters and pair coefficient-head parameters.
- D2: token encoder, GRU parameters, and pair head.
- D3: token encoder; attention Q/K/V/O parameters; feed-forward parameters; and pair head.

Stage 04C must define coverage so that every named group contributes formal hard evidence; a passing aggregate cannot hide a missing group. Only parameters that Stage 04E would update are within this hard boundary.

## Diagnostic-only input derivatives

Initial velocity, initial density, and reference prehistory tokens are fixed inputs in K=1 supervised training, not optimizer variables. Their derivatives are retained as diagnostic-only probes if measured, but do not determine the K=1 parameter-gradient verdict. Excluding them from the hard gate does not claim that their Stage 03D gradient failures are repaired.

## Formal environment

Formal hard evidence uses CPU float64; D3 additionally uses fixed PyTorch `SDPBackend.MATH`. Any other backend/device/precision is diagnostic only.
