# Next evidence plan toward a publication-scale claim

This plan preserves the current fail-closed claim boundary. It is ordered by
information gain and dependency, not by presentation polish.

| Priority | Evidence slice | Minimum design | Success / promotion rule | Current blocker |
|---|---|---|---|---|
| P0 | Valid matched harness comparison | Exactly 18 frozen task IDs, same model/provider, 4,500 generated tokens, 60 covered local tools, 180 seconds, one attempt, paired outcomes | First pass three-system non-scored live smoke; then report parity, task-level delta, bootstrap CI, exact McNemar test, cost and latency; no superiority unless every gate passes | Provider credential in the launch process; adapters and dry-run are complete |
| P1 | Real-task controller ablation | Execute the frozen 12-task × 4-policy / 48-cell Latin-square protocol with fixed model and budget | Report paired resolution, verification count, tokens, wall-clock, failure modes, bootstrap CI, McNemar and conditional cost test; protocol readiness cannot satisfy causality | Authenticated run plus campaign-capable execution surface |
| P2 | Model-generated PPT slice | At least 12 frozen paired prompts and sources across Xiaopu/Claude/Codex; render all 36+ decks | Blind structural + semantic + visual rubric from at least two reviewers, inter-rater agreement, full artifact traces; controlled demo remains separate | Model credential and two independent reviewers |
| P3 | Multi-instance SWE check | Frozen 12 official instances across 7 repositories; at least 10 score-eligible reports before non-pilot wording | Protocol metadata/evaluator are validated; next require genuine patches, official test outcomes, token/latency ledger | Model execution and Docker evaluation time; data/protocol are ready |
| P4 | Independent review | Send manuscript plus evidence manifest to a reviewer with no implementation role | Dated report plus hash-pinned non-author/conflict attestation | External reviewer access |

## Stop conditions

- Any infrastructure-invalid trial is excluded from the denominator and triggers
  protocol repair before new model calls.
- A missing budget ledger blocks competitor claims even if task outcomes exist.
- A failed minimum-n or confidence gate downgrades the wording; it does not
  motivate selective task removal.
- PPT pixel checks remain reliability gates, never substitutes for semantic or
  aesthetic human/vision assessment.

The machine-readable objective gate remains authoritative until every required
row is closed.
