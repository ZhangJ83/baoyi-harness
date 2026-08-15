# Xiaopu evidence-aware PPT harness: final implementation report

Date: 2026-08-10

## Outcome

Xiaopu now implements a local, provider-neutral harness for PowerPoint creation, modification, layout repair, structural verification, rendering, and rendered-pixel auditing. Its distinguishing mechanism is mutation-scoped evidence: every deck edit increments an epoch, and verification from an older epoch cannot justify completion.

The implementation is derived from a mechanism-level study of Claude Code, Cursor, and Codex, while explicitly reconstructing document-specific stages that generic coding-agent descriptions omit. Competitor facts, locally observed structures, and Xiaopu inferences are separated in `docs/competitive-harness-ppt.md`.

## Delivered architecture

### Generic harness layer

- provider-neutral chat/tool loop;
- typed JSON tool schemas and validation;
- permissions and sandboxed paths;
- pre/post tool hooks;
- dynamic skill loading;
- tool/turn/token budgets;
- parallel read-only calls;
- repeated-action circuit breaker;
- context compaction with durable task/evidence state.

### PowerPoint artifact layer

- create and open decks;
- cover, content, comparison, metric, table, process, image, and freeform layouts;
- slide/shape inventory with stable ids and geometry;
- text replacement with primary style preservation;
- shape move/resize and deletion;
- slide deletion and reordering;
- save with workspace path enforcement;
- structural overflow, boundary, empty-box, and overlap checks;
- PowerPoint/LibreOffice rendering adapters;
- deterministic blank-render and edge-content pixel audit;
- PowerPoint workflow skill.

### Evidence layer

- every edit records a mutation epoch transition;
- structural, render, and pixel evidence records carry the epoch;
- evidence from before the last mutation remains auditable but is not fresh;
- renderer failure is reported as an environment limitation rather than converted into a passing visual check.

## Verified results

### Regression suite

- 71 tests passed;
- 2 tests skipped;
- focused PPT/evidence suite: 10 passed;
- new tests cover geometry editing, slide movement/deletion, stale-evidence invalidation, and rendered-pixel evidence.

### End-to-end deck demonstration

Artifact: `workspace/results/ppt_harness_demo/ppt-harness-demo.pptx`

- four slides created using multiple semantic layouts;
- one existing shape repositioned through a stable shape id;
- structural evidence collected before the edit became stale after the edit;
- `old_evidence_rejected: true` in `demo-report.json`;
- fresh structural verification collected after saving;
- deterministic scorer: 1.0 for opens, minimum slide count, required text, and slide-boundary geometry.

## Rendered evidence and remaining limitation

After starting the local Docker Desktop engine, the pinned local
`xiaopu-ppt-render:mini` image produced a PDF and four genuine PNG slide
renders. The montage was manually inspected and the deterministic pixel audit
passed. Two slides report edge-content warnings because full-bleed theme
backgrounds touch the edge; this is informational because geometric clipping is
already checked structurally.

Therefore:

- structural correctness is verified;
- mutation freshness is verified;
- PDF/PNG rendering is verified;
- rendered-pixel audit is verified;
- the montage was manually inspected;
- aesthetic quality beyond this inspection is still not claimed.

## Why the hybrid architecture was chosen

Purely hard-coding the office workflow makes integrations rigid. Putting every operation behind a remote plugin loses low-latency in-memory state and weakens provenance between an edit and its evidence. Xiaopu therefore uses:

- core tools for stateful deck mutations and evidence;
- a skill for repeatable PowerPoint workflow guidance;
- MCP/plugin boundaries for external content, cloud storage, asset generation, remote renderers, and optional review UI.

This follows OpenAI's documented distinction between skill instructions and MCP-backed tools while retaining the artifact safety properties needed for office documents.

## Claim boundary

Supported:

- the harness performs the implemented PPT operations;
- edits invalidate earlier evidence;
- structural and deterministic pixel gates are executable and tested;
- the final demo passes deterministic structural scoring.

Not supported:

- aesthetic superiority;
- better performance than Claude Code, Cursor, or Codex;
- a full PPT benchmark score;
- broad aesthetic superiority or human preference beyond the inspected demo.

## Reproduction

From the repository root:

```powershell
python -m pytest -q --basetemp .pytest_tmp_full
python experiments/ppt_harness_demo.py
python benchmarks/ppt_score.py workspace/results/ppt_harness_demo/ppt-harness-demo.pptx --min-slides 4 --required-text Evidence-Aware --required-text render-feedback
```

The checked-in demo already includes PNGs, PDF, montage, and
`rendered-audit.json` under `workspace/results/ppt_harness_demo/rendered`.
The machine-readable completion audit now records this as a
`controlled_rendered_demo` while keeping full model-generated PPTBench status
separate.
