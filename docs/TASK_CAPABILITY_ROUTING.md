# Task capability routing and balanced execution display

## Design claim

Xiaopu does not expose private model chain-of-thought. It exposes an auditable
execution stream: task profile, phase, controller decision, model response
signal, tool result, verification, repair, and termination evidence.

This is the right comparison unit for a harness because it separates what the
model proposed from what the runtime actually allowed and what the artifact
proved.

## Claude Code source-grounded abstraction

The local Claude Code source was inspected for three reusable ideas:

1. A task/skill catalog has a description and an applicability rule.
2. A selected skill can constrain its allowed tools.
3. Skill bodies are loaded on demand, while the tool-use loop keeps tool calls
   and tool results as separate stream events.

Xiaopu implements the same general control idea, without claiming to copy
internal proprietary behavior:

| Source-grounded idea | Xiaopu implementation |
| --- | --- |
| Task/skill catalog | `agent/task_profiles.py` and `TaskProfile` |
| Applicability rule | marker-based `classify_task()` |
| Capability route | profile capabilities plus phase tool routing |
| Allowed-tool envelope | `RuntimeController.tool_names_for_phase()` |
| Separate stream events | `agent/events.py` and `EventBus` |
| On-demand task context | preflight ContentIR and dynamically selected skills |

## Five PPT profiles

- `edit_existing`: preserve unrelated slides, target shapes, make the smallest
  native edit, then verify.
- `create_deck`: compose semantic slide layouts with restrained density and
  traceable source material.
- `layout_reflow`: preserve required content, use geometry first, repair
  overlap before shrinking typography.
- `source_grounded`: bind claims to supplied sources, use semantic layouts, and
  keep provenance in notes/trajectory rather than decorative slide text.
- `repair_deck`: diagnose one concrete defect, apply a bounded repair, and rerun
  the affected check.

The profile is an adaptive capability route, not a fixed script. It is stored
in runtime state and in the recorder so later trajectory analysis can compare
routes across agents.

## Balanced terminal display

The default `/process balanced` view is intentionally compact:

```text
Task profile
  capabilities / verification / design policy
Decision
Model turn
  tool calls requested, or no-tool response with evidence guard
Tool result
Phase change
Run summary
```

`/process hidden` suppresses the stream, `/process summary` keeps compact tool
results, and `/process detail` keeps the expanded tool result lines. The UI
never renders raw hidden reasoning content; the displayed reasoning signal is
only a count and an auditable controller summary.

## PPT quality gate

`ppt_quality_check` is a deterministic pre-visual lint. It reports structured
JSON evidence for slide boundaries, text-to-object overlap, shape density, and
very small text. Warnings do not automatically fail a deck; blocking geometry
findings do. This complements `ppt_verify`, `render_deck`, and
`inspect_rendered_deck` rather than pretending to replace semantic or
aesthetic human review.

## Why this is a harness design

The capability catalog is not just a prompt template. It changes the runtime's
state, phase-specific tool envelope, evidence requirements, recorder fields,
and terminal stream. The same task can therefore be compared at four layers:

```text
task classification -> capability route -> execution envelope -> evidence gate
```

That makes the design testable and lets a future benchmark compare tool
selection, verification behavior, repair loops, and stop conditions instead of
only comparing the final PPTX.
