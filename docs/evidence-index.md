# Xiaopu evidence index

This index separates implementation evidence from benchmark claims.

## Reproducibility

- Editable package installation now reports `xiaopu 0.2.0`, matching
  `pyproject.toml`; installation uses `--no-build-isolation` in this offline
  environment.
- Full local regression: `python -m pytest -q --basetemp workspace/pytest-tmp`
  -> **35 passed**.
- Provider-loop budget control now shrinks each response to the remaining
  allowance and injects a final-verification hint near exhaustion; both OpenAI
  and Anthropic caps are restored after each call.
- One-command offline replay: `powershell -ExecutionPolicy Bypass -File
  benchmarks/run_offline_regression.ps1` (compile + tests, no provider calls).
- Environment-only diagnosis: `python -m agent.doctor --offline` (does not
  require provider credentials).
- Source compilation: `python -m compileall -q agent benchmarks`.
- PPT artifact: `workspace/results/ppt_regression/ppt_regression.pptx`.
- Deterministic PPT scorer: `python benchmarks/ppt_score.py <deck> --min-slides
  N --required-text ...`; the representative deck scores **1.0** on open,
  slide-count, and required-content checks.
- Fixed PPTBench manifest: `benchmarks/pptbench_tasks.json`; batch scoring is
  available via `benchmarks/score_pptbench.py`. Missing artifacts score zero,
  so missing tasks cannot be silently counted as successes. A synthetic local
  baseline now supplies all five artifacts and scores **1.0** on deterministic
  structural checks; this is a scorer smoke test, not an agent or human-quality
  benchmark result.
- Matched comparison protocol: `benchmarks/matched_eval_manifest.json`; it
  fixes model, temperature, budgets, retries, container policy, metrics, and
  explicitly disables superiority/official-score claims until matched runs
  exist.
- Blinded human-review protocol: `benchmarks/pptbench_review_rubric.md`, with
  seven 1–5 dimensions, anonymized labels, two reviewers, disagreement logging,
  and confidence-interval reporting.

## Provider pilot

- `workspace/results/provider_pilot_new.json` records one successful DeepSeek
  interaction: 11 tool calls and 23,915 tokens, stopped at the configured
  budget. It is connectivity/loop evidence, not a benchmark score.
- `workspace/results/provider_pilot_latest.json` records the corrected
  low-cost pilot: `completed`, 2 tool calls, and 1,796 total tokens under
  budget. It is a provider smoke result, not an official SWE-bench score.
- No API key is stored in source, fixtures, or reports.

## Official Terminal-Bench pilot

- The official Terminal-Bench checkout is pinned at `d28711d` (`0.2.18`) and
  runs through its own Docker harness, task parsers, and `results.json` schema.
- `workspace/results/official_tb_xiaopu/xiaopu_hello_20260810f/results.json`
  resolves the official `hello-world` task (1/1, 100%).
- The finalized three-task pilot in
  `workspace/results/official_tb_xiaopu/xiaopu_tb_easy3_20260810g/results.json`
  resolves `fix-permissions` and `hello-world` but not `extract-safely`
  (2/3, 66.67%).
- The fresh post-guard pilot in
  `workspace/results/official_tb_xiaopu/xiaopu_guard_20260810/results.json`
  resolves all three tasks (3/3, 100%); it remains a three-task pilot, not a
  full leaderboard score.
- The adapter and Windows container-path shim are documented in
  `docs/official-terminal-bench-windows.md`. These are official-protocol pilot
  slices, not full leaderboard scores and not evidence of superiority over
  Claude Code or Codex.
- `benchmarks/official_matched_protocol.json` fixes the task IDs, scorer,
  model, temperature, concurrency, attempts, and task-level statistical unit
  for the future Xiaopu/Claude Code/Codex comparison. It intentionally keeps
  superiority and full-score claims disabled until all three systems produce
  finalized results under that contract.
- `research/COMPETITOR_PROTOCOL_AUDIT.md` records a material caveat: the
  built-in Claude Code, Codex, and OpenCode agents use different provider/key
  contracts, so task matching alone is not sufficient for a same-provider
  superiority claim.

