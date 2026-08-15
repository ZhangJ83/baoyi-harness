# Xiaopu CEGAR-H Native Artifact Runtime implementation plan

## Selected architecture

Xiaopu will use a Codex-like session/turn/event runtime, Claude Code-like progressive capability loading and bounded tool-result context, and Xiaopu's CEGAR-H controller plus native PowerPoint artifact/evidence plane.

The implementation must preserve the theory contract in `research/THEORY.md`: runtime meta-actions are selected by estimated gain minus cost, latency, and residual risk; every mutation advances the artifact epoch; completion requires fresh evidence for the current epoch.

## Non-negotiable requirements

- CEGAR-H must execute in the production harness, not exist only as a prompt or simulator.
- Repeated observation without new information must be detected semantically.
- A source presentation has one stable working artifact per run; reopening it is idempotent.
- Context compaction must retain facts, obligations, artifact identity, failures, and evidence.
- Tool visibility must be progressive and phase-aware.
- Interrupt, budget exhaustion, completion, and failure are typed runtime outcomes rather than repeated tool errors.
- PPT mutations and verification remain native so mutation epochs and evidence scopes cannot drift across plugins.
- Skills provide workflows; MCP/plugins provide external integrations, not core artifact ownership.

## Implementation sequence

1. Introduce typed runtime phases, turn outcomes, progress signals, and a richer belief state.
2. Connect the CEGAR-H meta-action scorer to real execution decisions.
3. Add read-result caching, semantic no-progress detection, and bounded context fragments.
4. Add an idempotent artifact manager and connect it to PPT open/save/mutation handling.
5. Make tool exposure phase-aware while preserving policy and permission guards.
6. Make trajectory recording bounded, deduplicated, and safe under parallel read calls.
7. Add regression tests reproducing the HTML-report failure pattern.
8. Run focused and full test suites; record any compatibility boundary.

## Acceptance contract

- `choose_meta_action` is called on the real harness path.
- An unchanged file is physically read at most once per run for an equivalent request.
- Opening an original deck, its working copy, or the same original again resolves to one working artifact.
- Repeated low-information observations trigger a controlled transition, not hundreds of calls.
- Tool outputs stored in model context are bounded while full outputs remain in trajectory/artifact storage.
- Mutating after verification invalidates previous evidence.
- Finish is admitted only with current-epoch evidence required by the task.
- Existing provider, benchmark, and TUI entry points remain compatible.

## Implemented architecture decision

The runtime is now split into four cooperating planes:

1. **Session/control plane (Codex-aligned):** typed session/turn outcomes, runtime events, cancellation, permission boundaries, phase-aware tool routing, and compact state retention.
2. **Capability plane (Claude Code-aligned):** progressively loaded skills, bounded model-visible tool results, deterministic preflight context, and structured stop/failure reasons.
3. **Artifact/evidence plane (Xiaopu-native):** ContentIR, stable editable PPT working copies, semantic PPT operations, mutation epochs, structural/render/pixel certificates, automatic source provenance, and contract-owned output paths.
4. **Adaptive controller (CEGAR-H):** compare the expected value of more observation/computation against cost, latency, and residual risk; force production when observation novelty collapses; allow at most targeted repair; finish only with fresh current-epoch evidence.

Core PPT lifecycle mechanics are native rather than plugins. Skills define reusable workflows and plugins/MCP remain the extension boundary for external systems. This prevents artifact identity, provenance, verification epochs, and completion gates from drifting across optional integrations.

## Real acceptance result

The previously failing `html-report-quadrant-ppt` trajectory made 1,660 tool calls over 1,714 seconds and produced no final artifact. The final acceptance run (`architecture_acceptance_live_v14.jsonl`) completed in 31.837 seconds with four model tool calls:

`compose_quadrant_slide → save_deck → ppt_verify → finish`

`finish` then automatically obtained real PowerPoint render and deterministic visual evidence. The run produced the contract path, fresh structural/render/visual certificates, eight source-provenance bindings, and a refreshed task trajectory. This is a single-task engineering acceptance result, not a cross-system superiority claim.

## Source-reference discipline

- Codex references guide runtime separation, tool routing, bounded history, interrupt, and sandbox boundaries.
- Claude Code references guide progressive skill loading, abort propagation, structured stop reasons, and large tool-result replacement.
- Xiaopu theory and domain evidence determine meta-action selection, artifact epochs, verifier choice, repair, and completion.
- Source-backed product mechanisms and trajectory-inferred PPT policies remain explicitly distinguished.
