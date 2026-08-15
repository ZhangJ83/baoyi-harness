# Candidate paper outline: CEGAR-H

Working title: **When Should an Agent Think or Check? Joint Evidence and
Computation Allocation for Cost-Risk-Constrained Harnesses**

## 1. Introduction

- Fixed harness loops fail in opposite directions: wasteful over-deliberation
  and unsupported early completion.
- Research question and qualified contributions.
- Evidence needed: cross-domain frontier figure and one stale-evidence example.

## 2. Problem formulation

- Belief/history state, meta-actions, utility/cost/latency/risk.
- Fresh-certificate constraint.
- Claim boundary: no general POMDP optimality.

## 3. Method

- Interpretable marginal-value controller.
- Evidence ledger and mutation epochs.
- Calibration from held-out trajectories.
- Correlation-aware verifier selection.

## 4. Theory

- Binary plug-in gate epsilon regret.
- Multi-action plug-in argmax 2-epsilon regret.
- Stale-certificate exclusion under complete instrumentation.
- Correlation-robust all-pass bound.
- Counterexamples: missed mutation, correlated verifiers, myopic planning gap.

## 5. Experimental design

- Controlled MDP with dynamic-programming oracle.
- SWE-bench Verified, Terminal-Bench, PPTBench-X.
- Matched policies and frozen contract.

## 6. Results

- Main Pareto/frontier comparison.
- Calibration shift and risk-coverage.
- Ablations and failure taxonomy.
- Cost breakdown and qualitative trajectories.

## 7. Related work

- reasoning/acting/search;
- SWE agent interfaces and simple workflows;
- adaptive/test-time computation;
- verification, evidence grounding, and stale memory.

## 8. Limitations and broader impact

- estimator distribution shift;
- incomplete mutation instrumentation;
- benchmark contamination and model dependence;
- cost/risk weights encode deployment preferences.

## Claim-evidence matrix

| Claim | Required evidence | Current status |
|---|---|---|
| epoch gate rejects stale certificates | invariant tests + instrumentation audit | unit-tested; audit incomplete |
| joint policy helps on heterogeneous tasks | held-out calibrated simulation + real tasks | oracle-feature simulation only |
| no gain on homogeneous tasks | negative control | passed synthetic check |
| robust to correlated verifiers | correlation sweep + bound | bound only |
| improves real frontier | paired external benchmarks | blocked/not run |
| PPT transfer | frozen PPTBench-X | not yet defined |

No abstract, conclusion, or “state of the art” language should be finalized until
the last two rows have evidence.