## SWE container evidence

- `workspace/official_swe/verification5_rerun.json` verifies five pinned
  Astropy base commits and gold patches.
- `workspace/official_swe/run*/result.json` contains the five local container
  build/test runs; all five builds and test slices passed.
- `score_eligible` is intentionally false: this is not an official
  SWE-bench score.
- The repaired official evaluator path was validated with the gold-patch
  oracle: `astropy__astropy-12907` resolved 1/1 after normalizing Windows
  CRLF to Linux LF in `eval.sh`; see
  `workspace/results/official_swe_verified/oracle_smoke_status_20260810g.json`.
- The official SWE-bench source is pinned at `official_refs/swe-bench` commit
  `cd37836`. Import auditing reaches the official evaluator but currently
  uses a narrow local-only fallback for the optional `modal` path; the local
  Docker scorer remains the official evaluator code path.
- The official loader has been verified against the cached
  `SWE-bench/SWE-bench_Verified` test split: one record,
  `astropy__astropy-12907`, base commit
  `d16bfe05a744909de4b27f5875fe0d4ed41ce607`. Metadata is recorded in
  `workspace/results/official_swe_verified/verified_metadata_smoke.json`.
  This is dataset/evaluator readiness evidence, not an agent score.
- The repeatable no-inference readiness command is
  `python benchmarks/official_swe_readiness.py --out
  workspace/results/official_swe_verified/verified_metadata_smoke.json`.
- An oracle-only official scorer smoke reached Docker base-image construction
  but stopped before tests because Ubuntu apt endpoints were inaccessible or
  returned 403/CA errors. The audit is in
  `workspace/results/official_swe_verified/oracle_smoke_status.json`; no score
  is reported from this attempt.

## PPT limitations

- OOXML reopen and structural checks pass for the representative six-slide
  deck.
- The `xiaopu-ppt-render:mini` Docker image supplied LibreOffice; the deck was
  converted to PDF and six PNGs, then inspected as
  `workspace/results/ppt_regression/rendered/montage.png`. Review notes are in
  `visual_review.json`. This is single-deck visual evidence, not a blinded
  benchmark score.
- The reproducible wrapper is `benchmarks/render_ppt_docker.ps1`; it was
  executed successfully and produced the same six PNGs under
  `rendered_script/`.
- All five fixed PPTBench baseline artifacts were also rendered in batch;
  counts are recorded in `workspace/results/pptbench/render_batch_summary.json`.
  Render success is recorded separately from human/blinded visual quality.

## Claims boundary

No claim that Xiaopu beats Claude Code, Codex, or any official benchmark is
made without matched task sets, scoring versions, budgets, and independent
comparison runs.

## Synthetic ablation evidence

- `research/CEGARH_ABLATION_REPORT.md` and the paired JSON outputs record a
  20-seed, 2,000-task-per-seed synthetic ablation with 95% seed-level
  intervals, a pointwise oracle, and an estimator-shift condition. The result
  is explicitly simulator-only and does not support external benchmark or
  competitor claims.

## ICLR-style skeptical review

- `research/review/review.md` is an evidence-grounded independent audit that
  downgrades current efficacy claims; `research/review/revision_log.md` tracks
  which experimental issues are now addressed and which external blockers remain.
- `research/review/revision_log.md` maps each issue to a required fix.
- `research/review/experiment_todo.md` gives concrete dynamic-oracle,
  calibration, verifier-correlation, and official-pilot experiments.
- `workspace/results/dynamic_oracle_h3.json` is a finite-horizon counterexample
  showing the pointwise greedy policy can be suboptimal; the theory now
  explicitly avoids a multi-step optimality claim.
- `benchmarks/claim_gate.py` emits `workspace/results/claims_gate_current.json`
  and currently refuses a superiority claim because finalized Claude Code and
  Codex result files are absent. Even after files exist, its separate
  `superiority_supported` field requires both paired 95% intervals to exclude
  zero; complete files alone are not treated as a win.
