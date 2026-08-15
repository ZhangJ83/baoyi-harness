# Competitor protocol audit

The official Terminal-Bench checkout resolves all three built-in classes:
`ClaudeCodeAgent`, `CodexAgent`, and `OpenCodeAgent`. This is an import and
command-generation check only; no competitor task was run.

## Important comparability finding

The built-in agents do not expose the same provider contract:

- `ClaudeCodeAgent` requires `ANTHROPIC_API_KEY` and runs the Claude CLI.
- `CodexAgent` requires `OPENAI_API_KEY` and runs `codex exec`; its current
  wrapper does not forward `OPENAI_BASE_URL`.
- `OpenCodeAgent` can select `deepseek/...` and forwards a provider-specific
  key, but its CLI configuration is separate from the Xiaopu BaseLLM path.

Therefore the existing `official_matched_protocol.json` is a task/scorer
contract, not yet a valid same-provider comparison. A defensible comparison
needs either (a) each vendor's native endpoint and explicitly reported model
differences, or (b) a common BaseLLM adapter for all systems, in which case it
compares harness policies rather than the native products. Mixing these two
conditions would invalidate a superiority claim.

## Required evidence before comparison

1. Pin task IDs, benchmark commit, container image, attempts, timeout, and
   temperature.
2. Record each system's provider/model and CLI version separately.
3. Persist raw `results.json`, transcripts, token/cost accounting, and failure
   modes for every task.
4. Use paired task-level bootstrap intervals; never treat model calls as
   independent samples.

Current status: classes import successfully, but no matched Claude/Codex run
or superiority claim exists.

## 2026-08-10 evidence update

The Windows newline and provider-forwarding defects were repaired in the pinned
official checkout. A three-task common-DeepSeek Flash slice now exists for all
four systems: Xiaopu 3/3, Claude Code 2/3, Codex 2/3, OpenCode 2/3. The native
result summary verifies identical task IDs and the paired gate reports `[0, 1]`
95% intervals for Xiaopu versus Claude Code and Codex. Thus the comparison is
now reproducible and protocol-audited, but it remains a pilot and does not
support a superiority claim.
