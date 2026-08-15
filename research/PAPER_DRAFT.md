# CEGAR-H: Cost-Risk-Constrained Evidence and Computation Allocation for Agent Harnesses

## Abstract

Agent harnesses for software and office-document tasks must decide not only
what action to take, but also when to inspect, verify, retry, or stop. A fixed
loop either spends computation after the task is already sufficiently
supported or accepts a stale certificate after the workspace has changed. We
present CEGAR-H, an interpretable harness design that couples mutation-scoped
evidence epochs with calibrated marginal-value allocation of computation and
verification. The central invariant is simple: a certificate is admissible
only if it was produced in the current mutation epoch and satisfies the
declared evidence contract. We give bounded plug-in regret statements for
binary and finite-action gates and a correlation-robust all-pass bound that
does not assume verifier independence. A dynamic-programming counterexample
shows why these results do not imply global optimality of a myopic controller.

Our current evaluation is deliberately reported as a pilot. In synthetic
controlled environments, held-out bin calibration reduces ECE from 0.0639 to
0.0250 and Brier score from 0.2440 to 0.2401 (20 seeds; synthetic only). In a
frozen three-task Terminal-Bench pilot using `deepseek-v4-flash`, Xiaopu
resolves 3/3 tasks, while Claude Code, Codex, and OpenCode each resolve 2/3.
The paired bootstrap intervals are [0, 1] and exact two-sided McNemar p=1.0;
therefore this result is exploratory and does not establish superiority. A
separate official SWE-bench Verified run resolves one score-eligible instance,
which is likewise not a benchmark score. The artifact is thus a reproducible
theory-and-engineering pilot, not a state-of-the-art claim.

## 1. Introduction

Modern coding agents expose a loop of language-model calls, tools, tests, and
workspace mutations. The same loop also appears in PPT generation and repair:
inspect the deck, apply a transformation, render, check structure and visual
constraints, then either continue or stop. The difficult decision is a control
decision under uncertainty. A successful test before a mutation is not evidence
for the post-mutation state; a second verification call is useful only when its
expected risk reduction exceeds its cost.

CEGAR-H (Cost-Risk-Constrained Evidence and Computation Allocation for Agent
Harnesses) makes these two facts explicit. It records a monotone mutation epoch,
stores certificates with their provenance, and uses a calibrated estimate of
marginal value to select among acting, checking, repairing, and stopping. The
design is intentionally model-agnostic and can sit below a provider adapter.

This paper makes three bounded contributions:

1. an epoch-scoped evidence contract and admissibility invariant;
2. regret and correlation bounds whose assumptions are explicit, plus a
   counterexample delimiting myopic optimality;
3. an auditable implementation and frozen evaluation protocol for Terminal-
   Bench, SWE-bench Verified, and future PPTBench slices.

The paper does **not** claim that Xiaopu currently beats Claude Code or Codex.
The available external runs are small pilots and the claim gate rejects such a
conclusion.

## 2. Problem formulation

Let the workspace state be (x_t), the evidence ledger be (L_t), and the
mutation epoch be (e_t). A mutation increments (e_t) and invalidates every
certificate whose provenance epoch is smaller than (e_t). A certificate `c = (e, tau, rho)` records the epoch, evidence type `tau`, and provenance `rho` (command, test, render, or verifier trace). A gate may accept only if

\[
  \operatorname{fresh}(c,L_t) \equiv (c.e=e_t) \land
  \operatorname{meets}(c, L_t, \mathcal{C}),
\]

where (mathcal{C}) is the task-specific evidence contract. The contract can
require, for example, a passing test, absence of forbidden output, and a
render inspection after the latest slide mutation.

At each decision point the controller chooses a meta-action (a) from acting,
checking, repairing, escalating, or stopping. The action has cost (k(a)),
changes the evidence distribution, and incurs residual failure risk
(r(a\mid x_t,L_t)). CEGAR-H estimates action value from held-out trajectories
and selects the action with the largest estimated risk reduction per unit
cost, subject to freshness and hard safety caps.

## 3. Harness design

### 3.1 Evidence epochs

The adapter separates observation, mutation, and verification. A mutation is
committed only through the ledger, which increments the epoch and marks prior
certificates stale. Verifiers return structured provenance rather than a bare
boolean. This makes stale-certificate rejection testable and auditable.

### 3.2 Mutation-surface audit

