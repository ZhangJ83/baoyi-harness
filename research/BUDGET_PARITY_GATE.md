# Strict matched-budget parity gate

The comparison gate now validates three layers:

1. per-task integrity: result tokens equal ledger tokens; tool calls, steps,
   declared caps, within-budget flag, and agent wall time are present and valid;
2. per-system integrity: no duplicate tasks and every task remains within all
   fixed caps;
3. cross-system integrity: identical task-ID sets across every comparator.

Missing values are never interpreted as zero. Any mismatch makes the affected
system ineligible and keeps the overall parity gate false.

Applied to the existing Xiaopu, Claude Code, and Codex three-task pilot, task
sets match but all nine task-system pairs lack a budget ledger. Therefore all
three systems are ineligible and the historical pilot cannot support a fair-
budget superiority claim. The canonical report is
`workspace/results/budget_parity_current.json`.

Future comparator adapters must emit the same observable ledger schema. The
gate does not claim access to vendor-internal reasoning tokens.

The scientific claim gate is now hard-linked to this report. Even if paired
bootstrap and exact McNemar tests pass, `superiority_supported` remains false
unless the parity report is verified, every system is eligible, and its task
IDs exactly match the result files. The current fail-closed output is
`workspace/results/claims_gate_current.json`.
