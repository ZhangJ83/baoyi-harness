"""Deterministic end-to-end PPT harness demonstration.

Creates, modifies, lays out, verifies, saves, and (when available) renders a
deck. The trace records the stale-evidence intervention explicitly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agent.state import RunState
from agent.tools.registry import dispatch


class DemoHarness:
    def __init__(self) -> None:
        self.state = RunState(goal="create and refine a PPT harness architecture deck")
        self.deck = None


def call(harness: DemoHarness, name: str, arguments: dict) -> dict:
    before = harness.state.mutation_epoch
    output = dispatch(name, json.dumps(arguments, ensure_ascii=False), harness)
    return {
        "tool": name,
        "arguments": arguments,
        "output": output,
        "epoch_before": before,
        "epoch_after": harness.state.mutation_epoch,
        "fresh_evidence": [record.kind for record in harness.state.fresh_evidence()],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "workspace" / "results" / "ppt_harness_demo"
    output.mkdir(parents=True, exist_ok=True)
    os.environ["WORKSPACE"] = str(output)
    h = DemoHarness()
    trace: list[dict] = []
    trace.append(call(h, "new_deck", {"title": "Evidence-Aware PPT Harness", "subtitle": "From generic agent loop to render-feedback workflow"}))
    trace.append(call(h, "add_two_column_slide", {
        "title": "What competitors provide — and omit",
        "left_title": "Reusable harness primitives",
        "left_bullets": ["Typed tools and permissions", "Skills/rules and context", "Hooks, MCP, checkpoints"],
        "right_title": "Document-specific gap",
        "right_bullets": ["No slide semantics", "No render-inspect contract", "No mutation-scoped evidence"],
    }))
    trace.append(call(h, "add_process_slide", {
        "title": "Reconstructed office-document loop",
        "steps": [
            {"title": "Inspect", "detail": "Deck, shapes, sources"},
            {"title": "Plan", "detail": "Slide roles and constraints"},
            {"title": "Mutate", "detail": "Typed deck operations"},
            {"title": "Render", "detail": "PNG visual evidence"},
            {"title": "Repair", "detail": "Targeted re-layout"},
        ],
        "takeaway": "Every mutation invalidates earlier evidence.",
    }))
    trace.append(call(h, "add_metric_slide", {
        "title": "Current implementation evidence",
        "metrics": [
            {"value": "71", "label": "tests passed", "detail": "full regression"},
            {"value": "4", "label": "edit primitives", "detail": "move, resize, delete, reorder"},
            {"value": "3", "label": "evidence tiers", "detail": "structural, render, pixel"},
        ],
        "takeaway": "Pixel checks are reliability gates, not aesthetic judges.",
    }))
    trace.append(call(h, "ppt_verify", {}))
    evidence_epoch = h.state.mutation_epoch
    title_shape = next(shape for shape in h.deck.slides[1].shapes if shape.has_text_frame and shape.text_frame.text == "What competitors provide — and omit")
    trace.append(call(h, "set_shape_geometry", {"slide_number": 2, "shape_id": title_shape.shape_id, "x": 0.75, "y": 0.30, "w": 11.8, "height": 0.7}))
    stale_rejected = not h.state.fresh_evidence() and h.state.mutation_epoch > evidence_epoch
    trace.append(call(h, "ppt_verify", {}))
    trace.append(call(h, "save_deck", {"path": "ppt-harness-demo.pptx"}))
    # Saving is a mutation; verify once more so the persisted artifact has
    # evidence from its current epoch.
    trace.append(call(h, "ppt_verify", {}))
    renderer = {"available": False, "output": "not attempted"}
    try:
        render_step = call(h, "render_deck", {"path": "ppt-harness-demo.pptx", "output_dir": "rendered"})
        trace.append(render_step)
        visual_step = call(h, "inspect_rendered_deck", {"output_dir": "rendered"})
        trace.append(visual_step)
        renderer = {"available": True, "output": visual_step["output"]}
    except Exception as exc:  # stable evidence of an environment limitation
        renderer = {"available": False, "output": f"{type(exc).__name__}: {exc}"}
    report = {
        "kind": "ppt_harness_end_to_end_demo",
        "artifact": str(output / "ppt-harness-demo.pptx"),
        "slides": len(h.deck.slides),
        "stale_evidence_intervention": {
            "evidence_epoch": evidence_epoch,
            "post_edit_epoch": evidence_epoch + 1,
            "old_evidence_rejected": stale_rejected,
        },
        "renderer": renderer,
        "final_epoch": h.state.mutation_epoch,
        "final_fresh_evidence": [record.kind for record in h.state.fresh_evidence()],
        "trace": trace,
    }
    (output / "demo-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "trace"}, ensure_ascii=False, indent=2))
    return 0 if stale_rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