The implementation exposes 15 PPT mutation entry points, including a speaker-
notes primitive needed for source disclosure. A static coverage
audit maps every registered mutator to either a direct ledger write or the
central dispatch fallback, which records a generic `deck:<tool>` change when
the implementation has not already advanced the epoch. The resulting artifact
is `workspace/results/ppt_mutation_coverage.json`. This audits the known tool
surface; it does not prove arbitrary external side effects are observable.

### 3.3 Adaptive computation

The controller maintains a small action table with calibrated success and
failure estimates. It can spend another tool call when the estimated reduction
in residual risk is greater than the configured cost, or stop when the evidence
contract is satisfied. Independent hard caps on total tokens, output tokens,
tool calls, and steps bound runaway behavior. The implementation defaults to
`deepseek-v4-flash` but the controller does not depend on a particular model.

### 3.4 Office-document extension

For PPT tasks, the ledger treats every XML/layout edit as a mutation. Structural
checks (slide count, object bounds, required text, and relationships) and render
checks are separate certificate types. A render certificate is therefore tied
to the exact post-edit epoch. The controlled four-slide demonstration now has
real PDF/PNG output, montage inspection, and a passing rendered-pixel audit;
the larger model-generated PPTBench result remains future evaluation work. A
prospective v2 transfer protocol now freezes 12 tasks across Xiaopu, Claude
Code and Codex, including six hash-pinned modification inputs, 36 expected
decks, common rendering, and mandatory two-reviewer blind scoring. The review
pipeline constructs two independently randomized, identity-free public bundles,
keeps system mappings private, rejects visible system-name leakage, and accepts
only locked forms with non-author, independence, and conflict attestations. The
result validator recomputes task-paired bootstrap intervals, exact paired
permutation tests, and Holm-adjusted comparisons. A resumable, version-pinned
36-cell launcher now enforces the shared model and output/tool/wall-time caps,
and the result validator independently reopens every PPTX and reruns geometry,
font, source-notes, required-text, and rendered-pixel checks rather than trusting
self-reported JSON. Its protocol and execution-readiness gate validate, but no
model outputs or review scores exist.

### 3.5 Reconstructing the office-document loop

Our harness study maps three general-purpose competitors to the needs of
editable presentations. Claude Code contributes a typed tool loop with
permissions, hooks, skills, resumable sessions, and compaction. Cursor exposes
context selection, client-side tools, parallel apply, checkpoints, rules, and
MCP. Codex separates repeatable workflow guidance in skills from external
capabilities in MCP-backed plugins. These are documented mechanisms, not claims
about hidden vendor internals.

The office-document gap is that a file write or successful command is not a
presentation result. A reliable PPT workflow must inspect the existing deck,
plan slide roles, mutate stable shapes, verify structural constraints, render
the exact post-edit artifact, inspect the pixels, and repair before stopping.
CEGAR-H therefore treats the deck as a stateful artifact and implements the
following completion contract:

\[
  \text{finish} \Rightarrow
  \text{fresh(structural)} \land \text{fresh(render)}
  \land \text{fresh(pixel-audit)}.
\]

The contract is scoped to the controlled demo and does not claim that a coarse
pixel audit measures aesthetics or storytelling quality.

## 4. Analysis

### Proposition 1 (binary plug-in gate)

If the estimated acceptance probability differs from the true probability by at
most (epsilon) for each binary action, the selected action's expected utility
regret is at most (2epsilon) times the action range. The proof is the usual
two-sided plug-in comparison: each estimate can move the selected and optimal
action by at most (epsilon).

### Proposition 2 (finite-action gate)

For a finite action set with uniformly bounded estimation error (epsilon),
the plug-in argmax has regret at most (2epsilon) times the utility range.
This is a bound on selection error, not a claim of dynamic optimality.

### Proposition 3 (freshness invariant)

Assuming every workspace mutation increments the ledger epoch and every
certificate stores its creation epoch, no certificate created before a
mutation can satisfy `fresh` afterward. The result is purely an admissibility
property; it does not say the verifier is sound or complete.

### Correlated verifiers

For all-pass verification with marginal false-accept probabilities
(alpha_1,\ldots,\alpha_m), the safe upper bound is

\[
 P(\text{all pass incorrectly}) \leq \min_i \alpha_i,
\]

