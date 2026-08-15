# Official Terminal-Bench execution note

The official checkout is pinned to `d28711d` (`0.2.18`). On Windows,
`pathlib.Path("/tmp")` and `Path("/tests")` become backslash paths before they
reach Docker's archive API. The local checkout therefore contains a narrowly
scoped compatibility shim: container-only constants use `PurePosixPath`, while
host filesystem paths remain `Path`.

The shim is outside the Xiaopu package and is recorded here so an official run
can be reproduced. It does not change task prompts, tests, parsers, model
prompts, or scoring.

Completed evidence:

- `workspace/results/official_tb_xiaopu/xiaopu_hello_20260810f/results.json`:
  official `hello-world`, 1/1 resolved.
- `workspace/results/official_tb_xiaopu/xiaopu_tb_easy3_20260810g/results.json`:
  finalized three-task pilot (`fix-permissions`, `hello-world`,
  `extract-safely`), 2/3 resolved (66.67%).
- The corrected fixed-protocol run is
  `workspace/results/official_tb_xiaopu/xiaopu_official_terminal_pilot/results.json`;
  it also resolves 2/3, with the same scorer and task IDs.
- After adding the sensitive-output guard, the fresh run
  `workspace/results/official_tb_xiaopu/xiaopu_guard_20260810/results.json`
  resolves all three pinned tasks (3/3, 100%). This is still a three-task
  pilot, not the full Terminal-Bench leaderboard score.
- The model-corrected flash run
  `workspace/results/official_tb_xiaopu/xiaopu_flash_20260810/results.json`
  also resolves 3/3 (100%); its exact model/provider settings are recorded in
  the adjacent `run_metadata.json`.

These are protocol pilots on a tiny, easy-task subset. They must not be
reported as the full Terminal-Bench score or as a comparison win.

Infrastructure check: the official `oracle` agent resolved all three pinned
tasks (`hello-world`, `fix-permissions`, `extract-safely`) with accuracy 1.0 in
`workspace/results/official_tb_oracle_infra/oracle_infra_20260810/results.json`.
This validates Docker containers and the scorer only; it is not Xiaopu or
competitor performance. The CLI's final Windows progress rendering emitted a
GBK Unicode error after persisting results, so the Xiaopu protocol now forces
`PYTHONUTF8=1`.

For a reproducible fixed-condition run, use
`benchmarks/run_official_matched.ps1`. It runs Xiaopu without persisting a key;
`-IncludeCompetitors` additionally invokes the official Claude Code and Codex
agents only when their native credentials are already present in the session.
Because those native agents use different vendor endpoints, the resulting
files still require the comparability audit and `benchmarks/claim_gate.py`
before any superiority statement.

## Flash matched slice (2026-08-10)

Using the same three task IDs, `n_concurrent=1`, `n_attempts=1`, temperature
0, and `openai/deepseek-v4-flash` (or its Anthropic/OpenCode provider spelling):

- Xiaopu: `3/3` (`workspace/results/official_tb_xiaopu/xiaopu_flash_20260810/results.json`)
- Claude Code: `2/3` (`workspace/results/official_tb_claude/claude_flash_easy3_20260810/results.json`)
- Codex: `2/3` (`workspace/results/official_tb_codex/codex_flash_easy3_20260810/results.json`)
- OpenCode: `2/3` (`workspace/results/official_tb_opencode/opencode_flash_easy3_20260810/results.json`)

The paired gate is now complete but deliberately does not support a
superiority claim: Xiaopu's observed delta is `+0.333` against both Claude
Code and Codex, while the 95% paired bootstrap intervals are `[0, 1]` with
only one discordant task. This is valid pilot evidence, not a statistically
conclusive benchmark victory.

The next power-sized slice is predeclared in
`benchmarks/matched_12_task_manifest.json`. It must be run separately for all
systems; its outcomes must not be merged with the 3-task pilot.

Both official runners now enforce a three-task model-call cap by default.
Expanding the slice requires `-AllowExpandedSlice` plus an explicit token/cost
budget; this prevents accidental DeepSeek spend.
