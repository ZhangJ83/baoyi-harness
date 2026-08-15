# EGAD research plan

## Selected idea

Agent harness design is treated as budgeted metareasoning over two coupled decisions:
whether to spend additional inference/tool budget, and whether current evidence is fresh
enough to terminate. EGAD combines value-of-computation gating, epoch-scoped evidence,
and approximately sufficient context state.

## Non-negotiable claims policy

- No “best paper”, “SOTA”, or competitor-superiority claim without controlled results.
- Same base model, task set, container, retry, time, token, and tool policy for comparisons.
- Theory assumptions must be stated next to each theorem and stress-tested by counterexamples.
- All main figures must include uncertainty and cost, not success alone.

## Hypotheses

H1. Freshness-gated completion reduces false completion after post-verification mutations.

H2. Value-of-computation gating dominates both never-deliberate and always-deliberate
policies on success per token when task difficulty is heterogeneous and the benefit
predictor is calibrated.

H3. A structured state that preserves goal, open obligations, mutation epochs, evidence,
and recent failures has lower recovery loss than FIFO truncation at equal context budget.

H4. Correlation-robust verifier cascades retain most detection benefit without relying on
the false independence equation in the original attachment.

## Code touchpoints

- `agent/state.py`: typed evidence ledger and mutation epochs.
- `agent/harness.py`: fresh-evidence completion gate and deliberation decision events.
- `agent/deliberation.py`: value-of-computation controller.
- `agent/tools/*`: scoped mutation/evidence recording.
- `experiments/`: deterministic simulations and ablations.

## Evidence ladder

1. Minimum: unit counterexamples and deterministic simulator.
2. Solid: seeded ablation over heterogeneous synthetic task families plus offline repair tasks.
3. Maximum: same-model Terminal-Bench, SWE-bench Verified, and PPTBench evaluation.

## Stop conditions

- Abandon a theorem if its assumptions cannot be measured or its prediction fails in simulation.
- Do not run paid DeepSeek tests until all deterministic and simulated gates pass.
- Do not run full benchmarks until a small stratified pilot beats fixed baselines on the
predeclared success-cost metric without increased safety violations.

## Expected outputs

- Formal theory and proofs/counterexamples.
- Reproducible simulator with seed manifest and JSON/CSV metrics.
- Ablation tables and Pareto plots.
- External benchmark manifests and raw logs when infrastructure is restored.
- Paper draft with limitations and a claim-evidence matrix.

## Current route decision (2026-08-09)

The selected route is now CEGAR-H, with EGAD as its binary compute-gating
subproblem. Freshness alone was rejected as a novel core after locating STALE
and EA-Graph. The next local experiment is a dynamic oracle plus estimator-shift
study; external benchmarks remain gated by Docker restoration and key rotation.
