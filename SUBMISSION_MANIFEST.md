# Xiaopu PPT harness submission manifest

## Start here

1. `docs/competitive-harness-ppt.md` — Claude Code, Cursor, and Codex mechanism study; facts and inference are separated.
2. `research/PPT_HARNESS_FINAL_REPORT.md` — implemented architecture, verified results, limitations, and reproduction.
3. `docs/interview-story-v2.md` — one-minute and step-by-step interview narrative.
4. `research/PPT_HARNESS_EVAL_CONTRACT.md` — frozen evaluation questions, baselines, metrics, and promotion gate.
5. `research/BEST_PAPER_GAP_MATRIX.md` — strict requirement-by-requirement audit and closure plan.

## Implementation

The paper draft also has a static QA record at
`research/PAPER_STATIC_QA.md`.

The first authorized external slice and its infrastructure/agent separation
are documented in `research/FAILURE_ANALYSIS_20260811.md`.
`benchmarks/terminal_bench_preflight.ps1` records whether the official images
are cached before spending provider tokens.

- `agent/harness.py` — provider-neutral tool loop, budgets, compaction, hooks, and completion checks.
- `agent/state.py` — task, mutation epoch, and evidence state.
- `agent/tools/ppt_tools.py` — PPT create/edit/layout/render/verify tools.
- `agent/tools/registry.py` — tool schemas, validation, routing, and centralized PPT mutation tracking.
- `agent/builtin_skills/powerpoint/SKILL.md` — office-document workflow.

## Verification

- `tests/test_ppt.py` — creation, modification, layout, evidence invalidation, and pixel-audit tests.
- `tests/test_ppt_score.py` and `tests/test_evidence_validator.py` — scoring and evidence gates.
- `experiments/ppt_harness_demo.py` — reproducible end-to-end demonstration.
- `workspace/results/ppt_harness_demo/ppt-harness-demo.pptx` — four-slide output artifact.
- `workspace/results/ppt_harness_demo/demo-report.json` — tool trace and stale-evidence intervention.
- `workspace/results/ppt_harness_demo/final-evidence-report.json` — unified trace, deck hash, PNG count, montage, and rendered audit.
- `benchmarks/completion_audit.py` and `workspace/results/completion_audit_current.json` — machine-readable promotion boundary; controlled rendered demo is tracked separately from full PPTBench.

## Final verified status

Mutation-surface audit: `benchmarks/audit_ppt_mutation_coverage.py` reports 15
registered PPT mutators, each covered by a direct ledger write or the central
dispatch fallback. The report is stored at
`workspace/results/ppt_mutation_coverage.json`.

Claim-evidence audit: `benchmarks/validate_claim_evidence_map.py` reports all
4 paper claims with existing evidence paths and explicit caveats; its result
is `workspace/results/claim_evidence_map_validation.json`.

Integrity manifest: `benchmarks/build_evidence_manifest.py` records SHA-256
digests for the paper draft, claim map, gap matrix, and core evidence outputs;
the current manifest is `workspace/results/evidence_manifest.json`.

Full-objective gate: `workspace/results/objective_gate_current.json` is the
authoritative requirement audit. It currently reports `objective_complete=false`;
infrastructure, ablations, and theory checks pass, while publication-scale
benchmark, PPT, parity, and independent-review requirements remain open.

The archive root contains the source trees (`agent/`, `benchmarks/`,
`docs/`, `experiments/`, `research/`, and `tests/`). Generated evidence is
stored at the archive root under `completion_audit_current.json`,
`evidence_validation_current.json`, and `ppt_harness_demo/` because the
Windows archive command flattens explicitly selected generated paths.

- full lightweight regression: 138 passed, 7 skipped (official Terminal-Bench integration tests require the official host dependency);
- official Terminal-Bench environment: 14 focused adapter/parity tests passed, including authoritative usage accounting, CLI-specific hook installation, and failure-path ledger preservation;
- compile gate: `python -m compileall -q agent benchmarks experiments` passed;
- demo deterministic score: 1.0;
- post-verification edit rejects old evidence: true;
- final demo rendered visual evidence: four PNGs, PDF, montage, and a passing deterministic pixel audit are present;
- SWE Verified v2 readiness: 12 frozen official instances across 7 repositories validated against the 500-row split and pinned evaluator; multi-instance model scoring remains pending;
- real controller readiness: prospective 12-task × 4-policy / 48-cell fixed-budget protocol validated; causal results remain pending;
- controller intervention integrity: four executable policy guards are hash-pinned, and the result validator recomputes success, budgets, paired uncertainty and tests from artifact-backed cells;
- controller execution readiness: resumable 48-cell Latin-square runner, separate provider input/output usage accounting, and a hash-matched real PowerPoint PDF/PNG evaluator smoke pass; provider credential is absent, so live cells remain unrun;
- intervention semantics: fixed 25-step compute for direct/always-verify/evidence-only, adaptive up-to-50 for CEGAR-H under identical output/tool/time caps; always-verify requires fresh structural + render + pixel evidence between material mutations;
- edge-content warnings are informational for intentional full-bleed backgrounds;
- no competitor-superiority or broad aesthetic-quality claim is made.

