# Evaluation contract

## Claims policy

Passing local tests establishes implementation correctness only. It does not
establish that Xiaopu beats Claude Code or Codex. A superiority claim requires
the same model, task split, container images, time/token budget, retry policy,
network policy, and scoring version, with confidence intervals and failure logs.

## SWE-bench Verified

- Use the official Verified task IDs and pinned repository environments.
- Primary metric: percentage of instances whose official tests pass.
- Report resolved/attempted, infrastructure failures separately, median cost,
  median wall time, and bootstrap confidence intervals.
- First gate: 10 stratified tasks offline/dry-run where possible; then 25; only
  run the full set when regression and budget gates pass.

## Terminal-Bench

- Pin benchmark version and task containers; never compare scores across changed
  task sets or graders.
- Primary metric: official aggregate task success. Secondary: cost, time,
  unnecessary commands, permission violations, and repeated-error loops.
- Validate shell behavior in Linux containers; Windows-host tests are not a
  substitute for benchmark execution.

## PowerPoint

Use three layers:

1. OOXML validity and reopen test.
2. Structural checks: bounds, overflow proxy, overlap, empty shapes, slide count,
   requested content, and edit preservation.
3. Rendered-slide inspection: clipping, hierarchy, alignment, contrast,
   consistency, information density, and content fidelity.

Maintain a fixed prompt set covering generation, modification of an existing
deck, restyling, dense-content rescue, bilingual typography, and charts/tables.
Use blinded pairwise review plus deterministic checks; report disagreements.

## Low-budget DeepSeek gate

Do not call the API until all unit/integration tests pass and the exact prompt is
frozen. Then run one short tool-use smoke task with a strict 0.10 USD harness
budget, inspect its transcript, fix deterministic issues, and only then sample a
small benchmark subset. Keys must come from environment variables and must never
appear in fixtures, reports, command history, or committed files.
# Current execution note (2026-08-10, updated)

Implementation regression now passes **41/41** tests when pytest is run with
the explicit writable basetemp `workspace/pytest-tmp`. The suite includes core,
harness, PPT, benchmark diagnostics, official-sample verification, and the
repeated-identical-action circuit breaker.

PPT regression produced a six-slide representative deck at
`workspace/results/ppt_regression/ppt_regression.pptx`; OOXML reopen and
structural verification passed. Native Windows rendering was attempted but the
host PowerPoint COM session is unavailable; LibreOffice is not installed, so
PNG visual evidence remains an environment-gated item.

The controlled provider pilot reached DeepSeek successfully for one SWE-style
task (11 tool calls, 23,915 tokens) and stopped at the configured budget. It is
connectivity/loop evidence only, not a benchmark score.

The mini-suite entry point was previously exercised for all three suites with five tasks
each. The adapter reached the provider boundary but returned
`APIConnectionError` before any tool call or token usage, so these runs are
availability diagnostics rather than benchmark scores. Raw records are kept
under `workspace/results/{terminal_current,swe_current,ppt_current}.json`.

The five deliberation invariants were also executed directly without pytest
and passed 5/5; the remaining pytest issue is local dependency permissions,
not a failed invariant.

Security audit (2026-08-09): source, benchmark, research, documentation, and
test trees contain no key-like `sk-...` strings; the benchmark entry points and
official verifier also pass Python compilation checks.

Doctor status: core Python/PPT dependencies and workspace permissions pass;
provider credentials are intentionally absent, and LibreOffice is not installed
on the host. The Docker Desktop CLI is present but its engine pipes currently
return permission denied; official container evaluators remain pending until
the elevated repair script restores `docker info`. The latter only disables the
optional native rendering path; the PPT structural checks remain available.
