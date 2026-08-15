# Competitor stream observability audit

Local CLI inspection used Claude Code 2.1.224 and Codex CLI 0.146.1. The
representative-schema audit is stored at
`workspace/results/competitor_stream_observability.json`; it is not a live
benchmark trace.

Claude `stream-json` exposes usage-bearing assistant events, so observable
input/output tokens, tool-use blocks, and model-response steps can be counted
without recursively double-counting the final result event. Codex `exec
--json` exposes tool-item events and cumulative usage at `turn.completed`, but
does not expose an equivalent count of internal model-response/provider-call
steps.

Consequently, a strict common token/tool/**step** ledger cannot yet be produced
from both public streams. Treating reasoning items, tool items, or the single
top-level turn as a proxy would change the metric asymmetrically. The protocol
therefore remains fail-closed and `budget_parity_verified=false`.

The next defensible route is to pre-register a vendor-independent observable
contract (for example token, external tool-start, and wall-time caps) and rerun
all systems under it, or obtain an authoritative Codex event that exposes the
missing step counter. This finding is protocol-design evidence, not performance
or superiority evidence.

That route is now materialized prospectively as v3. Both official CLI
documentation sets expose blocking `PreToolUse` decisions for covered local
tools, so `agent/tool_budget_hook.py` provides one shared pre-execution counter.
`agent/generation_budget_proxy.py` reserves and rewrites provider-specific
maximum output fields before forwarding, then commits authoritative response
usage. Offline unit and fake-upstream tests pass; authenticated live CLI smoke
tests remain pending. Hosted/specialized tool paths are disabled because the
Codex documentation explicitly notes that some paths can bypass hooks.

The two CLIs share the hook JSON semantics. Claude Code loads the block from
`~/.claude/settings.json`; Codex 0.146.1 source tests establish that it loads
`~/.codex/hooks.json` and merges it with optional TOML hooks, so the comparator
uses the same JSON block there and explicitly enables the Codex hooks feature.
The all-tools matcher is the valid regular expression `.*`, not the invalid
bare `*` pattern.
