---
name: powerpoint
description: Create, modify, restyle, render, and verify PPT or PowerPoint slide decks and presentations.
when_to_use: Use for PPT, PPTX, PowerPoint, slide deck, presentation, layout repair, or rendering tasks.
allowed_tools: ppt_open, ppt_inspect, ppt_edit_text, ppt_style, ppt_compose, ppt_save, ppt_check, ppt_arrange, ppt_metadata, ppt_notes, finish
---

# PowerPoint workflow

1. Use the harness-provided ContentIR brief as the authoritative task scope. Do not rediscover or reread sources already listed there.
2. For an existing deck, call `ppt_open`, then `ppt_inspect` only for the affected scope. The harness preserves the original.
3. Atomic edits execute directly. Only multi-page or multi-source synthesis needs a compact slide-role outline. Use `ppt_edit_text`, `ppt_style`, or the one matching `ppt_compose` kind; do not recreate them with scripts or many primitives.
4. Keep one main message per slide. Prefer short labels and evidence over paragraphs.
5. Call `ppt_save`, then `ppt_check`, then `finish`. Finish owns task-native evaluation, final rendering, visual audit, provenance, and trajectory completion.
6. Repair only concrete defects on specific slides/shapes, remain within the repair budget, and rerun the failed check after every repair.
7. Low-level PPT primitives, evaluator invocation, rendering and provenance are harness-owned. They are not part of the normal model-facing tool surface.
8. Finish only with a saved final PPTX, fresh structural evidence, applicable render/pixel evidence, the output path, slide count, checks performed, provenance, and any renderer limitation.
