# Half-hour generic-agent minimum completion pass

## Selected idea

Complete the smallest reusable Xiaopu harness that a user can benchmark
without adding another agent loop: every ordinary text mutation uses the
existing ActionTransaction, execution leaves a recoverable journal, and every
run can be checked against one stable evidence-bundle contract. PPT remains
the first deep domain pack rather than leaking PPT rules into the generic core.

## Fixed contract

- Time box: one focused half-hour implementation pass.
- Preserve current model-visible tools and benchmark scoring definitions.
- No Word/Excel object model in this pass; those remain future domain packs.
- Migrate `write_file`, `edit_file`, and `apply_edits` to one file-transaction
  path; shell/Python remain explicit non-atomic escape hatches.
- Add a minimal crash journal that reports incomplete transactions without
  pretending it can automatically recover arbitrary external side effects.
- Provide one command that validates a benchmark run bundle and explains every
  missing artifact.
- Keep benchmark inputs and frozen research protocols read-only.

## Acceptance

1. File create/overwrite/edit/multi-edit success and rollback tests pass.
2. Path escape and cancellation produce zero committed file effects.
3. Transaction journal atomically records terminal state and can list stale
   incomplete entries.
4. Benchmark bundle validator accepts a valid fixture and rejects incomplete,
   corrupt, path-escaping, or unredacted bundles.
5. Existing focused harness/PPT/CLI regression remains green.
6. README contains the exact commands the user should run for their benchmark.

## Honest boundary

This pass produces a benchmark-ready general local-agent MVP, not a claim of
full Word/Excel/browser/SaaS coverage, crash-safe recovery of shell commands,
or benchmark superiority before the user executes the frozen evaluation.
