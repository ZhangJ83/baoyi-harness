# Review-driven experiment TODO

## E1 — Dynamic oracle

- **Status:** completed as a synthetic counterexample; see `workspace/results/dynamic_oracle_h3.json` (greedy -0.19 vs dynamic 0.18).
- **Answers:** R2
- **Design:** finite-horizon synthetic MDP with observable evidence cost,
  delayed reward, and mutation transitions; compare CEGAR-H with exact
  backward-induction policy.
- **Metrics:** objective gap, success, cost, residual risk, regret by horizon.
- **Minimum criterion:** report the gap and a counterexample where myopic
  choice is suboptimal; do not assume the gap is zero.

## E2 — Estimator calibration and shift

- **Status:** controlled calibration sweep and 20-seed held-out synthetic calibration completed. See `workspace/results/cegarh_calibration_sweep.json` and `workspace/results/heldout_calibration_metrics.json`.
- **Answers:** R3
- **Design:** train/calibrate benefit estimates on one seed family, evaluate on
  held-out families and controlled difficulty/evidence shifts.
- **Metrics:** ECE/Brier for action selection, objective delta, risk-coverage.
- **Minimum criterion:** include null/negative shifts and report degradation,
  not only favorable settings.

## E3 — Verifier correlation sweep

- **Status:** completed; see `workspace/results/verifier_correlation_sweep.json`.
- **Answers:** R6
- **Design:** vary shared latent failure probability from 0 to 1 while holding
  marginal verifier false-accept rates fixed.
- **Metrics:** empirical all-pass false acceptance, `min(alpha_i)` bound,
  product-form estimate shown only as a deliberately invalid comparison.
- **Minimum criterion:** verify the non-independence bound remains valid.

## E4 — Official benchmark pilot

- **Status:** protocol implemented; Terminal-Bench Flash pilot is 3/3, Claude/Codex/OpenCode matched pilots are 2/3 each, and one official SWE agent pilot is 1/1. Publication-scale runs remain pending.
- **Answers:** R1, R5
- **Design:** exact pinned task IDs, same scorer/container, one attempt, native
  provider contracts disclosed; persist raw results for Xiaopu and each
  comparator.
- **Metrics:** resolved task rate, token/cost, latency, failure mode.
- **Minimum criterion:** paired task-level bootstrap 95% CI and no hidden
  provider/mode mixing.