- `benchmarks/paired_stats.py` also records paired wins, losses, and ties, so
  a future comparison exposes the task-level discordance behind each delta.
- `agent/safety.py` and `tests/test_terminal_adapter.py` add a transcript
  safety guard for likely secret/solution-content readers, motivated by the
  official `extract-safely` failure; metadata checks remain allowed.
- `workspace/results/verifier_correlation_sweep.json` records a 200,000-trial
  correlation sweep validating the `min(alpha_i)` bound and showing why the
  independence product cannot be used without an independence assumption.
- `workspace/results/cegarh_calibration_sweep.json` adds a paired 20-seed
  calibration/bias sweep; it quantifies objective regret under estimator
  misspecification and is explicitly not external benchmark evidence.
- `workspace/results/theory_bound_check.json` performs 200,000 randomized
  consistency trials for the binary `epsilon` and multi-action `2 epsilon`
  plug-in bounds; it reports zero violations but is not a proof.
- `workspace/results/exhaustive_theory_check.json` exhaustively checks 27 binary
  and 19,683 three-action finite-grid cases with zero violations. It strengthens
  implementation consistency but is explicitly not a continuous proof.
- `workspace/results/pptbench_structural_smoke.json` is a five-task deterministic
  scorer smoke test generated by `experiments/generate_pptbench_fixtures.py`.
  It validates artifact naming and structural checks only; the fixtures are not
  model-generated decks and therefore do not count as PPTBench performance.
- `workspace/results/official_swe_verified/xiaopu_flash_predictions.json` and
  `xiaopu_flash_prediction_provenance.json` record the first genuine Flash
  agent patch pilot. The official evaluator report
  `xiaopu-deepseek-v4-flash.xiaopu_astropy_12907_flash_20260810.json` resolved
  1/1 with zero errors. This is pilot evidence only, not a full benchmark
  score or superiority claim.
- The matched Flash slice is recorded in
  `docs/official-terminal-bench-windows.md` and
  `workspace/results/claims_gate_current.json`: Xiaopu 3/3, Claude Code 2/3,
  Codex 2/3, and OpenCode 2/3 on identical three-task IDs. The gate allows a
  paired comparison but correctly rejects statistical superiority because the
  bootstrap intervals include zero.
- `workspace/results/paired_power_analysis.json` is a predeclared planning
  analysis: under the observed one-win/no-loss pattern, 12 paired tasks are
  needed before the current bootstrap lower bound becomes positive. It is not
  external benchmark evidence.
- `benchmarks/matched_12_task_manifest.json` freezes the next 12-task stratified
  slice and fixed protocol. It is a preregistration artifact, not a score.
- `benchmarks/validate_task_manifest.py` validates that slice against the pinned
  Terminal-Bench checkout (`d28711d`); current validation is recorded in
  `workspace/results/matched_12_manifest_validation.json`.
- `benchmarks/estimate_slice_budget.py` estimates token-only expansion bounds
  from the Flash pilot. For 12 tasks at a 4x safety multiplier it recommends a
  total cap of 31,344 tokens; it intentionally leaves price unset.
- `benchmarks/validate_evidence.py` checks that achieved audit entries and
  experiment-matrix fields point to existing artifacts. Current report:
  `workspace/results/evidence_consistency_current.json` (valid, no errors).
- The official Terminal-Bench runner defaults to three model-backed tasks and
  requires an explicit expansion switch with a user-specified budget.
- Xiaopu's official adapter now enforces per-task `max_total_tokens`,
  `max_output_tokens`, `max_tool_calls`, and `max_steps`; the matched runner
  passes the manifest defaults explicitly instead of treating them as prose.
- `tests/test_terminal_adapter.py` contains offline behavior checks for token
  and tool-call exhaustion; they are dependency-gated when the official
  Terminal-Bench package is absent from the host environment.
- `benchmarks/summarize_official_matched.py` and
  `workspace/results/official_tb_matched_summary.json` now consume the native
  Terminal-Bench result schema, verify identical task IDs across all four
  systems, and compute task-level paired deltas including OpenCode.
