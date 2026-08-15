# Writing plan: CEGAR-H (2026-08-10)

## Current judgment

The evidence supports an engineering/pilot paper with (i) an epoch-scoped
fresh-evidence invariant, (ii) bounded synthetic controller findings, and
(iii) reproducible benchmark protocol engineering. It does not support a
leaderboard, state-of-the-art, or best-paper claim.

## Evidence used

- Theory and finite-grid checks: `THEORY.md`, `workspace/results/theory_bound_check.json`, `workspace/results/exhaustive_theory_check.json`.
- Synthetic controller/calibration: `workspace/results/cegarh_ablation_20seed.json`, `workspace/results/heldout_calibration_metrics.json`.
- Matched official pilot: `workspace/results/official_tb_matched_summary.json` and `workspace/results/claims_gate_current.json`.
- SWE pilot: `xiaopu-deepseek-v4-flash.xiaopu_astropy_12907_flash_20260810.json`.
- Independent local audit: `review/post_pilot_review.md`.

## Main text gate

The external-efficacy section is explicitly pilot-only until the predeclared
12-task slice and a multi-instance SWE slice are run under an approved budget.
PPT transfer remains a structural smoke test and is not a model-generated
benchmark result.

## Next revision

If budget is approved, run the frozen manifest, update the paired claim gate,
and revise only the results/limitations sections. If budget is not approved,
retain the current draft as a reproducibility and theory note.
