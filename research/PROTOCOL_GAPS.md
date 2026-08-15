# Matched-protocol audit

The pinned Terminal-Bench Claude Code and Codex adapters launch vendor CLIs
with unbounded command timeouts.  They expose model and endpoint selection, but
do not expose the same `max_total_tokens`, `max_output_tokens`,
`max_tool_calls`, or `max_steps` controls that Xiaopu accepts.

Therefore the current three-task comparison is a pilot only.  The result files
are useful for debugging, but they cannot support a causal superiority claim.
The protocol gate now requires `budget_parity_verified: true` in
`benchmarks/official_matched_protocol.json` before it reports matched
protocol completion.

## Required completion path

1. Pin a provider gateway (or equivalent adapter) that records request usage
   and rejects calls after the shared token budget.
2. Add a common wall-clock deadline and record terminal tool events for every
   system.
3. Define the same observable tool-event budget for all systems; do not infer
   vendor-internal reasoning tokens from terminal transcripts.
4. Run the preregistered 18-task slice in
   `research/matched_terminal_slice_v1.json` with one attempt and identical
   scorer settings.
5. Store the gateway ledger, raw results, infrastructure classifications, and
   exact paired statistics beside the run manifest.

The prospective v3 contract and its anti-HARKing boundary are now recorded in
`benchmarks/matched_protocol_v3.json` and
`research/MATCHED_PROTOCOL_V3_DECISION.json`. A shared blocking `PreToolUse`
counter and cumulative generated-token proxy have offline tests, including a
local fake-upstream HTTP round trip. They are readiness mechanisms only: live
CLI/container smoke tests and a current-process credential are still false,
and v2 outcomes cannot be pooled into v3 statistics.

Xiaopu now writes an observable `budget_ledger.json` for official terminal
trials.  The ledger is intentionally limited to provider input/output tokens,
terminal command events, and agent turns; it does not claim access to hidden
vendor reasoning tokens.  Competitor adapters must emit the same artifact
before `budget_parity_verified` can be enabled.

Until these artifacts exist, the correct claim boundary is exploratory pilot,
regardless of the raw accuracy difference.
