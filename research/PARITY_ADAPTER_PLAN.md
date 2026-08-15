# Observable-budget comparator adapter plan

## Selected idea

Replace the unmetered stock Claude Code and Codex Terminal-Bench launchers with
workspace-owned wrappers that consume each CLI's JSON event stream, enforce a
common wall/tool/token contract, and emit the same ledger schema as Xiaopu.
This is an infrastructure experiment: it can make a future comparison valid,
but does not itself provide comparative performance evidence.

## Run contract

- Run ID: `parity-adapter-20260811`
- Tier: auxiliary/dev
- Baseline: pinned Terminal-Bench installed adapters at commit `d28711d`
- Research question: can all three systems expose auditable observable budget
  fields without relying on vendor-internal reasoning traces?
- Null: one or both competitor streams cannot be normalized fail-closed.
- Alternative: representative Claude and Codex streams produce deterministic,
  cap-checked ledgers and malformed/ambiguous streams are rejected.
- Primary acceptance keys: token totals, tool calls, model steps, wall time,
  cap metadata, `within_budget`, and explicit parse errors.
- Fixed claim boundary: passing parser tests is readiness evidence only.
- Stop condition: focused tests and full regression pass, or a CLI event lacks
  enough observable information for a defensible common metric.
- Outputs: parser/supervisor code, fixtures, tests, protocol update, evidence
  note, refreshed objective and archive audits.

## Execution path

1. Normalize representative Claude `stream-json` and Codex `--json` events.
2. Count only schema-specific events to avoid recursive double-counting.
3. Fail closed on malformed JSON, missing final usage, negative counters, or
   cap overshoot.
4. Add subprocess supervision only after offline normalization is verified.
5. Keep `budget_parity_verified=false` until a live matched run emits complete
   ledgers for every task-system pair.

## Revision log

- 2026-08-11: created after hard-linking parity to the superiority gate.