ICLR alignment audit: `research/ICLR_REVIEW_ALIGNMENT.md` maps the manuscript
to the four core reviewer questions and records required wording and evidence
boundaries.

Rendered visual review: `research/PPT_VISUAL_REVIEW.md` records the direct
inspection of the four-slide montage after the deterministic pixel audit.

Archive verification: `benchmarks/verify_submission_archive.py` checks required
source, research, and flattened evidence paths in the final zip; the latest
result is `workspace/results/submission_archive_verification.json` with
`valid=true`.

Next evidence plan: `research/NEXT_EVIDENCE_PLAN.md` orders the remaining
publication-scale experiments by dependency and information gain.

Continuous goal charter: `research/CONTINUOUS_OPTIMIZATION_GOAL.md` defines the
iteration loop, priority frontier, non-negotiable claim gates, and completion
condition for ongoing Best-Paper-level optimization.

Provider preflight: `benchmarks/provider_preflight.ps1` checks credential
presence, Docker Engine, and pinned image cache before any model-backed run;
the current report is `workspace/results/provider_preflight.json`.

Fresh synthetic ablation: `experiments/paired_synthetic_ablation.py` was
rerun with 20 seeds × 2,000 tasks per seed; output is
`workspace/results/paired_synthetic_ablation_latest.json` and remains
synthetic-only evidence.

Offline real-trace sensitivity: `benchmarks/analyze_budget_sensitivity.py`
compares singleton and aggregate executions of the same three tasks. The
result, `workspace/results/offline_budget_sensitivity_20260811.json`, records a
3/3 to 1/3 regression and missing ledgers on truncated aggregate trials; it is
descriptive offline evidence, not a causal or official score.

Strict budget parity: `benchmarks/verify_budget_parity.py` now checks result-
ledger token agreement, caps, tool/step usage, wall time, duplicates, and
cross-system task-set parity. The current historical pilot correctly fails at
`workspace/results/budget_parity_current.json` because all per-task ledgers are
missing. `benchmarks/claim_gate.py` now consumes that report as a required
input and independently checks eligibility plus exact task-ID alignment; the
current `workspace/results/claims_gate_current.json` therefore rejects a
superiority claim even before the sample-size and significance failures are
considered.

Prospective v3 parity protocol: `benchmarks/matched_protocol_v3.json` freezes
18 confirmatory tasks and a common enforceable envelope of 4,500 generated
tokens, 60 covered local tool calls, and 180 seconds of agent wall time.
Blocking PreToolUse accounting, a generated-token gateway, budgeted Claude
Code/Codex adapters, Xiaopu authoritative usage accounting, and the strict v3
parity verifier are implemented and unit/integration tested. The validation
report at `workspace/results/matched_protocol_v3_validation.json` is valid but
correctly records `ready_for_confirmatory_run=false`: no provider credential is
available in the current process and no live gateway/hook smoke has been run.
Historical v2 pilot outcomes are explicitly excluded from v3 confirmatory
statistics.
`benchmarks/run_matched_protocol_v3.ps1` is the single guarded entry point for
dry-run, non-scored live smoke, and the confirmatory three-system execution.
`benchmarks/validate_v3_live_smoke.py` keeps persistent smoke evidence separate
from the transient launch-time credential check and emits no performance score.

Deadline status: `research/DEADLINE_0600_STATUS.md` is the concise handoff at
the 2026-08-11 06:00 CST cutoff, including completed deliverables, failed gates,
and the exact next executable step.

Objective-gate hardening: synthetic E8 and real controller causality are now
separate checks. V3 live-smoke readiness, completed 18-task parity, PPT blind
evaluation, and independent review each have distinct machine-admissible
contracts. A review packet or deterministic deck cannot satisfy those gates.

PPT model-evaluation preparation: `benchmarks/pptbench_model_eval_v2.json`
freezes 12 tasks, three systems, 36 expected outputs, six hash-pinned input
decks, common budgets, rendering requirements, and mandatory two-reviewer blind
scoring. The protocol validation is green. The blind-review pipeline creates
two independently randomized identity-free bundles, rejects visible system-name
leakage, separates private mappings, and locks only complete reviewer forms with
non-author, generation-independence, and conflict attestations. The result
validator recomputes task-paired intervals, exact permutation tests, and Holm
adjustments. The separate model-evaluation result gate remains false until all
36 raw rendered artifacts and two genuine locked score forms pass
`benchmarks/validate_model_generated_ppt_eval.py`.

PPT execution readiness: `benchmarks/run_pptbench_model_eval_v2.py` produces a
resumable, fixed-budget 36-cell schedule and pins Claude Code 2.1.224 and Codex
0.146.1. The runner and result validator are hash-pinned in the protocol. The
result validator independently reopens every PPTX and recomputes geometry,
required text, font, `[Sources]` speaker-note, and rendered-pixel checks rather
than trusting generated report JSON. The execution-readiness report is green;
provider-backed cells remain unrun because no credential is present.
