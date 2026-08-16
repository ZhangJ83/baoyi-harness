---
name: powerpoint
description: Create, modify, restyle, render, and verify PPT or PowerPoint slide decks and presentations.
when_to_use: Use for PPT, PPTX, PowerPoint, slide deck, presentation, layout repair, or rendering tasks.
allowed_tools: ppt_open, ppt_inspect, ppt_edit_text, ppt_style, ppt_compose, ppt_save, ppt_check, ppt_arrange, ppt_metadata, ppt_notes, finish
---

# PowerPoint workflow

1. Use the harness-provided ContentIR brief as the authoritative task scope. Do not rediscover or reread sources already listed there.
2. For an existing deck, call `ppt_open`, then `ppt_inspect` for the affected scope. The harness preserves the original.
3. For a new deck, call `ppt_compose(kind="new_deck")` then add slides with `ppt_compose` using the layout that best matches each page's content (flowchart, quadrant, comparison, content, table).
4. Make every slide content-rich:
   - Include 3-8 substantive bullet points per content slide
   - Each bullet can be a full sentence or phrase with concrete details
   - Use comparison layouts for pros/cons or feature comparisons
   - Use quadrant layouts for dashboards or multi-metric views
   - Use flowchart layouts for process or architecture diagrams
5. Call `ppt_save`, then `ppt_check`, then `finish`. Finish owns task-native evaluation, final rendering, visual audit, provenance, and trajectory completion.
6. Repair only concrete defects on specific slides/shapes, remain within the repair budget, and rerun the failed check after every repair.
7. Low-level PPT primitives, evaluator invocation, rendering and provenance are harness-owned. They are not part of the normal model-facing tool surface.
8. Finish only with a saved final PPTX, fresh structural evidence, applicable render/pixel evidence, the output path, slide count, checks performed, provenance, and any renderer limitation.
