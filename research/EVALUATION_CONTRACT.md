# Frozen evaluation contract (pre-results)

## Research question

At a matched base model and environment, does joint evidence/computation
allocation improve the success-cost-risk frontier over fixed and single-axis
agent loops?

## Compared policies

- Direct/minimal workflow (Agentless-like control).
- ReAct-style sequential tool loop.
- Always deliberate/search.
- Fixed verifier cascade.
- Adaptive compute only.
- Adaptive evidence only.
- CEGAR-H.
- Oracle, only in synthetic environments.

## Domains

1. Synthetic controlled MDPs: mechanism, theorem assumptions, counterexamples.
2. SWE-bench Verified: coding generalization; official instance IDs and scorer.
3. Terminal-Bench: terminal task generalization; official task version/scorer.
4. PPTBench-X: create/edit/layout tasks with structural, render, and semantic
   checks. The held-out split must be frozen before paid model runs.

## Fairness controls

Same model snapshot, endpoint, system-level tool affordances where possible,
instance set, retry allowance, wall-time cap, token accounting, temperature,
container image, hardware class, and failure policy. Framework-native tools may
differ, but capability differences must be enumerated and a common-tool ablation
reported. No benchmark-specific prompt patch after seeing held-out outcomes.

Token accounting separates input-context tokens from per-response output tokens.
The current pilot contract uses 20,000 total tokens for terminal/SWE tasks and
32,000 for PPT tasks because PPT tool schemas and serialized slide state are
larger; this is a predeclared suite-level budget, not a post-hoc adjustment.

## Primary reporting

Do not collapse the paper into one cherry-picked scalar. Report:

- task success with paired bootstrap 95% confidence intervals;
- input/output tokens, tool calls, wall time, and estimated API cost;
- unsafe/unsupported completion rate;
- risk-coverage and success-cost Pareto curves;
- frontier hypervolume against a predeclared reference point;
- calibration error/Brier score for predicted marginal gains and risks.

The scalar objective `success - lambda*cost - mu*risk` is used for controller
decisions and sensitivity sweeps, not as the only headline metric.

## Statistical protocol

- Use paired instances and paired bootstrap differences.
- Predeclare seeds and preserve raw trajectories.
- Report all attempted main configurations and failed runs.
- Correct for multiple primary pairwise comparisons or clearly label exploratory
  analyses.
- Treat synthetic results as mechanism evidence, never benchmark evidence.

## Promotion gates

1. Unit invariants and deterministic counterexamples pass.
2. Offline benefit/risk predictors beat constant predictors on held-out data.
3. Stratified 10–20 task pilot improves frontier hypervolume without higher
   unsafe completion.
4. Only then run the full paid evaluation.

## Current blockers

Docker engine is unavailable on this host, so official container benchmarks are
not yet runnable. The previously pasted API key is compromised and must be
rotated; it must be supplied as an environment variable, never committed.
