"""Regression tests for multi-scenario interactive reuse of one Harness."""
from pathlib import Path
from unittest.mock import patch

from agent.harness import Harness
from agent.state import RunState


def test_open_deck_does_not_force_every_later_question_into_ppt():
    h = Harness.__new__(Harness)
    h.deck = object()
    assert h._is_ppt_task("你是什么模型") is False
    assert h._is_ppt_task("继续") is True
    assert h._is_ppt_task("把第 2 页标题改成绿色") is True


def test_task_local_facts_are_cleared_between_unrelated_tasks():
    h = Harness.__new__(Harness)
    h.state = RunState()
    h.state.facts.update({
        "task_root": "tasks/xmind-screenshot-template-ppt",
        "official_evaluator": "tasks/xmind-screenshot-template-ppt/tests/grading/test_verify.py",
        "official_evaluator_present": "true",
        "required_output_pptx": "tasks/xmind-screenshot-template-ppt/output/community_sustainability_workshop_deck.pptx",
        "ppt_input_deck": "tasks/xmind-screenshot-template-ppt/input/template/community_workshop_green_template.pptx",
        "source:input/01.html": "sha256=abc",
        "preflight:some-task": "done",
        "keep_me": "yes",
    })
    h.state.verification_contract_terms = {"required_slide_expectations": {}}
    h.state.content_brief = "old brief"
    h.state.unresolved_checks.update({"task_evaluator", "ppt_contract"})
    h.state.repair_attempts = 2
    h.task_spec = object()
    h._clear_task_facts()
    assert "task_evaluator" not in h.state.unresolved_checks
    assert "ppt_contract" not in h.state.unresolved_checks
    assert h.state.repair_attempts == 0
    assert "official_evaluator" not in h.state.facts
    assert "official_evaluator_present" not in h.state.facts
    assert "required_output_pptx" not in h.state.facts
    assert "task_root" not in h.state.facts
    assert "source:input/01.html" not in h.state.facts
    assert "preflight:some-task" not in h.state.facts
    assert h.state.facts.get("keep_me") == "yes"
    assert h.state.verification_contract_terms == {}
    assert h.state.content_brief == ""
    assert h.task_spec is None


def test_stale_evaluator_path_clears_instead_of_stucking():
    h = Harness.__new__(Harness)
    h.state = RunState()
    h.state.facts["official_evaluator"] = "tasks/gone/tests/grading/test_verify.py"
    h.state.facts["official_evaluator_present"] = "true"
    h.state.unresolved_checks.add("task_evaluator")
    with patch("agent.tools.lifecycle_tools.config.sandbox_root", return_value=Path("E:/project/agent/xiaopu/workspace/iteration_runs")):
        from agent.tools.lifecycle_tools import _run_task_evaluator
        result = _run_task_evaluator(h)
    assert "stale evaluator facts were cleared" in result
    assert "official_evaluator" not in h.state.facts
    assert "task_evaluator" not in h.state.unresolved_checks
