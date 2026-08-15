# Failure-path budget ledger completeness

## Problem

Terminal-Bench results could contain null token totals when the adapter exited
through fatal parse, provider, or tmux exceptions. Those paths bypassed the
normal ledger serialization and `AgentResult` token fields.

## Fix

`XiaopuTerminalAgent.perform_task` now uses one `finish` path that:

- returns observable input and output token totals for every exit;
- writes `budget_ledger.json` and `xiaopu_commands.json` when logging is enabled;
- tags the ledger with the terminal failure mode;
- counts prompt input before the provider call and output immediately after;
- converts provider and tmux exceptions into explicit failure results.

## Verification

The official Terminal-Bench virtual environment reports seven focused adapter
tests passing. New tests cover fatal parse repair failure and provider failure,
including ledger-file existence and exact token totals.

Historical trials with null ledgers cannot be reconstructed. The fix applies to
future trials and improves failure attribution; it does not itself establish
controller efficacy.
