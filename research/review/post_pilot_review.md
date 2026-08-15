# Post-pilot independent audit (2026-08-10)

## Scope and evidence

This is a local, skeptical audit of the current artifact, not an external
peer review. It reads the frozen protocol, official scorer outputs, claim gate,
theory checks, calibration runs, and prior review. It intentionally treats all
3-task and 1-task runs as pilots.

## Core claims

- **C1 — Harness invariant:** epoch-scoped fresh evidence prevents accepting a
  certificate produced before a mutation, assuming complete instrumentation.
- **C2 — Controller behavior:** CEGAR-H improves synthetic objective under
  heterogeneous benefit and calibrated estimates.
- **C3 — External superiority:** Xiaopu exceeds Claude Code/Codex on official
  benchmarks.

## Findings

### Strengths

1. C1 has a precise invariant and an explicit assumption boundary; the theory
   does not silently claim verifier soundness.
2. The correlation-robust bound correctly avoids an independence product.
3. The dynamic-oracle counterexample prevents an invalid multi-step optimality
   claim.
4. The Flash matched slice is reproducible and the claim gate refuses a
   superiority claim when the lower interval is zero.

### Blocking issues

1. **C3 is not supported.** Xiaopu is 3/3 versus Claude Code and Codex 2/3 on
   three easy tasks, but both paired 95% intervals are `[0, 1]`. This is one
   discordant task, not evidence of a reliable advantage.
2. **Leaderboard-scale efficacy is absent.** Terminal-Bench is a 3-task pilot;
   SWE-bench Verified is a one-instance agent pilot. Neither is a benchmark
   score.
3. **External independence is absent.** `review.md` is a baseline skeptical
   review plus an evidence update; it must not be described as an external
   peer review.
4. **Synthetic calibration is bounded.** Held-out ECE/Brier improved in the
   synthetic stream, but no real-task calibration or cost/latency analysis is
   available.

## Decision

The artifact is suitable for an engineering/pilot report with C1 and bounded
synthetic C2 claims. It is not submission-ready for a best-paper claim and
must not state C3. The next route is `baseline/analysis-campaign`: run the
predeclared 12-task slice only after a user-approved token/cost cap, then
repeat all systems under identical task IDs and update the paired gate.

## Claim-safe wording

> On a three-task Flash-provider pilot, Xiaopu resolved 3/3 tasks while Claude
> Code and Codex resolved 2/3; the paired bootstrap intervals include zero, so
> this result is exploratory and does not establish superiority.
