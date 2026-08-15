# 2026-08-11 06:00 CST deadline status

## Submission-safe outcome

The repository contains a working PPT generation/edit/layout harness, rendered
and pixel-audited evidence for a controlled four-slide demo, a frozen research
protocol, claim/evidence integrity checks, and a prospective fairness layer for
Xiaopu, Claude Code, and Codex. The package is suitable for an engineering
demo, interview walkthrough, and continued research execution.

It is **not** evidence of ICLR Best Paper quality or competitor superiority.
The authoritative objective gate remains `objective_complete=false`.

## Verified before packaging

- Main regression suite: 104 passed, 7 skipped.
- Official Terminal-Bench environment: 14 focused tests passed.
- Evidence consistency: valid; no missing referenced files.
- Claim/evidence map: valid as a path-and-caveat audit.
- Prospective v3 protocol: valid, with exactly 18 frozen tasks.
- Guarded v3 runner: one-task and full-manifest dry-runs pass; a confirmatory
  launch without validated live-smoke evidence is rejected before API use.
- Controlled PPT demo: four rendered PNGs, PDF/montage evidence, deterministic
  structural score 1.0, and stale-evidence rejection.
- Docker and the pinned official benchmark images are available locally.

## Prospective v3 fairness mechanism

The common hard envelope is 4,500 cumulative generated output tokens, 60
covered local PreToolUse calls, and 180 seconds of agent wall time. The
implementation includes a blocking tool-budget hook, a reservation-based
generated-token gateway/proxy, budgeted installed-agent adapters for Claude
Code and Codex, Xiaopu authoritative provider-usage accounting, and a strict
per-task/cross-system parity verifier. Historical v2 pilot outcomes cannot be
pooled with the v3 confirmatory analysis.

## Gates still open at cutoff

1. No provider credential is available in the current process or user profile;
   therefore the live gateway/hook smoke and the 18-task three-system run were
   not executed. The current smoke-validation artifact fails explicitly with
   `missing_results` for all three systems; dry-run manifests are not accepted
   as live evidence.
2. The historical matched comparison has only three tasks, lacks verified
   budget parity, and has confidence intervals crossing zero with McNemar
   p=1.0. No superiority claim is allowed.
3. Full official Terminal-Bench and SWE-bench Verified evidence is absent.
4. The PPT result is a controlled harness demo, not a frozen model-generated
   multi-system blind evaluation.
5. No dated independent external review has been received.

The final objective audit was hardened before packaging: completed synthetic
E8 evidence is tracked separately from the still-false real controller causal
gate; v3 smoke and parity are separate; the PPT gate requires at least 12 paired
tasks across three systems, all 36+ decks rendered, and two-reviewer blind
scoring with agreement; external review requires a dated, SHA-256-pinned
non-author/conflict attestation. These are evidence contracts, not completed
results.

The PPT v2 preparation gate is now achieved: 12 tasks, three systems, 36
expected decks, six from-scratch tasks and six hash-pinned modification inputs
are frozen, with common rendering and mandatory two-reviewer blind scoring.
This is protocol readiness only. The model-generated PPT result gate remains
false because no 36-deck raw artifact set or locked review forms exist.

The SWE Verified v2 preparation gate is also achieved: 12 frozen instances
across seven repositories were checked against the complete cached 500-row
official split. Every ID, repository, base commit, problem statement, and test
patch matches, and the pinned official evaluator is present. The multi-instance
result gate remains false: the package contains no new model patches and zero
new score-eligible reports beyond the previously disclosed one-instance pilot.

Final local verification after the post-deadline intervention hardening reports 138 passed
and 7 skipped; compilation and evidence-consistency checks pass. A separate
official-venv diagnostic reported 12 passed and one environment startup failure
in the generation-budget proxy, so it is not represented as a clean official
integration run and does not change any scientific claim.

