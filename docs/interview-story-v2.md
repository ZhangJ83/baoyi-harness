# Interview story: how I built an evidence-aware PPT agent harness

## One-minute version

I began by reverse-engineering the reusable control patterns in Claude Code, Cursor, and Codex rather than copying their UI. Claude Code suggested a typed tool loop with permissions, hooks, skills, resumable state, and compaction. Cursor highlighted context selection, client-side tools, parallel apply, review, and checkpoints. Codex showed how to separate repeatable workflow knowledge in skills from external capabilities in MCP-backed plugins.

The gap was that these are general-purpose agent designs. For PowerPoint, writing a file is not task completion: the deck may overflow, render blank, lose content outside the slide, or be modified after a passing check. I therefore built Xiaopu around an artifact state machine. It inspects before editing, uses stable slide and shape identifiers, supports semantic layouts and precise edit operations, increments a mutation epoch after every edit, and accepts only verification evidence produced for the current epoch. The loop saves, structurally verifies, renders to PNG, performs a deterministic pixel audit, and then supports targeted repair and re-verification.

## Step-by-step narrative

1. **Mapped the competitors by mechanism.** I separated documented behavior, locally observed protocol/source structure, and my own inference so I would not overclaim hidden implementation details.
2. **Converted coding-agent primitives into document primitives.** Read/edit/test became deck inventory, semantic slide construction, shape-level mutation, structural verification, rendering, and visual review.
3. **Chose a hybrid extension architecture.** Stateful deck mutations stay in the core harness; workflow guidance is a PowerPoint skill; cloud data, image generation, storage, and review can be MCP/plugin integrations.
4. **Built the basic agent loop.** The model calls typed tools; the harness validates schemas, checks permissions and budgets, executes tools, records observations, compacts context, and blocks repeated no-progress actions.
5. **Added document-aware state.** Each mutation increments an epoch. Old evidence remains in the audit trail but cannot discharge the current completion contract.
6. **Implemented creation and editing.** The harness supports cover, content, comparison, metric, table, process, and image layouts, plus open, inventory, text replacement, geometry changes, deletion, and reordering.
7. **Reconstructed the omitted verification loop.** Saving is followed by structural checks, PNG rendering, deterministic blank/edge checks, and semantic review when available.
8. **Tested failure cases, not only happy paths.** Regression tests check that an edit invalidates earlier evidence and that rendered-pixel checks create fresh visual evidence only after passing.
9. **Kept claims bounded.** Structural and pixel heuristics are reliability gates, not aesthetic judges; benchmark pilots are not superiority results.

## Why this design is defensible

- Compared with a pure Claude-Code-style generic loop, it adds artifact semantics and evidence freshness.
- Compared with Cursor-style checkpoints alone, it distinguishes recoverability from correctness.
- Compared with putting everything in a plugin, it keeps low-latency stateful mutations and evidence provenance in one trusted local boundary.
- Compared with a monolithic PPT script, it remains extensible through skills and MCP/plugin adapters.

## Honest limitations

- Pixel heuristics cannot judge storytelling or aesthetics.
- Full visual quality requires blinded human review or a calibrated vision evaluator.
- Small benchmark pilots demonstrate operability, not competitor superiority.
- Complete instrumentation is required for mutation-epoch guarantees.

