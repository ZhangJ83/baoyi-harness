# Research state audit

Date: 2026-08-09

## Classification

- State: `baseline_partial`, `analysis_ready`, `paper_missing`.
- Engineering baseline: **usable with verification**. The harness is executable,
  packaged, and covered by deterministic tests, but has no external benchmark score.
- PPT artifact: **trusted for renderability**, not for general aesthetic superiority.
- Existing theory: **reference only**. It correctly rejects several invalid claims,
  but it is not itself a novel theory or experimentally supported contribution.
- Competitive analysis: **usable with provenance caveats**. Codex/OpenCode sources
  are direct; Claude Code/Cursor conclusions include explicitly marked inference.
- Superiority claim: **untrusted / unsupported**. No controlled Terminal-Bench or
  SWE-bench Verified comparison exists.

## Reusable assets

1. Provider-neutral tool loop and benchmark adapter.
2. Permission, path, timeout, retry, compaction, tool-schema, and secret-isolation tests.
3. Real PowerPoint rendering loop and semantic slide primitives.
4. Evaluation contract that forbids cross-version or cross-budget score comparisons.

## Trust gaps that change the research route

1. Typed epoch-scoped evidence and a stale-evidence regression now exist; broader
   verifier provenance and scorer integration remain unimplemented.
2. A deterministic adaptive controller and synthetic mechanism checks now exist;
   calibration-shift and dynamic-oracle experiments remain unimplemented.
3. Context compression has no operational definition of sufficiency and no counterexample suite.
4. The mechanism-level simulator covers heterogeneous and homogeneous controls, but
   does not yet isolate calibration shift, oracle regret, compaction, or verifier ordering.
5. No external task results, confidence intervals, cost curves, or same-model baselines.

## Route decision

Next anchor: `idea`, followed by a bounded `experiment`.

The paper line will not claim a universally optimal harness. It will test whether an
**Evidence-Gated Adaptive Deliberation (EGAD)** controller improves the success-cost-risk
Pareto frontier relative to fixed ReAct, fixed planning, and always-search policies.
