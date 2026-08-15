# Xiaopu Harness

## Evidence-aware PowerPoint workflow

Xiaopu includes stateful PowerPoint tools for creation, existing-deck inspection,
text and geometry edits, slide/shape deletion, reordering, structural verification,
rendering, and deterministic rendered-pixel checks. Every mutation increments an
evidence epoch, so a verifier result from before the latest deck edit cannot be
used as fresh completion evidence.

The competitive design study, final implementation report, and interview story
are in `docs/competitive-harness-ppt.md`, `research/PPT_HARNESS_FINAL_REPORT.md`,
and `docs/interview-story-v2.md`.

Xiaopu is a provider-neutral coding and PowerPoint agent harness. It combines a
tool loop, workspace confinement, command permissions, structured task state,
bounded retries, context compaction, parallel read-only tools, and a PPT
inspect/edit/verify workflow.

Current verified capabilities include runtime tool-schema validation, atomic
multi-file edits, project-instruction discovery, progressive skill/tool loading,
pre/post tool hooks, token/tool budgets, secret-redacted benchmark logs, and a
real PowerPoint-to-PNG render path on Windows.

## Quick start

```powershell
python -m pip install -e .
$env:OPENAI_API_KEY = "..."
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:OPENAI_MODEL = "deepseek-v4-flash"
xiaopu "inspect this repository, fix the failing tests, and verify the result"
```

Run `xiaopu-doctor` before any paid API test. It reports provider, endpoint,
dependency and renderer readiness without printing the key value.

For the Anthropic-compatible endpoint, set `PROVIDER=anthropic`,
`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, and the corresponding
key/model environment variables. Never put a real key in `.env.example` or Git.

Shell execution defaults to `ask`, which returns an approval requirement rather
than executing. In an already isolated benchmark container, set
`COMMAND_POLICY=allow`. Destructive and network/package-mutating commands remain
denied or approval-gated.

## PowerPoint workflow

The agent can create decks or load an existing `.pptx`, inspect stable shape IDs,
replace text while preserving primary styling, add editorial and two-column
layouts, save, and run structural checks for overflow, bounds, and text overlap.
When a real renderer is available, visual rendering should be added as the final
verification tier; OOXML geometry checks are deliberately not claimed to equal a
pixel-level review.

The offline demo creates a five-slide deck using cover, KPI, comparison, table,
and process layouts:

```powershell
xiaopu /demo
```

Reference output: `workspace/coffee_demo.pptx` and
`workspace/render_final/montage.png`.

### Native GUI entry

Launch the native window without using the terminal UI:

```powershell
agent-gui --workspace E:\project\agent\xiaopu\workspace
```

The desktop shortcut **小朴 Agent GUI** opens the same window. It reuses the
complete Harness: long-horizon Goal, planning events, Skill routing, code/PPT
tools, transactions, verification, trajectory recording and cancellation are
all retained.

## Container benchmark adapter

Use only inside an isolated benchmark task container; it intentionally enables
ordinary shell and package/network commands while still blocking destructive
commands and external `git push`:

```powershell
xiaopu-bench --workspace C:\task --json "fix the repository and run its tests"
```

The adapter writes a redacted JSONL trace under `.xiaopu/run.jsonl`. A completed
status requires either no file changes or concrete verifier evidence after file
changes. Official Terminal-Bench/SWE-bench claims still require their pinned
containers and graders; the adapter itself is not a benchmark score.

Before scoring a collected run, validate its score-neutral handoff bundle:

```powershell
xiaopu-validate-run C:\path\to\run
```

The validator checks input, output, trajectory/events, tool calls, evaluation,
and manifest presence and readability without computing or changing scores.
See [docs/BENCHMARK_RUN_BUNDLE.md](docs/BENCHMARK_RUN_BUNDLE.md).

For a fresh isolated run, add `--bundle run` to `xiaopu-bench`. Xiaopu writes
the instruction, redacted events, tool calls, run result, and manifest; your
evaluator supplies `output` and `evaluation.json`, then the validator checks
the complete handoff without changing any score.

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m unittest discover -s tests -v
```

The reproducible PowerShell regression entry point also compiles sources and
uses a writable pytest temporary directory:

```powershell
powershell -ExecutionPolicy Bypass -File benchmarks/run_offline_regression.ps1
```

For deterministic PPTBench structural scoring:

```powershell
python benchmarks/ppt_score.py workspace/results/ppt_regression/ppt_regression.pptx --min-slides 6
python benchmarks/score_pptbench.py benchmarks/pptbench_tasks.json workspace/results/pptbench
```

With Docker Desktop running, render a deck through the bundled LibreOffice
image:

```powershell
powershell -ExecutionPolicy Bypass -File benchmarks/render_ppt_docker.ps1 `
  -Deck workspace/results/ppt_regression/ppt_regression.pptx
```

See [docs/theory-audit.md](docs/theory-audit.md) and
[docs/evaluation.md](docs/evaluation.md). The competitor analysis and interview
walkthrough are in [docs/competitive-design.md](docs/competitive-design.md) and
[docs/interview-story.md](docs/interview-story.md).

## Offline evidence

The frozen Astropy execution evidence can be rechecked without a model call:

```powershell
python benchmarks/official_swe_verifier.py --root . --checkout-root workspace/official_swe --limit 5 --out workspace/official_swe/verification5.json
python benchmarks/summarize_swe_container.py workspace/official_swe/run12907/result.json workspace/official_swe/run13033/result.json workspace/official_swe/run13236/result.json workspace/official_swe/run13398/result.json workspace/official_swe/run13453/result.json
python experiments/summarize_cegarh.py --output workspace/results/cegarh_multiseed.json
```

These commands report local execution and mechanism evidence only; they do not
produce official benchmark scores or call DeepSeek.

For a provider-backed smoke test, copy `.env.example` to an untracked `.env`
and fill the key through a secure local mechanism; never commit that file.

Alternatively, run the one-task secure pilot wrapper. It prompts once without
echoing the key, disables retries, caps each response, and writes a fresh result:

```powershell
powershell -ExecutionPolicy Bypass -File benchmarks/run_provider_pilot.ps1
```

To configure DeepSeek once for future PowerShell sessions (the key is stored
in the current Windows user environment, never in the repository), run:

```powershell
powershell -ExecutionPolicy Bypass -File benchmarks/configure_provider.ps1
```

Open a new terminal afterward. Remove the persisted setting with
`benchmarks/configure_provider.ps1 -Clear`.

The mini-suite runner stops after the first provider outage by default to avoid
wasted retries. Use `--continue-on-provider-unavailable` only when a complete
availability probe is intentional.

Benchmark adapter calls also default to `API_RETRIES=0`; set that environment
variable explicitly only for a controlled retry experiment.
# Optional operational recording

Run evidence is an observer, not a prerequisite for task execution. Set
`XIAOPU_RECORD_MODE` to one of:

- `minimal`: lifecycle milestones only; no benchmark trajectory export.
- `audit` (default): compact redacted operational journal and provenance.
- `research`: larger redacted event payloads and trajectory export for studies.

Transaction safety state is separate from these recording modes. Mutations
that opt into `ActionTransaction` can persist an atomic state file under
`.xiaopu/transactions/`. At startup Xiaopu reports records left in `planned` or
`checkpointed` state after a possible crash. The generic layer never attempts
automatic domain recovery: inspect the domain adapter checkpoint before taking
recovery action.

Recorder write failures are isolated and reported through in-memory
`recording_health`; they do not fail the task. Source-preserving working-copy
failures remain fatal because they are part of execution correctness.
