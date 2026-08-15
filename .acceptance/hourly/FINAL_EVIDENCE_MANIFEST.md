# One-hour general harness MVP evidence manifest

## Outcome

- General action transaction: permission scope, cancellation, checkpoint,
  deterministic postcondition, commit, rollback, and best-effort events.
- General file adapter: `apply_edits` now commits atomically across files.
- PPT capability pack: canonical local mutations use scoped transactions and
  emit immutability certificates without adding model-visible tools.
- Recording is optional (`minimal`, `audit`, `research`) and cannot decide
  task success.

## Verification

- Focused harness regression: `135 passed`.
- CLI/TUI regression: `18 passed, 6 skipped`.
- One-command acceptance: `8/8 passed`; see `final/acceptance.json`.
- Full tests: `259 passed, 7 skipped, 5 failed`.
  - Four failures are frozen research-runtime hash mismatches after legitimate
    source changes.
  - One failure is the missing `claude_code` executable in this environment.
  - Frozen protocol hashes were deliberately not rewritten.

## New real PPT transaction smokes

Evidence: `transaction-smoke/evidence.json`.

1. Aircraft slide 2
   - Added the required peer bullet.
   - Render inspection found a real image/text collision missed by structural
     verification.
   - One bounded layout repair reduced overlap from `23.041 in²` to `0`.
   - Artifact-tool full-deck overflow check passed.
   - All three scoped mutation certificates passed; the other 18 slides were
     unchanged and the benchmark source hash stayed unchanged.
2. Pre-Colonial slide 1
   - Changed the target title runs to 48pt.
   - Only slide 1 changed and the source hash stayed unchanged.
   - Source and output report the same historical overflow-warning slides, so
     this is baseline-delta evidence, not a claim that the source deck is clean.

## Honest boundary

This is a competitive, extensible MVP: one general transaction kernel, one
proved non-PPT adapter, and a deep PPT pack. It is not yet a fully mature
Word/Excel/browser/SaaS agent, a crash-durable WAL, or a completed 13-task
paired benchmark with blind human review.

The PPT transaction V1 is deliberately limited to canonical local
edit/style/geometry/delete-shape/reflow operations. Compose, slide
insert/delete/reorder, legacy primitives, and shell side effects are not yet
inside this envelope; cancellation of older long-running tools remains
cooperative at their next check/return boundary.
