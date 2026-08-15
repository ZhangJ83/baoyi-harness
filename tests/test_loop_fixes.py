"""Loop regressions for the quick5 findings.

1. A failed repair attempt must not consume the bounded repair budget.
2. A safety pause must persist any unsaved in-memory draft before stopping.
"""
from __future__ import annotations

import json

import pytest
from pptx import Presentation

from agent.state import RunState
from agent.tools.registry import dispatch


class DummyHarness:
    def __init__(self):
        self.state = RunState()
        self.deck = None


def _deck_with_one_shape():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(914400, 914400, 914400 * 2, 914400)
    box.text_frame.text = "keep"
    return prs, box.shape_id


def test_failed_repair_does_not_consume_budget():
    h = DummyHarness()
    h.deck, _ = _deck_with_one_shape()
    h.state.unresolved_checks.add("ppt_structural")
    h.state.max_repairs = 1

    with pytest.raises(Exception):
        dispatch("ppt_arrange", json.dumps({
            "operation": "delete_shape", "slide_number": 1, "shape_id": 99999,
        }), h)
    assert h.state.repair_attempts == 0


def test_successful_repair_consumes_budget_once_then_blocks():
    h = DummyHarness()
    deck, shape_id = _deck_with_one_shape()
    second = deck.slides[0].shapes.add_textbox(914400, 914400, 914400 * 2, 914400)
    second.text_frame.text = "drop"
    h.deck = deck
    h.state.unresolved_checks.add("ppt_structural")
    h.state.max_repairs = 1

    dispatch("ppt_arrange", json.dumps({
        "operation": "delete_shape", "slide_number": 1, "shape_id": shape_id,
    }), h)
    assert h.state.repair_attempts == 1

    with pytest.raises(RuntimeError, match="repair budget exhausted"):
        dispatch("ppt_arrange", json.dumps({
            "operation": "delete_shape", "slide_number": 1, "shape_id": second.shape_id,
        }), h)


def test_save_draft_before_pause_persists_in_memory_deck(tmp_path, monkeypatch):
    from agent.harness import Harness

    h = Harness.__new__(Harness)
    h.state = RunState()
    h.deck, _ = _deck_with_one_shape()
    h.state.facts["required_output_pptx"] = "tasks/demo/output/final.pptx"
    h.state.record_change("deck:edit")
    monkeypatch.setattr("agent.config.sandbox_root", lambda: tmp_path)

    saved = h._save_draft_before_pause()
    assert saved == "tasks/demo/output/final.pptx"
    assert (tmp_path / "tasks" / "demo" / "output" / "final.pptx").is_file()


def test_save_draft_before_pause_is_noop_without_mutation():
    from agent.harness import Harness

    h = Harness.__new__(Harness)
    h.state = RunState()
    h.deck, _ = _deck_with_one_shape()
    assert h._save_draft_before_pause() == ""
