---
name: powerpoint
description: Create, modify, restyle, render, and verify PPT or PowerPoint slide decks and presentations.
when_to_use: Use for PPT, PPTX, PowerPoint, slide deck, presentation, layout repair, or rendering tasks.
allowed_tools: ppt_open, ppt_inspect, ppt_edit_text, ppt_style, ppt_compose, ppt_save, ppt_check, ppt_arrange, ppt_metadata, ppt_notes, finish
---

# PowerPoint workflow

1. Use the harness-provided ContentIR brief as the authoritative task scope. Do not rediscover or reread sources already listed there.
2. For an existing deck, call `ppt_open`, then `ppt_inspect` for the affected scope. The harness preserves the original.
3. For a new deck, call `ppt_compose(kind="new_deck")` then compose each page using the semantic layout that best matches its intent:
   - **Process / Workflow / Architecture**: Use `ppt_compose(kind="workflow_pipeline", title="...", steps=[{"title": "...", "action": "...", "bullets": [...], "tag": "..."}], takeaway="...")` with 3-6 step cards, step badges `01, 02`, action highlights, and detail bullets. Never use plain text bullet lists for workflows.
   - **Direct HTML / CSS Vector Slide**: Use `ppt_compose(kind="html_slide", slide_number=N, html="<div class='slide'><div class='grid'><div class='card'><span class='badge'>ACTIVE</span><h3>01. 感知与意图</h3><p>• 详细要点 1</p><p>• 详细要点 2</p></div>...</div></div>")` or write `.html` files and use `ppt_compose(kind="from_html", slide_number=N, file_path="slide.html")` to compile modern web layouts directly into 100% native vector editable PowerPoint cards, badges, and text boxes.
   - **HTML / Web UI / System Console Mockup**: Use `ppt_compose(kind="html_mockup", title="...", cards=[{"title": "...", "status": "ACTIVE", "metric": "...", "bullets": [...], "html_anchor": "..."}], url_bar="...")` to render authentic browser window chrome (🔴🟡🟢), navigation sidebar, and card grids.
   - **Keynote / Core Highlight**: Use `ppt_compose(kind="hero_split", title="...", hero_title="...", hero_metric="...", hero_text="...", cards=[...])` for left 1/3 key takeaway + right 2/3 breakdown cards.
   - **Multi-Metric Dashboard**: Use `ppt_compose(kind="quadrant", title="...", quadrants=[...])` for 2x2 executive dashboards.
   - **Comparison / Pros & Cons**: Use `ppt_compose(kind="comparison", title="...", left_title="...", left_bullets=[...], right_title="...", right_bullets=[...])`.
4. High Design Quality & Canvas Coverage Standards:
   - **No Bare Bullet Lists & Balanced Space Utilization**: Every content slide must use visual container cards, badges, or structured grids. Plain single-column bullet lists on blank backgrounds or clustered in one corner leaving large unused space fail quality & density gates.
   - **Geometric Coverage & Span Standards**: Content slides should achieve meaningful canvas coverage (body coverage >= 50%, horizontal span >= 72%, vertical span >= 60%). Redistribute content across grids, 2-column, quadrant, or hero_split layouts rather than leaving large whitespace voids.
   - **Substantive Content over Filler**: Content slides should convey rich, structured technical information. Never invent repetitive filler text merely to occupy space—achieve layout density through proper typography, card expansion, visual containers, and multi-column structure.
   - Use slide-numbered compose (`slide_number=1`) to transform fresh deck cover scaffolds into real content pages when multi-page custom builds are requested.
5. Call `ppt_save`, then `ppt_check`, then `finish`. Finish owns task-native evaluation, final rendering, visual audit, provenance, and trajectory completion.
6. Repair only concrete defects on specific slides/shapes, remain within the repair budget, and rerun the failed check after every repair.
7. Low-level PPT primitives, evaluator invocation, rendering and provenance are harness-owned.
8. Finish only with a saved final PPTX, fresh structural evidence, applicable render/pixel evidence, the output path, slide count, checks performed, provenance, and any renderer limitation.

