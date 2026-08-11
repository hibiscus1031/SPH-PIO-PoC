# Local-causal training definition v0.1

## Sample and causal information set

For trajectory origin `n`, the accepted history is

`H_n = (S_ref^(n-3), S_ref^(n-2), S_ref^(n-1), S_ref^n)`.

The first three states are strictly earlier than the origin and `S_ref^n` is the current reference state, so accepted history length is exactly `H=4`. Legal token fields and their transformations must be frozen in Stage 04D and must be identical across D1, D2, and D3. D1 is instantaneous and may ignore temporal distinctions by architecture, but it receives the same legal current-state token interface; D2/D3 may use the causal prehistory. No future state or midpoint reference is exposed as model input.

## Formal transition

The v0.1 training horizon is exactly `K=1`. Starting from `S_ref^n`, each arm executes one complete start → midpoint → accepted RK2 step with the same deterministic solver wrapper and graph rules. The output is `S_theta^(n+1)`. The target is `S_ref^(n+1)` and supervision is applied only through the accepted-state loss.

At the midpoint, positions/state are predicted from the start evaluation, the neighbor graph is rebuilt from that predicted midpoint state, and a midpoint token is constructed ephemerally. The midpoint token may be used within the second RK2 evaluation but is never committed to accepted history. The accepted prediction is committed only as the output of the transition; during K=1 supervised training there is no second autonomous step.

## Optimized quantities

Only neural-network parameters of the active arm are optimizer variables. Initial velocity, initial density, reference prehistory states, current reference state, graph indices, and reference accepted target are fixed inputs/data. Their input derivatives may be inspected later only as diagnostic evidence and cannot determine the K=1 training hard-gate verdict.

## Exclusions

The formal target is not direct acceleration correction, direct `delta_a`, or direct pair force. No reference midpoint state may be injected after training begins. No Stage 02/03 weight is loaded. This definition does not assert that a one-step fit will remain stable under autonomous rollout.
