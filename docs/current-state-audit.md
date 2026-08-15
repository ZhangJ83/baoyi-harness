# Xiaopu current-state audit

Audit date: 2026-08-10

This file supersedes stale or incorrectly encoded portions of
`docs/completion-audit.md`.

## Evidence update — 2026-08-10

The official Docker engine is operational. Xiaopu's Flash Terminal-Bench
three-task pilot is 3/3, the first genuine official SWE-bench Verified pilot is
1/1, and the common-provider matched slice is Xiaopu 3/3 versus Claude Code,
Codex, and OpenCode at 2/3 each. These are still pilots, not leaderboard
scores; the paired confidence intervals include zero.

The pinned Terminal-Bench runner now forwards provider-specific endpoints,
supports all four systems, and enforces a three-task default API cap. The
official SWE launcher accepts local official-schema JSON/JSONL datasets.

## Verified

- Full local regression currently passes: 44 tests, including the claim-gate,
  repeated-action
  circuit-breaker invariant. Pytest is run with an explicit workspace basetemp
  because the host's default `E:\Temp\pytest-of-zzz` is access-restricted.
- A one-task DeepSeek provider pilot reached the model successfully (11 tool
  calls, 23,915 tokens); it stopped at the configured token budget and made no
  workspace changes. This is connectivity/loop evidence, not a benchmark score.

- Xiaopu v0.2.0 source and distributable wheel exist.
- Provider-neutral OpenAI/Anthropic loop, tools, permissions, hooks, skills,
  budgets, recovery, mutation epochs, and fresh-evidence gates are implemented.
- `xiaopu-pilot:mini` and `xiaopu-ppt-render:mini` exist and Docker reports
  client/server 29.5.3.
- PPT pilot completed model-driven creation, structural checks, Linux render,
  PNG output, and montage inspection.
- Five frozen SWE-bench Verified Astropy samples have matching base commits,
  problem statements, and gold patches. `verification5.json` reports
  `gold_patch_check: true` and `checkout_verified` for all five.
- `benchmarks/official_slice_runner.py` persists exact-commit test output and
  keeps execution status separate from official score eligibility.
- Official Terminal-Bench Flash pilot is persisted at
  `workspace/results/official_tb_xiaopu/xiaopu_flash_20260810/results.json`:
  3/3 resolved. This is a finalized pilot, not a full benchmark score.
- `benchmarks/run_official_matched.ps1` now provides a fixed task/scorer
  protocol for Xiaopu and the official Claude Code/Codex agents.
- `workspace/results/cegarh_calibration_sweep.json` and
  `workspace/results/pptbench_structural_smoke.json` extend the no-API theory
  and PPT evidence; both are explicitly simulator/smoke evidence.
- Pilot summary is persisted in `research/PILOT_SUMMARY.json`.
- Near-line issue reproductions are persisted in `research/NEARLINE_EVIDENCE.json`;
  they are explicitly marked `formal_score_eligible: false`.

## Verified only as prototype evidence

- Terminal-style pilot: 3/5 completed.
- SWE-style pilot: 3/5 completed; these are custom tasks, not official
  SWE-bench scores.
- PPT pilot: 1/1 completed with rendered evidence.
- Theory and competitor analysis are documented, but novelty and superiority
  are not externally established.

## Not achieved

- Full official SWE-bench score over the Verified split (one official
  score-eligible agent pilot exists, but the full split has not run).
- Scorer-backed promotion from raw test execution to an official score.
- Official Terminal-Bench score.
- Full Terminal-Bench and SWE-bench Verified scores.
- Sufficiently powered matched Claude Code/Codex comparison.
- Evidence that Xiaopu beats any competitor.
- ICLR Best Paper or state-of-the-art claim.

## Current next anchor

Improve PPT visual regression coverage and tighten the provider loop's budget
and stopping policy. Keep official benchmark claims separate from local pilots,
and do not spend model/API budget unless a change requires a controlled pilot.
