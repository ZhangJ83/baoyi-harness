# CEGAR-H synthetic ablation report

This report is a simulator result, not an external benchmark result. Each
policy sees the same generated task stream within a seed. The unit for the
interval is a seed-level task-family mean; it is not a claim of independent
benchmark tasks.

## Configuration

- 20 seeds, 2,000 tasks per seed, heterogeneous and homogeneous families.
- Objective: `success - 0.05 * cost - 1.0 * residual_risk`.
- Policies: direct, compute-only, evidence-only, always-joint, CEGAR-H, and
  pointwise oracle.
- Estimator-shift condition: independent Gaussian perturbation with standard
  deviation `0.08` applied to estimated gain/risk only; realized outcomes use
  the selected action's true values.
- Intervals: normal 95% intervals over the 20 seed means.

## Main synthetic result

| Family | Policy | Objective | 95% interval |
|---|---|---:|---:|
| heterogeneous | CEGAR-H | 0.5965 | [0.5955, 0.5975] |
| heterogeneous | always-joint | 0.5695 | [0.5686, 0.5703] |
| heterogeneous | pointwise oracle | 0.5965 | [0.5955, 0.5975] |
| homogeneous | CEGAR-H | 0.5748 | [0.5748, 0.5748] |
| homogeneous | always-joint | 0.5693 | [0.5693, 0.5693] |

In this simulator CEGAR-H matches the pointwise oracle at zero estimator noise.
That is an implementation sanity check under the simulator's constructed
features, not evidence of real-task optimality.

## Estimator-shift result

At noise `0.08`, CEGAR-H falls to `0.5697 [0.5684, 0.5711]` on the
heterogeneous family and `0.5541 [0.5538, 0.5545]` on the homogeneous family,
while the pointwise oracle remains `0.5955 [0.5943, 0.5967]` and `0.5748`
respectively. This is the expected calibration-shift failure mode and bounds
the claim: the controller is not distribution-shift invariant.

Canonical JSON outputs:

- `workspace/results/cegarh_ablation_20seed.json`
- `workspace/results/cegarh_ablation_shift_20seed.json`

The experiment does not establish Terminal-Bench, SWE-bench, PPTBench, or
competitor superiority. A future paper result needs a held-out learned
calibrator and paired external task outcomes. A separate finite-horizon
counterexample is recorded in `workspace/results/dynamic_oracle_h3.json`:
the greedy immediate-index policy acts immediately with value `-0.19`, while
the dynamic oracle verifies twice and then acts with value `0.18`. This
supports narrowing the theory to a myopic policy and explicitly not claiming
multi-step optimality.

## Verifier-correlation sweep

With three verifiers at marginal false-accept rate `alpha=0.1`, 200,000 trials
per point produced all-pass false-accept rates of `0.00106`, `0.00363`,
`0.01661`, `0.04652`, and `0.09909` as shared-error correlation increased
from `0` to `1`. The independence product remains `0.001`, while the
correlation-robust `min(alpha_i)=0.1` bound holds at every point. This is a
synthetic validation of the bound and a counterexample to presenting the
product as generally valid.

Output: `workspace/results/verifier_correlation_sweep.json`.

## Calibration sweep

To address the feature-oracle concern, a separate sweep injects both Gaussian
estimation noise (`sigma=0.04`) and matched systematic gain/risk bias in
`{-0.12,-0.06,0,0.06,0.12}`. Each point uses the same 20 seeded task streams;
intervals are over seed means. The result is a calibration sensitivity curve,
not a robustness guarantee: the heterogeneous-family objective ranges from
approximately 0.582 to 0.5965 as bias changes, with the oracle fixed at
approximately 0.5965. This quantifies regret from estimator misspecification
instead of hiding it behind the zero-noise ablation.

Canonical output: `workspace/results/cegarh_calibration_sweep.json`.

## Paired seed-level component deltas

`experiments/paired_synthetic_ablation.py` reuses the same task stream for all
policies within each seed and reports paired bootstrap intervals over 20 seed
means. On the heterogeneous family, CEGAR-H minus always-joint is
`0.0270 [0.0267, 0.0273]`, minus compute-only is `0.0196 [0.0193, 0.0199]`,
and minus evidence-only is `0.0791 [0.0786, 0.0796]`. It matches the oracle
within floating-point precision. On the homogeneous family it ties
compute-only and the oracle, while its advantage over always-joint is
`0.00552`.

These intervals are seed-level simulator intervals. The homogeneous values are
degenerate because the constructed family fixes the difficulty and evidence
quality; they must not be interpreted as independent-task uncertainty. The
canonical paired output is `workspace/results/paired_synthetic_ablation.json`.