without an independence assumption. Multiplying the marginals would be
invalid for correlated verifiers. Randomized and finite-grid checks in the
artifact found no violations of the declared bounds; they are consistency
checks rather than a formal proof.

### Limitation: myopic allocation

A finite-horizon dynamic-programming construction in the artifact produces a
nonzero greedy-versus-oracle gap. Consequently, CEGAR-H claims bounded local
selection error and stale-evidence safety, not global POMDP optimality.

## 5. Experimental protocol

All external pilot runs freeze provider, model, task IDs, temperature, attempt
count, concurrency, and safety caps. The matched Terminal-Bench pilot uses the
identical three task IDs (`extract-safely`, `fix-permissions`, `hello-world`)
for all systems and computes task-level paired statistics. A separate
prospective v3 manifest freezes exactly 18 tasks but has not been run because
no provider credential is available in the launch process. The SWE pilot uses the
official evaluator on one generated patch for `astropy__astropy-12907`.

Historical v2 budget parity is fail-closed. Its verifier requires result and ledger token
counts to agree, explicit tool/step/cap fields, a within-budget flag, valid
agent wall time, no duplicate tasks, and identical cross-system task sets. The
current three-system pilot has task-set parity but no per-task ledgers for any
system, so every system is ineligible for a fair-budget comparison and
`budget_parity_verified=false`. This parity report is a hard prerequisite of
the claim gate: statistical significance alone cannot set
`superiority_supported=true`, and the parity task IDs must match the evaluated
result files exactly.

An observability audit of Claude Code 2.1.224 and Codex CLI 0.146.1 further
narrows the limitation. Representative public JSON schemas expose Claude
usage-bearing assistant steps, while Codex exposes cumulative turn usage and
tool items but no equivalent internal model-response count. We therefore do
not infer Codex steps from reasoning or tool events. The v2 token/tool/step
pilot therefore remains ineligible and is never pooled with later results.

We therefore register a separate prospective v3 protocol after the pilot,
without pooling v2 outcomes. Its common hard envelope uses cumulative generated
output tokens (4,500), covered local `PreToolUse` calls (60), and agent wall
time (180 seconds); input
tokens, vendor-internal steps, and cost remain reported outcomes. The shared
hook, buffering usage proxy, installed Claude/Codex adapters, Xiaopu
authoritative-usage adapter, and strict cross-system parity verifier pass unit,
fake-upstream, and official-environment integration tests. Both one-task and
full-manifest command dry-runs pass. No authenticated CLI/container smoke or v3
task run has occurred, so this remains infrastructure evidence only.

## 6. Results

### 6.1 Synthetic calibration and controller behavior

Held-out bin calibration on a synthetic 70/30 split improves ECE from 0.0639 to
0.0250 and Brier score from 0.2440 to 0.2401. The result supports a narrow
statement about the synthetic estimator, not real-task calibration or a
deployment cost advantage.

### 6.2 Matched Terminal-Bench pilot

| System | Resolved / 3 | Accuracy |
|---|---:|---:|
| Xiaopu | 3 | 100.0% |
| Claude Code | 2 | 66.7% |
| Codex | 2 | 66.7% |
| OpenCode | 2 | 66.7% |

Xiaopu has one discordant win and no discordant losses against each comparator;
two tasks are ties. The paired bootstrap 95% interval for the delta is [0, 1]
and exact two-sided McNemar p=1.0 for both Claude Code and Codex comparisons.
These numbers demonstrate protocol reproducibility and motivate a larger
slice; they do not establish superiority.

### 6.3 SWE-bench Verified pilot

The official evaluator reports one resolved, score-eligible instance with no
empty patch and no evaluator error. Since the denominator is one, the result is
reported only as an agent pilot and not as a SWE-bench score. For the next
evaluation, we froze 12 official instances spanning seven repositories and
validated every instance ID, repository, base commit, problem statement, and
test patch against the cached 500-row official Verified split. The pinned
official evaluator is present, but no new model patches or multi-instance
scores have been produced; this is protocol readiness, not performance evidence.

### 6.4 Offline real-trace budget sensitivity

Across the same three offline reproduction tasks, singleton runs resolve 3/3,
while a single aggregate run under the shared cap resolves 1/3. The descriptive
resolution-rate difference is -0.667: `extract-safely` and `hello-world`
regress, while `fix-permissions` remains resolved. The two regressed aggregate
trials lack token ledgers after truncation, so this analysis identifies a
budget-allocation sensitivity but cannot attribute the failures precisely to a
controller decision. These offline traces are neither an official benchmark
score nor randomized causal evidence.