The frozen bilingual PPT fields were additionally checked at the Unicode code
point level after terminal output displayed mojibake. The source JSON contains
the intended Chinese text; the display problem was terminal decoding only. A
new fail-closed validator test now rejects replacement characters and known
mojibake signatures before any model evaluation can start.

The real controller ablation is now frozen as 12 artifact tasks by four
policies (48 cells), with identical model and budgets, Latin-square order
control, predefined outcomes, authoritative ledgers, and preregistered paired
statistics. Its separate readiness gate passes. Its causal result gate remains
false until the full run and result validation are complete.

The four controller policies are now executable interventions in the Harness,
not labels supplied only to the model. Their runtime implementation and Harness
integration are hash-pinned in the frozen protocol. The 48-cell result
validator independently recomputes artifact success, budget compliance,
paired bootstrap intervals, exact McNemar tests, and matched-success cost
permutation tests; missing cells, policy drift, forged success, budget excess,
or bad artifact hashes fail closed.

The 48-cell launcher is now resumable and refuses protocol/runtime drift on
resume. Provider input and generated-output usage are recorded separately;
missing provider usage fails the authoritative ledger instead of becoming a
zero. The common evaluator was run through desktop PowerPoint and produced a
real PDF, four PNG slides, montage, structural report, and pixel audit. The
smoke deck did not satisfy all frozen task text and is excluded from results;
its only claim is execution-pipeline readiness.

The intervention semantics are now operational rather than prompt labels:
direct, always-verify, and evidence-only share a fixed 25-model-step cap;
CEGAR-H may adapt up to 50 steps under the same generated-output/tool/wall-time
envelope. Always-verify requires fresh structural, PDF/PNG render, and pixel
evidence before another material mutation. Fixed policy instructions are shown
to the model, while runtime guards enforce them independently.

The model-PPT protocol now also has an executable blind-review chain: two
independently randomized public bundles omit system identity, the mapping stays
private, visible system-name leakage fails closed, and review forms cannot be
locked without reviewer identity, non-author, generation-independence, conflict,
completion-time, and score attestations. The result validator recomputes
task-paired confidence intervals, exact permutation tests, and Holm adjustments.
This closes review-procedure ambiguity only; all 36 model decks and both real
locked reviewer forms are still absent, so the result gate remains false.

The model-PPT line now also has a version-pinned, resumable 36-cell launcher
covering Xiaopu, Claude Code 2.1.224, and Codex 0.146.1 under the same model and
generated-output/tool/wall-time envelope. A new speaker-notes mutator makes the
frozen `[Sources]` contract executable. The result validator independently
reopens PPTX and PNG artifacts to recompute structure, text, font, notes, and
blank-render checks instead of trusting self-reported JSON. A real PowerPoint
PDF/PNG smoke and the 36-cell dry-run pass; these are execution-readiness
evidence only, not model results.

## Exact continuation step

Inject an authorized provider credential into the evaluation process, run one
discardable live smoke per adapter to set the two v3 live-smoke readiness flags,
then execute the frozen 18-task manifest without modifying the protocol. Feed
the resulting per-task ledgers to `benchmarks/verify_budget_parity_v3.py` before
computing paired confidence intervals or significance tests. Any failed parity
check invalidates the corresponding trial rather than being waived.

`benchmarks/run_matched_protocol_v3.ps1 -DryRun -Smoke` validates the frozen
task set and emits the exact three adapter commands without using a credential.
With a credential in the current process, add `-AcknowledgeNonScoredSmoke` and
remove `-DryRun` for the discardable live smoke. The runner then validates all
three per-task ledgers into `matched_v3_live_smoke_validation.json`. The same
entry point refuses a confirmatory run unless that persistent smoke evidence is
valid and a credential is also present at launch; no transient credential flag
is written back into the preregistered protocol.

## Claim boundary

Safe claim: the harness and prospective measurement infrastructure are
implemented and tested, and the package transparently identifies what remains.

Unsafe claim: the system beats Claude Code or Codex, completes benchmark-scale
evaluation, or has reached ICLR Best Paper evidence quality.
