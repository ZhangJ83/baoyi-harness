# Independent skeptical review: CEGAR-H (baseline review)

> This review predates the 2026-08-10 official pilots. Its reject
> recommendation remains the conservative status of the full paper claim;
> the post-pilot evidence update is appended below.

## Summary

The manuscript proposes a harness controller that jointly allocates extra
computation/evidence and enforces epoch-scoped fresh completion certificates.
The formal binary gate and stale-certificate invariant are clear and useful as
engineering claims. The current evidence, however, is mostly unit tests and a
synthetic simulator. It does not yet support claims about real-agent
improvement, benchmark superiority, or a best-paper-level contribution.

## Strengths

1. The theory explicitly distinguishes a pointwise plug-in gate from a
   multi-action argmax and avoids an unsupported sublinear-regret claim.
2. The correlation-robust verifier bound correctly avoids multiplying error
   probabilities without a conditional-independence assumption.
3. The 20-seed simulator includes a negative homogeneous control and an
   estimator-shift failure condition.
4. The benchmark protocol records a task-level statistical unit and keeps
   official/superiority claims disabled until matched runs exist.

## Major concerns

### R1. No external efficacy evidence (blocking)

The current official Terminal-Bench evidence is a two-task easy slice, and the
official SWE-bench oracle smoke stopped before tests because Docker apt
dependencies were unreachable. There is no agent-generated official
SWE-bench score and no full Terminal-Bench score. The main efficacy claim must
be removed or explicitly marked as a future test.

### R2. The simulator oracle is pointwise, not dynamic

The current `oracle` selects the best action for each synthetic state. That
does not test multi-step planning or belief-state value. The paper should call
it a pointwise oracle and add a small finite-horizon MDP with a dynamic
programming oracle before making allocation-optimality claims.

### R3. CEGAR-H is feature-oracle dependent

At zero estimator noise, CEGAR-H exactly matches the pointwise oracle in the
current simulator. This is a sanity check, but it also indicates that the
features and action values are constructed in the controller's favor. The
learned/calibrated estimator, held-out split, and calibration metrics are
missing.

### R4. Competitor comparison is not currently commensurate

Official Claude Code, Codex, and OpenCode adapters use different provider/key
contracts. A task-matched run alone would not establish a same-provider
comparison. The protocol must either compare native products with provider
differences disclosed, or use a common model adapter and describe the study as
harness-policy comparison.

### R5. Confidence intervals are not yet external-task intervals

The reported intervals are over seed-level synthetic means. They are useful
for the simulator but cannot be substituted for paired task-level intervals on
Terminal-Bench/SWE-bench/PPTBench.

## Recommendation

**Reject in current form / encourage resubmission after major revision.** The
engineering artifact and theory are promising, but the central real-world
claim is unverified. The paper should narrow its current claim to a formal
invariant plus synthetic evidence until the blocking experiments are complete.

## Required revision route

1. Add the finite-horizon dynamic-programming oracle and calibration-shift
   ablations.
2. Repair the official Linux/Docker dependency path and run a predeclared
   stratified official pilot.
3. Freeze a valid native-vs-native or common-model competitor protocol and
   collect paired task outcomes.
4. Report task-level paired bootstrap intervals, cost/token/latency, and all
   failures; do not report a superiority claim unless the lower confidence
   bound of the paired delta is positive.
5. Add an independent external review after those artifacts exist.

## Post-pilot evidence update (2026-08-10)

The Docker path is now repaired. The same Flash 3-task Terminal-Bench slice
resolved Xiaopu 3/3, Claude Code 2/3, Codex 2/3, and OpenCode 2/3; paired
bootstrap intervals are `[0, 1]` for Xiaopu versus both Claude Code and Codex,
so the superiority claim remains rejected. A genuine one-instance official
SWE-bench Verified Xiaopu pilot also resolved 1/1, but this is not a full
benchmark score. These results close the infrastructure and matched-protocol
gates, but not publication-scale R1/R5. The power plan in
`workspace/results/paired_power_analysis.json` recommends at least 12 paired
tasks under the observed no-loss pattern before the current interval gate can
exclude zero; this is planning evidence, not a substitute for those runs.
