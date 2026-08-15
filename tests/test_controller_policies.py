import pytest

from agent.controller_policies import PolicyGuard, eligible_meta_actions, policy_instruction, resolve_policy
from agent.deliberation import MetaAction
from agent.state import RunState
from agent.tools.registry import select_tools


def test_four_policy_action_sets_are_distinct_and_preregistered():
    actions = [MetaAction("d", 1, kind="direct"), MetaAction("e", 1, kind="evidence"),
               MetaAction("c", 1, kind="compute"), MetaAction("j", 1, kind="joint")]
    assert [x.name for x in eligible_meta_actions("direct", actions)] == ["d"]
    assert [x.name for x in eligible_meta_actions("evidence_only", actions)] == ["d", "e"]
    assert [x.name for x in eligible_meta_actions("cegar_h", actions)] == ["d", "e", "c", "j"]
    assert resolve_policy("always_verify").verify_after_every_mutation is True


def test_direct_forbids_mutation_after_terminal_verification():
    guard = PolicyGuard("direct")
    state = RunState()
    guard.before_tool("add_slide", state)
    guard.before_tool("ppt_verify", state)
    with pytest.raises(RuntimeError, match="terminal verification"):
        guard.before_tool("add_slide", state)


def test_always_verify_requires_fresh_evidence_between_mutations():
    guard = PolicyGuard("always_verify")
    state = RunState()
    guard.before_tool("add_slide", state)
    state.record_change("deck:add_slide")
    with pytest.raises(RuntimeError, match="fresh structural, render, and pixel evidence"):
        guard.before_tool("add_textbox", state)
    state.record_evidence("ppt_structural", "pass")
    with pytest.raises(RuntimeError, match="structural, render, and pixel"):
        guard.before_tool("add_textbox", state)
    state.record_evidence("ppt_render", "pass")
    state.record_evidence("ppt_visual", "pass")
    guard.before_tool("add_textbox", state)


def test_policy_compute_caps_operationalize_adaptive_compute():
    assert resolve_policy("direct").max_model_steps == 25
    assert resolve_policy("always_verify").max_model_steps == 25
    assert resolve_policy("evidence_only").max_model_steps == 25
    assert resolve_policy("cegar_h").max_model_steps == 50
    assert "terminal verification" in policy_instruction("direct")
    assert "structural verification" in policy_instruction("always_verify")
    assert "do not request extra compute" in policy_instruction("evidence_only")
    assert "Adaptively allocate" in policy_instruction("cegar_h")


def test_chinese_ppt_markers_select_presentation_tools():
    for task in ("制作演示文稿", "修改幻灯片", "进行PPT排版"):
        names = {item["function"]["name"] for item in select_tools(task)}
        assert "ppt_open" in names
        assert "ppt_check" in names
        assert "new_deck" not in names
