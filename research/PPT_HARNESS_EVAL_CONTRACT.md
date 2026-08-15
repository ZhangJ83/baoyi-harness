# PPT harness evaluation contract

## Research questions

1. Does mutation-scoped evidence prevent false completion after a deck is edited?
2. Does the reconstructed render-feedback loop reduce structural and rendered-pixel failures compared with save-only and structural-only loops?
3. Can the same harness support creation, text modification, geometry/layout repair, slide deletion, and slide reordering without bypassing verification?

## Frozen systems

- `save_only`: create or edit and save.
- `structural_only`: save plus `ppt_verify`.
- `render_feedback`: save, structural verification, rendering, rendered-pixel audit, targeted repair, and re-verification.

## Primary metrics

- task success under deterministic task requirements;
- false completion after a post-verification mutation;
- structural overflow/boundary/overlap findings;
- blank-render and edge-content findings;
- tool calls, turns, wall-clock, and verifier calls.

## Evidence tiers

- unit/regression tests establish tool and invariant behavior;
- deterministic fixtures establish scorer behavior;
- model-generated decks establish agent-loop behavior;
- blinded human or vision review is required for aesthetic claims.

Deterministic pixel checks must never be reported as semantic visual quality.

## Promotion gate

A claim is paper-facing only when raw artifacts, task manifests, common budgets, task-level outcomes, and current-epoch evidence are persisted. Small smoke tests remain prototype evidence.

## Frozen model-evaluation v2

`benchmarks/pptbench_model_eval_v2.json` supersedes the five-fixture v1 manifest
for model evaluation. It freezes 12 tasks across Xiaopu, Claude Code and Codex:
six from-scratch tasks and six modification/repair tasks whose input deck hashes
are pinned. The expected result is 36 model-generated decks, each rendered by
the same renderer and accompanied by PDF, slide PNGs, montage, structural report
and pixel audit. Two blinded reviewers use the mandatory anchored rubric in
`benchmarks/pptbench_review_rubric.md`; adjudication is excluded from the
primary analysis.

`benchmarks/prepare_pptbench_blind_review.py` creates a separate, independently
randomized public bundle for each reviewer and a private system-to-anonymous-ID
mapping. Public bundles contain no system field and fail closed when visible
slide text contains a system identity marker. Review drafts are accepted only
after `benchmarks/lock_pptbench_review_form.py` verifies reviewer identity,
non-authorship, independence from generation, declared conflicts, complete
integer scores, and completion time. The locked forms are immutable inputs to
the result validator. Primary system contrasts use the task as the paired unit,
with paired bootstrap intervals, exact paired permutation tests, and Holm
correction across the two Xiaopu contrasts.

The single live entry point is `benchmarks/run_pptbench_model_eval_v2.py`. It
freezes Claude Code 2.1.224 and Codex 0.146.1, creates exactly 36 resumable
cells, enforces the shared generated-output/tool/wall-time envelope, renders
through the same PowerPoint path, and creates review bundles only after every
cell passes the artifact contract. `benchmarks/validate_model_generated_ppt_eval.py`
does not trust the cell reports: it independently reopens each PPTX and
recomputes slide bounds, required text, placeholders, overlap, overflow, font
minimums, `[Sources]` notes, PNG count, and blank-render checks.

`workspace/results/pptbench_model_eval_v2_validation.json` and
`workspace/results/pptbench_model_eval_v2_execution_readiness.json` prove only
that the protocol, local assets, 36-cell schedule, runtimes, and real renderer
smoke are ready. They are not model-generation or human-review evidence and
cannot satisfy the result gate.
