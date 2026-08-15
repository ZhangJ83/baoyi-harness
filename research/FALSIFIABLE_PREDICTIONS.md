# Falsifiable prediction ledger

This ledger separates claims that can be tested from implementation goals.  A
prediction is not promoted to a paper claim until its preregistered data and
failure cases are present.

| ID | Prediction | Observable test | Falsifier | Current evidence |
|---|---|---|---|---|
| P1 | Freshness-gated completion never accepts a certificate from before the latest mutation epoch. | Inject a mutation after a passing verifier and call `finish`. | Any stale certificate discharges the changed requirement. | Offline regression passes; uninstrumented external side effects remain out of scope. |
| P2 | Under heterogeneous task benefit, adaptive computation/evidence selection improves the cost-risk frontier over fixed direct/evidence-only policies. | Paired seeded simulator, report risk and cost at every budget quantile. | The adaptive Pareto curve is dominated by a fixed policy or the effect disappears under held-out seeds. | Synthetic 20-seed ablation only. |
| P3 | The correlation-robust all-pass false-acceptance bound is not violated without conditional-independence assumptions. | Reproduce the declared finite sweep and report marginal and all-pass rates. | Any sweep violates `all_pass <= min(marginal_alpha)`. | Finite randomized/grid checks pass; not a universal empirical guarantee. |
| P4 | Context compaction below the stated transition-kernel error preserves bounded finite-horizon value loss. | Compare full and compressed histories under a controlled simulator and estimate the kernel error. | Observed loss exceeds the stated bound under its assumptions. | Theorem plus finite checks; no real-task claim yet. |
| P5 | On the preregistered matched task slice, Xiaopu's paired success delta is positive under enforceable common budgets. | Official scorer, task-level paired bootstrap and exact McNemar test. | CI lower bound is non-positive, exact test fails, or budget parity is unverifiable. | Three-task pilot is exploratory; parity is currently unverified. |
| P6 | Render-feedback iterations reduce PPT overflow/overlap rate relative to a no-render-feedback control. | Frozen model-generated decks, blinded render review, structural checks and inter-rater agreement. | No improvement or a cost-adjusted regression on held-out prompts. | Deterministic structural smoke only; prediction untested. |

The ledger is deliberately asymmetric: passing a prediction supports only its
stated scope, while a failed prediction invalidates the corresponding claim
and triggers a revision of the harness or theory.
