# Compact PPT tool architecture

## Decision

Xiaopu keeps a complete internal PPT executor, but exposes a small semantic
facade to the model. The routing key is:

`artifact mode x lifecycle phase x user intent x required evidence`

The model decides *what the user means*; the harness decides *which tools are
visible, when verification is fresh enough, whether repair is allowed, and
when the run may stop*. This keeps ordinary PPT instructions short and moves
repeated workflow constraints out of the prompt and into executable policy.

## Problem baseline

Before this refactor, the executor contained 29 fine-grained PPT primitives
and phase/profile combinations could expose roughly 17-25 tools at once.
Several tools represented adjacent operations, while save, render, inspection,
repair and stopping were still reinforced through long prompts. Recorded runs
then showed the predictable failure modes: excessive discovery, repeated reads,
choosing a low-level script for a semantic edit, verification of a stale
artifact, and repeated calls after a budget boundary.

The current registry still retains all required executor capabilities (37 PPT
tools in the implementation snapshot), but only eight canonical PPT tools can
become model-visible: seven Direct and one Deferred. The other 29 are Hidden.

## Exposure model

| Exposure | Meaning in Xiaopu | Current PPT tools |
|---|---|---|
| Direct | Small, stable default API; may be further narrowed by phase and intent | `ppt_open`, `ppt_inspect`, `ppt_edit_text`, `ppt_style`, `ppt_compose`, `ppt_save`, `ppt_check` |
| Deferred | Omitted by default and promoted only when the task or a verifier counterexample requires it | `ppt_arrange` |
| Hidden | Registered and dispatchable for compatibility, tests and internal composition, but never advertised to the model | legacy primitives such as `replace_text`, `append_bullet`, `add_table_slide`, `set_shape_geometry`, `render_deck` and `save_deck` |

Deferred is a routing property, not a weaker implementation. For example,
`ppt_arrange` is promoted when layout/overlap/move/resize intent is detected or
when a failed check has opened a bounded repair step.

## Canonical facade

| Tool | Semantic contract | Effect |
|---|---|---|
| `ppt_open` | Open an existing deck without changing the input | Observe |
| `ppt_inspect` | Return a slide summary or editable-shape inventory | Observe |
| `ppt_edit_text` | Replace text or append a peer bullet while preserving style | Mutate |
| `ppt_style` | Change text style or shape fill | Mutate |
| `ppt_compose` | Create a deck/slide or add a typed content structure | Mutate |
| `ppt_arrange` | Move, resize, reorder or delete a specific object | Mutate / repair |
| `ppt_save` | Commit the active deck to the required output path | Commit |
| `ppt_check` | Run structural or full current-revision checks | Verify |

Every facade schema rejects unknown fields. Each public name has one stable
meaning; internal compatibility names do not leak into prompts, logs or policy
decisions as competing choices.

## Stage-specific tool surface

| Lifecycle state | Model-visible PPT surface |
|---|---|
| Intake / understand | `ppt_open`, `ppt_inspect`; workspace discovery/read tools remain available only until ContentIR closes discovery |
| Produce | open/inspect + only the intent-relevant mutation tools + save/check |
| Verify, no counterexample | `ppt_save`, `ppt_check`, and the supplied task evaluator when present |
| Verify, counterexample present | only the relevant semantic repair tools, with `ppt_arrange` promoted, followed by save/check |
| Deliver | `finish` |

`finish` is available as a terminal request, but the final-artifact gate - not
the model - decides whether current-epoch evidence is sufficient to accept it.

## Routing

1. **Artifact mode** - an existing deck begins with open/inspect; a creation
   task promotes compose. The original input remains immutable.
2. **Intent** - deterministic lexical/profile routing selects `text`, `style`,
   `compose`, or `arrange`; multiple intents may be combined without exposing
   unrelated low-level operations.
3. **Lifecycle phase** - observation tools shrink after ContentIR; mutation
   tools disappear during a clean verification phase.
4. **Evidence** - a supplied evaluator is preferred over generic checks;
   structural, rendered and visual evidence is attached to the exact mutation
   epoch it certifies.

The resulting normal path is deliberately short:

`discover once -> inspect target -> semantic mutation -> save -> check -> finish`

Complex creation adds a compact plan; a concrete verifier failure adds at most
one scoped `repair -> save -> re-check` cycle. Broad exploration is not a default
phase.