- `benchmarks/paired_stats.py` now reports both percentile bootstrap intervals
  and exact McNemar/sign-test p-values plus discordant-win Wilson intervals;
  the current pilot has exact p=1.0 and remains non-significant.
- `benchmarks/run_official_swe_local.py` and
  `benchmarks/official_swe_readiness.py` support local official-schema
  JSON/JSONL datasets, closing the Windows cache-path reproducibility issue
  without creating additional SWE-bench score evidence.
- `workspace/results/heldout_calibration_metrics.json` reports a 20-seed 70/30
  held-out synthetic calibration check (ECE 0.0639 -> 0.0250; Brier 0.2440 ->
  0.2401). It is still synthetic and not external efficacy evidence.
- `research/review/review.md` is a skeptical baseline review with a post-pilot
  update; an independent post-pilot external review remains open.
- Pilot baseline contracts are durable under
  `baselines/local/official_flash_pilot/` and
  `baselines/local/official_swe_flash_pilot/`. Both are explicitly marked
  pilot-scoped and partially verified rather than promoted to leaderboard
  baselines.
- `research/paper_experiment_matrix.json` and its Markdown companion map each
  paper claim to a concrete experiment, status, metric, promotion rule, and
  next action. E4/E5/E7 remain explicitly open at publication scale.
- `research/PAPER_DRAFT.md` is the current claim-safe ICLR-style draft. It
  reports theory and pilot evidence while explicitly rejecting SOTA/best-paper
  language until the open external evaluations are completed.
- `research/THEORY_APPENDIX.md` gives the proof-facing derivations for binary
  and finite-action regret, freshness, correlated verifiers, and compressed
  state; finite-grid checks remain explicitly labeled as regression evidence.
- `workspace/results/paired_synthetic_ablation.json` adds same-stream paired
  seed-level CIs and exact sign-test p-values for component ablations; it is
  synthetic-only evidence.
- `research/review/EXTERNAL_REVIEW_PACKET.md` is a ready-to-send independent
  review protocol. It is not counted as an external review until a reviewer
  returns a dated report.
- `research/WRITING_PLAN.md`, `research/CLAIM_EVIDENCE_MAP.json`,
  `research/FIGURE_STORYBOARD.md`, and `research/REVIEWER_FIRST_PASS.md` are
  the durable writing contract, claim map, figure plan, and local skeptical
  review for that draft.
- `workspace/results/pptbench_structural_smoke_latest.json` records five
  deterministic fixture checks, now including a geometry `no_overflow`
  invariant. It is explicitly structural smoke evidence, not model-generated
  PPTBench performance.
- The current completion audit counts 241 pinned Terminal-Bench task
  directories. The Xiaopu pilot covers 3/241 (1.245%); the SWE evidence is
  1 official instance, with a five-instance local metadata sample. These
  coverage figures are audit metadata, not benchmark scores.
- `benchmarks/claim_gate.py` now separates protocol comparability from a
  superiority claim: the latter requires paired bootstrap lower CI > 0,
  exact McNemar `p < 0.05`, and at least 18 paired tasks. The current 3-task
  pilot fails all relevant superiority gates and remains exploratory.
- `benchmarks/diagnose_docker_desktop.ps1` records the current identity,
  Docker contexts, process count, service state, and named-pipe probe without
  touching credentials. The current Codex sandbox identity receives
  `Access denied` and sees `com.docker.service=Stopped`; this is an external
  Windows-account/privilege blocker for official container runs.
- `workspace/results/full_objective_gate_current.json` is the strict
  requirement-by-requirement gate. It currently marks matched protocol,
  component ablations, and theory checks as achieved, while correctly leaving
  full benchmark scores, superiority statistics, model-generated PPT, and
  external review open.

## Security check

The current `agent`, `benchmarks`, `docs`, `research`, and `tests` trees contain
zero key-like `sk-...` strings. Provider credentials remain environment-only.