### 6.5 Prospective real-controller ablation

We froze a 12-task by four-policy real PPT artifact experiment covering direct,
always-verify, evidence-only, and CEGAR-H. All 48 cells share DeepSeek V4 Flash,
temperature zero, one attempt, 4,500 generated output tokens, 60 covered local
tool calls, and 300 seconds. A four-order Latin square controls execution order.
Direct, always-verify, and evidence-only use the same fixed 25-model-step cap;
CEGAR-H may adaptively use up to 50 steps while remaining under the identical
output-token, tool, and wall-time envelopes. Always-verify requires structural,
PDF/PNG render, and pixel evidence between material mutations; save-only
persistence is not misclassified as a content mutation.
Artifact success, verification count, authoritative usage, wall time, and
failure mode are defined before execution. The protocol is validated, but no
48-cell result exists; therefore it provides no causal evidence yet. The four
interventions are executable Harness policies rather than prompt labels: their
action eligibility and verification-order invariants are enforced at runtime
and hash-pinned by the protocol. A separate validator reconstructs success,
budget compliance, McNemar tests, bootstrap intervals, and conditional cost
tests from all 48 artifact-backed cells; it rejects missing cells, forged
success flags, policy drift, over-budget usage, and artifact hash failures.
The resumable runner materializes the preregistered Latin-square order, isolates
each cell in a subprocess, enforces cumulative provider-reported output tokens,
and records partial results after every cell. A policy-independent evaluator
was exercised with desktop PowerPoint: it produced a PDF, four slide PNGs, a
montage, structural output, and pixel evidence. That smoke deck failed one
task-content requirement and is therefore not counted as a successful task;
it establishes rendering-pipeline readiness only.

After this diagnosis, the Terminal-Bench adapter was changed to finalize its
budget ledger on every return path. Provider, tmux, parse, and budget failures
now preserve input/output token totals and a failure-mode-tagged ledger. The
official dependency environment passes seven focused adapter tests. This fixes
future observability but cannot reconstruct the two historical null ledgers.

## 7. Limitations and broader impact

The current evidence is limited by provider/model dependence, small external
sample sizes, synthetic calibration, incomplete PPT evaluation, and the lack of
independent external review. The cost-risk objective encodes deployment
preferences and should not be treated as a universal utility. Freshness also
depends on complete mutation instrumentation; unobserved side effects can
invalidate the invariant's operational interpretation. The harness can reduce
stale acceptance, but it cannot make an unsound verifier sound.

## 8. Reproducibility and claim boundary

The repository records source commits, task manifests, provider configuration,
result paths, token/tool caps, and the generated claim gate. The PPT demo's
unified trace is `workspace/results/ppt_harness_demo/final-evidence-report.json`.
Running
`benchmarks/validate_evidence.py` checks cross-artifact consistency. The
authoritative objective gate currently reports `objective_complete=false`.
It separately tracks v3 live-smoke readiness, the 18-task parity report,
competitor statistics, real controller causality, multi-instance SWE,
model-generated PPT blind evaluation, and hash-pinned independent review. All
of these remain open; the completed synthetic ablation satisfies none of the
real-controller or external-efficacy gates.

A time-bounded 2026-08-11 sprint reran the 20-seed paired synthetic ablation
and regenerated the deterministic PPT fixture slice. Three fixture classes were
also rendered to PDF/PNG and passed the coarse pixel audit. Provider-backed
runs were stopped before token spend because no credential was present in the
current process. These checks confirm reproducibility of auxiliary paths; they
do not add external efficacy evidence or promote the fixture slice to PPTBench.

## 9. Conclusion

CEGAR-H offers a concrete way to make harness decisions evidence-aware:
certificates are scoped to mutation epochs, verifier risk is bounded without a
false independence assumption, and computation allocation is explicit and
budgeted. The current artifact validates these design claims in theory checks,
synthetic experiments, and reproducible pilots. It intentionally stops short
of a best-paper or state-of-the-art claim. The decisive next step is the
discardable authenticated three-system v3 smoke; only after it passes may the
frozen 18-task matched slice run. Real controller causality, multi-instance SWE,
frozen model-generated PPT evaluation, and independent external review remain
separate required evidence lines.