## Harness-owned lifecycle

The harness owns operations that should not depend on the model remembering a
long instruction:

- task/workspace and official-evaluator discovery;
- ContentIR and source provenance binding;
- mutation epochs, observation-cache invalidation and fresh-evidence checks;
- required-path save and final-artifact selection;
- structural verification, supplied task evaluator, render and visual audit;
- counterexample-scoped repair limits and termination;
- complete tool-call, artifact, check, repair and stop trajectory recording.

This division also prevents a model from satisfying the narrative of a check
without producing the corresponding evidence artifact.

## Alignment with locally inspected Claude Code and Codex sources

The alignment here is with their **general harness/tool architecture**. It is
not a claim that either repository contains this PPT facade or Xiaopu's PPT
verification lifecycle.

Claude Code source evidence:

- `E:\project\agent\claude-code-source\source\src\Tool.ts` ties tools to typed
  schemas, execution context and permission state.
- `E:\project\agent\claude-code-source\source\src\tools.ts` assembles the tool
  pool with presets and feature gates.
- `E:\project\agent\claude-code-source\source\src\utils\toolPool.ts` merges,
  deduplicates, orders and mode-filters the effective pool.
- `E:\project\agent\claude-code-source\source\src\utils\toolSearch.ts` supports
  deferred tool loading/search and accounts for tool-definition context cost.
- `E:\project\agent\claude-code-source\source\src\services\tools\toolOrchestration.ts`
  batches concurrency-safe reads while serializing state-changing calls.

Codex source evidence:

- `E:\project\agent\openai-codex\codex-rs\tools\src\tool_executor.rs` defines a
  shared tool runtime contract and Direct/Deferred/Hidden exposure semantics.
- `E:\project\agent\openai-codex\codex-rs\core\src\tools\registry.rs` keeps
  typed registration, dispatch, hooks and exposure metadata together.
- `E:\project\agent\openai-codex\codex-rs\core\src\tools\spec_plan.rs` builds
  the effective registry and applies step-specific exposure policy.
- `E:\project\agent\openai-codex\codex-rs\core\src\tools\handlers\tool_search.rs`
  retrieves deferred tools from searchable metadata.
- `E:\project\agent\openai-codex\codex-rs\core\src\tools\hook_names.rs` keeps a
  canonical serialized name while treating cross-ecosystem aliases as
  internal matcher compatibility.

Xiaopu adopts those verified separation principles - complete registry, compact
model surface, typed runtime, deferred discovery and canonical identity - then
adds a PPT-specific semantic facade and evidence lifecycle.

## Why trajectory-driven

The design is grounded in the normalized records for 42 benchmark runs (13
Claude Code, 13 Codex, 13 WorkBuddy-DeepSeek and 3 OpenCode). Repeated useful
patterns were targeted inspection, deterministic editing, render/inspection,
scoped repair and task-native evaluation. Repeated failures exposed excessive
discovery, missing or stale verification and non-terminating retries.

Most source trajectories are agent-authored summaries rather than complete raw
telemetry, so they support mechanism selection - not a causal claim that this
refactor already improves benchmark quality. That claim requires a fresh,
frozen Xiaopu evaluation.

## Migration and compatibility

- Legacy tool handlers remain registered so old tests, saved trajectories and
  internal composed operations continue to dispatch.
- Legacy tools are Hidden from new model turns; new prompts and policies use
  canonical facade names only.
- Compatibility is one-way: old calls may reach the current executor, but old
  aliases never replace canonical names in new trajectory records.
- Frozen competitor trajectories and completed benchmark protocols are not
  rewritten by this migration.

## Next capabilities

The next additions should extend the facade only when benchmark failures show
a repeated missing semantic operation:

1. `reflow_slide` inside `ppt_arrange` for overlap/overflow repair;
2. cross-slide merge/compose inside `ppt_compose` for synthesis tasks;
3. transactional batch text/style updates to reduce edit/save/check turns;
4. an explicit visual-counterexample object that identifies slide, shape and
   defect before enabling repair;
5. searchable deferred skills/tools when the non-PPT registry grows enough to
   justify runtime retrieval.

No new public tool should be added merely because a low-level function exists.
Promotion requires repeated trajectory evidence, a distinct semantic contract
and a measurable reduction in failure or execution cost.
